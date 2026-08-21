import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ar_society_app/features/auth/domain/entities/user_entity.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/features/dashboard/role_dashboards.dart';
import 'package:ar_society_app/features/onboarding/presentation/providers/trial_status_provider.dart';
import 'package:ar_society_app/features/staff/data/datasources/staff_remote_datasource.dart';
import 'package:ar_society_app/features/staff/data/repositories/staff_repository.dart';
import 'package:ar_society_app/features/staff/presentation/providers/staff_providers.dart';
import 'package:ar_society_app/features/visitor/domain/entities/visitor_entities.dart';
import 'package:ar_society_app/features/complaint/domain/entities/complaint_entities.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';

// ── Helpers ───────────────────────────────────────────────────────────────────

UserEntity _makeUser({String role = 'Resident'}) => UserEntity(
      id: 'user-1',
      email: 'test@example.com',
      fullName: 'Test User',
      roles: [role],
    );

Widget _wrapWithUser(Widget child, UserEntity user, {List<Override> overrides = const []}) {
  return ProviderScope(
    overrides: [
      // Override only the derived provider — avoids needing real platform channels
      currentUserProvider.overrideWithValue(user),
      ...overrides,
    ],
    child: MaterialApp(
      theme: AppTheme.lightTheme,
      home: child,
    ),
  );
}

/// Admin/Committee/Security dashboards unconditionally watch staffListProvider
/// and approvalProvider (unlike the societyId-guarded providers), which
/// otherwise construct a real StaffRepository backed by ApiClient's
/// process-wide `late Dio` singleton — never initialized outside a real app
/// boot, so it throws LateInitializationError in a bare widget test. Route
/// them through a standalone Dio() instead, mirroring the pattern
/// resident_master_test.dart already uses for the same reason.
List<Override> _dashboardScreenOverrides() => [
      societyInfoProvider.overrideWith((ref) async => null),
      staffRepositoryProvider.overrideWithValue(
        StaffRepository(ds: StaffRemoteDataSource(dio: Dio())),
      ),
    ];

// ── Entity unit tests ─────────────────────────────────────────────────────────

