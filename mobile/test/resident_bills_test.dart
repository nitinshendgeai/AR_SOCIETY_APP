import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/core/theme/design_tokens.dart';
import 'package:ar_society_app/features/maintenance_billing/data/maintenance_billing_api.dart';
import 'package:ar_society_app/features/maintenance_billing/presentation/providers/maintenance_billing_providers.dart';
import 'package:ar_society_app/features/maintenance_billing/presentation/screens/my_bills_screen.dart';
import 'package:ar_society_app/features/resident_master/presentation/providers/resident_master_providers.dart' show myFlatsProvider;

MaintenanceBill _bill(String no, DateTime due, {String status = 'issued', bool overdue = false, String total = '5000.00', String paid = '0.00'}) {
  final outstanding = (double.parse(total) - double.parse(paid)).toStringAsFixed(2);
  return MaintenanceBill(
    id: no,
    cycleId: 'c',
    cycleName: 'Cycle $no',
    flatId: 'f1',
    invoiceNumber: no,
    status: status,
    isOverdue: overdue,
    billDate: due.subtract(const Duration(days: 15)),
    dueDate: due,
    totalAmount: total,
    paidAmount: paid,
    outstanding: status == 'paid' ? '0.00' : outstanding,
  );
}

MaintenanceBill _at(DateTime today, int dueInDays, {String paid = '0.00', String status = 'issued'}) =>
    _bill('B$dueInDays', today.add(Duration(days: dueInDays)), paid: paid, status: status);

void main() {
  final today = DateTime(2026, 11, 6, 15);

  group('billDueNote', () {
    test('overdue, due today and due soon are worded and coloured by urgency', () {
      expect(billDueNote(_at(today, -4), today)!.text, 'Overdue by 4 days');
      expect(billDueNote(_at(today, -4), today)!.color, kToneColors[AppTone.danger]!.foreground);
      expect(billDueNote(_at(today, -1), today)!.text, 'Overdue by 1 day');
      expect(billDueNote(_at(today, 0), today)!.text, 'Due today');
      expect(billDueNote(_at(today, 1), today)!.text, 'Due in 1 day');
      expect(billDueNote(_at(today, 3), today)!.color, kToneColors[AppTone.warning]!.foreground);
      expect(billDueNote(_at(today, 20), today)!.text, 'Due in 20 days');
      expect(billDueNote(_at(today, 20), today)!.color, AppTheme.textSecondary);
    });

    test('a part payment is mentioned, a settled bill has no note', () {
      expect(billDueNote(_at(today, 5, paid: '2000.00'), today)!.text, contains('paid'));
      expect(billDueNote(_at(today, -5, status: 'paid', paid: '5000.00'), today), isNull);
    });
  });

  testWidgets('My Bills leads with the total due and groups bills as Overdue, To Pay and History', (tester) async {
    tester.view.physicalSize = const Size(800, 2400);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    final now = DateTime.now();
    final summary = MyBillsSummary(
      totalOutstanding: '9000.00',
      openCount: 2,
      overdueCount: 1,
      bills: [
        _bill('OLD-1', now.subtract(const Duration(days: 10)), overdue: true, status: 'overdue', total: '4000.00'),
        _bill('NEW-1', now.add(const Duration(days: 9)), total: '5000.00'),
        _bill('PAID-1', now.subtract(const Duration(days: 40)), status: 'paid', total: '5000.00', paid: '5000.00'),
      ],
    );
    await tester.pumpWidget(ProviderScope(
      overrides: [
        myBillsProvider.overrideWith((ref) async => summary),
        myFlatsProvider.overrideWith((ref) async => const []),
      ],
      child: MaterialApp(theme: AppTheme.lightTheme, home: const MyBillsScreen()),
    ));
    await tester.pumpAndSettle();

    expect(find.text('Total due'), findsOneWidget);
    expect(find.textContaining('2 unpaid bills'), findsOneWidget);
    expect(find.textContaining('1 overdue'), findsOneWidget);
    expect(find.text('Overdue'), findsNWidgets(2));               // the group heading, and the overdue bill's own status
    expect(find.text('To Pay'), findsOneWidget);
    expect(find.text('History'), findsOneWidget);
    expect(find.textContaining('Overdue by 10 days'), findsWidgets);
    expect(find.textContaining('Due in 9 days'), findsWidgets);
  });

  testWidgets('with nothing owing it says the resident is all paid up', (tester) async {
    final summary = MyBillsSummary(totalOutstanding: '0.00', openCount: 0, overdueCount: 0, bills: [
      _bill('PAID-1', DateTime.now().subtract(const Duration(days: 40)), status: 'paid', paid: '5000.00'),
    ]);
    await tester.pumpWidget(ProviderScope(
      overrides: [
        myBillsProvider.overrideWith((ref) async => summary),
        myFlatsProvider.overrideWith((ref) async => const []),
      ],
      child: MaterialApp(theme: AppTheme.lightTheme, home: const MyBillsScreen()),
    ));
    await tester.pumpAndSettle();
    expect(find.text('You are all paid up'), findsOneWidget);
    expect(find.text('Total due'), findsNothing);
  });
}
