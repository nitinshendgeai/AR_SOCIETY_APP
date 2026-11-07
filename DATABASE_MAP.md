# Database map — 140 tables, 562 indexes, 36 unique constraints, 417 FK constraints, 2 check constraints

Generated from SQLAlchemy model metadata (what Alembic autogenerate would create). Primary-key indexes are implicit.

## Module: accounts  (14 tables)

### `account_groups`  — 10 cols, PK(id)
- FKs: society_id→societies.id
- UNIQUE constraint `uq_account_groups_society_name`: (society_id, name)
- INDEX `ix_account_groups_society_id` (society_id)

### `account_year_closings`  — 20 cols, PK(id)
- FKs: reopened_by→users.id; closing_voucher_id→vouchers.id; society_id→societies.id; closed_by→users.id
- INDEX `ix_account_year_closings_fiscal_year` (fiscal_year)
- INDEX `ix_account_year_closings_society_id` (society_id)

### `accounting_entities`  — 11 cols, PK(id)
- FKs: society_id→societies.id
- UNIQUE constraint `uq_accounting_entity_source`: (society_id, entity_type, source_id)
- UNIQUE constraint `uq_accounting_entity_code`: (society_id, entity_code)
- INDEX `ix_accounting_entities_entity_type` (entity_type)
- INDEX `ix_accounting_entities_society_id` (society_id)
- INDEX `ix_accounting_entities_source_id` (source_id)

### `accounting_posting_errors`  — 18 cols, PK(id)
- FKs: resolved_by→users.id; society_id→societies.id; last_voucher_id→vouchers.id
- UNIQUE constraint `uq_accounting_posting_error_source`: (society_id, source_type, source_id, operation)
- INDEX `ix_accounting_posting_errors_society_id` (society_id)
- INDEX `ix_accounting_posting_errors_source_id` (source_id)
- INDEX `ix_accounting_posting_errors_source_type` (source_type)
- INDEX `ix_accounting_posting_errors_status` (status)

### `accounting_tax_configurations`  — 19 cols, PK(id)
- FKs: society_id→societies.id
- UNIQUE constraint `uq_tax_config_society_code`: (society_id, code)
- INDEX `ix_accounting_tax_configurations_is_active` (is_active)
- INDEX `ix_accounting_tax_configurations_society_id` (society_id)
- INDEX `ix_accounting_tax_configurations_tax_type` (tax_type)

### `accounts`  — 22 cols, PK(id)
- FKs: group_id→account_groups.id; maintenance_element_id→maintenance_elements.id; society_id→societies.id
- UNIQUE constraint `uq_accounts_society_name`: (society_id, name)
- INDEX `ix_accounts_group_id` (group_id)
- INDEX `ix_accounts_maintenance_element_id` (maintenance_element_id)
- INDEX `ix_accounts_society_id` (society_id)
- INDEX `ix_accounts_system_key` (system_key)

### `entity_accounts`  — 10 cols, PK(id)
- FKs: entity_id→accounting_entities.id; society_id→societies.id; control_account_id→accounts.id
- UNIQUE constraint `uq_entity_account_number`: (society_id, account_number)
- UNIQUE constraint `uq_entity_account_subledger`: (entity_id, subledger_type)
- INDEX `ix_entity_accounts_control_account_id` (control_account_id)
- INDEX `ix_entity_accounts_entity_id` (entity_id)
- INDEX `ix_entity_accounts_society_id` (society_id)
- INDEX `ix_entity_accounts_subledger_type` (subledger_type)

### `petty_cash_counts`  — 10 cols, PK(id)
- FKs: society_id→societies.id; counted_by→users.id
- INDEX `ix_petty_cash_counts_count_date` (count_date)
- INDEX `ix_petty_cash_counts_society_id` (society_id)

### `petty_cash_settings`  — 8 cols, PK(id)
- FKs: society_id→societies.id
- UNIQUE constraint `uq_petty_cash_settings_society`: (society_id)
- INDEX `ix_petty_cash_settings_society_id` (society_id)

### `recurring_expense_runs`  — 11 cols, PK(id)
- FKs: decided_by→users.id; society_id→societies.id; recurring_id→recurring_expenses.id; voucher_id→vouchers.id
- UNIQUE constraint `uq_recurring_run_month`: (recurring_id, month)
- INDEX `ix_recurring_expense_runs_recurring_id` (recurring_id)
- INDEX `ix_recurring_expense_runs_society_id` (society_id)

### `recurring_expenses`  — 16 cols, PK(id)
- FKs: paid_from_id→accounts.id; vendor_id→vendors.id; expense_account_id→accounts.id; society_id→societies.id; created_by→users.id
- INDEX `ix_recurring_expenses_expense_account_id` (expense_account_id)
- INDEX `ix_recurring_expenses_society_id` (society_id)
- INDEX `ix_recurring_expenses_vendor_id` (vendor_id)

### `voucher_entries`  — 16 cols, PK(id)
- FKs: voucher_id→vouchers.id; entity_account_id→entity_accounts.id; flat_id→flats.id; cleared_by→users.id; vendor_id→vendors.id; account_id→accounts.id
- INDEX `ix_voucher_entries_account_id` (account_id)
- INDEX `ix_voucher_entries_cleared_date` (cleared_date)
- INDEX `ix_voucher_entries_entity_account_id` (entity_account_id)
- INDEX `ix_voucher_entries_flat_id` (flat_id)
- INDEX `ix_voucher_entries_matched_row_id` (matched_row_id)
- INDEX `ix_voucher_entries_vendor_id` (vendor_id)
- INDEX `ix_voucher_entries_voucher_id` (voucher_id)

### `voucher_revisions`  — 9 cols, PK(id)
- FKs: edited_by→users.id; voucher_id→vouchers.id
- INDEX `ix_voucher_revisions_voucher_id` (voucher_id)

### `vouchers`  — 30 cols, PK(id)
- FKs: cancelled_by→users.id; vendor_id→vendors.id; approved_by→users.id; reversal_of_id→vouchers.id; created_by→users.id; society_id→societies.id; edited_by→users.id; submitted_by→users.id
- UNIQUE constraint `uq_vouchers_society_number`: (society_id, voucher_number)
- INDEX `ix_vouchers_approval_status` (approval_status)
- INDEX `ix_vouchers_fiscal_year` (fiscal_year)
- INDEX `ix_vouchers_is_cancelled` (is_cancelled)
- INDEX `ix_vouchers_society_id` (society_id)
- INDEX `ix_vouchers_source_id` (source_id)
- INDEX `ix_vouchers_source_type` (source_type)
- INDEX `ix_vouchers_vendor_id` (vendor_id)
- INDEX `ix_vouchers_voucher_date` (voucher_date)
- INDEX `ix_vouchers_voucher_type` (voucher_type)


## Module: amenity  (7 tables)

### `amenities`  — 16 cols, PK(id)
- FKs: society_id→societies.id
- INDEX `ix_amenities_amenity_type` (amenity_type)
- INDEX `ix_amenities_society_id` (society_id)

### `amenity_blackout_dates`  — 8 cols, PK(id)
- FKs: amenity_id→amenities.id; created_by→users.id
- INDEX `ix_amenity_blackout_dates_amenity_id` (amenity_id)
- INDEX `ix_amenity_blackout_dates_blackout_date` (blackout_date)
- INDEX `ix_amenity_blackout_dates_created_by` (created_by)

### `amenity_bookings`  — 25 cols, PK(id)
- FKs: flat_id→flats.id; booked_by→users.id; amenity_id→amenities.id; approved_by→users.id; society_id→societies.id; slot_id→amenity_slots.id
- INDEX `ix_amenity_bookings_amenity_id` (amenity_id)
- INDEX `ix_amenity_bookings_approved_by` (approved_by)
- INDEX `ix_amenity_bookings_booked_by` (booked_by)
- INDEX `ix_amenity_bookings_booking_date` (booking_date)
- INDEX `ix_amenity_bookings_flat_id` (flat_id)
- INDEX `ix_amenity_bookings_slot_id` (slot_id)
- INDEX `ix_amenity_bookings_society_id` (society_id)
- INDEX `ix_amenity_bookings_status` (status)

