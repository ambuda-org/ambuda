"""Background tasks for running batch LLM prompts and storing results as suggestions."""

import logging

from ambuda import consts
from ambuda import database as db
from ambuda.models.proofing import SuggestionStatus
from ambuda.tasks import app
from ambuda.tasks.utils import get_db_session
from ambuda.utils import llm_structuring, reconciliation_check
from ambuda.utils.xml_validation import validate_proofing_xml, ValidationType

LOG = logging.getLogger(__name__)


# Truncate output snippets stored on the failure result so the Celery
# result payload doesn't grow unbounded.
_SNIPPET_MAX_CHARS = 240


def _snippet(text: str | None) -> str:
    if not text:
        return ""
    text = text.strip()
    if len(text) <= _SNIPPET_MAX_CHARS:
        return text
    return text[:_SNIPPET_MAX_CHARS] + "…"


@app.task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=10,
    retry_backoff_max=60,
    retry_jitter=True,
    max_retries=1,
)
def run_batch_llm(
    self,
    *,
    app_env: str,
    project_slug: str,
    page_slugs: list[str],
    prompt_template: str,
    batch_id: str,
):
    """Run an LLM prompt over all pages in a single API call, then create suggestions.

    On transient failure, retries the whole batch once. The task result
    includes per-page failure reasons so the user can see why pages were
    skipped.
    """
    with get_db_session(app_env) as (session, query, config_obj):
        bot_user = query.user(consts.BOT_USERNAME)
        if not bot_user:
            raise ValueError(f'User "{consts.BOT_USERNAME}" is not defined.')

        api_key = config_obj.GEMINI_API_KEY
        if not api_key:
            raise ValueError("GEMINI_API_KEY not configured")

        project = query.project(project_slug)

        # Single bulk fetch for all pages with their revisions.
        pages_in_db = query.pages_with_revisions(project.id, page_slugs)
        page_by_slug = {p.slug: p for p in pages_in_db}

        page_contents: dict[str, str] = {}
        page_meta: dict[str, tuple[db.Page, db.Revision]] = {}
        failures: list[dict] = []

        for slug in page_slugs:
            page = page_by_slug.get(slug)
            if page is None:
                failures.append({"slug": slug, "reason": "Page not found."})
                continue
            if not page.revisions:
                failures.append({"slug": slug, "reason": "Page has no revisions."})
                continue
            latest = page.revisions[-1]
            if not latest.content:
                failures.append({"slug": slug, "reason": "Latest revision is empty."})
                continue
            page_contents[slug] = latest.content
            page_meta[slug] = (page, latest)

        if not page_contents:
            raise ValueError(f"No pages with content found for {project_slug}")

        # Single LLM call for all pages. Parse errors don't trigger retry —
        # re-running won't fix bad model output. Surface the diagnostic to the
        # user instead of silently marking every page as "no output".
        try:
            results = llm_structuring.run_batch(page_contents, api_key, prompt_template)
        except llm_structuring.BatchParseError as e:
            LOG.warning("Batch LLM parse error: %s", e)
            session.commit()
            return {
                "created": 0,
                "skipped": len(page_slugs),
                "total": len(page_slugs),
                "failures": [
                    {
                        "slug": "(batch)",
                        "reason": str(e),
                        "snippet": e.snippet,
                    }
                ],
            }

        explanation = prompt_template[:100].strip()
        if len(prompt_template) > 100:
            explanation += "..."

        is_reconciliation = "<gold-standard>" in prompt_template

        created = 0
        for slug, (page, latest_revision) in page_meta.items():
            if slug not in results:
                failures.append(
                    {"slug": slug, "reason": "LLM returned no output for this page."}
                )
                continue

            llm_output = results[slug]

            validation_errors = validate_proofing_xml(llm_output)
            errors = [r for r in validation_errors if r.type == ValidationType.ERROR]
            if errors:
                error_msgs = "; ".join(r.message for r in errors[:3])
                LOG.warning(
                    "LLM output failed XML validation for %s/%s: %s",
                    project_slug,
                    slug,
                    error_msgs,
                )
                failures.append(
                    {
                        "slug": slug,
                        "reason": f"XML validation failed: {error_msgs}",
                        "snippet": _snippet(llm_output),
                    }
                )
                continue

            if is_reconciliation:
                layout_problems = reconciliation_check.check_layout_preserved(
                    page_contents[slug], llm_output
                )
                if layout_problems:
                    reason = "; ".join(layout_problems)
                    LOG.warning(
                        "Reconciliation layout check failed for %s/%s: %s",
                        project_slug,
                        slug,
                        reason,
                    )
                    failures.append(
                        {
                            "slug": slug,
                            "reason": f"Layout not preserved: {reason}",
                            "snippet": _snippet(llm_output),
                        }
                    )
                    continue

            suggestion = db.Suggestion(
                project_id=project.id,
                page_id=page.id,
                revision_id=latest_revision.id,
                user_id=bot_user.id,
                batch_id=batch_id,
                content=llm_output,
                explanation=explanation,
                status=SuggestionStatus.PENDING,
            )
            session.add(suggestion)
            created += 1

        session.commit()
        return {
            "created": created,
            "skipped": len(failures),
            "total": len(page_slugs),
            "failures": failures,
        }
