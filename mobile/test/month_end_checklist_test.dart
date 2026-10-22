import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/accounts/data/accounts_api.dart';
import 'package:ar_society_app/features/accounts/presentation/providers/accounts_providers.dart';
import 'package:ar_society_app/features/auth/domain/entities/user_entity.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/features/maintenance_billing/data/maintenance_billing_api.dart';
import 'package:ar_society_app/features/maintenance_billing/presentation/providers/maintenance_billing_providers.dart';
import 'package:ar_society_app/features/maintenance_billing/presentation/widgets/bill_actual_expenses_sheet.dart';
import 'package:ar_society_app/features/maintenance_billing/presentation/widgets/month_end_checklist.dart';

class _FakeBilling extends MaintenanceBillingApi {
  final List<ChargeHead> heads;
  final List<String> approveCalls = [];
  List<String>? switched;
  final List<String> elementCalls = [];
  _FakeBilling({this.heads = const []}) : super(dio: Dio());

  @override
  Future<({int approved, int leftForAnother})> approvePendingPayments(String societyId,
      {DateTime? from, DateTime? to}) async {
    approveCalls.add('$societyId ${from?.toIso8601String().substring(0, 10)}..${to?.toIso8601String().substring(0, 10)}');
    return (approved: 2, leftForAnother: 1);
  }

  @override
  Future<List<ChargeHead>> listChargeHeads(String societyId) async => heads;

  @override
  Future<List<MaintenanceElement>> listElements(String societyId, {bool includeInactive = false}) async => const [
        MaintenanceElement(id: 'e1', code: 'housekeeping', name: 'Housekeeping', category: 'maintenance',
            defaultBasis: 'fixed'),
        MaintenanceElement(id: 'e2', code: 'security', name: 'Security Services', category: 'maintenance',
            defaultBasis: 'budget_equal'),
      ];

  @override
  Future<BillActualResult> billActualExpenses(String societyId, List<String> chargeIds,
      {List<String> elementIds = const []}) async {
    switched = chargeIds;
    elementCalls.addAll(elementIds);
    return BillActualResult(changed: [for (final h in heads.where((h) => chargeIds.contains(h.id))) h], skipped: const []);
  }
}

class _FakeAccounts extends AccountsApi {
  final List<String> linked = [];
  _FakeAccounts() : super(dio: Dio());
  @override
  Future<LedgerAccount> updateLedger(String id, Map<String, dynamic> changes) async {
    linked.add('$id -> ${changes['maintenance_element_id']}');
    throw StateError('stop');
  }
}

CyclePreview _preview(Map<String, dynamic> readiness) => CyclePreview.fromJson({
      'months': 1, 'flats_count': 3, 'total': '0', 'warnings': [], 'flats': [],
      'cycle_start': '2026-10-01', 'cycle_end': '2026-10-31', 'readiness': readiness,
    });

Widget _wrap(Widget child, {required _FakeBilling billing, _FakeAccounts? accounts}) => ProviderScope(
      overrides: [
        currentUserProvider.overrideWithValue(
            const UserEntity(id: 'u', email: 'u@t.com', fullName: 'U', roles: ['Society Admin'], societyId: 's1')),
        maintenanceBillingApiProvider.overrideWithValue(billing),
        accountsApiProvider.overrideWithValue(accounts ?? _FakeAccounts()),
      ],
      child: MaterialApp(theme: AppTheme.lightTheme, home: Scaffold(body: SingleChildScrollView(child: child))),
    );

ChargeHead _head(String id, String name, String basis, {bool period = false}) => ChargeHead(
      id: id, chargeType: 'maintenance', name: name, basis: basis, defaultAmount: '450', elementId: 'e$id',
      autoFromExpenses: period, expenseMode: period ? 'period' : 'trailing');