### `amenity_pricing`  — 10 cols, PK(id)
- FKs: amenity_id→amenities.id
- INDEX `ix_amenity_pricing_amenity_id` (amenity_id)

### `amenity_rules`  — 8 cols, PK(id)
- FKs: amenity_id→amenities.id
- INDEX `ix_amenity_rules_amenity_id` (amenity_id)
- INDEX `ix_amenity_rules_rule_type` (rule_type)

### `amenity_slots`  — 11 cols, PK(id)
- FKs: amenity_id→amenities.id
- INDEX `ix_amenity_slots_amenity_id` (amenity_id)
- INDEX `ix_amenity_slots_slot_date` (slot_date)

### `amenity_usage_logs`  — 14 cols, PK(id)
- FKs: booking_id→amenity_bookings.id; society_id→societies.id; used_by→users.id; amenity_id→amenities.id
- INDEX `ix_amenity_usage_logs_amenity_id` (amenity_id)
- INDEX `ix_amenity_usage_logs_booking_id` (booking_id)
- INDEX `ix_amenity_usage_logs_society_id` (society_id)
- INDEX `ix_amenity_usage_logs_used_by` (used_by)


## Module: automation  (2 tables)

### `scheduled_job_runs`  — 12 cols, PK(id)
- FKs: society_id→societies.id
- UNIQUE constraint `uq_scheduled_job_run`: (job, society_id, period_key)
- INDEX `ix_scheduled_job_runs_job` (job)
- INDEX `ix_scheduled_job_runs_society_id` (society_id)

### `society_automation`  — 12 cols, PK(id)
- FKs: society_id→societies.id
- UNIQUE constraint `uq_society_automation_society`: (society_id)
- INDEX `ix_society_automation_society_id` (society_id)


## Module: billing  (19 tables)

### `bank_statement_balances`  — 10 cols, PK(id)
- FKs: entered_by→users.id; bank_account_id→accounts.id; society_id→societies.id
- UNIQUE constraint `uq_bank_statement_balance_day`: (bank_account_id, as_on)
- INDEX `ix_bank_statement_balances_bank_account_id` (bank_account_id)
- INDEX `ix_bank_statement_balances_society_id` (society_id)

### `bank_statement_entries`  — 18 cols, PK(id)
- FKs: matched_entry_id→voucher_entries.id; matched_by→users.id; imported_by→users.id; society_id→societies.id; bank_account_id→accounts.id; matched_submission_id→online_payment_submissions.id
- INDEX `ix_bank_statement_entries_bank_account_id` (bank_account_id)
- INDEX `ix_bank_statement_entries_imported_by` (imported_by)
- INDEX `ix_bank_statement_entries_match_status` (match_status)
- INDEX `ix_bank_statement_entries_matched_by` (matched_by)
- INDEX `ix_bank_statement_entries_matched_entry_id` (matched_entry_id)
- INDEX `ix_bank_statement_entries_matched_submission_id` (matched_submission_id)
- INDEX `ix_bank_statement_entries_reference` (reference)
- INDEX `ix_bank_statement_entries_society_id` (society_id)
- INDEX `ix_bank_statement_entries_txn_date` (txn_date)

### `billing_cycles`  — 17 cols, PK(id)
- FKs: society_id→societies.id; created_by→users.id; period_id→financial_periods.id
- INDEX `ix_billing_cycles_created_by` (created_by)
- INDEX `ix_billing_cycles_due_date` (due_date)
- INDEX `ix_billing_cycles_period_id` (period_id)
- INDEX `ix_billing_cycles_society_id` (society_id)

### `billing_expense_allocations`  — 18 cols, PK(id)
- FKs: charge_id→maintenance_charge_configs.id; element_id→maintenance_elements.id; cycle_id→billing_cycles.id; society_id→societies.id
- INDEX `ix_billing_expense_allocations_charge_id` (charge_id)
- INDEX `ix_billing_expense_allocations_cycle_id` (cycle_id)
- INDEX `ix_billing_expense_allocations_element_id` (element_id)
- INDEX `ix_billing_expense_allocations_society_id` (society_id)

### `billing_expense_sources`  — 11 cols, PK(id)
- FKs: account_id→accounts.id; voucher_id→vouchers.id; allocation_id→billing_expense_allocations.id
- INDEX `ix_billing_expense_sources_allocation_id` (allocation_id)
- INDEX `ix_billing_expense_sources_voucher_id` (voucher_id)

### `due_trackers`  — 16 cols, PK(id)
- FKs: flat_id→flats.id; last_updated_by→users.id; society_id→societies.id
- UNIQUE INDEX `ix_due_trackers_flat_id` (flat_id)
- INDEX `ix_due_trackers_last_updated_by` (last_updated_by)
- INDEX `ix_due_trackers_society_id` (society_id)

### `financial_periods`  — 10 cols, PK(id)
- FKs: closed_by→users.id; society_id→societies.id
- INDEX `ix_financial_periods_closed_by` (closed_by)
- INDEX `ix_financial_periods_period_start` (period_start)
- INDEX `ix_financial_periods_society_id` (society_id)

### `flat_charges`  — 23 cols, PK(id)
- FKs: created_by→users.id; flat_id→flats.id; cancelled_by→users.id; bill_id→maintenance_bills.id; society_id→societies.id
- INDEX `ix_flat_charges_bill_id` (bill_id)
- INDEX `ix_flat_charges_cancelled_by` (cancelled_by)
- INDEX `ix_flat_charges_created_by` (created_by)
- INDEX `ix_flat_charges_effective_date` (effective_date)
- INDEX `ix_flat_charges_flat_id` (flat_id)
- INDEX `ix_flat_charges_kind` (kind)
- INDEX `ix_flat_charges_society_id` (society_id)
- INDEX `ix_flat_charges_source_id` (source_id)
- INDEX `ix_flat_charges_source_type` (source_type)
- INDEX `ix_flat_charges_status` (status)

### `interest_waivers`  — 16 cols, PK(id)
- FKs: created_by→users.id; cancelled_by→users.id; flat_id→flats.id; society_id→societies.id
- INDEX `ix_interest_waivers_cancelled_by` (cancelled_by)
- INDEX `ix_interest_waivers_created_by` (created_by)
- INDEX `ix_interest_waivers_flat_id` (flat_id)
- INDEX `ix_interest_waivers_society_id` (society_id)
- INDEX `ix_interest_waivers_status` (status)

### `invoice_line_items`  — 14 cols, PK(id)
- FKs: allocation_id→billing_expense_allocations.id; bill_id→maintenance_bills.id
- INDEX `ix_invoice_line_items_allocation_id` (allocation_id)
- INDEX `ix_invoice_line_items_bill_id` (bill_id)

### `maintenance_bills`  — 31 cols, PK(id)
- FKs: generated_by→users.id; flat_id→flats.id; resident_id→residents.id; cycle_id→billing_cycles.id; society_id→societies.id
- UNIQUE constraint `uq_bill_society_invoice_number`: (society_id, invoice_number)
- INDEX `ix_maintenance_bills_bill_status` (bill_status)
- INDEX `ix_maintenance_bills_cycle_id` (cycle_id)
- INDEX `ix_maintenance_bills_due_date` (due_date)
- INDEX `ix_maintenance_bills_flat_id` (flat_id)
- INDEX `ix_maintenance_bills_generated_by` (generated_by)
- INDEX `ix_maintenance_bills_invoice_number` (invoice_number)
- INDEX `ix_maintenance_bills_resident_id` (resident_id)
- INDEX `ix_maintenance_bills_society_id` (society_id)

