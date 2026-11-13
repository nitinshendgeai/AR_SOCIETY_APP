import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ar_society_app/core/layout/phone_bottom_bar.dart';
import 'package:ar_society_app/core/navigation/app_menu.dart';
import 'package:ar_society_app/core/router/app_router.dart' show userRoleHome;
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/auth/domain/entities/user_entity.dart';
import 'package:ar_society_app/features/visitor/presentation/providers/visitor_providers.dart';

/// Which screens each role's phone menu offers. These were the "Role-aware navigation drawer" tests; the dashboards'
/// own drawer is gone (the bottom bar's More menu holds the same server-granted menu), so the same checks now open
/// that menu. The persona form codes mirror backend/app/core/rbac_seed.py's default FORM_ROLE_GRANTS.

UserEntity _user(String role) =>
    UserEntity(id: 'user-1', email: 'test@example.com', fullName: 'Test User', roles: [role], societyId: 's1');

const _adminFormCodes = [
  'residents', 'tenants', 'users_roles', 'permission_matrix', 'forms_matrix',
  'society_settings', 'visitors', 'complaints', 'pending_resident_changes',
  'staff', 'parking_management', 'setup_wizard',
];
const _committeeFormCodes = [
  'residents', 'tenants', 'society_settings', 'visitors', 'complaints',
  'pending_resident_changes', 'staff', 'parking_management', 'setup_wizard',
];
const _securityFormCodes = ['visitors', 'complaints', 'staff'];
const _residentFormCodes = ['visitors', 'complaints', 'edit_my_info', 'my_bills'];

/// The account actions at the bottom of More: not screens of the menu.
const _accountActions = {'Language', 'Switch society', 'Help', 'Signed-in devices', 'Sign out'};

/// Opens More for [user] and returns every screen the menu lists, group by group (the sheet shows one group at a
/// time, so each group's pill is tapped in turn).
Future<Set<String>> _menuOf(WidgetTester t, UserEntity user, List<String> codes) async {
  t.view.physicalSize = const Size(800, 2400);
  t.view.devicePixelRatio = 1;
  addTearDown(t.view.resetPhysicalSize);
  addTearDown(t.view.resetDevicePixelRatio);
  final granted = codes.toSet();
  final menu = visibleMenuCategories(granted, user: user);
  await t.pumpWidget(ProviderScope(
    overrides: [pendingVisitorApprovalsProvider.overrideWith((ref) => Stream.value(const []))],
    child: MaterialApp(
      theme: AppTheme.lightTheme,
      home: Scaffold(
        bottomNavigationBar: PhoneBottomBar(
            location: userRoleHome(user), user: user, tabs: phoneTabsFor(user, granted), menu: menu),
      ),
    ),
  ));
  await t.pumpAndSettle();
  await t.tap(find.text('More'));
  await t.pumpAndSettle();

  final labels = <String>{};
  for (final group in menu) {
    await t.tap(find.text(group.label));
    await t.pumpAndSettle();
    for (final tile in t.widgetList<ListTile>(find.byType(ListTile))) {
      final title = tile.title;
      if (title is Text && title.data != null && !_accountActions.contains(title.data)) labels.add(title.data!);
    }
  }
  return labels;
}

void main() {
  group('Role-aware navigation (the More menu)', () {
    testWidgets('Society Admin sees the full administrative menu', (t) async {
      final labels = await _menuOf(t, _user('Society Admin'), _adminFormCodes);
      for (final label in [
        'Residents', 'Tenants', 'Users & Roles', 'Permission Matrix', 'Forms Matrix', 'Society Settings',
        'Visitors', 'Complaints', 'Pending Resident Changes', 'Staff', 'Parking Management', 'Setup Wizard',
        'Wings', 'Flats',
      ]) {
        expect(labels, contains(label), reason: '$label should be in the admin menu');
      }
    });

    testWidgets('Committee sees admin-committee items but not Users & Roles, Permission Matrix, or Forms Matrix', (t) async {
      final labels = await _menuOf(t, _user('Committee'), _committeeFormCodes);
      for (final label in [
        'Residents', 'Tenants', 'Society Settings', 'Visitors', 'Complaints',
        'Pending Resident Changes', 'Staff', 'Parking Management', 'Setup Wizard',
      ]) {
        expect(labels, contains(label), reason: '$label should be in the committee menu');
      }
      for (final label in ['Users & Roles', 'Permission Matrix', 'Forms Matrix']) {
        expect(labels, isNot(contains(label)), reason: '$label must not be visible to Committee');
      }
    });

    testWidgets('Security Staff sees operational items only, no admin configuration screens', (t) async {
      final labels = await _menuOf(t, _user('Security'), _securityFormCodes);
      for (final label in ['Visitors', 'Complaints', 'Staff']) {
        expect(labels, contains(label), reason: '$label should be in the security menu');
      }
      for (final label in [
        'Residents', 'Tenants', 'Users & Roles', 'Permission Matrix', 'Forms Matrix', 'Society Settings', 'Setup Wizard',
      ]) {
        expect(labels, isNot(contains(label)), reason: '$label must not be visible to Security');
      }
    });

    testWidgets('Resident sees only resident-facing navigation, not admin or master links', (t) async {
      final labels = await _menuOf(t, _user('Resident'), _residentFormCodes);
      for (final label in ['Visitors', 'Complaints']) {
        expect(labels, contains(label), reason: '$label should be in the resident menu');
      }
      for (final label in [
        'Residents', 'Tenants', 'Users & Roles', 'Permission Matrix', 'Forms Matrix', 'Society Settings', 'Staff', 'Setup Wizard',
      ]) {
        expect(labels, isNot(contains(label)), reason: '$label must not be visible to Resident');
      }
    });

    testWidgets('the menu lists nothing the role was not granted, whatever the role is called', (t) async {
      // A person with no grants at all is offered no screens.
      final labels = await _menuOf(t, _user('Society Admin'), const ['visitors']);
      expect(labels, {'Visitors'});
    });
  });
}