void main() {
  void phone(WidgetTester tester) {
    tester.view.physicalSize = const Size(390, 900);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.reset);
  }

  testWidgets('with nothing to flag the checklist says all clear', (tester) async {
    phone(tester);
    await tester.pumpWidget(_wrap(
        MonthEndChecklist(cycleId: 'c1', preview: _preview({'applies': true, 'ready': true})),
        billing: _FakeBilling()));
    expect(find.text('Month-end check: all clear'), findsOneWidget);
    expect(find.byKey(const ValueKey('checklist-approve-all')), findsNothing);
  });

  testWidgets('waiting expenses are approved in one tap, limited to the cycle, and the result is reported',
      (tester) async {
    phone(tester);
    final billing = _FakeBilling();
    await tester.pumpWidget(_wrap(
        MonthEndChecklist(
            cycleId: 'c1',
            preview: _preview({'applies': true, 'ready': false, 'pending_count': 3, 'pending_amount': '1250.00'})),
        billing: billing));
    expect(find.textContaining('3 expense(s)'), findsOneWidget);
    expect(find.textContaining('waiting for approval'), findsOneWidget);
    await tester.tap(find.byKey(const ValueKey('checklist-approve-all')));
    await tester.pump();
    expect(billing.approveCalls, ['s1 2026-10-01..2026-10-31']);
    await tester.pump(const Duration(milliseconds: 300));
    expect(find.textContaining('2 approved'), findsOneWidget);
    expect(find.textContaining('1 you entered yourself'), findsOneWidget);
  });

  testWidgets('an unlinked ledger names its spend and can be linked to an element from the list', (tester) async {
    phone(tester);
    final accounts = _FakeAccounts();
    await tester.pumpWidget(_wrap(
        MonthEndChecklist(
            cycleId: 'c1',
            preview: _preview({
              'applies': true, 'ready': false,
              'unlinked_ledgers': [{'account_id': 'a9', 'name': 'Repairs — Plumbing', 'amount': '800.00'}],
              'uncovered_elements': [
                {'element_id': 'e2', 'element_name': 'Security Services', 'amount': '500.00', 'has_head': false},
                {'element_id': 'e3', 'element_name': 'Lift', 'amount': '90.00', 'has_head': true},
              ],
              'heads_without_spend': ['Lift'],
            })),
        billing: _FakeBilling(), accounts: accounts));
    expect(find.textContaining('Repairs — Plumbing'), findsOneWidget);
    expect(find.textContaining('no maintenance element covers it'), findsOneWidget);
    expect(find.textContaining('Security Services'), findsOneWidget);
    expect(find.textContaining('Lift: nothing spent'), findsOneWidget);
    expect(find.text('Add head'), findsOneWidget);                 // no head yet: one is made
    expect(find.text('Switch head'), findsOneWidget);              // a head exists: it is switched

    await tester.tap(find.byKey(const ValueKey('checklist-link-a9')));
    await tester.pumpAndSettle();
    expect(find.text('Housekeeping'), findsOneWidget);
    await tester.tap(find.byKey(const ValueKey('element-e1')));
    await tester.pumpAndSettle();
    expect(accounts.linked, ['a9 -> e1']);
  });

  testWidgets('an element nobody bills gets a head in one tap', (tester) async {
    phone(tester);
    final billing = _FakeBilling();
    await tester.pumpWidget(_wrap(
        MonthEndChecklist(
            cycleId: 'c1',
            preview: _preview({
              'applies': true, 'ready': false,
              'uncovered_elements': [
                {'element_id': 'e2', 'element_name': 'Security Services', 'amount': '500.00', 'has_head': false}
              ],
            })),
        billing: billing));
    await tester.tap(find.byKey(const ValueKey('checklist-cover-e2')));
    await tester.pump();
    expect(billing.elementCalls, ['e2']);
    await tester.pump(const Duration(milliseconds: 300));
  });

  testWidgets('when no head bills actual expenses the checklist offers to set it up', (tester) async {
    phone(tester);
    await tester.pumpWidget(_wrap(
        MonthEndChecklist(cycleId: 'c1', preview: _preview({'applies': false, 'ready': true})),
        billing: _FakeBilling(heads: [_head('1', 'Housekeeping', 'fixed')])));
    expect(find.textContaining('No charge head bills the actual expenses'), findsOneWidget);
    await tester.tap(find.byKey(const ValueKey('checklist-setup')));
    await tester.pumpAndSettle();
    expect(find.text('Bill actual expenses'), findsOneWidget);
  });

  testWidgets('the bulk sheet pre-ticks yearly-budget heads, leaves typed rates unticked and switches the ticked',
      (tester) async {
    phone(tester);
    final billing = _FakeBilling(heads: [
      _head('1', 'Security', 'budget_equal'),
      _head('2', 'Housekeeping', 'fixed'),
      _head('3', 'Lift', 'budget_area', period: true),
      const ChargeHead(id: '4', chargeType: 'sinking_fund', name: 'Sinking fund', basis: 'construction_cost_pct', elementId: 'x'),
    ]);
    await tester.pumpWidget(_wrap(const BillActualExpensesSheet(societyId: 's1'), billing: billing));
    await tester.pumpAndSettle();

    CheckboxListTile box(String id) => tester.widget(find.byKey(ValueKey('actual-$id')));
    expect(box('1').value, isTrue);                                  // a yearly budget starts ticked
    expect(box('2').value, isFalse);                                 // a typed rate does not
    expect(box('3').value, isTrue);                                  // already on actual expenses...
    expect(box('3').onChanged, isNull);                              // ...and cannot be changed here
    expect(find.byKey(const ValueKey('actual-4')), findsNothing);    // a percentage of construction cost is not offered
    expect(find.text('Switch 1 charge head(s)'), findsOneWidget);

    await tester.tap(find.byKey(const ValueKey('actual-2')));
    await tester.pump();
    expect(find.text('Switch 2 charge head(s)'), findsOneWidget);
    await tester.tap(find.text('Switch 2 charge head(s)'));
    await tester.pumpAndSettle();
    expect(billing.switched!.toSet(), {'1', '2'});
  });
}