### `maintenance_charge_configs`  — 24 cols, PK(id)
- FKs: society_id→societies.id; parking_zone_id→parking_zones.id; element_id→maintenance_elements.id
- INDEX `ix_maintenance_charge_configs_charge_type` (charge_type)
- INDEX `ix_maintenance_charge_configs_element_id` (element_id)
- INDEX `ix_maintenance_charge_configs_parking_zone_id` (parking_zone_id)
- INDEX `ix_maintenance_charge_configs_society_id` (society_id)

### `maintenance_elements`  — 16 cols, PK(id)
- FKs: society_id→societies.id
- UNIQUE constraint `uq_maintenance_element_code`: (society_id, code)
- INDEX `ix_maintenance_elements_society_id` (society_id)

### `maintenance_settings`  — 22 cols, PK(id)
- FKs: society_id→societies.id
- UNIQUE INDEX `ix_maintenance_settings_society_id` (society_id)

### `online_payment_submissions`  — 25 cols, PK(id)
- FKs: flat_id→flats.id; society_id→societies.id; reviewed_by→users.id; bill_id→maintenance_bills.id; wing_id→wings.id; deposit_account_id→accounts.id; recorded_by→users.id
- UNIQUE constraint `uq_online_payment_society_receipt`: (society_id, receipt_number)
- INDEX `ix_online_payment_submissions_bill_id` (bill_id)
- INDEX `ix_online_payment_submissions_flat_id` (flat_id)
- INDEX `ix_online_payment_submissions_payment_date` (payment_date)
- INDEX `ix_online_payment_submissions_payment_mode` (payment_mode)
- INDEX `ix_online_payment_submissions_receipt_number` (receipt_number)
- INDEX `ix_online_payment_submissions_recorded_by` (recorded_by)
- INDEX `ix_online_payment_submissions_reviewed_by` (reviewed_by)
- INDEX `ix_online_payment_submissions_society_id` (society_id)
- INDEX `ix_online_payment_submissions_status` (status)
- INDEX `ix_online_payment_submissions_transaction_ref` (transaction_ref)
- INDEX `ix_online_payment_submissions_wing_id` (wing_id)

### `payment_allocations`  — 12 cols, PK(id)
- FKs: bill_id→maintenance_bills.id; flat_id→flats.id; society_id→societies.id; allocated_by→users.id; payment_id→online_payment_submissions.id
- INDEX `ix_payment_allocations_bill_id` (bill_id)
- INDEX `ix_payment_allocations_flat_id` (flat_id)
- INDEX `ix_payment_allocations_payment_id` (payment_id)
- INDEX `ix_payment_allocations_society_id` (society_id)

### `payment_claims`  — 22 cols, PK(id)
- FKs: reviewed_by→users.id; bill_id→maintenance_bills.id; society_id→societies.id; submission_id→online_payment_submissions.id; claimed_by→users.id; flat_id→flats.id
- INDEX `ix_payment_claims_bill_id` (bill_id)
- INDEX `ix_payment_claims_claimed_by` (claimed_by)
- INDEX `ix_payment_claims_flat_id` (flat_id)
- INDEX `ix_payment_claims_society_id` (society_id)
- INDEX `ix_payment_claims_status` (status)
- INDEX `ix_payment_claims_transaction_ref` (transaction_ref)

### `payment_receipts`  — 19 cols, PK(id)
- FKs: received_by→users.id; society_id→societies.id; bill_id→maintenance_bills.id; flat_id→flats.id
- UNIQUE constraint `uq_receipt_society_number`: (society_id, receipt_number)
- INDEX `ix_payment_receipts_bill_id` (bill_id)
- INDEX `ix_payment_receipts_flat_id` (flat_id)
- INDEX `ix_payment_receipts_payment_date` (payment_date)
- INDEX `ix_payment_receipts_payment_mode` (payment_mode)
- INDEX `ix_payment_receipts_receipt_number` (receipt_number)
- INDEX `ix_payment_receipts_received_by` (received_by)
- INDEX `ix_payment_receipts_society_id` (society_id)
- INDEX `ix_payment_receipts_transaction_ref` (transaction_ref)

### `penalty_rules`  — 11 cols, PK(id)
- FKs: society_id→societies.id
- INDEX `ix_penalty_rules_society_id` (society_id)


## Module: certificates  (1 tables)

### `certificate_requests`  — 17 cols, PK(id)
- FKs: requested_by→users.id; decided_by→users.id; flat_id→flats.id; society_id→societies.id
- UNIQUE constraint `uq_certificate_no`: (society_id, certificate_no)
- INDEX `ix_certificate_requests_flat_id` (flat_id)
- INDEX `ix_certificate_requests_requested_by` (requested_by)
- INDEX `ix_certificate_requests_society_id` (society_id)
- INDEX `ix_certificate_requests_status` (status)


## Module: checklist  (3 tables)

### `manager_checklist_items`  — 23 cols, PK(id)
- FKs: society_id→societies.id; created_by→users.id
- UNIQUE constraint `uq_checklist_society_code`: (society_id, code)
- INDEX `ix_manager_checklist_items_society_id` (society_id)

### `manager_checklist_logs`  — 13 cols, PK(id)
- FKs: item_id→manager_checklist_items.id; society_id→societies.id; done_by→users.id
- UNIQUE constraint `uq_checklist_log_item_date`: (item_id, for_date)
- INDEX `ix_manager_checklist_logs_for_date` (for_date)
- INDEX `ix_manager_checklist_logs_item_id` (item_id)
- INDEX `ix_manager_checklist_logs_society_id` (society_id)

### `manager_checklist_signoffs`  — 11 cols, PK(id)
- FKs: signed_by→users.id; society_id→societies.id
- UNIQUE constraint `uq_checklist_signoff_day`: (society_id, for_date)
- INDEX `ix_manager_checklist_signoffs_for_date` (for_date)
- INDEX `ix_manager_checklist_signoffs_society_id` (society_id)


## Module: complaint  (4 tables)

### `complaint_attachments`  — 10 cols, PK(id)
- FKs: complaint_id→complaints.id; uploaded_by→users.id
- INDEX `ix_complaint_attachments_complaint_id` (complaint_id)
- INDEX `ix_complaint_attachments_uploaded_by` (uploaded_by)

### `complaint_comments`  — 8 cols, PK(id)
- FKs: author_id→users.id; complaint_id→complaints.id
- INDEX `ix_complaint_comments_author_id` (author_id)
- INDEX `ix_complaint_comments_complaint_id` (complaint_id)

### `complaint_status_history`  — 9 cols, PK(id)
- FKs: complaint_id→complaints.id; changed_by→users.id
- INDEX `ix_complaint_status_history_changed_by` (changed_by)
- INDEX `ix_complaint_status_history_complaint_id` (complaint_id)

### `complaints`  — 23 cols, PK(id)
- FKs: assigned_by→users.id; raised_by→users.id; society_id→societies.id; assigned_to→users.id; flat_id→flats.id
- UNIQUE constraint `uq_complaint_society_number`: (society_id, complaint_number)
- INDEX `ix_complaints_assigned_by` (assigned_by)
- INDEX `ix_complaints_assigned_department` (assigned_department)
- INDEX `ix_complaints_assigned_to` (assigned_to)
- INDEX `ix_complaints_category` (category)
- INDEX `ix_complaints_complaint_number` (complaint_number)
- INDEX `ix_complaints_flat_id` (flat_id)
- INDEX `ix_complaints_priority` (priority)
- INDEX `ix_complaints_raised_by` (raised_by)
- INDEX `ix_complaints_society_id` (society_id)
- INDEX `ix_complaints_status` (status)


## Module: core  (23 tables)

### `agreement_tracker`  — 22 cols, PK(id)
- FKs: created_by→users.id; resident_id→residents.id; flat_id→flats.id; renewal_of_id→agreement_tracker.id; tenant_id→tenants.id; society_id→societies.id
- INDEX `ix_agreement_tracker_agreement_number` (agreement_number)
- INDEX `ix_agreement_tracker_created_by` (created_by)
- INDEX `ix_agreement_tracker_end_date` (end_date)
- INDEX `ix_agreement_tracker_flat_id` (flat_id)
- INDEX `ix_agreement_tracker_renewal_of_id` (renewal_of_id)
- INDEX `ix_agreement_tracker_resident_id` (resident_id)
- INDEX `ix_agreement_tracker_society_id` (society_id)
- INDEX `ix_agreement_tracker_start_date` (start_date)
- INDEX `ix_agreement_tracker_status` (status)
- INDEX `ix_agreement_tracker_tenant_id` (tenant_id)

