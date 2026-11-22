import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ar_society_app/features/auth/domain/entities/user_entity.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/features/maintenance_billing/data/maintenance_billing_api.dart';
import 'package:ar_society_app/features/maintenance_billing/presentation/providers/maintenance_billing_providers.dart';
import 'package:ar_society_app/features/maintenance_billing/presentation/screens/bill_estimate_screen.dart';

class _FakeBilling extends MaintenanceBillingApi {
  final List<({List<Map<String, dynamic>> lines, bool compare})> plans = [];
  _FakeBilling() : super(dio: Dio());

  @override
  Future<BillEstimate> estimateBills(String societyId, {String? month, List<EstimateChange> changes = const []}) async =>
      BillEstimate.fromJson({
        'month': '2030-06',
        'month_label': 'June 2030',
        'adjusted': false,
        'flats_count': 2,
        'total_area_sqft': 1800,
        'elements': [
          {
            'element': 'Water Charges', 'current_total': '3600.00', 'estimate_total': '3600.00', 'change': '0.00',
            'current_per_sqft': '2.00', 'estimate_per_sqft': '2.00', 'adjusted': false,
          },
          {
            'element': 'Service Charges', 'current_total': '2000.00', 'estimate_total': '2000.00', 'change': '0.00',
            'current_per_sqft': '1.11', 'estimate_per_sqft': '1.11', 'adjusted': false,
          },
        ],
        'flats': [],
        'totals': {'current': '5600.00', 'estimate': '5600.00', 'change': '0.00', 'current_per_sqft': '3.11', 'estimate_per_sqft': '3.11'},
        'notes': [],
      });

