"""A society can have roles of its own

Revision ID: e3a5c7d9f1b4
Revises: e2f4a6b8c0d2
Create Date: 2026-11-17

roles.society_id: empty for the standard roles every society shares; set for a role a society made for itself, which only
that society sees and can give out. A standard role's name stays unique across the platform; a society's own role names
are unique within the society (two societies may each have their own "Gym Instructor"). Additive and idempotent: every
existing role keeps no society.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision      = 'e3a5c7d9f1b4'
down_revision = 'e2f4a6b8c0d2'
branch_labels = None
depends_on    = None


def _has_col(table, name):
    return name in {c['name'] for c in sa.inspect(op.get_bind()).get_columns(table)}


def _index(table, name):
    return next((i for i in sa.inspect(op.get_bind()).get_indexes(table) if i['name'] == name), None)


def upgrade():
    if not _has_col('roles', 'society_id'):
        op.add_column('roles', sa.Column('society_id', postgresql.UUID(as_uuid=True), nullable=True))
        op.create_foreign_key('fk_roles_society_id', 'roles', 'societies', ['society_id'], ['id'], ondelete='CASCADE')
    if not _index('roles', 'ix_roles_society_id'):
        op.create_index('ix_roles_society_id', 'roles', ['society_id'])
    # the name index was unique on its own: it now only speeds lookups, and the two partial indexes carry the rule
    existing = _index('roles', 'ix_roles_name')
    if existing is not None and existing.get('unique'):
        op.drop_index('ix_roles_name', table_name='roles')
        op.create_index('ix_roles_name', 'roles', ['name'])
    if not _index('roles', 'uq_roles_system_name'):
        op.create_index('uq_roles_system_name', 'roles', ['name'], unique=True,
                        postgresql_where=sa.text('society_id IS NULL'))
    if not _index('roles', 'uq_roles_society_name'):
        op.create_index('uq_roles_society_name', 'roles', ['society_id', 'name'], unique=True,
                        postgresql_where=sa.text('society_id IS NOT NULL'))


def downgrade():
    bind = op.get_bind()
    if _has_col('roles', 'society_id'):
        # a society's own roles go with the column: their grants and assignments first
        mine = "SELECT id FROM roles WHERE society_id IS NOT NULL"
        for table in ('user_roles', 'role_permissions', 'role_forms'):
            bind.execute(sa.text(f"DELETE FROM {table} WHERE role_id IN ({mine})"))
        bind.execute(sa.text("DELETE FROM roles WHERE society_id IS NOT NULL"))
    for name in ('uq_roles_society_name', 'uq_roles_system_name'):
        if _index('roles', name):
            op.drop_index(name, table_name='roles')
    existing = _index('roles', 'ix_roles_name')
    if existing is not None and not existing.get('unique'):
        op.drop_index('ix_roles_name', table_name='roles')
        op.create_index('ix_roles_name', 'roles', ['name'], unique=True)
    if _index('roles', 'ix_roles_society_id'):
        op.drop_index('ix_roles_society_id', table_name='roles')
    if _has_col('roles', 'society_id'):
        op.drop_constraint('fk_roles_society_id', 'roles', type_='foreignkey')
        op.drop_column('roles', 'society_id')
