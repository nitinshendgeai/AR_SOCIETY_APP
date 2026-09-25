"""db_integrity_audit

Revision ID: d6e7f8a9b0c1
Revises: c5d6e7f8a9b0
Create Date: 2026-09-25

Database integrity pass after a full audit of a fresh `alembic upgrade head`
against the SQLAlchemy models:

1. Relationships: 13 reference columns that had no foreign key get one
   (all nullable, ON DELETE SET NULL). References that already point at a
   row that no longer exists are cleared first, otherwise the constraint
   could not be created on an existing database.
2. Foreign-key indexes: PostgreSQL does not index foreign keys by itself, so
   joins on them and deletes of the parent row (a society, a user…) had to
   scan the child table. Every foreign-key column now has an index, as do the
   columns the models already declared `index=True` but no migration created.
3. Redundant indexes: 81 `ix_<table>_id` indexes duplicated their table's
   primary-key index; they are dropped (TimestampMixin no longer asks for them).
4. Naming: 34 indexes are renamed to the names the models generate, so
   the models and the migrated schema compare clean.
5. forms.code, permissions.code and online_payment_submissions.receipt_number
   keep their uniqueness as a unique index (as the models declare it) instead
   of a unique constraint plus a separate plain index.

Every step is reversible; downgrade restores the previous schema (cleared
dangling references are not restored).
"""
from alembic import op

revision      = 'd6e7f8a9b0c1'
down_revision = 'c5d6e7f8a9b0'
branch_labels = None
depends_on    = None

# (table, column, referenced table) — nullable, ON DELETE SET NULL
NEW_FOREIGN_KEYS = [
    ('amc_contracts', 'asset_id', 'assets'),
    ('amc_contracts', 'renewed_from_id', 'amc_contracts'),
    ('amc_service_schedules', 'visit_log_id', 'service_visit_logs'),
    ('inventory_issues', 'complaint_id', 'complaints'),
    ('inventory_issues', 'task_id', 'staff_tasks'),
    ('parking_access_logs', 'gate_id', 'gates'),
    ('service_requests', 'asset_id', 'assets'),
    ('service_requests', 'complaint_id', 'complaints'),
    ('staff_attendance', 'checkout_approved_by', 'users'),
    ('staff_handovers', 'duty_assignment_id', 'duty_assignments'),
    ('staff_tasks', 'complaint_id', 'complaints'),
    ('staff_tasks', 'visitor_id', 'visitors'),
    ('visitor_parking', 'visitor_id', 'visitors'),
]

