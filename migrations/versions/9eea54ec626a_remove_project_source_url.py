"""remove_project_source_url

Revision ID: 9eea54ec626a
Revises: 4ab32672bbc9
Create Date: 2026-04-01 08:13:46.967736

"""

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "9eea54ec626a"
down_revision = "4ab32672bbc9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()

    # Migrate source_url data to project_sources where not already present.
    rows = conn.execute(
        sa.text(
            "SELECT id, source_url, display_title, creator_id "
            "FROM proof_projects "
            "WHERE source_url IS NOT NULL AND source_url != ''"
        )
    ).fetchall()

    for project_id, source_url, display_title, creator_id in rows:
        exists = conn.execute(
            sa.text(
                "SELECT 1 FROM project_sources "
                "WHERE project_id = :pid AND url = :url "
                "LIMIT 1"
            ),
            {"pid": project_id, "url": source_url},
        ).fetchone()

        if not exists:
            conn.execute(
                sa.text(
                    "INSERT INTO project_sources (project_id, url, description, author_id, created_at) "
                    "VALUES (:pid, :url, :desc, :author_id, CURRENT_TIMESTAMP)"
                ),
                {
                    "pid": project_id,
                    "url": source_url,
                    "desc": display_title or "Source PDF",
                    "author_id": creator_id,
                },
            )

    op.drop_column("proof_projects", "source_url")


def downgrade() -> None:
    op.add_column("proof_projects", sa.Column("source_url", sa.String(), nullable=True))
