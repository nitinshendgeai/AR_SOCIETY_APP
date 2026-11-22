import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:intl/intl.dart';
import 'package:ar_society_app/features/auth/domain/entities/user_entity.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/features/maintenance_billing/data/maintenance_billing_api.dart';
import 'package:ar_society_app/features/maintenance_billing/presentation/providers/maintenance_billing_providers.dart';
import 'package:ar_society_app/features/maintenance_billing/presentation/screens/bill_estimate_screen.dart';

typedef _Call = ({String? month, List<Map<String, dynamic>> changes});

class _FakeBilling extends MaintenanceBillingApi {
  final List<_Call> calls = [];
  _FakeBilling() : super(dio: Dio());

  @override
  Future<BillEstimate> estimateBills(String societyId, {String? month, List<EstimateChange> changes = const []}) async {
    calls.add((month: month, changes: [for (final c in changes) c.toJson()]));
    final up = changes.isNotEmpty; // Service Charges +10%: each flat +100
    return BillEstimate.fromJson({
      'month': month ?? '2030-06',
      'month_label': 'June 2030',
      'adjusted': up,
      'flats_count': 2,
      'total_area_sqft': 1800,
      'elements': [
        {
          'element': 'Water Charges', 'current_total': '3600.00', 'estimate_total': '3600.00', 'change': '0.00',
          'change_pct': '0.00', 'current_per_sqft': '2.00', 'estimate_per_sqft': '2.00', 'adjusted': false,
        },
        {
          'element': 'Service Charges', 'current_total': '2000.00', 'estimate_total': up ? '2200.00' : '2000.00',
          'change': up ? '200.00' : '0.00', 'change_pct': up ? '10.00' : '0.00', 'current_per_sqft': '1.11',
          'estimate_per_sqft': up ? '1.22' : '1.11', 'adjusted': up,
        },
      ],
      'flats': [
        {
          'flat_id': 'f1', 'flat_label': 'A / 101', 'area_sqft': 600,
          'lines': [
            {'element': 'Water Charges', 'current': '1200.00', 'estimate': '1200.00'},
            {'element': 'Service Charges', 'current': '1000.00', 'estimate': up ? '1100.00' : '1000.00'},
          ],
          'tax': '0.00', 'round_off': '0.00', 'current_total': '2200.00', 'estimate_total': up ? '2300.00' : '2200.00',
          'change': up ? '100.00' : '0.00', 'current_per_sqft': '3.67', 'estimate_per_sqft': up ? '3.83' : '3.67',
        },
        {
          'flat_id': 'f2', 'flat_label': 'A / 201', 'area_sqft': 1200,
          'lines': [
            {'element': 'Water Charges', 'current': '2400.00', 'estimate': '2400.00'},
            {'element': 'Service Charges', 'current': '1000.00', 'estimate': up ? '1100.00' : '1000.00'},
          ],
          'tax': '0.00', 'round_off': '0.00', 'current_total': '3400.00', 'estimate_total': up ? '3500.00' : '3400.00',
          'change': up ? '100.00' : '0.00', 'current_per_sqft': '2.83', 'estimate_per_sqft': up ? '2.92' : '2.83',
        },
      ],
      'totals': {
        'current': '5600.00', 'estimate': up ? '5800.00' : '5600.00', 'change': up ? '200.00' : '0.00',
        'current_per_sqft': '3.11', 'estimate_per_sqft': up ? '3.22' : '3.11',
      },
      'notes': ['Arrears, interest and fines are not part of an estimate.'],
    });
  }
}

Widget _app(_FakeBilling api) => ProviderScope(
      overrides: [
        currentUserProvider.overrideWithValue(
            const UserEntity(id: 'u', email: 'u@t.com', fullName: 'U', roles: ['Society Admin'], societyId: 's1')),
        maintenanceBillingApiProvider.overrideWithValue(api),
      ],
      child: const MaterialApp(home: BillEstimateScreen()),
    );

String _total(WidgetTester t) => t.widget<Text>(find.byKey(const ValueKey('estimate-total'))).data!;

