import 'package:flutter/material.dart';
import 'package:ar_society_app/core/router/app_router.dart';
import 'package:ar_society_app/features/accounts/presentation/screens/financial_statements_screen.dart' show reportRoute;
import 'package:ar_society_app/features/accounts/presentation/widgets/voucher_hotkeys.dart';

/// One thing the Accounts page can open: a form to enter something, a report, a book or register, or a setup screen.
class AccountsEntry {
  final String section;
  final String title;
  final String subtitle;
  final IconData icon;
  final String route;

  /// Other words people search with ("P&L" finds Income & Expenditure).
  final List<String> keywords;
  const AccountsEntry(this.section, this.title, this.subtitle, this.icon, this.route, {this.keywords = const []});

  /// True when every word of [query] is in the title, the description or the keywords (any case, any order).
  bool matches(String query) {
    final words = query.toLowerCase().split(RegExp(r'\s+')).where((w) => w.isNotEmpty);
    final hay = '$title $subtitle ${keywords.join(' ')}'.toLowerCase();
    return words.every(hay.contains);
  }
}

/// The sections of the Accounts page, in order.
const kAccountsSections = ['Enter a transaction', 'Financial reports', 'Books & registers', 'Review & setup'];

String _voucher(String type) => Uri(path: AppRoutes.accountsVoucherNew, queryParameters: {'type': type}).toString();