### `audit_logs`  — 15 cols, PK(id)
- FKs: user_id→users.id
- INDEX `ix_audit_logs_action` (action)
- INDEX `ix_audit_logs_entity_id` (entity_id)
- INDEX `ix_audit_logs_module` (module)
- INDEX `ix_audit_logs_user_id` (user_id)

### `device_tokens`  — 8 cols, PK(id)
- FKs: user_id→users.id
- UNIQUE INDEX `ix_device_tokens_token` (token)
- INDEX `ix_device_tokens_user_id` (user_id)

### `flats`  — 19 cols, PK(id)
- FKs: wing_id→wings.id
- INDEX `ix_flats_wing_id` (wing_id)

### `floors`  — 8 cols, PK(id)
- FKs: wing_id→wings.id; society_id→societies.id
- INDEX `ix_floors_society_id` (society_id)
- INDEX `ix_floors_wing_id` (wing_id)
- UNIQUE INDEX `uq_floor_wing_number` (wing_id, floor_number) WHERE is_active = true

### `forms`  — 7 cols, PK(id)
- UNIQUE INDEX `ix_forms_code` (code)

### `notifications`  — 15 cols, PK(id)
- FKs: user_id→users.id
- INDEX `ix_notifications_status` (status)
- INDEX `ix_notifications_user_id` (user_id)

### `occupancy_logs`  — 13 cols, PK(id)
- FKs: logged_by→users.id; resident_id→residents.id; flat_id→flats.id; society_id→societies.id; tenant_id→tenants.id; wing_id→wings.id
- INDEX `ix_occupancy_logs_event_date` (event_date)
- INDEX `ix_occupancy_logs_event_type` (event_type)
- INDEX `ix_occupancy_logs_flat_id` (flat_id)
- INDEX `ix_occupancy_logs_logged_by` (logged_by)
- INDEX `ix_occupancy_logs_resident_id` (resident_id)
- INDEX `ix_occupancy_logs_society_id` (society_id)
- INDEX `ix_occupancy_logs_tenant_id` (tenant_id)
- INDEX `ix_occupancy_logs_wing_id` (wing_id)

### `password_reset_requests`  — 10 cols, PK(id)
- FKs: society_id→societies.id; user_id→users.id; resolved_by→users.id
- INDEX `ix_password_reset_requests_resolved_by` (resolved_by)
- INDEX `ix_password_reset_requests_society_id` (society_id)
- INDEX `ix_password_reset_requests_status` (status)
- INDEX `ix_password_reset_requests_user_id` (user_id)

### `permissions`  — 7 cols, PK(id)
- UNIQUE INDEX `ix_permissions_code` (code)

### `resident_edit_requests`  — 12 cols, PK(id)
- FKs: reviewed_by→users.id; society_id→societies.id; requested_by→users.id; resident_id→residents.id
- INDEX `ix_resident_edit_requests_requested_by` (requested_by)
- INDEX `ix_resident_edit_requests_resident_id` (resident_id)
- INDEX `ix_resident_edit_requests_reviewed_by` (reviewed_by)
- INDEX `ix_resident_edit_requests_society_id` (society_id)
- INDEX `ix_resident_edit_requests_status` (status)

### `residents`  — 23 cols, PK(id)
- FKs: flat_id→flats.id; user_id→users.id
- CHECK `ck_resident_primary_type`: is_primary IS NOT TRUE OR resident_type IN ('owner', 'co_owner')
- INDEX `ix_residents_flat_id` (flat_id)
- INDEX `ix_residents_user_id` (user_id)
- UNIQUE INDEX `uq_resident_name_per_flat` (flat_id, lower, resident_type) WHERE is_active = true
- UNIQUE INDEX `uq_resident_primary_per_flat` (flat_id) WHERE is_primary = true AND is_active = true

### `role_forms`  — 6 cols, PK(id)
- FKs: role_id→roles.id; form_id→forms.id
- UNIQUE constraint `uq_role_form`: (role_id, form_id)
- INDEX `ix_role_forms_form_id` (form_id)
- INDEX `ix_role_forms_role_id` (role_id)

### `role_permissions`  — 6 cols, PK(id)
- FKs: permission_id→permissions.id; role_id→roles.id
- UNIQUE constraint `uq_role_permission`: (role_id, permission_id)
- INDEX `ix_role_permissions_permission_id` (permission_id)
- INDEX `ix_role_permissions_role_id` (role_id)

### `roles`  — 6 cols, PK(id)
- UNIQUE INDEX `ix_roles_name` (name)

### `societies`  — 41 cols, PK(id)
- UNIQUE INDEX `ix_societies_name` (name)
- UNIQUE INDEX `ix_societies_society_code` (society_code)

### `society_services`  — 8 cols, PK(id)
- FKs: changed_by→users.id; society_id→societies.id
- UNIQUE constraint `uq_society_services_key`: (society_id, service_key)
- INDEX `ix_society_services_society_id` (society_id)

### `tenants`  — 29 cols, PK(id)
- FKs: user_id→users.id; flat_id→flats.id
- INDEX `ix_tenants_flat_id` (flat_id)
- INDEX `ix_tenants_user_id` (user_id)

### `user_roles`  — 6 cols, PK(id)
- FKs: role_id→roles.id; user_id→users.id
- INDEX `ix_user_roles_role_id` (role_id)
- INDEX `ix_user_roles_user_id` (user_id)

### `user_sessions`  — 10 cols, PK(id)
- FKs: user_id→users.id
- INDEX `ix_user_sessions_revoked_at` (revoked_at)
- INDEX `ix_user_sessions_user_id` (user_id)

### `users`  — 16 cols, PK(id)
- FKs: society_id→societies.id
- INDEX `ix_users_email` (email)
- INDEX `ix_users_phone` (phone)
- INDEX `ix_users_society_id` (society_id)
- UNIQUE INDEX `uq_users_platform_email` (email) WHERE society_id IS NULL AND is_active AND status = 'active'
- UNIQUE INDEX `uq_users_platform_phone` (phone) WHERE society_id IS NULL AND phone IS NOT NULL AND is_active AND status = 'active'
- UNIQUE INDEX `uq_users_society_email` (society_id, email) WHERE society_id IS NOT NULL AND is_active AND status = 'active'
- UNIQUE INDEX `uq_users_society_phone` (society_id, phone) WHERE society_id IS NOT NULL AND phone IS NOT NULL AND is_active AND status = 'active'

### `vehicles`  — 21 cols, PK(id)
- FKs: society_id→societies.id; tenant_id→tenants.id; flat_id→flats.id; registered_by→users.id; resident_id→residents.id
- CHECK `ck_vehicle_resident_tenant_xor`: resident_id IS NULL OR tenant_id IS NULL
- INDEX `ix_vehicles_flat_id` (flat_id)
- INDEX `ix_vehicles_parking_slot` (parking_slot)
- INDEX `ix_vehicles_registered_by` (registered_by)
- INDEX `ix_vehicles_resident_id` (resident_id)
- UNIQUE INDEX `ix_vehicles_rfid_tag` (rfid_tag)
- INDEX `ix_vehicles_society_id` (society_id)
- INDEX `ix_vehicles_tenant_id` (tenant_id)
- INDEX `ix_vehicles_vehicle_number` (vehicle_number)
- INDEX `ix_vehicles_vehicle_type` (vehicle_type)
- UNIQUE INDEX `uq_vehicle_society_normalized_number` (society_id, upper) WHERE is_active = true

