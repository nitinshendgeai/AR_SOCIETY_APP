import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/layout/app_sheet.dart';
import 'package:ar_society_app/core/layout/app_shell.dart' show isDesktopLayout;
import 'package:ar_society_app/core/router/app_router.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/accounts/data/accounts_api.dart';
import 'package:ar_society_app/features/accounts/presentation/providers/accounts_providers.dart';
import 'package:ar_society_app/features/accounts/presentation/widgets/accounts_widgets.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/features/maintenance_billing/presentation/widgets/billing_sheet_frame.dart';
import 'package:ar_society_app/shared/widgets/app_data_table.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';

String ledgerRoute(String accountId, {String? flatId, String? vendorId}) {
  final path = AppRoutes.accountsLedger.replaceFirst(':accountId', accountId);
  final q = {if (flatId != null) 'flat': flatId, if (vendorId != null) 'vendor': vendorId};
  return q.isEmpty ? path : Uri(path: path, queryParameters: q).toString();
}

String newVoucherRoute(String type) => Uri(path: AppRoutes.accountsVoucherNew, queryParameters: {'type': type}).toString();

/// Asks which kind of voucher to enter, then opens the voucher form.
Future<void> chooseNewVoucher(BuildContext context) async {
  final type = await showAppSheet<String>(
    context: context,
    builder: (ctx) => BillingSheetFrame(
      title: 'New voucher',
      child: Column(mainAxisSize: MainAxisSize.min, children: [
        for (final t in kManualVoucherTypes)
          ListTile(
            contentPadding: const EdgeInsets.symmetric(horizontal: 4),
            leading: CircleAvatar(
              radius: 18,
              backgroundColor: voucherTypeColor(t).withOpacity(0.12),
              child: Icon(_voucherIcon(t), size: 18, color: voucherTypeColor(t)),
            ),
            title: Text(voucherTypeLabel(t), style: const TextStyle(fontWeight: FontWeight.w600)),
            subtitle: Text(voucherTypeHint(t), style: const TextStyle(fontSize: 12)),
            onTap: () => Navigator.pop(ctx, t),
          ),
      ]),
    ),
  );
  if (type != null && context.mounted) context.push(newVoucherRoute(type));
}

IconData _voucherIcon(String t) => switch (t) {
      'receipt' => Icons.south_west_rounded,
      'payment' => Icons.north_east_rounded,
      'contra' => Icons.swap_horiz_rounded,
      _ => Icons.edit_note_rounded,
    };

/// The society's books at a glance: cash and bank balances, what members
/// owe, what's payable to vendors, this year's income and expenditure,
/// and the way into the day book, ledgers and voucher entry.
class AccountsScreen extends ConsumerStatefulWidget {
  const AccountsScreen({super.key});

  @override
  ConsumerState<AccountsScreen> createState() => _AccountsScreenState();
}

class _AccountsScreenState extends ConsumerState<AccountsScreen> {
  bool _syncing = false;

