import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ar_society_app/features/auth/domain/entities/user_entity.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/features/dashboard/role_dashboards.dart';
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

Widget _wrapWithUser(Widget child, UserEntity user) {
  return ProviderScope(
    overrides: [
      // Override only the derived provider — avoids needing real platform channels
      currentUserProvider.overrideWithValue(user),
      // AdminDashboardScreen/CommitteeDashboardScreen unconditionally watch
      // staffListProvider/approvalProvider, both of which eagerly read
      // staffRepositoryProvider. Its default StaffRepository() reaches for
      // ApiClient.instance, which is never initialized in a widget test
      // (that only happens in main.dart) and throws synchronously,
      // crashing the whole build. Route it through a repository built on a
      // plain Dio() instead — nothing calls .load() without a societyId, so
      // this is purely there to dodge the crash, not to fake real data.
      staffRepositoryProvider.overrideWithValue(StaffRepository(ds: StaffRemoteDataSource(dio: Dio()))),
    ],
    child: MaterialApp(
      theme: AppTheme.lightTheme,
      home: child,
    ),
  );
}

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

  // ── Role-aware drawer navigation (certification gap: the shared drawer
  // previously showed every admin-oriented item to every role) ────────────

  group('Role-aware navigation drawer', () {
    Future<void> openDrawer(WidgetTester tester) async {
      await tester.tap(find.byTooltip('Open menu'));
      await tester.pumpAndSettle();
    }

    // Several menu labels (Complaints, Visitors, Staff, ...) are also shown
    // as "Quick Actions" chips on the dashboard body itself, so a plain
    // find.text() would double-count once the drawer overlays the body.
    // Scope the presence checks to inside the open Drawer specifically.
    Finder inDrawer(String label) =>
        find.descendant(of: find.byType(Drawer), matching: find.text(label));

    // The drawer's menu ListView only lazily builds items within its
    // viewport — for a role with enough items that the list doesn't fit
    // on screen without scrolling (Admin/Committee, once Parking
    // Management joined the menu), a plain findsOneWidget on a later item
    // sees nothing built yet. Scroll forward until each label appears;
    // since callers check labels in the order they appear top-to-bottom,
    // scrolling only ever moves forward and never has to re-find an
    // earlier, now off-screen, item.
    Future<void> expectVisibleInDrawer(WidgetTester tester, String label) async {
      await tester.dragUntilVisible(
        inDrawer(label),
        find.descendant(of: find.byType(Drawer), matching: find.byType(ListView)),
        const Offset(0, -60),
      );
      expect(inDrawer(label), findsOneWidget, reason: '$label should be visible in the drawer');
    }

    testWidgets('Society Admin sees the full administrative menu', (tester) async {
      await tester.pumpWidget(_wrapWithUser(const AdminDashboardScreen(), _makeUser(role: 'Society Admin')));
      await tester.pump();
      await openDrawer(tester);

      for (final label in [
        'Residents', 'Tenants', 'Users & Roles', 'Society Settings',
        'Visitors', 'Complaints', 'Staff', 'Parking Management', 'Setup Wizard',
      ]) {
        await expectVisibleInDrawer(tester, label);
      }
    });

    testWidgets('Committee sees admin-committee items but not Users & Roles', (tester) async {
      await tester.pumpWidget(_wrapWithUser(const CommitteeDashboardScreen(), _makeUser(role: 'Committee')));
      await tester.pump();
      await openDrawer(tester);

      for (final label in [
        'Residents', 'Tenants', 'Society Settings', 'Visitors', 'Complaints',
        'Staff', 'Parking Management', 'Setup Wizard',
      ]) {
        await expectVisibleInDrawer(tester, label);
      }
      expect(inDrawer('Users & Roles'), findsNothing);
    });

    testWidgets('Security Staff sees operational items only, no admin configuration screens', (tester) async {
      await tester.pumpWidget(_wrapWithUser(const SecurityDashboardScreen(), _makeUser(role: 'Security')));
      await tester.pump();
      await openDrawer(tester);

      expect(inDrawer('Visitors'), findsOneWidget);
      expect(inDrawer('Complaints'), findsOneWidget);
      expect(inDrawer('Staff'), findsOneWidget);
      for (final label in ['Residents', 'Tenants', 'Users & Roles', 'Society Settings', 'Setup Wizard']) {
        expect(inDrawer(label), findsNothing, reason: '$label must not be visible to Security');
      }
    });

    testWidgets('Resident sees only resident-facing navigation', (tester) async {
      await tester.pumpWidget(_wrapWithUser(const ResidentDashboardScreen(), _makeUser(role: 'Resident')));
      await tester.pump();
      await openDrawer(tester);

      expect(inDrawer('Visitors'), findsOneWidget);
      expect(inDrawer('Complaints'), findsOneWidget);
      for (final label in ['Residents', 'Tenants', 'Users & Roles', 'Society Settings', 'Staff', 'Setup Wizard']) {
        expect(inDrawer(label), findsNothing, reason: '$label must not be visible to Resident');
      }
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
}
