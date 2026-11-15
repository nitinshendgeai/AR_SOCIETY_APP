import 'dart:io';
import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:ar_society_app/core/router/app_router.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/auth/domain/entities/user_entity.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/features/gym/data/gym_api.dart';
import 'package:ar_society_app/features/gym/presentation/screens/gym_check_in_screen.dart';
import 'package:ar_society_app/features/gym/presentation/screens/gym_desk_screen.dart';
import 'package:ar_society_app/features/gym/presentation/screens/gym_report_screen.dart';
import 'package:ar_society_app/features/society_structure/data/models/structure_models.dart';
import 'package:ar_society_app/features/society_structure/presentation/providers/structure_providers.dart';

const _trainer = UserEntity(id: 't', email: 't@x.c', fullName: 'Trainer', roles: ['Gym Trainer'], societyId: 's1', termsAccepted: true);

GymVisitRow _row(String id, String name, {String flat = 'A-101', int? minutes = 25, DateTime? at}) =>
    GymVisitRow(visitId: id, name: name, flatLabel: flat, checkedInAt: at ?? DateTime.now().subtract(const Duration(minutes: 25)), minutesInside: minutes);

GymMember _member(String id, String name, String type, {bool inside = false}) =>
    GymMember(residentId: id, name: name, memberType: type, inside: inside, visitId: inside ? 'v-$id' : null);

GymReport _report({String period = 'week', DateTime? from, DateTime? to, String label = 'Week of 09 Mar 2026 to 15 Mar 2026',
    int visits = 4, int notOut = 0, List<GymReportMember>? members}) {
  final first = from ?? DateTime(2026, 3, 9);
  return GymReport(
    period: period, from: first, to: to ?? first.add(const Duration(days: 6)), label: label, visits: visits, uniqueMembers: 2,
    uniqueFlats: 1, averageMinutes: 60, notCheckedOut: notOut,
    days: [for (var i = 0; i < 7; i++) GymDay(date: first.add(Duration(days: i)), visits: i == 0 ? 2 : (i == 2 ? 1 : 0), uniqueMembers: 1)],
    members: members ??
        const [
          GymReportMember(name: 'Asha Rao', flatLabel: 'A-101', visits: 3, totalMinutes: 150),
          GymReportMember(name: 'Vik Rao', flatLabel: 'A-101', visits: 1, totalMinutes: 30),
        ],
  );
}

/// A gym server that remembers what it was asked.
class FakeGym extends GymApi {
  FakeGym({GymLive? live}) : liveData = live ?? const GymLive(insideNow: 0, checkedInToday: 0, checkedOutToday: 0, inside: [], earlierOpen: []), super(dio: Dio());
  final GymLive liveData;
  Map<String, GymFlatMembers> flats = {};
  final outs = <List<String>>[];
  var outAll = 0;
  final checkIns = <({String flat, List<String> ids})>[];
  final reports = <({String period, DateTime? on})>[];
  GymReport Function(String period, DateTime? on)? reportFor;
  Object? failCheckIn;
  Object? failLive;
  var liveCalls = 0;

  @override
  Future<GymLive> live() async {
    liveCalls++;
    if (failLive != null) throw failLive!;
    return liveData;
  }

  @override
  Future<GymFlatMembers> flatMembers(String flatId) async => flats[flatId]!;

  @override
  Future<({int checkedIn, List<String> alreadyInside})> checkIn(String flatId, List<String> residentIds) async {
    if (failCheckIn != null) throw failCheckIn!;
    checkIns.add((flat: flatId, ids: residentIds));
    return (checkedIn: residentIds.length, alreadyInside: <String>[]);
  }

  @override
  Future<int> checkOut(List<String> visitIds) async {
    outs.add(visitIds);
    return visitIds.length;
  }

  @override
  Future<int> checkOutAll() async => ++outAll;

  @override
  Future<GymReport> report(String period, {DateTime? on}) async {
    reports.add((period: period, on: on));
    return (reportFor ?? (p, o) => _report(period: p))(period, on);
  }

  @override
  Future<Uint8List> reportPdf(String period, {DateTime? on}) async => Uint8List.fromList([0x25, 0x50, 0x44, 0x46]);
}

