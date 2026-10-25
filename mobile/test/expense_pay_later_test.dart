import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:ar_society_app/core/router/app_router.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/accounts/data/accounts_api.dart';
import 'package:ar_society_app/features/accounts/presentation/providers/accounts_providers.dart';
import 'package:ar_society_app/features/accounts/presentation/screens/expense_form_screen.dart';
import 'package:ar_society_app/features/auth/domain/entities/user_entity.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/features/maintenance_billing/data/maintenance_billing_api.dart';
import 'package:ar_society_app/features/maintenance_billing/presentation/providers/maintenance_billing_providers.dart';
import 'package:ar_society_app/features/vendor/data/datasources/vendor_remote_datasource.dart';
import 'package:ar_society_app/features/vendor/data/repositories/vendor_repository.dart';
import 'package:ar_society_app/features/vendor/data/vendors_work_api.dart' show VendorRecord;
import 'package:ar_society_app/features/vendor/domain/entities/vendor_entities.dart';
import 'package:ar_society_app/features/vendor/presentation/providers/vendor_providers.dart';
import 'package:ar_society_app/features/vendor/presentation/providers/vendors_work_providers.dart';

class _Bill {
  final String vendorId, number, accountId;
  final double amount;
  final DateTime? due;
  final String? description;
  _Bill(this.vendorId, this.number, this.amount, this.due, this.description, this.accountId);
}

class _FakeVendors extends VendorRepository {
  _FakeVendors() : super(ds: VendorRemoteDataSource(dio: Dio()));
  final bills = <_Bill>[];
  String? failWith;

  @override
  Future<VendorResult<VendorInvoiceEntity>> createInvoice({
    required String societyId,
    required String vendorId,
    required String invoiceNumber,
    required DateTime invoiceDate,
    DateTime? dueDate,
    required double amount,
    double gstAmount = 0,
    required double totalAmount,
    String? description,
    String? expenseAccountId,
  }) async {
    if (failWith != null) return VendorFailure(failWith!);
    bills.add(_Bill(vendorId, invoiceNumber, amount, dueDate, description, expenseAccountId ?? ''));
    return VendorSuccess(VendorInvoiceEntity(
      id: 'i1',
      societyId: societyId,
      vendorId: vendorId,
      vendorName: 'Sparkle Services',
      invoiceNumber: invoiceNumber,
      invoiceDate: invoiceDate,
      amount: '$amount',
      totalAmount: '$amount',
      outstanding: '$amount',
    ));
  }
}

class _FakeAccounts extends AccountsApi {
  _FakeAccounts() : super(dio: Dio());
  final created = <String>[];

  @override
  Future<Voucher> createVoucher({
    required String societyId,
    required String type,
    required DateTime date,
    required List<VoucherLineInput> lines,
    String? narration,
    String? reference,
    String? vendorId,
  }) async {
    created.add(type);
    return Voucher.fromJson({
      'id': 'v1',
      'voucher_type': type,
      'voucher_number': 'PV/1',
      'voucher_date': '2026-10-11',
      'amount': '1',
      'approval_status': 'approved',
    });
  }
}

LedgerAccount _l(String id, String name, String nature, {bool cash = false, String? element}) =>
    LedgerAccount.fromJson({
      'id': id,
      'group_id': 'g',
      'group_name': 'G',
      'name': name,
      'nature': nature,
      'is_cash': cash,
      'is_active': true,
      'opening_balance': '0',
      'opening_type': 'dr',
      'maintenance_element_id': element,
      'maintenance_element_name': element == null ? null : 'Security Services',
    });

