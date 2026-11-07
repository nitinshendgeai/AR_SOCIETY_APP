import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:ar_society_app/core/router/app_router.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/shared/widgets/app_form.dart';

/// One place to open every register the society keeps. Each line says what the register is for.
class RegistersHubScreen extends StatelessWidget {
  const RegistersHubScreen({super.key});

  static const entries = <(String, String, String, IconData, String)>[
    ('invoices', 'Invoice Register', 'Maintenance invoices raised on members: billed, paid and due', Icons.request_quote_rounded,
        AppRoutes.accountsInvoices),
    ('bills', 'Bills Register', 'Bills received from vendors: billed, paid and still to pay', Icons.inventory_2_rounded,
        AppRoutes.accountsBills),
    ('cash', 'Cash & Bank Book', 'Every receipt and payment through each cash and bank account', Icons.menu_book_rounded,
        AppRoutes.accountsCashBook),
    ('receipts', 'Receipts Register', 'Payments received from members, what they settled and any advance',
        Icons.receipt_long_rounded, AppRoutes.accountsRegisterReceipts),
    ('rental', 'Rental Register', 'Flats and shops let out: tenant, agreement, rent, deposit and expiry',
        Icons.key_rounded, AppRoutes.accountsRegisterRental),
    ('attendance', 'Staff Attendance Register', "A month's present, absent, half day and leave for each staff member",
        Icons.event_available_rounded, AppRoutes.accountsRegisterAttendance),
    ('petty_cash', 'Petty Cash Book', 'Day by day: opening cash, money received, expenses by head, closing and the cash counted',
        Icons.payments_outlined, AppRoutes.accountsRegisterPettyCash),
  ];

  @override
  Widget build(BuildContext context) => AppPage(
        title: 'Registers',
        subtitle: 'Open, print or download any register',
        body: ListView(
          padding: const EdgeInsets.fromLTRB(16, 12, 16, 32),
          children: [
            for (final (id, title, text, icon, route) in entries)
              Card(
                margin: const EdgeInsets.only(bottom: 10),
                child: ListTile(
                  key: ValueKey('register-$id'),
                  leading: Icon(icon, color: AppTheme.primary),
                  title: Text(title, style: const TextStyle(fontWeight: FontWeight.w700)),
                  subtitle: Text(text),
                  trailing: const Icon(Icons.chevron_right_rounded),
                  onTap: () => context.push(route),
                ),
              ),
          ],
        ),
      );
}
