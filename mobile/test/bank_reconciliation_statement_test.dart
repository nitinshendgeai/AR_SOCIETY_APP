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

BankReconciliation _brs({bool cleared = false}) => BankReconciliation.fromJson(_brsJson(cleared: cleared));

Map<String, dynamic> _brsJson({bool cleared = false}) => {
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
    };

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
  final booked = <(String, String)>[];
  final selectedMatches = <(List<String>, List<String>)>[];
  final rowsFor = <String?>[]; // the bank ledger each rows request was for
  DateTime? clearedFrom; // how far back the Cleared tab asked
  final balances = <(DateTime, double)>[];
  var autoMatched = 0;
  var imported = 0;

  @override
  Future<BankReconciliation> statement(String societyId, {String? accountId, DateTime? asOn}) async => brs ?? _brs();

  @override
  Future<List<BrsLine>> cleared(String societyId, {String? accountId, DateTime? dateFrom}) async {
    clearedFrom = dateFrom;
    return clearedList;
  }

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
  Future<List<StatementRow>> rows(String societyId, {String? accountId}) async {
    rowsFor.add(accountId);
    return rowList;
  }

  @override
  Future<List<BrsLine>> suggestions(String societyId, String rowId) async => suggested;

  @override
  Future<void> match(String societyId, String rowId, String entryId) async => matches.add((rowId, entryId));

  @override
  Future<void> matchSelected(String societyId, {required List<String> rowIds, required List<String> entryIds}) async =>
      selectedMatches.add((rowIds, entryIds));

  @override
  Future<void> book(String societyId, String rowId, String ledgerId, {String? narration}) async =>
      booked.add((rowId, ledgerId));

  @override
  Future<void> setStatementBalance(String societyId,
          {required String accountId, required DateTime asOn, required double balance}) async =>
      balances.add((asOn, balance));

  @override
  Future<AutoMatchResult> autoMatch(String societyId, {String? accountId}) async {
    autoMatched++;
    return const AutoMatchResult(matched: 2, leftForAPerson: 1);
  }

  @override
  Future<StatementImportResult> importStatement(String societyId,
      {required Uint8List bytes, required String fileName, String? accountId}) async {
    imported++;
    return const StatementImportResult(imported: 1);
  }
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

