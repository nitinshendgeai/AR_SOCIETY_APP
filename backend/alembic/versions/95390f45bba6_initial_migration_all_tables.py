"""initial_migration_all_tables

Revision ID: 95390f45bba6
Revises:
Create Date: 2026-05-23

Tables created:
  societies, wings, flats, roles, users, user_roles, residents, tenants
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
import uuid

revision = '95390f45bba6'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── societies ─────────────────────────────────────────────────────────────
    op.create_table(
        'societies',
        sa.Column('id',            UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('created_at',    sa.DateTime(), nullable=False),
        sa.Column('updated_at',    sa.DateTime(), nullable=False),
        sa.Column('is_active',     sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('name',          sa.String(255), nullable=False),
        sa.Column('address',       sa.Text(), nullable=True),
        sa.Column('city',          sa.String(100), nullable=True),
        sa.Column('state',         sa.String(100), nullable=True),
        sa.Column('pincode',       sa.String(20), nullable=True),
        sa.Column('contact_email', sa.String(255), nullable=True),
        sa.Column('contact_phone', sa.String(20), nullable=True),
        sa.Column('logo_url',      sa.String(500), nullable=True),
    )
    op.create_index('ix_societies_id',   'societies', ['id'])
    op.create_index('ix_societies_name', 'societies', ['name'], unique=True)

    # ── wings ─────────────────────────────────────────────────────────────────
    op.create_table(
        'wings',
        sa.Column('id',           UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('created_at',   sa.DateTime(), nullable=False),
        sa.Column('updated_at',   sa.DateTime(), nullable=False),
        sa.Column('is_active',    sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('name',         sa.String(100), nullable=False),
        sa.Column('code',         sa.String(20), nullable=True),
        sa.Column('total_floors', sa.Integer(), nullable=True),
        sa.Column('society_id',   UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(['society_id'], ['societies.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_wings_id',        'wings', ['id'])
    op.create_index('ix_wings_society_id','wings', ['society_id'])

    # ── flats ─────────────────────────────────────────────────────────────────
    flat_type_enum = sa.Enum(
        '1BHK','2BHK','3BHK','4BHK','Penthouse','Studio','Other',
        name='flattype'
    )
    occupancy_enum = sa.Enum(
        'owner_occupied','tenant_occupied','vacant',
        name='occupancystatus'
    )
    op.create_table(
        'flats',
        sa.Column('id',               UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('created_at',       sa.DateTime(), nullable=False),
        sa.Column('updated_at',       sa.DateTime(), nullable=False),
        sa.Column('is_active',        sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('flat_number',      sa.String(20), nullable=False),
        sa.Column('floor',            sa.Integer(), nullable=True),
        sa.Column('flat_type',        flat_type_enum, nullable=True),
        sa.Column('area_sqft',        sa.Float(), nullable=True),
        sa.Column('occupancy_status', occupancy_enum, nullable=True),
        sa.Column('wing_id',          UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(['wing_id'], ['wings.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_flats_id',     'flats', ['id'])
    op.create_index('ix_flats_wing_id','flats', ['wing_id'])

    # ── roles ─────────────────────────────────────────────────────────────────
    op.create_table(
        'roles',
        sa.Column('id',          UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('created_at',  sa.DateTime(), nullable=False),
        sa.Column('updated_at',  sa.DateTime(), nullable=False),
        sa.Column('is_active',   sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('name',        sa.String(100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
    )
    op.create_index('ix_roles_id',  'roles', ['id'])
    op.create_index('ix_roles_name','roles', ['name'], unique=True)

    # ── users ─────────────────────────────────────────────────────────────────
    user_status_enum = sa.Enum(
        'active','inactive','suspended','pending',
        name='userstatus'
    )
    op.create_table(
        'users',
        sa.Column('id',              UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('created_at',      sa.DateTime(), nullable=False),
        sa.Column('updated_at',      sa.DateTime(), nullable=False),
        sa.Column('is_active',       sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('email',           sa.String(255), nullable=False),
        sa.Column('phone',           sa.String(20), nullable=True),
        sa.Column('full_name',       sa.String(255), nullable=False),
        sa.Column('hashed_password', sa.String(255), nullable=False),
        sa.Column('status',          user_status_enum, nullable=False, server_default='pending'),
        sa.Column('profile_image',   sa.String(500), nullable=True),
        sa.Column('is_superadmin',   sa.Boolean(), nullable=False, server_default='false'),
    )
    op.create_index('ix_users_id',   'users', ['id'])
    op.create_index('ix_users_email','users', ['email'], unique=True)
    op.create_index('ix_users_phone','users', ['phone'], unique=True)

    # ── user_roles ────────────────────────────────────────────────────────────
    op.create_table(
        'user_roles',
        sa.Column('id',         UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('is_active',  sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('user_id',    UUID(as_uuid=True), nullable=False),
        sa.Column('role_id',    UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['role_id'], ['roles.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_user_roles_id',     'user_roles', ['id'])
    op.create_index('ix_user_roles_user_id','user_roles', ['user_id'])
    op.create_index('ix_user_roles_role_id','user_roles', ['role_id'])

    # ── residents ─────────────────────────────────────────────────────────────
    resident_type_enum = sa.Enum(
        'owner','co_owner','family','dependent',
        name='residenttype'
    )
    op.create_table(
        'residents',
        sa.Column('id',              UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('created_at',      sa.DateTime(), nullable=False),
        sa.Column('updated_at',      sa.DateTime(), nullable=False),
        sa.Column('is_active',       sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('full_name',       sa.String(255), nullable=False),
        sa.Column('phone',           sa.String(20), nullable=True),
        sa.Column('email',           sa.String(255), nullable=True),
        sa.Column('date_of_birth',   sa.Date(), nullable=True),
        sa.Column('resident_type',   resident_type_enum, nullable=False, server_default='owner'),
        sa.Column('is_primary',      sa.Boolean(), server_default='false'),
        sa.Column('move_in_date',    sa.Date(), nullable=True),
        sa.Column('move_out_date',   sa.Date(), nullable=True),
        sa.Column('id_proof_type',   sa.String(50), nullable=True),
        sa.Column('id_proof_number', sa.String(100), nullable=True),
        sa.Column('flat_id',         UUID(as_uuid=True), nullable=False),
        sa.Column('user_id',         UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(['flat_id'], ['flats.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
    )
    op.create_index('ix_residents_id',     'residents', ['id'])
    op.create_index('ix_residents_flat_id','residents', ['flat_id'])
    op.create_index('ix_residents_user_id','residents', ['user_id'])

    # ── tenants ───────────────────────────────────────────────────────────────
    op.create_table(
        'tenants',
        sa.Column('id',                      UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('created_at',              sa.DateTime(), nullable=False),
        sa.Column('updated_at',              sa.DateTime(), nullable=False),
        sa.Column('is_active',               sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('full_name',               sa.String(255), nullable=False),
        sa.Column('phone',                   sa.String(20), nullable=True),
        sa.Column('email',                   sa.String(255), nullable=True),
        sa.Column('lease_start_date',        sa.Date(), nullable=True),
        sa.Column('lease_end_date',          sa.Date(), nullable=True),
        sa.Column('monthly_rent',            sa.Numeric(12, 2), nullable=True),
        sa.Column('security_deposit',        sa.Numeric(12, 2), nullable=True),
        sa.Column('id_proof_type',           sa.String(50), nullable=True),
        sa.Column('id_proof_number',         sa.String(100), nullable=True),
        sa.Column('emergency_contact_name',  sa.String(255), nullable=True),
        sa.Column('emergency_contact_phone', sa.String(20), nullable=True),
        sa.Column('flat_id',                 UUID(as_uuid=True), nullable=False),
        sa.Column('user_id',                 UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(['flat_id'], ['flats.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
    )
    op.create_index('ix_tenants_id',     'tenants', ['id'])
    op.create_index('ix_tenants_flat_id','tenants', ['flat_id'])
    op.create_index('ix_tenants_user_id','tenants', ['user_id'])


def downgrade() -> None:
    op.drop_table('tenants')
    op.drop_table('residents')
    op.drop_table('user_roles')
    op.drop_table('users')
    op.drop_table('roles')
    op.drop_table('flats')
    op.drop_table('wings')
    op.drop_table('societies')

    # Drop custom enum types
    sa.Enum(name='residenttype').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='userstatus').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='occupancystatus').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='flattype').drop(op.get_bind(), checkfirst=True)
