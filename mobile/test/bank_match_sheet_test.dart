import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/features/billing/domain/entities/billing_entities.dart';
import 'package:ar_society_app/features/billing/presentation/providers/billing_providers.dart';
import 'package:ar_society_app/features/billing/presentation/screens/bank_reconciliation_screen.dart';

final _entry = BankStatementEntryEntity(
  id: 'e1',
  societyId: 's1',
  txnDate: DateTime(2026, 10, 8),
  description: 'UPI/9876/Asha Kulkarni',
  reference: 'UTR123',
  amount: '4500.00',
);

Widget _sheet(List<OnlinePaymentEntity> candidates) => ProviderScope(
      overrides: [
        currentUserProvider.overrideWithValue(null),
        bankMatchCandidatesProvider.overrideWith((ref, id) async => candidates),
      ],
      child: MaterialApp(theme: AppTheme.lightTheme, home: Scaffold(body: BankMatchEntrySheet(entry: _entry))),
    );

void main() {
  testWidgets('the sheet names the entry, lists the suggested payments with Confirm, and offers Ignore', (tester) async {
    tester.view.physicalSize = const Size(390, 844);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.reset);
    await tester.pumpWidget(_sheet([
      OnlinePaymentEntity(
        id: 'p1',
        societyId: 's1',
        flatId: 'f1',
        wingName: 'A',
        flatNumber: '101',
        receiptNumber: 'RC-0042',
        amount: '4500.00',
        paymentDate: DateTime(2026, 10, 7),
        paymentMode: 'upi',
      ),
    ]));
    await tester.pumpAndSettle();

    expect(find.text('₹4500.00'), findsOneWidget);
    expect(find.textContaining('UPI/9876/Asha Kulkarni'), findsOneWidget);
    expect(find.textContaining('8/10/2026'), findsOneWidget);
    expect(find.text('Suggested matches'), findsOneWidget);
    expect(find.textContaining('RC-0042'), findsOneWidget);
    expect(find.text('Confirm'), findsOneWidget);
    expect(find.text('Not a resident payment — ignore'), findsOneWidget);
  });

  testWidgets('with no suggestions it says so and still offers Ignore', (tester) async {
    tester.view.physicalSize = const Size(390, 844);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.reset);
    await tester.pumpWidget(_sheet(const []));
    await tester.pumpAndSettle();

    expect(find.textContaining('No pending payment found'), findsOneWidget);
    expect(find.text('Confirm'), findsNothing);
    expect(find.text('Not a resident payment — ignore'), findsOneWidget);
  });
}