void main() {
  void tall(WidgetTester tester) {
    tester.view.physicalSize = const Size(800, 2400);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.reset);
  }

  testWidgets('it opens on next month with every element and every flat, and the rate per sq ft', (tester) async {
    tall(tester);
    final api = _FakeBilling();
    await tester.pumpWidget(_app(api));
    await tester.pumpAndSettle();

    final now = DateTime.now();
    expect(api.calls.single.month, DateFormat('yyyy-MM').format(DateTime(now.year, now.month + 1)));
    expect(api.calls.single.changes, isEmpty);
    expect(find.text('Estimated total for June 2030'), findsOneWidget);
    expect(_total(tester), '₹5,600.00');
    expect(find.textContaining('₹3.11 / sq ft on average'), findsOneWidget);
    expect(find.text('Service Charges'), findsOneWidget);
    expect(find.text('Water Charges'), findsOneWidget);
    expect(find.text('A / 101'), findsOneWidget);
    expect(find.text('A / 201'), findsOneWidget);
    expect(find.textContaining('for the society each month'), findsNothing);   // no what-if yet

    await tester.tap(find.byKey(const ValueKey('estimate-flat-A / 101')));
    await tester.pumpAndSettle();
    expect(find.text('Estimated bill'), findsOneWidget);                // a flat opens to its elements
    expect(find.text('₹1,200.00'), findsWidgets);
  });

  testWidgets('a change to an element asks for it and shows the new bills, the rate and the difference', (tester) async {
    tall(tester);
    final api = _FakeBilling();
    await tester.pumpWidget(_app(api));
    await tester.pumpAndSettle();

    await tester.enterText(find.byKey(const ValueKey('estimate-pct-Service Charges')), '10');
    await tester.tap(find.byKey(const ValueKey('estimate-calc')));
    await tester.pumpAndSettle();
    expect(api.calls.last.changes, [
      {'element': 'Service Charges', 'percent': 10.0}
    ]);
    expect(find.text('Estimated total with your changes'), findsOneWidget);
    expect(_total(tester), '₹5,800.00');
    expect(find.textContaining('₹3.22 / sq ft on average'), findsOneWidget);
    expect(find.textContaining('As it stands: ₹5,600.00'), findsOneWidget);
    expect(find.text('Change: +₹200.00 for the society each month'), findsOneWidget);
    expect(find.text('₹2,300.00'), findsOneWidget);                     // flat A / 101 now
    expect(find.text('+₹100.00'), findsNWidgets(2));                    // and what it went up by, for both flats

    await tester.enterText(find.byKey(const ValueKey('estimate-pct-Water Charges')), '');
    await tester.enterText(find.byKey(const ValueKey('estimate-total-Water Charges')), '4800');
    await tester.tap(find.byKey(const ValueKey('estimate-calc')));
    await tester.pumpAndSettle();
    expect(api.calls.last.changes, unorderedEquals([
      {'element': 'Service Charges', 'percent': 10.0},
      {'element': 'Water Charges', 'target_total': 4800.0},
    ]));

    await tester.tap(find.byKey(const ValueKey('estimate-reset')));
    await tester.pumpAndSettle();
    expect(api.calls.last.changes, isEmpty);                            // reset asks for the figures as they stand
    expect(_total(tester), '₹5,600.00');
    expect(tester.widget<TextField>(find.byKey(const ValueKey('estimate-pct-Service Charges'))).controller!.text, '');
  });

  testWidgets('a figure that is not a number is refused before anything is asked, and the month arrows ask again',
      (tester) async {
    tall(tester);
    final api = _FakeBilling();
    await tester.pumpWidget(_app(api));
    await tester.pumpAndSettle();
    await tester.enterText(find.byKey(const ValueKey('estimate-pct-Service Charges')), '-');
    await tester.tap(find.byKey(const ValueKey('estimate-calc')));
    await tester.pumpAndSettle();
    expect(api.calls, hasLength(1));                                    // only the first load

    await tester.enterText(find.byKey(const ValueKey('estimate-pct-Service Charges')), '');
    final first = api.calls.single.month;
    await tester.tap(find.byKey(const ValueKey('estimate-month-next')));
    await tester.pumpAndSettle();
    expect(api.calls.last.month, isNot(first));
    await tester.tap(find.byKey(const ValueKey('estimate-month-prev')));
    await tester.pumpAndSettle();
    expect(api.calls.last.month, first);
  });

  testWidgets('billing by area: a rate per sq ft, the By area switch, and every element by area at once', (tester) async {
    tall(tester);
    final api = _FakeBilling();
    await tester.pumpWidget(_app(api));
    await tester.pumpAndSettle();

    await tester.enterText(find.byKey(const ValueKey('estimate-rate-Service Charges')), '2.5');
    await tester.tap(find.byKey(const ValueKey('estimate-calc')));
    await tester.pumpAndSettle();
    expect(api.calls.last.changes, [
      {'element': 'Service Charges', 'per_sqft': 2.5}
    ]);

    await tester.enterText(find.byKey(const ValueKey('estimate-rate-Service Charges')), '');
    await tester.enterText(find.byKey(const ValueKey('estimate-pct-Water Charges')), '5');
    await tester.tap(find.byKey(const ValueKey('estimate-area-Water Charges')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const ValueKey('estimate-calc')));
    await tester.pumpAndSettle();
    expect(api.calls.last.changes, [
      {'element': 'Water Charges', 'percent': 5.0, 'by_area': true}
    ]);                                                                  // a rise, shared out by area

    await tester.tap(find.byKey(const ValueKey('estimate-reset')));
    await tester.pumpAndSettle();
    expect(api.calls.last.changes, isEmpty);

    await tester.tap(find.byKey(const ValueKey('estimate-all-by-area')));
    await tester.pumpAndSettle();
    expect(
        api.calls.last.changes,
        unorderedEquals([
          {'element': 'Water Charges', 'by_area': true},
          {'element': 'Service Charges', 'by_area': true},
        ]));                                                             // the same totals, shared by flat area
  });
}
