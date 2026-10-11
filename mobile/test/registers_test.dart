import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/accounts/data/accounts_api.dart';
import 'package:ar_society_app/features/accounts/data/registers_api.dart';
import 'package:ar_society_app/features/accounts/presentation/providers/accounts_providers.dart';
import 'package:ar_society_app/features/accounts/presentation/screens/approvals_screen.dart';
import 'package:ar_society_app/features/accounts/presentation/screens/cash_bank_book_screen.dart';
import 'package:ar_society_app/features/accounts/presentation/screens/invoice_bill_registers_screen.dart';
import 'package:ar_society_app/features/auth/domain/entities/user_entity.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';

UserEntity _user(String role) => UserEntity(id: 'u', email: 'u@t.com', fullName: 'U', roles: [role], societyId: 's1');

Widget _wrap(Widget screen, String role, List<Override> overrides) => ProviderScope(
      overrides: [currentUserProvider.overrideWithValue(_user(role)), ...overrides],
      child: MaterialApp(theme: AppTheme.lightTheme, home: screen),
    );

void _size(WidgetTester t, Size s) {
  t.view.physicalSize = s;
  t.view.devicePixelRatio = 1.0;
  addTearDown(t.view.resetPhysicalSize);
  addTearDown(t.view.resetDevicePixelRatio);
}

Map<String, dynamic> _voucher({String status = 'pending', bool canApprove = true}) => {
      'id': 'v1', 'society_id': 's1', 'voucher_type': 'payment', 'voucher_type_label': 'Payment',
      'voucher_number': 'PV/2026-27/0007', 'voucher_date': '2026-10-06', 'fiscal_year': '2026-27', 'amount': '450.00',
      'narration': 'Plumber', 'approval_status': status, 'created_by_name': 'Meera Manager', 'can_approve': canApprove,
      'is_auto': false, 'is_cancelled': false,
      'entries': [
        {'account_id': 'a1', 'account_name': 'Repairs & Maintenance', 'debit': '450.00', 'credit': '0.00'},
        {'account_id': 'a2', 'account_name': 'Cash in Hand', 'debit': '0.00', 'credit': '450.00'},
      ],
    };