void main() {
  group('UserEntity', () {
    test('primaryRole returns Admin for admin user', () {
      final user = _makeUser(role: 'Admin');
      expect(user.primaryRole, equals('Admin'));
      expect(user.isAdmin, isTrue);
    });

    test('primaryRole returns Resident by default', () {
      final user = _makeUser(role: 'Resident');
      expect(user.isResident, isTrue);
      expect(user.isAdmin, isFalse);
    });

    test('mustChangePassword defaults to false', () {
      final user = _makeUser();
      expect(user.mustChangePassword, isFalse);
    });

    test('copyWith preserves unchanged fields', () {
      final user = _makeUser();
      final updated = user.copyWith(fullName: 'New Name');
      expect(updated.email, equals(user.email));
      expect(updated.fullName, equals('New Name'));
    });
  });

  group('VisitorEntity enums', () {
    test('VisitorType.fromString handles all values', () {
      expect(VisitorType.fromString('guest'), equals(VisitorType.guest));
      expect(VisitorType.fromString('delivery'), equals(VisitorType.delivery));
      expect(VisitorType.fromString('cab'), equals(VisitorType.cab));
      expect(VisitorType.fromString('unknown'), equals(VisitorType.guest));
    });

    test('VisitorStatus.fromString handles all values', () {
      expect(VisitorStatus.fromString('pending'), equals(VisitorStatus.pending));
      expect(VisitorStatus.fromString('checked_in'), equals(VisitorStatus.checkedIn));
      expect(VisitorStatus.fromString('checked_out'), equals(VisitorStatus.checkedOut));
    });

    test('VisitorEntity.canCheckIn is true only when approved', () {
      final approved = VisitorEntity(
        id: 'v1',
        societyId: 's1',
        name: 'John',
        mobile: '9999999999',
        visitorType: VisitorType.guest,
        status: VisitorStatus.approved,
        createdAt: DateTime.now(),
        logs: const [],
      );
      expect(approved.canCheckIn, isTrue);
      expect(approved.canCheckOut, isFalse);
      expect(approved.isPending, isFalse);

      final checkedIn = VisitorEntity(
        id: 'v2',
        societyId: 's1',
        name: 'Jane',
        mobile: '9999999998',
        visitorType: VisitorType.delivery,
        status: VisitorStatus.checkedIn,
        createdAt: DateTime.now(),
        logs: const [],
      );
      expect(checkedIn.canCheckIn, isFalse);
      expect(checkedIn.canCheckOut, isTrue);
    });
  });

  group('ComplaintEntity enums', () {
    test('ComplaintStatus.fromString handles all values', () {
      expect(ComplaintStatus.fromString('open'), equals(ComplaintStatus.open));
      expect(ComplaintStatus.fromString('in_progress'), equals(ComplaintStatus.inProgress));
      expect(ComplaintStatus.fromString('resolved'), equals(ComplaintStatus.resolved));
      expect(ComplaintStatus.fromString('rejected'), equals(ComplaintStatus.rejected));
    });

    test('ComplaintPriority.fromString handles all values', () {
      expect(ComplaintPriority.fromString('low'), equals(ComplaintPriority.low));
      expect(ComplaintPriority.fromString('high'), equals(ComplaintPriority.high));
      expect(ComplaintPriority.fromString('critical'), equals(ComplaintPriority.critical));
      expect(ComplaintPriority.fromString('unknown'), equals(ComplaintPriority.medium));
    });

    test('ComplaintCategory.fromString handles all values', () {
      expect(ComplaintCategory.fromString('plumbing'), equals(ComplaintCategory.plumbing));
      expect(ComplaintCategory.fromString('electrical'), equals(ComplaintCategory.electrical));
      expect(ComplaintCategory.fromString('unknown'), equals(ComplaintCategory.other));
    });

    test('ComplaintEntity.isActive reflects status', () {
      final base = ComplaintEntity(
        id: 'c1',
        complaintNumber: 'C-001',
        title: 'Test',
        description: 'Test desc',
        category: ComplaintCategory.plumbing,
        priority: ComplaintPriority.medium,
        status: ComplaintStatus.open,
        societyId: 's1',
        raisedBy: 'user1',
        createdAt: DateTime.now(),
      );
      expect(base.isActive, isTrue);
      final closed = ComplaintEntity(
        id: 'c2',
        complaintNumber: 'C-002',
        title: 'Test',
        description: 'Test desc',
        category: ComplaintCategory.electrical,
        priority: ComplaintPriority.low,
        status: ComplaintStatus.closed,
        societyId: 's1',
        raisedBy: 'user1',
        createdAt: DateTime.now(),
      );
      expect(closed.isActive, isFalse);
    });
  });

  group('ResidentDashboardScreen', () {
    testWidgets('renders greeting and module grid', (tester) async {
      final user = _makeUser(role: 'Resident');

      await tester.pumpWidget(_wrapWithUser(const ResidentDashboardScreen(), user));
      await tester.pump();

      expect(find.text('Resident Dashboard'), findsOneWidget);
      expect(find.text('Complaints'), findsOneWidget);
      expect(find.text('My Visitors'), findsOneWidget);
      expect(find.text('Pending Approvals'), findsOneWidget);
    });
  });

  group('SecurityDashboardScreen', () {
    testWidgets('renders gate operation modules', (tester) async {
      final user = _makeUser(role: 'Security');

      await tester.pumpWidget(_wrapWithUser(const SecurityDashboardScreen(), user));
      await tester.pump();

      expect(find.text('Security Dashboard'), findsOneWidget);
      expect(find.text('Log Visitor'), findsOneWidget);
      expect(find.text('Check In'), findsOneWidget);
      expect(find.text('Check Out'), findsOneWidget);
    });
  });

  // ── Role-aware drawer navigation (M1.9-R3 Gap H) ────────────────────────
  //
  // A hidden item here is a UX/navigation-hygiene layer only — every route it
  // links to independently re-enforces its own backend permission, so this
  // suite verifies *visibility*, never treats it as a stand-in for
  // authorization. Society Admin has a real login fixture; Committee,
  // Security and Resident are exercised with a synthetic UserEntity the same
  // way the two tests above already do (no backend fixture needed for a pure
  // Flutter visibility check). Platform Admin has no supported provisioning
  // mechanism in this app (see M1.9-R2 Gap I) — NOT TESTED, no valid fixture.

  Future<void> openDrawer(WidgetTester tester) async {
    await tester.tap(find.byIcon(Icons.menu_rounded));
    await tester.pumpAndSettle();
  }

  // Several menu labels ("Staff", "Complaints", "Residents", ...) also appear
  // as dashboard-body summary-card labels, so a bare find.text() is ambiguous
  // once the drawer is open. Scope every assertion to the Drawer itself.
  Finder inDrawer(String label) =>
      find.descendant(of: find.byType(Drawer), matching: find.text(label));

  group('Role-aware drawer navigation', () {
    testWidgets('Society Admin sees every management item', (tester) async {
      final user = _makeUser(role: 'Society Admin');
      await tester.pumpWidget(_wrapWithUser(const AdminDashboardScreen(), user,
          overrides: _dashboardScreenOverrides()));
      await tester.pumpAndSettle();
      await openDrawer(tester);

      for (final label in [
        'Residents', 'Tenants', 'Users & Roles', 'Society Settings',
        'Visitors', 'Complaints', 'Staff', 'Setup Wizard',
      ]) {
        expect(inDrawer(label), findsOneWidget, reason: '$label must be visible to Society Admin');
      }
    });

    testWidgets('Committee sees Society Settings and Setup Wizard but not Users & Roles',
        (tester) async {
      final user = _makeUser(role: 'Committee Member');
      await tester.pumpWidget(_wrapWithUser(const CommitteeDashboardScreen(), user,
          overrides: _dashboardScreenOverrides()));
      await tester.pumpAndSettle();
      await openDrawer(tester);

      expect(inDrawer('Society Settings'), findsOneWidget,
          reason: 'PATCH /societies/{id} accepts Committee (require_admin_committee)');
      expect(inDrawer('Setup Wizard'), findsOneWidget,
          reason: 'setup-progress PATCH accepts Committee (admin_or_committee)');
      expect(inDrawer('Users & Roles'), findsNothing,
          reason: 'every /users/* route requires Platform/Society Admin only');
      expect(inDrawer('Residents'), findsOneWidget);
      expect(inDrawer('Staff'), findsOneWidget);
    });

    testWidgets('Resident sees read-broad items but not admin-only management screens',
        (tester) async {
      final user = _makeUser(role: 'Resident');
      await tester.pumpWidget(_wrapWithUser(const ResidentDashboardScreen(), user,
          overrides: _dashboardScreenOverrides()));
      await tester.pumpAndSettle();
      await openDrawer(tester);

      // read-broad by design (GET is get_current_user, screen self-gates canEdit)
      expect(inDrawer('Residents'), findsOneWidget);
      expect(inDrawer('Tenants'), findsOneWidget);
      expect(inDrawer('Visitors'), findsOneWidget);
      expect(inDrawer('Complaints'), findsOneWidget);
      // admin/committee-only management screens
      expect(inDrawer('Users & Roles'), findsNothing);
      expect(inDrawer('Society Settings'), findsNothing);
      expect(inDrawer('Setup Wizard'), findsNothing);
      // not a staff member — staffHome has nothing to show them
      expect(inDrawer('Staff'), findsNothing);
    });

    testWidgets('Security sees the same restricted set as Resident (no admin/committee role)',
        (tester) async {
      final user = _makeUser(role: 'Security');
      await tester.pumpWidget(_wrapWithUser(const SecurityDashboardScreen(), user,
          overrides: _dashboardScreenOverrides()));
      await tester.pumpAndSettle();
      await openDrawer(tester);

      expect(inDrawer('Residents'), findsOneWidget);
      expect(inDrawer('Visitors'), findsOneWidget);
      expect(inDrawer('Users & Roles'), findsNothing);
      expect(inDrawer('Society Settings'), findsNothing);
      expect(inDrawer('Setup Wizard'), findsNothing);
      // Security is a staff-tier role, unlike Resident — Staff stays visible
      expect(inDrawer('Staff'), findsOneWidget);
    });
  });
}
