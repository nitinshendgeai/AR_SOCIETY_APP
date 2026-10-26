"""Advance maintenance gets its own ledger

Revision ID: 0b1c2d3e4f5a
Revises: d6f8a0c2e4b6
Create Date: 2026-10-26

Members' advance maintenance was credited to "Deposits from Members", the account that also holds refundable
deposits. It now has its own ledger, "Advance Maintenance from Members" (a current liability). For societies that
already hold advances, create the ledger beside Deposits from Members and move the advance postings and each flat's
advance account to it. Idempotent.
"""
from alembic import op

revision      = "0b1c2d3e4f5a"
down_revision = "d6f8a0c2e4b6"
branch_labels = None
depends_on    = None


def upgrade():
    op.execute("""
        INSERT INTO accounts
            (id, created_at, updated_at, is_active, society_id, group_id, code, name, system_key, sort_order,
             is_system, opening_balance, opening_type, is_cash, is_bank, is_default_bank)
        SELECT gen_random_uuid(), NOW(), NOW(), TRUE, d.society_id, d.group_id, '1407',
               'Advance Maintenance from Members', 'advance_maintenance', d.sort_order + 1,
               TRUE, 0, 'cr', FALSE, FALSE, FALSE
        FROM accounts d
        WHERE d.system_key = 'member_deposits'
          AND EXISTS (SELECT 1 FROM entity_accounts ea
                      WHERE ea.control_account_id = d.id AND ea.subledger_type = 'ADVANCE')
          AND NOT EXISTS (SELECT 1 FROM accounts n
                          WHERE n.society_id = d.society_id
                            AND (n.system_key = 'advance_maintenance'
                                 OR n.name = 'Advance Maintenance from Members'))
    """)
    op.execute("""
        UPDATE voucher_entries ve
        SET account_id = n.id
        FROM entity_accounts ea, accounts d, accounts n
        WHERE ve.entity_account_id = ea.id
          AND ea.subledger_type = 'ADVANCE'
          AND ve.account_id = d.id AND d.system_key = 'member_deposits'
          AND n.society_id = d.society_id AND n.system_key = 'advance_maintenance'
    """)
    op.execute("""
        UPDATE entity_accounts ea
        SET control_account_id = n.id
        FROM accounts d, accounts n
        WHERE ea.subledger_type = 'ADVANCE'
          AND ea.control_account_id = d.id AND d.system_key = 'member_deposits'
          AND n.society_id = d.society_id AND n.system_key = 'advance_maintenance'
    """)
    # Tag each advance line with its flat, so a flat's advance can be read from the ledger like its dues.
    op.execute("""
        UPDATE voucher_entries ve
        SET flat_id = e.source_id
        FROM entity_accounts ea, accounting_entities e
        WHERE ve.entity_account_id = ea.id
          AND ea.subledger_type = 'ADVANCE'
          AND ea.entity_id = e.id
          AND e.source_type = 'flat'
          AND ve.flat_id IS NULL
          AND EXISTS (SELECT 1 FROM flats f WHERE f.id = e.source_id)
    """)


def downgrade():
    pass            # the data move is not undone; the ledger stays
