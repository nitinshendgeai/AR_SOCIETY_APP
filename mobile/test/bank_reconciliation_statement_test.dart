import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/accounts/data/accounts_api.dart' show LedgerAccount;
import 'package:ar_society_app/features/accounts/data/bank_reconciliation_api.dart';
import 'package:ar_society_app/features/accounts/presentation/providers/accounts_providers.dart';
import 'package:ar_society_app/features/accounts/presentation/providers/bank_reconciliation_providers.dart';
import 'package:ar_society_app/features/accounts/presentation/screens/bank_reconciliation_statement_screen.dart';
import 'package:ar_society_app/features/auth/domain/entities/user_entity.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';

Map<String, dynamic> _line(String no, String amount, String direction,
        {String? party, String? ref, bool refMatch = false}) =>
    {
      'entry_id': 'e-$no',
      'voucher_id': 'v-$no',
      'voucher_number': no,
      'voucher_type': 'payment',
      'date': '2026-10-06',
      'reference': ref,
      'narration': null,
      'party': party,
      'amount': amount,
      'direction': direction,
      'cleared_date': null,
      'days_pending': 12,
      'reference_matches': refMatch,
    };

BankReconciliation _brs({bool cleared = false}) => BankReconciliation.fromJson({
      'account_id': 'sbi',
      'account_name': 'SBI Savings',
      'as_on': '2026-10-25',
      'balance_per_books': '103000.00',
      'payments_not_cleared':
          cleared ? [] : [_line('PV/2026-27/0007', '2000.00', 'payment', party: 'Sparkle Services')],
      'payments_not_cleared_total': cleared ? '0.00' : '2000.00',
      'deposits_not_cleared': cleared ? [] : [_line('RV/2026-27/0012', '5000.00', 'deposit')],
      'deposits_not_cleared_total': cleared ? '0.00' : '5000.00',
      'balance_per_bank': cleared ? '103000.00' : '100000.00',
      'unmatched_statement_rows': 1,
    });

StatementRow _row(String id, {String status = 'unmatched', String? account = 'sbi', bool credit = false}) =>
    StatementRow.fromJson({
      'id': id,
      'txn_date': '2026-10-20',
      'description': 'CHQ 000123',
      'reference': '000123',
      'amount': '2000.00',
      'direction': credit ? 'credit' : 'debit',
      'bank_account_id': account,
      'match_status': status,
      'matched_entry_id': status == 'matched' ? 'e-x' : null,
    });

class _FakeApi extends BankReconciliationApi {
  _FakeApi({this.brs, this.rowList = const [], this.suggested = const [], this.clearedList = const []})
      : super(dio: Dio());
  final BankReconciliation? brs;
  final List<StatementRow> rowList;
  final List<BrsLine> suggested;
  final List<BrsLine> clearedList;
  final clearCalls = <(List<String>, DateTime)>[];
  final uncleared = <List<String>>[];
  final matches = <(String, String)>[];
  var autoMatched = 0;
  var imported = 0;

  @override
  Future<BankReconciliation> statement(String societyId, {String? accountId, DateTime? asOn}) async => brs ?? _brs();

  @override
  Future<List<BrsLine>> cleared(String societyId, {String? accountId}) async => clearedList;

  @override
  Future<int> clear(String societyId, List<String> entryIds, DateTime clearedOn) async {
    clearCalls.add((entryIds, clearedOn));
    return entryIds.length;
  }

  @override
  Future<int> unclear(String societyId, List<String> entryIds) async {
    uncleared.add(entryIds);
    return entryIds.length;
  }

  @override
  Future<List<StatementRow>> rows(String societyId) async => rowList;

  @override
  Future<List<BrsLine>> suggestions(String societyId, String rowId) async => suggested;

  @override
  Future<void> match(String societyId, String rowId, String entryId) async => matches.add((rowId, entryId));

  @override
  Future<AutoMatchResult> autoMatch(String societyId, {String? accountId}) async {
    autoMatched++;
    return const AutoMatchResult(matched: 2, leftForAPerson: 1);
  }

  @override
  Future<int> importStatement(String societyId,
          {required Uint8List csvBytes, required String fileName, String? accountId}) async =>
      ++imported;
}

LedgerAccount _bank(String id, String name, {bool def = false}) => LedgerAccount.fromJson({
      'id': id,
      'group_id': 'g',
      'name': name,
      'is_bank': true,
      'is_default_bank': def,
      'is_system': false,
      'is_active': true,
      'opening_balance': '0',
      'opening_type': 'dr',
    });

Widget _screen(_FakeApi api, {List<LedgerAccount>? ledgers}) => ProviderScope(
      overrides: [
        currentUserProvider.overrideWithValue(const UserEntity(
            id: 'u1',
            email: 'a@b.c',
            fullName: 'Asha',
            roles: ['Society Admin'],
            societyId: 's1',
            termsAccepted: true)),
        bankReconciliationApiProvider.overrideWithValue(api),
        ledgersProvider.overrideWith(
            (ref, id) async => ledgers ?? [_bank('hdfc', 'HDFC Current'), _bank('sbi', 'SBI Savings', def: true)]),
      ],
      child: MaterialApp(theme: AppTheme.lightTheme, home: const BankReconciliationStatementScreen()),
    );

void _phone(WidgetTester t) {
  t.view.physicalSize = const Size(390, 2000);
  t.view.devicePixelRatio = 1;
  addTearDown(t.view.reset);
}

