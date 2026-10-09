import 'package:flutter/material.dart';
import 'package:ar_society_app/core/router/app_router.dart';
import 'package:ar_society_app/features/auth/domain/entities/user_entity.dart';

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
  AppMenuCategory('Platform', Icons.public_rounded, [
    AppMenuItem('platform_admin', 'Platform Console', Icons.dashboard_rounded, AppRoutes.platformHome),
  ]),
  AppMenuCategory('People', Icons.people_alt_rounded, [
    AppMenuItem('residents', 'Residents', Icons.people_outline_rounded, AppRoutes.residentsList),
    AppMenuItem('tenants', 'Tenants', Icons.groups_2_outlined, AppRoutes.tenantsList),
  ]),
  // Wings and flats are everyday records (who lives where, what is vacant), not
  // just first-time setup, so they sit in the menu rather than only behind the
  // Setup Wizard. They share the wizard's access.
  AppMenuCategory('Property', Icons.apartment_rounded, [
    AppMenuItem('setup_wizard', 'Wings', Icons.domain_rounded, AppRoutes.wingsList),
    AppMenuItem('setup_wizard', 'Flats', Icons.door_front_door_rounded, AppRoutes.flatsList),
    AppMenuItem('shops', 'Shops', Icons.storefront_rounded, AppRoutes.shops),
  ]),
  AppMenuCategory('Community', Icons.diversity_3_rounded, [
    AppMenuItem('visitors', 'Visitors', Icons.meeting_room_rounded, AppRoutes.visitorsMy),
    AppMenuItem('notices', 'Notices', Icons.campaign_rounded, AppRoutes.notices),
    AppMenuItem('amenities', 'Amenities', Icons.pool_rounded, AppRoutes.amenities),
    AppMenuItem('meetings', 'Meetings', Icons.groups_rounded, AppRoutes.meetings),
    AppMenuItem('polls', 'Polls', Icons.how_to_vote_rounded, AppRoutes.polls),
    AppMenuItem('documents', 'Documents', Icons.folder_open_rounded, AppRoutes.documents),
    AppMenuItem('certificates', 'Certificates & NOC', Icons.verified_outlined, AppRoutes.certificates),
    AppMenuItem('parcels', 'Parcels', Icons.inventory_2_rounded, AppRoutes.parcels),
    AppMenuItem('domestic_help', 'Domestic help', Icons.cleaning_services_rounded, AppRoutes.domesticHelp),
    AppMenuItem('complaints', 'Complaints', Icons.report_problem_rounded, AppRoutes.complaints),
    AppMenuItem('pending_resident_changes', 'Pending Resident Changes', Icons.fact_check_outlined, AppRoutes.pendingResidentChanges),
  ]),
  AppMenuCategory('Operations', Icons.build_rounded, [
    AppMenuItem('staff', 'Staff', Icons.badge_rounded, AppRoutes.staffHome),
    AppMenuItem('checklist_templates', 'Checklist Templates', Icons.checklist_rtl_rounded, AppRoutes.checklistTemplates),
    AppMenuItem('parking_management', 'Parking Management', Icons.local_parking_rounded, AppRoutes.parkingManagement),
    AppMenuItem('assets', 'Assets', Icons.inventory_2_rounded, AppRoutes.assets),
    AppMenuItem('inventory', 'Stores', Icons.warehouse_rounded, AppRoutes.stores),
    AppMenuItem('vendors', 'Vendors & Work', Icons.handyman_rounded, AppRoutes.vendorsWork),
  ]),
  AppMenuCategory('Finance', Icons.payments_rounded, [
    AppMenuItem('maintenance_billing', 'Maintenance Billing', Icons.request_quote_rounded, AppRoutes.maintenanceBilling),
    AppMenuItem('maintenance_elements', 'Maintenance Elements', Icons.tune_rounded, AppRoutes.maintenanceElements),
    AppMenuItem('online_payments', 'Payments', Icons.receipt_long_rounded, AppRoutes.onlinePayments),
    AppMenuItem('defaulters', 'Defaulters', Icons.warning_amber_rounded, AppRoutes.defaulters),
    AppMenuItem('bank_reconciliation', 'Bank Reconciliation', Icons.account_balance_rounded, AppRoutes.bankReconciliation),
    AppMenuItem('vendor_bills', 'Vendor Bills', Icons.storefront_rounded, AppRoutes.vendorBills),
    AppMenuItem('accounts', 'Accounts', Icons.account_balance_wallet_rounded, AppRoutes.accounts),
  ]),
  AppMenuCategory('Administration', Icons.admin_panel_settings_rounded, [
    AppMenuItem('users_roles', 'Users & Roles', Icons.people_rounded, AppRoutes.usersList),
    AppMenuItem('permission_matrix', 'Permission Matrix', Icons.rule_rounded, AppRoutes.permissionMatrix),
    AppMenuItem('forms_matrix', 'Forms Matrix', Icons.dashboard_customize_rounded, AppRoutes.formsMatrix),
    AppMenuItem('society_settings', 'Society Settings', Icons.apartment_rounded, AppRoutes.societySettings),
    AppMenuItem('automation', 'Automatic tasks', Icons.autorenew_rounded, AppRoutes.automation),
    AppMenuItem('setup_wizard', 'Setup Wizard', Icons.checklist_rounded, AppRoutes.structureWizard),
  ]),
  AppMenuCategory('My Account', Icons.person_rounded, [
    AppMenuItem('my_bills', 'My Bills', Icons.receipt_long_rounded, AppRoutes.myBills),
    AppMenuItem('edit_my_info', 'Edit My Info', Icons.edit_note_rounded, AppRoutes.editMyProfile),
  ]),
];

