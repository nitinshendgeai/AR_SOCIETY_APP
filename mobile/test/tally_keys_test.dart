import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ar_society_app/features/accounts/data/accounts_api.dart';
import 'package:ar_society_app/features/accounts/presentation/providers/accounts_providers.dart';
import 'package:ar_society_app/features/accounts/presentation/widgets/quick_ledger_sheet.dart';
import 'package:ar_society_app/features/accounts/presentation/widgets/voucher_hotkeys.dart';
import 'package:ar_society_app/shared/widgets/typeahead_field.dart';

Map<String, dynamic> _group(String id, String name, String nature, {String? key}) =>
    {'id': id, 'name': name, 'nature': nature, 'system_key': key, 'accounts': <dynamic>[]};

class _FakeAccounts extends AccountsApi {
  _FakeAccounts() : super(dio: Dio());
  Map<String, dynamic>? created;

  @override
  Future<List<AccountGroupRow>> chart(String societyId) async => [
        AccountGroupRow.fromJson(_group('g1', 'Cash & Bank Balances', 'asset', key: 'cash_bank')),
        AccountGroupRow.fromJson(_group('g2', 'Establishment & Administrative Expenses', 'expense')),
        AccountGroupRow.fromJson(_group('g3', 'Income from Members', 'income')),
      ];

  @override
  Future<LedgerAccount> createLedger(Map<String, dynamic> fields) async {
    created = fields;
    return LedgerAccount.fromJson({
      'id': 'new1', 'group_id': fields['group_id'], 'name': fields['name'], 'is_system': false, 'is_active': true,
      'opening_balance': '0', 'opening_type': 'dr', 'is_cash': false, 'is_bank': false, 'is_default_bank': false,
    });
  }
}

Future<void> _alt(WidgetTester tester, LogicalKeyboardKey key) async {
  await tester.sendKeyDownEvent(LogicalKeyboardKey.altLeft);
  await tester.sendKeyEvent(key);
  await tester.sendKeyUpEvent(LogicalKeyboardKey.altLeft);
}