class _Flats extends FlatsBySocietyNotifier {
  @override
  Future<List<FlatModel>> build() async => [
        FlatModel(id: 'f1', flatNumber: '101', wingId: 'wa', wingName: 'A', occupancyStatus: 'occupied'),
        FlatModel(id: 'f2', flatNumber: '202', wingId: 'wb', wingName: 'B', occupancyStatus: 'occupied'),
      ];
}

Widget _app(FakeGym api) {
  final router = GoRouter(initialLocation: AppRoutes.gym, routes: [
    GoRoute(path: AppRoutes.gym, builder: (_, __) => const GymDeskScreen()),
    GoRoute(path: AppRoutes.gymCheckIn, builder: (_, __) => const GymCheckInScreen()),
    GoRoute(path: AppRoutes.gymReport, builder: (_, __) => const GymReportScreen()),
  ]);
  return ProviderScope(
    overrides: [
      currentUserProvider.overrideWithValue(_trainer),
      gymApiProvider.overrideWithValue(api),
      flatsBySocietyProvider.overrideWith(() => _Flats()),
    ],
    child: MaterialApp.router(theme: AppTheme.lightTheme, routerConfig: router),
  );
}

void _phone(WidgetTester t) {
  t.view.physicalSize = const Size(900, 2200);
  t.view.devicePixelRatio = 2;
  addTearDown(t.view.resetPhysicalSize);
  addTearDown(t.view.resetDevicePixelRatio);
}

Future<void> _pickFlat(WidgetTester t, String wing, String flat) async {
  await t.tap(find.byKey(const ValueKey('filter-wing')));
  await t.pumpAndSettle();
  await t.tap(find.text(wing).last);
  await t.pumpAndSettle();
  await t.tap(find.byKey(ValueKey('filter-flat-${wing == 'A' ? 'wa' : 'wb'}')));
  await t.pumpAndSettle();
  await t.tap(find.text(flat).last);
  await t.pumpAndSettle();
}

/// The app's own font; without it the test draws every letter as a wide square and labels overflow that never would.
Future<void> _loadInter() async {
  final loader = FontLoader('Inter')
    ..addFont(Future.value(ByteData.sublistView(File('assets/fonts/Inter-Variable.ttf').readAsBytesSync())));
  await loader.load();
}