### `wings`  — 10 cols, PK(id)
- FKs: society_id→societies.id
- INDEX `ix_wings_society_id` (society_id)
- UNIQUE INDEX `uq_wing_society_code` (society_id, code) WHERE is_active = true
- UNIQUE INDEX `uq_wing_society_name` (society_id, name) WHERE is_active = true


## Module: gate  (4 tables)

### `domestic_help`  — 16 cols, PK(id)
- FKs: registered_by→users.id; society_id→societies.id; approved_by→users.id
- UNIQUE constraint `uq_domestic_help_pass`: (society_id, pass_no)
- INDEX `ix_domestic_help_mobile` (mobile)
- INDEX `ix_domestic_help_society_id` (society_id)
- INDEX `ix_domestic_help_status` (status)

### `domestic_help_entries`  — 9 cols, PK(id)
- FKs: logged_by→users.id; society_id→societies.id; help_id→domestic_help.id
- INDEX `ix_domestic_help_entries_help_id` (help_id)
- INDEX `ix_domestic_help_entries_in_at` (in_at)
- INDEX `ix_domestic_help_entries_society_id` (society_id)

### `domestic_help_flats`  — 6 cols, PK(id)
- FKs: help_id→domestic_help.id; flat_id→flats.id
- UNIQUE constraint `uq_domestic_help_flat`: (help_id, flat_id)
- INDEX `ix_domestic_help_flats_flat_id` (flat_id)
- INDEX `ix_domestic_help_flats_help_id` (help_id)

### `gate_parcels`  — 16 cols, PK(id)
- FKs: logged_by→users.id; closed_by→users.id; flat_id→flats.id; society_id→societies.id
- INDEX `ix_gate_parcels_flat_id` (flat_id)
- INDEX `ix_gate_parcels_society_id` (society_id)
- INDEX `ix_gate_parcels_status` (status)


## Module: governance  (7 tables)

### `meeting_attendees`  — 9 cols, PK(id)
- FKs: meeting_id→meetings.id
- INDEX `ix_meeting_attendees_meeting_id` (meeting_id)

### `meeting_resolutions`  — 10 cols, PK(id)
- FKs: meeting_id→meetings.id
- INDEX `ix_meeting_resolutions_meeting_id` (meeting_id)

### `meetings`  — 16 cols, PK(id)
- FKs: created_by→users.id; society_id→societies.id
- INDEX `ix_meetings_meeting_date` (meeting_date)
- INDEX `ix_meetings_society_id` (society_id)
- INDEX `ix_meetings_status` (status)

### `poll_options`  — 7 cols, PK(id)
- FKs: poll_id→polls.id
- INDEX `ix_poll_options_poll_id` (poll_id)

### `poll_votes`  — 9 cols, PK(id)
- FKs: flat_id→flats.id; user_id→users.id; option_id→poll_options.id; poll_id→polls.id
- UNIQUE constraint `uq_poll_vote_flat`: (poll_id, flat_id)
- INDEX `ix_poll_votes_poll_id` (poll_id)

### `polls`  — 11 cols, PK(id)
- FKs: created_by→users.id; society_id→societies.id
- INDEX `ix_polls_society_id` (society_id)

### `society_documents`  — 14 cols, PK(id)
- FKs: uploaded_by→users.id; society_id→societies.id
- INDEX `ix_society_documents_category` (category)
- INDEX `ix_society_documents_society_id` (society_id)


## Module: inventory  (10 tables)

### `asset_amc`  — 16 cols, PK(id)
- FKs: asset_id→assets.id; society_id→societies.id
- INDEX `ix_asset_amc_asset_id` (asset_id)
- INDEX `ix_asset_amc_end_date` (end_date)
- INDEX `ix_asset_amc_society_id` (society_id)

### `asset_maintenance`  — 17 cols, PK(id)
- FKs: society_id→societies.id; asset_id→assets.id; performed_by→users.id
- INDEX `ix_asset_maintenance_asset_id` (asset_id)
- INDEX `ix_asset_maintenance_maintenance_type` (maintenance_type)
- INDEX `ix_asset_maintenance_performed_by` (performed_by)
- INDEX `ix_asset_maintenance_society_id` (society_id)
- INDEX `ix_asset_maintenance_status` (status)

### `asset_usage_logs`  — 10 cols, PK(id)
- FKs: asset_id→assets.id; logged_by→users.id; society_id→societies.id
- INDEX `ix_asset_usage_logs_asset_id` (asset_id)
- INDEX `ix_asset_usage_logs_logged_by` (logged_by)
- INDEX `ix_asset_usage_logs_society_id` (society_id)

### `assets`  — 27 cols, PK(id)
- FKs: assigned_to_user→users.id; society_id→societies.id
- UNIQUE constraint `uq_asset_society_code`: (society_id, asset_code)
- INDEX `ix_assets_asset_category` (asset_category)
- INDEX `ix_assets_asset_code` (asset_code)
- INDEX `ix_assets_assigned_to_user` (assigned_to_user)
- INDEX `ix_assets_next_service_due` (next_service_due)
- INDEX `ix_assets_serial_number` (serial_number)
- INDEX `ix_assets_society_id` (society_id)
- INDEX `ix_assets_status` (status)

### `inventory_categories`  — 7 cols, PK(id)
- FKs: society_id→societies.id
- INDEX `ix_inventory_categories_society_id` (society_id)

### `inventory_issues`  — 18 cols, PK(id)
- FKs: task_id→staff_tasks.id; issued_by→users.id; item_id→inventory_items.id; society_id→societies.id; complaint_id→complaints.id; issued_to_user→users.id
- INDEX `ix_inventory_issues_complaint_id` (complaint_id)
- INDEX `ix_inventory_issues_issued_by` (issued_by)
- INDEX `ix_inventory_issues_issued_to_user` (issued_to_user)
- INDEX `ix_inventory_issues_item_id` (item_id)
- INDEX `ix_inventory_issues_society_id` (society_id)
- INDEX `ix_inventory_issues_status` (status)
- INDEX `ix_inventory_issues_task_id` (task_id)

### `inventory_items`  — 18 cols, PK(id)
- FKs: society_id→societies.id; category_id→inventory_categories.id
- UNIQUE constraint `uq_item_society_code`: (society_id, item_code)
- INDEX `ix_inventory_items_category` (category)
- INDEX `ix_inventory_items_category_id` (category_id)
- INDEX `ix_inventory_items_item_code` (item_code)
- INDEX `ix_inventory_items_society_id` (society_id)

### `inventory_returns`  — 11 cols, PK(id)
- FKs: returned_by→users.id; society_id→societies.id; issue_id→inventory_issues.id; received_by→users.id
- INDEX `ix_inventory_returns_issue_id` (issue_id)
- INDEX `ix_inventory_returns_received_by` (received_by)
- INDEX `ix_inventory_returns_returned_by` (returned_by)
- INDEX `ix_inventory_returns_society_id` (society_id)

### `inventory_stock`  — 8 cols, PK(id)
- FKs: last_updated_by→users.id; society_id→societies.id; item_id→inventory_items.id
- UNIQUE INDEX `ix_inventory_stock_item_id` (item_id)
- INDEX `ix_inventory_stock_last_updated_by` (last_updated_by)
- INDEX `ix_inventory_stock_society_id` (society_id)

### `inventory_transactions`  — 15 cols, PK(id)
- FKs: performed_by→users.id; item_id→inventory_items.id; society_id→societies.id
- INDEX `ix_inventory_transactions_item_id` (item_id)
- INDEX `ix_inventory_transactions_performed_by` (performed_by)
- INDEX `ix_inventory_transactions_society_id` (society_id)
- INDEX `ix_inventory_transactions_transaction_type` (transaction_type)


## Module: notice  (5 tables)

### `announcements`  — 15 cols, PK(id)
- FKs: created_by→users.id; society_id→societies.id
- INDEX `ix_announcements_category` (category)
- INDEX `ix_announcements_created_by` (created_by)
- INDEX `ix_announcements_is_published` (is_published)
- INDEX `ix_announcements_society_id` (society_id)

