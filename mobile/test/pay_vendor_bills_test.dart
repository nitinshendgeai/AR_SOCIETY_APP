import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/accounts/data/accounts_api.dart' show LedgerAccount;
import 'package:ar_society_app/features/accounts/presentation/providers/accounts_providers.dart';
import 'package:ar_society_app/features/auth/domain/entities/user_entity.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/features/vendor/data/vendors_work_api.dart';
import 'package:ar_society_app/features/vendor/presentation/providers/vendors_work_providers.dart';
import 'package:ar_society_app/features/vendor/presentation/screens/pay_vendor_bills_screen.dart';

class _Paid {
  final String vendorId;
  final List<({String invoiceId, double amount})> items;
  final String mode;
  final String? ref;
  final String? bankAccountId;
  _Paid(this.vendorId, this.items, this.mode, this.ref, this.bankAccountId);
}

class _FakeApi extends VendorsWorkApi {
  _FakeApi() : super(dio: Dio());
  final paid = <_Paid>[];

  @override
  Future<PayBillsResult> payBills({
    required String vendorId,
    required List<({String invoiceId, double amount})> items,
    required DateTime paidDate,
    required String paymentMode,
    String? paymentRef,
    String? bankName,
    String? bankAccountId,
  }) async {
    paid.add(_Paid(vendorId, items, paymentMode, paymentRef, bankAccountId));
    final total = items.fold<double>(0, (s, i) => s + i.amount);
    return PayBillsResult(
        billsPaid: items.length,
        settled: total.toStringAsFixed(2),
        tdsHeld: '0.00',
        paidToVendor: total.toStringAsFixed(2));
  }
}

LedgerAccount _ledger(String id, String name, {bool cash = false, bool bank = false, bool def = false}) =>
    LedgerAccount.fromJson({
      'id': id,
      'group_id': 'g',
      'name': name,
      'is_cash': cash,
      'is_bank': bank,
      'is_default_bank': def,
      'is_system': true,
      'is_active': true,
      'opening_balance': '0',
      'opening_type': 'dr',
    });

VendorRecord _vendor() => VendorRecord.fromJson({
      'id': 'v1',
      'vendor_code': 'V-1',
      'company_name': 'Sparkle Services',
      'mobile': '9876543210',
      'category': 'housekeeping',
      'status': 'active',
    });

OpenBills _open(List<Map<String, dynamic>> bills) => OpenBills.fromJson({
      'vendor_id': 'v1',
      'vendor_name': 'Sparkle Services',
      'total_outstanding':
          bills.fold<double>(0, (s, b) => s + double.parse(b['outstanding'] as String)).toStringAsFixed(2),
      'bills': bills,
    });

Map<String, dynamic> _bill(String no, String outstanding, {int late = 0}) => {
      'invoice_id': 'inv-$no',
      'invoice_number': no,
      'description': null,
      'invoice_date': '2026-09-01',
      'due_date': '2026-09-15',
      'total': outstanding,
      'paid': '0.00',
      'outstanding': outstanding,
      'days_overdue': late,
    };

Widget _screen(_FakeApi api, OpenBills open) => ProviderScope(
      overrides: [
        currentUserProvider.overrideWithValue(const UserEntity(
            id: 'u1',
            email: 'a@b.c',
            fullName: 'Asha',
            roles: const ['Society Admin'],
            societyId: 's1',
            termsAccepted: true)),
        vendorsWorkApiProvider.overrideWithValue(api),
        vendorRecordsProvider.overrideWith((ref, id) async => [_vendor()]),
        vendorOpenBillsProvider.overrideWith((ref, id) async => open),
        ledgersProvider.overrideWith((ref, id) async => [
              _ledger('cash', 'Cash in Hand', cash: true),
              _ledger('hdfc', 'HDFC Current', bank: true),
              _ledger('sbi', 'SBI Savings', bank: true, def: true),
            ]),
      ],
      child: MaterialApp(theme: AppTheme.lightTheme, home: const PayVendorBillsScreen(initialVendorId: 'v1')),
    );

void _phone(WidgetTester t) {
  t.view.physicalSize = const Size(390, 1600);
  t.view.devicePixelRatio = 1;
  addTearDown(t.view.reset);
}