LedgerAccount _ledger(String id, String name, {String? key}) => LedgerAccount.fromJson({
      'id': id,
      'group_id': 'g',
      'name': name,
      'system_key': key,
      'is_bank': false,
      'is_cash': false,
      'is_system': true,
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

  testWidgets('a bank statement balance that agrees says Reconciled', (t) async {
    _phone(t);
    final api = _FakeApi(
        brs: BankReconciliation.fromJson({
      ..._brsJson(cleared: true),
      'statement_balance': '103000.00',
      'statement_balance_source': 'pdf',
      'difference': '0.00',
      'unexplained': '0.00',
      'status': 'reconciled',
    }));
    await t.pumpWidget(_screen(api));
    await t.pumpAndSettle();
    expect(find.text('Balance as per the bank statement'), findsOneWidget);
    expect(find.textContaining('Reconciled — the books agree with the bank statement'), findsOneWidget);
    expect(find.text('Enter balance'), findsNothing);
  });

  testWidgets('without a statement balance it offers to enter one, and saves it for the day', (t) async {
    _phone(t);
    final api = _FakeApi();
    await t.pumpWidget(_screen(api));
    await t.pumpAndSettle();
    expect(find.textContaining('Not checked against the bank statement yet'), findsOneWidget);
    await t.tap(find.byKey(const ValueKey('enter-statement-balance')));
    await t.pumpAndSettle();
    await t.enterText(find.byKey(const ValueKey('statement-balance-field')), '1,00,000');
    await t.tap(find.text('Save'));
    await t.pumpAndSettle();
    expect(api.balances, hasLength(1));
    expect(api.balances.single.$2, 100000);
  });

  testWidgets('a difference that is the bank\'s own items lists them, and Record in books sends the row to the ledger',
      (t) async {
    _phone(t);
    final api = _FakeApi(
        brs: BankReconciliation.fromJson({
      ..._brsJson(cleared: true),
      'statement_balance': '102975.00',
      'statement_balance_source': 'pdf',
      'difference': '25.00',
      'unexplained': '0.00',
      'status': 'bank_items_to_book',
      'bank_only_rows': [
        {
          'id': 'b1',
          'txn_date': '2026-10-20',
          'description': 'SMS CHARGES',
          'reference': 'SMS1',
          'amount': '25.00',
          'direction': 'debit',
          'match_status': 'unmatched',
        }
      ],
    }));
    await t.pumpWidget(_screen(api, ledgers: [
      _bank('sbi', 'SBI Savings', def: true),
      _ledger('bc', 'Bank Charges', key: 'bank_charges'),
      _ledger('misc', 'Miscellaneous Expenses'),
    ]));
    await t.pumpAndSettle();
    expect(find.text('In the bank, not in your books'), findsOneWidget);
    expect(find.textContaining('exactly the bank\'s own items'), findsOneWidget);
    await t.tap(find.byKey(const ValueKey('row-b1')));
    await t.pumpAndSettle();
    expect(find.text('Not in your books yet?'), findsOneWidget);
    expect(find.text('Bank Charges'), findsOneWidget); // a bank debit is offered to Bank Charges
    await t.tap(find.byKey(const ValueKey('book-row')));
    await t.pumpAndSettle();
    expect(api.booked, [('b1', 'bc')]);
  });

  testWidgets('Match tab: two grids; ticking an entry and a bank row of the same total enables Match selected', (t) async {
    _phone(t);
    final api = _FakeApi(rowList: [_row('r1'), _row('r2', credit: true)]); // r1: debit 2000, r2: credit 2000
    await t.pumpWidget(_screen(api));
    await t.pumpAndSettle();
    await t.tap(find.text('Match'));
    await t.pumpAndSettle();
    expect(find.text('Our bank entries (2)'), findsOneWidget);
    expect(find.text('Bank statement rows (2)'), findsOneWidget);
    FilledButton button() => t.widget<FilledButton>(find.byKey(const ValueKey('match-selected')));
    expect(button().onPressed, isNull); // nothing ticked

    await t.tap(find.byKey(const ValueKey('match-entry-e-PV/2026-27/0007'))); // payment 2,000
    await t.tap(find.byKey(const ValueKey('match-row-r2'))); // a bank CREDIT of 2,000
    await t.pumpAndSettle();
    expect(find.textContaining('A bank credit belongs to a deposit'), findsOneWidget);
    expect(button().onPressed, isNull);

    await t.tap(find.byKey(const ValueKey('match-row-r2'))); // untick it
    await t.tap(find.byKey(const ValueKey('match-row-r1'))); // the bank DEBIT of 2,000
    await t.pumpAndSettle();
    expect(find.text('Totals agree: ready to match.'), findsOneWidget);
    await t.tap(find.byKey(const ValueKey('match-selected')));
    await t.pumpAndSettle();
    expect(api.selectedMatches, hasLength(1));
    expect(api.selectedMatches.single.$1, ['r1']); // the bank rows ticked
    expect(api.selectedMatches.single.$2, ['e-PV/2026-27/0007']); // the books' entries ticked
  });

  testWidgets('Match tab: totals that differ say by how much and cannot be matched', (t) async {
    _phone(t);
    final api = _FakeApi(rowList: [_row('r1')]);
    await t.pumpWidget(_screen(api));
    await t.pumpAndSettle();
    await t.tap(find.text('Match'));
    await t.pumpAndSettle();
    await t.tap(find.byKey(const ValueKey('match-entry-e-RV/2026-27/0012'))); // a deposit of 5,000
    await t.tap(find.byKey(const ValueKey('match-row-r1'))); // a debit of 2,000
    await t.pumpAndSettle();
    expect(t.widget<FilledButton>(find.byKey(const ValueKey('match-selected'))).onPressed, isNull);
    expect(api.selectedMatches, isEmpty);
  });

  testWidgets('Match tab: our entries and the bank rows are told apart by colour and by a label', (t) async {
    _phone(t);
    await t.pumpWidget(_screen(_FakeApi(rowList: [_row('r1')])));
    await t.pumpAndSettle();
    await t.tap(find.text('Match'));
    await t.pumpAndSettle();
    expect(find.text('From your books'), findsOneWidget);
    expect(find.text('From the bank statement'), findsOneWidget);
    Color iconColor(IconData i) => t.widget<Icon>(find.byIcon(i)).color!;
    final books = iconColor(Icons.menu_book_rounded);
    final bank = iconColor(Icons.account_balance_rounded);
    expect(books, AppTheme.primary); // blue: the society's own entries
    expect(bank, AppTheme.secondary); // purple: the bank's rows
    expect(books, isNot(bank));
    // a ticked box takes its side's colour
    await t.tap(find.byKey(const ValueKey('match-entry-e-PV/2026-27/0007')));
    await t.tap(find.byKey(const ValueKey('match-row-r1')));
    await t.pumpAndSettle();
    Color tick(String key) => t.widget<CheckboxListTile>(find.byKey(ValueKey(key))).activeColor!;
    expect(tick('match-entry-e-PV/2026-27/0007'), AppTheme.primary);
    expect(tick('match-row-r1'), AppTheme.secondary);
  });

  testWidgets('Bank rows tab: the rows are purple like the bank side of the Match tab', (t) async {
    _phone(t);
    await t.pumpWidget(_screen(_FakeApi(rowList: [_row('r1')])));
    await t.pumpAndSettle();
    await t.tap(find.text('Bank rows'));
    await t.pumpAndSettle();
    expect(find.text('Rows from the bank statement'), findsOneWidget);
    expect(t.widget<Icon>(find.byIcon(Icons.account_balance_rounded)).color, AppTheme.secondary);
    final purpleBar = t
        .widgetList<DecoratedBox>(find.ancestor(of: find.byKey(const ValueKey('row-r1')), matching: find.byType(DecoratedBox)))
        .any((d) {
      final b = d.decoration;
      return b is BoxDecoration && b.border is Border && (b.border! as Border).left.color == AppTheme.secondary;
    });
    expect(purpleBar, isTrue); // a purple bar down the side of every bank row
  });

  testWidgets('Cleared tab: the books\' entries are blue like the app side of the Match tab', (t) async {
    _phone(t);
    final l = BrsLine.fromJson({..._line('PV/2026-27/0003', '900.00', 'payment'), 'cleared_date': '2026-10-10'});
    await t.pumpWidget(_screen(_FakeApi(clearedList: [l])));
    await t.pumpAndSettle();
    await t.tap(find.text('Cleared'));
    await t.pumpAndSettle();
    expect(find.text('Entries from your books that the bank has cleared'), findsOneWidget);
    expect(t.widget<Icon>(find.byIcon(Icons.menu_book_rounded)).color, AppTheme.primary);
    final blueBar = t
        .widgetList<DecoratedBox>(find.ancestor(of: find.byKey(const ValueKey('cleared-e-PV/2026-27/0003')), matching: find.byType(DecoratedBox)))
        .any((d) {
      final b = d.decoration;
      return b is BoxDecoration && b.border is Border && (b.border! as Border).left.color == AppTheme.primary;
    });
    expect(blueBar, isTrue); // a blue bar down the side of every cleared entry
  });

  testWidgets('Statement tab: the books\' lines are blue and the bank\'s own items are purple', (t) async {
    _phone(t);
    final api = _FakeApi(
        brs: BankReconciliation.fromJson({
      ..._brsJson(),
      'bank_only_rows': [
        {
          'id': 'b1',
          'txn_date': '2026-10-20',
          'description': 'SMS CHARGES',
          'amount': '25.00',
          'direction': 'debit',
          'match_status': 'unmatched',
        }
      ],
    }));
    await t.pumpWidget(_screen(api));
    await t.pumpAndSettle();
    Color? titleColor(String text) => t.widget<Text>(find.text(text)).style?.color;
    expect(titleColor('Payments not yet cleared'), AppTheme.primary);
    expect(titleColor('Deposits not yet cleared'), AppTheme.primary);
    expect(titleColor('In the bank, not in your books'), AppTheme.secondary);
    bool leftBar(String key, Color color) => t
        .widgetList<DecoratedBox>(find.ancestor(of: find.byKey(ValueKey(key)), matching: find.byType(DecoratedBox)))
        .any((d) {
      final b = d.decoration;
      return b is BoxDecoration && b.border is Border && (b.border! as Border).left.color == color;
    });
    expect(leftBar('line-PV/2026-27/0007', AppTheme.primary), isTrue); // a payment of the books: blue bar
    expect(leftBar('line-RV/2026-27/0012', AppTheme.primary), isTrue); // a deposit of the books: blue bar
    expect(leftBar('row-b1', AppTheme.secondary), isTrue); // the bank's own item: purple bar
    expect(t.widget<CheckboxListTile>(find.byKey(const ValueKey('line-PV/2026-27/0007'))).activeColor, AppTheme.primary);
  });

  testWidgets('the rows of the chosen bank are asked for, so another bank\'s rows are not listed here', (t) async {
    _phone(t);
    final api = _FakeApi(rowList: [_row('r1')]);
    await t.pumpWidget(_screen(api));
    await t.pumpAndSettle();
    await t.tap(find.text('Bank rows'));
    await t.pumpAndSettle();
    expect(api.rowsFor, isNotEmpty);
    expect(api.rowsFor.toSet(), {'sbi'}); // the default bank, and only that one
  });

  testWidgets('Statement tab: only the first five of the bank\'s own items are listed, the rest are on the Match tab',
      (t) async {
    _phone(t);
    final api = _FakeApi(
        brs: BankReconciliation.fromJson({
      ..._brsJson(cleared: true),
      'bank_only_rows': [
        for (var i = 1; i <= 7; i++)
          {
            'id': 'b$i',
            'txn_date': '2026-10-${10 + i}',
            'description': 'CHARGE $i',
            'amount': '${i * 10}.00',
            'direction': 'debit',
            'match_status': 'unmatched',
          }
      ],
    }));
    await t.pumpWidget(_screen(api));
    await t.pumpAndSettle();
    for (var i = 1; i <= 5; i++) {
      expect(find.byKey(ValueKey('row-b$i')), findsOneWidget);
    }
    expect(find.byKey(const ValueKey('row-b6')), findsNothing);
    expect(find.byKey(const ValueKey('row-b7')), findsNothing);
    expect(find.text('2 more: they are all on the Match tab.'), findsOneWidget);
  });

  testWidgets('Cleared tab: only the last 90 days are asked for, and it says so', (t) async {
    _phone(t);
    final l = BrsLine.fromJson({..._line('PV/2026-27/0003', '900.00', 'payment'), 'cleared_date': '2026-10-10'});
    final api = _FakeApi(clearedList: [l]);
    await t.pumpWidget(_screen(api));
    await t.pumpAndSettle();
    await t.tap(find.text('Cleared'));
    await t.pumpAndSettle();
    expect(find.text('Cleared in the last 90 days'), findsOneWidget);
    final asked = api.clearedFrom!;
    final ago = DateTime.now().difference(asked).inDays;
    expect(ago, inInclusiveRange(89, 90)); // from 90 days back
  });

  testWidgets('without a bank ledger there is nothing to reconcile and it says how to start', (t) async {
    _phone(t);
    await t.pumpWidget(_screen(_FakeApi(), ledgers: const []));
    await t.pumpAndSettle();
    expect(find.text('No bank account yet'), findsOneWidget);
  });
}
