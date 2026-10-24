import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ar_society_app/features/accounts/presentation/screens/accounts_gateway_screen.dart';
import 'package:ar_society_app/features/accounts/presentation/widgets/gateway_menu.dart';
import 'package:ar_society_app/features/accounts/presentation/widgets/voucher_hotkeys.dart';

Widget _menu(List<String> opened, {VoidCallback? onBack}) => MaterialApp(
      home: Scaffold(
        body: GatewayMenu(
          onBack: onBack,
          sections: [
            GatewaySection('Vouchers', [
              GatewayItem(label: 'Receipt', letter: 'R', icon: Icons.south_west_rounded, hint: 'F6', onOpen: () => opened.add('receipt')),
              GatewayItem(label: 'Payment', letter: 'P', icon: Icons.north_east_rounded, hint: 'F5', onOpen: () => opened.add('payment')),
            ]),
            GatewaySection('Books', [
              GatewayItem(label: 'Day Book', letter: 'D', icon: Icons.receipt_long_rounded, onOpen: () => opened.add('daybook')),
              GatewayItem(
                  label: 'Approvals', letter: 'A', icon: Icons.fact_check_rounded, badge: '3 waiting', onOpen: () => opened.add('approvals')),
            ]),
          ],
        ),
      ),
    );

void main() {
  group('the Gateway of Accounts hierarchy', () {
    Future<List<GatewaySection>> build(WidgetTester t, {Set<String>? granted}) async {
      late List<GatewaySection> sections;
      await t.pumpWidget(MaterialApp(
        home: Builder(builder: (context) {
          sections = AccountsGatewayScreen.sections(context, fy: '2025-26', pendingApprovals: 2, granted: granted);
          return const SizedBox();
        }),
      ));
      return sections;
    }

    testWidgets('five groups, every account function reachable once, no letter used twice', (t) async {
      final sections = await build(t);
      expect({for (final s in sections) s.title: [for (final i in s.items) i.label]}, {
        'Transactions': ['Receipt', 'Payment', 'Contra (cash / bank transfer)', 'Journal', 'Expense'],
        'Books & Registers': ['Day Book', 'Cash & Bank Book', 'Invoice Register', 'Bills Register', 'Monthly Expenses'],
        'Receivables & Payables': [
          'Outstanding Receivable (members)', 'Outstanding Payable (vendors)', "Members' Ledger", 'Vendor Bills', 'Approvals',
        ],
        'Accounting Setup': ['Chart of Accounts (ledgers)'],
        'Financial Reports': [
          'Trial Balance', 'Income & Expenditure', 'Balance Sheet', 'Receipts & Payments', 'Schedule of Funds',
          'Spend by Maintenance Element', 'Financial Statements and Year-end Closing',
        ],
      });
      final items = [for (final s in sections) ...s.items];
      expect(items.length, 23); // nothing dropped from before the regrouping
      expect(items.map((i) => i.letter).toSet().length, items.length);
      expect(items.map((i) => i.label).toSet().length, items.length);
    });

    testWidgets('the shortcut letters did not move', (t) async {
      final items = {for (final s in await build(t)) for (final i in s.items) i.label: i.letter};
      expect(items['Receipt'], 'R');
      expect(items['Day Book'], 'D');
      expect(items['Approvals'], 'A');
      expect(items['Trial Balance'], 'T');
      expect(items['Chart of Accounts (ledgers)'], 'H');
      expect(items["Members' Ledger"], 'N');
      expect(items['Vendor Bills'], 'V');
      expect(items['Financial Statements and Year-end Closing'], 'Z');
    });

    testWidgets('the approvals badge is kept, and Vendor Bills is left out for someone without that grant', (t) async {
      final all = [for (final s in await build(t)) ...s.items];
      expect(all.firstWhere((i) => i.label == 'Approvals').badge, '2 waiting');
      final without = [for (final s in await build(t, granted: {'accounts'})) ...s.items];
      expect(without.any((i) => i.label == 'Vendor Bills'), isFalse);
      expect(without.length, 22);
      final withGrant = [for (final s in await build(t, granted: {'accounts', 'vendor_bills'})) ...s.items];
      expect(withGrant.length, 23);
    });
  });

  group('the Gateway menu', () {
    testWidgets('shows the sections, the letters, the hints and a badge', (tester) async {
      await tester.pumpWidget(_menu([]));
      await tester.pump();
      expect(find.text('VOUCHERS'), findsOneWidget);
      expect(find.text('BOOKS'), findsOneWidget);
      expect(find.text('Day Book'), findsOneWidget);
      expect(find.text('F6'), findsOneWidget);
      expect(find.text('3 waiting'), findsOneWidget);
      expect(find.text('R'), findsOneWidget);
      expect(find.text('D'), findsOneWidget);
    });

    testWidgets('Enter opens the highlighted line, and the arrow keys move it (and wrap round)', (tester) async {
      final opened = <String>[];
      await tester.pumpWidget(_menu(opened));
      await tester.pump();

      await tester.sendKeyEvent(LogicalKeyboardKey.enter);              // starts on the first line
      await tester.sendKeyEvent(LogicalKeyboardKey.arrowDown);
      await tester.sendKeyEvent(LogicalKeyboardKey.enter);
      await tester.sendKeyEvent(LogicalKeyboardKey.arrowDown);
      await tester.sendKeyEvent(LogicalKeyboardKey.arrowDown);
      await tester.sendKeyEvent(LogicalKeyboardKey.enter);
      await tester.sendKeyEvent(LogicalKeyboardKey.arrowDown);          // past the last: back to the first
      await tester.sendKeyEvent(LogicalKeyboardKey.enter);
      await tester.sendKeyEvent(LogicalKeyboardKey.arrowUp);            // before the first: the last
      await tester.sendKeyEvent(LogicalKeyboardKey.enter);
      expect(opened, ['receipt', 'payment', 'approvals', 'receipt', 'approvals']);
    });

    testWidgets('pressing a letter opens that line directly, in either case', (tester) async {
      final opened = <String>[];
      await tester.pumpWidget(_menu(opened));
      await tester.pump();
      await tester.sendKeyEvent(LogicalKeyboardKey.keyD);
      await tester.sendKeyEvent(LogicalKeyboardKey.keyP);
      await tester.sendKeyEvent(LogicalKeyboardKey.keyZ);               // no such letter: nothing happens
      expect(opened, ['daybook', 'payment']);
    });

    testWidgets('Esc goes back', (tester) async {
      var back = 0;
      await tester.pumpWidget(_menu([], onBack: () => back++));
      await tester.pump();
      await tester.sendKeyEvent(LogicalKeyboardKey.escape);
      expect(back, 1);
    });

    testWidgets('keys with Ctrl or Alt held are left to the app, not taken as letters', (tester) async {
      final opened = <String>[];
      await tester.pumpWidget(_menu(opened));
      await tester.pump();
      await tester.sendKeyDownEvent(LogicalKeyboardKey.controlLeft);
      await tester.sendKeyEvent(LogicalKeyboardKey.keyR);
      await tester.sendKeyUpEvent(LogicalKeyboardKey.controlLeft);
      await tester.sendKeyDownEvent(LogicalKeyboardKey.altLeft);
      await tester.sendKeyEvent(LogicalKeyboardKey.keyD);
      await tester.sendKeyUpEvent(LogicalKeyboardKey.altLeft);
      expect(opened, isEmpty);
    });

    testWidgets('a tap opens a line too', (tester) async {
      final opened = <String>[];
      await tester.pumpWidget(_menu(opened));
      await tester.pump();
      await tester.tap(find.byKey(const Key('gateway-d')));
      await tester.pump();
      expect(opened, ['daybook']);
    });
  });

  testWidgets('Alt+G opens the Gateway from a screen with the voucher keys', (tester) async {
    var gateway = 0;
    final types = <String>[];
    await tester.pumpWidget(MaterialApp(
      home: Scaffold(
        body: VoucherHotkeys(
          onGateway: (_) => gateway++,
          onType: (_, t) => types.add(t),
          child: const TextField(autofocus: true),
        ),
      ),
    ));
    await tester.pump();
    await tester.sendKeyDownEvent(LogicalKeyboardKey.altLeft);
    await tester.sendKeyEvent(LogicalKeyboardKey.keyG);
    await tester.sendKeyUpEvent(LogicalKeyboardKey.altLeft);
    await tester.sendKeyEvent(LogicalKeyboardKey.f6);
    expect(gateway, 1);
    expect(types, ['receipt']);
  });
}