void main() {
  group('voucher hotkeys', () {
    test('Tally keys: F4 Contra, F5 Payment, F6 Receipt, F7 Journal', () {
      expect(voucherHotkeyLabel('contra'), 'F4');
      expect(voucherHotkeyLabel('payment'), 'F5');
      expect(voucherHotkeyLabel('receipt'), 'F6');
      expect(voucherHotkeyLabel('journal'), 'F7');
      expect(voucherHotkeyLabel('bill'), isNull);
    });

    testWidgets('each key reports its voucher type, also while typing in a field', (tester) async {
      final got = <String>[];
      await tester.pumpWidget(MaterialApp(
        home: Scaffold(body: VoucherHotkeys(onType: (_, t) => got.add(t), child: const TextField(autofocus: true))),
      ));
      await tester.pump();
      for (final k in [LogicalKeyboardKey.f6, LogicalKeyboardKey.f5, LogicalKeyboardKey.f4, LogicalKeyboardKey.f7]) {
        await tester.sendKeyEvent(k);
      }
      expect(got, ['receipt', 'payment', 'contra', 'journal']);
    });

    testWidgets('the keys work before anything has been clicked', (tester) async {
      final got = <String>[];
      await tester.pumpWidget(MaterialApp(
        home: Scaffold(body: VoucherHotkeys(onType: (_, t) => got.add(t), child: const Text('Day Book'))),
      ));
      await tester.pump();
      await tester.sendKeyEvent(LogicalKeyboardKey.f6);
      expect(got, ['receipt']);
    });
  });

  group('creating a ledger from the field', () {
    Widget host(List<String> options, Future<String?> Function(String) onCreate, void Function(String) onSelected,
            {String? value}) =>
        MaterialApp(
          home: Scaffold(
            body: Padding(
              padding: const EdgeInsets.all(16),
              child: TypeaheadField<String>(
                options: options,
                value: value,
                label: (s) => s,
                onSelected: onSelected,
                onCreate: onCreate,
                advanceOnSelect: false,
                autofocus: true,
              ),
            ),
          ),
        );

    testWidgets('a name nothing matches says how to create it, and Enter creates it', (tester) async {
      String? asked, chosen;
      await tester.pumpWidget(host(['Electricity', 'Water charges'], (n) async {
        asked = n;
        return n;
      }, (s) => chosen = s));
      await tester.pump();
      await tester.enterText(find.byType(TextField), 'Lift AMC');
      await tester.pump();
      expect(find.text('Nothing matches. Press Enter or Alt+C to create "Lift AMC"'), findsOneWidget);

      await tester.testTextInput.receiveAction(TextInputAction.done);
      await tester.pumpAndSettle();
      expect(asked, 'Lift AMC');
      expect(chosen, 'Lift AMC');
    });

    testWidgets('Alt+C creates from a partly matching name too', (tester) async {
      String? asked;
      await tester.pumpWidget(host(['Electricity', 'Water charges'], (n) async {
        asked = n;
        return n;
      }, (_) {}));
      await tester.pump();
      await tester.enterText(find.byType(TextField), 'Water');
      await tester.pump();
      await _alt(tester, LogicalKeyboardKey.keyC);
      await tester.pumpAndSettle();
      expect(asked, 'Water');
    });

    testWidgets('an exact existing name is never offered for creation', (tester) async {
      var asked = false;
      await tester.pumpWidget(host(['Electricity'], (n) async {
        asked = true;
        return n;
      }, (_) {}));
      await tester.pump();
      await tester.enterText(find.byType(TextField), 'electricity');
      await tester.pump();
      await _alt(tester, LogicalKeyboardKey.keyC);
      await tester.pumpAndSettle();
      expect(asked, isFalse);
      expect(find.byKey(const Key('typeahead-create')), findsNothing);
    });

    testWidgets('cancelling the creation leaves nothing chosen', (tester) async {
      String? chosen;
      await tester.pumpWidget(host(['Electricity'], (n) async => null, (s) => chosen = s));
      await tester.pump();
      await tester.enterText(find.byType(TextField), 'Brand new');
      await tester.pump();
      await tester.testTextInput.receiveAction(TextInputAction.done);
      await tester.pumpAndSettle();
      expect(chosen, isNull);
    });
  });

  group('the new-ledger sheet', () {
    Future<_FakeAccounts> open(WidgetTester tester, {String? nature, ValueSetter<LedgerAccount?>? done}) async {
      final api = _FakeAccounts();
      await tester.pumpWidget(ProviderScope(
        overrides: [accountsApiProvider.overrideWithValue(api)],
        child: MaterialApp(
          home: Scaffold(
            body: Builder(
              builder: (context) => ElevatedButton(
                onPressed: () async {
                  final made = await showQuickLedger(context, societyId: 'soc', name: 'Lift AMC', preferNature: nature);
                  done?.call(made);
                },
                child: const Text('open'),
              ),
            ),
          ),
        ),
      ));
      await tester.tap(find.text('open'));
      await tester.pumpAndSettle();
      return api;
    }

    testWidgets('keeps the typed name, leaves out cash and bank groups, and preselects the likely group', (tester) async {
      await open(tester, nature: 'expense');
      expect(find.text('New ledger'), findsOneWidget);
      expect(tester.widget<TextField>(find.byKey(const Key('quick-ledger-name'))).controller!.text, 'Lift AMC');
      expect(find.text('Establishment & Administrative Expenses'), findsOneWidget);   // preselected for a payment
      expect(find.text('Cash & Bank Balances'), findsNothing);
    });

    testWidgets('creating it returns the new ledger', (tester) async {
      LedgerAccount? got;
      await open(tester, nature: 'expense', done: (l) => got = l);
      await tester.tap(find.byKey(const Key('quick-ledger-save')));
      await tester.pumpAndSettle();
      expect(got?.name, 'Lift AMC');
      expect(got?.groupId, 'g2');
    });
  });
}
