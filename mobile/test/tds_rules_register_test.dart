import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ar_society_app/features/auth/domain/entities/user_entity.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/features/vendor/data/vendor_master_api.dart';
import 'package:ar_society_app/features/vendor/presentation/screens/tds_register_screen.dart';
import 'package:ar_society_app/features/vendor/presentation/screens/tds_rules_screen.dart';

const _admin = UserEntity(id: 'u1', email: 'a@b.c', fullName: 'Asha', roles: ['Society Admin'], societyId: 's1', termsAccepted: true);
const _manager = UserEntity(id: 'u2', email: 'm@b.c', fullName: 'Manu', roles: ['Manager'], societyId: 's1', termsAccepted: true);

Map<String, dynamic> _rule(String id, String name, String section, String klass, String rate, String? yearly, String? single,
        {bool active = true}) =>
    {
      'id': id, 'code': 'TDS-$section-$klass', 'name': name, 'section': section, 'payee_class': klass, 'rate': rate,
      'yearly_limit': yearly, 'single_limit': single, 'effective_from': '2025-04-01', 'effective_to': null,
      'is_active': active, 'notes': null,
    };

class _Saved {
  final String id, rate;
  final String? yearly, single;
  final bool active;
  _Saved(this.id, this.rate, this.yearly, this.single, this.active);
}

class _FakeApi extends VendorMasterApi {
  _FakeApi() : super(dio: Dio());
  final saved = <_Saved>[];
  final asked = <(DateTime, DateTime)>[];

  @override
  Future<List<TdsRule>> tdsRules(String societyId) async => [
        TdsRule.fromJson(_rule('r1', 'Contract: individual / HUF', '194C', 'individual_huf', '1.0000', '100000.00', '30000.00')),
        TdsRule.fromJson(_rule('r2', 'Professional fees', '194J_PROF', 'any', '10.0000', '50000.00', null)),
        TdsRule.fromJson(_rule('r3', 'Commission / brokerage', '194H', 'any', '2.0000', '20000.00', null, active: false)),
      ];

  @override
  Future<void> updateTdsRule(String id, {required String rate, String? yearlyLimit, String? singleLimit, required bool active}) async {
    saved.add(_Saved(id, rate, yearlyLimit, singleLimit, active));
  }

  @override
  Future<TdsRegister> tdsRegister(String societyId, DateTime from, DateTime to) async {
    asked.add((from, to));
    return TdsRegister.fromJson({
      'total_tds': '6000.00',
      'rows': [
        {'payment_number': 'VPY-0001', 'payment_date': '2026-09-10', 'vendor': 'Sparkle Services', 'pan': 'AABCC1234F',
          'constitution': 'Private Limited company', 'section_label': '194C contract', 'amount_settled': '200000.00',
          'tds_base': '200000.00', 'rate': '2.0000', 'tds_amount': '4000.00', 'net_paid': '196000.00',
          'deposit_due': '2026-10-07', 'note': null},
        {'payment_number': 'VPY-0002', 'payment_date': '2026-03-20', 'vendor': 'No Pan Co', 'pan': null,
          'constitution': null, 'section_label': '194C contract', 'amount_settled': '10000.00',
          'tds_base': '10000.00', 'rate': '20.0000', 'tds_amount': '2000.00', 'net_paid': '8000.00',
          'deposit_due': '2026-04-30', 'note': null},
      ],
    });
  }
}

Widget _app(_FakeApi api, Widget home, {UserEntity user = _admin}) => ProviderScope(
      overrides: [currentUserProvider.overrideWithValue(user), vendorMasterApiProvider.overrideWithValue(api)],
      child: MaterialApp(home: home),
    );