/// Everything the Accounts page offers, every report and form opening directly. [fy] is the financial year the reports
/// open on; [vendorBills] whether the person may open Vendor Bills (its own grant); [pendingApprovals] is shown on the
/// Approvals line.
List<AccountsEntry> accountsCatalogue({required String fy, bool vendorBills = true, int pendingApprovals = 0}) {
  String key(String type) {
    final k = voucherHotkeyLabel(type);
    return k == null ? '' : ' · $k';
  }

  const enter = 'Enter a transaction', reports = 'Financial reports', books = 'Books & registers', review = 'Review & setup';
  return [
    // ── Forms ──────────────────────────────────────────────────────────────────────────────────────────────────
    AccountsEntry(enter, 'Receipt', 'Money received: member payments, interest, other income${key('receipt')}',
        Icons.south_west_rounded, _voucher('receipt'), keywords: const ['income', 'collection', 'voucher', 'form']),
    AccountsEntry(enter, 'Payment', 'Money paid out to a vendor or anyone else${key('payment')}', Icons.north_east_rounded,
        _voucher('payment'), keywords: const ['pay', 'vendor', 'voucher', 'form']),
    const AccountsEntry(enter, 'Expense', 'An expense with its bill, booked to the right head', Icons.shopping_bag_outlined,
        AppRoutes.accountsExpenseNew, keywords: ['bill', 'spend', 'form']),
    AccountsEntry(enter, 'Contra', 'Cash deposited in or withdrawn from the bank, or bank to bank${key('contra')}',
        Icons.swap_horiz_rounded, _voucher('contra'), keywords: const ['transfer', 'deposit', 'withdraw', 'voucher', 'form']),
    AccountsEntry(enter, 'Journal', 'Adjustments, provisions and corrections${key('journal')}', Icons.edit_note_rounded,
        _voucher('journal'), keywords: const ['adjustment', 'jv', 'voucher', 'form']),
    const AccountsEntry(enter, 'Petty Cash', 'Small cash spends and top-ups of the petty cash box', Icons.payments_outlined,
        AppRoutes.accountsPettyCash, keywords: ['cash', 'form']),
    const AccountsEntry(enter, 'Monthly Expenses', 'Security, lift, electricity: record each month as they fall due',
        Icons.event_repeat_rounded, AppRoutes.accountsRecurring, keywords: ['recurring', 'standing', 'form']),

    // ── Reports ────────────────────────────────────────────────────────────────────────────────────────────────
    AccountsEntry(reports, 'Trial Balance', 'Every ledger\'s debit and credit balance, $fy', Icons.balance_rounded,
        reportRoute('trial-balance', fy), keywords: const ['tb', 'report']),
    AccountsEntry(reports, 'Income & Expenditure', 'Income against expenses and the surplus or deficit, $fy',
        Icons.trending_up_rounded, reportRoute('income-expenditure', fy),
        keywords: const ['i&e', 'profit', 'loss', 'p&l', 'surplus', 'report']),
    AccountsEntry(reports, 'Balance Sheet', 'What the society owns and owes, $fy', Icons.account_balance_rounded,
        reportRoute('balance-sheet', fy), keywords: const ['assets', 'liabilities', 'report']),
    AccountsEntry(reports, 'Receipts & Payments', 'All cash and bank money in and out, $fy', Icons.compare_arrows_rounded,
        reportRoute('receipts-payments', fy), keywords: const ['r&p', 'cash flow', 'report']),
    AccountsEntry(reports, 'Schedule of Funds', 'Sinking, repair and other funds: opening, added, used, closing',
        Icons.savings_outlined, reportRoute('funds', fy), keywords: const ['sinking fund', 'repair fund', 'report']),
    const AccountsEntry(reports, 'Outstanding Receivable', 'What members owe, aged by days overdue',
        Icons.hourglass_bottom_rounded, AppRoutes.accountsReceivable, keywords: ['dues', 'defaulters', 'ageing', 'report']),
    const AccountsEntry(reports, 'Outstanding Payable', 'What the society owes vendors, aged', Icons.hourglass_top_rounded,
        AppRoutes.accountsPayable, keywords: ['creditors', 'ageing', 'report']),
    const AccountsEntry(reports, 'Spend by Element', 'Monthly and yearly spend on each maintenance element',
        Icons.pie_chart_outline_rounded, AppRoutes.accountsExpenses, keywords: ['expenses', 'budget', 'report']),
    const AccountsEntry(reports, 'Element-wise Expenses', 'Every expense entry by maintenance element, month by month, with what was billed',
        Icons.table_chart_rounded, AppRoutes.accountsExpensesMonthly,
        keywords: ['element wise', 'monthly', 'expenses', 'maintenance', 'estimate', 'report']),
    const AccountsEntry(reports, 'TDS Ledger', 'TDS to deposit with the government and TDS to claim back',
        Icons.account_balance_rounded, AppRoutes.accountsTdsLedger, keywords: ['tax', 'report', 'register']),
    const AccountsEntry(reports, 'Depreciation', 'Each asset\'s depreciation for the year, and its setup',
        Icons.trending_down_rounded, AppRoutes.accountsDepreciation, keywords: ['assets', 'report', 'register']),
    const AccountsEntry(reports, 'Year-end Closing', 'All statements for a year, and closing or reopening the books',
        Icons.summarize_rounded, AppRoutes.accountsStatements,
        keywords: ['financial statements', 'close', 'audit', 'report']),

    // ── Books & registers ──────────────────────────────────────────────────────────────────────────────────────
    const AccountsEntry(books, 'Day Book', 'Every voucher, date-wise', Icons.receipt_long_rounded, AppRoutes.accountsDayBook,
        keywords: ['vouchers', 'journal', 'register']),
    const AccountsEntry(books, 'Cash & Bank Book', 'Every receipt and payment through each cash and bank account',
        Icons.menu_book_rounded, AppRoutes.accountsCashBook, keywords: ['bank book', 'cash book', 'register']),
    const AccountsEntry(books, 'Bank Reconciliation', 'Match the bank statement with the books',
        Icons.account_balance_wallet_outlined, AppRoutes.accountsBankRecon, keywords: ['brs', 'statement']),
    const AccountsEntry(books, "Members' Ledger", 'Flat-wise dues, payments and advances', Icons.groups_2_rounded,
        AppRoutes.accountsMembers, keywords: ['flat', 'member', 'dues', 'ledger']),
    const AccountsEntry(books, 'Invoice Register', 'Maintenance invoices raised on members: billed, paid and due',
        Icons.request_quote_rounded, AppRoutes.accountsInvoices, keywords: ['bills', 'maintenance', 'register']),
    const AccountsEntry(books, 'Receipts Register', 'Payments received from members, what they settled and any advance',
        Icons.receipt_rounded, AppRoutes.accountsRegisterReceipts, keywords: ['collections', 'register']),
    const AccountsEntry(books, 'Bills Register', 'Bills received from vendors: billed, paid and still to pay',
        Icons.inventory_2_rounded, AppRoutes.accountsBills, keywords: ['vendor', 'purchase', 'register']),
    if (vendorBills)
      const AccountsEntry(books, 'Vendor Bills', 'Book a vendor bill and pay it', Icons.storefront_rounded,
          AppRoutes.vendorBills, keywords: ['vendor', 'purchase', 'form']),
    const AccountsEntry(books, 'Expenses Register', 'Every expense booked, with its bill or receipt',
        Icons.shopping_bag_rounded, AppRoutes.accountsRegisterExpenses, keywords: ['spend', 'register']),
    const AccountsEntry(books, 'Petty Cash Book', 'Day by day: opening cash, received, spent by head, closing',
        Icons.payments_rounded, AppRoutes.accountsRegisterPettyCash, keywords: ['cash', 'register']),
    const AccountsEntry(books, 'Rental Register', 'Flats and shops let out: tenant, agreement, rent, deposit, expiry',
        Icons.key_rounded, AppRoutes.accountsRegisterRental, keywords: ['tenant', 'rent', 'lease', 'register']),
    const AccountsEntry(books, 'Staff Attendance Register', "A month's present, absent, half day and leave for each person",
        Icons.event_available_rounded, AppRoutes.accountsRegisterAttendance, keywords: ['salary', 'staff', 'register']),

    // ── Review & setup ─────────────────────────────────────────────────────────────────────────────────────────
    AccountsEntry(review, 'Approvals', pendingApprovals > 0 ? '$pendingApprovals waiting for you' : 'Payments and journals to approve',
        Icons.fact_check_rounded, AppRoutes.accountsApprovals, keywords: const ['pending', 'approve']),
    const AccountsEntry(review, 'Chart of Accounts', 'Groups, ledgers and their balances; add or edit a ledger',
        Icons.account_tree_rounded, AppRoutes.accountsChart, keywords: ['ledger', 'groups', 'heads', 'setup']),
    const AccountsEntry(review, 'Accounts Agent', 'Audits new entries, explains anything unusual, proposes corrections',
        Icons.policy_rounded, AppRoutes.accountsAgent, keywords: ['audit', 'ai', 'bye-laws', 'compliance']),
    const AccountsEntry(review, 'Gateway of Accounts', 'Everything above from the keyboard · Alt+G', Icons.keyboard_rounded,
        AppRoutes.accountsGateway, keywords: ['tally', 'shortcuts', 'keyboard']),
  ];
}
