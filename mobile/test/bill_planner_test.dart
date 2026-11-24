import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ar_society_app/features/auth/domain/entities/user_entity.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/features/maintenance_billing/data/maintenance_billing_api.dart';
import 'package:ar_society_app/features/maintenance_billing/presentation/providers/maintenance_billing_providers.dart';
import 'package:ar_society_app/features/maintenance_billing/presentation/screens/bill_estimate_screen.dart';

typedef _Plan = ({List<Map<String, dynamic>> lines, bool compare, double? area});

/// A server that does the planner's arithmetic for two flats, A / 101 (600 sq ft) and A / 201 (1,200 sq ft), whose
/// charge heads bill 2,200 and 3,400 a month today.
class _FakeBilling extends MaintenanceBillingApi {
  final List<_Plan> plans = [];
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
  Future<BillPlan> planMaintenance(String societyId, List<PlanLineInput> lines,
      {bool compare = true, double? totalAreaSqft}) async {
    plans.add((lines: [for (final l in lines) l.toJson()], compare: compare, area: totalAreaSqft));
    final area = totalAreaSqft ?? 1800.0;
    const months = {'month': 1, 'quarter': 3, 'year': 12};
    const periods = {'monthly': 1, 'quarterly': 3, 'yearly': 12};
    String f(double v) => v.toStringAsFixed(2);
    final monthly = [for (final l in lines) l.amount / months[l.period]!];
    double sum(bool byArea) {
      var t = 0.0;
      for (var i = 0; i < lines.length; i++) {
        if ((lines[i].split == 'area') == byArea) t += monthly[i];
      }
      return t;
    }

    final areaMonthly = sum(true), equalMonthly = sum(false);
    const flats = [('A / 101', 600.0, 2200.0), ('A / 201', 1200.0, 3400.0)];
    final collected = {for (final e in periods.entries) e.key: 0.0};
    final flatsJson = [];
    for (final (label, a, now) in flats) {
      final by = <String, dynamic>{};
      for (final e in periods.entries) {
        final shares = [
          for (var i = 0; i < lines.length; i++)
            {
              'name': lines[i].name,
              'amount': f(lines[i].split == 'area' ? monthly[i] * e.value * a / area : monthly[i] * e.value / 2),
            }
        ];
        final total = [for (final s in shares) double.parse(s['amount'] as String)].fold(0.0, (x, y) => x + y);
        collected[e.key] = collected[e.key]! + total;
        by[e.key] = {
          'total': f(total), 'per_sqft': f(total / a), 'shares': shares,
          if (compare) 'current': f(now * e.value),
          if (compare) 'change': f(total - now * e.value),
        };
      }
      flatsJson.add(<String, dynamic>{'flat_id': label, 'flat_label': label, 'area_sqft': a, ...(by['monthly'] as Map<String, dynamic>), 'by_period': by});
    }
    return BillPlan.fromJson({
      'lines': [
        for (var i = 0; i < lines.length; i++)
          {
            'name': lines[i].name,
            'amount': f(lines[i].amount),
            'period': lines[i].period,
            'split': lines[i].split,
            'by_period': {for (final e in periods.entries) e.key: f(monthly[i] * e.value)},
          }
      ],
      'periods': {
        for (final e in periods.entries)
          e.key: {
            'total': f((areaMonthly + equalMonthly) * e.value),
            'rate_per_sqft': f(areaMonthly * e.value / area),
            'per_flat_equal': f(equalMonthly * e.value / 2),
            'average_per_sqft': f((areaMonthly + equalMonthly) * e.value / area),
            'collected': f(collected[e.key]!),
            'shortfall': f((areaMonthly + equalMonthly) * e.value - collected[e.key]!),
          }
      },
      'total': f(areaMonthly + equalMonthly),
      'area_total_sqft': area,
      'area_source': totalAreaSqft == null ? 'flats' : 'typed',
      'flats_area_sqft': 1800,
      'flats_count': 2,
      'flats': flatsJson,
      'compared': compare,
      'month_label': 'June 2030',
      'totals': compare ? {'current': '5600.00', 'change': f(collected['monthly']! - 5600)} : null,
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
    tester.view.physicalSize = const Size(800, 4000);
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

  Future<void> fill(WidgetTester tester, int id, String name, String amount) async {
    await tester.enterText(find.byKey(ValueKey('plan-name-$id')), name);
    await tester.enterText(find.byKey(ValueKey('plan-amount-$id')), amount);
  }

  Future<void> calculate(WidgetTester tester) async {
    await tester.tap(find.byKey(const ValueKey('plan-calc')));
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
    await calculate(tester);

    expect(api.plans.single.compare, isTrue);
    expect(api.plans.single.area, isNull);                                                // the flats' areas, not a typed one
    expect(api.plans.single.lines, [
      {'name': 'Refuse Area', 'amount': 5000.0, 'split': 'area', 'period': 'month'},
      {'name': 'Gym', 'amount': 8000.0, 'split': 'equal', 'period': 'month'},
    ]);
    expect(tester.widget<Text>(find.byKey(const ValueKey('plan-total'))).data, '₹13,000.00');
    expect(tester.widget<Text>(find.byKey(const ValueKey('plan-rate'))).data, 'Rate by area: ₹2.78 / sq ft');
    expect(find.text('Plus an equal share: ₹4,000.00 per flat'), findsOneWidget);
    expect(find.textContaining('Difference: +₹7,400.00 a month'), findsOneWidget);

    await tester.tap(find.byKey(const ValueKey('plan-flat-A / 101')));
    await tester.pumpAndSettle();
    expect(find.text('Maintenance for the month'), findsOneWidget);                        // a flat opens to its shares
    expect(find.text('₹1,666.67'), findsWidgets);
    expect(find.text('Charge heads now'), findsOneWidget);
  });

  testWidgets('amounts per year or per quarter come out monthly, quarterly and yearly, side by side', (tester) async {
    final api = _FakeBilling();
    await openPlanner(tester, api);
    await fill(tester, 0, 'Insurance', '36000');
    await tester.tap(find.byKey(const ValueKey('plan-period-0')));                         // a yearly cost
    await tester.pumpAndSettle();
    await tester.tap(find.text('Per year').last);
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const ValueKey('plan-add')));
    await tester.pumpAndSettle();
    await fill(tester, 1, 'Security', '9000');
    await calculate(tester);

    expect(api.plans.single.lines, [
      {'name': 'Insurance', 'amount': 36000.0, 'split': 'area', 'period': 'year'},
      {'name': 'Security', 'amount': 9000.0, 'split': 'area', 'period': 'month'},
    ]);
    expect(tester.widget<Text>(find.byKey(const ValueKey('plan-total'))).data, '₹12,000.00');       // a month
    // the element table has the three periods in columns: monthly 12,000 · quarterly 36,000 · yearly 1,44,000
    expect(find.text('₹36,000.00'), findsWidgets);
    expect(find.text('₹1,44,000.00'), findsWidgets);
    expect(find.text('₹3,000.00'), findsWidgets);                                           // Insurance a month: 36,000 / 12

    await tester.tap(find.descendant(of: find.byKey(const ValueKey('plan-period')), matching: find.text('Quarterly')));
    await tester.pumpAndSettle();
    expect(tester.widget<Text>(find.byKey(const ValueKey('plan-total'))).data, '₹36,000.00');
    expect(find.text('Total the society needs each quarter'), findsOneWidget);
    expect(tester.widget<Text>(find.byKey(const ValueKey('plan-rate'))).data, 'Rate by area: ₹20.00 / sq ft per quarter');
  });

