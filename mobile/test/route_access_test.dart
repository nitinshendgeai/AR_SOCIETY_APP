import 'dart:async';

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:ar_society_app/core/navigation/app_menu.dart';
import 'package:ar_society_app/core/navigation/route_access.dart';
import 'package:ar_society_app/core/router/app_router.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/auth/data/datasources/auth_remote_datasource.dart';
import 'package:ar_society_app/features/auth/data/repositories/auth_repository.dart';
import 'package:ar_society_app/features/auth/domain/entities/user_entity.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/features/staff/data/datasources/staff_remote_datasource.dart';
import 'package:ar_society_app/features/staff/data/repositories/staff_repository.dart';
import 'package:ar_society_app/features/staff/presentation/providers/staff_providers.dart';
import 'package:ar_society_app/features/users/presentation/providers/user_providers.dart';

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
final _securityStaff = {..._member, 'staff'};

RouteDenial? _deny(String path, {required String home, Set<String>? granted, bool platform = false}) =>
    routeDenial(path: path, home: home, platformAdmin: platform, granted: granted);

void main() {
  group('formCodeForPath', () {
    const table = <String, String?>{
      '/residents': 'residents',
      '/residents/detail': 'residents',
      '/residents/import': 'residents',
      '/residents/edit-requests/pending': 'pending_resident_changes',
      '/residents/me/edit': null,                    // a member's own profile
      '/tenants/form': 'tenants',
      '/users': 'users_roles',
      '/users/abc/roles': 'users_roles',
      '/users/password-requests': 'users_roles',
      '/usersx': null,                                // whole segments only
      '/permission-matrix': 'permission_matrix',
      '/forms-matrix': 'forms_matrix',
      '/society-settings': 'society_settings',
      '/wings/form': 'setup_wizard',
      '/wings/w1/floors': 'setup_wizard',
      '/flats/detail': 'setup_wizard',
      '/structure-wizard': 'setup_wizard',
      '/parking/management': 'parking_management',
      '/parking/gate-check': null,                    // the guard's screen
      '/staff/checklist-templates': 'checklist_templates',
      '/staff': null,                                 // the Staff area is not guarded
      '/staff/attendance/s1': null,
      '/manager-checklist': 'manager_checklist',
      '/billing/maintenance': 'maintenance_billing',
      '/billing/maintenance-elements': 'maintenance_elements',
      '/billing/online-payments': 'online_payments',
      '/billing/bank-reconciliation': 'bank_reconciliation',
      '/billing/defaulters': 'defaulters',
      '/billing/my-bills': null,                      // members' own bills
      '/vendors/bills': 'vendor_bills',
      '/vendors/master': 'vendor_master',
      '/vendors/import': 'vendor_master',        // the import and the TDS review are part of the Vendor Master
      '/vendors/tds-review': 'vendor_master',
      '/vendors/tds-rules': 'vendor_master',
      '/vendors/tds-register': 'vendor_master',
      '/vendors/work': 'vendors',
      '/vendors/work-orders/w1': 'vendors',
      '/accounts': 'accounts',
      '/accounts/ledger/a1': 'accounts',
      '/assets/a1': 'assets',
      '/stores/i1': 'inventory',
      '/visitors/pending': null,                      // member screens are left to the backend
      '/complaints': null,
      '/notices': null,
      '/amenities': null,
      '/shops': 'shops',
      '/automation': 'automation',
      '/accounts?tab=cash': 'accounts',               // a query string does not matter
      '/accounts/': 'accounts',
    };
    table.forEach((path, code) => test(path, () => expect(formCodeForPath(path), code)));

    test('agrees with the menu: every guarded menu entry maps to its own form code', () {
      const memberForms = {
        'visitors', 'complaints', 'notices', 'amenities', 'meetings', 'polls', 'documents', 'certificates',
        'parcels', 'domestic_help', 'my_bills', 'edit_my_info', 'staff', 'platform_admin',
      };
      for (final category in appMenuCategories) {
        for (final item in category.items) {
          final route = item.route;
          if (route == null || memberForms.contains(item.formCode)) continue;
          expect(formCodeForPath(route), item.formCode,
              reason: '${item.label} (${item.formCode}) opens $route; the guard must use the same form code as the menu');
        }
      }
    });

    test('the member-facing menu entries are deliberately not guarded', () {
      for (final category in appMenuCategories) {
        for (final item in category.items) {
          if (item.route == null) continue;
          if (const {'my_bills', 'edit_my_info', 'visitors', 'complaints', 'notices', 'amenities', 'meetings', 'polls',
            'documents', 'certificates', 'parcels', 'domestic_help'}.contains(item.formCode)) {
            expect(formCodeForPath(item.route!), isNull, reason: item.label);
          }
        }
      }
    });
  });

  group('routeDenial', () {
    test('a screen the person has no grant for goes to their home, with a notice', () {
      final d = _deny('/accounts', home: '/resident', granted: _resident)!;
      expect(d.location, '/resident');
      expect(d.notify, isTrue);
    });

    test('a screen the person is granted opens', () {
      expect(_deny('/accounts', home: '/manager', granted: _manager), isNull);
      expect(_deny('/permission-matrix', home: '/admin', granted: _admin), isNull);
    });

    test('while the grants are unknown nothing is blocked (the backend decides)', () {
      expect(_deny('/accounts', home: '/resident', granted: null), isNull);
      expect(_deny('/users', home: '/resident', granted: null), isNull);
    });

    test('an empty grant list is a real answer: management screens are refused', () {
      expect(_deny('/residents', home: '/resident', granted: <String>{})?.location, '/resident');
    });

    test('screens that are not guarded here are never refused', () {
      expect(_deny('/visitors/pending', home: '/resident', granted: <String>{}), isNull);
      expect(_deny('/billing/my-bills', home: '/resident', granted: <String>{}), isNull);
      expect(_deny('/staff/attendance/s1', home: '/staff', granted: <String>{}), isNull);
    });

    test('the platform admin is never refused here', () {
      expect(_deny('/accounts', home: '/platform', granted: <String>{}, platform: true), isNull);
      expect(_deny('/admin', home: '/platform', granted: <String>{}, platform: true), isNull);
    });

    test('someone is never sent to a place that would send them back', () {
      // A home that is itself guarded, or the very screen requested, ends the redirect chain.
      expect(_deny('/accounts', home: '/accounts', granted: <String>{}), isNull);
      expect(_deny('/accounts', home: '/residents', granted: <String>{}), isNull);
    });

    test('another role\'s dashboard goes to the person\'s own, quietly', () {
      final d = _deny('/admin', home: '/resident', granted: _resident)!;
      expect(d.location, '/resident');
      expect(d.notify, isFalse);
      expect(_deny('/resident', home: '/resident', granted: _resident), isNull);
    });

    test('dashboards are refused even before the grants have loaded', () {
      expect(_deny('/manager', home: '/resident', granted: null)?.location, '/resident');
    });

    // The role-by-role picture, using what each seeded role is granted by default.
    final scenarios = <String, ({String home, Set<String> granted, List<String> open, List<String> shut})>{
      'Society Admin': (home: '/admin', granted: _admin,
          open: ['/users', '/permission-matrix', '/forms-matrix', '/accounts', '/residents', '/wings', '/automation'], shut: []),
      'Committee Chairman': (home: '/committee', granted: _committee,
          open: ['/accounts', '/residents', '/society-settings', '/billing/defaulters'],
          shut: ['/users', '/permission-matrix', '/forms-matrix']),
      'Manager': (home: '/manager', granted: _manager,
          open: ['/billing/maintenance', '/accounts', '/vendors/bills', '/assets', '/stores'],
          shut: ['/residents', '/tenants', '/users', '/society-settings', '/wings', '/permission-matrix']),
      'Resident': (home: '/resident', granted: _resident,
          open: ['/visitors/pending', '/complaints', '/billing/my-bills', '/residents/me/edit', '/notices'],
          shut: ['/accounts', '/residents', '/users', '/billing/maintenance', '/vendors/bills', '/wings', '/automation']),
      'Security Staff': (home: '/staff', granted: _securityStaff,
          open: ['/staff/attendance/s1', '/visitors/society/s1', '/parking/gate-check'],
          shut: ['/accounts', '/residents', '/users', '/billing/maintenance']),
    };
    scenarios.forEach((role, sc) {
      test('$role: what opens and what is turned away', () {
        for (final p in sc.open) {
          expect(_deny(p, home: sc.home, granted: sc.granted), isNull, reason: '$role should open $p');
        }
        for (final p in sc.shut) {
          expect(_deny(p, home: sc.home, granted: sc.granted)?.location, sc.home, reason: '$role should be turned away from $p');
        }
      });
    });
  });

  // The real router, with real redirects: a signed-in person types an address.
  group('the router applies the guard to typed addresses', () {
    StaffRepository staffRepo() => StaffRepository(ds: StaffRemoteDataSource(dio: Dio()));

    Future<GoRouter> boot(WidgetTester t, UserEntity user, Future<List<String>> Function() forms) async {
      final container = ProviderContainer(overrides: [
        authProvider.overrideWith((ref) => _SignedIn(ref, user)),
        myFormCodesProvider.overrideWith((ref) => forms()),
        staffRepositoryProvider.overrideWithValue(staffRepo()),
      ]);
      addTearDown(container.dispose);
      final router = container.read(appRouterProvider);
      t.view.physicalSize = const Size(420, 2400);
      t.view.devicePixelRatio = 1.0;
      addTearDown(t.view.resetPhysicalSize);
      addTearDown(t.view.resetDevicePixelRatio);
      await t.pumpWidget(UncontrolledProviderScope(
        container: container,
        child: MaterialApp.router(theme: AppTheme.lightTheme, routerConfig: router),
      ));
      await t.pump();
      await t.pump(const Duration(milliseconds: 100));
      return router;
    }

    String where(GoRouter r) => r.routeInformationProvider.value.uri.path;

    UserEntity user(String role) => UserEntity(
        id: 'u-$role', email: 'a@b.c', fullName: 'A B', roles: [role], societyId: 's1', termsAccepted: true,
        enabledServices: const ['complaints', 'visitors']);

    testWidgets('a Resident who types a management address lands on their dashboard and is told', (t) async {
      final router = await boot(t, user('Resident'), () async => _resident.toList());
      expect(where(router), '/resident');

      router.go('/residents');                     // no per-route guard of its own: only the form-code guard stops it
      await t.pump();
      await t.pump(const Duration(milliseconds: 100));
      expect(where(router), '/resident');
      expect(find.text(routeDeniedMessage), findsOneWidget);
    });

    testWidgets('a Resident who types another role\'s dashboard stays on their own', (t) async {
      final router = await boot(t, user('Resident'), () async => _resident.toList());
      router.go('/admin');
      await t.pump();
      await t.pump(const Duration(milliseconds: 100));
      expect(where(router), '/resident');
    });

    testWidgets('a Committee Chairman is turned away from Users', (t) async {
      final router = await boot(t, user('Committee Chairman'), () async => _committee.toList());
      expect(where(router), '/committee');
      router.go('/users');
      await t.pump();
      await t.pump(const Duration(milliseconds: 100));
      expect(where(router), '/committee');
      expect(find.text(routeDeniedMessage), findsOneWidget);
    });

    testWidgets('until the grants have loaded nothing is blocked; once loaded, the screen is re-checked', (t) async {
      final gate = Completer<List<String>>();
      final router = await boot(t, user('Resident'), () => gate.future);
      expect(where(router), '/resident');

      router.go('/residents');                     // grants still loading: the guard does not decide
      await t.pump();
      expect(where(router), '/residents');
      t.takeException();                           // the real list screen cannot build without the API client in a test

      gate.complete(_resident.toList());           // the codes arrive: this person is moved off the screen
      await t.pump();
      await t.pump(const Duration(milliseconds: 100));
      t.takeException();                           // (the list screen's build error again, as above)
      expect(where(router), '/resident');
    });

    testWidgets('when a different person signs in, the previous person\'s grants are not used for them', (t) async {
      final adminGate = Completer<List<String>>();
      final container = ProviderContainer(overrides: [
        authProvider.overrideWith((ref) => _SignedIn(ref, user('Resident'))),
        myFormCodesProvider.overrideWith((ref) {
          final u = ref.watch(currentUserProvider);
          return u?.id == 'u-Society Admin' ? adminGate.future : Future.value(_resident.toList());
        }),
        staffRepositoryProvider.overrideWithValue(staffRepo()),
      ]);
      addTearDown(container.dispose);
      final router = container.read(appRouterProvider);
      t.view.physicalSize = const Size(420, 2400);
      t.view.devicePixelRatio = 1.0;
      addTearDown(t.view.resetPhysicalSize);
      addTearDown(t.view.resetDevicePixelRatio);
      await t.pumpWidget(UncontrolledProviderScope(
        container: container,
        child: MaterialApp.router(theme: AppTheme.lightTheme, routerConfig: router),
      ));
      await t.pump();
      await t.pump(const Duration(milliseconds: 100));
      expect(where(router), '/resident');

      // The resident signs out and an administrator signs in on the same device. Their codes are still loading.
      container.read(authProvider.notifier).state = AuthAuthenticated(user('Society Admin'));
      await t.pump();
      await t.pump(const Duration(milliseconds: 100));
      expect(where(router), '/admin');

      router.go('/users');                         // the resident's codes (no "users_roles") must not apply to the admin
      await t.pump();
      t.takeException();
      expect(where(router), '/users');
    });
  });
}

class _SignedIn extends AuthNotifier {
  _SignedIn(Ref ref, UserEntity user) : super(AuthRepository(remote: AuthRemoteDataSource(dio: Dio())), ref) {
    state = AuthAuthenticated(user);
  }
}
