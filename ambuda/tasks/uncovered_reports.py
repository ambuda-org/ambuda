"""Celery task: compute & cache the uncovered-blocks report for a project.

Used by the admin "unpublished projects" drill-down page. Mirrors the
text-validation report flow (see ``ambuda.tasks.text_validation``).
"""

import dataclasses as dc
import logging
from datetime import UTC, datetime

from ambuda import database as db
from ambuda.tasks import app
from ambuda.tasks.utils import get_db_session, get_redis
from ambuda.utils.text_publishing import find_unpublished_blocks


REPORT_LOCK_TTL = 300  # seconds


def maybe_rerun_report(
    project_id: int, app_environment: str, redis_client=None
) -> bool:
    """Trigger a re-run if no other re-run is in progress for this project."""
    r = redis_client or get_redis()
    lock_key = db.ProjectUncoveredReport.rerun_lock_key(project_id)

    if r.set(lock_key, "1", nx=True, ex=REPORT_LOCK_TTL):
        run_report.apply_async(args=(project_id, app_environment))
        return True
    return False


def run_report_inner(
    project_id: int, app_environment: str, engine=None, redis_client=None
) -> None:
    """Compute and store an uncovered-blocks report for the given project.

    ``engine`` is exposed for testing.
    """
    with get_db_session(app_environment, engine=engine) as (session, _q, _cfg):
        project = session.get(db.Project, project_id)
        if not project:
            raise ValueError(f"Project with id {project_id} not found")

        logging.info(f"Computing unpublished-blocks report for {project.slug}")
        report = find_unpublished_blocks(project, session=session)
        payload = {
            "blocks": [dc.asdict(b) for b in report.blocks],
            "total_proofed_blocks": report.total_proofed_blocks,
        }

        existing = (
            session.query(db.ProjectUncoveredReport)
            .filter_by(project_id=project_id)
            .one_or_none()
        )

        now = datetime.now(UTC)
        if existing:
            existing.payload = payload
            existing.generated_at = now
        else:
            session.add(
                db.ProjectUncoveredReport(
                    project_id=project_id,
                    generated_at=now,
                    payload=payload,
                )
            )

        session.commit()

        r = redis_client or get_redis()
        r.delete(db.ProjectUncoveredReport.rerun_lock_key(project_id))


@app.task(bind=True)
def run_report(self, project_id: int, app_environment: str):
    run_report_inner(project_id, app_environment)


def dispatch_all_reports_inner(
    app_environment: str, engine=None, redis_client=None
) -> tuple[int, int]:
    """Fan out: enqueue an uncovered-blocks report for every project.

    The admin "Refresh all reports" button enqueues this single task instead
    of looping over every project in the request handler — that loop blocked
    the HTTP response on N×(redis SET + broker publish) round-trips.

    ``engine`` and ``redis_client`` are exposed for testing.
    """
    with get_db_session(app_environment, engine=engine) as (session, _q, _cfg):
        project_ids = [pid for (pid,) in session.query(db.Project.id).all()]

    dispatched = 0
    skipped = 0
    for pid in project_ids:
        if maybe_rerun_report(pid, app_environment, redis_client=redis_client):
            dispatched += 1
        else:
            skipped += 1
    logging.info(
        f"dispatch_all_reports: dispatched={dispatched} skipped={skipped} "
        f"(of {len(project_ids)} projects)"
    )
    return dispatched, skipped


@app.task(bind=True)
def dispatch_all_reports(self, app_environment: str):
    dispatch_all_reports_inner(app_environment)
