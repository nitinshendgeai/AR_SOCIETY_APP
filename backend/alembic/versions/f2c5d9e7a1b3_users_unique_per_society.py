"""A mobile number or email may belong to one login per society

Revision ID: f2c5d9e7a1b3
Revises: e1b4c8d6f3a2
Create Date: 2026-10-12

users.email and users.phone were unique across the whole platform, so a person in two societies couldn't have a login in
each (the second society was quietly linked to the first society's login). They are now unique within a society among
*active* users only (a disabled or removed user doesn't hold the number), and platform admins (no society) among
themselves. Every existing row satisfies the stricter old rule, so the new indexes can't fail. Idempotent.
"""
import uuid
from datetime import datetime

import sqlalchemy as sa
from alembic import op

revision      = 'f2c5d9e7a1b3'
down_revision = 'e1b4c8d6f3a2'
branch_labels = None
depends_on    = None

ACTIVE = "is_active AND status = 'active'"
NEW = {
    'uq_users_society_email': ('email', f"society_id IS NOT NULL AND {ACTIVE}", 'society_id, email'),
    'uq_users_society_phone': ('phone', f"society_id IS NOT NULL AND phone IS NOT NULL AND {ACTIVE}", 'society_id, phone'),
    'uq_users_platform_email': ('email', f"society_id IS NULL AND {ACTIVE}", 'email'),
    'uq_users_platform_phone': ('phone', f"society_id IS NULL AND phone IS NOT NULL AND {ACTIVE}", 'phone'),
}


def upgrade():
    # Plain (non-unique) lookup indexes in place of the platform-wide unique ones
    for col in ('email', 'phone'):
        op.execute(sa.text(f"DROP INDEX IF EXISTS ix_users_{col}"))
        op.execute(sa.text(f"CREATE INDEX IF NOT EXISTS ix_users_{col} ON users ({col})"))
    for name, (_col, where, cols) in NEW.items():
        op.execute(sa.text(f"CREATE UNIQUE INDEX IF NOT EXISTS {name} ON users ({cols}) WHERE {where}"))
    _split_cross_society_links()


def _split_cross_society_links():
    """Until now a second society that entered the same mobile number was linked to the first society's login, which
    only ever sees the first society. Give each such resident / tenant a login of their own in their own society
    (same name, mobile, email and password as the existing one, so the person keeps signing in the same way and can
    now switch between societies)."""
    bind = op.get_bind()
    tables = sa.inspect(bind).get_table_names()
    role = bind.execute(sa.text("SELECT id FROM roles WHERE name = 'Resident'")).scalar()
    made = {}
    for table in ('residents', 'tenants'):
        if table not in tables:
            continue
        rows = bind.execute(sa.text(f"""
            SELECT p.id AS pid, w.society_id AS sid, u.id AS uid, u.email, u.phone, u.full_name, u.hashed_password,
                   u.must_change_password
            FROM {table} p
            JOIN flats f ON f.id = p.flat_id JOIN wings w ON w.id = f.wing_id
            JOIN users u ON u.id = p.user_id
            WHERE u.society_id IS NOT NULL AND u.society_id <> w.society_id""")).mappings().all()
        for r in rows:
            key = (r['sid'], r['uid'])
            if key not in made:
                existing = bind.execute(sa.text(
                    "SELECT id FROM users WHERE society_id = :sid AND is_active AND status = 'active' "
                    "AND (email = :email OR (phone IS NOT NULL AND phone = :phone))"),
                    {'sid': r['sid'], 'email': r['email'], 'phone': r['phone']}).scalar()
                if existing is None:
                    existing = uuid.uuid4()
                    now = datetime.utcnow()
                    bind.execute(sa.text("""
                        INSERT INTO users (id, created_at, updated_at, is_active, email, phone, full_name, hashed_password,
                                           status, is_superadmin, must_change_password, terms_accepted, setup_completed,
                                           society_id)
                        VALUES (:id, :now, :now, true, :email, :phone, :name, :pw, 'active', false, :mcp, false, false,
                                :sid)"""), {'id': existing, 'now': now, 'email': r['email'], 'phone': r['phone'],
                                            'name': r['full_name'], 'pw': r['hashed_password'],
                                            'mcp': r['must_change_password'], 'sid': r['sid']})
                    if role is not None:
                        bind.execute(sa.text("""
                            INSERT INTO user_roles (id, created_at, updated_at, is_active, user_id, role_id)
                            VALUES (:id, :now, :now, true, :uid, :rid)"""),
                                     {'id': uuid.uuid4(), 'now': now, 'uid': existing, 'rid': role})
                made[key] = existing
            bind.execute(sa.text(f"UPDATE {table} SET user_id = :new WHERE id = :pid"), {'new': made[key], 'pid': r['pid']})


def downgrade():
    # Going back to platform-wide uniqueness fails if a number is now used in two societies — by design.
    for name in NEW:
        op.execute(sa.text(f"DROP INDEX IF EXISTS {name}"))
    for col in ('email', 'phone'):
        op.execute(sa.text(f"DROP INDEX IF EXISTS ix_users_{col}"))
        op.execute(sa.text(f"CREATE UNIQUE INDEX ix_users_{col} ON users ({col})"))
