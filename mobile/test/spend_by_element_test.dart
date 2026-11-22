import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ar_society_app/features/accounts/data/accounts_api.dart' show ElementMonths, ExpensesByElement;
import 'package:ar_society_app/features/accounts/presentation/providers/accounts_providers.dart';
import 'package:ar_society_app/features/accounts/presentation/screens/expenses_by_element_screen.dart';
import 'package:ar_society_app/features/auth/domain/entities/user_entity.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/features/maintenance_billing/data/maintenance_billing_api.dart' show MaintenanceElement;
import 'package:ar_society_app/features/maintenance_billing/presentation/providers/maintenance_billing_providers.dart';

String _d(DateTime d) => d.toIso8601String().substring(0, 10);

Widget _app(List<ExpensePeriodKey> asked, List<ElementMonthsKey> askedMonths) => ProviderScope(
      overrides: [
        currentUserProvider.overrideWithValue(
            const UserEntity(id: 'u', email: 'u@t.com', fullName: 'U', roles: ['Society Admin'], societyId: 's1')),
        maintenanceElementsProvider.overrideWith((ref, key) async => const <MaintenanceElement>[]),
        expensesByElementProvider.overrideWith((ref, key) async {
          asked.add(key);
          return ExpensesByElement.fromJson({
            'date_from': _d(key.from),
            'date_to': _d(key.to),
            'total': '30000.00',
            'linked_total': '30000.00',
            'unlinked_total': '0.00',
            'elements': [
              {
                'element_id': 'e1',
                'code': 'security',
                'name': 'Security Services',
                'total': '30000.00',
                'ledgers': [
                  {'account_id': 'a1', 'name': 'Security Charges', 'amount': '30000.00'}
                ],
              },
            ],
            'unlinked': [],
          });
        }),
        elementMonthsProvider.overrideWith((ref, key) async {
          askedMonths.add(key);
          return ElementMonths.fromJson({
            'element_id': key.elementId,
            'title': 'Security Services',
            'date_from': _d(key.from),
            'date_to': _d(key.to),
            'total': '61000.00',
            'months': [
              {
                'month': '2026-08',
                'label': 'Aug 2026',
                'total': '30000.00',
                'ledgers': [
                  {'account_id': 'a1', 'name': 'Security Charges', 'amount': '30000.00'}
                ],
              },
              {'month': '2026-09', 'label': 'Sep 2026', 'total': '0.00', 'ledgers': []},
              {
                'month': '2026-10',
                'label': 'Oct 2026',
                'total': '31000.00',
                'ledgers': [
                  {'account_id': 'a1', 'name': 'Security Charges', 'amount': '31000.00'}
                ],
              },
            ],
          });
        }),
      ],
      child: const MaterialApp(home: ExpensesByElementScreen()),
    );

void main() {
  void tall(WidgetTester tester) {
    tester.view.physicalSize = const Size(800, 2400);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.reset);
  }

  final now = DateTime.now();
  final today = DateTime(now.year, now.month, now.day);
  final fyYear = now.month >= 4 ? now.year : now.year - 1;

  testWidgets('the Month arrows and Year so far ask the report for exactly those dates', (tester) async {
    tall(tester);
    final asked = <ExpensePeriodKey>[];
    await tester.pumpWidget(_app(asked, []));
    await tester.pumpAndSettle();
    expect(asked.last.from, DateTime(now.year, now.month));                    // this month, from its first day
    expect(asked.last.to, today);                                               // to today (the month is not over)

    await tester.tap(find.byTooltip('Previous month'));
    await tester.pumpAndSettle();
    expect(asked.last.from, DateTime(now.year, now.month - 1));
    expect(asked.last.to, DateTime(now.year, now.month, 0));                    // the last day of the month before

    await tester.tap(find.text('Year so far'));
    await tester.pumpAndSettle();
    expect(asked.last.from, DateTime(fyYear, 4, 1));                           // from the financial year's first day
    expect(asked.last.to, today);

    await tester.tap(find.text('Month'));
    await tester.pumpAndSettle();
    expect(asked.last.from, DateTime(now.year, now.month - 1));                // back on the month last looked at
  });

  testWidgets('an element opens its spend month by month, for the financial year so far', (tester) async {
    tall(tester);
    final askedMonths = <ElementMonthsKey>[];
    await tester.pumpWidget(_app([], askedMonths));
    await tester.pumpAndSettle();

    await tester.tap(find.byKey(const ValueKey('element-e1')));
    await tester.pumpAndSettle();
    expect(askedMonths.last.elementId, 'e1');
    expect(askedMonths.last.from, DateTime(fyYear, 4, 1));                     // this financial year...
    expect(askedMonths.last.to, today);                                         // ...up to today
    expect(find.text('Spend month by month'), findsOneWidget);
    expect(find.text('Aug 2026'), findsOneWidget);
    expect(find.text('Sep 2026'), findsOneWidget);
    expect(find.text('Oct 2026'), findsOneWidget);
    expect(find.text('Nothing recorded'), findsOneWidget);                      // a month with no spend is listed too
    expect(find.text('Security Charges'), findsNWidgets(2));                    // the ledger behind each month with spend
    expect(tester.widget<Text>(find.byKey(const ValueKey('months-total'))).data, '₹61,000.00');

    await tester.tap(find.byKey(const ValueKey('months-last-year')));
    await tester.pumpAndSettle();
    expect(askedMonths.last.from, DateTime(fyYear - 1, 4, 1));
    expect(askedMonths.last.to, DateTime(fyYear, 3, 31));

    await tester.tap(find.byKey(const ValueKey('months-this-year')));
    await tester.pumpAndSettle();
    expect(askedMonths.last.from, DateTime(fyYear, 4, 1));
    expect(askedMonths.last.to, today);
  });
}