### `communication_logs`  — 11 cols, PK(id)
- FKs: society_id→societies.id; user_id→users.id; notice_id→notices.id
- INDEX `ix_communication_logs_notice_id` (notice_id)
- INDEX `ix_communication_logs_society_id` (society_id)
- INDEX `ix_communication_logs_user_id` (user_id)

### `emergency_alerts`  — 22 cols, PK(id)
- FKs: resolved_by→users.id; triggered_by→users.id; society_id→societies.id
- INDEX `ix_emergency_alerts_alert_type` (alert_type)
- INDEX `ix_emergency_alerts_resolved_by` (resolved_by)
- INDEX `ix_emergency_alerts_society_id` (society_id)
- INDEX `ix_emergency_alerts_status` (status)
- INDEX `ix_emergency_alerts_triggered_by` (triggered_by)

### `notice_acknowledgements`  — 9 cols, PK(id)
- FKs: flat_id→flats.id; user_id→users.id; notice_id→notices.id
- INDEX `ix_notice_acknowledgements_flat_id` (flat_id)
- INDEX `ix_notice_acknowledgements_notice_id` (notice_id)
- INDEX `ix_notice_acknowledgements_user_id` (user_id)

### `notices`  — 21 cols, PK(id)
- FKs: created_by→users.id; society_id→societies.id
- INDEX `ix_notices_audience_type` (audience_type)
- INDEX `ix_notices_category` (category)
- INDEX `ix_notices_created_by` (created_by)
- INDEX `ix_notices_priority` (priority)
- INDEX `ix_notices_society_id` (society_id)
- INDEX `ix_notices_status` (status)


## Module: parking  (7 tables)

### `parking_access_logs`  — 16 cols, PK(id)
- FKs: slot_id→parking_slots.id; society_id→societies.id; gate_id→gates.id; vehicle_id→vehicles.id; user_id→users.id
- INDEX `ix_parking_access_logs_access_time` (access_time)
- INDEX `ix_parking_access_logs_access_type` (access_type)
- INDEX `ix_parking_access_logs_gate_id` (gate_id)
- INDEX `ix_parking_access_logs_is_authorized` (is_authorized)
- INDEX `ix_parking_access_logs_slot_id` (slot_id)
- INDEX `ix_parking_access_logs_society_id` (society_id)
- INDEX `ix_parking_access_logs_user_id` (user_id)
- INDEX `ix_parking_access_logs_vehicle_id` (vehicle_id)
- INDEX `ix_parking_access_logs_vehicle_number` (vehicle_number)

### `parking_allocations`  — 18 cols, PK(id)
- FKs: released_by→users.id; allocated_to_user→users.id; flat_id→flats.id; allocated_by→users.id; vehicle_id→vehicles.id; slot_id→parking_slots.id; society_id→societies.id
- INDEX `ix_parking_allocations_allocated_by` (allocated_by)
- INDEX `ix_parking_allocations_allocated_to_user` (allocated_to_user)
- INDEX `ix_parking_allocations_allocation_type` (allocation_type)
- INDEX `ix_parking_allocations_flat_id` (flat_id)
- INDEX `ix_parking_allocations_released_by` (released_by)
- INDEX `ix_parking_allocations_slot_id` (slot_id)
- INDEX `ix_parking_allocations_society_id` (society_id)
- INDEX `ix_parking_allocations_status` (status)
- INDEX `ix_parking_allocations_vehicle_id` (vehicle_id)

### `parking_floors`  — 9 cols, PK(id)
- FKs: zone_id→parking_zones.id; society_id→societies.id
- INDEX `ix_parking_floors_society_id` (society_id)
- INDEX `ix_parking_floors_zone_id` (zone_id)

### `parking_slots`  — 18 cols, PK(id)
- FKs: society_id→societies.id; zone_id→parking_zones.id; floor_id→parking_floors.id
- INDEX `ix_parking_slots_floor_id` (floor_id)
- INDEX `ix_parking_slots_slot_number` (slot_number)
- INDEX `ix_parking_slots_slot_type` (slot_type)
- INDEX `ix_parking_slots_society_id` (society_id)
- INDEX `ix_parking_slots_status` (status)
- INDEX `ix_parking_slots_zone_id` (zone_id)

### `parking_violations`  — 16 cols, PK(id)
- FKs: resolved_by→users.id; vehicle_id→vehicles.id; reported_by→users.id; slot_id→parking_slots.id; society_id→societies.id
- INDEX `ix_parking_violations_is_resolved` (is_resolved)
- INDEX `ix_parking_violations_reported_by` (reported_by)
- INDEX `ix_parking_violations_resolved_by` (resolved_by)
- INDEX `ix_parking_violations_slot_id` (slot_id)
- INDEX `ix_parking_violations_society_id` (society_id)
- INDEX `ix_parking_violations_vehicle_id` (vehicle_id)
- INDEX `ix_parking_violations_vehicle_number` (vehicle_number)
- INDEX `ix_parking_violations_violation_type` (violation_type)

### `parking_zones`  — 10 cols, PK(id)
- FKs: society_id→societies.id
- INDEX `ix_parking_zones_society_id` (society_id)

### `visitor_parking`  — 18 cols, PK(id)
- FKs: assigned_by→users.id; slot_id→parking_slots.id; society_id→societies.id; host_flat_id→flats.id; visitor_id→visitors.id
- INDEX `ix_visitor_parking_assigned_by` (assigned_by)
- INDEX `ix_visitor_parking_host_flat_id` (host_flat_id)
- INDEX `ix_visitor_parking_slot_id` (slot_id)
- INDEX `ix_visitor_parking_society_id` (society_id)
- INDEX `ix_visitor_parking_status` (status)
- INDEX `ix_visitor_parking_vehicle_number` (vehicle_number)
- INDEX `ix_visitor_parking_visitor_id` (visitor_id)


## Module: shops  (1 tables)

### `shops`  — 21 cols, PK(id)
- FKs: created_by→users.id; society_id→societies.id
- INDEX `ix_shops_society_id` (society_id)
- UNIQUE INDEX `uq_shop_society_number` (society_id, shop_number) WHERE is_active = true


## Module: staff  (18 tables)

### `attendance_corrections`  — 19 cols, PK(id)
- FKs: requested_by→users.id; staff_id→staff.id; society_id→societies.id; approved_by→users.id; attendance_id→staff_attendance.id
- INDEX `ix_attendance_corrections_approved_by` (approved_by)
- INDEX `ix_attendance_corrections_attendance_id` (attendance_id)
- INDEX `ix_attendance_corrections_correction_date` (correction_date)
- INDEX `ix_attendance_corrections_requested_by` (requested_by)
- INDEX `ix_attendance_corrections_society_id` (society_id)
- INDEX `ix_attendance_corrections_staff_id` (staff_id)
- INDEX `ix_attendance_corrections_status` (status)

### `checklist_template_items`  — 9 cols, PK(id)
- FKs: template_id→checklist_templates.id
- INDEX `ix_checklist_template_items_template_id` (template_id)

### `checklist_templates`  — 9 cols, PK(id)
- FKs: society_id→societies.id; created_by→users.id
- INDEX `ix_checklist_templates_created_by` (created_by)
- INDEX `ix_checklist_templates_department` (department)
- INDEX `ix_checklist_templates_society_id` (society_id)

### `duty_assignments`  — 24 cols, PK(id)
- FKs: checklist_template_id→checklist_templates.id; assigned_by→users.id; staff_id→staff.id; completed_by→users.id; verified_by→users.id; shift_id→staff_shifts.id; society_id→societies.id
- INDEX `ix_duty_assignments_assigned_by` (assigned_by)
- INDEX `ix_duty_assignments_checklist_template_id` (checklist_template_id)
- INDEX `ix_duty_assignments_completed_by` (completed_by)
- INDEX `ix_duty_assignments_duty_date` (duty_date)
- INDEX `ix_duty_assignments_series_id` (series_id)
- INDEX `ix_duty_assignments_shift_id` (shift_id)
- INDEX `ix_duty_assignments_society_id` (society_id)
- INDEX `ix_duty_assignments_staff_id` (staff_id)
- INDEX `ix_duty_assignments_verified_by` (verified_by)

