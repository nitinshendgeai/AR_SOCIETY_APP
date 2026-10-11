import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/accounts/data/accounts_api.dart';
import 'package:ar_society_app/features/accounts/presentation/providers/accounts_providers.dart';
import 'package:ar_society_app/features/accounts/presentation/screens/voucher_form_screen.dart';
import 'package:ar_society_app/features/auth/domain/entities/user_entity.dart';
import 'package:ar_society_app/features/accounts/presentation/screens/expense_form_screen.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/features/maintenance_billing/data/maintenance_billing_api.dart';
import 'package:ar_society_app/features/maintenance_billing/presentation/providers/maintenance_billing_providers.dart';
import 'package:ar_society_app/shared/widgets/app_form.dart';
import 'package:ar_society_app/shared/widgets/typeahead_field.dart';

void _desktop(WidgetTester t) {
  t.view.physicalSize = const Size(1440, 1000);
  t.view.devicePixelRatio = 1.0;
  addTearDown(t.view.reset);
}

Future<void> _ctrl(WidgetTester t, LogicalKeyboardKey key) async {
  await t.sendKeyDownEvent(LogicalKeyboardKey.controlLeft);
  await t.sendKeyEvent(key);
  await t.sendKeyUpEvent(LogicalKeyboardKey.controlLeft);
  await t.pump();
}

/// The Enter key pressed in whatever field has the focus.
Future<void> _enter(WidgetTester t) async {
  await t.testTextInput.receiveAction(TextInputAction.done);
  await t.pumpAndSettle();
}

class _Host extends StatefulWidget {
  final List<String> options;
  final String? initial;
  final void Function(String) onPicked;
  const _Host({required this.options, this.initial, required this.onPicked});

  @override
  State<_Host> createState() => _HostState();
}

class _HostState extends State<_Host> {
  late String? value = widget.initial;

  @override
  Widget build(BuildContext context) => MaterialApp(
        theme: AppTheme.lightTheme,
        home: Scaffold(
          body: Padding(
            padding: const EdgeInsets.all(24),
            child: Column(children: [
              TypeaheadField<String>(
                options: widget.options,
                value: value,
                label: (s) => s,
                autofocus: true,
                onSelected: (s) {
                  setState(() => value = s);
                  widget.onPicked(s);
                },
              ),
              const SizedBox(height: 12),
              const TextField(key: Key('next')),
            ]),
          ),
        ),
      );
}

bool _focused(WidgetTester t, Key key) =>
    t.widget<EditableText>(find.descendant(of: find.byKey(key), matching: find.byType(EditableText))).focusNode.hasFocus;

