import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/accounts/data/accounts_api.dart';
import 'package:ar_society_app/features/accounts/presentation/providers/accounts_providers.dart';
import 'package:ar_society_app/features/accounts/presentation/screens/voucher_form_screen.dart';
import 'package:ar_society_app/features/auth/domain/entities/user_entity.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';

LedgerAccount _l(String id, String name, {String? key, bool bank = false, bool def = false}) => LedgerAccount.fromJson({
      'id': id,
      'group_id': 'g',
      'group_name': 'G',
      'name': name,
      'system_key': key,
      'is_bank': bank,
      'is_default_bank': def,
      'is_active': true,
      'opening_balance': '0',
      'opening_type': 'dr',
    });

class _Fake extends AccountsApi {
  _Fake() : super(dio: Dio());
}

Future<void> _open(WidgetTester t, String type) async {
  t.view.physicalSize = const Size(390, 1800);
  t.view.devicePixelRatio = 1;
  addTearDown(t.view.reset);
  await t.pumpWidget(ProviderScope(
    overrides: [
      currentUserProvider.overrideWithValue(const UserEntity(
          id: 'u', email: 'u@t.com', fullName: 'U', roles: ['Manager'], societyId: 's1', termsAccepted: true)),
      ledgersProvider.overrideWith((ref, id) async => [
            _l('bank', 'Bank Account', bank: true, def: true),
            _l('dues', "Members' Dues", key: 'members_dues'),
            _l('int', 'Interest Income'),
          ]),
      membersLedgerProvider.overrideWith((ref, id) async => throw Exception('not needed')),
      nextVoucherNumberProvider.overrideWith((ref, k) async => 'RV/1'),
      accountsApiProvider.overrideWithValue(_Fake()),
    ],
    child: MaterialApp.router(
      theme: AppTheme.lightTheme,
      routerConfig: GoRouter(routes: [GoRoute(path: '/', builder: (_, __) => VoucherFormScreen(type: type))]),
    ),
  ));
  await t.pumpAndSettle();
}

Future<void> _pickLedger(WidgetTester t, String name) async {
  await t.tap(find.text('Choose ledger').first);
  await t.pumpAndSettle();
  await t.tap(find.text(name).last);
  await t.pumpAndSettle();
}

void main() {
  testWidgets('a Receipt line on Members\' Dues says a resident\'s payment belongs in Online Payments', (t) async {
    await _open(t, 'receipt');
    expect(find.textContaining('Online Payments'), findsNothing);
    await _pickLedger(t, "Members' Dues");
    expect(find.textContaining("A resident's payment is recorded in Online Payments"), findsOneWidget);
  });

  testWidgets('an income line on a Receipt does not carry the note', (t) async {
    await _open(t, 'receipt');
    await _pickLedger(t, 'Interest Income');
    expect(find.textContaining('Online Payments'), findsNothing);
  });
}