# (table, index to drop, column) — duplicates of the primary key, or plain
# indexes replaced by unique ones below
DROP_INDEXES = [
    ('agreement_tracker', 'ix_agreement_tracker_id', 'id'),
    ('amc_contracts', 'ix_amc_contracts_id', 'id'),
    ('amc_service_schedules', 'ix_amc_schedules_id', 'id'),
    ('amenities', 'ix_amenities_id', 'id'),
    ('amenity_blackout_dates', 'ix_amenity_blackout_dates_id', 'id'),
    ('amenity_bookings', 'ix_amenity_bookings_id', 'id'),
    ('amenity_pricing', 'ix_amenity_pricing_id', 'id'),
    ('amenity_rules', 'ix_amenity_rules_id', 'id'),
    ('amenity_slots', 'ix_amenity_slots_id', 'id'),
    ('amenity_usage_logs', 'ix_amenity_usage_logs_id', 'id'),
    ('announcements', 'ix_announcements_id', 'id'),
    ('asset_amc', 'ix_asset_amc_id', 'id'),
    ('asset_maintenance', 'ix_asset_maintenance_id', 'id'),
    ('asset_usage_logs', 'ix_asset_usage_logs_id', 'id'),
    ('assets', 'ix_assets_id', 'id'),
    ('attendance_corrections', 'ix_attendance_corrections_id', 'id'),
    ('audit_logs', 'ix_audit_logs_id', 'id'),
    ('billing_cycles', 'ix_billing_cycles_id', 'id'),
    ('communication_logs', 'ix_communication_logs_id', 'id'),
    ('complaint_attachments', 'ix_complaint_attachments_id', 'id'),
    ('complaint_comments', 'ix_complaint_comments_id', 'id'),
    ('complaint_status_history', 'ix_complaint_status_history_id', 'id'),
    ('complaints', 'ix_complaints_id', 'id'),
    ('due_trackers', 'ix_due_trackers_id', 'id'),
    ('duty_assignments', 'ix_duty_assignments_id', 'id'),
    ('emergency_alerts', 'ix_emergency_alerts_id', 'id'),
    ('financial_periods', 'ix_financial_periods_id', 'id'),
    ('flats', 'ix_flats_id', 'id'),
    ('forms', 'ix_forms_code', 'code'),
    ('gates', 'ix_gates_id', 'id'),
    ('handover_items', 'ix_handover_items_id', 'id'),
    ('inventory_categories', 'ix_inventory_categories_id', 'id'),
    ('inventory_issues', 'ix_inventory_issues_id', 'id'),
    ('inventory_items', 'ix_inventory_items_id', 'id'),
    ('inventory_returns', 'ix_inventory_returns_id', 'id'),
    ('inventory_stock', 'ix_inventory_stock_id', 'id'),
    ('inventory_transactions', 'ix_inventory_transactions_id', 'id'),
    ('invoice_line_items', 'ix_invoice_line_items_id', 'id'),
    ('maintenance_bills', 'ix_maintenance_bills_id', 'id'),
    ('maintenance_charge_configs', 'ix_charge_configs_id', 'id'),
    ('monthly_attendance_summaries', 'ix_monthly_att_summaries_id', 'id'),
    ('notice_acknowledgements', 'ix_notice_acks_id', 'id'),
    ('notices', 'ix_notices_id', 'id'),
    ('notifications', 'ix_notifications_id', 'id'),
    ('occupancy_logs', 'ix_occupancy_logs_id', 'id'),
    ('online_payment_submissions', 'ix_online_payment_submissions_receipt_number', 'receipt_number'),
    ('parking_access_logs', 'ix_parking_access_logs_id', 'id'),
    ('parking_allocations', 'ix_parking_allocations_id', 'id'),
    ('parking_floors', 'ix_parking_floors_id', 'id'),
    ('parking_slots', 'ix_parking_slots_id', 'id'),
    ('parking_violations', 'ix_parking_violations_id', 'id'),
    ('parking_zones', 'ix_parking_zones_id', 'id'),
    ('payment_receipts', 'ix_payment_receipts_id', 'id'),
    ('penalty_rules', 'ix_penalty_rules_id', 'id'),
    ('permissions', 'ix_permissions_code', 'code'),
    ('resident_edit_requests', 'ix_resident_edit_requests_id', 'id'),
    ('residents', 'ix_residents_id', 'id'),
    ('roles', 'ix_roles_id', 'id'),
    ('service_requests', 'ix_service_requests_id', 'id'),
    ('service_visit_logs', 'ix_service_visit_logs_id', 'id'),
    ('societies', 'ix_societies_id', 'id'),
    ('staff', 'ix_staff_id', 'id'),
    ('staff_attendance', 'ix_staff_attendance_id', 'id'),
    ('staff_designations', 'ix_staff_designations_id', 'id'),
    ('staff_handovers', 'ix_staff_handovers_id', 'id'),
    ('staff_leave_balances', 'ix_staff_leave_balances_id', 'id'),
    ('staff_leaves', 'ix_staff_leaves_id', 'id'),
    ('staff_rosters', 'ix_staff_rosters_id', 'id'),
    ('staff_salary_structures', 'ix_staff_salary_structures_id', 'id'),
    ('staff_shifts', 'ix_staff_shifts_id', 'id'),
    ('staff_tasks', 'ix_staff_tasks_id', 'id'),
    ('staff_work_logs', 'ix_staff_work_logs_id', 'id'),
    ('tenants', 'ix_tenants_id', 'id'),
    ('user_roles', 'ix_user_roles_id', 'id'),
    ('users', 'ix_users_id', 'id'),
    ('vehicles', 'ix_vehicles_id', 'id'),
    ('vendor_invoices', 'ix_vendor_invoices_id', 'id'),
    ('vendor_services', 'ix_vendor_services_id', 'id'),
    ('vendors', 'ix_vendors_id', 'id'),
    ('visitor_logs', 'ix_visitor_logs_id', 'id'),
    ('visitor_parking', 'ix_visitor_parking_id', 'id'),
    ('visitor_vehicles', 'ix_visitor_vehicles_id', 'id'),
    ('visitors', 'ix_visitors_id', 'id'),
    ('wings', 'ix_wings_id', 'id'),
]

