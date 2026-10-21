import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/auth/domain/entities/user_entity.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/features/complaint/presentation/providers/complaint_providers.dart';
import 'package:ar_society_app/features/dashboard/admin_overview.dart';
import 'package:ar_society_app/features/dashboard/gate_summary.dart';
import 'package:ar_society_app/features/dashboard/role_dashboards.dart';
import 'package:ar_society_app/features/maintenance_billing/presentation/providers/maintenance_billing_providers.dart';
import 'package:ar_society_app/features/platform/data/platform_api.dart';
import 'package:ar_society_app/features/platform/presentation/providers/platform_providers.dart';
import 'package:ar_society_app/features/platform/presentation/screens/platform_console_screen.dart';
import 'package:ar_society_app/features/staff/data/datasources/staff_remote_datasource.dart';
import 'package:ar_society_app/features/staff/data/repositories/staff_repository.dart';
import 'package:ar_society_app/features/staff/domain/entities/staff_entities.dart';
import 'package:ar_society_app/features/staff/presentation/providers/staff_providers.dart';
import 'package:ar_society_app/features/users/presentation/providers/user_providers.dart';
import 'package:ar_society_app/features/visitor/domain/entities/visitor_entities.dart';
import 'package:ar_society_app/features/visitor/presentation/providers/visitor_providers.dart';

/// The rule under test: a number on a dashboard comes from the server. While the request is loading the card
/// says so, and if it failed the card says that and offers a retry. It is never drawn as 0 - a real 0 is still shown.

const _retryNote = 'Could not load. Tap to retry';

StaffRepository _repo() => StaffRepository(ds: StaffRemoteDataSource(dio: Dio()));

class _FakeApproval extends ApprovalNotifier {
  int loads = 0;
  _FakeApproval(ApprovalState first) : super(_repo()) {
    state = first;
  }
  @override
  Future<void> load(String societyId, {String? department}) async => loads++;
}

class _FakeStaffList extends StaffListNotifier {
  _FakeStaffList() : super(_repo()) {
    state = StaffListLoading();
  }
  @override
  Future<void> load(String societyId, {String? department}) async {}
}

UserEntity _user(String role, {String? societyId = 's1'}) => UserEntity(
      id: 'u1',
      email: 'u@example.com',
      fullName: 'Test User',
      roles: [role],
      societyId: societyId,
      // the manager checklist card is left out: it would call the API
      enabledServices: const ['staff', 'complaints', 'visitors'],
    );

Widget _app(Widget screen, UserEntity user, List<Override> overrides) => ProviderScope(
      overrides: [
        currentUserProvider.overrideWithValue(user),
        myFormCodesProvider.overrideWith((ref) async => const []),
        staffRepositoryProvider.overrideWithValue(_repo()),
        ...overrides,
      ],
      child: MaterialApp(
        theme: AppTheme.lightTheme,
        // The test font is wider and taller than the app's; scale it down so tiles are judged on layout.
        builder: (context, child) => MediaQuery(
          data: MediaQuery.of(context).copyWith(textScaler: const TextScaler.linear(0.75)),
          child: child!,
        ),
        home: screen,
      ),
    );

void _tall(WidgetTester t) {
  t.view.physicalSize = const Size(420, 3200);
  t.view.devicePixelRatio = 1.0;
  addTearDown(t.view.resetPhysicalSize);
  addTearDown(t.view.resetDevicePixelRatio);
}

Future<void> _settle(WidgetTester t) async {
  await t.pump();
  await t.pump(const Duration(milliseconds: 50));
  await t.pump(const Duration(seconds: 2));      // lets the staggered section reveal finish
}