Future<(_FakeVendors, _FakeAccounts)> _pump(WidgetTester t) async {
  t.view.physicalSize = const Size(390, 2400);
  t.view.devicePixelRatio = 1;
  addTearDown(t.view.reset);
  final vendors = _FakeVendors();
  final accounts = _FakeAccounts();
  await t.pumpWidget(ProviderScope(
    overrides: [
      currentUserProvider.overrideWithValue(const UserEntity(
          id: 'u', email: 'u@t.com', fullName: 'U', roles: ['Manager'], societyId: 's1', termsAccepted: true)),
      ledgersProvider.overrideWith((ref, id) async => [
            _l('cash', 'Cash in Hand', 'asset', cash: true),
            _l('sec', 'Security Charges', 'expense', element: 'e1'),
          ]),
      maintenanceElementsProvider.overrideWith((ref, k) async => [
            const MaintenanceElement(
                id: 'e1',
                code: 'security',
                name: 'Security Services',
                category: 'maintenance',
                defaultBasis: 'budget_equal'),
          ]),
      nextVoucherNumberProvider.overrideWith((ref, k) async => 'PV/1'),
      vendorRecordsProvider.overrideWith((ref, id) async => [
            VendorRecord.fromJson({
              'id': 'v1',
              'vendor_code': 'V-1',
              'company_name': 'Sparkle Services',
              'mobile': '9876543210',
              'category': 'housekeeping',
              'status': 'active',
            }),
          ]),
      vendorRepositoryProvider.overrideWithValue(vendors),
      accountsApiProvider.overrideWithValue(accounts),
    ],
    child: MaterialApp.router(
      theme: AppTheme.lightTheme,
      routerConfig: GoRouter(routes: [
        GoRoute(path: '/', builder: (_, __) => const ExpenseFormScreen()),
        GoRoute(path: AppRoutes.accounts, builder: (_, __) => const Scaffold(body: Text('Accounts home'))),
      ]),
    ),
  ));
  await t.pumpAndSettle();
  return (vendors, accounts);
}

Future<void> _fill(WidgetTester t, {String amount = '4800', bool withVendor = true, String bill = 'INV-77'}) async {
  await t.tap(find.text('What is it for?'));
  await t.pumpAndSettle();
  await t.tap(find.text('Security Services').last);
  await t.pumpAndSettle();
  await t.enterText(find.widgetWithText(TextField, '0.00'), amount);
  if (withVendor) {
    await t.tap(find.byType(DropdownButtonFormField<String?>));
    await t.pumpAndSettle();
    await t.tap(find.textContaining('Sparkle Services').last);
    await t.pumpAndSettle();
  }
  final billField = find.descendant(
      of: find.ancestor(of: find.textContaining('Supplier'), matching: find.byType(Column)).first,
      matching: find.byType(TextField));
  if (bill.isNotEmpty) await t.enterText(billField.first, bill);
  await t.pumpAndSettle();
}

Future<void> _save(WidgetTester t, String label) async {
  await t.ensureVisible(find.text(label).last);
  await t.tap(find.text(label).last);
  await t.pumpAndSettle();
}

Future<void> _altP(WidgetTester t) async {
  await t.sendKeyDownEvent(LogicalKeyboardKey.altLeft);
  await t.sendKeyEvent(LogicalKeyboardKey.keyP);
  await t.sendKeyUpEvent(LogicalKeyboardKey.altLeft);
  await t.pumpAndSettle();
}

