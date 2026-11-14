import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/maintenance_billing/data/maintenance_billing_api.dart';
import 'package:ar_society_app/features/maintenance_billing/presentation/providers/maintenance_billing_providers.dart';
import 'package:ar_society_app/features/maintenance_billing/presentation/screens/my_bills_screen.dart';
import 'package:ar_society_app/features/maintenance_billing/presentation/screens/my_ledger_screen.dart';
import 'package:ar_society_app/features/resident_master/presentation/providers/resident_master_providers.dart' show myFlatsProvider;

MyLedgerFlat _flat(String label, {String dues = '0.00', String advance = '0.00', String balance = '0.00', String drCr = 'Dr',
        List<MyLedgerLine> lines = const []}) =>
    MyLedgerFlat(flatId: label, flatLabel: label, dues: dues, advance: advance, balance: balance, drCr: drCr, lines: lines);

Widget _app(Future<MyLedger> Function() load) => ProviderScope(
      overrides: [myLedgerProvider.overrideWith((ref) => load())],
      child: MaterialApp(theme: AppTheme.lightTheme, home: const MyLedgerScreen()),
    );

void main() {
  billsTileTests();
  test('parses the server\'s answer', () {
    final l = MyLedger.fromJson({
      'as_of': '2026-11-14',
      'flats': [
        {
          'flat_id': 'f1', 'flat_label': 'Tower A-101', 'dues': '2500.00', 'advance': '0.00',
          'balance': '2500.00', 'balance_dr_cr': 'Dr',
          'lines': [
            {'date': '2026-11-01', 'narration': 'Bill INV-1', 'debit': '2500.00', 'credit': '0.00', 'balance': '2500.00', 'balance_dr_cr': 'Dr'}
          ],
        }
      ],
    });
    expect(l.flats.single.flatLabel, 'Tower A-101');
    expect(l.flats.single.lines.single.debit, '2500.00');
    expect(l.flats.single.settled, isFalse);
  });

  group('the words for a balance', () {
    test('owing, in credit and settled', () {
      expect(ledgerBalanceWords(_flat('A', balance: '10.00', drCr: 'Dr')), 'You owe the society');
      expect(ledgerBalanceWords(_flat('A', balance: '10.00', drCr: 'Cr')), 'You are in credit');
      expect(ledgerBalanceWords(_flat('A', balance: '0.00', drCr: 'Dr')), 'Nothing due');
      expect(ledgerBalanceWords(_flat('A', balance: '0.00', drCr: 'Cr')), 'Nothing due');
    });
  });

  testWidgets('a resident who owes sees it in plain words, with dues and advance', (t) async {
    await t.pumpWidget(_app(() async => MyLedger(asOf: '2026-11-14', flats: [
          _flat('Tower A-101', dues: '2500.00', balance: '2500.00', drCr: 'Dr', lines: const [
            MyLedgerLine(date: '2026-11-01', narration: 'Maintenance Oct', debit: '2500.00', credit: '0.00', balance: '2500.00', drCr: 'Dr'),
          ]),
        ])));
    await t.pumpAndSettle();
    expect(find.text('Tower A-101'), findsOneWidget);
    expect(find.byKey(const Key('ledger-words')), findsOneWidget);
    expect(find.text('You owe the society'), findsOneWidget);
    expect(find.text('₹2,500.00'), findsWidgets);                     // the balance (and the dues row)
    expect(find.text('Advance paid ahead'), findsOneWidget);
    expect(find.text('Latest entries'), findsOneWidget);
    expect(find.text('Maintenance Oct'), findsOneWidget);
    expect(find.text('+ ₹2,500.00'), findsOneWidget);                 // a bill raised
    expect(find.textContaining('Dr'), findsWidgets);
  });

  testWidgets('a resident in credit sees it, and a payment shows as money coming off', (t) async {
    await t.pumpWidget(_app(() async => MyLedger(asOf: '2026-11-14', flats: [
          _flat('Tower A-102', advance: '3500.00', balance: '3500.00', drCr: 'Cr', lines: const [
            MyLedgerLine(date: '2026-10-05', narration: 'Receipt R-7', debit: '0.00', credit: '6000.00', balance: '6000.00', drCr: 'Cr'),
          ]),
        ])));
    await t.pumpAndSettle();
    expect(find.text('You are in credit'), findsOneWidget);
    expect(find.text('− ₹6,000.00'), findsOneWidget);
  });

  testWidgets('a settled account says nothing is due and has a note when empty', (t) async {
    await t.pumpWidget(_app(() async => MyLedger(asOf: '2026-11-14', flats: [_flat('Tower B-5')])));
    await t.pumpAndSettle();
    expect(find.text('Nothing due'), findsOneWidget);
    expect(find.text('Nothing has been entered in this account yet.'), findsOneWidget);
  });

  testWidgets('a resident with several flats sees each one', (t) async {
    await t.pumpWidget(_app(() async => MyLedger(asOf: '2026-11-14', flats: [
          _flat('Tower A-101', balance: '100.00', drCr: 'Dr'),
          _flat('Tower C-9', balance: '50.00', drCr: 'Cr'),
        ])));
    await t.pumpAndSettle();
    expect(find.text('Tower A-101'), findsOneWidget);
    expect(find.text('Tower C-9'), findsOneWidget);
    expect(find.byKey(const Key('ledger-balance')), findsNWidgets(2));
  });

  testWidgets('no flat linked gives a clear message', (t) async {
    await t.pumpWidget(_app(() async => const MyLedger(asOf: '2026-11-14', flats: [])));
    await t.pumpAndSettle();
    expect(find.textContaining('No flat is linked'), findsOneWidget);
  });

  testWidgets('a failed load says so and offers Try again', (t) async {
    await t.pumpWidget(_app(() async => throw DioException(requestOptions: RequestOptions(path: '/x'))));
    await t.pumpAndSettle();
    expect(find.text('Try again'), findsOneWidget);
  });
}

