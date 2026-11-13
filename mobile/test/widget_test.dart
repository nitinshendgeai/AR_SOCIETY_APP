import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ar_society_app/features/auth/domain/entities/user_entity.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/features/dashboard/resident_dues_card.dart';
import 'package:ar_society_app/features/dashboard/role_dashboards.dart';
import 'package:ar_society_app/features/staff/data/datasources/staff_remote_datasource.dart';
import 'package:ar_society_app/features/staff/data/repositories/staff_repository.dart';
import 'package:ar_society_app/features/staff/presentation/providers/staff_providers.dart';
import 'package:ar_society_app/features/users/presentation/providers/user_providers.dart';
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

/// [formCodes] simulates what GET /roles/forms/mine would return for the
/// user's role — the drawer now renders purely from this server-driven
/// list (see myFormCodesProvider), not from role-name checks, so tests
/// supply it directly rather than relying on UserEntity's role heuristics.
Widget _wrapWithUser(Widget child, UserEntity user, {List<String> formCodes = const []}) {
  return ProviderScope(
    overrides: [
      // Override only the derived provider — avoids needing real platform channels
      currentUserProvider.overrideWithValue(user),
      myFormCodesProvider.overrideWith((ref) async => formCodes),
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

// Mirrors backend/app/core/rbac_seed.py's default FORM_ROLE_GRANTS for the
// role personas these tests exercise.
const _residentFormCodes = ['visitors', 'complaints', 'edit_my_info', 'my_bills'];

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

  // (The role-aware menu tests live in role_menu_visibility_test.dart: the dashboards no longer have their own drawer.)

  group('ResidentDashboardScreen', () {
    testWidgets('renders greeting and module grid', (tester) async {
      final user = _makeUser(role: 'Resident');
      // The quick actions sit below the first screen; a taller screen makes the list build them.
      tester.view.physicalSize = const Size(800, 2000);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);

      await tester.pumpWidget(_wrapWithUser(const ResidentDashboardScreen(), user, formCodes: _residentFormCodes));
      await tester.pump();
      await tester.pump();

      expect(find.text('Resident Dashboard'), findsOneWidget);
      expect(find.text('Open Complaints'), findsOneWidget);
      expect(find.text('Visitors Waiting'), findsOneWidget);
      // What is owed is shown once, on the dues card at the top, not again as a summary card, a chip and a row.
      expect(find.byType(ResidentDuesCard), findsOneWidget);
      expect(find.text('Bills Due'), findsNothing);
      expect(find.text('My Bills'), findsNothing);
      expect(find.text('Recent updates'), findsNothing);
      expect(find.text('My Flat'), findsOneWidget);
      expect(find.text('Edit My Info'), findsOneWidget);
    });

    testWidgets('shows the society services as tiles, only the ones the resident is granted', (tester) async {
      tester.view.physicalSize = const Size(800, 2000);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);

      await tester.pumpWidget(_wrapWithUser(const ResidentDashboardScreen(), _makeUser(role: 'Resident'),
          formCodes: const ['visitors', 'complaints', 'notices', 'amenities', 'my_bills']));
      await tester.pump();
      await tester.pump();

      expect(find.text('Society services'), findsOneWidget);
      expect(find.text('Invite guest'), findsOneWidget);
      expect(find.text('Raise complaint'), findsOneWidget);
      expect(find.text('Pay bills'), findsNothing);          // paying is the dues card's button, not a second chip
      expect(find.byType(ResidentDuesCard), findsOneWidget);
      for (final label in ['Visitors', 'Complaints', 'Notices', 'Amenities']) {
        expect(find.text(label), findsOneWidget, reason: label);
      }
      for (final label in ['Parcels', 'Daily help', 'Meetings', 'Polls', 'Documents', 'Certificates']) {
        expect(find.text(label), findsNothing, reason: '$label is not granted');
      }
    });

    testWidgets('a Tenant is not offered My Bills or Edit My Info (they work from a resident record)', (tester) async {
      // A Tenant is granted the member screens only; the bills and the profile edit would be empty or fail for them.
      // The quick actions sit below the first screen; a taller screen makes the list build them.
      tester.view.physicalSize = const Size(800, 2000);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      await tester.pumpWidget(_wrapWithUser(const ResidentDashboardScreen(), _makeUser(role: 'Tenant'),
          formCodes: const ['visitors', 'complaints']));
      await tester.pump();
      await tester.pump();

      expect(find.text('Open Complaints'), findsOneWidget);
      expect(find.text('My Flat'), findsOneWidget);
      expect(find.text('Bills Due'), findsNothing);
      expect(find.text('My Bills'), findsNothing);
      expect(find.text('Edit My Info'), findsNothing);
      expect(find.text('Maintenance'), findsNothing);
      expect(find.text('Pay bills'), findsNothing);
      expect(find.byType(ResidentDuesCard), findsNothing);   // no bills grant, so no dues card either
    });
  });

  group('SecurityDashboardScreen', () {
    testWidgets('renders gate operation modules', (tester) async {
      final user = _makeUser(role: 'Security');
      // The summary tiles are taller than before (room for a "could not load" note), so the quick actions sit lower;
      // use a taller screen so the list builds them.
      tester.view.physicalSize = const Size(800, 1600);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);

      await tester.pumpWidget(_wrapWithUser(const SecurityDashboardScreen(), user));
      await tester.pump();

      expect(find.text('Security Supervisor'), findsWidgets);
      expect(find.text('Log Visitor'), findsOneWidget);
      expect(find.text('Check In'), findsOneWidget);
      expect(find.text('Check Out'), findsOneWidget);
    });
  });
}
