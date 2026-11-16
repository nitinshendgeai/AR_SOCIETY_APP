import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/accounts/data/depreciation_api.dart';
import 'package:ar_society_app/features/accounts/presentation/screens/depreciation_screen.dart';
import 'package:ar_society_app/features/auth/domain/entities/user_entity.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';

final _schedule = DepreciationSchedule.fromJson({
  'fy': '2026-27',
  'rows': [
    {
      'asset_id': 'a1', 'asset_code': 'AST-001', 'name': 'Terrace pump', 'category': 'pump', 'method': 'wdv', 'rate': '15.00',
      'start': '2026-04-01', 'stop': null, 'days': 365, 'cost': '100000.00', 'additions': '100000.00', 'opening_wdv': '100000.00',
      'depreciation': '15000.00', 'closing_wdv': '85000.00', 'opening_accumulated': '0.00', 'closing_accumulated': '15000.00',
    },
  ],
  'totals': {
    'cost': '100000.00', 'additions': '100000.00', 'opening_wdv': '100000.00', 'depreciation': '15000.00',
    'closing_wdv': '85000.00', 'opening_accumulated': '0.00', 'closing_accumulated': '15000.00',
  },
  'ledgers': [],
  'journal': {
    'debit': {'ledger': 'Depreciation', 'amount': '15000.00'},
    'credits': [{'ledger': 'Plant & Machinery (Lift, Pumps, DG)', 'amount': '15000.00'}],
  },
  'problems': [
    {'asset_id': 'a2', 'asset_code': 'AST-002', 'name': 'Mystery box', 'issues': ['No purchase cost']},
  ],
});

final _rules = [
  const DepreciationRule(id: 'r1', category: 'pump', method: 'wdv', rate: 15, salvagePercent: 0, lifeYears: null),
  const DepreciationRule(id: 'r2', category: 'furniture', method: 'slm', rate: 10, salvagePercent: 5, lifeYears: 10),
];

final _assets = [
  AssetDepreciationSetting.fromJson({
    'asset_id': 'a1', 'asset_code': 'AST-001', 'name': 'Terrace pump', 'category': 'pump', 'status': 'active', 'purchase_date': '2026-04-01',
    'cost': '100000.00', 'depreciate': true, 'method': 'wdv', 'rate': '15.00', 'life_years': null, 'salvage': '0.00',
    'start_on': '2026-04-01', 'stop_on': null, 'own': null, 'problems': [],
  }),
  AssetDepreciationSetting.fromJson({
    'asset_id': 'a2', 'asset_code': 'AST-002', 'name': 'Mystery box', 'category': 'other', 'status': 'active', 'purchase_date': null,
    'cost': '0.00', 'depreciate': true, 'method': 'wdv', 'rate': '15.00', 'life_years': null, 'salvage': '0.00',
    'start_on': null, 'stop_on': null, 'own': null, 'problems': ['No purchase cost', 'No purchase or start date'],
  }),
];

Widget _app(String role) => ProviderScope(
      overrides: [
        currentUserProvider.overrideWithValue(UserEntity(id: 'u', email: 'u@t.com', fullName: 'U', roles: [role], societyId: 's1')),
        depreciationScheduleProvider.overrideWith((ref, key) async => _schedule),
        depreciationRulesProvider.overrideWith((ref, id) async => _rules),
        depreciationAssetsProvider.overrideWith((ref, id) async => _assets),
      ],
      child: MaterialApp(theme: AppTheme.lightTheme, home: DepreciationScreen(today: DateTime(2026, 11, 16))),
    );

void _size(WidgetTester t) {
  t.view.physicalSize = const Size(420, 2600);
  t.view.devicePixelRatio = 1.0;
  addTearDown(t.view.resetPhysicalSize);
  addTearDown(t.view.resetDevicePixelRatio);
}

void main() {
  test('the financial year label', () {
    expect(financialYearLabel(2026), '2026-27');
    expect(financialYearLabel(2099), '2099-00');
  });

  testWidgets('the schedule shows each asset, the journal that would book it, and what is left out', (t) async {
    _size(t);
    await t.pumpWidget(_app('Manager'));
    await t.pumpAndSettle();
    expect(find.text('Terrace pump'), findsOneWidget);
    expect(find.textContaining('15,000'), findsWidgets);
    expect(find.text('Journal to book this year'), findsOneWidget);
    expect(find.textContaining('Dr  Depreciation'), findsOneWidget);
    expect(find.textContaining('Nothing has been posted'), findsOneWidget);
    expect(find.text('Left out until their setup is complete'), findsOneWidget);
    expect(find.textContaining('No purchase cost'), findsOneWidget);
    expect(find.byKey(const Key('dep-fy-2026')), findsOneWidget);
  });

  testWidgets('the setup lists the kinds of asset and the assets, and the committee can edit a kind', (t) async {
    _size(t);
    await t.pumpWidget(_app('Society Admin'));
    await t.pumpAndSettle();
    await t.tap(find.text('Setup'));
    await t.pumpAndSettle();
    expect(find.byKey(const Key('dep-rule-pump')), findsOneWidget);
    expect(find.textContaining('Straight line (SLM) · 10%'), findsOneWidget);
    expect(find.textContaining('keeps 5% of cost'), findsOneWidget);
    expect(find.text('No purchase or start date'), findsOneWidget);
    await t.tap(find.byKey(const Key('dep-rule-pump')));
    await t.pumpAndSettle();
    expect(find.byKey(const Key('dep-rate')), findsOneWidget);
    expect(find.text('Save'), findsOneWidget);
  });

  testWidgets('a manager can read the setup but not change it', (t) async {
    _size(t);
    await t.pumpWidget(_app('Manager'));
    await t.pumpAndSettle();
    await t.tap(find.text('Setup'));
    await t.pumpAndSettle();
    expect(find.byKey(const Key('dep-rule-pump')), findsOneWidget);
    expect(find.byIcon(Icons.edit_outlined), findsNothing);
    await t.tap(find.byKey(const Key('dep-rule-pump')));
    await t.pumpAndSettle();
    expect(find.byKey(const Key('dep-rate')), findsNothing);
  });
}
