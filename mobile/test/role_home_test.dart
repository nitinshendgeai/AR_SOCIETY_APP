import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ar_society_app/core/router/app_router.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/auth/domain/entities/user_entity.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/features/staff/presentation/providers/staff_providers.dart';
import 'package:ar_society_app/features/staff/presentation/screens/staff_home_screen.dart';
import 'package:ar_society_app/features/users/presentation/providers/user_providers.dart';
import 'package:ar_society_app/features/dashboard/role_dashboards.dart';

UserEntity _u(List<String> roles, {String? societyId = 's1', List<String>? services}) => UserEntity(
      id: 'u1', email: 'u@example.com', fullName: 'Test User', roles: roles, societyId: societyId, enabledServices: services);

void main() {
  // Every role the backend seeds (backend/app/core/rbac_seed.py), and where its holder lands after sign-in.
  group('userRoleHome: every canonical role lands on its intended home', () {
    const expected = <String, String>{
      'Platform Admin': AppRoutes.platformHome,
      'Society Admin': AppRoutes.adminHome,
      'Committee Chairman': AppRoutes.committeeHome,
      'Committee Secretary': AppRoutes.committeeHome,
      'Committee Treasurer': AppRoutes.committeeHome,
      'Committee Member': AppRoutes.committeeHome,
      'Manager': AppRoutes.managerHome,
      'Security Supervisor': AppRoutes.securityHome,       // runs the gate: was sent to the generic supervisor page
      'Housekeeping Supervisor': AppRoutes.supervisorHome,
      'Technical Supervisor': AppRoutes.supervisorHome,
      'Security Staff': AppRoutes.staffHome,
      'Housekeeping Staff': AppRoutes.staffHome,
      'Technical Staff': AppRoutes.staffHome,
      'Gym Trainer': AppRoutes.staffHome,
      'Resident': AppRoutes.residentHome,
      'Tenant': AppRoutes.residentHome,
    };
    expected.forEach((role, home) {
      test(role, () => expect(userRoleHome(_u([role])), home));
    });

    test('a custom role named like "Security" reaches the Security dashboard', () {
      expect(userRoleHome(_u(['Security'])), AppRoutes.securityHome);
    });

    test('every canonical role is covered by the table above', () {
      // A new role added to the backend seed must be given a home here on purpose.
      expect(expected.length, 16);
    });

    test('admin wins over any other role the person holds', () {
      expect(userRoleHome(_u(['Security Supervisor', 'Society Admin'])), AppRoutes.adminHome);
      expect(userRoleHome(_u(['Resident', 'Committee Member'])), AppRoutes.committeeHome);
    });

    test('each landing page is a real route', () {
      for (final home in expected.values) {
        expect(home, startsWith('/'));
      }
    });
  });

  group('Security Staff reach the gate from their Staff Portal', () {
    Widget app(UserEntity user) => ProviderScope(
          overrides: [
            currentUserProvider.overrideWithValue(user),
            myFormCodesProvider.overrideWith((ref) async => const []),
            currentStaffProvider.overrideWith((ref) async => null),
          ],
          child: MaterialApp(
            theme: AppTheme.lightTheme,
            // The test font is wider than the app's; scale it down so tiles are judged on layout.
            builder: (context, child) => MediaQuery(
              data: MediaQuery.of(context).copyWith(textScaler: const TextScaler.linear(0.75)),
              child: child!,
            ),
            home: const StaffHomeScreen(),
          ),
        );

    void tall(WidgetTester t) {
      t.view.physicalSize = const Size(420, 2400);
      t.view.devicePixelRatio = 1.0;
      addTearDown(t.view.resetPhysicalSize);
      addTearDown(t.view.resetDevicePixelRatio);
    }

    testWidgets('Visitor Log and Vehicle Gate are offered to Security Staff', (t) async {
      tall(t);
      await t.pumpWidget(app(_u(['Security Staff'])));
      await t.pump();
      expect(find.text('Visitor Log'), findsOneWidget);
      expect(find.text('Vehicle Gate'), findsOneWidget);
    });

    testWidgets('a service the platform owner switched off is not offered', (t) async {
      tall(t);
      await t.pumpWidget(app(_u(['Security Staff'], services: const ['staff'])));
      await t.pump();
      expect(find.text('Visitor Log'), findsNothing);
      expect(find.text('Vehicle Gate'), findsNothing);
    });

    testWidgets('other staff do not get gate tiles', (t) async {
      tall(t);
      await t.pumpWidget(app(_u(['Housekeeping Staff'])));
      await t.pump();
      expect(find.text('Visitor Log'), findsNothing);
      expect(find.text('Vehicle Gate'), findsNothing);
    });
  });

  group('Security dashboard carries the supervisor\'s team shortcuts', () {
    Widget app(UserEntity user) => ProviderScope(
          overrides: [
            currentUserProvider.overrideWithValue(user),
            myFormCodesProvider.overrideWith((ref) async => const []),
          ],
          child: MaterialApp(theme: AppTheme.lightTheme, home: const SecurityDashboardScreen()),
        );

    testWidgets('a Security Supervisor sees My Team, a custom Security role does not', (t) async {
      t.view.physicalSize = const Size(420, 2800);
      t.view.devicePixelRatio = 1.0;
      addTearDown(t.view.resetPhysicalSize);
      addTearDown(t.view.resetDevicePixelRatio);

      await t.pumpWidget(app(_u(['Security Supervisor'])));
      await t.pump(const Duration(seconds: 2));
      expect(find.text('My Team'), findsWidgets);
      expect(find.text('Assign Duty'), findsOneWidget);

      await t.pumpWidget(app(_u(['Security'])));
      await t.pump(const Duration(seconds: 2));
      expect(find.text('Assign Duty'), findsNothing);
    });
  });
}
