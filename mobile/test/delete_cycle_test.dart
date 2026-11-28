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

BillingCycle _cycle(String id, String name, {required bool canDelete, bool finalized = false, int bills = 0}) =>
    BillingCycle.fromJson({
      'id': id, 'name': name, 'cycle_start': '2030-06-01', 'cycle_end': '2030-06-30', 'due_date': '2030-06-10',
      'frequency': 'monthly', 'is_finalized': finalized, 'can_delete': canDelete, 'bills_count': bills,
      'generated_count': bills,
    });

class _FakeBilling extends MaintenanceBillingApi {
  _FakeBilling() : super(dio: Dio());
  final deleted = <String>[];
  final cycles = [
    _cycle('c-open', 'June 2030', canDelete: true, finalized: true, bills: 12),
    _cycle('c-empty', 'July 2030', canDelete: true),
    _cycle('c-issued', 'May 2030', canDelete: false, finalized: true, bills: 12),
  ];

  @override
  Future<List<BillingCycle>> listCycles(String societyId) async => [...cycles];

  final renamed = <({String id, String? name})>[];

  @override
  Future<({BillingCycle cycle, int billsMoved})> updateCycle(String cycleId,
      {String? name, DateTime? cycleStart, DateTime? cycleEnd}) async {
    renamed.add((id: cycleId, name: name));
    final i = cycles.indexWhere((c) => c.id == cycleId);
    final old = cycles[i];
    cycles[i] = BillingCycle.fromJson({
      'id': old.id, 'name': name ?? old.name, 'cycle_start': '2030-06-01', 'cycle_end': '2030-06-30',
      'due_date': '2030-06-10', 'frequency': 'monthly', 'is_finalized': old.isFinalized,
      'can_delete': old.canDelete, 'bills_count': old.billsCount, 'generated_count': old.generatedCount,
    });
    return (cycle: cycles[i], billsMoved: 0);
  }

  @override
  Future<int> deleteCycle(String cycleId) async {
    deleted.add(cycleId);
    final gone = cycles.firstWhere((c) => c.id == cycleId);
    cycles.remove(gone);
    return gone.billsCount;
  }
}

void main() {
  testWidgets('only a cycle that has not been billed can be deleted, after asking', (t) async {
    t.view.physicalSize = const Size(500, 3000);
    t.view.devicePixelRatio = 1.0;
    addTearDown(t.view.resetPhysicalSize);
    addTearDown(t.view.resetDevicePixelRatio);
    final api = _FakeBilling();
    await t.pumpWidget(ProviderScope(
      overrides: [
        currentUserProvider.overrideWithValue(_admin),
        maintenanceBillingApiProvider.overrideWithValue(api),
        chargeHeadsProvider.overrideWith((ref, id) async => const <ChargeHead>[]),
      ],
      child: MaterialApp(theme: AppTheme.lightTheme, home: const MaintenanceBillingScreen()),
    ));
    await t.pumpAndSettle();

    expect(find.byKey(const ValueKey('cycle-delete-c-open')), findsOneWidget);
    expect(find.byKey(const ValueKey('cycle-delete-c-empty')), findsOneWidget);
    expect(find.byKey(const ValueKey('cycle-delete-c-issued')), findsNothing);           // issued: no delete

    await t.tap(find.byKey(const ValueKey('cycle-delete-c-open')));
    await t.pumpAndSettle();
    expect(find.text('Delete June 2030?'), findsOneWidget);
    expect(find.textContaining('its 12 unissued bills'), findsOneWidget);
    await t.tap(find.text('Keep it'));                                                    // nothing happens
    await t.pumpAndSettle();
    expect(api.deleted, isEmpty);

    await t.tap(find.byKey(const ValueKey('cycle-delete-c-open')));
    await t.pumpAndSettle();
    await t.tap(find.text('Delete cycle'));
    await t.pumpAndSettle();
    expect(api.deleted, ['c-open']);
    expect(find.text('June 2030'), findsNothing);                                         // gone from the list
    expect(find.text('July 2030'), findsOneWidget);
    expect(find.text('May 2030'), findsOneWidget);
  });

  testWidgets('every cycle in the list can be renamed, billed or not', (t) async {
    t.view.physicalSize = const Size(500, 3000);
    t.view.devicePixelRatio = 1.0;
    addTearDown(t.view.resetPhysicalSize);
    addTearDown(t.view.resetDevicePixelRatio);
    final api = _FakeBilling();
    await t.pumpWidget(ProviderScope(
      overrides: [
        currentUserProvider.overrideWithValue(_admin),
        maintenanceBillingApiProvider.overrideWithValue(api),
        chargeHeadsProvider.overrideWith((ref, id) async => const <ChargeHead>[]),
      ],
      child: MaterialApp(theme: AppTheme.lightTheme, home: const MaintenanceBillingScreen()),
    ));
    await t.pumpAndSettle();

    for (final id in ['c-open', 'c-empty', 'c-issued']) {
      expect(find.byKey(ValueKey('cycle-edit-$id')), findsOneWidget, reason: id);
    }
    await t.tap(find.byKey(const ValueKey('cycle-edit-c-issued')));          // the issued one: only the edit, no delete
    await t.pumpAndSettle();
    expect(find.text('Correct this cycle'), findsOneWidget);
    await t.enterText(find.byKey(const Key('cycle-edit-name')), 'April 2030 Maintenance');
    await t.tap(find.byKey(const Key('cycle-edit-save')));
    await t.pumpAndSettle();
    expect(api.renamed, [(id: 'c-issued', name: 'April 2030 Maintenance')]);
    expect(find.text('April 2030 Maintenance'), findsOneWidget);
    expect(find.text('May 2030'), findsNothing);
  });
}