### `duty_checklist_items`  — 15 cols, PK(id)
- FKs: duty_id→duty_assignments.id; completed_by→users.id; template_item_id→checklist_template_items.id
- INDEX `ix_duty_checklist_items_completed_by` (completed_by)
- INDEX `ix_duty_checklist_items_duty_id` (duty_id)
- INDEX `ix_duty_checklist_items_template_item_id` (template_item_id)

### `handover_items`  — 14 cols, PK(id)
- FKs: handover_id→staff_handovers.id
- INDEX `ix_handover_items_handover_id` (handover_id)
- INDEX `ix_handover_items_item_type` (item_type)

### `monthly_attendance_summaries`  — 20 cols, PK(id)
- FKs: staff_id→staff.id; society_id→societies.id; finalized_by→users.id
- INDEX `ix_monthly_attendance_summaries_finalized_by` (finalized_by)
- INDEX `ix_monthly_attendance_summaries_month` (month)
- INDEX `ix_monthly_attendance_summaries_society_id` (society_id)
- INDEX `ix_monthly_attendance_summaries_staff_id` (staff_id)
- INDEX `ix_monthly_attendance_summaries_year` (year)

### `staff`  — 26 cols, PK(id)
- FKs: shift_id→staff_shifts.id; user_id→users.id; reporting_manager_id→users.id; designation_id→staff_designations.id; society_id→societies.id
- INDEX `ix_staff_department` (department)
- INDEX `ix_staff_designation_id` (designation_id)
- UNIQUE INDEX `ix_staff_employee_code` (employee_code)
- INDEX `ix_staff_mobile` (mobile)
- INDEX `ix_staff_reporting_manager_id` (reporting_manager_id)
- INDEX `ix_staff_shift_id` (shift_id)
- INDEX `ix_staff_society_id` (society_id)
- INDEX `ix_staff_status` (status)
- INDEX `ix_staff_user_id` (user_id)

### `staff_attendance`  — 23 cols, PK(id)
- FKs: marked_by→users.id; approved_by→users.id; society_id→societies.id; checkout_approved_by→users.id; staff_id→staff.id
- INDEX `ix_staff_attendance_approved_by` (approved_by)
- INDEX `ix_staff_attendance_attendance_date` (attendance_date)
- INDEX `ix_staff_attendance_checkout_approved_by` (checkout_approved_by)
- INDEX `ix_staff_attendance_is_approved` (is_approved)
- INDEX `ix_staff_attendance_marked_by` (marked_by)
- INDEX `ix_staff_attendance_society_id` (society_id)
- INDEX `ix_staff_attendance_staff_id` (staff_id)
- INDEX `ix_staff_attendance_status` (status)

### `staff_designations`  — 8 cols, PK(id)
- FKs: society_id→societies.id
- INDEX `ix_staff_designations_department` (department)
- INDEX `ix_staff_designations_society_id` (society_id)

### `staff_handovers`  — 20 cols, PK(id)
- FKs: outgoing_staff_id→staff.id; verified_by→users.id; incoming_staff_id→staff.id; duty_assignment_id→duty_assignments.id; society_id→societies.id
- INDEX `ix_staff_handovers_duty_assignment_id` (duty_assignment_id)
- INDEX `ix_staff_handovers_incoming_staff_id` (incoming_staff_id)
- INDEX `ix_staff_handovers_outgoing_staff_id` (outgoing_staff_id)
- INDEX `ix_staff_handovers_society_id` (society_id)
- INDEX `ix_staff_handovers_status` (status)
- INDEX `ix_staff_handovers_verified_by` (verified_by)

### `staff_leave_balances`  — 13 cols, PK(id)
- FKs: staff_id→staff.id; society_id→societies.id
- INDEX `ix_staff_leave_balances_society_id` (society_id)
- INDEX `ix_staff_leave_balances_staff_id` (staff_id)
- INDEX `ix_staff_leave_balances_year` (year)

### `staff_leaves`  — 15 cols, PK(id)
- FKs: society_id→societies.id; approved_by→users.id; staff_id→staff.id
- INDEX `ix_staff_leaves_approved_by` (approved_by)
- INDEX `ix_staff_leaves_leave_type` (leave_type)
- INDEX `ix_staff_leaves_society_id` (society_id)
- INDEX `ix_staff_leaves_staff_id` (staff_id)
- INDEX `ix_staff_leaves_status` (status)

### `staff_rosters`  — 20 cols, PK(id)
- FKs: shift_id→staff_shifts.id; created_by→users.id; staff_id→staff.id; society_id→societies.id
- INDEX `ix_staff_rosters_created_by` (created_by)
- INDEX `ix_staff_rosters_shift_id` (shift_id)
- INDEX `ix_staff_rosters_society_id` (society_id)
- INDEX `ix_staff_rosters_staff_id` (staff_id)
- INDEX `ix_staff_rosters_week_start` (week_start)

### `staff_salary_structures`  — 22 cols, PK(id)
- FKs: created_by→users.id; staff_id→staff.id; society_id→societies.id
- INDEX `ix_staff_salary_structures_created_by` (created_by)
- INDEX `ix_staff_salary_structures_society_id` (society_id)
- INDEX `ix_staff_salary_structures_staff_id` (staff_id)

### `staff_shifts`  — 10 cols, PK(id)
- FKs: society_id→societies.id
- INDEX `ix_staff_shifts_society_id` (society_id)

### `staff_tasks`  — 21 cols, PK(id)
- FKs: verified_by→users.id; staff_id→staff.id; complaint_id→complaints.id; assigned_by→users.id; society_id→societies.id; visitor_id→visitors.id
- INDEX `ix_staff_tasks_assigned_by` (assigned_by)
- INDEX `ix_staff_tasks_complaint_id` (complaint_id)
- INDEX `ix_staff_tasks_society_id` (society_id)
- INDEX `ix_staff_tasks_staff_id` (staff_id)
- INDEX `ix_staff_tasks_status` (status)
- INDEX `ix_staff_tasks_verified_by` (verified_by)
- INDEX `ix_staff_tasks_visitor_id` (visitor_id)

### `staff_work_logs`  — 10 cols, PK(id)
- FKs: task_id→staff_tasks.id; staff_id→staff.id; society_id→societies.id
- INDEX `ix_staff_work_logs_society_id` (society_id)
- INDEX `ix_staff_work_logs_staff_id` (staff_id)
- INDEX `ix_staff_work_logs_task_id` (task_id)


## Module: vendor  (11 tables)

### `amc_contracts`  — 39 cols, PK(id)
- FKs: vendor_id→vendors.id; renewed_from_id→amc_contracts.id; asset_id→assets.id; society_id→societies.id; sanctioned_by→users.id; created_by→users.id
- UNIQUE constraint `uq_contract_society_number`: (society_id, contract_number)
- INDEX `ix_amc_contracts_asset_id` (asset_id)
- INDEX `ix_amc_contracts_category` (category)
- INDEX `ix_amc_contracts_contract_number` (contract_number)
- INDEX `ix_amc_contracts_created_by` (created_by)
- INDEX `ix_amc_contracts_end_date` (end_date)
- INDEX `ix_amc_contracts_renewed_from_id` (renewed_from_id)
- INDEX `ix_amc_contracts_society_id` (society_id)
- INDEX `ix_amc_contracts_start_date` (start_date)
- INDEX `ix_amc_contracts_status` (status)
- INDEX `ix_amc_contracts_vendor_id` (vendor_id)

### `amc_service_schedules`  — 11 cols, PK(id)
- FKs: visit_log_id→service_visit_logs.id; society_id→societies.id; contract_id→amc_contracts.id
- INDEX `ix_amc_service_schedules_contract_id` (contract_id)
- INDEX `ix_amc_service_schedules_scheduled_date` (scheduled_date)
- INDEX `ix_amc_service_schedules_society_id` (society_id)
- INDEX `ix_amc_service_schedules_status` (status)
- INDEX `ix_amc_service_schedules_visit_log_id` (visit_log_id)

