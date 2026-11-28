import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/auth/domain/entities/user_entity.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/features/maintenance_billing/data/maintenance_billing_api.dart';
import 'package:ar_society_app/features/maintenance_billing/presentation/providers/maintenance_billing_providers.dart';
import 'package:ar_society_app/features/maintenance_billing/presentation/screens/billing_cycle_screen.dart';

const _admin = UserEntity(id: 'u', email: 'u@t.com', fullName: 'U', roles: ['Society Admin'], societyId: 's1');

class _FakeBilling extends MaintenanceBillingApi {
  _FakeBilling() : super(dio: Dio());
  final calls = <Map<String, Object?>>[];
  BillingCycle cycle = BillingCycle.fromJson({
    'id': 'c1', 'name': 'October 2026 Maintenance', 'cycle_start': '2026-10-01', 'cycle_end': '2026-10-31',
    'due_date': '2026-11-05', 'frequency': 'monthly', 'is_finalized': true, 'bills_count': 3, 'paid_count': 2,
    'issued_count': 3, 'issued_billed': '1000', 'total_billed': '1000',
  });

  @override
  Future<BillingCycle> getCycle(String cycleId) async => cycle;

  @override
  Future<List<MaintenanceBill>> cycleBills(String cycleId) async => const [];

  @override
  Future<({BillingCycle cycle, int billsMoved})> updateCycle(String cycleId,
      {String? name, DateTime? cycleStart, DateTime? cycleEnd}) async {
    calls.add({'name': name, 'start': cycleStart, 'end': cycleEnd});
    cycle = BillingCycle.fromJson({
      'id': 'c1', 'name': name ?? cycle.name, 'cycle_start': '2026-09-01', 'cycle_end': '2026-09-30',
      'due_date': '2026-11-05', 'frequency': 'monthly', 'is_finalized': true, 'bills_count': 3, 'paid_count': 2,
      'issued_count': 3, 'issued_billed': '1000', 'total_billed': '1000',
    });
    return (cycle: cycle, billsMoved: 3);
  }
}

void main() {
  testWidgets('a cycle made under the wrong month can be renamed and given its right period', (t) async {
    t.view.physicalSize = const Size(900, 3000);
    t.view.devicePixelRatio = 1.0;
    addTearDown(t.view.resetPhysicalSize);
    addTearDown(t.view.resetDevicePixelRatio);
    final api = _FakeBilling();
    await t.pumpWidget(ProviderScope(
      overrides: [
        currentUserProvider.overrideWithValue(_admin),
        maintenanceBillingApiProvider.overrideWithValue(api),
      ],
      child: MaterialApp(
        theme: AppTheme.lightTheme,
        home: const BillingCycleScreen(cycleId: 'c1', societyId: 's1'),
      ),
    ));
    await t.pumpAndSettle();

    await t.tap(find.byKey(const Key('cycle-edit')));
    await t.pumpAndSettle();
    expect(find.text('Correct this cycle'), findsOneWidget);
    expect(find.text('From 1 Oct 2026'), findsOneWidget);
    await t.enterText(find.byKey(const Key('cycle-edit-name')), 'September 2026 Maintenance');
    await t.tap(find.byKey(const Key('cycle-edit-start')));
    await t.pumpAndSettle();
    // the date picker opens on the current start: pick the 1st of the month before, by stepping back a month
    await t.tap(find.byIcon(Icons.chevron_left));
    await t.pumpAndSettle();
    await t.tap(find.text('1').first);
    await t.tap(find.text('OK'));
    await t.pumpAndSettle();
    await t.tap(find.byKey(const Key('cycle-edit-end')));
    await t.pumpAndSettle();
    await t.tap(find.byIcon(Icons.chevron_left));
    await t.pumpAndSettle();
    await t.tap(find.text('30'));
    await t.tap(find.text('OK'));
    await t.pumpAndSettle();
    await t.tap(find.byKey(const Key('cycle-edit-save')));
    await t.pumpAndSettle();

    expect(api.calls, hasLength(1));
    expect(api.calls.single['name'], 'September 2026 Maintenance');
    expect(api.calls.single['start'], DateTime(2026, 9, 1));
    expect(api.calls.single['end'], DateTime(2026, 9, 30));
    expect(find.textContaining('3 bills moved'), findsOneWidget);
  });
}
