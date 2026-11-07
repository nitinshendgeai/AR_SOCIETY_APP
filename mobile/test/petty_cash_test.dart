import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/accounts/data/accounts_api.dart';
import 'package:ar_society_app/features/accounts/data/petty_cash_api.dart';
import 'package:ar_society_app/features/accounts/presentation/providers/accounts_providers.dart';
import 'package:ar_society_app/features/accounts/presentation/screens/petty_cash_screen.dart';
import 'package:ar_society_app/features/auth/domain/entities/user_entity.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';

Map<String, dynamic> _box({String balance = '2600.00', String pending = '0.00'}) => {
      'account_id': 'pc',
      'account_name': 'Petty Cash',
      'balance': balance,
      'pending': pending,
      'available': (double.parse(balance) - double.parse(pending)).toStringAsFixed(2),
      'float_amount': '3000.00',
      'expense_limit': '500.00',
      'custodian_name': 'Ramesh',
      'top_up_needed': '400.00',
      'spent_today': '150.00',
      'spent_month': '900.00',
      'last_count': null,
      'today': '2026-11-07',
    };

class _FakePetty extends PettyCashApi {
  _FakePetty({this.pending = '0.00'}) : super(dio: Dio());
  final String pending;
  final spent = <List<Map<String, dynamic>>>[];
  final counted = <double>[];

  @override
  Future<PettyCash> overview(String societyId) async => PettyCash.fromJson(_box(pending: pending));

  @override
  Future<List<PettyCashCount>> counts(String societyId) async => [
        PettyCashCount.fromJson({
          'date': '2026-11-05', 'counted': '2550.00', 'book': '2600.00', 'difference': '-50.00', 'state': 'short',
          'note': 'Tea money', 'counted_by': 'Meena',
        }),
      ];

  @override
  Future<Voucher> spend(String societyId, {required DateTime date, required List<Map<String, dynamic>> items}) async {
    spent.add(items);
    return Voucher.fromJson({
      'id': 'v1', 'voucher_type': 'payment', 'voucher_number': 'PV/9', 'voucher_date': '2026-11-07',
      'amount': '700.00', 'approval_status': 'pending', 'entries': [],
    });
  }

  @override
  Future<PettyCashCount> count(String societyId, {required double counted, DateTime? date, String? note}) async {
    this.counted.add(counted);
    return PettyCashCount.fromJson({
      'date': '2026-11-07', 'counted': '$counted', 'book': '2600.00', 'difference': '${counted - 2600}',
      'state': counted == 2600 ? 'tallies' : (counted < 2600 ? 'short' : 'excess'),
    });
  }
}

LedgerAccount _l(String id, String name, String nature, {bool cash = false, bool bank = false}) =>
    LedgerAccount.fromJson({
      'id': id, 'group_id': 'g', 'group_name': 'G', 'name': name, 'nature': nature,
      'is_cash': cash, 'is_bank': bank, 'is_active': true, 'opening_balance': '0', 'opening_type': 'dr',
    });

Future<_FakePetty> _pump(WidgetTester t, {List<String> roles = const ['Society Admin'], String pending = '0.00'}) async {
  t.view.physicalSize = const Size(700, 2600);
  t.view.devicePixelRatio = 1;
  addTearDown(t.view.reset);
  final api = _FakePetty(pending: pending);
  await t.pumpWidget(ProviderScope(
    overrides: [
      currentUserProvider.overrideWithValue(
          UserEntity(id: 'u', email: 'u@t.com', fullName: 'U', roles: roles, societyId: 's1', termsAccepted: true)),
      pettyCashApiProvider.overrideWithValue(api),
      ledgersProvider.overrideWith((ref, id) async => [
            _l('pc', 'Petty Cash', 'asset', cash: true),
            _l('bank', 'Bank Account', 'asset', bank: true),
            _l('off', 'Office & General Expenses', 'expense'),
            _l('print', 'Printing & Stationery', 'expense'),
          ]),
    ],
    child: MaterialApp(theme: AppTheme.lightTheme, home: const PettyCashScreen()),
  ));
  await t.pumpAndSettle();
  return api;
}

