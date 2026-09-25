import 'package:flutter/material.dart';
import 'package:ar_society_app/core/router/app_router.dart';

class AppMenuItem {
  final String formCode;
  final String label;
  final IconData icon;
  final String? route;

  const AppMenuItem(this.formCode, this.label, this.icon, this.route);
}

class AppMenuCategory {
  final String label;
  final IconData icon;
  final List<AppMenuItem> items;

  const AppMenuCategory(this.label, this.icon, this.items);
}

/// Every navigable drawer item, grouped under a parent header, tagged with
/// the form code that gates it (see backend/app/core/rbac_seed.py
/// FORM_DEFINITIONS and the Forms Matrix screen). Which of these a given
/// user sees is entirely server-driven — fetched via GET /roles/forms/mine
/// into myFormCodesProvider — rather than guessed from role-name checks
/// here, so an Admin can regrant/revoke individual screens per role at
/// runtime without an app update. The backend remains the authority
/// regardless: every endpoint still rejects unauthorized reads/writes with
/// a 403 no matter what the drawer shows. Categories with zero granted
/// items are dropped entirely rather than shown empty.
const appMenuCategories = [
  AppMenuCategory('People', Icons.people_alt_rounded, [
    AppMenuItem('residents', 'Residents', Icons.people_outline_rounded, AppRoutes.residentsList),
    AppMenuItem('tenants', 'Tenants', Icons.groups_2_outlined, AppRoutes.tenantsList),
  ]),
  AppMenuCategory('Community', Icons.diversity_3_rounded, [
    AppMenuItem('visitors', 'Visitors', Icons.meeting_room_rounded, AppRoutes.visitorsMy),
    AppMenuItem('complaints', 'Complaints', Icons.report_problem_rounded, AppRoutes.complaints),
    AppMenuItem('pending_resident_changes', 'Pending Resident Changes', Icons.fact_check_outlined, AppRoutes.pendingResidentChanges),
  ]),
  AppMenuCategory('Operations', Icons.build_rounded, [
    AppMenuItem('staff', 'Staff', Icons.badge_rounded, AppRoutes.staffHome),
    AppMenuItem('checklist_templates', 'Checklist Templates', Icons.checklist_rtl_rounded, AppRoutes.checklistTemplates),
    AppMenuItem('parking_management', 'Parking Management', Icons.local_parking_rounded, AppRoutes.parkingManagement),
  ]),
  AppMenuCategory('Finance', Icons.payments_rounded, [
    AppMenuItem('maintenance_billing', 'Maintenance Billing', Icons.request_quote_rounded, AppRoutes.maintenanceBilling),
    AppMenuItem('maintenance_elements', 'Maintenance Elements', Icons.tune_rounded, AppRoutes.maintenanceElements),
    AppMenuItem('online_payments', 'Payments', Icons.receipt_long_rounded, AppRoutes.onlinePayments),
    AppMenuItem('bank_reconciliation', 'Bank Reconciliation', Icons.account_balance_rounded, AppRoutes.bankReconciliation),
    AppMenuItem('vendor_bills', 'Vendor Bills', Icons.storefront_rounded, AppRoutes.vendorBills),
  ]),
  AppMenuCategory('Administration', Icons.admin_panel_settings_rounded, [
    AppMenuItem('users_roles', 'Users & Roles', Icons.people_rounded, AppRoutes.usersList),
    AppMenuItem('permission_matrix', 'Permission Matrix', Icons.rule_rounded, AppRoutes.permissionMatrix),
    AppMenuItem('forms_matrix', 'Forms Matrix', Icons.dashboard_customize_rounded, AppRoutes.formsMatrix),
    AppMenuItem('society_settings', 'Society Settings', Icons.apartment_rounded, AppRoutes.societySettings),
    AppMenuItem('setup_wizard', 'Setup Wizard', Icons.checklist_rounded, AppRoutes.structureWizard),
  ]),
  AppMenuCategory('My Account', Icons.person_rounded, [
    AppMenuItem('my_bills', 'My Bills', Icons.receipt_long_rounded, AppRoutes.myBills),
    AppMenuItem('edit_my_info', 'Edit My Info', Icons.edit_note_rounded, AppRoutes.editMyProfile),
  ]),
];

List<AppMenuCategory> visibleMenuCategories(Set<String> grantedFormCodes) => appMenuCategories
    .map((category) => AppMenuCategory(
          category.label,
          category.icon,
          category.items.where((item) => grantedFormCodes.contains(item.formCode)).toList(),
        ))
    .where((category) => category.items.isNotEmpty)
    .toList();
