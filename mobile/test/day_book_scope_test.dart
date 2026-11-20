import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/accounts/data/accounts_api.dart';
import 'package:ar_society_app/features/accounts/presentation/providers/accounts_providers.dart';
import 'package:ar_society_app/features/accounts/presentation/screens/day_book_screen.dart';
import 'package:ar_society_app/features/accounts/presentation/widgets/accounts_widgets.dart';
import 'package:ar_society_app/features/auth/domain/entities/user_entity.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';

Voucher _voucher(String id, String number, String type, String scope) => Voucher.fromJson({
      'id': id,
      'voucher_type': type,
      'voucher_number': number,
      'voucher_date': '2026-11-10',
      'amount': '500.00',
      'scope': scope,
      'is_auto': false,
      'is_cancelled': false,
      'entries': [
        {'account_id': 'a1', 'account_name': 'Bank', 'debit': '500.00', 'credit': '0'},
        {'account_id': 'a2', 'account_name': 'Ledger', 'debit': '0', 'credit': '500.00'},
      ],
    });

final _all = [
  _voucher('v1', 'BV/2026-27/0001', 'bill', 'members'),
  _voucher('v2', 'PV/2026-27/0001', 'payment', 'society'),
];

void main() {
  testWidgets('the Day Book tells residents\' vouchers from the society\'s operations, and can show either on its own', (t) async {
    t.view.physicalSize = const Size(420, 1600);
    t.view.devicePixelRatio = 1.0;
    addTearDown(t.view.resetPhysicalSize);
    addTearDown(t.view.resetDevicePixelRatio);
    final asked = <String?>[];
    await t.pumpWidget(ProviderScope(
      overrides: [
        currentUserProvider.overrideWithValue(const UserEntity(
            id: 'u', email: 'a@t.com', fullName: 'Asha', roles: ['Manager'], societyId: 's1', termsAccepted: true)),
        vouchersProvider.overrideWith((ref, k) async {
          asked.add(k.scope);
          return _all.where((v) => k.scope == null || v.scope == k.scope).toList();
        }),
      ],
      child: MaterialApp(theme: AppTheme.lightTheme, home: const DayBookScreen()),
    ));
    await t.pumpAndSettle();

    // everything at first, and each voucher says which kind it is
    expect(asked, [null]);
    expect(find.text('BV/2026-27/0001'), findsOneWidget);
    expect(find.text('PV/2026-27/0001'), findsOneWidget);
    expect(find.byType(VoucherScopeChip), findsNWidgets(2));

    await t.tap(find.byKey(const Key('scope-members')));
    await t.pumpAndSettle();
    expect(asked.last, 'members');
    expect(find.text('BV/2026-27/0001'), findsOneWidget);
    expect(find.text('PV/2026-27/0001'), findsNothing);

    await t.tap(find.byKey(const Key('scope-society')));
    await t.pumpAndSettle();
    expect(asked.last, 'society');
    expect(find.text('PV/2026-27/0001'), findsOneWidget);
    expect(find.text('BV/2026-27/0001'), findsNothing);

    await t.tap(find.byKey(const Key('scope-all')));
    await t.pumpAndSettle();
    expect(asked.last, isNull);
    expect(find.byType(VoucherScopeChip), findsNWidgets(2));
  });
}