void main() {
  const heads = ['Cash in Hand', 'Bank Account', 'Interest Income', 'Water Charges'];

  testWidgets('typing narrows the list, Enter takes the highlighted one and moves to the next field', (t) async {
    final picked = <String>[];
    await t.pumpWidget(_Host(options: heads, onPicked: picked.add));
    await t.pumpAndSettle();
    expect(find.text('Water Charges'), findsOneWidget); // focused: the whole list is open
    await t.enterText(find.byType(TextField).first, 'inter inc');
    await t.pumpAndSettle();
    expect(find.text('Interest Income'), findsOneWidget);
    expect(find.text('Water Charges'), findsNothing);
    await _enter(t);
    expect(picked, ['Interest Income']);
    expect(find.text('Interest Income'), findsOneWidget); // the field shows the choice
    expect(_focused(t, const Key('next')), isTrue);
  });

  testWidgets('with something chosen and nothing typed, Enter just moves on', (t) async {
    final picked = <String>[];
    await t.pumpWidget(_Host(options: heads, initial: 'Bank Account', onPicked: picked.add));
    await t.pumpAndSettle();
    await _enter(t);
    expect(picked, isEmpty);
    expect(_focused(t, const Key('next')), isTrue);
  });

  testWidgets('leaving the field with half a word typed puts the chosen value back', (t) async {
    await t.pumpWidget(_Host(options: heads, initial: 'Bank Account', onPicked: (_) {}));
    await t.pumpAndSettle();
    await t.enterText(find.byType(TextField).first, 'zzz');
    await t.pumpAndSettle();
    expect(find.text('zzz'), findsOneWidget);
    await t.tap(find.byKey(const Key('next')));
    await t.pumpAndSettle();
    expect(find.text('Bank Account'), findsOneWidget);
  });

  testWidgets('Ctrl+S saves and Ctrl+Enter saves and starts the next, but never while a save is running', (t) async {
    _desktop(t);
    var saved = 0, savedNew = 0;
    Widget page({bool saving = false}) => MaterialApp(
          theme: AppTheme.lightTheme,
          home: AppFormPage(
            title: 'Add Thing',
            submitLabel: 'Save thing',
            saving: saving,
            onSubmit: () => saved++,
            onSubmitAndNew: () => savedNew++,
            children: const [FormSection(title: 'Basics', children: [TextField(autofocus: true)])],
          ),
        );
    await t.pumpWidget(page());
    await t.pumpAndSettle();
    await _ctrl(t, LogicalKeyboardKey.keyS);
    await _ctrl(t, LogicalKeyboardKey.enter);
    expect((saved, savedNew), (1, 1));
    await t.pumpWidget(page(saving: true));
    await t.pump();
    await _ctrl(t, LogicalKeyboardKey.keyS);
    expect(saved, 1);
  });

  group('the voucher form by keyboard', () {
    const user = UserEntity(id: 'u', email: 'u@t.com', fullName: 'U', roles: ['Society Admin'], societyId: 's1');
    LedgerAccount ledger(String id, String name, String group,
            {bool cash = false, bool bank = false, bool def = false, String? key}) =>
        LedgerAccount.fromJson({
          'id': id, 'group_id': 'g', 'group_name': group, 'name': name, 'is_cash': cash, 'is_bank': bank,
          'is_default_bank': def, 'system_key': key, 'is_active': true, 'opening_balance': '0', 'opening_type': 'dr',
        });
    final ledgers = [
      ledger('cash', 'Cash in Hand', 'Cash', cash: true),
      ledger('bank', 'Bank Account', 'Bank', bank: true, def: true),
      ledger('int', 'Interest Income', 'Indirect Income'),
      ledger('rent', 'Hall Rent Income', 'Indirect Income'),
    ];

    final calls = <({String type, List<VoucherLineInput> lines, String? narration})>[];
    Widget app() {
      calls.clear();
      return ProviderScope(
        overrides: [
          currentUserProvider.overrideWithValue(user),
          ledgersProvider.overrideWith((ref, id) async => ledgers),
          nextVoucherNumberProvider.overrideWith((ref, k) async => 'RV/2026-27/0001'),
          accountsApiProvider.overrideWithValue(_FakeAccounts((type, lines, narration) {
            calls.add((type: type, lines: lines, narration: narration));
          })),
        ],
        child: MaterialApp.router(
          theme: AppTheme.lightTheme,
          routerConfig: GoRouter(routes: [GoRoute(path: '/', builder: (_, __) => const VoucherFormScreen(type: 'receipt'))]),
        ),
      );
    }

    testWidgets('a receipt is typed, saved with Ctrl+Enter, and the next one starts in the first field', (t) async {
      _desktop(t);
      await t.pumpWidget(app());
      await t.pumpAndSettle();
      // The cursor is already in the ledger of the first line.
      t.testTextInput.enterText('inter');
      await t.pump();
      await t.pumpAndSettle();
      expect(find.text('Hall Rent Income'), findsNothing);
      await _enter(t); // takes "Interest Income", moves to the amount
      t.testTextInput.enterText('450');
      await t.pump();
      await _ctrl(t, LogicalKeyboardKey.enter); // save and add another
      await t.pumpAndSettle();
      expect(calls, hasLength(1));
      expect(calls.single.type, 'receipt');
      final lines = calls.single.lines;
      expect((lines[0].accountId, lines[0].debit), ('bank', 450.0)); // into the default bank account
      expect((lines[1].accountId, lines[1].credit), ('int', 450.0));
      // A clean voucher, the cursor back on the first ledger, ready for the next.
      expect(find.byWidgetPredicate((w) => w is EditableText && w.controller.text == 'Interest Income'), findsNothing);
      t.testTextInput.enterText('hall');
      await t.pump();
      await t.pumpAndSettle();
      await _enter(t);
      t.testTextInput.enterText('1200');
      await _ctrl(t, LogicalKeyboardKey.keyS);
      await t.pumpAndSettle();
      expect(calls, hasLength(2));
      expect(calls[1].lines[1].accountId, 'rent');
    });

    testWidgets('Ctrl+S with nothing entered says what is missing instead of saving', (t) async {
      _desktop(t);
      await t.pumpWidget(app());
      await t.pumpAndSettle();
      await _ctrl(t, LogicalKeyboardKey.keyS);
      await t.pumpAndSettle();
      expect(calls, isEmpty);
    });
  });

  testWidgets('Add Expense by keyboard: type the element, Enter, type the amount, Ctrl+S', (t) async {
    _desktop(t);
    const user = UserEntity(id: 'u', email: 'u@t.com', fullName: 'U', roles: ['Manager'], societyId: 's1');
    LedgerAccount l(String id, String name, String nature, {bool cash = false, String? element}) => LedgerAccount.fromJson({
          'id': id, 'group_id': 'g', 'group_name': 'G', 'name': name, 'nature': nature, 'is_cash': cash,
          'is_active': true, 'opening_balance': '0', 'opening_type': 'dr', 'maintenance_element_id': element,
          'maintenance_element_name': element == null ? null : 'Security Services',
        });
    final ledgers = [l('cash', 'Cash in Hand', 'asset', cash: true), l('sec', 'Security Charges', 'expense', element: 'e1'), l('misc', 'Misc Expense', 'expense')];
    final elements = [
      const MaintenanceElement(id: 'e1', code: 'security', name: 'Security Services', category: 'maintenance', defaultBasis: 'budget_equal'),
      const MaintenanceElement(id: 'e2', code: 'lift', name: 'Lift Maintenance', category: 'maintenance', defaultBasis: 'budget_equal'),
    ];
    final calls = <List<VoucherLineInput>>[];
    await t.pumpWidget(ProviderScope(
      overrides: [
        currentUserProvider.overrideWithValue(user),
        ledgersProvider.overrideWith((ref, id) async => ledgers),
        maintenanceElementsProvider.overrideWith((ref, k) async => elements),
        nextVoucherNumberProvider.overrideWith((ref, k) async => 'PV/1'),
        accountsApiProvider.overrideWithValue(_FakeAccounts((type, lines, narration) => calls.add(lines))),
      ],
      child: MaterialApp.router(
        theme: AppTheme.lightTheme,
        routerConfig: GoRouter(routes: [GoRoute(path: '/', builder: (_, __) => const ExpenseFormScreen())]),
      ),
    ));
    await t.pumpAndSettle();
    t.testTextInput.enterText('secur'); // the cursor starts in "What is it for?"
    await t.pump();
    await _enter(t); // "Security Services"; its one head is chosen for you
    expect(find.byWidgetPredicate((w) => w is EditableText && w.controller.text == 'Security Services'), findsOneWidget);
    expect(find.byWidgetPredicate((w) => w is EditableText && w.controller.text == 'Security Charges'), findsOneWidget);
    await _enter(t); // head already chosen: Enter moves on to the amount
    t.testTextInput.enterText('7200');
    await t.pump();
    await _ctrl(t, LogicalKeyboardKey.keyS);
    await t.pumpAndSettle();
    expect(calls, hasLength(1));
    expect((calls.single[0].accountId, calls.single[0].debit), ('sec', 7200.0));
    expect((calls.single[1].accountId, calls.single[1].credit), ('cash', 7200.0));
  });
}

class _FakeAccounts extends AccountsApi {
  final void Function(String type, List<VoucherLineInput> lines, String? narration) onCreate;
  _FakeAccounts(this.onCreate) : super(dio: Dio());

  @override
  Future<Voucher> createVoucher({
    required String societyId,
    required String type,
    required DateTime date,
    required List<VoucherLineInput> lines,
    String? narration,
    String? reference,
    String? vendorId,
  }) async {
    onCreate(type, lines, narration);
    return Voucher.fromJson({
      'id': 'v1', 'voucher_type': type, 'voucher_number': 'RV/2026-27/0001', 'voucher_date': '2026-10-11',
      'amount': '450', 'approval_status': 'approved',
    });
  }
}