void main() {
  test('a rule reads its rate and kind of vendor plainly', () {
    final r = TdsRule.fromJson(_rule('r', 'x', '194C', 'other', '2.0000', null, null));
    expect((r.rateText, r.payeeLabel), ('2', 'Firm, LLP, company, other'));
    expect(TdsRule.fromJson(_rule('r', 'x', '194H', 'any', '0.5000', null, null)).rateText, '0.5');
    expect(TdsRule.fromJson(_rule('r', 'x', '194H', 'any', '2', null, null)).payeeLabel, 'Everyone');
  });

  testWidgets('the rates list their limits and mark a rule that is switched off', (tester) async {
    await tester.pumpWidget(_app(_FakeApi(), const TdsRulesScreen()));
    await tester.pumpAndSettle();
    expect(find.text('Contract: individual / HUF · 1%'), findsOneWidget);
    expect(find.textContaining('₹1,00,000.00 in the year'), findsOneWidget);
    expect(find.text('Professional fees · 10%'), findsOneWidget);
    expect(find.text('Not in use'), findsOneWidget);
  });

  testWidgets('the committee corrects a rate and a limit', (tester) async {
    final api = _FakeApi();
    tester.view.physicalSize = const Size(800, 1800);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.reset);
    await tester.pumpWidget(_app(api, const TdsRulesScreen()));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Professional fees · 10%'));
    await tester.pumpAndSettle();
    final fields = find.byType(TextFormField);
    await tester.enterText(fields.at(0), '12.5');
    await tester.enterText(fields.at(1), '');
    await tester.enterText(fields.at(2), '25000');
    await tester.tap(find.widgetWithText(FilledButton, 'Save'));
    await tester.pump(const Duration(seconds: 6));
    final s = api.saved.single;
    expect((s.id, s.rate, s.yearly, s.single, s.active), ('r2', '12.5', null, '25000', true));
  });

  testWidgets('a rate outside 0 to 100 is refused before saving', (tester) async {
    final api = _FakeApi();
    tester.view.physicalSize = const Size(800, 1800);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.reset);
    await tester.pumpWidget(_app(api, const TdsRulesScreen()));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Professional fees · 10%'));
    await tester.pumpAndSettle();
    await tester.enterText(find.byType(TextFormField).first, '150');
    await tester.tap(find.widgetWithText(FilledButton, 'Save'));
    await tester.pumpAndSettle();
    expect(find.text('Enter a rate from 0 to 100'), findsOneWidget);
    expect(api.saved, isEmpty);
  });

  testWidgets('a manager reads the rates but cannot change them', (tester) async {
    await tester.pumpWidget(_app(_FakeApi(), const TdsRulesScreen(), user: _manager));
    await tester.pumpAndSettle();
    expect(find.text('Professional fees · 10%'), findsOneWidget);
    expect(find.byIcon(Icons.edit_outlined), findsNothing);
    await tester.tap(find.text('Professional fees · 10%'));
    await tester.pumpAndSettle();
    expect(find.widgetWithText(FilledButton, 'Save'), findsNothing);
  });

  testWidgets('the register opens on this financial year and totals what was deducted', (tester) async {
    final api = _FakeApi();
    await tester.pumpWidget(_app(api, TdsRegisterScreen(today: DateTime(2026, 10, 25))));
    await tester.pumpAndSettle();
    expect(api.asked.single, (DateTime(2026, 4, 1), DateTime(2026, 10, 25)));
    expect(find.text('Total TDS ₹6,000.00'), findsOneWidget);
    expect(find.text('Sparkle Services'), findsOneWidget);
    expect(find.text('Deposit by 7 Oct 2026'), findsOneWidget);
    expect(find.textContaining('No PAN'), findsOneWidget);
  });

  testWidgets('a quarter chip asks for that quarter of the financial year', (tester) async {
    final api = _FakeApi();
    await tester.pumpWidget(_app(api, TdsRegisterScreen(today: DateTime(2026, 10, 25))));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('tds-q-7')));
    await tester.pumpAndSettle();
    expect(api.asked.last, (DateTime(2026, 7, 1), DateTime(2026, 9, 30)));
    await tester.tap(find.byKey(const Key('tds-q-1'))); // Jan–Mar belongs to the same financial year, in 2027
    await tester.pumpAndSettle();
    expect(api.asked.last, (DateTime(2027, 1, 1), DateTime(2027, 3, 31)));
  });

  testWidgets('before April the financial year started the April before', (tester) async {
    final api = _FakeApi();
    await tester.pumpWidget(_app(api, TdsRegisterScreen(today: DateTime(2027, 2, 10))));
    await tester.pumpAndSettle();
    expect(api.asked.single, (DateTime(2026, 4, 1), DateTime(2027, 2, 10)));
  });
}