void main() {
  testWidgets('the statement shows the books, the uncleared payments and deposits, and the balance per the bank',
      (t) async {
    _phone(t);
    await t.pumpWidget(_screen(_FakeApi()));
    await t.pumpAndSettle();

    expect(find.textContaining('SBI Savings as on'), findsOneWidget); // the default bank is chosen
    expect(find.text('₹1,03,000.00'), findsOneWidget);
    expect(find.text('+ ₹2,000.00'), findsOneWidget);
    expect(find.text('− ₹5,000.00'), findsOneWidget);
    expect(find.text('₹1,00,000.00'), findsOneWidget); // as per the bank
    expect(find.text('Payments not yet cleared'), findsOneWidget);
    expect(find.text('Deposits not yet cleared'), findsOneWidget);
    expect(find.text('PV/2026-27/0007'), findsOneWidget);
    expect(find.textContaining('Sparkle Services'), findsOneWidget);
    expect(find.text('Mark cleared'), findsNothing); // nothing ticked yet
  });

  testWidgets('ticking lines offers Mark cleared, which sends them with the day the bank cleared them', (t) async {
    _phone(t);
    final api = _FakeApi();
    await t.pumpWidget(_screen(api));
    await t.pumpAndSettle();
    await t.tap(find.byKey(const ValueKey('line-PV/2026-27/0007')));
    await t.pumpAndSettle();
    await t.tap(find.byKey(const ValueKey('line-RV/2026-27/0012')));
    await t.pumpAndSettle();
    expect(find.text('2 selected · deposits ₹5,000.00 · payments ₹2,000.00'), findsOneWidget);

    await t.tap(find.text('Mark cleared'));
    await t.pumpAndSettle();
    await t.tap(find.text('OK')); // the date picker, on today
    await t.pumpAndSettle();

    expect(api.clearCalls, hasLength(1));
    expect(api.clearCalls.single.$1, ['e-PV/2026-27/0007', 'e-RV/2026-27/0012']);
    final today = DateTime.now();
    expect(api.clearCalls.single.$2, DateTime(today.year, today.month, today.day));
    expect(find.text('Mark cleared'), findsNothing); // the selection is cleared
  });

  testWidgets('when everything is cleared it says so', (t) async {
    _phone(t);
    await t.pumpWidget(_screen(_FakeApi(brs: _brs(cleared: true))));
    await t.pumpAndSettle();
    expect(find.text('Everything is cleared'), findsOneWidget);
    expect(find.text('Payments not yet cleared'), findsNothing);
  });

  testWidgets('Bank rows lists the unmatched rows of this bank only; a row opens its suggestions and Match sends it',
      (t) async {
    _phone(t);
    final api = _FakeApi(
      rowList: [_row('r1'), _row('r2', account: 'hdfc'), _row('r3', status: 'matched')],
      suggested: [BrsLine.fromJson(_line('PV/2026-27/0007', '2000.00', 'payment', ref: '000123', refMatch: true))],
    );
    await t.pumpWidget(_screen(api));
    await t.pumpAndSettle();
    await t.tap(find.text('Bank rows'));
    await t.pumpAndSettle();
    expect(find.byKey(const ValueKey('row-r1')), findsOneWidget);
    expect(find.byKey(const ValueKey('row-r2')), findsNothing); // another bank account
    expect(find.byKey(const ValueKey('row-r3')), findsNothing); // matched: hidden by the filter

    await t.tap(find.byKey(const ValueKey('row-r1')));
    await t.pumpAndSettle();
    expect(find.text('Could be'), findsOneWidget);
    expect(find.textContaining('reference agrees'), findsOneWidget);
    await t.tap(find.byKey(const ValueKey('match-PV/2026-27/0007')));
    await t.pumpAndSettle();
    expect(api.matches, [('r1', 'e-PV/2026-27/0007')]);
  });

  testWidgets('a row with nothing in the books to match says so and still offers Ignore', (t) async {
    _phone(t);
    await t.pumpWidget(_screen(_FakeApi(rowList: [_row('r1', credit: true)])));
    await t.pumpAndSettle();
    await t.tap(find.text('Bank rows'));
    await t.pumpAndSettle();
    await t.tap(find.byKey(const ValueKey('row-r1')));
    await t.pumpAndSettle();
    expect(find.textContaining('No payment or deposit of this amount is waiting'), findsOneWidget);
    expect(find.text('Not in the books — ignore this row'), findsOneWidget);
  });

  testWidgets('Auto-match reports what it matched and what it left', (t) async {
    _phone(t);
    final api = _FakeApi(rowList: [_row('r1')]);
    await t.pumpWidget(_screen(api));
    await t.pumpAndSettle();
    await t.tap(find.text('Bank rows'));
    await t.pumpAndSettle();
    await t.tap(find.text('Auto-match'));
    await t.pumpAndSettle();
    expect(api.autoMatched, 1);
    expect(find.text('2 matched on their own · 1 left for you'), findsOneWidget);
  });

  testWidgets('the Cleared tab lists cleared lines and Undo takes one back', (t) async {
    _phone(t);
    final l = BrsLine.fromJson({..._line('PV/2026-27/0003', '900.00', 'payment'), 'cleared_date': '2026-10-10'});
    final api = _FakeApi(clearedList: [l]);
    await t.pumpWidget(_screen(api));
    await t.pumpAndSettle();
    await t.tap(find.text('Cleared'));
    await t.pumpAndSettle();
    expect(find.textContaining('PV/2026-27/0003'), findsOneWidget);
    await t.tap(find.text('Undo'));
    await t.pumpAndSettle();
    expect(api.uncleared, [
      ['e-PV/2026-27/0003']
    ]);
  });

  testWidgets('without a bank ledger there is nothing to reconcile and it says how to start', (t) async {
    _phone(t);
    await t.pumpWidget(_screen(_FakeApi(), ledgers: const []));
    await t.pumpAndSettle();
    expect(find.text('No bank account yet'), findsOneWidget);
  });
}
