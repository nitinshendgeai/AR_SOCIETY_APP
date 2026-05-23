"""amenity_management_module

Revision ID: a05bc0ded1e2
Revises: aab340f2f215
Create Date: 2026-05-23

Tables: amenities, amenity_rules, amenity_slots, amenity_pricing,
        amenity_blackout_dates, amenity_bookings, amenity_usage_logs
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
import uuid

revision      = 'a05bc0ded1e2'
down_revision = 'aab340f2f215'
branch_labels = None
depends_on    = None


def upgrade() -> None:
    amenity_type_enum  = sa.Enum('clubhouse','gym','pool','party_hall','guest_room','sports_court','terrace','conference','other', name='amenitytype')
    booking_status_enum= sa.Enum('pending','approved','rejected','cancelled','completed', name='bookingstatus')
    rule_type_enum     = sa.Enum('owners_only','tenants_restricted','no_dues_required','max_duration_hours','max_bookings_per_week','max_bookings_per_month','min_advance_hours','max_advance_days','deposit_required','charge_per_hour','approval_required','max_guests', name='ruletype')

    # ── amenities ─────────────────────────────────────────────────────────────
    op.create_table('amenities',
        sa.Column('id',               UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('created_at',       sa.DateTime(), nullable=False),
        sa.Column('updated_at',       sa.DateTime(), nullable=False),
        sa.Column('is_active',        sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('society_id',       UUID(as_uuid=True), nullable=False),
        sa.Column('name',             sa.String(150), nullable=False),
        sa.Column('amenity_type',     amenity_type_enum, nullable=False),
        sa.Column('description',      sa.Text(), nullable=True),
        sa.Column('location',         sa.String(255), nullable=True),
        sa.Column('capacity',         sa.Integer(), nullable=True),
        sa.Column('open_time',        sa.Time(), nullable=True),
        sa.Column('close_time',       sa.Time(), nullable=True),
        sa.Column('booking_required', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('approval_required',sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('is_chargeable',    sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('image_url',        sa.String(500), nullable=True),
        sa.ForeignKeyConstraint(['society_id'], ['societies.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_amenities_id',        'amenities', ['id'])
    op.create_index('ix_amenities_society_id','amenities', ['society_id'])
    op.create_index('ix_amenities_type',      'amenities', ['amenity_type'])

    # ── amenity_rules ─────────────────────────────────────────────────────────
    op.create_table('amenity_rules',
        sa.Column('id',          UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('created_at',  sa.DateTime(), nullable=False),
        sa.Column('updated_at',  sa.DateTime(), nullable=False),
        sa.Column('is_active',   sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('amenity_id',  UUID(as_uuid=True), nullable=False),
        sa.Column('rule_type',   rule_type_enum, nullable=False),
        sa.Column('rule_value',  sa.String(255), nullable=True),
        sa.Column('description', sa.String(500), nullable=True),
        sa.ForeignKeyConstraint(['amenity_id'], ['amenities.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_amenity_rules_id',         'amenity_rules', ['id'])
    op.create_index('ix_amenity_rules_amenity_id', 'amenity_rules', ['amenity_id'])
    op.create_index('ix_amenity_rules_rule_type',  'amenity_rules', ['rule_type'])

    # ── amenity_slots ─────────────────────────────────────────────────────────
    op.create_table('amenity_slots',
        sa.Column('id',           UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('created_at',   sa.DateTime(), nullable=False),
        sa.Column('updated_at',   sa.DateTime(), nullable=False),
        sa.Column('is_active',    sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('amenity_id',   UUID(as_uuid=True), nullable=False),
        sa.Column('slot_date',    sa.Date(), nullable=False),
        sa.Column('start_time',   sa.Time(), nullable=False),
        sa.Column('end_time',     sa.Time(), nullable=False),
        sa.Column('max_capacity', sa.Integer(), nullable=True),
        sa.Column('booked_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('is_available', sa.Boolean(), nullable=False, server_default='true'),
        sa.ForeignKeyConstraint(['amenity_id'], ['amenities.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_amenity_slots_id',        'amenity_slots', ['id'])
    op.create_index('ix_amenity_slots_amenity_id','amenity_slots', ['amenity_id'])
    op.create_index('ix_amenity_slots_date',      'amenity_slots', ['slot_date'])

    # ── amenity_pricing ───────────────────────────────────────────────────────
    op.create_table('amenity_pricing',
        sa.Column('id',             UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('created_at',     sa.DateTime(), nullable=False),
        sa.Column('updated_at',     sa.DateTime(), nullable=False),
        sa.Column('is_active',      sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('amenity_id',     UUID(as_uuid=True), nullable=False),
        sa.Column('label',          sa.String(100), nullable=False),
        sa.Column('price_per_hour', sa.Float(), nullable=True),
        sa.Column('flat_price',     sa.Float(), nullable=True),
        sa.Column('deposit_amount', sa.Float(), nullable=True),
        sa.Column('is_default',     sa.Boolean(), nullable=False, server_default='false'),
        sa.ForeignKeyConstraint(['amenity_id'], ['amenities.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_amenity_pricing_id',        'amenity_pricing', ['id'])
    op.create_index('ix_amenity_pricing_amenity_id','amenity_pricing', ['amenity_id'])

    # ── amenity_blackout_dates ────────────────────────────────────────────────
    op.create_table('amenity_blackout_dates',
        sa.Column('id',            UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('created_at',    sa.DateTime(), nullable=False),
        sa.Column('updated_at',    sa.DateTime(), nullable=False),
        sa.Column('is_active',     sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('amenity_id',    UUID(as_uuid=True), nullable=False),
        sa.Column('blackout_date', sa.Date(), nullable=False),
        sa.Column('reason',        sa.String(255), nullable=True),
        sa.Column('created_by',    UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(['amenity_id'], ['amenities.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'],     ondelete='SET NULL'),
    )
    op.create_index('ix_amenity_blackout_dates_id',        'amenity_blackout_dates', ['id'])
    op.create_index('ix_amenity_blackout_dates_amenity_id','amenity_blackout_dates', ['amenity_id'])
    op.create_index('ix_amenity_blackout_dates_date',      'amenity_blackout_dates', ['blackout_date'])

    # ── amenity_bookings ──────────────────────────────────────────────────────
    op.create_table('amenity_bookings',
        sa.Column('id',                  UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('created_at',          sa.DateTime(), nullable=False),
        sa.Column('updated_at',          sa.DateTime(), nullable=False),
        sa.Column('is_active',           sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('amenity_id',          UUID(as_uuid=True), nullable=False),
        sa.Column('slot_id',             UUID(as_uuid=True), nullable=True),
        sa.Column('booked_by',           UUID(as_uuid=True), nullable=False),
        sa.Column('society_id',          UUID(as_uuid=True), nullable=False),
        sa.Column('flat_id',             UUID(as_uuid=True), nullable=True),
        sa.Column('booking_date',        sa.Date(), nullable=False),
        sa.Column('start_time',          sa.Time(), nullable=False),
        sa.Column('end_time',            sa.Time(), nullable=False),
        sa.Column('guest_count',         sa.Integer(), nullable=False, server_default='1'),
        sa.Column('purpose',             sa.Text(), nullable=True),
        sa.Column('special_notes',       sa.Text(), nullable=True),
        sa.Column('status',              booking_status_enum, nullable=False, server_default='pending'),
        sa.Column('approved_by',         UUID(as_uuid=True), nullable=True),
        sa.Column('approved_at',         sa.DateTime(), nullable=True),
        sa.Column('rejection_reason',    sa.Text(), nullable=True),
        sa.Column('cancelled_at',        sa.DateTime(), nullable=True),
        sa.Column('cancellation_reason', sa.Text(), nullable=True),
        sa.Column('charge_amount',       sa.Float(), nullable=True),
        sa.Column('deposit_amount',      sa.Float(), nullable=True),
        sa.Column('deposit_paid',        sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('deposit_refunded',    sa.Boolean(), nullable=False, server_default='false'),
        sa.ForeignKeyConstraint(['amenity_id'],  ['amenities.id'],     ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['slot_id'],     ['amenity_slots.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['booked_by'],   ['users.id'],         ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['society_id'],  ['societies.id'],     ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['flat_id'],     ['flats.id'],         ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['approved_by'], ['users.id'],         ondelete='SET NULL'),
    )
    op.create_index('ix_amenity_bookings_id',         'amenity_bookings', ['id'])
    op.create_index('ix_amenity_bookings_amenity_id', 'amenity_bookings', ['amenity_id'])
    op.create_index('ix_amenity_bookings_booked_by',  'amenity_bookings', ['booked_by'])
    op.create_index('ix_amenity_bookings_society_id', 'amenity_bookings', ['society_id'])
    op.create_index('ix_amenity_bookings_date',       'amenity_bookings', ['booking_date'])
    op.create_index('ix_amenity_bookings_status',     'amenity_bookings', ['status'])

    # ── amenity_usage_logs ────────────────────────────────────────────────────
    op.create_table('amenity_usage_logs',
        sa.Column('id',            UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('created_at',    sa.DateTime(), nullable=False),
        sa.Column('updated_at',    sa.DateTime(), nullable=False),
        sa.Column('is_active',     sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('booking_id',    UUID(as_uuid=True), nullable=False),
        sa.Column('amenity_id',    UUID(as_uuid=True), nullable=False),
        sa.Column('society_id',    UUID(as_uuid=True), nullable=False),
        sa.Column('used_by',       UUID(as_uuid=True), nullable=True),
        sa.Column('actual_start',  sa.DateTime(), nullable=True),
        sa.Column('actual_end',    sa.DateTime(), nullable=True),
        sa.Column('guest_count',   sa.Integer(), nullable=True),
        sa.Column('damage_noted',  sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('damage_notes',  sa.Text(), nullable=True),
        sa.Column('extra_charges', sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(['booking_id'], ['amenity_bookings.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['amenity_id'], ['amenities.id'],        ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['society_id'], ['societies.id'],        ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['used_by'],    ['users.id'],            ondelete='SET NULL'),
    )
    op.create_index('ix_amenity_usage_logs_id',         'amenity_usage_logs', ['id'])
    op.create_index('ix_amenity_usage_logs_booking_id', 'amenity_usage_logs', ['booking_id'])
    op.create_index('ix_amenity_usage_logs_amenity_id', 'amenity_usage_logs', ['amenity_id'])


def downgrade() -> None:
    op.drop_table('amenity_usage_logs')
    op.drop_table('amenity_bookings')
    op.drop_table('amenity_blackout_dates')
    op.drop_table('amenity_pricing')
    op.drop_table('amenity_slots')
    op.drop_table('amenity_rules')
    op.drop_table('amenities')
    sa.Enum(name='ruletype').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='bookingstatus').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='amenitytype').drop(op.get_bind(), checkfirst=True)