### `procurement_settings`  — 10 cols, PK(id)
- FKs: society_id→societies.id
- UNIQUE INDEX `ix_procurement_settings_society_id` (society_id)

### `service_requests`  — 28 cols, PK(id)
- FKs: complaint_id→complaints.id; assigned_by→users.id; vendor_id→vendors.id; society_id→societies.id; asset_id→assets.id; verified_by→users.id; raised_by→users.id
- UNIQUE constraint `uq_service_request_society_number`: (society_id, request_number)
- INDEX `ix_service_requests_asset_id` (asset_id)
- INDEX `ix_service_requests_assigned_by` (assigned_by)
- INDEX `ix_service_requests_category` (category)
- INDEX `ix_service_requests_complaint_id` (complaint_id)
- INDEX `ix_service_requests_is_overdue` (is_overdue)
- INDEX `ix_service_requests_raised_by` (raised_by)
- INDEX `ix_service_requests_request_number` (request_number)
- INDEX `ix_service_requests_society_id` (society_id)
- INDEX `ix_service_requests_status` (status)
- INDEX `ix_service_requests_vendor_id` (vendor_id)
- INDEX `ix_service_requests_verified_by` (verified_by)

### `service_visit_logs`  — 17 cols, PK(id)
- FKs: logged_by→users.id; society_id→societies.id; vendor_id→vendors.id; contract_id→amc_contracts.id; request_id→service_requests.id
- INDEX `ix_service_visit_logs_contract_id` (contract_id)
- INDEX `ix_service_visit_logs_logged_by` (logged_by)
- INDEX `ix_service_visit_logs_request_id` (request_id)
- INDEX `ix_service_visit_logs_society_id` (society_id)
- INDEX `ix_service_visit_logs_vendor_id` (vendor_id)
- INDEX `ix_service_visit_logs_visit_date` (visit_date)

### `vendor_invoices`  — 39 cols, PK(id)
- FKs: society_id→societies.id; expense_account_id→accounts.id; work_order_id→work_orders.id; contract_id→amc_contracts.id; approved_by→users.id; request_id→service_requests.id; vendor_id→vendors.id
- INDEX `ix_vendor_invoices_approved_by` (approved_by)
- INDEX `ix_vendor_invoices_contract_id` (contract_id)
- INDEX `ix_vendor_invoices_invoice_date` (invoice_date)
- INDEX `ix_vendor_invoices_invoice_number` (invoice_number)
- INDEX `ix_vendor_invoices_is_paid` (is_paid)
- INDEX `ix_vendor_invoices_request_id` (request_id)
- INDEX `ix_vendor_invoices_society_id` (society_id)
- INDEX `ix_vendor_invoices_vendor_id` (vendor_id)
- INDEX `ix_vendor_invoices_work_order_id` (work_order_id)

### `vendor_payment_transactions`  — 26 cols, PK(id)
- FKs: invoice_id→vendor_invoices.id; society_id→societies.id; bank_account_id→accounts.id; vendor_id→vendors.id; created_by→users.id
- UNIQUE constraint `uq_vendor_payment_society_number`: (society_id, payment_number)
- INDEX `ix_vendor_payment_transactions_invoice_id` (invoice_id)
- INDEX `ix_vendor_payment_transactions_is_legacy` (is_legacy)
- INDEX `ix_vendor_payment_transactions_is_reversed` (is_reversed)
- INDEX `ix_vendor_payment_transactions_payment_date` (payment_date)
- INDEX `ix_vendor_payment_transactions_payment_mode` (payment_mode)
- INDEX `ix_vendor_payment_transactions_payment_number` (payment_number)
- INDEX `ix_vendor_payment_transactions_society_id` (society_id)
- INDEX `ix_vendor_payment_transactions_transaction_ref` (transaction_ref)
- INDEX `ix_vendor_payment_transactions_vendor_id` (vendor_id)

### `vendor_quotations`  — 18 cols, PK(id)
- FKs: vendor_id→vendors.id; work_order_id→work_orders.id; society_id→societies.id; received_by→users.id; contract_id→amc_contracts.id
- INDEX `ix_vendor_quotations_contract_id` (contract_id)
- INDEX `ix_vendor_quotations_society_id` (society_id)
- INDEX `ix_vendor_quotations_vendor_id` (vendor_id)
- INDEX `ix_vendor_quotations_work_order_id` (work_order_id)

### `vendor_services`  — 10 cols, PK(id)
- FKs: vendor_id→vendors.id
- INDEX `ix_vendor_services_vendor_id` (vendor_id)

### `vendors`  — 34 cols, PK(id)
- FKs: society_id→societies.id; registered_by→users.id
- UNIQUE constraint `uq_vendor_society_code`: (society_id, vendor_code)
- INDEX `ix_vendors_category` (category)
- INDEX `ix_vendors_company_name` (company_name)
- INDEX `ix_vendors_gst_number` (gst_number)
- INDEX `ix_vendors_mobile` (mobile)
- INDEX `ix_vendors_registered_by` (registered_by)
- INDEX `ix_vendors_society_id` (society_id)
- INDEX `ix_vendors_status` (status)
- INDEX `ix_vendors_vendor_code` (vendor_code)

### `work_orders`  — 45 cols, PK(id)
- FKs: sanctioned_by→users.id; society_id→societies.id; completed_by→users.id; expense_account_id→accounts.id; complaint_id→complaints.id; vendor_id→vendors.id; cancelled_by→users.id; created_by→users.id; asset_id→assets.id; service_request_id→service_requests.id
- UNIQUE constraint `uq_work_order_society_number`: (society_id, wo_number)
- INDEX `ix_work_orders_asset_id` (asset_id)
- INDEX `ix_work_orders_category` (category)
- INDEX `ix_work_orders_complaint_id` (complaint_id)
- INDEX `ix_work_orders_service_request_id` (service_request_id)
- INDEX `ix_work_orders_society_id` (society_id)
- INDEX `ix_work_orders_status` (status)
- INDEX `ix_work_orders_vendor_id` (vendor_id)
- INDEX `ix_work_orders_wo_number` (wo_number)


## Module: visitor  (4 tables)

### `gates`  — 8 cols, PK(id)
- FKs: society_id→societies.id
- INDEX `ix_gates_society_id` (society_id)

### `visitor_logs`  — 9 cols, PK(id)
- FKs: performed_by→users.id; gate_id→gates.id; visitor_id→visitors.id
- INDEX `ix_visitor_logs_gate_id` (gate_id)
- INDEX `ix_visitor_logs_performed_by` (performed_by)
- INDEX `ix_visitor_logs_visitor_id` (visitor_id)

### `visitor_vehicles`  — 9 cols, PK(id)
- FKs: visitor_id→visitors.id
- INDEX `ix_visitor_vehicles_vehicle_number` (vehicle_number)
- INDEX `ix_visitor_vehicles_visitor_id` (visitor_id)

### `visitors`  — 24 cols, PK(id)
- FKs: approved_by→users.id; resident_id→users.id; society_id→societies.id; logged_by→users.id; gate_id→gates.id; flat_id→flats.id
- INDEX `ix_visitors_approved_by` (approved_by)
- INDEX `ix_visitors_flat_id` (flat_id)
- INDEX `ix_visitors_gate_id` (gate_id)
- INDEX `ix_visitors_logged_by` (logged_by)
- INDEX `ix_visitors_mobile` (mobile)
- INDEX `ix_visitors_pass_code` (pass_code)
- UNIQUE INDEX `ix_visitors_qr_token` (qr_token)
- INDEX `ix_visitors_resident_id` (resident_id)
- INDEX `ix_visitors_society_id` (society_id)
- INDEX `ix_visitors_status` (status)
- INDEX `ix_visitors_visitor_type` (visitor_type)