  Future<void> _sync(String societyId) async {
    setState(() => _syncing = true);
    try {
      final n = await ref.read(accountsApiProvider).sync(societyId);
      invalidateBooks(ref);
      if (mounted) AppToast.success(context, n == 0 ? 'Books are up to date' : '$n entries posted to the books');
    } catch (e) {
      if (mounted) showErrorToast(context, e);
    } finally {
      if (mounted) setState(() => _syncing = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final societyId = ref.watch(currentUserProvider)?.societyId;
    if (societyId == null) return const Scaffold(body: Center(child: Text('No society context')));
    final summaryAsync = ref.watch(accountsSummaryProvider(societyId));
    final desktop = isDesktopLayout(context);
    // Phone tiles are too narrow for "₹11,44,973.82"; they show "₹11.45 L".
    final narrow = MediaQuery.sizeOf(context).width < 600;
    String money(num v) => narrow ? formatInrShort(v) : formatInr(v);

    return Scaffold(
      backgroundColor: AppTheme.surface,
      appBar: AppBar(title: const Text('Accounts'), actions: [
        if (desktop)
          HeaderActionButton(
              icon: Icons.add_rounded, label: 'New Voucher', onPressed: () => chooseNewVoucher(context)),
      ]),
      floatingActionButton: desktop
          ? null
          : FloatingActionButton.extended(
              onPressed: () => chooseNewVoucher(context),
              icon: const Icon(Icons.add_rounded),
              label: const Text('New Voucher'),
            ),
      body: RefreshIndicator(
        onRefresh: () async => invalidateBooks(ref),
        child: summaryAsync.when(
          loading: () => const Center(child: CircularProgressIndicator()),
          error: (e, _) => ListView(children: [
            Padding(
              padding: const EdgeInsets.all(24),
              child: Text(friendlyErrorMessage(e), style: const TextStyle(color: AppTheme.error)),
            ),
          ]),
          data: (s) => ResponsiveBody(
            maxWidth: 1200,
            child: ListView(
              padding: const EdgeInsets.fromLTRB(16, 16, 16, 96),
              children: [
                if (s.pendingPostings > 0) ...[
                  _PendingBanner(
                    count: s.pendingPostings,
                    busy: _syncing,
                    onSync: () => _sync(societyId),
                  ),
                  const SizedBox(height: 14),
                ],
                KpiGrid(cards: [
                  KpiCard(
                    icon: Icons.account_balance_rounded,
                    label: 'Bank Balance',
                    value: money(s.bank),
                    color: AppTheme.primary,
                    onTap: _bankLedger(s) == null ? null : () => context.push(ledgerRoute(_bankLedger(s)!.id)),
                  ),
                  KpiCard(
                    icon: Icons.payments_rounded,
                    label: 'Cash in Hand',
                    value: money(s.cash),
                    color: AppTheme.success,
                    onTap: _cashLedger(s) == null ? null : () => context.push(ledgerRoute(_cashLedger(s)!.id)),
                  ),
                  KpiCard(
                    icon: Icons.groups_rounded,
                    label: "Members' Dues",
                    value: money(s.membersDues.amount),
                    note: s.membersDues.type == 'Cr' && !s.membersDues.isZero ? 'Net advance received' : 'Receivable',
                    color: AppTheme.warning,
                    onTap: () => context.push(AppRoutes.accountsMembers),
                  ),
                  KpiCard(
                    icon: Icons.storefront_rounded,
                    label: 'Payable to Vendors',
                    value: money(s.creditors),
                    color: AppTheme.error,
                    onTap: () => context.push(AppRoutes.vendorBills),
                  ),
                  KpiCard(
                    icon: Icons.trending_up_rounded,
                    label: 'Income ${s.fy}',
                    value: money(s.fyIncome),
                    color: AppTheme.success,
                    onTap: () => context.push(AppRoutes.accountsChart),
                  ),
                  KpiCard(
                    icon: Icons.trending_down_rounded,
                    label: 'Expenditure ${s.fy}',
                    value: money(s.fyExpense),
                    note: '${s.fySurplus >= 0 ? 'Surplus' : 'Deficit'} ${formatInr(s.fySurplus.abs())}',
                    color: AppTheme.secondary,
                    onTap: () => context.push(AppRoutes.accountsChart),
                  ),
                ]),
                const SizedBox(height: 22),
                const _SectionTitle('Books'),
                _BooksGrid(items: [
                  _BookItem(Icons.receipt_long_rounded, 'Day Book', 'Every voucher, date-wise',
                      () => context.push(AppRoutes.accountsDayBook)),
                  _BookItem(Icons.account_tree_rounded, 'Chart of Accounts', 'Groups, ledgers and balances',
                      () => context.push(AppRoutes.accountsChart)),
                  _BookItem(Icons.groups_2_rounded, "Members' Ledger", 'Flat-wise dues and advances',
                      () => context.push(AppRoutes.accountsMembers)),
                  _BookItem(Icons.storefront_rounded, 'Vendor Bills', 'Bills booked and paid',
                      () => context.push(AppRoutes.vendorBills)),
                  _BookItem(Icons.summarize_rounded, 'Financial Statements',
                      'Balance Sheet, I&E, Trial Balance · Year-end closing',
                      () => context.push(AppRoutes.accountsStatements)),
                ]),
                const SizedBox(height: 22),
                const _SectionTitle('Cash & Bank Books'),
                _CashBankCard(accounts: s.cashBankAccounts),
                const SizedBox(height: 22),
                const _SectionTitle('Enter a voucher'),
                Wrap(spacing: 10, runSpacing: 10, children: [
                  for (final t in kManualVoucherTypes)
                    ActionChip(
                      avatar: Icon(_voucherIcon(t), size: 18, color: voucherTypeColor(t)),
                      label: Text(voucherTypeLabel(t)),
                      onPressed: () => context.push(newVoucherRoute(t)),
                    ),
                ]),
                const SizedBox(height: 10),
                const Text(
                  'Maintenance bills, payments received and vendor bills are posted to the books '
                  'automatically — enter vouchers here only for everything else.',
                  style: TextStyle(fontSize: 12, color: AppTheme.textSecondary),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  LedgerAccount? _bankLedger(AccountsSummary s) =>
      s.cashBankAccounts.where((a) => a.isDefaultBank).firstOrNull ?? s.cashBankAccounts.where((a) => a.isBank).firstOrNull;

  LedgerAccount? _cashLedger(AccountsSummary s) =>
      s.cashBankAccounts.where((a) => a.systemKey == 'cash').firstOrNull ?? s.cashBankAccounts.where((a) => a.isCash).firstOrNull;
}

class _PendingBanner extends StatelessWidget {
  final int count;
  final bool busy;
  final VoidCallback onSync;
  const _PendingBanner({required this.count, required this.busy, required this.onSync});

  @override
  Widget build(BuildContext context) => Container(
        padding: const EdgeInsets.fromLTRB(14, 12, 10, 12),
        decoration: BoxDecoration(
          color: AppTheme.warningSoft,
          borderRadius: BorderRadius.circular(AppTheme.radiusM),
          border: Border.all(color: AppTheme.warning.withOpacity(0.3)),
        ),
        child: Row(children: [
          const Icon(Icons.sync_problem_rounded, color: AppTheme.warning),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              '$count ${count == 1 ? 'bill or payment isn\'t' : 'bills and payments aren\'t'} in the books yet '
              '(recorded before accounts were set up).',
              style: const TextStyle(fontSize: 13),
            ),
          ),
          const SizedBox(width: 8),
          FilledButton(
            onPressed: busy ? null : onSync,
            child: busy
                ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2))
                : const Text('Post now'),
          ),
        ]),
      );
}

class _SectionTitle extends StatelessWidget {
  final String text;
  const _SectionTitle(this.text);

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.only(left: 2, bottom: 10),
        child: Text(text, style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w700)),
      );
}

class _BookItem {
  final IconData icon;
  final String title;
  final String subtitle;
  final VoidCallback onTap;
  const _BookItem(this.icon, this.title, this.subtitle, this.onTap);
}

class _BooksGrid extends StatelessWidget {
  final List<_BookItem> items;
  const _BooksGrid({required this.items});

  @override
  Widget build(BuildContext context) => LayoutBuilder(builder: (context, c) {
        final columns = c.maxWidth >= 900 ? 4 : (c.maxWidth >= 520 ? 2 : 1);
        return GridView(
          shrinkWrap: true,
          physics: const NeverScrollableScrollPhysics(),
          gridDelegate: SliverGridDelegateWithFixedCrossAxisCount(
              crossAxisCount: columns, mainAxisSpacing: 10, crossAxisSpacing: 10, mainAxisExtent: 72),
          children: [
            for (final i in items)
              Material(
                color: AppTheme.cardBg,
                borderRadius: BorderRadius.circular(AppTheme.radiusM),
                child: InkWell(
                  borderRadius: BorderRadius.circular(AppTheme.radiusM),
                  onTap: i.onTap,
                  child: Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 14),
                    child: Row(children: [
                      Container(
                        width: 38,
                        height: 38,
                        decoration: BoxDecoration(
                            color: AppTheme.primarySoft, borderRadius: BorderRadius.circular(10)),
                        child: Icon(i.icon, color: AppTheme.primary, size: 20),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: Column(mainAxisAlignment: MainAxisAlignment.center, crossAxisAlignment: CrossAxisAlignment.start, children: [
                          Text(i.title, style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600)),
                          Text(i.subtitle,
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                              style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
                        ]),
                      ),
                      const Icon(Icons.chevron_right_rounded, color: AppTheme.textTertiary),
                    ]),
                  ),
                ),
              ),
          ],
        );
      });
}

class _CashBankCard extends StatelessWidget {
  final List<LedgerAccount> accounts;
  const _CashBankCard({required this.accounts});