// ── The way in from My Bills ──
MyBillsSummary _noBills() => const MyBillsSummary(totalOutstanding: '0.00', openCount: 0, overdueCount: 0, bills: []);

Widget _bills(MyLedger ledger) => ProviderScope(
      overrides: [
        myBillsProvider.overrideWith((ref) async => _noBills()),
        myLedgerProvider.overrideWith((ref) async => ledger),
        myFlatsProvider.overrideWith((ref) async => const []),
      ],
      child: MaterialApp(theme: AppTheme.lightTheme, home: const MyBillsScreen()),
    );

void billsTileTests() {
  testWidgets('My Bills has a My Ledger tile showing the balance when there is one flat', (t) async {
    await t.pumpWidget(_bills(MyLedger(asOf: '2026-11-14', flats: [_flat('Tower A-101', balance: '2500.00', drCr: 'Dr')])));
    await t.pumpAndSettle();
    expect(find.byKey(const Key('my-ledger-tile')), findsOneWidget);
    expect(find.text('My Ledger'), findsOneWidget);
    expect(find.text('You owe the society · ₹2,500.00'), findsOneWidget);
  });

  testWidgets('with several flats the tile does not pick one balance', (t) async {
    await t.pumpWidget(_bills(MyLedger(asOf: '2026-11-14', flats: [
      _flat('Tower A-101', balance: '100.00'),
      _flat('Tower C-9', balance: '50.00', drCr: 'Cr'),
    ])));
    await t.pumpAndSettle();
    expect(find.text('Your account with the society'), findsOneWidget);
  });

  testWidgets('if the ledger cannot be loaded the bills still show and the tile still opens the ledger', (t) async {
    await t.pumpWidget(ProviderScope(
      overrides: [
        myBillsProvider.overrideWith((ref) async => _noBills()),
        myLedgerProvider.overrideWith((ref) async => throw DioException(requestOptions: RequestOptions(path: '/x'))),
        myFlatsProvider.overrideWith((ref) async => const []),
      ],
      child: MaterialApp(theme: AppTheme.lightTheme, home: const MyBillsScreen()),
    ));
    await t.pumpAndSettle();
    expect(find.text('Your account with the society'), findsOneWidget);
    expect(find.byKey(const Key('my-ledger-tile')), findsOneWidget);
  });
}