void main() {
  setUpAll(_loadInter);

  group('the desk', () {
    testWidgets('shows how many are inside and how many came and left today, and who is inside', (t) async {
      _phone(t);
      final api = FakeGym(live: GymLive(insideNow: 2, checkedInToday: 5, checkedOutToday: 3,
          inside: [_row('v1', 'Asha Rao', minutes: 25), _row('v2', 'Vik Rao', flat: 'B-202', minutes: 75)], earlierOpen: const []));
      await t.pumpWidget(_app(api));
      await t.pumpAndSettle();
      expect(find.descendant(of: find.byKey(const Key('gym-inside')), matching: find.text('2')), findsOneWidget);
      expect(find.descendant(of: find.byKey(const Key('gym-came')), matching: find.text('5')), findsOneWidget);
      expect(find.descendant(of: find.byKey(const Key('gym-left')), matching: find.text('3')), findsOneWidget);
      expect(find.text('Asha Rao'), findsOneWidget);
      expect(find.textContaining('A-101 · Since'), findsOneWidget);
      expect(find.textContaining('25 min'), findsOneWidget);
      expect(find.textContaining('1 h 15 min'), findsOneWidget);
      expect(find.text('Tick out'), findsNWidgets(2));
    });

    testWidgets('with nobody inside it says so and offers no check-everyone-out', (t) async {
      _phone(t);
      await t.pumpWidget(_app(FakeGym()));
      await t.pumpAndSettle();
      expect(find.text('Nobody is in the gym.'), findsOneWidget);
      expect(find.byKey(const Key('gym-check-out-all')), findsNothing);
    });

    testWidgets('ticking one person out asks for exactly that visit and reloads the desk', (t) async {
      _phone(t);
      final api = FakeGym(live: GymLive(insideNow: 1, checkedInToday: 1, checkedOutToday: 0, inside: [_row('v1', 'Asha Rao')], earlierOpen: const []));
      await t.pumpWidget(_app(api));
      await t.pumpAndSettle();
      final before = api.liveCalls;
      await t.tap(find.byKey(const Key('gym-out-v1')));
      await t.pumpAndSettle();
      expect(api.outs, [
        ['v1']
      ]);
      expect(api.liveCalls, greaterThan(before));
      expect(find.textContaining('Asha Rao checked out'), findsOneWidget);
    });

    testWidgets('check everyone out asks first, and only then ticks everyone out', (t) async {
      _phone(t);
      final api = FakeGym(live: GymLive(insideNow: 2, checkedInToday: 2, checkedOutToday: 0,
          inside: [_row('v1', 'Asha Rao'), _row('v2', 'Vik Rao')], earlierOpen: const []));
      await t.pumpWidget(_app(api));
      await t.pumpAndSettle();
      await t.tap(find.byKey(const Key('gym-check-out-all')));
      await t.pumpAndSettle();
      expect(find.text('Check everyone out?'), findsOneWidget);
      expect(find.text('2 still in the gym will be ticked out now.'), findsOneWidget);
      await t.tap(find.text('Cancel'));
      await t.pumpAndSettle();
      expect(api.outAll, 0);                                              // cancelled: nothing happened
      await t.tap(find.byKey(const Key('gym-check-out-all')));
      await t.pumpAndSettle();
      await t.tap(find.widgetWithText(FilledButton, 'Check everyone out'));
      await t.pumpAndSettle();
      expect(api.outAll, 1);
    });

    testWidgets('visits left open from an earlier day are listed apart, with Close', (t) async {
      _phone(t);
      final api = FakeGym(live: GymLive(insideNow: 0, checkedInToday: 0, checkedOutToday: 0, inside: const [],
          earlierOpen: [_row('old1', 'Tia Rao', at: DateTime.now().subtract(const Duration(days: 2)))]));
      await t.pumpWidget(_app(api));
      await t.pumpAndSettle();
      expect(find.text('Not ticked out on an earlier day'), findsOneWidget);
      expect(find.text('Nobody is in the gym.'), findsOneWidget);          // she is not counted as inside
      await t.tap(find.byKey(const Key('gym-out-old1')));
      await t.pumpAndSettle();
      expect(api.outs, [
        ['old1']
      ]);
    });

    testWidgets('a failed load says so and offers Try again', (t) async {
      _phone(t);
      final api = FakeGym()..failLive = DioException(requestOptions: RequestOptions(path: '/x'));
      await t.pumpWidget(_app(api));
      await t.pumpAndSettle();
      expect(find.text('Try again'), findsOneWidget);
    });

    testWidgets('the two buttons lead to the check-in and the report', (t) async {
      _phone(t);
      await t.pumpWidget(_app(FakeGym()));
      await t.pumpAndSettle();
      await t.tap(find.byKey(const Key('gym-check-in')));
      await t.pumpAndSettle();
      expect(find.text('Choose a wing and a flat to see its members.'), findsOneWidget);
      t.state<NavigatorState>(find.byType(Navigator).last).pop();
      await t.pumpAndSettle();
      await t.tap(find.byKey(const Key('gym-reports')));
      await t.pumpAndSettle();
      expect(find.byKey(const Key('gym-period')), findsOneWidget);
    });
  });

  group('checking members in', () {
    GymFlatMembers a101({bool ashaInside = false}) => GymFlatMembers(flatId: 'f1', flatLabel: 'A-101', letToTenants: false, members: [
          _member('r1', 'Asha Rao', 'owner', inside: ashaInside),
          _member('r2', 'Vik Rao', 'family'),
          _member('r3', 'Tia Rao', 'dependent'),
        ]);

    Future<FakeGym> open(WidgetTester t, {Map<String, GymFlatMembers>? flats}) async {
      _phone(t);
      final api = FakeGym()..flats = flats ?? {'f1': a101()};
      await t.pumpWidget(_app(api));
      await t.pumpAndSettle();
      await t.tap(find.byKey(const Key('gym-check-in')));
      await t.pumpAndSettle();
      return api;
    }

    testWidgets('nothing is listed until a wing and a flat are chosen; then the flat\'s members appear with how they are related', (t) async {
      await open(t);
      expect(find.text('Choose wing'), findsOneWidget);
      expect(find.byKey(const Key('gym-member-r1')), findsNothing);
      await _pickFlat(t, 'A', '101');
      expect(find.text('Asha Rao'), findsOneWidget);
      expect(find.text('Owner'), findsOneWidget);
      expect(find.text('Family'), findsOneWidget);
      expect(find.text('Dependent'), findsOneWidget);
      expect(find.text('Tick who is here'), findsOneWidget);       // the button waits for a tick
    });

    testWidgets('ticking two members checks exactly those two in', (t) async {
      final api = await open(t);
      await _pickFlat(t, 'A', '101');
      await t.tap(find.byKey(const Key('gym-member-r1')));
      await t.tap(find.byKey(const Key('gym-member-r3')));
      await t.pumpAndSettle();
      expect(find.text('Check in 2'), findsOneWidget);
      await t.tap(find.text('Check in 2'));
      await t.pumpAndSettle();
      expect(api.checkIns.length, 1);
      expect(api.checkIns.single.flat, 'f1');
      expect(api.checkIns.single.ids.toSet(), {'r1', 'r3'});                  // Vik was not ticked
      expect(find.text('2 checked in'), findsOneWidget);
      expect(find.byKey(const Key('gym-check-in')), findsOneWidget);          // back on the desk
    });

    testWidgets('someone already inside is shown as inside and cannot be ticked again', (t) async {
      final api = await open(t, flats: {'f1': a101(ashaInside: true)});
      await _pickFlat(t, 'A', '101');
      expect(find.text('Inside now'), findsOneWidget);
      await t.tap(find.byKey(const Key('gym-member-r1')));
      await t.pumpAndSettle();
      expect(find.text('Tick who is here'), findsOneWidget);     // still nothing ticked
      expect(api.checkIns, isEmpty);
    });

    testWidgets('a flat let to tenants says the gym is for owners and offers nobody', (t) async {
      await open(t, flats: {'f2': const GymFlatMembers(flatId: 'f2', flatLabel: 'B-202', letToTenants: true, members: [])});
      await _pickFlat(t, 'B', '202');
      expect(find.byKey(const Key('gym-no-members')), findsOneWidget);
      expect(find.text('This flat is let to tenants. The gym is for owners and their families.'), findsOneWidget);
      expect(find.textContaining('Not on the list?'), findsNothing);              // no way to "add" someone to a let flat
    });

    testWidgets('someone the resident has asked for but the office has not approved is named, not offered, and the trainer is told what to do', (t) async {
      await open(t, flats: {
        'f1': GymFlatMembers(flatId: 'f1', flatLabel: 'A-101', letToTenants: false, waitingForApproval: const ['Neel Rao', 'Tia Rao'], members: [
          _member('r1', 'Asha Rao', 'owner'),
        ]),
      });
      await _pickFlat(t, 'A', '101');
      expect(find.byKey(const Key('gym-waiting')), findsOneWidget);
      expect(find.text('Waiting for the office to approve: Neel Rao, Tia Rao'), findsOneWidget);
      expect(find.byKey(const Key('gym-member-r1')), findsOneWidget);
      expect(find.byType(CheckboxListTile), findsOneWidget);                       // only the approved member can be ticked
      expect(find.textContaining('Not on the list?'), findsOneWidget);
      expect(find.textContaining('Add family member'), findsOneWidget);
    });

    testWidgets('a flat with nobody listed still says how to get someone on the list', (t) async {
      await open(t, flats: {'f1': const GymFlatMembers(flatId: 'f1', flatLabel: 'A-101', letToTenants: false, members: [])});
      await _pickFlat(t, 'A', '101');
      expect(find.byKey(const Key('gym-no-members')), findsOneWidget);
      expect(find.byKey(const Key('gym-not-listed')), findsOneWidget);
      expect(find.textContaining('Not on the list?'), findsOneWidget);
    });

    testWidgets('choosing another flat clears what was ticked', (t) async {
      final api = await open(t, flats: {
        'f1': a101(),
        'f2': GymFlatMembers(flatId: 'f2', flatLabel: 'B-202', letToTenants: false, members: [_member('r9', 'Bela Shah', 'owner')]),
      });
      await _pickFlat(t, 'A', '101');
      await t.tap(find.byKey(const Key('gym-member-r2')));
      await t.pumpAndSettle();
      expect(find.text('Check in 1'), findsOneWidget);
      await _pickFlat(t, 'B', '202');
      expect(find.text('Bela Shah'), findsOneWidget);
      expect(find.text('Tick who is here'), findsOneWidget);
      expect(api.checkIns, isEmpty);
    });

    testWidgets('if the server refuses, the trainer is told and stays on the screen with the ticks kept', (t) async {
      final api = await open(t);
      api.failCheckIn = DioException(requestOptions: RequestOptions(path: '/x'), type: DioExceptionType.connectionError);
      await _pickFlat(t, 'A', '101');
      await t.tap(find.byKey(const Key('gym-member-r2')));
      await t.pumpAndSettle();
      await t.tap(find.text('Check in 1'));
      await t.pumpAndSettle();
      expect(find.byKey(const Key('gym-member-r2')), findsOneWidget);          // still here
      expect(find.text('Check in 1'), findsOneWidget);                          // the tick is kept
    });
  });

  group('the report', () {
    Future<FakeGym> open(WidgetTester t, {FakeGym? api}) async {
      _phone(t);
      final a = api ?? FakeGym();
      await t.pumpWidget(_app(a));
      await t.pumpAndSettle();
      await t.tap(find.byKey(const Key('gym-reports')));
      await t.pumpAndSettle();
      return a;
    }

    testWidgets('shows the week with its figures, each day and each member', (t) async {
      final api = await open(t);
      expect(api.reports.first.period, 'week');
      expect(find.byKey(const Key('gym-period-label')), findsOneWidget);
      expect(find.text('Week of 09 Mar 2026 to 15 Mar 2026'), findsOneWidget);
      expect(find.text('4'), findsOneWidget);                                   // visits
      expect(find.text('1 h 00 min'), findsOneWidget);                          // average stay
      expect(find.text('Mon 9 Mar'), findsOneWidget);
      expect(find.text('Asha Rao'), findsOneWidget);
      expect(find.text('3 visits'), findsOneWidget);
      expect(find.text('1 visit'), findsOneWidget);
      expect(find.text('Print report'), findsOneWidget);
    });

    testWidgets('Monthly asks for the month; Previous and Next move by a whole period', (t) async {
      final today = DateTime.now();
      final api = FakeGym()..reportFor = (p, on) => _report(period: p, from: DateTime(2026, 3, 1), to: p == 'month' ? DateTime(2026, 3, 31) : DateTime(2026, 3, 7), label: p == 'month' ? 'March 2026' : 'Week');
      await open(t, api: api);
      await t.tap(find.text('Monthly'));
      await t.pumpAndSettle();
      expect(api.reports.last.period, 'month');
      expect(find.text('March 2026'), findsOneWidget);
      await t.tap(find.byKey(const Key('gym-prev')));
      await t.pumpAndSettle();
      final asked = api.reports.last.on!;
      expect((asked.year, asked.month), today.month == 1 ? (today.year - 1, 12) : (today.year, today.month - 1));
      // This fake period ended in the past, so Next is allowed.
      expect(t.widget<IconButton>(find.byKey(const Key('gym-next'))).onPressed, isNotNull);
    });

    testWidgets('Next is off for the period that contains today', (t) async {
      final now = DateTime.now();
      final api = FakeGym()..reportFor = (p, on) => _report(period: p, from: now.subtract(const Duration(days: 2)), to: now.add(const Duration(days: 4)));
      await open(t, api: api);
      expect(t.widget<IconButton>(find.byKey(const Key('gym-next'))).onPressed, isNull);
      expect(t.widget<IconButton>(find.byKey(const Key('gym-prev'))).onPressed, isNotNull);
    });

    testWidgets('visits nobody ticked out are explained; an empty period says nobody came', (t) async {
      final api = FakeGym()..reportFor = (p, on) => _report(period: p, visits: 0, notOut: 3, members: const []);
      await open(t, api: api);
      expect(find.byKey(const Key('gym-not-out-note')), findsOneWidget);
      expect(find.textContaining('3 visits were not ticked out'), findsOneWidget);
      expect(find.byKey(const Key('gym-empty')), findsOneWidget);
    });
  });
}