void main() {
  testWidgets('the Petty Cash page shows the box, what is free, the nudge to top up, and recent counts', (t) async {
    await _pump(t, pending: '300.00');
    expect(find.byKey(const ValueKey('petty-balance')), findsOneWidget);
    expect(find.text('₹2,600.00'), findsWidgets);
    expect(find.byKey(const ValueKey('petty-pending')), findsOneWidget);
    expect(find.byKey(const ValueKey('petty-low')), findsOneWidget);
    expect(find.text('Ramesh'), findsOneWidget);
    expect(find.textContaining('Short ₹50.00'), findsOneWidget);
    for (final k in ['petty-add-expenses', 'petty-top-up', 'petty-count', 'petty-book', 'petty-settings']) {
      expect(find.byKey(ValueKey(k)), findsOneWidget, reason: k);
    }
  });

  testWidgets('only the admin or committee sees Float and limit', (t) async {
    await _pump(t, roles: const ['Manager']);
    expect(find.byKey(const ValueKey('petty-add-expenses')), findsOneWidget);
    expect(find.byKey(const ValueKey('petty-settings')), findsNothing);
  });

  testWidgets('a day\'s expenses go in as one entry, each line to its own head', (t) async {
    final api = await _pump(t, roles: const ['Manager']);
    await t.tap(find.byKey(const ValueKey('petty-add-expenses')));
    await t.pumpAndSettle();

    await t.tap(find.byKey(const ValueKey('petty-head-0')));
    await t.pumpAndSettle();
    await t.tap(find.text('Office & General Expenses').last);
    await t.pumpAndSettle();
    await t.enterText(find.byKey(const ValueKey('petty-amount-0')), '450');
    await t.enterText(find.byKey(const ValueKey('petty-note-0')), 'Tea and biscuits');

    await t.tap(find.byKey(const ValueKey('petty-add-line')));
    await t.pumpAndSettle();
    await t.tap(find.byKey(const ValueKey('petty-head-1')));
    await t.pumpAndSettle();
    await t.tap(find.text('Printing & Stationery').last);
    await t.pumpAndSettle();
    await t.enterText(find.byKey(const ValueKey('petty-amount-1')), '250');
    await t.pumpAndSettle();
    expect(find.text('Total ₹700.00'), findsOneWidget);

    await t.tap(find.text('Save expenses'));
    await t.pumpAndSettle();
    expect(api.spent.length, 1);
    expect(api.spent.single, [
      {'expense_account_id': 'off', 'amount': 450.0, 'note': 'Tea and biscuits'},
      {'expense_account_id': 'print', 'amount': 250.0},
    ]);
  });

  testWidgets('saving with no head or amount asks for it and sends nothing', (t) async {
    final api = await _pump(t, roles: const ['Manager']);
    await t.tap(find.byKey(const ValueKey('petty-add-expenses')));
    await t.pumpAndSettle();
    await t.tap(find.text('Save expenses'));
    await t.pumpAndSettle();
    expect(api.spent, isEmpty);
    expect(find.textContaining('choose what it was for'), findsOneWidget);
  });

  testWidgets('counting the cash shows the difference as it is typed and records the count', (t) async {
    final api = await _pump(t);
    await t.tap(find.byKey(const ValueKey('petty-count')));
    await t.pumpAndSettle();
    await t.enterText(find.byKey(const ValueKey('petty-counted')), '2550');
    await t.pumpAndSettle();
    expect(find.text('Short by ₹50.00.'), findsOneWidget);
    await t.enterText(find.byKey(const ValueKey('petty-counted')), '2600');
    await t.pumpAndSettle();
    expect(find.text('Tallies with the books.'), findsOneWidget);
    await t.tap(find.text('Save count'));
    await t.pumpAndSettle();
    expect(api.counted, [2600.0]);
  });
}
