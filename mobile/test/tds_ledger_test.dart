import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/accounts/data/tds_ledger_api.dart';
import 'package:ar_society_app/features/accounts/presentation/screens/tds_ledger_screen.dart';
import 'package:ar_society_app/features/auth/domain/entities/user_entity.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';

Map<String, dynamic> _statement(String name, Map<String, String> closing, List<Map<String, dynamic>> lines) => {
      'account': {'id': 'a', 'name': name, 'code': '1'},
      'opening': {'amount': '0.00', 'type': 'Dr'},
      'closing': closing,
      'total_debit': '1200.00',
      'total_credit': '2500.00',
      'lines': lines,
    };

Map<String, dynamic> _report({String excess = '0.00'}) => {
      'date_from': '2026-04-01',
      'date_to': '2026-09-30',
      'to_pay': '1300.00',
      'excess_deposited': excess,
      'to_receive': '90.00',
      'receivable_over_adjusted': '0.00',
      'payable_quarters': [
        {'quarter': 'Q1 Apr–Jun 2026-27', 'credit': '2000.00', 'debit': '0.00', 'net': '2000.00'},
        {'quarter': 'Q2 Jul–Sep 2026-27', 'credit': '500.00', 'debit': '1200.00', 'net': '-700.00'},
      ],
      'receivable_quarters': [],
      'payable': _statement('TDS Payable', {'amount': '1300.00', 'type': 'Cr'}, [
        {
          'date': '2026-05-10', 'voucher_number': 'JV/2026-27/0001', 'voucher_id': 'v1', 'particulars': 'Security Charges',
          'narration': 'TDS on guard agency', 'debit': '0.00', 'credit': '2000.00', 'balance': {'amount': '2000.00', 'type': 'Cr'},
        },
      ]),
      'receivable': _statement('TDS Receivable', {'amount': '90.00', 'type': 'Dr'}, []),
    };

void main() {
  testWidgets('the TDS ledger shows what to pay and what to receive, by quarter, with both ledgers', (t) async {
    t.view.physicalSize = const Size(420, 2600);
    t.view.devicePixelRatio = 1.0;
    addTearDown(t.view.resetPhysicalSize);
    addTearDown(t.view.resetDevicePixelRatio);
    final report = TdsLedger.fromJson(_report(excess: '50.00'));
    await t.pumpWidget(ProviderScope(
      overrides: [
        currentUserProvider.overrideWithValue(
            const UserEntity(id: 'u', email: 'u@t.com', fullName: 'U', roles: ['Manager'], societyId: 's1')),
        tdsLedgerProvider.overrideWith((ref, key) async => report),
      ],
      child: MaterialApp(theme: AppTheme.lightTheme, home: const TdsLedgerScreen()),
    ));
    await t.pumpAndSettle();

    expect(find.byKey(const Key('tds-to-pay')), findsOneWidget);
    expect(t.widget<Text>(find.byKey(const Key('tds-to-pay'))).data, contains('1,300'));
    expect(t.widget<Text>(find.byKey(const Key('tds-to-receive'))).data, contains('90'));
    expect(find.byKey(const Key('tds-excess')), findsOneWidget);
    expect(find.text('Q1 Apr–Jun 2026-27'), findsOneWidget);
    expect(find.text('TDS Payable'), findsOneWidget);
    expect(find.text('TDS Receivable'), findsOneWidget);
    expect(find.text('TDS on guard agency'), findsOneWidget);
    expect(find.text('No entries in this period'), findsOneWidget);
  });
}
