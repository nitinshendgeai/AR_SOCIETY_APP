import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/accounts/data/accounts_api.dart';
import 'package:ar_society_app/features/accounts/presentation/providers/accounts_providers.dart';
import 'package:ar_society_app/features/accounts/presentation/screens/accounts_screen.dart';
import 'package:ar_society_app/features/accounts/presentation/widgets/accounts_catalogue.dart';
import 'package:ar_society_app/features/auth/domain/entities/user_entity.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';

Future<void> _loadInter() async {
  final loader = FontLoader('Inter')
    ..addFont(Future.value(ByteData.sublistView(File('assets/fonts/Inter-Variable.ttf').readAsBytesSync())));
  await loader.load();
}

void main() {
  setUpAll(_loadInter);

  testWidgets('on a phone the Accounts page links straight to every register and report', (t) async {
    t.view.physicalSize = const Size(420, 4200);
    t.view.devicePixelRatio = 1.0;
    addTearDown(t.view.resetPhysicalSize);
    addTearDown(t.view.resetDevicePixelRatio);
    final summary = AccountsSummary.fromJson({'fy': '2026-27'});
    await t.pumpWidget(ProviderScope(
      overrides: [
        currentUserProvider.overrideWithValue(
            const UserEntity(id: 'u', email: 'u@t.com', fullName: 'U', roles: ['Manager'], societyId: 's1')),
        accountsSummaryProvider.overrideWith((ref, id) async => summary),
      ],
      child: MaterialApp(theme: AppTheme.lightTheme, home: const AccountsScreen()),
    ));
    await t.pumpAndSettle();
    for (final label in [
      'Receipt', 'Payment', 'Contra', 'Journal', 'Trial Balance', 'Balance Sheet', 'Income & Expenditure',
      'Receipts & Payments', 'Rental Register', 'Staff Attendance Register', 'Petty Cash Book', 'TDS Ledger',
      'Depreciation',
    ]) {
      expect(find.text(label), findsOneWidget, reason: label);
    }
  });

  testWidgets('typing in Find narrows the page to the matching reports and forms', (t) async {
    t.view.physicalSize = const Size(420, 4200);
    t.view.devicePixelRatio = 1.0;
    addTearDown(t.view.resetPhysicalSize);
    addTearDown(t.view.resetDevicePixelRatio);
    final summary = AccountsSummary.fromJson({'fy': '2026-27'});
    await t.pumpWidget(ProviderScope(
      overrides: [
        currentUserProvider.overrideWithValue(
            const UserEntity(id: 'u', email: 'u@t.com', fullName: 'U', roles: ['Manager'], societyId: 's1')),
        accountsSummaryProvider.overrideWith((ref, id) async => summary),
      ],
      child: MaterialApp(theme: AppTheme.lightTheme, home: const AccountsScreen()),
    ));
    await t.pumpAndSettle();
    await t.enterText(find.byKey(const Key('accounts-find')), 'balance');
    await t.pumpAndSettle();
    expect(find.text('Balance Sheet'), findsOneWidget);
    expect(find.text('Trial Balance'), findsOneWidget);
    expect(find.text('Day Book'), findsNothing);
    expect(find.text('Bank Balance'), findsNothing); // the figures make way for the results

    await t.enterText(find.byKey(const Key('accounts-find')), 'zzz');
    await t.pumpAndSettle();
    expect(find.textContaining('Nothing called'), findsOneWidget);
  });

  test('the catalogue: every report opens on the year, every entry has a route, search by other words', () {
    final all = accountsCatalogue(fy: '2026-27');
    expect(all.map((e) => e.section).toSet(), kAccountsSections.toSet());
    expect(all.every((e) => e.route.startsWith('/')), isTrue);
    expect(all.map((e) => e.title).toSet().length, all.length, reason: 'no duplicate names');
    expect(all.firstWhere((e) => e.title == 'Balance Sheet').route, '/accounts/statements/balance-sheet?fy=2026-27');
    expect(all.where((e) => e.matches('p&l')).map((e) => e.title), ['Income & Expenditure']);
    expect(all.where((e) => e.matches('RENTAL')).map((e) => e.title), ['Rental Register']);
    expect(accountsCatalogue(fy: '2026-27', vendorBills: false).any((e) => e.title == 'Vendor Bills'), isFalse);
  });
}