# (table, old name, new name)
RENAME_INDEXES = [
    ('agreement_tracker', 'ix_agreement_tracker_number', 'ix_agreement_tracker_agreement_number'),
    ('amc_service_schedules', 'ix_amc_schedules_contract_id', 'ix_amc_service_schedules_contract_id'),
    ('amc_service_schedules', 'ix_amc_schedules_date', 'ix_amc_service_schedules_scheduled_date'),
    ('amc_service_schedules', 'ix_amc_schedules_status', 'ix_amc_service_schedules_status'),
    ('amenities', 'ix_amenities_type', 'ix_amenities_amenity_type'),
    ('amenity_blackout_dates', 'ix_amenity_blackout_dates_date', 'ix_amenity_blackout_dates_blackout_date'),
    ('amenity_bookings', 'ix_amenity_bookings_date', 'ix_amenity_bookings_booking_date'),
    ('amenity_slots', 'ix_amenity_slots_date', 'ix_amenity_slots_slot_date'),
    ('announcements', 'ix_announcements_published', 'ix_announcements_is_published'),
    ('asset_maintenance', 'ix_asset_maintenance_type', 'ix_asset_maintenance_maintenance_type'),
    ('assets', 'ix_assets_category', 'ix_assets_asset_category'),
    ('assets', 'ix_assets_code', 'ix_assets_asset_code'),
    ('assets', 'ix_assets_serial', 'ix_assets_serial_number'),
    ('attendance_corrections', 'ix_attendance_corrections_date', 'ix_attendance_corrections_correction_date'),
    ('duty_assignments', 'ix_duty_assignments_date', 'ix_duty_assignments_duty_date'),
    ('emergency_alerts', 'ix_emergency_alerts_type', 'ix_emergency_alerts_alert_type'),
    ('inventory_items', 'ix_inventory_items_code', 'ix_inventory_items_item_code'),
    ('inventory_transactions', 'ix_inventory_transactions_type', 'ix_inventory_transactions_transaction_type'),
    ('maintenance_bills', 'ix_maintenance_bills_status', 'ix_maintenance_bills_bill_status'),
    ('maintenance_charge_configs', 'ix_charge_configs_society_id', 'ix_maintenance_charge_configs_society_id'),
    ('maintenance_charge_configs', 'ix_charge_configs_type', 'ix_maintenance_charge_configs_charge_type'),
    ('monthly_attendance_summaries', 'ix_monthly_att_summaries_month', 'ix_monthly_attendance_summaries_month'),
    ('monthly_attendance_summaries', 'ix_monthly_att_summaries_staff_id', 'ix_monthly_attendance_summaries_staff_id'),
    ('monthly_attendance_summaries', 'ix_monthly_att_summaries_year', 'ix_monthly_attendance_summaries_year'),
    ('notice_acknowledgements', 'ix_notice_acks_notice_id', 'ix_notice_acknowledgements_notice_id'),
    ('notice_acknowledgements', 'ix_notice_acks_user_id', 'ix_notice_acknowledgements_user_id'),
    ('notices', 'ix_notices_audience', 'ix_notices_audience_type'),
    ('payment_receipts', 'ix_payment_receipts_mode', 'ix_payment_receipts_payment_mode'),
    ('staff_attendance', 'ix_staff_attendance_date', 'ix_staff_attendance_attendance_date'),
    ('staff_designations', 'ix_staff_designations_dept', 'ix_staff_designations_department'),
    ('staff_leaves', 'ix_staff_leaves_type', 'ix_staff_leaves_leave_type'),
    ('vendor_invoices', 'ix_vendor_invoices_inv_date', 'ix_vendor_invoices_invoice_date'),
    ('vendors', 'ix_vendors_company', 'ix_vendors_company_name'),
    ('vendors', 'ix_vendors_gst', 'ix_vendors_gst_number'),
]