void main() {
  testWidgets('the vendor\'s unpaid bills are listed oldest first, none ticked, and ticking asks for an amount',
      (t) async {
    _phone(t);
    await t.pumpWidget(_screen(_FakeApi(), _open([_bill('B-1', '10000.00', late: 40), _bill('B-2', '4000.00')])));
    await t.pumpAndSettle();

    expect(find.textContaining('owed ₹14,000.00 across 2 bills'), findsOneWidget);
    expect(find.text('B-1'), findsOneWidget);
    expect(find.textContaining('40 days late'), findsOneWidget);
    expect(find.text('Paying ₹0.00'), findsOneWidget);
    expect(find.byKey(const ValueKey('amount-B-1')), findsNothing); // nothing ticked yet

    await t.tap(find.byKey(const ValueKey('bill-B-1')));
    await t.pumpAndSettle();
    expect(find.byKey(const ValueKey('amount-B-1')), findsOneWidget);
    expect(find.text('Paying ₹10,000.00'), findsOneWidget);
  });

  testWidgets('Select all ticks every bill at what is owed', (t) async {
    _phone(t);
    await t.pumpWidget(_screen(_FakeApi(), _open([_bill('B-1', '10000.00'), _bill('B-2', '4000.00')])));
    await t.pumpAndSettle();
    await t.tap(find.text('Select all'));
    await t.pumpAndSettle();
    expect(find.text('Paying ₹14,000.00'), findsOneWidget);
    expect(find.text('Clear all'), findsOneWidget);
  });

  testWidgets('paying sends the ticked bills at the amounts typed, from the default bank, in one payment', (t) async {
    _phone(t);
    final api = _FakeApi();
    await t.pumpWidget(_screen(api, _open([_bill('B-1', '10000.00'), _bill('B-2', '4000.00')])));
    await t.pumpAndSettle();
    await t.tap(find.byKey(const ValueKey('bill-B-1')));
    await t.tap(find.byKey(const ValueKey('bill-B-2')));
    await t.pumpAndSettle();
    await t.enterText(find.byKey(const ValueKey('amount-B-2')), '1500');
    await t.pumpAndSettle();
    expect(find.text('Paying ₹11,500.00'), findsOneWidget);

    await t.ensureVisible(find.text('Pay bills').last);
    await t.tap(find.text('Pay bills').last);
    await t.pumpAndSettle();

    expect(api.paid, hasLength(1));
    final p = api.paid.single;
    expect(p.vendorId, 'v1');
    expect([for (final i in p.items) (i.invoiceId, i.amount)], [('inv-B-1', 10000.0), ('inv-B-2', 1500.0)]);
    expect(p.mode, 'upi');
    expect(p.bankAccountId, 'sbi'); // the default bank
    expect(find.text('Paying ₹0.00'), findsOneWidget); // cleared for the next payment
  });

  testWidgets('more than a bill is owed is refused and nothing is sent', (t) async {
    _phone(t);
    final api = _FakeApi();
    await t.pumpWidget(_screen(api, _open([_bill('B-1', '4000.00')])));
    await t.pumpAndSettle();
    await t.tap(find.byKey(const ValueKey('bill-B-1')));
    await t.pumpAndSettle();
    await t.enterText(find.byKey(const ValueKey('amount-B-1')), '4500');
    await t.pumpAndSettle();
    await t.ensureVisible(find.text('Pay bills').last);
    await t.tap(find.text('Pay bills').last);
    await t.pumpAndSettle();
    expect(find.textContaining('Cannot exceed what is owed'), findsOneWidget);
    expect(api.paid, isEmpty);
  });

  testWidgets('with nothing ticked it says so and sends nothing', (t) async {
    _phone(t);
    final api = _FakeApi();
    await t.pumpWidget(_screen(api, _open([_bill('B-1', '4000.00')])));
    await t.pumpAndSettle();
    await t.ensureVisible(find.text('Pay bills').last);
    await t.tap(find.text('Pay bills').last);
    await t.pumpAndSettle();
    expect(find.text('Tick at least one bill to pay'), findsOneWidget);
    expect(api.paid, isEmpty);
  });

  testWidgets('paying in cash is from a cash ledger', (t) async {
    _phone(t);
    final api = _FakeApi();
    await t.pumpWidget(_screen(api, _open([_bill('B-1', '700.00')])));
    await t.pumpAndSettle();
    await t.tap(find.byKey(const ValueKey('bill-B-1')));
    await t.pumpAndSettle();
    await t.ensureVisible(find.text('UPI'));
    await t.tap(find.text('UPI'));
    await t.pumpAndSettle();
    await t.tap(find.text('Cash').last);
    await t.pumpAndSettle();
    await t.ensureVisible(find.text('Pay bills').last);
    await t.tap(find.text('Pay bills').last);
    await t.pumpAndSettle();
    expect(api.paid.single.mode, 'cash');
    expect(api.paid.single.bankAccountId, 'cash');
  });

  testWidgets('a vendor with nothing owed gets a clear empty state and no payment form', (t) async {
    _phone(t);
    await t.pumpWidget(_screen(_FakeApi(), _open(const [])));
    await t.pumpAndSettle();
    expect(find.text('Nothing to pay'), findsOneWidget);
    expect(find.text('Payment'), findsNothing);
  });
}