void main() {
  testWidgets('the cash and bank book names who entered and who approved each line', (t) async {
    _size(t, const Size(420, 2000));
    final book = CashBankBook.fromJson({
      'sections': [
        {
          'account_id': 'c1', 'account_name': 'Cash in Hand', 'kind': 'cash', 'opening': '0.00', 'receipts': '0.00',
          'payments': '450.00', 'closing': '-450.00',
          'lines': [
            {
              'voucher_id': 'v1', 'date': '2026-10-06', 'voucher_number': 'PV/2026-27/0007', 'voucher_type': 'payment',
              'particulars': 'Repairs & Maintenance', 'narration': 'Plumber', 'reference': null, 'receipt': '0.00',
              'payment': '450.00', 'balance': '-450.00', 'entered_by': 'Meera Manager', 'approved_by': 'Asha Admin',
              'is_auto': false,
            }
          ],
        }
      ],
      'totals': {'opening': '0.00', 'receipts': '0.00', 'payments': '450.00', 'closing': '-450.00'},
    });
    await t.pumpWidget(_wrap(const CashBankBookScreen(), 'Society Admin', [
      cashBankBookProvider.overrideWith((ref, key) async => book),
    ]));
    await t.pumpAndSettle();
    expect(find.text('Cash & Bank Book'), findsWidgets);
    expect(find.text('Cash in Hand'), findsOneWidget);
    expect(find.textContaining('Entered by Meera Manager'), findsOneWidget);
    expect(find.textContaining('Approved by Asha Admin'), findsOneWidget);
  });

  testWidgets('the invoice register lists each invoice with who generated it, and its totals', (t) async {
    _size(t, const Size(420, 2000));
    final reg = Register.fromJson<InvoiceRow>({
      'rows': [
        {
          'bill_id': 'b1', 'invoice_number': 'INV-2026-00016', 'bill_date': '2026-09-01', 'due_date': '2026-09-10',
          'flat': 'A Wing 101', 'member': 'Meera Patil', 'cycle': 'Sep 2026', 'subtotal': '13025.00', 'tax': '0.00',
          'penalty': '0.00', 'discount': '0.00', 'total': '13025.00', 'paid': '13025.00', 'outstanding': '0.00',
          'status': 'paid', 'is_cancelled': false, 'entered_by': 'Meera Manager',
        }
      ],
      'totals': {'count': 1, 'total': '13025.00', 'paid': '13025.00', 'outstanding': '0.00'},
    }, InvoiceRow.fromJson);
    await t.pumpWidget(_wrap(const InvoiceRegisterScreen(), 'Manager', [
      invoiceRegisterProvider.overrideWith((ref, key) async => reg),
    ]));
    await t.pumpAndSettle();
    expect(find.text('Invoice Register'), findsWidgets);
    expect(find.text('A Wing 101 · Meera Patil'), findsOneWidget);
    expect(find.textContaining('Entered by Meera Manager'), findsOneWidget);
    expect(find.text('Paid'), findsWidgets);
  });

  testWidgets('the bills register shows what is left to pay on each vendor bill', (t) async {
    _size(t, const Size(420, 2000));
    final reg = Register.fromJson<BillRow>({
      'rows': [
        {
          'invoice_id': 'i1', 'invoice_number': 'SS/112', 'invoice_date': '2026-09-05', 'due_date': null,
          'vendor': 'Shield Security', 'description': null, 'expense_head': 'Security Charges', 'amount': '40000.00',
          'gst': '7200.00', 'tds': '0.00', 'total': '47200.00', 'net_payable': '47200.00', 'paid': '20000.00',
          'outstanding': '27200.00', 'status': 'part_paid', 'entered_by': 'Meera Manager',
        }
      ],
      'totals': {'count': 1, 'total': '47200.00', 'paid': '20000.00', 'outstanding': '27200.00'},
    }, BillRow.fromJson);
    await t.pumpWidget(_wrap(const BillsRegisterScreen(), 'Manager', [
      billsRegisterProvider.overrideWith((ref, key) async => reg),
    ]));
    await t.pumpAndSettle();
    expect(find.text('Shield Security'), findsOneWidget);
    expect(find.text('To pay ₹27,200.00'), findsOneWidget);
    expect(find.text('Part paid'), findsWidgets);
    expect(find.textContaining('Entered by Meera Manager'), findsOneWidget);
  });

  testWidgets('approvals: the admin sees Approve and Reject on what is waiting', (t) async {
    _size(t, const Size(420, 2000));
    await t.pumpWidget(_wrap(const ApprovalsScreen(), 'Society Admin', [
      pendingApprovalsProvider('s1').overrideWith((ref) async => [Voucher.fromJson(_voucher())]),
    ]));
    await t.pumpAndSettle();
    expect(find.text('PV/2026-27/0007'), findsOneWidget);
    expect(find.textContaining('Entered by Meera Manager'), findsOneWidget);
    expect(find.text('Approve'), findsOneWidget);
    expect(find.text('Reject'), findsOneWidget);
  });

  testWidgets('approvals: an admin cannot approve their own entry while someone else could', (t) async {
    _size(t, const Size(420, 2000));
    await t.pumpWidget(_wrap(const ApprovalsScreen(), 'Society Admin', [
      pendingApprovalsProvider('s1').overrideWith((ref) async => [Voucher.fromJson(_voucher(canApprove: false))]),
    ]));
    await t.pumpAndSettle();
    expect(find.text('Approve'), findsNothing);
    expect(find.textContaining('another admin or committee member has to approve'), findsOneWidget);
  });

  testWidgets('approvals: a manager sees what is waiting but has no buttons', (t) async {
    _size(t, const Size(420, 2000));
    await t.pumpWidget(_wrap(const ApprovalsScreen(), 'Manager', [
      pendingApprovalsProvider('s1').overrideWith((ref) async => [Voucher.fromJson(_voucher())]),
    ]));
    await t.pumpAndSettle();
    expect(find.text('PV/2026-27/0007'), findsOneWidget);
    expect(find.text('Approve'), findsNothing);
    expect(find.textContaining('Waiting for the admin or a committee member'), findsOneWidget);
  });

  testWidgets('approvals: with nothing waiting it says so', (t) async {
    _size(t, const Size(420, 2000));
    await t.pumpWidget(_wrap(const ApprovalsScreen(), 'Society Admin', [
      pendingApprovalsProvider('s1').overrideWith((ref) async => <Voucher>[]),
    ]));
    await t.pumpAndSettle();
    expect(find.text('Nothing is waiting for approval'), findsOneWidget);
  });
}