# (table, index, column, unique)
CREATE_INDEXES = [
    ('agreement_tracker', 'ix_agreement_tracker_created_by', 'created_by', False),
    ('agreement_tracker', 'ix_agreement_tracker_renewal_of_id', 'renewal_of_id', False),
    ('agreement_tracker', 'ix_agreement_tracker_resident_id', 'resident_id', False),
    ('agreement_tracker', 'ix_agreement_tracker_society_id', 'society_id', False),
    ('agreement_tracker', 'ix_agreement_tracker_start_date', 'start_date', False),
    ('amc_contracts', 'ix_amc_contracts_category', 'category', False),
    ('amc_contracts', 'ix_amc_contracts_created_by', 'created_by', False),
    ('amc_contracts', 'ix_amc_contracts_renewed_from_id', 'renewed_from_id', False),
    ('amc_service_schedules', 'ix_amc_service_schedules_society_id', 'society_id', False),
    ('amc_service_schedules', 'ix_amc_service_schedules_visit_log_id', 'visit_log_id', False),
    ('amenity_blackout_dates', 'ix_amenity_blackout_dates_created_by', 'created_by', False),
    ('amenity_bookings', 'ix_amenity_bookings_approved_by', 'approved_by', False),
    ('amenity_bookings', 'ix_amenity_bookings_flat_id', 'flat_id', False),
    ('amenity_bookings', 'ix_amenity_bookings_slot_id', 'slot_id', False),
    ('amenity_usage_logs', 'ix_amenity_usage_logs_society_id', 'society_id', False),
    ('amenity_usage_logs', 'ix_amenity_usage_logs_used_by', 'used_by', False),
    ('announcements', 'ix_announcements_category', 'category', False),
    ('announcements', 'ix_announcements_created_by', 'created_by', False),
    ('asset_amc', 'ix_asset_amc_society_id', 'society_id', False),
    ('asset_maintenance', 'ix_asset_maintenance_performed_by', 'performed_by', False),
    ('asset_maintenance', 'ix_asset_maintenance_society_id', 'society_id', False),
    ('asset_usage_logs', 'ix_asset_usage_logs_logged_by', 'logged_by', False),
    ('asset_usage_logs', 'ix_asset_usage_logs_society_id', 'society_id', False),
    ('assets', 'ix_assets_assigned_to_user', 'assigned_to_user', False),
    ('attendance_corrections', 'ix_attendance_corrections_approved_by', 'approved_by', False),
    ('attendance_corrections', 'ix_attendance_corrections_attendance_id', 'attendance_id', False),
    ('attendance_corrections', 'ix_attendance_corrections_requested_by', 'requested_by', False),
    ('attendance_corrections', 'ix_attendance_corrections_society_id', 'society_id', False),
    ('bank_statement_entries', 'ix_bank_statement_entries_imported_by', 'imported_by', False),
    ('bank_statement_entries', 'ix_bank_statement_entries_matched_by', 'matched_by', False),
    ('billing_cycles', 'ix_billing_cycles_created_by', 'created_by', False),
    ('billing_cycles', 'ix_billing_cycles_period_id', 'period_id', False),
    ('checklist_templates', 'ix_checklist_templates_created_by', 'created_by', False),
    ('communication_logs', 'ix_communication_logs_user_id', 'user_id', False),
    ('complaint_attachments', 'ix_complaint_attachments_uploaded_by', 'uploaded_by', False),
    ('complaint_comments', 'ix_complaint_comments_author_id', 'author_id', False),
    ('complaint_status_history', 'ix_complaint_status_history_changed_by', 'changed_by', False),
    ('complaints', 'ix_complaints_assigned_by', 'assigned_by', False),
    ('complaints', 'ix_complaints_flat_id', 'flat_id', False),
    ('due_trackers', 'ix_due_trackers_last_updated_by', 'last_updated_by', False),
    ('duty_assignments', 'ix_duty_assignments_assigned_by', 'assigned_by', False),
    ('duty_assignments', 'ix_duty_assignments_checklist_template_id', 'checklist_template_id', False),
    ('duty_assignments', 'ix_duty_assignments_shift_id', 'shift_id', False),
    ('duty_assignments', 'ix_duty_assignments_verified_by', 'verified_by', False),
    ('duty_checklist_items', 'ix_duty_checklist_items_template_item_id', 'template_item_id', False),
    ('emergency_alerts', 'ix_emergency_alerts_resolved_by', 'resolved_by', False),
    ('emergency_alerts', 'ix_emergency_alerts_triggered_by', 'triggered_by', False),
    ('financial_periods', 'ix_financial_periods_closed_by', 'closed_by', False),
    ('forms', 'ix_forms_code', 'code', True),
    ('inventory_issues', 'ix_inventory_issues_complaint_id', 'complaint_id', False),
    ('inventory_issues', 'ix_inventory_issues_issued_by', 'issued_by', False),
    ('inventory_issues', 'ix_inventory_issues_task_id', 'task_id', False),
    ('inventory_returns', 'ix_inventory_returns_received_by', 'received_by', False),
    ('inventory_returns', 'ix_inventory_returns_returned_by', 'returned_by', False),
    ('inventory_returns', 'ix_inventory_returns_society_id', 'society_id', False),
    ('inventory_stock', 'ix_inventory_stock_last_updated_by', 'last_updated_by', False),
    ('inventory_stock', 'ix_inventory_stock_society_id', 'society_id', False),
    ('inventory_transactions', 'ix_inventory_transactions_performed_by', 'performed_by', False),
    ('inventory_transactions', 'ix_inventory_transactions_society_id', 'society_id', False),
    ('maintenance_bills', 'ix_maintenance_bills_generated_by', 'generated_by', False),
    ('monthly_attendance_summaries', 'ix_monthly_attendance_summaries_finalized_by', 'finalized_by', False),
    ('monthly_attendance_summaries', 'ix_monthly_attendance_summaries_society_id', 'society_id', False),
    ('notice_acknowledgements', 'ix_notice_acknowledgements_flat_id', 'flat_id', False),
    ('notices', 'ix_notices_created_by', 'created_by', False),
    ('occupancy_logs', 'ix_occupancy_logs_logged_by', 'logged_by', False),
    ('occupancy_logs', 'ix_occupancy_logs_society_id', 'society_id', False),
    ('occupancy_logs', 'ix_occupancy_logs_wing_id', 'wing_id', False),
    ('online_payment_submissions', 'ix_online_payment_submissions_receipt_number', 'receipt_number', True),
    ('online_payment_submissions', 'ix_online_payment_submissions_recorded_by', 'recorded_by', False),
    ('online_payment_submissions', 'ix_online_payment_submissions_reviewed_by', 'reviewed_by', False),
    ('parking_access_logs', 'ix_parking_access_logs_access_type', 'access_type', False),
    ('parking_access_logs', 'ix_parking_access_logs_gate_id', 'gate_id', False),
    ('parking_access_logs', 'ix_parking_access_logs_slot_id', 'slot_id', False),
    ('parking_access_logs', 'ix_parking_access_logs_user_id', 'user_id', False),
    ('parking_access_logs', 'ix_parking_access_logs_vehicle_id', 'vehicle_id', False),
    ('parking_allocations', 'ix_parking_allocations_allocated_by', 'allocated_by', False),
    ('parking_allocations', 'ix_parking_allocations_allocated_to_user', 'allocated_to_user', False),
    ('parking_allocations', 'ix_parking_allocations_allocation_type', 'allocation_type', False),
    ('parking_allocations', 'ix_parking_allocations_released_by', 'released_by', False),
    ('parking_allocations', 'ix_parking_allocations_society_id', 'society_id', False),
    ('parking_allocations', 'ix_parking_allocations_vehicle_id', 'vehicle_id', False),
    ('parking_floors', 'ix_parking_floors_society_id', 'society_id', False),
    ('parking_slots', 'ix_parking_slots_floor_id', 'floor_id', False),
    ('parking_violations', 'ix_parking_violations_reported_by', 'reported_by', False),
    ('parking_violations', 'ix_parking_violations_resolved_by', 'resolved_by', False),
    ('parking_violations', 'ix_parking_violations_slot_id', 'slot_id', False),
    ('parking_violations', 'ix_parking_violations_vehicle_id', 'vehicle_id', False),
    ('parking_violations', 'ix_parking_violations_violation_type', 'violation_type', False),
    ('payment_receipts', 'ix_payment_receipts_received_by', 'received_by', False),
    ('permissions', 'ix_permissions_code', 'code', True),
    ('resident_edit_requests', 'ix_resident_edit_requests_reviewed_by', 'reviewed_by', False),
    ('service_requests', 'ix_service_requests_asset_id', 'asset_id', False),
    ('service_requests', 'ix_service_requests_assigned_by', 'assigned_by', False),
    ('service_requests', 'ix_service_requests_category', 'category', False),
    ('service_requests', 'ix_service_requests_complaint_id', 'complaint_id', False),
    ('service_requests', 'ix_service_requests_verified_by', 'verified_by', False),
    ('service_visit_logs', 'ix_service_visit_logs_logged_by', 'logged_by', False),
    ('service_visit_logs', 'ix_service_visit_logs_society_id', 'society_id', False),
    ('service_visit_logs', 'ix_service_visit_logs_vendor_id', 'vendor_id', False),
    ('staff', 'ix_staff_designation_id', 'designation_id', False),
    ('staff', 'ix_staff_shift_id', 'shift_id', False),
    ('staff_attendance', 'ix_staff_attendance_approved_by', 'approved_by', False),
    ('staff_attendance', 'ix_staff_attendance_checkout_approved_by', 'checkout_approved_by', False),
    ('staff_attendance', 'ix_staff_attendance_marked_by', 'marked_by', False),
    ('staff_handovers', 'ix_staff_handovers_duty_assignment_id', 'duty_assignment_id', False),
    ('staff_handovers', 'ix_staff_handovers_verified_by', 'verified_by', False),
    ('staff_leave_balances', 'ix_staff_leave_balances_society_id', 'society_id', False),
    ('staff_leaves', 'ix_staff_leaves_approved_by', 'approved_by', False),
    ('staff_rosters', 'ix_staff_rosters_created_by', 'created_by', False),
    ('staff_rosters', 'ix_staff_rosters_shift_id', 'shift_id', False),
    ('staff_salary_structures', 'ix_staff_salary_structures_created_by', 'created_by', False),
    ('staff_salary_structures', 'ix_staff_salary_structures_society_id', 'society_id', False),
    ('staff_tasks', 'ix_staff_tasks_assigned_by', 'assigned_by', False),
    ('staff_tasks', 'ix_staff_tasks_complaint_id', 'complaint_id', False),
    ('staff_tasks', 'ix_staff_tasks_verified_by', 'verified_by', False),
    ('staff_tasks', 'ix_staff_tasks_visitor_id', 'visitor_id', False),
    ('staff_work_logs', 'ix_staff_work_logs_society_id', 'society_id', False),
    ('vehicles', 'ix_vehicles_registered_by', 'registered_by', False),
    ('vehicles', 'ix_vehicles_tenant_id', 'tenant_id', False),
    ('vendor_invoices', 'ix_vendor_invoices_approved_by', 'approved_by', False),
    ('vendor_invoices', 'ix_vendor_invoices_contract_id', 'contract_id', False),
    ('vendor_invoices', 'ix_vendor_invoices_invoice_number', 'invoice_number', False),
    ('vendor_invoices', 'ix_vendor_invoices_request_id', 'request_id', False),
    ('vendors', 'ix_vendors_registered_by', 'registered_by', False),
    ('visitor_logs', 'ix_visitor_logs_gate_id', 'gate_id', False),
    ('visitor_logs', 'ix_visitor_logs_performed_by', 'performed_by', False),
    ('visitor_parking', 'ix_visitor_parking_assigned_by', 'assigned_by', False),
    ('visitor_parking', 'ix_visitor_parking_host_flat_id', 'host_flat_id', False),
    ('visitor_parking', 'ix_visitor_parking_slot_id', 'slot_id', False),
    ('visitor_parking', 'ix_visitor_parking_visitor_id', 'visitor_id', False),
    ('visitors', 'ix_visitors_approved_by', 'approved_by', False),
    ('visitors', 'ix_visitors_gate_id', 'gate_id', False),
    ('visitors', 'ix_visitors_logged_by', 'logged_by', False),
    ('visitors', 'ix_visitors_visitor_type', 'visitor_type', False),
]