void main() {
  testWidgets('Alt+P flips between Paid now and Pay later from the keyboard, even while typing', (t) async {
    await _pump(t);
    expect(find.text('Save expense'), findsOneWidget);

    await _altP(t);
    expect(find.text('Save bill'), findsOneWidget);
    expect(find.text('Due date'), findsOneWidget);
    expect(find.text('Paid from'), findsNothing);

    // from inside a text field too, and back again
    await t.tap(find.widgetWithText(TextField, '0.00'));
    await t.pump();
    await _altP(t);
    expect(find.text('Save expense'), findsOneWidget);
    expect(find.text('Paid from'), findsOneWidget);
    expect(find.text('Due date'), findsNothing);
  });

  testWidgets('P alone, or Ctrl+P, does not switch; and what was typed is kept when switching', (t) async {
    await _pump(t);
    await t.enterText(find.widgetWithText(TextField, '0.00'), '4800');
    await t.sendKeyEvent(LogicalKeyboardKey.keyP);
    await t.sendKeyDownEvent(LogicalKeyboardKey.controlLeft);
    await t.sendKeyEvent(LogicalKeyboardKey.keyP);
    await t.sendKeyUpEvent(LogicalKeyboardKey.controlLeft);
    await t.pumpAndSettle();
    expect(find.text('Save expense'), findsOneWidget);

    await _altP(t);
    expect(find.text('Save bill'), findsOneWidget);
    expect(find.text('4800'), findsOneWidget);
  });

  testWidgets('Paid now is the default; Pay later swaps the payment details for the bill\'s', (t) async {
    await _pump(t);
    expect(find.text('Save expense'), findsOneWidget);
    expect(find.text('Paid from'), findsOneWidget);
    expect(find.text('Voucher no.'), findsOneWidget);
    expect(find.text('Due date'), findsNothing);

    await t.tap(find.text('Pay later'));
    await t.pumpAndSettle();
    expect(find.text('Save bill'), findsOneWidget);
    expect(find.text('Paid from'), findsNothing);
    expect(find.text('Voucher no.'), findsNothing);
    expect(find.text('Due date'), findsOneWidget);
    expect(find.textContaining("Supplier's bill no."), findsOneWidget);
    expect(find.textContaining('Vendor'), findsWidgets);

    await t.tap(find.text('Paid now'));
    await t.pumpAndSettle();
    expect(find.text('Paid from'), findsOneWidget);
  });

  testWidgets('a bill needs its vendor and its number, and nothing is saved without them', (t) async {
    final (vendors, accounts) = await _pump(t);
    await t.tap(find.text('Pay later'));
    await t.pumpAndSettle();
    await _fill(t, withVendor: false, bill: '');
    await _save(t, 'Save bill');
    expect(find.text('Choose the vendor the bill is from'), findsOneWidget);
    await t.pump(const Duration(seconds: 6)); // the message goes away
    await t.pumpAndSettle();

    await t.tap(find.byType(DropdownButtonFormField<String?>));
    await t.pumpAndSettle();
    await t.tap(find.textContaining('Sparkle Services').last);
    await t.pumpAndSettle();
    await _save(t, 'Save bill');
    expect(find.text("Enter the supplier's bill number"), findsOneWidget);
    expect(vendors.bills, isEmpty);
    expect(accounts.created, isEmpty);
  });

  testWidgets('saving a bill books it to the vendor under the expense head, not as a paid voucher', (t) async {
    final (vendors, accounts) = await _pump(t);
    await t.tap(find.text('Pay later'));
    await t.pumpAndSettle();
    await _fill(t);
    await _save(t, 'Save bill');

    expect(accounts.created, isEmpty); // nothing was paid
    expect(vendors.bills, hasLength(1));
    final b = vendors.bills.single;
    expect((b.vendorId, b.number, b.amount, b.accountId), ('v1', 'INV-77', 4800.0, 'sec'));
    expect(find.text('Accounts home'), findsOneWidget); // back to the books
  });

  testWidgets('Paid now still saves a payment voucher and no bill', (t) async {
    final (vendors, accounts) = await _pump(t);
    await _fill(t, withVendor: false, bill: '');
    await _save(t, 'Save expense');
    expect(accounts.created, ['payment']);
    expect(vendors.bills, isEmpty);
  });

  testWidgets('a bill the server refuses is reported and the form stays', (t) async {
    final (vendors, _) = await _pump(t);
    vendors.failWith = 'Invoice INV-77 is already recorded for Sparkle Services';
    await t.tap(find.text('Pay later'));
    await t.pumpAndSettle();
    await _fill(t);
    await _save(t, 'Save bill');
    expect(find.textContaining('already recorded'), findsOneWidget);
    expect(find.text('Accounts home'), findsNothing);
    expect(find.text('Save bill'), findsOneWidget);
  });
}
