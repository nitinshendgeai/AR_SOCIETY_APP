import 'dart:io';

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:ar_society_app/core/layout/app_shell.dart';
import 'package:ar_society_app/core/navigation/app_menu.dart';
import 'package:ar_society_app/core/navigation/route_access.dart';
import 'package:ar_society_app/core/router/app_router.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/auth/data/datasources/auth_remote_datasource.dart';
import 'package:ar_society_app/features/auth/data/repositories/auth_repository.dart';
import 'package:ar_society_app/features/auth/domain/entities/society_choice.dart';
import 'package:ar_society_app/features/auth/domain/entities/user_entity.dart';
import 'package:ar_society_app/shared/widgets/dux_logo.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/features/notices/presentation/providers/notices_providers.dart';
import 'package:ar_society_app/features/users/presentation/providers/user_providers.dart';
import 'package:ar_society_app/features/visitor/presentation/providers/visitor_providers.dart';

// Form codes each seeded role is granted by default (mirrors FORM_ROLE_GRANTS in backend/app/core/rbac_seed.py).
const _member = ['meetings', 'polls', 'documents', 'certificates', 'parcels', 'domestic_help', 'visitors', 'complaints', 'notices', 'amenities'];
const _adminCommittee = [
  'residents', 'tenants', 'shops', 'automation', 'society_settings', 'pending_resident_changes', 'parking_management',
  'setup_wizard', 'manager_checklist', 'checklist_templates', 'online_payments', 'bank_reconciliation', 'vendor_bills',
  'vendors', 'vendor_master', 'maintenance_billing', 'maintenance_elements', 'accounts', 'defaulters', 'assets', 'inventory', 'staff',
];
final _admin = {..._member, ..._adminCommittee, 'users_roles', 'permission_matrix', 'forms_matrix'};
final _committee = {..._member, ..._adminCommittee};
final _manager = {
  ..._member, 'manager_checklist', 'staff', 'checklist_templates', 'online_payments', 'bank_reconciliation', 'vendor_bills',
  'vendors', 'vendor_master', 'maintenance_billing', 'maintenance_elements', 'accounts', 'defaulters', 'assets', 'inventory',
};
final _resident = {..._member, 'edit_my_info', 'my_bills'};
final _tenant = {..._member};
final _securityStaff = {..._member, 'staff'};

UserEntity _user(String role, {String? societyId = 's1'}) => UserEntity(
    id: 'u-$role', email: 'a@b.c', fullName: 'A B', roles: [role], societyId: societyId, termsAccepted: true);

Map<String, List<String>> _tree(Set<String> granted, UserEntity user) =>
    {for (final c in visibleMenuCategories(granted, user: user)) c.label: [for (final i in c.items) i.label]};