# (table, unique constraint superseded by a unique index, column)
DROP_UNIQUE_CONSTRAINTS = [
    ('forms', 'uq_forms_code', 'code'),
    ('online_payment_submissions', 'uq_online_payment_submissions_receipt_number', 'receipt_number'),
    ('permissions', 'uq_permissions_code', 'code'),
]


def _fk_name(table, column):
    return f"{table}_{column}_fkey"


# Every step is guarded (IF EXISTS / IF NOT EXISTS) so the migration applies
# cleanly to databases whose indexes drifted from a fresh `upgrade head` — some
# production objects were created outside migrations — and a failure here
# would stop the app from starting.

def _drop_index(name):
    op.execute(f'DROP INDEX IF EXISTS "{name}"')


def _create_index(name, table, column, unique=False):
    op.execute(f'CREATE {"UNIQUE " if unique else ""}INDEX IF NOT EXISTS "{name}" ON "{table}" ("{column}")')


def _rename_index(old, new):
    # Rename when only the old name exists; when both do, the old one is a duplicate.
    op.execute(f"""
        DO $$ BEGIN
            IF to_regclass('"{old}"') IS NOT NULL THEN
                IF to_regclass('"{new}"') IS NULL THEN
                    ALTER INDEX "{old}" RENAME TO "{new}";
                ELSE
                    DROP INDEX "{old}";
                END IF;
            END IF;
        END $$;
    """)


