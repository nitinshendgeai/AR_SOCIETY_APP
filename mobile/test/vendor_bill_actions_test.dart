import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/accounts/data/accounts_api.dart' show LedgerAccount;
import 'package:ar_society_app/features/accounts/presentation/providers/accounts_providers.dart';
import 'package:ar_society_app/features/auth/domain/entities/user_entity.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/features/vendor/domain/entities/vendor_entities.dart';
import 'package:ar_society_app/features/vendor/presentation/providers/vendor_providers.dart';
import 'package:ar_society_app/features/vendor/presentation/screens/vendor_bills_screen.dart';

class _Invoices extends VendorInvoicesNotifier {
  final List<VendorInvoiceEntity> rows;
  _Invoices(this.rows);

  @override
  Future<List<VendorInvoiceEntity>> build(String societyId) async => rows;
}

VendorInvoiceEntity _bill({String paid = '0.00', bool isPaid = false}) => VendorInvoiceEntity(
      id: 'i1',
      societyId: 's1',
      vendorId: 'v1',
      vendorName: 'Sparkle Services',
      invoiceNumber: 'B-1',
      invoiceDate: DateTime(2026, 10, 1),
      amount: '5000.00',
      totalAmount: '5000.00',
      paidAmount: paid,
      outstanding: isPaid ? '0.00' : '5000.00',
      isPaid: isPaid,
    );

Widget _screen(String role, VendorInvoiceEntity bill) => ProviderScope(
      overrides: [
        currentUserProvider.overrideWithValue(UserEntity(
            id: 'u1', email: 'a@b.c', fullName: 'Asha', roles: [role], societyId: 's1', termsAccepted: true)),
        vendorInvoicesProvider.overrideWith(() => _Invoices([bill])),
        ledgersProvider.overrideWith((ref, id) async => <LedgerAccount>[]),
      ],
      child: MaterialApp(theme: AppTheme.lightTheme, home: const VendorBillsScreen()),
    );

Future<void> _open(WidgetTester t, String role, VendorInvoiceEntity bill) async {
  t.view.physicalSize = const Size(390, 900);
  t.view.devicePixelRatio = 1;
  addTearDown(t.view.reset);
  await t.pumpWidget(_screen(role, bill));
  await t.pumpAndSettle();
  await t.tap(find.text('Sparkle Services'));
  await t.pumpAndSettle();
}

void main() {
  testWidgets(
      'an unpaid bill offers paying it, paying several of the vendor\'s, and — to the committee — cancelling it',
      (t) async {
    await _open(t, 'Society Admin', _bill());
    expect(find.text('Record Payment'), findsOneWidget);
    expect(find.text('Pay several bills of this vendor'), findsOneWidget);
    expect(find.text('Cancel this bill'), findsOneWidget);
  });

  testWidgets('a manager enters and pays bills but does not cancel them', (t) async {
    await _open(t, 'Manager', _bill());
    expect(find.text('Record Payment'), findsOneWidget);
    expect(find.text('Cancel this bill'), findsNothing);
  });

  testWidgets('a bill with a payment on it cannot be cancelled from here', (t) async {
    await _open(t, 'Society Admin', _bill(paid: '1000.00'));
    expect(find.text('Record Payment'), findsOneWidget);
    expect(find.text('Cancel this bill'), findsNothing);
  });

  testWidgets('a paid bill has nothing left to pay', (t) async {
    await _open(t, 'Society Admin', _bill(paid: '5000.00', isPaid: true));
    expect(find.text('Record Payment'), findsNothing);
    expect(find.text('Pay several bills of this vendor'), findsNothing);
    expect(find.text('Cancel this bill'), findsNothing);
  });

  testWidgets('the payment sheet asks which account the money leaves', (t) async {
    await _open(t, 'Manager', _bill());
    await t.tap(find.text('Record Payment'));
    await t.pumpAndSettle();
    expect(find.text('Paid from'), findsOneWidget);
  });
}
