import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/parking/data/vehicle_report_api.dart';
import 'package:ar_society_app/features/parking/presentation/screens/vehicle_report_tab.dart';
import 'package:ar_society_app/features/society_structure/data/models/structure_models.dart';
import 'package:ar_society_app/features/society_structure/presentation/providers/structure_providers.dart';

class _FakeWings extends WingsNotifier {
  @override
  Future<List<WingModel>> build() async => const [WingModel(id: 'w1', name: 'Wing A', societyId: 's1')];
}

class _FakeFlats extends FlatsByWingNotifier {
  @override
  Future<List<FlatModel>> build(String wingId) async => const [
        FlatModel(id: 'f101', flatNumber: '101', floor: 1, wingId: 'w1'),
        FlatModel(id: 'f102', flatNumber: '102', floor: 1, wingId: 'w1'),
      ];
}

Map<String, dynamic> _report(String month) => {
      'month': month,
      'month_label': month == '2026-11' ? 'November 2026' : 'October 2026',
      'as_on': '2026-11-20',
      'timezone': 'Asia/Kolkata',
      'wing': null,
      'flat': null,
      'vehicles': {
        'summary': {
          'total': 3, 'with_parking': 1, 'without_parking': 2, 'by_type': {'Car': 2, 'Motorcycle': 1}, 'by_wing': {'A': 2, 'B': 1},
          'insurance_expired': 1, 'insurance_soon': 1, 'insurance_missing': 0, 'flats_without_vehicle': 1,
        },
        'rows': [
          {
            'vehicle_number': 'MH12AA1111', 'type': 'Car', 'make_model': 'Honda City', 'color': '', 'flat': 'A 101', 'flat_id': 'f101',
            'wing': 'A', 'owner': 'Asha', 'category': 'Owner / resident', 'has_parking': true, 'parking_slot': 'P1',
            'insurance_expiry': '2026-11-01', 'insurance': 'expired',
          }
        ],
        'row_count': 3,
        'flats_without_vehicle': ['A 102'],
      },
      'parking': {
        'summary': {'slots': 3, 'allotted': 1, 'free': 1, 'blocked': 1, 'flats_short': 1, 'ending_soon': 1},
        'zones': [
          {'zone': 'Basement', 'code': 'B1', 'total': 3, 'allotted': 1, 'free': 1, 'reserved': 0, 'blocked': 1}
        ],
        'flats_short': [
          {'flat': 'A 101', 'vehicles': 2, 'with_parking': 1, 'without_parking': 1}
        ],
        'flats_short_count': 1,
        'ending_soon': [
          {'slot': 'P1', 'flat': 'A 101', 'vehicle': 'MH12AA1111', 'ends': '2026-12-05'}
        ],
        'ending_soon_count': 1,
      },
      'violations': {
        'summary': {
          'total': 3, 'open': 2, 'resolved': 1, 'by_type': {'Wrong slot': 1}, 'fines_charged': 500, 'fines_on_bills': 0,
          'fines_taken_off': 0, 'fines_not_charged': 0,
        },
        'rows': [
          {
            'date': '2026-11-10', 'vehicle_number': 'MH12BB2222', 'type': 'Wrong slot', 'flat': 'A 101', 'slot': 'P1',
            'description': 'In another slot', 'fine': 500, 'fine_status': 'On the next bill', 'fine_status_key': 'active', 'resolved': false,
          }
        ],
        'row_count': 3,
        'repeat_offenders': [
          {'vehicle_number': 'MH12BB2222', 'count': 2, 'flat': 'A 101'}
        ],
      },
      'gate': {
        'summary': {
          'total': 4, 'entries': 3, 'exits': 1, 'residents': 2, 'visitors': 1, 'unknown': 1, 'not_allowed': 2, 'visitor_inside': 1,
          'visitor_visits': 2, 'visitor_overstayed': 1, 'visitor_avg_stay_minutes': 30,
        },
        'rows': [
          {
            'time': '2026-11-10T09:00:00Z', 'vehicle_number': 'MH12BB2222', 'direction': 'Entry', 'who': 'resident', 'flat': 'A 101',
            'method': 'Guard', 'allowed': true, 'notes': '',
          }
        ],
        'row_count': 4,
        'visitors_inside': [
          {
            'vehicle_number': 'MH14VV0001', 'host_flat': 'A 101', 'since': '2026-11-10T07:00:00Z', 'expected_hours': 1,
            'overstayed': true, 'minutes': 90, 'slot': '',
          }
        ],
      },
    };

Widget _wrap(List<Map<String, dynamic>> asked) {
  final dio = Dio();
  dio.interceptors.add(InterceptorsWrapper(onRequest: (o, h) {
    asked.add(Map<String, dynamic>.from(o.queryParameters));
    h.resolve(Response(requestOptions: o, statusCode: 200, data: _report((o.queryParameters['month'] as String?) ?? '2026-11')));
  }));
  return ProviderScope(
    overrides: [
      wingsProvider.overrideWith(() => _FakeWings()),
      flatsByWingProvider.overrideWith(() => _FakeFlats()),
      vehicleReportApiProvider.overrideWithValue(VehicleReportApi(dio: dio)),
    ],
    child: MaterialApp(theme: AppTheme.lightTheme, home: const Scaffold(body: VehicleReportTab(societyId: 's1'))),
  );
}