def _add_unique_constraint(name, table, column):
    op.execute(f"""
        DO $$ BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = '{name}') THEN
                ALTER TABLE "{table}" ADD CONSTRAINT "{name}" UNIQUE ("{column}");
            END IF;
        END $$;
    """)


def _add_foreign_key(table, column, ref):
    # Skip when the column already has a foreign key, under any name.
    op.execute(f"""
        DO $$ BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint c
                JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = ANY (c.conkey)
                WHERE c.contype = 'f' AND c.conrelid = '"{table}"'::regclass AND a.attname = '{column}'
            ) THEN
                UPDATE "{table}" SET "{column}" = NULL WHERE "{column}" IS NOT NULL
                    AND NOT EXISTS (SELECT 1 FROM "{ref}" r WHERE r.id = "{table}"."{column}");
                ALTER TABLE "{table}" ADD CONSTRAINT "{_fk_name(table, column)}"
                    FOREIGN KEY ("{column}") REFERENCES "{ref}" (id) ON DELETE SET NULL;
            END IF;
        END $$;
    """)


def upgrade():
    for table, name, _ in DROP_INDEXES:
        _drop_index(name)
    for table, old, new in RENAME_INDEXES:
        _rename_index(old, new)
    for table, name, column, unique in CREATE_INDEXES:
        _create_index(name, table, column, unique)
    for table, name, _ in DROP_UNIQUE_CONSTRAINTS:
        op.execute(f'ALTER TABLE "{table}" DROP CONSTRAINT IF EXISTS "{name}"')
    for table, column, ref in NEW_FOREIGN_KEYS:
        _add_foreign_key(table, column, ref)


def downgrade():
    for table, column, _ in reversed(NEW_FOREIGN_KEYS):
        op.execute(f'ALTER TABLE "{table}" DROP CONSTRAINT IF EXISTS "{_fk_name(table, column)}"')
    for table, name, column in reversed(DROP_UNIQUE_CONSTRAINTS):
        _add_unique_constraint(name, table, column)
    for table, name, _, _ in reversed(CREATE_INDEXES):
        _drop_index(name)
    for table, old, new in reversed(RENAME_INDEXES):
        _rename_index(new, old)
    for table, name, column in reversed(DROP_INDEXES):
        _create_index(name, table, column)