void main() {
  group('Resident dashboard', () {
    testWidgets('complaints and visitors that failed to load are not shown as 0', (t) async {
      _tall(t);
      await t.pumpWidget(_app(const ResidentDashboardScreen(), _user('Resident'), [
        myOpenComplaintsCountProvider.overrideWith((ref) async => throw Exception('offline')),
        pendingVisitorApprovalsProvider.overrideWith((ref) => Stream<List<VisitorEntity>>.error(Exception('offline'))),
      ]));
      await _settle(t);

      expect(find.text('Open Complaints'), findsOneWidget);
      expect(find.text('Visitors Waiting'), findsOneWidget);
      expect(find.text('0'), findsNothing);
      expect(find.text(_retryNote), findsNWidgets(2));
      expect(find.text('Could not check. Open Approvals'), findsOneWidget);
    });

    testWidgets('a genuine zero is still shown as 0', (t) async {
      _tall(t);
      await t.pumpWidget(_app(const ResidentDashboardScreen(), _user('Resident'), [
        myOpenComplaintsCountProvider.overrideWith((ref) async => 0),
        pendingVisitorApprovalsProvider.overrideWith((ref) => Stream.value(const <VisitorEntity>[])),
      ]));
      await _settle(t);

      expect(find.text('0'), findsNWidgets(2));        // complaints and visitors waiting
      expect(find.text(_retryNote), findsNothing);
      expect(find.text('No one waiting'), findsOneWidget);
    });

    testWidgets('tapping a failed card asks the server again', (t) async {
      _tall(t);
      var calls = 0;
      await t.pumpWidget(_app(const ResidentDashboardScreen(), _user('Resident'), [
        myOpenComplaintsCountProvider.overrideWith((ref) async {
          calls++;
          if (calls == 1) throw Exception('offline');
          return 4;
        }),
        pendingVisitorApprovalsProvider.overrideWith((ref) => Stream.value(const <VisitorEntity>[])),
      ]));
      await _settle(t);
      expect(find.text(_retryNote), findsOneWidget);

      await t.tap(find.text(_retryNote));
      await _settle(t);
      expect(calls, 2);
      expect(find.text('4'), findsOneWidget);
      expect(find.text(_retryNote), findsNothing);
    });
  });

  group('Manager dashboard', () {
    List<Override> failing(_FakeApproval approval) => [
          approvalProvider.overrideWith((ref) => approval),
          staffListProvider.overrideWith((ref) => _FakeStaffList()),
          openComplaintsCountProvider('s1').overrideWith((ref) async => throw Exception('offline')),
          societyDutiesProvider('s1').overrideWith((ref) async => throw Exception('offline')),
          attendanceSummaryProvider('s1').overrideWith((ref) async => throw Exception('offline')),
          billingCyclesProvider('s1').overrideWith((ref) async => const []),
        ];

    testWidgets('every staff and complaint figure that failed says so instead of showing 0', (t) async {
      _tall(t);
      await t.pumpWidget(_app(const ManagerDashboardScreen(), _user('Manager'),
          failing(_FakeApproval(ApprovalError('offline')))));
      await _settle(t);

      // pending check-in, punch-out, absent, late, open complaints, duty queue
      expect(find.text(_retryNote), findsNWidgets(6));
      expect(find.text('0'), findsNothing);
      expect(find.text('--'), findsNWidgets(7));      // the six above and Total Staff (still loading)
    });

    testWidgets('tapping a failed approvals card reloads the approvals', (t) async {
      _tall(t);
      final approval = _FakeApproval(ApprovalError('offline'));
      await t.pumpWidget(_app(const ManagerDashboardScreen(), _user('Manager'), failing(approval)));
      await _settle(t);

      await t.tap(find.text(_retryNote).first);
      await t.pump();
      expect(approval.loads, 1);
    });

    testWidgets('real zeros are shown as 0', (t) async {
      _tall(t);
      await t.pumpWidget(_app(const ManagerDashboardScreen(), _user('Manager'), [
        approvalProvider.overrideWith((ref) => _FakeApproval(ApprovalLoaded(pendingCheckin: const [], pendingCheckout: const []))),
        staffListProvider.overrideWith((ref) => _FakeStaffList()),
        openComplaintsCountProvider('s1').overrideWith((ref) async => 0),
        societyDutiesProvider('s1').overrideWith((ref) async => const <DutyEntity>[]),
        attendanceSummaryProvider('s1').overrideWith((ref) async => {'absent': 0, 'late': 0}),
        billingCyclesProvider('s1').overrideWith((ref) async => const []),
      ]));
      await _settle(t);

      expect(find.text(_retryNote), findsNothing);
      expect(find.text('0'), findsNWidgets(6));
    });
  });

  group('Supervisor dashboard', () {
    testWidgets('duties and attendance that failed are not shown as 0', (t) async {
      _tall(t);
      await t.pumpWidget(_app(const SupervisorDashboardScreen(), _user('Security Supervisor'), [
        approvalProvider.overrideWith((ref) => _FakeApproval(ApprovalError('offline'))),
        staffListProvider.overrideWith((ref) => _FakeStaffList()),
        societyDutiesProvider('s1').overrideWith((ref) async => throw Exception('offline')),
        attendanceSummaryProvider('s1').overrideWith((ref) async => throw Exception('offline')),
      ]));
      await _settle(t);

      expect(find.text(_retryNote), findsNWidgets(6));
      expect(find.text('0'), findsNothing);
    });
  });

  group('Platform console', () {
    testWidgets('platform figures that failed are not shown as 0', (t) async {
      _tall(t);
      await t.pumpWidget(_app(const PlatformConsoleScreen(), _user('Platform Admin', societyId: null), [
        platformStatsProvider.overrideWith((ref) async => throw Exception('offline')),
        platformSocietiesProvider.overrideWith((ref, q) async => const <PlatformSociety>[]),
        platformActivityProvider.overrideWith((ref) async => const <PlatformEvent>[]),
      ]));
      await _settle(t);

      expect(find.text('Societies'), findsWidgets);
      expect(find.text('0'), findsNothing);
      expect(find.text(_retryNote), findsNWidgets(4));
    });

    testWidgets('platform figures that loaded are shown, including a real 0', (t) async {
      _tall(t);
      await t.pumpWidget(_app(const PlatformConsoleScreen(), _user('Platform Admin', societyId: null), [
        platformStatsProvider.overrideWith((ref) async => PlatformStats.fromJson({
              'total_societies': 3, 'trial_societies': 1, 'active_societies': 2, 'suspended_societies': 0,
              'expired_societies': 0, 'expiring_soon': 0, 'trial_ended_not_marked': 0, 'total_users': 9, 'total_flats': 40,
            })),
        platformSocietiesProvider.overrideWith((ref, q) async => const <PlatformSociety>[]),
        platformActivityProvider.overrideWith((ref) async => const <PlatformEvent>[]),
      ]));
      await _settle(t);

      expect(find.text(_retryNote), findsNothing);
      expect(find.text('3'), findsOneWidget);
      expect(find.text('0'), findsOneWidget);          // suspended
    });
  });

  group('Security dashboard', () {
    GateSummary summary(Map<String, dynamic> j) => GateSummary.fromJson(j);

    testWidgets('shows the server\'s figures for today, and nothing invented', (t) async {
      _tall(t);
      await t.pumpWidget(_app(const SecurityDashboardScreen(), _user('Security Staff'), [
        gateSummaryProvider('s1').overrideWith((ref) async => summary({
              'today': {'visitors_today': 12, 'checked_in_today': 9, 'visitors_inside': 4}, 'errors': <String>[]})),
      ]));
      await _settle(t);

      expect(find.text('12'), findsOneWidget);
      expect(find.text('9'), findsOneWidget);
      expect(find.text('4'), findsOneWidget);
      expect(find.text('Visitors Today'), findsOneWidget);
      expect(find.text('Let In Today'), findsOneWidget);
      expect(find.text('Inside Now'), findsOneWidget);
      // the old placeholders are gone
      expect(find.text('Parking Entries'), findsNothing);
      expect(find.text('Duty Status'), findsNothing);
      expect(find.text('Check-ins'), findsNothing);
    });

    testWidgets('a quiet gate is a real 0', (t) async {
      _tall(t);
      await t.pumpWidget(_app(const SecurityDashboardScreen(), _user('Security Staff'), [
        gateSummaryProvider('s1').overrideWith((ref) async => summary({
              'today': {'visitors_today': 0, 'checked_in_today': 0, 'visitors_inside': 0}, 'errors': <String>[]})),
      ]));
      await _settle(t);

      expect(find.text('0'), findsNWidgets(3));
      expect(find.text(_retryNote), findsNothing);
    });

    testWidgets('a request that failed says so and offers a retry, never 0', (t) async {
      _tall(t);
      var calls = 0;
      await t.pumpWidget(_app(const SecurityDashboardScreen(), _user('Security Staff'), [
        gateSummaryProvider('s1').overrideWith((ref) async {
          calls++;
          if (calls == 1) throw Exception('offline');
          return summary({'today': {'visitors_today': 5, 'checked_in_today': 3, 'visitors_inside': 1}, 'errors': <String>[]});
        }),
      ]));
      await _settle(t);
      expect(find.text(_retryNote), findsNWidgets(3));
      expect(find.text('0'), findsNothing);

      await t.tap(find.text(_retryNote).first);
      await _settle(t);
      expect(calls, 2);
      expect(find.text('5'), findsOneWidget);
      expect(find.text(_retryNote), findsNothing);
    });

    testWidgets('a figure the server could not work out is unavailable, not 0', (t) async {
      _tall(t);
      await t.pumpWidget(_app(const SecurityDashboardScreen(), _user('Security Staff'), [
        gateSummaryProvider('s1').overrideWith((ref) async => summary({'today': null, 'errors': ['today']})),
      ]));
      await _settle(t);

      expect(find.text(_retryNote), findsNWidgets(3));
      expect(find.text('0'), findsNothing);
    });

    testWidgets('with the Visitors service switched off the gate figures are not shown at all', (t) async {
      _tall(t);
      final user = const UserEntity(id: 'u1', email: 'g@x.in', fullName: 'G', roles: ['Security Staff'],
          societyId: 's1', enabledServices: ['staff']);
      await t.pumpWidget(_app(const SecurityDashboardScreen(), user, const []));
      await _settle(t);

      expect(find.text('Visitors Today'), findsNothing);
      expect(find.text(_retryNote), findsNothing);
    });

    test('a reply without figures reads as unavailable, not zero', () {
      final g = GateSummary.fromJson({'today': null, 'errors': <String>[]});
      expect(g.visitorsToday, isNull);
      expect(g.failed, isFalse);
    });
  });

  group('Committee dashboard', () {
    Map<String, dynamic> overview({List<String> errors = const []}) => {
          'as_of': '2026-10-09',
          'collection': {
            'cycle_name': 'October 2026', 'due_date': '2026-10-20', 'billed': '58500.00', 'collected': '13025.00',
            'outstanding': '45475.00', 'percent': 22, 'bills': 5, 'paid_bills': 1, 'overdue_bills': 0,
            'trend': <Map<String, dynamic>>[],
          },
          'money': {'cash': '1000', 'bank': '5000', 'members_dues': '200', 'creditors': '0', 'fy': '2026-27',
            'fy_income': '9000', 'fy_expense': '4000'},
          'occupancy': {'flats': 5, 'occupied': 3, 'vacant': 2, 'residents': 4},
          'today': {'visitors_today': 1, 'visitors_inside': 1},
          'attention': [
            {'key': 'complaints_open', 'count': 2, 'severity': 'info'},
          ],
          'errors': errors,
        };

    List<Override> loaded({List<String> errors = const []}) => [
          staffListProvider.overrideWith((ref) => _FakeStaffList()),
          dashboardOverviewProvider('s1').overrideWith((ref) async => DashboardOverview.fromJson(overview(errors: errors))),
        ];

    testWidgets('shows the same server figures as the admin overview', (t) async {
      _tall(t);
      await t.pumpWidget(_app(const CommitteeDashboardScreen(), _user('Committee Treasurer'), loaded()));
      await _settle(t);

      expect(find.text('Maintenance collection'), findsOneWidget);
      expect(find.text('₹13,025'), findsOneWidget);
      expect(find.text('2 open complaints'), findsOneWidget);
      expect(find.text('3 of 5 flats occupied'), findsOneWidget);
    });

    testWidgets('has no static status text and no figure worked out in the app', (t) async {
      _tall(t);
      await t.pumpWidget(_app(const CommitteeDashboardScreen(), _user('Committee Secretary'), loaded()));
      await _settle(t);

      expect(find.text('Staff module operational'), findsNothing);
      expect(find.text('See Staff → Approvals'), findsNothing);
      expect(find.text('Maintenance Dues'), findsNothing);
    });

    testWidgets('is titled for the role held, not always Chairman', (t) async {
      _tall(t);
      for (final (role, title) in [
        ('Committee Chairman', 'Chairman Dashboard'),
        ('Committee Secretary', 'Secretary Dashboard'),
        ('Committee Treasurer', 'Treasurer Dashboard'),
        ('Committee Member', 'Committee Dashboard'),
      ]) {
        await t.pumpWidget(_app(const CommitteeDashboardScreen(), _user(role), loaded()));
        await _settle(t);
        expect(find.text(title), findsOneWidget, reason: role);
        expect(find.text('Chairman Dashboard'), role == 'Committee Chairman' ? findsOneWidget : findsNothing, reason: role);
      }
    });

    testWidgets('a block the server failed on is reported, not drawn as all clear', (t) async {
      _tall(t);
      await t.pumpWidget(_app(const CommitteeDashboardScreen(), _user('Committee Member'),
          loaded(errors: ['attention'])));
      await _settle(t);

      expect(find.textContaining('All clear'), findsNothing);
      expect(find.text('This could not be loaded just now.'), findsOneWidget);
    });
  });
}