  testWidgets('a typed total area is sent, and a shortfall against the budget is shown', (tester) async {
    final api = _FakeBilling();
    await openPlanner(tester, api);
    await fill(tester, 0, 'Gym', '9000');
    await tester.enterText(find.byKey(const ValueKey('plan-area')), '2,000');
    await calculate(tester);

    expect(api.plans.single.area, 2000.0);
    expect(find.textContaining('(as typed)'), findsOneWidget);
    expect(find.byKey(const ValueKey('plan-shortfall')), findsOneWidget);                  // 8,100 collected of 9,000
    expect(tester.widget<Text>(find.byKey(const ValueKey('plan-shortfall'))).data, contains('short of the budget by ₹900.00'));
    expect(tester.widget<Text>(find.byKey(const ValueKey('plan-rate'))).data, 'Rate by area: ₹4.50 / sq ft');
  });

  testWidgets('a flat is picked to see its own monthly, quarterly and yearly figures', (tester) async {
    final api = _FakeBilling();
    await openPlanner(tester, api);
    await fill(tester, 0, 'Gym', '9000');
    await calculate(tester);
    expect(find.byKey(const ValueKey('plan-picked')), findsNothing);                       // nothing until one is picked

    await tester.tap(find.byKey(const ValueKey('plan-pick-wing')));
    await tester.pumpAndSettle();
    await tester.tap(find.text('A').last);
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const ValueKey('plan-pick-flat')));
    await tester.pumpAndSettle();
    await tester.tap(find.text('201').last);
    await tester.pumpAndSettle();

    expect(tester.widget<Text>(find.byKey(const ValueKey('plan-picked'))).data, 'A / 201 · 1200 sq ft');
    expect(find.text('This flat pays'), findsOneWidget);
    expect(find.text('₹6,000.00'), findsWidgets);                                           // 1,200 / 1,800 of 9,000 a month
    expect(find.text('₹18,000.00'), findsWidgets);                                          // a quarter
    expect(find.text('₹72,000.00'), findsWidgets);                                          // a year
    expect(find.text('Charge heads bill it now'), findsOneWidget);
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
    await calculate(tester);
    expect(api.plans.single.compare, isFalse);
    expect(api.plans.single.lines.map((l) => l['name']), ['Water Charges', 'Service Charges']);
    expect(api.plans.single.lines.map((l) => l['amount']), [3600.0, 2000.0]);
    expect(find.textContaining('Difference:'), findsNothing);
  });

  testWidgets('an incomplete plan or a bad area is refused before anything is asked, and a line can be removed', (tester) async {
    final api = _FakeBilling();
    await openPlanner(tester, api);
    await calculate(tester);                                                                // nothing listed
    expect(api.plans, isEmpty);

    await tester.enterText(find.byKey(const ValueKey('plan-name-0')), 'Podium');            // a name, no amount
    await calculate(tester);
    expect(api.plans, isEmpty);

    await tester.enterText(find.byKey(const ValueKey('plan-amount-0')), '100');
    await tester.enterText(find.byKey(const ValueKey('plan-area')), '1.2.3');               // not a number
    await calculate(tester);
    expect(api.plans, isEmpty);

    await tester.tap(find.byKey(const ValueKey('plan-remove-0')));
    await tester.pumpAndSettle();
    expect(find.byKey(const ValueKey('plan-name-0')), findsNothing);
    expect(find.byKey(const ValueKey('plan-name-1')), findsOneWidget);                      // a blank line is left to type in
    expect(tester.widget<TextField>(find.byKey(const ValueKey('plan-name-1'))).controller!.text, '');   // not the removed one
  });
}