void main() {
  void phone(WidgetTester t) {
    t.view.physicalSize = const Size(420, 2400);
    t.view.devicePixelRatio = 1.0;
    addTearDown(t.view.resetPhysicalSize);
    addTearDown(t.view.resetDevicePixelRatio);
  }

  Future<void> choose(WidgetTester t, Key dropdown, String text) async {
    await t.tap(find.byKey(dropdown));
    await t.pumpAndSettle();
    await t.tap(find.text(text).last);
    await t.pumpAndSettle();
  }

  testWidgets('the four parts of the report, one section at a time', (t) async {
    phone(t);
    final asked = <Map<String, dynamic>>[];
    await t.pumpWidget(_wrap(asked));
    await t.pumpAndSettle();

    // Vehicles
    expect(asked, [<String, dynamic>{}]);
    expect(find.text('MH12AA1111 · Car'), findsOneWidget);
    expect(find.text('Honda City · A 101 · Asha'), findsOneWidget);
    expect(find.text('Parking P1'), findsOneWidget);
    expect(find.text('Insurance expired'), findsOneWidget);
    expect(find.text('Showing the first 1 of 3. "Print or download" has them all.'), findsOneWidget);
    expect(find.text('Occupied flats with no vehicle on record (1)'), findsOneWidget);
    expect(find.text('A 102'), findsOneWidget);

    // Parking
    await t.tap(find.byKey(const Key('vr-section-1')));
    await t.pumpAndSettle();
    expect(find.text('Basement (B1)'), findsOneWidget);
    expect(find.text('3 slots · 1 allotted · 1 free'), findsOneWidget);
    expect(find.text('Flats with more vehicles than parking (1)'), findsOneWidget);
    expect(find.text('1 without'), findsOneWidget);
    expect(find.text('Slot P1 · A 101'), findsOneWidget);

    // Violations, for a month
    await t.tap(find.byKey(const Key('vr-section-2')));
    await t.pumpAndSettle();
    expect(find.text('November 2026'), findsOneWidget);
    expect(find.text('MH12BB2222 · Wrong slot'), findsOneWidget);
    expect(find.text('10 Nov 2026 · A 101 · In another slot'), findsOneWidget);
    expect(find.textContaining('Repeat offenders: MH12BB2222 ×2'), findsOneWidget);
    expect(find.text('Showing the first 1 of 3. "Print or download" has them all.'), findsOneWidget);

    // Gate
    await t.tap(find.byKey(const Key('vr-section-3')));
    await t.pumpAndSettle();
    expect(find.text('MH12BB2222 · Entry'), findsOneWidget);
    expect(find.text('Residents 2 · Visitors 1 · Unknown 1'), findsOneWidget);
    expect(find.text('Visitor parking: 2 visits · average stay 30 min · 1 stayed past the time given'), findsOneWidget);
    expect(find.text('Visitor vehicles inside now (1)'), findsOneWidget);
    expect(find.text('Overstayed'), findsOneWidget);
    expect(find.text('Not allowed'), findsWidgets);
  });

  testWidgets('the month arrows ask for another month, and only the violations and the gate follow the month', (t) async {
    phone(t);
    final asked = <Map<String, dynamic>>[];
    await t.pumpWidget(_wrap(asked));
    await t.pumpAndSettle();
    expect(find.byKey(const Key('vr-prev')), findsNothing);           // vehicles and parking are as on today
    expect(find.text('As on today'), findsOneWidget);
    await t.tap(find.byKey(const Key('vr-section-2')));
    await t.pumpAndSettle();
    expect(find.text('As on today'), findsNothing);
    await t.tap(find.byKey(const Key('vr-prev')));
    await t.pumpAndSettle();
    expect(asked.last['month'], '2026-10');
    expect(find.text('October 2026'), findsOneWidget);
  });

  testWidgets('a wing and then a flat narrow the report; Clear filters brings it all back', (t) async {
    phone(t);
    final asked = <Map<String, dynamic>>[];
    await t.pumpWidget(_wrap(asked));
    await t.pumpAndSettle();
    expect(t.widget<DropdownButtonFormField<String?>>(find.byKey(const Key('vr-flat'))).onChanged, isNull); // a flat needs its wing
    await choose(t, const Key('vr-wing'), 'Wing A');
    expect(asked.last, {'wing_id': 'w1'});
    await choose(t, const Key('vr-flat'), 'Flat 102');
    expect(asked.last, {'wing_id': 'w1', 'flat_id': 'f102'});
    await t.tap(find.byKey(const Key('vr-clear')));
    await t.pumpAndSettle();
    expect(asked.last, <String, dynamic>{});
  });

  testWidgets('Print or download offers the PDF and the Excel file', (t) async {
    phone(t);
    await t.pumpWidget(_wrap([]));
    await t.pumpAndSettle();
    await t.tap(find.byKey(const Key('vehicle-report-download')));
    await t.pumpAndSettle();
    for (final k in ['pdf-open', 'pdf-share', 'xlsx-download', 'xlsx-share']) {
      expect(find.byKey(Key('vr-$k')), findsOneWidget, reason: k);
    }
  });
}