  @override
  Widget build(BuildContext context) => Container(
        decoration: BoxDecoration(
          color: AppTheme.cardBg,
          borderRadius: BorderRadius.circular(AppTheme.radiusM),
        ),
        child: Column(children: [
          for (final (i, a) in accounts.indexed) ...[
            if (i > 0) const Divider(height: 1, indent: 60),
            ListTile(
              leading: CircleAvatar(
                radius: 18,
                backgroundColor: (a.isBank ? AppTheme.primary : AppTheme.success).withOpacity(0.12),
                child: Icon(a.isBank ? Icons.account_balance_rounded : Icons.payments_rounded,
                    size: 18, color: a.isBank ? AppTheme.primary : AppTheme.success),
              ),
              title: Text(a.name, style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600)),
              subtitle: Text(
                a.isBank
                    ? [if (a.isDefaultBank) 'Default bank', if (a.bankIfsc != null) a.bankIfsc!].join(' · ')
                    : 'Cash',
                style: const TextStyle(fontSize: 12),
              ),
              trailing: Row(mainAxisSize: MainAxisSize.min, children: [
                if (a.balance != null) DrCrText(a.balance!),
                const SizedBox(width: 4),
                const Icon(Icons.chevron_right_rounded, color: AppTheme.textTertiary),
              ]),
              onTap: () => context.push(ledgerRoute(a.id)),
            ),
          ],
        ]),
      );
}
