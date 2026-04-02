"""add text stage and simplify publish config

Revision ID: 0593733b2590
Revises: 812a287f9418
Create Date: 2026-04-02

Add Text.stage column ("stub" / "public"), create stub Texts for orphaned
PublishConfigs, then remove duplicated fields from publish_configs.
"""

from alembic import op
import sqlalchemy as sa

revision = "0593733b2590"
down_revision = "812a287f9418"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Add stage column (nullable initially for backfill).
    op.add_column("texts", sa.Column("stage", sa.String(), nullable=True))

    # Lightweight table aliases for data manipulation.
    texts = sa.table(
        "texts",
        sa.column("id", sa.Integer),
        sa.column("slug", sa.String),
        sa.column("title", sa.String),
        sa.column("language", sa.String),
        sa.column("license", sa.String),
        sa.column("stage", sa.String),
        sa.column("published_at", sa.DateTime),
        sa.column("project_id", sa.Integer),
        sa.column("author_id", sa.Integer),
        sa.column("parent_id", sa.Integer),
        sa.column("updated_at", sa.DateTime),
    )
    publish_configs = sa.table(
        "publish_configs",
        sa.column("id", sa.Integer),
        sa.column("project_id", sa.Integer),
        sa.column("text_id", sa.Integer),
        sa.column("slug", sa.String),
        sa.column("title", sa.String),
        sa.column("author", sa.String),
        sa.column("language", sa.String),
        sa.column("parent_slug", sa.String),
    )
    authors = sa.table(
        "authors",
        sa.column("id", sa.Integer),
        sa.column("slug", sa.String),
        sa.column("name", sa.String),
    )
    text_coll = sa.table(
        "text_collection_association",
        sa.column("text_id", sa.Integer),
        sa.column("collection_id", sa.Integer),
    )
    pc_coll = sa.table(
        "publish_config_collection_association",
        sa.column("publish_config_id", sa.Integer),
        sa.column("collection_id", sa.Integer),
    )

    # 2. Backfill stage for all existing texts as public.
    conn = op.get_bind()
    conn.execute(texts.update().where(texts.c.stage.is_(None)).values(stage="public"))

    # 3. Create stub Texts for PublishConfigs that have no text_id.
    orphan_configs = conn.execute(
        sa.select(
            publish_configs.c.id,
            publish_configs.c.project_id,
            publish_configs.c.slug,
            publish_configs.c.title,
            publish_configs.c.author,
            publish_configs.c.language,
            publish_configs.c.parent_slug,
        ).where(publish_configs.c.text_id.is_(None))
    ).fetchall()

    from datetime import datetime, UTC

    now = datetime.now(UTC)

    for pc in orphan_configs:
        # Look up or create author.
        author_id = None
        if pc.author:
            row = conn.execute(
                sa.select(authors.c.id).where(authors.c.name == pc.author)
            ).first()
            if row:
                author_id = row.id
            else:
                author_slug = pc.author.lower().replace(" ", "-")
                conn.execute(authors.insert().values(slug=author_slug, name=pc.author))
                row = conn.execute(
                    sa.select(authors.c.id).where(authors.c.slug == author_slug)
                ).first()
                author_id = row.id

        # Create stub text.
        conn.execute(
            texts.insert().values(
                slug=pc.slug,
                title=pc.title,
                language=pc.language or "sa",
                stage="stub",
                project_id=pc.project_id,
                author_id=author_id,
                updated_at=now,
            )
        )
        text_row = conn.execute(
            sa.select(texts.c.id).where(texts.c.slug == pc.slug)
        ).first()
        text_id = text_row.id

        # Link config to the new stub text.
        conn.execute(
            publish_configs.update()
            .where(publish_configs.c.id == pc.id)
            .values(text_id=text_id)
        )

        # Copy collections from publish_config to text.
        pc_colls = conn.execute(
            sa.select(pc_coll.c.collection_id).where(
                pc_coll.c.publish_config_id == pc.id
            )
        ).fetchall()
        for (coll_id,) in pc_colls:
            conn.execute(
                text_coll.insert().values(text_id=text_id, collection_id=coll_id)
            )

    # 4. Resolve parent_slug to parent_id for stub texts.
    stubs_with_parent = conn.execute(
        sa.select(
            publish_configs.c.id,
            publish_configs.c.text_id,
            publish_configs.c.parent_slug,
        ).where(
            publish_configs.c.parent_slug.isnot(None),
            publish_configs.c.parent_slug != "",
        )
    ).fetchall()

    for pc in stubs_with_parent:
        parent_row = conn.execute(
            sa.select(texts.c.id).where(texts.c.slug == pc.parent_slug)
        ).first()
        if parent_row:
            conn.execute(
                texts.update()
                .where(texts.c.id == pc.text_id)
                .values(parent_id=parent_row.id)
            )

    # 5. Make stage NOT NULL now that all rows are populated.
    with op.batch_alter_table("texts") as batch_op:
        batch_op.alter_column("stage", nullable=False)

    # 6. Make text_id NOT NULL and drop removed columns from publish_configs.
    with op.batch_alter_table("publish_configs") as batch_op:
        batch_op.alter_column("text_id", nullable=False)
        batch_op.drop_column("slug")
        batch_op.drop_column("title")
        batch_op.drop_column("author")
        batch_op.drop_column("language")
        batch_op.drop_column("parent_slug")

    # 7. Drop the publish_config_collection_association table.
    op.drop_table("publish_config_collection_association")


def downgrade() -> None:
    # Recreate association table.
    op.create_table(
        "publish_config_collection_association",
        sa.Column(
            "publish_config_id",
            sa.Integer,
            sa.ForeignKey("publish_configs.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "collection_id",
            sa.Integer,
            sa.ForeignKey("text_collections.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )

    # Re-add columns to publish_configs.
    with op.batch_alter_table("publish_configs") as batch_op:
        batch_op.add_column(sa.Column("slug", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("title", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("author", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("language", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("parent_slug", sa.String(), nullable=True))
        batch_op.alter_column("text_id", nullable=True)

    op.drop_column("texts", "stage")
