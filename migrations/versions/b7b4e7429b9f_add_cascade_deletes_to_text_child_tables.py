"""add cascade deletes to text child tables

Revision ID: b7b4e7429b9f
Revises: 9eea54ec626a
Create Date: 2026-04-01 17:16:59.337240

Add ON DELETE CASCADE / SET NULL to foreign keys referencing the texts table
(and its children text_sections, text_blocks) so that deleting a text
automatically cleans up all related rows.

SQLite does not support ALTER TABLE ... ADD/DROP CONSTRAINT, so we recreate
each affected table.  We must disable foreign key checks during the swap
because the intermediate state temporarily violates referential integrity.
"""

import re

import sqlalchemy as sa
from alembic import op


revision = "b7b4e7429b9f"
down_revision = "9eea54ec626a"
branch_labels = None
depends_on = None


def _update_fk_ondelete(conn, table_name, column_name, ondelete, ref_table):
    """Alter a FK's ON DELETE action on SQLite by recreating the table.

    Uses the safe order: create-new → copy → drop-old → rename-new so
    that other tables' FK references (which point at table_name) are
    not rewritten by SQLite's implicit rename propagation.

    If no existing FK is found on the column, a new out-of-line
    FOREIGN KEY constraint is added referencing *ref_table*(id).
    """
    create_sql = conn.execute(
        sa.text("SELECT sql FROM sqlite_master WHERE type='table' AND name=:t"),
        {"t": table_name},
    ).scalar()
    if not create_sql:
        raise ValueError(f"Table {table_name} not found")

    # Match inline FK:  col_name TYPE REFERENCES "tbl" ("id") [ON DELETE ...]
    inline_pat = (
        rf'("?{column_name}"?\s+[^,]*?REFERENCES\s+"?[\w]+"?\s*\(\s*"?id"?\s*\))'
        rf"(\s+ON\s+DELETE\s+\w[\w ]*)?"
    )
    # Match out-of-line FK: FOREIGN KEY(col_name) REFERENCES "tbl" ("id") [ON DELETE ...]
    constraint_pat = (
        rf'(FOREIGN\s+KEY\s*\(\s*"?{column_name}"?\s*\)\s*'
        rf'REFERENCES\s+"?[\w]+"?\s*\(\s*"?id"?\s*\))'
        rf"(\s+ON\s+DELETE\s+\w[\w ]*)?"
    )

    suffix = f" ON DELETE {ondelete}" if ondelete else ""

    new_sql, count = re.subn(
        inline_pat, rf"\1{suffix}", create_sql, flags=re.IGNORECASE
    )
    if count == 0:
        new_sql, count = re.subn(
            constraint_pat, rf"\1{suffix}", create_sql, flags=re.IGNORECASE
        )
    if count == 0:
        # Column exists but has no FK — add an out-of-line constraint.
        fk_clause = (
            f', FOREIGN KEY("{column_name}") '
            f'REFERENCES "{ref_table}" ("id"){suffix}'
        )
        # Insert before the final closing paren of CREATE TABLE.
        new_sql = re.sub(r"\s*\)\s*$", fk_clause + "\n)", create_sql)

    tmp = f"_mig_new_{table_name}"
    # Create the new table under a temp name
    tmp_sql = re.sub(
        rf'CREATE\s+TABLE\s+"?{table_name}"?',
        f'CREATE TABLE "{tmp}"',
        new_sql,
        count=1,
        flags=re.IGNORECASE,
    )
    conn.execute(sa.text(tmp_sql))
    conn.execute(sa.text(f'INSERT INTO "{tmp}" SELECT * FROM "{table_name}"'))
    conn.execute(sa.text(f'DROP TABLE "{table_name}"'))
    conn.execute(sa.text(f'ALTER TABLE "{tmp}" RENAME TO "{table_name}"'))


# Process parent tables first so their renames don't affect children.
# (table, column, ref_table, ondelete_upgrade, ondelete_downgrade)
_FK_CHANGES = [
    ("texts", "parent_id", "texts", "SET NULL", None),
    ("text_sections", "text_id", "texts", "CASCADE", None),
    ("text_blocks", "text_id", "texts", "CASCADE", None),
    ("text_blocks", "section_id", "text_sections", "CASCADE", None),
    ("text_exports", "text_id", "texts", "CASCADE", None),
    ("text_reports", "text_id", "texts", "CASCADE", None),
    ("text_alternate_titles", "text_id", "texts", "CASCADE", None),
    ("publish_configs", "text_id", "texts", "SET NULL", None),
    ("block_parses", "text_id", "texts", "CASCADE", None),
    ("block_parses", "block_id", "text_blocks", "CASCADE", None),
    ("token_blocks", "text_id", "texts", "CASCADE", None),
    ("token_blocks", "block_id", "text_blocks", "CASCADE", None),
]


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("PRAGMA foreign_keys=OFF"))
    for table, column, ref_table, ondelete_up, _ in _FK_CHANGES:
        _update_fk_ondelete(conn, table, column, ondelete_up, ref_table)
    conn.execute(sa.text("PRAGMA foreign_keys=ON"))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("PRAGMA foreign_keys=OFF"))
    for table, column, ref_table, _, ondelete_down in reversed(_FK_CHANGES):
        _update_fk_ondelete(conn, table, column, ondelete_down, ref_table)
    conn.execute(sa.text("PRAGMA foreign_keys=ON"))
