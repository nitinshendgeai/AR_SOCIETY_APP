import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:ar_society_app/core/router/app_router.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/accounts/data/accounts_api.dart';
import 'package:ar_society_app/features/accounts/presentation/providers/accounts_providers.dart';
import 'package:ar_society_app/features/accounts/presentation/screens/accounts_screen.dart' show newVoucherRoute;
import 'package:ar_society_app/features/accounts/presentation/screens/financial_statements_screen.dart' show reportRoute;
import 'package:ar_society_app/features/accounts/presentation/widgets/gateway_menu.dart';
import 'package:ar_society_app/features/accounts/presentation/widgets/voucher_hotkeys.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/features/users/presentation/providers/user_providers.dart' show myFormCodesProvider;
import 'package:ar_society_app/shared/widgets/app_form.dart';

/// The Gateway of Accounts: everything the books can do in one menu, worked from the keyboard (see [GatewayMenu]).
/// Opened with Alt+G from any accounts screen, or from the Gateway button on the Accounts page.
class AccountsGatewayScreen extends ConsumerWidget {
  const AccountsGatewayScreen({super.key});

  /// The sections of the Gateway. [fy] is the current financial year when it is known (the reports open on it);
  /// without it the reports open from the Financial Statements page, where the year is chosen.
  static List<GatewaySection> sections(BuildContext context,
      {String? fy, int pendingApprovals = 0, Set<String>? granted}) {
    void go(String route) => context.push(route);
    String? hint(String type) => voucherHotkeyLabel(type);
    String report(String key) => fy == null ? AppRoutes.accountsStatements : reportRoute(key, fy);
    // Vendor Bills is its own screen with its own grant: without it the line would only turn the person away.
    final vendorBills = granted == null || granted.contains('vendor_bills');
    return [
      GatewaySection('Transactions', [
        GatewayItem(label: 'Receipt', letter: 'R', icon: Icons.south_west_rounded, hint: hint('receipt'),
            onOpen: () => go(newVoucherRoute('receipt'))),
        GatewayItem(label: 'Payment', letter: 'P', icon: Icons.north_east_rounded, hint: hint('payment'),
            onOpen: () => go(newVoucherRoute('payment'))),
        GatewayItem(label: 'Contra (cash / bank transfer)', letter: 'C', icon: Icons.swap_horiz_rounded,
            hint: hint('contra'), onOpen: () => go(newVoucherRoute('contra'))),
        GatewayItem(label: 'Journal', letter: 'J', icon: Icons.edit_note_rounded, hint: hint('journal'),
            onOpen: () => go(newVoucherRoute('journal'))),
        GatewayItem(label: 'Expense', letter: 'E', icon: Icons.shopping_bag_outlined,
            onOpen: () => go(AppRoutes.accountsExpenseNew)),
      ]),
      GatewaySection('Books & Registers', [
        GatewayItem(label: 'Day Book', letter: 'D', icon: Icons.receipt_long_rounded,
            onOpen: () => go(AppRoutes.accountsDayBook)),
        GatewayItem(label: 'Cash & Bank Book', letter: 'B', icon: Icons.menu_book_rounded,
            onOpen: () => go(AppRoutes.accountsCashBook)),
        GatewayItem(label: 'Invoice Register', letter: 'I', icon: Icons.request_quote_rounded,
            onOpen: () => go(AppRoutes.accountsInvoices)),
        GatewayItem(label: 'Bills Register', letter: 'L', icon: Icons.inventory_2_rounded,
            onOpen: () => go(AppRoutes.accountsBills)),
        GatewayItem(label: 'Monthly Expenses', letter: 'M', icon: Icons.event_repeat_rounded,
            onOpen: () => go(AppRoutes.accountsRecurring)),
      ]),
      GatewaySection('Receivables & Payables', [
        GatewayItem(label: 'Outstanding Receivable (members)', letter: 'U', icon: Icons.hourglass_bottom_rounded,
            onOpen: () => go(AppRoutes.accountsReceivable)),
        GatewayItem(label: 'Outstanding Payable (vendors)', letter: 'W', icon: Icons.hourglass_top_rounded,
            onOpen: () => go(AppRoutes.accountsPayable)),
        GatewayItem(label: "Members' Ledger", letter: 'N', icon: Icons.groups_2_rounded,
            onOpen: () => go(AppRoutes.accountsMembers)),
        if (vendorBills)
          GatewayItem(label: 'Vendor Bills', letter: 'V', icon: Icons.storefront_rounded,
              onOpen: () => go(AppRoutes.vendorBills)),
        GatewayItem(
            label: 'Approvals',
            letter: 'A',
            icon: Icons.fact_check_rounded,
            badge: pendingApprovals > 0 ? '$pendingApprovals waiting' : null,
            onOpen: () => go(AppRoutes.accountsApprovals)),
      ]),
      GatewaySection('Accounting Setup', [
        GatewayItem(label: 'Chart of Accounts (ledgers)', letter: 'H', icon: Icons.account_tree_rounded,
            onOpen: () => go(AppRoutes.accountsChart)),
      ]),
      GatewaySection('Financial Reports', [
        GatewayItem(label: 'Trial Balance', letter: 'T', icon: Icons.balance_rounded,
            onOpen: () => go(report('trial-balance'))),
        GatewayItem(label: 'Income & Expenditure', letter: 'X', icon: Icons.trending_up_rounded,
            onOpen: () => go(report('income-expenditure'))),
        GatewayItem(label: 'Balance Sheet', letter: 'S', icon: Icons.account_balance_rounded,
            onOpen: () => go(report('balance-sheet'))),
        GatewayItem(label: 'Receipts & Payments', letter: 'Y', icon: Icons.compare_arrows_rounded,
            onOpen: () => go(report('receipts-payments'))),
        GatewayItem(label: 'Schedule of Funds', letter: 'F', icon: Icons.savings_outlined,
            onOpen: () => go(report('funds'))),
        GatewayItem(label: 'Spend by Maintenance Element', letter: 'O', icon: Icons.pie_chart_outline_rounded,
            onOpen: () => go(AppRoutes.accountsExpenses)),
        GatewayItem(label: 'Financial Statements and Year-end Closing', letter: 'Z', icon: Icons.summarize_rounded,
            onOpen: () => go(AppRoutes.accountsStatements)),
      ]),
    ];
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final societyId = ref.watch(currentUserProvider)?.societyId;
    if (societyId == null) return const Scaffold(body: Center(child: Text('No society context')));
    // The menu opens at once; the figures at the top and the year the reports open on arrive when they are loaded.
    final summary = ref.watch(accountsSummaryProvider(societyId)).valueOrNull;
    final fy = summary?.fy;
    // F4-F7 work here too (the menu keeps the focus, so these are bindings round it rather than a focus of their own).
    return CallbackShortcuts(
      bindings: voucherHotkeyBindings((t) => context.push(newVoucherRoute(t))),
      child: AppPage(
      title: 'Gateway of Accounts',
      subtitle: 'Arrow keys and Enter, or press the letter · F4–F7 new voucher · Esc goes back',
      maxWidth: 640,
      body: Column(children: [
        if (summary != null) _Strip(summary),
        Expanded(
          child: GatewayMenu(
            sections: sections(context,
                fy: fy,
                pendingApprovals: summary?.pendingApprovals ?? 0,
                granted: ref.watch(myFormCodesProvider).valueOrNull?.toSet()),
            onBack: () => context.canPop() ? context.pop() : context.go(AppRoutes.accounts),
          ),
        ),
      ]),
    ));
  }
}

/// The year and the cash and bank balances, a line under the title.
class _Strip extends StatelessWidget {
  final AccountsSummary s;
  const _Strip(this.s);

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.fromLTRB(24, 10, 24, 0),
        child: Row(children: [
          Expanded(
            child: Text('Financial year ${s.fy}',
                style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: AppTheme.textSecondary)),
          ),
          Text('Bank ${formatInr(s.bank)}   ·   Cash ${formatInr(s.cash)}',
              style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600)),
        ]),
      );
}