  @override
  Future<BillPlan> planMaintenance(String societyId, List<PlanLineInput> lines, {bool compare = true}) async {
    plans.add((lines: [for (final l in lines) l.toJson()], compare: compare));
    return BillPlan.fromJson({
      'lines': [
        for (final l in lines)
          {
            'name': l.name,
            'amount': l.amount.toStringAsFixed(2),
            'split': l.split,
            'rate_per_sqft': l.split == 'area' ? '2.7778' : null,
            'per_flat': l.split == 'equal' ? '4000.00' : null,
          }
      ],
      'total': '13000.00',
      'area_total_sqft': 1800,
      'flats_count': 2,
      'rate_per_sqft': '2.78',
      'per_flat_equal': '4000.00',
      'average_per_sqft': '7.22',
      'collected': '13000.00',
      'flats': [
        {
          'flat_id': 'f1', 'flat_label': 'A / 101', 'area_sqft': 600,
          'shares': [
            {'name': 'Refuse Area', 'amount': '1666.67'},
            {'name': 'Gym', 'amount': '4000.00'},
          ],
          'total': '5666.67', 'per_sqft': '9.44', 'current': '2200.00', 'change': '3466.67',
        },
        {
          'flat_id': 'f2', 'flat_label': 'A / 201', 'area_sqft': 1200,
          'shares': [
            {'name': 'Refuse Area', 'amount': '3333.33'},
            {'name': 'Gym', 'amount': '4000.00'},
          ],
          'total': '7333.33', 'per_sqft': '6.11', 'current': '3400.00', 'change': '3933.33',
        },
      ],
      'compared': compare,
      'month_label': 'June 2030',
      'totals': compare ? {'current': '5600.00', 'change': '7400.00'} : null,
      'notes': ['Rounded to the paisa for each flat.'],
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

void main() {
  void tall(WidgetTester tester) {
    tester.view.physicalSize = const Size(800, 3000);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.reset);
  }

  Future<void> openPlanner(WidgetTester tester, _FakeBilling api) async {
    tall(tester);
    await tester.pumpWidget(_app(api));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Budget planner'));
    await tester.pumpAndSettle();
  }

  testWidgets('common areas are added as lines, each shared by area or equally, and the plan shows the rate per sq ft',
      (tester) async {
    final api = _FakeBilling();
    await openPlanner(tester, api);

    await tester.tap(find.byKey(const ValueKey('plan-common-Refuse Area')));
    await tester.pumpAndSettle();
    expect(tester.widget<TextField>(find.byKey(const ValueKey('plan-name-0'))).controller!.text, 'Refuse Area');
    await tester.tap(find.byKey(const ValueKey('plan-common-Gym')));
    await tester.pumpAndSettle();
    expect(tester.widget<TextField>(find.byKey(const ValueKey('plan-name-1'))).controller!.text, 'Gym');
    await tester.tap(find.byKey(const ValueKey('plan-common-Gym')));                     // a second Gym is not added again
    await tester.pumpAndSettle();
    expect(find.byKey(const ValueKey('plan-name-2')), findsNothing);

    await tester.enterText(find.byKey(const ValueKey('plan-amount-0')), '5000');
    await tester.enterText(find.byKey(const ValueKey('plan-amount-1')), '8,000');
    await tester.tap(find.descendant(of: find.byKey(const ValueKey('plan-split-1')), matching: find.text('Equal per flat')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const ValueKey('plan-calc')));
    await tester.pumpAndSettle();

    expect(api.plans.single.compare, isTrue);
    expect(api.plans.single.lines, [
      {'name': 'Refuse Area', 'amount': 5000.0, 'split': 'area'},
      {'name': 'Gym', 'amount': 8000.0, 'split': 'equal'},
    ]);
    expect(tester.widget<Text>(find.byKey(const ValueKey('plan-total'))).data, '₹13,000.00');
    expect(tester.widget<Text>(find.byKey(const ValueKey('plan-rate'))).data, 'Rate by area: ₹2.78 / sq ft');
    expect(find.text('Plus an equal share: ₹4,000.00 per flat'), findsOneWidget);
    expect(find.textContaining('Difference: +₹7,400.00 a month'), findsOneWidget);

    await tester.tap(find.byKey(const ValueKey('plan-flat-A / 101')));
    await tester.pumpAndSettle();
    expect(find.text('Maintenance for the month'), findsOneWidget);                        // a flat opens to its shares
    expect(find.text('₹1,666.67'), findsOneWidget);
    expect(find.text('Charge heads now'), findsOneWidget);
  });

  testWidgets('a plan can start from the elements as they stand, and be compared or not', (tester) async {
    final api = _FakeBilling();
    await openPlanner(tester, api);
    await tester.tap(find.byKey(const ValueKey('plan-from-current')));
    await tester.pumpAndSettle();
    expect(find.text('Water Charges'), findsOneWidget);
    expect(find.text('Service Charges'), findsOneWidget);

    await tester.tap(find.byKey(const ValueKey('plan-compare')));                          // leave the comparison out
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const ValueKey('plan-calc')));
    await tester.pumpAndSettle();
    expect(api.plans.single.compare, isFalse);
    expect(api.plans.single.lines.map((l) => l['name']), ['Water Charges', 'Service Charges']);
    expect(api.plans.single.lines.map((l) => l['amount']), [3600.0, 2000.0]);
    expect(find.textContaining('Difference:'), findsNothing);
  });

  testWidgets('an incomplete plan is refused before anything is asked, and a line can be removed', (tester) async {
    final api = _FakeBilling();
    await openPlanner(tester, api);
    await tester.tap(find.byKey(const ValueKey('plan-calc')));                             // nothing listed
    await tester.pumpAndSettle();
    expect(api.plans, isEmpty);

    await tester.enterText(find.byKey(const ValueKey('plan-name-0')), 'Podium');            // a name, no amount
    await tester.tap(find.byKey(const ValueKey('plan-calc')));
    await tester.pumpAndSettle();
    expect(api.plans, isEmpty);

    await tester.tap(find.byKey(const ValueKey('plan-remove-0')));
    await tester.pumpAndSettle();
    expect(find.byKey(const ValueKey('plan-name-0')), findsNothing);
    expect(find.byKey(const ValueKey('plan-name-1')), findsOneWidget);                      // a blank line is left to type in
    expect(tester.widget<TextField>(find.byKey(const ValueKey('plan-name-1'))).controller!.text, '');   // not the removed one
  });
}
