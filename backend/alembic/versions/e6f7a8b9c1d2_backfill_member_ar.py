"""Backfill formal member AR entity accounts and voucher links.

Revision ID: e6f7a8b9c1d2
Revises: d5e6f7a8b9c1
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "e6f7a8b9c1d2"
down_revision = "d5e6f7a8b9c1"
branch_labels = None
depends_on = None


def upgrade():
    # Every existing flat gets a formal AR account. Existing EntityAccounts
    # created by runtime posting are preserved.
    op.execute("""
        WITH existing AS (
            SELECT society_id, COALESCE(MAX(account_number::bigint), 1000000) AS max_no
            FROM entity_accounts
            WHERE subledger_type = 'AR'
              AND account_number ~ '^10[0-9]+$'
            GROUP BY society_id
        ),
        numbered AS (
            SELECT e.id AS entity_id, e.society_id, a.id AS control_account_id,
                   (COALESCE(x.max_no, 1000000)
                    + ROW_NUMBER() OVER (
                        PARTITION BY e.society_id
                        ORDER BY e.source_id
                      ))::text AS account_number
            FROM accounting_entities e
            JOIN accounts a
              ON a.society_id = e.society_id
             AND a.system_key = 'members_dues'
             AND a.is_system = TRUE
            LEFT JOIN existing x ON x.society_id = e.society_id
            WHERE e.entity_type = 'member'
              AND e.source_type = 'flat'
              AND NOT EXISTS (
                  SELECT 1 FROM entity_accounts ea
                  WHERE ea.entity_id = e.id
                    AND ea.subledger_type = 'AR'
              )
        )
        INSERT INTO entity_accounts
            (id, created_at, updated_at, is_active, society_id, entity_id,
             control_account_id, subledger_type, account_number, is_primary)
        SELECT gen_random_uuid(), NOW(), NOW(), TRUE, society_id, entity_id,
               control_account_id, 'AR', account_number, TRUE
        FROM numbered
    """)

    # Link historical member-dues voucher lines to the formal AR subledger.
    # This preserves continuity for vouchers created before entity_account_id
    # was introduced.
    op.execute("""
        UPDATE voucher_entries ve
           SET entity_account_id = ea.id
          FROM vouchers v,
               accounts a,
               accounting_entities e,
               entity_accounts ea
         WHERE ve.voucher_id = v.id
           AND ve.account_id = a.id
           AND a.system_key = 'members_dues'
           AND ve.flat_id IS NOT NULL
           AND e.society_id = v.society_id
           AND e.entity_type = 'member'
           AND e.source_type = 'flat'
           AND e.source_id = ve.flat_id
           AND ea.entity_id = e.id
           AND ea.subledger_type = 'AR'
           AND ea.society_id = v.society_id
           AND ve.entity_account_id IS NULL
    """)


def downgrade():
    # Do not remove entity accounts or links: they may have been created or
    # reused by live accounting after this migration.
    pass