void main() {
  group('the master menu', () {
    test('groups and items, in order', () {
      expect({for (final c in appMenuCategories) c.label: [for (final i in c.items) i.label]}, {
        'Platform': ['Platform Console'],
        'People & Residents': ['Residents', 'Tenants', 'Pending Resident Changes', 'Staff'],
        'Property & Parking': ['Wings', 'Flats', 'Shops', 'Parking Management', 'Assets'],
        'Community & Services': [
          'Visitors', 'Parcels', 'Domestic help', 'Complaints', 'Notices', 'Amenities', 'Meetings', 'Polls', 'Documents',
          'Certificates & NOC',
        ],
        'Operations': ["Manager's Checklist", 'Checklist Templates', 'Stores', 'Vendors & Work', 'Vendor Master'],
        'Finance & Maintenance': [
          'Maintenance Billing', 'Maintenance Elements', 'Online Payments', 'Defaulters', 'Vendor Bills', 'Bank Reconciliation',
        ],
        'Accounts & Financial Reports': ['Accounts', 'Gateway of Accounts'],
        'Administration & Settings': [
          'Users & Roles', 'Permission Matrix', 'Forms Matrix', 'Society Settings', 'Automatic tasks', 'Setup Wizard',
        ],
        'Payments': ['My Bills'],
        'Profile & Help': ['Edit My Info'],
      });
    });

    test('no duplicate labels, routes or icons; every item has a route', () {
      final items = [for (final c in appMenuCategories) ...c.items];
      expect(items.length, 41); // the 40 that existed, plus the Vendor Master
      expect(items.map((i) => i.label).toSet().length, items.length, reason: 'duplicate label');
      expect(items.map((i) => i.route).toSet().length, items.length, reason: 'duplicate route');
      expect(items.map((i) => i.icon.codePoint).toSet().length, items.length, reason: 'duplicate icon');
      expect(items.every((i) => i.route != null && i.route!.startsWith('/')), isTrue);
      final groups = appMenuCategories.map((c) => c.label).toList();
      expect(groups.toSet().length, groups.length);
    });

    test('every form code in the menu is a real form on the server (no orphans)', () {
      final seed = File('../backend/app/core/rbac_seed.py').readAsStringSync();
      final defined = RegExp(r'^\s*\("([a-z_]+)",\s+"', multiLine: true).allMatches(seed).map((m) => m.group(1)!).toSet();
      expect(defined, isNotEmpty);
      final used = {for (final c in appMenuCategories) for (final i in c.items) i.formCode};
      expect(used.difference(defined), isEmpty);
    });

    test('every guarded menu route maps to the form code of its own entry', () {
      for (final c in appMenuCategories) {
        for (final i in c.items) {
          final guard = formCodeForPath(i.route!);
          if (guard != null) expect(guard, i.formCode, reason: i.label);
        }
      }
    });

    test('the Accounts group opens the existing landing page and Gateway, nothing new', () {
      final accounts = appMenuCategories.firstWhere((c) => c.label == 'Accounts & Financial Reports');
      expect(accounts.items.map((i) => i.route), [AppRoutes.accounts, AppRoutes.accountsGateway]);
      expect(accounts.items.map((i) => i.formCode).toSet(), {'accounts'});
    });
  });

  group('who sees what', () {
    test('Society Admin sees every management group and nothing of the resident menu', () {
      final t = _tree(_admin, _user('Society Admin'));
      expect(t.keys, [
        'People & Residents', 'Property & Parking', 'Community & Services', 'Operations', 'Finance & Maintenance',
        'Accounts & Financial Reports', 'Administration & Settings',
      ]);
      expect(t['Administration & Settings'], contains('Users & Roles'));
      expect(t.values.expand((x) => x).length, 38);
    });

    test('Committee has no Users, Permission Matrix or Forms Matrix', () {
      final t = _tree(_committee, _user('Committee Chairman'));
      expect(t['Administration & Settings'], ['Society Settings', 'Automatic tasks', 'Setup Wizard']);
    });

    test('Manager: no people records, no administration', () {
      final t = _tree(_manager, _user('Manager'));
      expect(t['People & Residents'], ['Staff']);
      expect(t['Property & Parking'], ['Assets']);
      expect(t.containsKey('Administration & Settings'), isFalse);
      expect(t['Accounts & Financial Reports'], ['Accounts', 'Gateway of Accounts']);
    });

    test('Resident: own bills first, community screens, own profile; nothing administrative', () {
      final t = _tree(_resident, _user('Resident'));
      expect(t.keys, ['Payments', 'Community & Services', 'Profile & Help']);
      expect(t['Payments'], ['My Bills']);
      expect(t['Profile & Help'], ['Edit My Info']);
      final all = t.values.expand((x) => x).toSet();
      for (final admin in ['Residents', 'Accounts', 'Gateway of Accounts', 'Users & Roles', 'Online Payments', 'Staff']) {
        expect(all, isNot(contains(admin)));
      }
    });

    test('Tenant keeps its existing gap: community screens only (decision D5, not changed)', () {
      expect(_tree(_tenant, _user('Tenant')).keys, ['Community & Services']);
    });

    test('Security Staff: community screens and the Staff Portal', () {
      final t = _tree(_securityStaff, _user('Security Staff'));
      expect(t.keys, ['People & Residents', 'Community & Services']);
      expect(t['People & Residents'], ['Staff']);
    });

    test('Platform Admin sees only the console', () {
      final t = _tree({..._admin, 'platform_admin'}, _user('Platform Admin', societyId: null));
      expect(t, {'Platform': ['Platform Console']});
    });

    test('a group with nothing granted is not shown, and with nothing granted there is no menu', () {
      expect(visibleMenuCategories(const {}, user: _user('Resident')), isEmpty);
    });

    test('role-resolved routes survive the move', () {
      final admin = visibleMenuCategories(_admin, user: _user('Society Admin'));
      String route(String label) => [for (final c in admin) ...c.items].firstWhere((i) => i.label == label).route!;
      expect(route('Visitors'), '/visitors/society/s1');
      expect(route('Complaints'), '/complaints/society/s1');
      expect(route('Staff'), AppRoutes.staffList);
      final sec = visibleMenuCategories(_securityStaff, user: _user('Security Staff'));
      expect([for (final c in sec) ...c.items].firstWhere((i) => i.label == 'Staff').route, AppRoutes.staffHome);
    });
  });

  group('breadcrumbs', () {
    test('pages opened from Accounts are named; unknown pages are not guessed', () {
      expect(subPageLabel('/accounts/day-book'), 'Day Book');
      expect(subPageLabel('/accounts/registers/cash-bank'), 'Cash & Bank Book');
      expect(subPageLabel('/accounts/statements/trial-balance?fy=2025-26'), 'Trial Balance');
      expect(subPageLabel('/accounts/statements'), 'Financial Statements');
      expect(subPageLabel('/accounts/vouchers/new?type=receipt'), 'New Voucher');
      expect(subPageLabel('/accounts/ledger/abc'), 'Ledger');
      expect(subPageLabel('/accounts/vouchers/v1/edit'), 'Edit Voucher');
      expect(subPageLabel('/accounts/statements/unknown-report'), isNull);
      expect(subPageLabel('/accounts'), isNull);
      expect(subPageLabel('/residents/detail'), isNull);
    });
  });

  group('the sidebar', () {
    Future<GoRouter> boot(WidgetTester t, UserEntity user, Set<String> granted, {String start = '/admin'}) async {
      t.view.physicalSize = const Size(1400, 1000);
      t.view.devicePixelRatio = 1.0;
      addTearDown(t.view.resetPhysicalSize);
      addTearDown(t.view.resetDevicePixelRatio);
      Widget page(String name) => Center(child: Text('page $name'));
      final router = GoRouter(initialLocation: start, routes: [
        ShellRoute(
          builder: (_, state, child) => AppShell(location: state.uri.path, child: child),
          routes: [
            for (final p in ['/admin', '/residents', '/staff/list', '/accounts', '/accounts/gateway', '/accounts/day-book', '/users', '/vendors/bills', '/billing/online-payments'])
              GoRoute(path: p, builder: (_, __) => page(p)),
          ],
        ),
      ]);
      await t.pumpWidget(ProviderScope(
        overrides: [
          authProvider.overrideWith((ref) => _SignedIn(ref, user)),
          myFormCodesProvider.overrideWith((ref) async => granted.toList()),
          pendingVisitorApprovalsProvider.overrideWith((ref) => Stream.value(const [])),
          activeAlertsProvider.overrideWith((ref) => Stream.value(const [])),
        ],
        child: MaterialApp.router(theme: AppTheme.lightTheme, routerConfig: router),
      ));
      await t.pumpAndSettle();
      return router;
    }

    bool open(String label) => find.byKey(Key('nav-group-$label')).evaluate().isNotEmpty;

    testWidgets('on the dashboard, which is in no group, the first group is open', (t) async {
      await boot(t, _user('Society Admin'), _admin, start: '/admin');
      expect(find.text('Residents'), findsOneWidget);            // People & Residents, the first group
      expect(find.text('Wings'), findsNothing);                 // the others stay closed
      expect(find.text('Gateway of Accounts'), findsNothing);
    });

    testWidgets('shows the groups; only the group of the current page starts open', (t) async {
      await boot(t, _user('Society Admin'), _admin, start: '/residents');
      expect(open('People & Residents') && open('Accounts & Financial Reports') && open('Administration & Settings'), isTrue);
      expect(find.text('Residents'), findsWidgets);              // its group is open (also in the breadcrumb)
      expect(find.text('Gateway of Accounts'), findsNothing);    // another group is closed
      expect(find.text('Users & Roles'), findsNothing);
    });

    testWidgets('clicking a heading opens and closes its group, and the choice lasts only for that page', (t) async {
      final router = await boot(t, _user('Society Admin'), _admin, start: '/residents');
      await t.tap(find.byKey(const Key('nav-group-Accounts & Financial Reports')));
      await t.pumpAndSettle();
      expect(find.text('Gateway of Accounts'), findsOneWidget);
      await t.tap(find.byKey(const Key('nav-group-Accounts & Financial Reports')));
      await t.pumpAndSettle();
      expect(find.text('Gateway of Accounts'), findsNothing);

      // Going to a page in a closed group opens that group.
      router.go('/accounts/gateway');
      await t.pumpAndSettle();
      expect(find.text('Gateway of Accounts'), findsWidgets);
      expect(find.text('Users & Roles'), findsNothing);
    });

    // The selected entry is drawn in the primary colour.
    bool selected(WidgetTester t, String label) {
      final text = t.widget<Text>(find.descendant(of: find.byType(ListView).first, matching: find.text(label)).first);
      return text.style?.color == AppTheme.primary;
    }

    testWidgets('the current page is the selected entry; a page below it keeps its parent selected', (t) async {
      await boot(t, _user('Society Admin'), _admin, start: '/accounts/day-book');
      expect(selected(t, 'Accounts'), isTrue);
      expect(selected(t, 'Gateway of Accounts'), isFalse);
    });

    testWidgets('the Gateway entry is selected on the Gateway, not Accounts', (t) async {
      await boot(t, _user('Society Admin'), _admin, start: '/accounts/gateway');
      expect(selected(t, 'Gateway of Accounts'), isTrue);
      expect(selected(t, 'Accounts'), isFalse);
    });

    testWidgets('a page opened from Accounts adds a third crumb; the entry itself does not', (t) async {
      final router = await boot(t, _user('Society Admin'), _admin, start: '/accounts');
      expect(find.text('Day Book'), findsNothing);
      router.go('/accounts/day-book');
      await t.pumpAndSettle();
      expect(find.text('Day Book'), findsOneWidget);                  // the crumb (the page is a stub)
      expect(find.text('Accounts & Financial Reports'), findsWidgets);
    });

    testWidgets('the brand block is the DUX OS logo, with the society under the name', (t) async {
      const user = UserEntity(
        id: 'u', email: 'a@b.c', fullName: 'A B', roles: ['Society Admin'], societyId: 's1', termsAccepted: true,
        societies: [
          SocietyChoice(societyId: 's0', societyName: 'Other Society'),
          SocietyChoice(societyId: 's1', societyName: 'Green Park CHS', current: true),
        ],
      );
      await boot(t, user, _admin, start: '/residents');
      expect(find.byType(DuxLogo), findsOneWidget);
      final image = t.widget<Image>(find.descendant(of: find.byType(DuxLogo), matching: find.byType(Image)));
      expect((image.image as AssetImage).assetName, 'assets/branding/duxos_logo.png');
      expect(find.text('DUX OS'), findsOneWidget);
      expect(find.text('Green Park CHS'), findsOneWidget);
      expect(find.text('Other Society'), findsNothing);
    });

    testWidgets('with a single society the subtitle stays "Society ERP"; collapsed shows the logo alone', (t) async {
      await boot(t, _user('Society Admin'), _admin, start: '/residents');
      expect(find.text('Society ERP'), findsOneWidget);
      await t.tap(find.text('Collapse'));
      await t.pumpAndSettle();
      expect(find.byType(DuxLogo), findsOneWidget);
      expect(find.text('DUX OS'), findsNothing);
    });

    testWidgets('a menu entry navigates to its route', (t) async {
      final router = await boot(t, _user('Society Admin'), _admin, start: '/accounts');
      await t.tap(find.text('Gateway of Accounts').first);
      await t.pumpAndSettle();
      expect(router.routeInformationProvider.value.uri.path, '/accounts/gateway');
    });

    testWidgets('collapsing the sidebar leaves an icon rail with every entry reachable by tooltip', (t) async {
      await boot(t, _user('Society Admin'), _admin, start: '/residents');
      t.view.physicalSize = const Size(1400, 2600);
      await t.pumpAndSettle();
      await t.tap(find.text('Collapse'));
      await t.pumpAndSettle();
      expect(find.byKey(const Key('nav-group-People & Residents')), findsNothing);
      expect(find.byType(Tooltip), findsWidgets);
      expect(find.byTooltip('Gateway of Accounts'), findsOneWidget);
    });

    testWidgets('a long menu scrolls while the brand and Collapse stay in place', (t) async {
      await boot(t, _user('Society Admin'), _admin, start: '/residents');
      t.view.physicalSize = const Size(1400, 2600);
      await t.pumpAndSettle();
      for (final g in ['Property & Parking', 'Community & Services', 'Operations']) {
        await t.tap(find.byKey(Key('nav-group-$g')));
        await t.pumpAndSettle();
      }
      t.view.physicalSize = const Size(1400, 380);
      await t.pumpAndSettle();
      final list = t.state<ScrollableState>(find.descendant(of: find.byType(ListView).first, matching: find.byType(Scrollable)).first);
      expect(list.position.maxScrollExtent, greaterThan(0));
      expect(find.text('DUX OS'), findsOneWidget);
      expect(find.text('Collapse'), findsOneWidget);
    });
  });
}

class _SignedIn extends AuthNotifier {
  _SignedIn(Ref ref, UserEntity user) : super(AuthRepository(remote: AuthRemoteDataSource(dio: Dio())), ref) {
    state = AuthAuthenticated(user);
  }
}
