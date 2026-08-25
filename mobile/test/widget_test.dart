import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ar_society_app/features/auth/domain/entities/user_entity.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/features/dashboard/role_dashboards.dart';
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

  // Backend RBAC is unaffected and remains authoritative — these tests only
  // confirm the drawer no longer shows links a role's own permissions can
  // never use (docs/RBAC_MATRIX.md), per the M1.9-R2 "drawer not role-scoped"
  // known gap.
  group('Role-filtered drawer', () {
    Future<void> openDrawer(WidgetTester tester, Widget screen, UserEntity user) async {
      await tester.pumpWidget(_wrapWithUser(screen, user));
      await tester.pump();
      await tester.tap(find.byIcon(Icons.menu_rounded));
      await tester.pumpAndSettle();
    }

    // AdminDashboardScreen pulls in several live-data providers (staff list,
    // society info, open-complaints count) that would need their own fake
    // repository overrides to render in isolation — the two role-exclusion
    // cases below already exercise the exact same _DashboardShell filtering
    // logic those extra roles share, so that mocking cost isn't repeated here.

    testWidgets('Resident only sees Visitors and Complaints, not admin/master links', (tester) async {
      await openDrawer(tester, const ResidentDashboardScreen(), _makeUser(role: 'Resident'));

      expect(find.text('Complaints'), findsOneWidget);
      expect(find.text('Residents'), findsNothing);
      expect(find.text('Tenants'), findsNothing);
      expect(find.text('Users & Roles'), findsNothing);
      expect(find.text('Society Settings'), findsNothing);
      expect(find.text('Setup Wizard'), findsNothing);
      expect(find.text('Staff'), findsNothing);
    });

    testWidgets('Security does not see Users & Roles or Society Settings', (tester) async {
      await openDrawer(tester, const SecurityDashboardScreen(), _makeUser(role: 'Security'));

      expect(find.text('Complaints'), findsOneWidget);
      expect(find.text('Users & Roles'), findsNothing);
      expect(find.text('Society Settings'), findsNothing);
      expect(find.text('Residents'), findsNothing);
    });
  });
}
