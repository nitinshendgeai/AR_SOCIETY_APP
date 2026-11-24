import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/auth/domain/entities/user_entity.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/features/maintenance_billing/data/maintenance_billing_api.dart';
import 'package:ar_society_app/features/maintenance_billing/presentation/providers/maintenance_billing_providers.dart';
import 'package:ar_society_app/features/maintenance_billing/presentation/screens/maintenance_billing_screen.dart';

const _admin = UserEntity(id: 'u', email: 'u@t.com', fullName: 'U', roles: ['Society Admin'], societyId: 's1');

class _FakeApi extends MaintenanceBillingApi {
  _FakeApi() : super(dio: Dio());

  final List<Map<String, dynamic>> saved = [];

  @override
  Future<MaintenanceRules> updateRules(String societyId, Map<String, dynamic> changes) async {
    saved.add(changes);
    return MaintenanceRules(
      roundToRupee: changes['round_to_rupee'] as bool? ?? false,
      roundUpStep: changes['round_up_step'] as int? ?? 0,
    );
  }
}

/// What a server sends for a society: the form needs a construction cost to be valid.
MaintenanceRules _rules({bool roundToRupee = false, int roundUpStep = 0}) =>
    MaintenanceRules(constructionCostPerSqft: '1500', roundToRupee: roundToRupee, roundUpStep: roundUpStep);

void main() {
  test('rounding up to the next 50 is off unless the server says so', () {
    expect(MaintenanceRules.fromJson({}).roundUpStep, 0);
    expect(MaintenanceRules.fromJson({'round_up_step': 0}).roundUpStep, 0);
    expect(MaintenanceRules.fromJson({'round_up_step': 50}).roundUpStep, 50);
  });

  Future<_FakeApi> openRules(WidgetTester t, MaintenanceRules rules) async {
    t.view.physicalSize = const Size(900, 6000);
    t.view.devicePixelRatio = 1.0;
    addTearDown(t.view.resetPhysicalSize);
    addTearDown(t.view.resetDevicePixelRatio);
    final api = _FakeApi();
    await t.pumpWidget(ProviderScope(
      overrides: [
        currentUserProvider.overrideWithValue(_admin),
        maintenanceBillingApiProvider.overrideWithValue(api),
        billingCyclesProvider.overrideWith((ref, id) async => const <BillingCycle>[]),
        chargeHeadsProvider.overrideWith((ref, id) async => const <ChargeHead>[]),
        maintenanceRulesProvider.overrideWith((ref, id) async => rules),
      ],
      child: MaterialApp(theme: AppTheme.lightTheme, home: const MaintenanceBillingScreen()),
    ));
    await t.pumpAndSettle();
    await t.tap(find.text('Rules'));
    await t.pumpAndSettle();
    return api;
  }

  testWidgets('the rounding choice shows what is set now: none, nearest rupee, or up to 50', (t) async {
    await openRules(t, _rules());
    expect(find.text('Round each bill'), findsOneWidget);
    expect(tester(t, 'round-off').groupValue, 'off');
  });

  testWidgets('a society that rounds to the rupee sees that chosen', (t) async {
    await openRules(t, _rules(roundToRupee: true));
    expect(tester(t, 'round-rupee').groupValue, 'rupee');
  });

  testWidgets('a society that rounds up to 50 sees that chosen, and it wins over the rupee', (t) async {
    await openRules(t, _rules(roundToRupee: true, roundUpStep: 50));
    expect(tester(t, 'round-up50').groupValue, 'up50');
  });

  testWidgets('choosing up to the next 50 saves the step and turns the rupee rounding off', (t) async {
    final api = await openRules(t, _rules(roundToRupee: true));
    await t.ensureVisible(find.byKey(const ValueKey('round-up50')));
    await t.tap(find.byKey(const ValueKey('round-up50')));
    await t.pumpAndSettle();
    await t.ensureVisible(find.text('Save Rules'));
    await t.tap(find.text('Save Rules'));
    await t.pumpAndSettle();
    expect(api.saved.single['round_up_step'], 50);
    expect(api.saved.single['round_to_rupee'], isFalse);
  });

  testWidgets('choosing the nearest rupee saves that, with no step', (t) async {
    final api = await openRules(t, _rules(roundUpStep: 50));
    await t.ensureVisible(find.byKey(const ValueKey('round-rupee')));
    await t.tap(find.byKey(const ValueKey('round-rupee')));
    await t.pumpAndSettle();
    await t.ensureVisible(find.text('Save Rules'));
    await t.tap(find.text('Save Rules'));
    await t.pumpAndSettle();
    expect(api.saved.single['round_to_rupee'], isTrue);
    expect(api.saved.single['round_up_step'], 0);
  });
}

RadioListTile<String> tester(WidgetTester t, String key) =>
    t.widget<RadioListTile<String>>(find.byKey(ValueKey(key)));