/// The menu entries [grantedFormCodes] allow, grouped by category, with
/// routes resolved for [user]: people who run the society (admin,
/// committee, manager, security) land on the society-wide Visitors and
/// Complaints lists, everyone else on their own; admin, committee and
/// managers get the staff register rather than the Staff Portal.
List<AppMenuCategory> visibleMenuCategories(Set<String> grantedFormCodes, {UserEntity? user}) => appMenuCategories
    // The society screens need a society; a platform admin has none, so they see only the console.
    .where((category) => user?.isPlatformAdmin != true || category.label == 'Platform')
    .map((category) => AppMenuCategory(
          category.label,
          category.icon,
          category.items
              .where((item) => grantedFormCodes.contains(item.formCode))
              .map((item) => _resolveFor(item, user))
              .toList(),
        ))
    .where((category) => category.items.isNotEmpty)
    .toList();

AppMenuItem _resolveFor(AppMenuItem item, UserEntity? user) {
  final societyId = user?.societyId;
  if (user == null || societyId == null) return item;
  final societyWide = user.isAdminOrCommittee || user.isManager || user.isSecurity;
  if (!societyWide) return item;
  // The Staff Portal is a staff member's own workspace (attendance,
  // duties…); people who manage staff but aren't staff themselves get the
  // staff register instead.
  final managesStaff = user.isAdminOrCommittee || user.isManager;
  final route = switch (item.route) {
    AppRoutes.visitorsMy => AppRoutes.visitorsSociety.replaceFirst(':societyId', societyId),
    AppRoutes.complaints => AppRoutes.complaintsSociety.replaceFirst(':societyId', societyId),
    AppRoutes.staffHome when managesStaff => AppRoutes.staffList,
    _ => item.route,
  };
  return route == item.route ? item : AppMenuItem(item.formCode, item.label, item.icon, route);
}

/// One tab of the phone's bottom bar.
class PhoneTab {
  final String label;
  final IconData icon;
  final String route;
  const PhoneTab(this.label, this.icon, this.route);
}

/// Short names for the bottom bar, where the menu's name is too long for it.
const _tabLabels = {'my_bills': 'Bills', 'maintenance_billing': 'Billing'};

/// The screens each kind of person reaches for most, in order. The bar takes the
/// first three they are allowed to open; "Home" and "More" are always there.
List<String> _tabPreference(UserEntity user) {
  if (user.isAdminOrCommittee || user.isManager) {
    return const ['visitors', 'complaints', 'maintenance_billing', 'notices'];
  }
  if (user.isSecurity) return const ['visitors', 'notices', 'complaints'];
  if (user.isResident) return const ['my_bills', 'visitors', 'notices', 'complaints'];
  return const ['notices', 'complaints', 'visitors'];
}

/// Home plus up to three screens for [user], limited to what [grantedFormCodes]
/// allow. Routes are resolved the way the menu does (society-wide lists for the
/// people who run the society).
List<PhoneTab> phoneTabsFor(UserEntity user, Set<String> grantedFormCodes) {
  final byCode = <String, AppMenuItem>{};
  for (final c in visibleMenuCategories(grantedFormCodes, user: user)) {
    for (final i in c.items) {
      if (i.route != null) byCode.putIfAbsent(i.formCode, () => i);
    }
  }
  final tabs = <PhoneTab>[PhoneTab('Home', Icons.home_rounded, userRoleHome(user))];
  for (final code in _tabPreference(user)) {
    final item = byCode[code];
    if (item == null) continue;
    tabs.add(PhoneTab(_tabLabels[code] ?? item.label, item.icon, item.route!));
    if (tabs.length == 4) break;
  }
  return tabs;
}
