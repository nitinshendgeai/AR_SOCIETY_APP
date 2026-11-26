import 'package:flutter/material.dart';
import 'package:ar_society_app/core/motion/loading.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/layout/app_sheet.dart';
import 'package:ar_society_app/core/layout/app_shell.dart' show isDesktopLayout;
import 'package:ar_society_app/core/router/app_router.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/accounts/data/accounts_api.dart';
import 'package:ar_society_app/features/accounts/presentation/providers/accounts_providers.dart';
import 'package:ar_society_app/features/accounts/presentation/screens/financial_statements_screen.dart' show reportRoute;
import 'package:ar_society_app/features/accounts/presentation/widgets/accounts_catalogue.dart';
import 'package:ar_society_app/features/accounts/presentation/widgets/accounts_widgets.dart';
import 'package:ar_society_app/features/accounts/presentation/widgets/voucher_hotkeys.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/features/users/presentation/providers/user_providers.dart' show myFormCodesProvider;
import 'package:ar_society_app/features/maintenance_billing/presentation/widgets/billing_sheet_frame.dart';
import 'package:ar_society_app/shared/widgets/app_data_table.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';
import 'package:ar_society_app/shared/widgets/app_form.dart';

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
            trailing: voucherHotkeyLabel(t) == null
                ? null
                : Text(voucherHotkeyLabel(t)!, style: TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
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
  final _find = TextEditingController();
  String _query = '';

  @override
  void dispose() {
    _find.dispose();
    super.dispose();
  }

  bool _syncing = false;

  Future<void> _sync(String societyId) async {
    setState(() => _syncing = true);
    try {
      final r = await ref.read(accountsApiProvider).sync(societyId);
      invalidateBooks(ref);
      if (!mounted) return;
      if (r.failures.isEmpty) {
        AppToast.success(context, r.total == 0 ? 'Books are up to date' : '${r.total} entries posted to the books');
      } else {
        await _showFailures(r);
      }
    } catch (e) {
      if (mounted) showErrorToast(context, e);
    } finally {
      if (mounted) setState(() => _syncing = false);
    }
  }

  Future<void> _showPending(String societyId) async {
    try {
      final items = await ref.read(accountsApiProvider).pendingPostings(societyId);
      if (!mounted) return;
      await showDialog<void>(
        context: context,
        builder: (ctx) => AlertDialog(
          title: Text('${items.length} waiting for the books'),
          content: SizedBox(
            width: 420,
            child: SingleChildScrollView(
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, mainAxisSize: MainAxisSize.min, children: [
                for (final i in items) ...[
                  Text(i.label, style: const TextStyle(fontWeight: FontWeight.w700)),
                  Text(i.why, style: const TextStyle(fontSize: 12)),
                  const SizedBox(height: 10),
                ],
              ]),
            ),
          ),
          actions: [TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('OK'))],
        ),
      );
    } catch (e) {
      if (mounted) showErrorToast(context, e);
    }
  }

  /// What could not be posted, and why: these stay on the pending list until what is wrong with them is fixed.
  Future<void> _showFailures(PostingSyncResult r) => showDialog<void>(
        context: context,
        builder: (ctx) => AlertDialog(
          title: Text(r.posted > 0
              ? '${r.posted} posted, ${r.failures.length} could not be'
              : '${r.failures.length} could not be posted'),
          content: SizedBox(
            width: 420,
            child: SingleChildScrollView(
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, mainAxisSize: MainAxisSize.min, children: [
                const Text('The books refused these. They stay on the list until the problem is fixed.',
                    style: TextStyle(fontSize: 13)),
                const SizedBox(height: 12),
                for (final f in r.failures) ...[
                  Text(f.label, style: const TextStyle(fontWeight: FontWeight.w700)),
                  Text(f.message, style: TextStyle(fontSize: 12, color: AppTheme.error)),
                  const SizedBox(height: 10),
                ],
              ]),
            ),
          ),
          actions: [TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('OK'))],
        ),
      );

  @override
  Widget build(BuildContext context) {
    final societyId = ref.watch(currentUserProvider)?.societyId;
    if (societyId == null) return const Scaffold(body: Center(child: Text('No society context')));
    final summaryAsync = ref.watch(accountsSummaryProvider(societyId));
    // Vendor Bills has its own grant; without it the link would only turn the person away.
    final canOpenVendorBills = ref.watch(myFormCodesProvider).valueOrNull?.contains('vendor_bills') ?? true;
    final desktop = isDesktopLayout(context);
    // Phone tiles are too narrow for "₹11,44,973.82"; they show "₹11.45 L".
    final narrow = MediaQuery.sizeOf(context).width < 600;
    String money(num v) => narrow ? formatInrShort(v) : formatInr(v);

    return VoucherHotkeys(child: AppPage(
      title: 'Accounts',
      actions: [
        if (desktop) ...[
          TextButton.icon(
            key: const Key('accounts-gateway'),
            onPressed: () => context.push(AppRoutes.accountsGateway),
            icon: const Icon(Icons.apps_rounded, size: 18),
            label: const Text('Gateway (Alt+G)'),
          ),
          TextButton.icon(
            onPressed: () => chooseNewVoucher(context),
            icon: const Icon(Icons.edit_note_rounded, size: 18),
            label: const Text('New Voucher'),
          ),
          HeaderActionButton(
              icon: Icons.add_rounded, label: 'Add Expense', onPressed: () => context.push(AppRoutes.accountsExpenseNew)),
        ],
      ],
      floatingActionButton: desktop
          ? null
          : FloatingActionButton.extended(
              onPressed: () => context.push(AppRoutes.accountsExpenseNew),
              icon: const Icon(Icons.add_rounded),
              label: const Text('Add Expense'),
            ),
      body: RefreshIndicator(
        onRefresh: () async => invalidateBooks(ref),
        child: summaryAsync.when(
          loading: () => const AppLoader(),
          error: (e, _) => AppErrorState(message: friendlyErrorMessage(e), onRetry: () => ref.invalidate(accountsSummaryProvider(societyId))),
          data: (s) => ResponsiveBody(
            maxWidth: 1200,
            child: ListView(
              padding: const EdgeInsets.fromLTRB(16, 16, 16, 96),
              children: [
                for (final w in s.warnings) ...[
                  _WarningBanner(
                    message: w.message,
                    onTap: () => context.push(w.accountId != null ? ledgerRoute(w.accountId!) : AppRoutes.accountsChart),
                  ),
                  const SizedBox(height: 14),
                ],
                if (s.pendingPostings > 0) ...[
                  _PendingBanner(
                    count: s.pendingPostings,
                    busy: _syncing,
                    onSync: () => _sync(societyId),
                    onDetails: () => _showPending(societyId),
                  ),
                  const SizedBox(height: 14),
                ],
                if (s.pendingApprovals > 0) ...[
                  _ApprovalBanner(count: s.pendingApprovals, onTap: () => context.push(AppRoutes.accountsApprovals)),
                  const SizedBox(height: 14),
                ],
                if (ref.watch(recurringDueProvider(societyId)).valueOrNull case final due? when due.isNotEmpty) ...[
                  _RecurringDueBanner(count: due.length, onTap: () => context.push(AppRoutes.accountsRecurring)),
                  const SizedBox(height: 14),
                ],
                _FindField(controller: _find, onChanged: (v) => setState(() => _query = v.trim())),
                const SizedBox(height: 16),
                if (_query.isNotEmpty)
                  _CatalogueView(
                    entries: accountsCatalogue(fy: s.fy, vendorBills: canOpenVendorBills, pendingApprovals: s.pendingApprovals)
                        .where((e) => e.matches(_query))
                        .toList(),
                    query: _query,
                  )
                else ...[
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
                    onTap: canOpenVendorBills ? () => context.push(AppRoutes.vendorBills) : null,
                  ),
                  KpiCard(
                    icon: Icons.trending_up_rounded,
                    label: 'Income ${s.fy}',
                    value: money(s.fyIncome),
                    color: AppTheme.success,
                    onTap: () => context.push(reportRoute('income-expenditure', s.fy)),
                  ),
                  KpiCard(
                    icon: Icons.trending_down_rounded,
                    label: 'Expenditure ${s.fy}',
                    value: money(s.fyExpense),
                    note: '${s.fySurplus >= 0 ? 'Surplus' : 'Deficit'} ${formatInr(s.fySurplus.abs())}',
                    color: AppTheme.secondary,
                    onTap: () => context.push(reportRoute('income-expenditure', s.fy)),
                  ),
                ]),
                const SizedBox(height: 22),
                _CatalogueView(
                  entries: accountsCatalogue(fy: s.fy, vendorBills: canOpenVendorBills, pendingApprovals: s.pendingApprovals),
                ),
                const _SectionTitle('Cash & Bank Books'),
                _CashBankCard(accounts: s.cashBankAccounts),
                const SizedBox(height: 10),
                Text(
                  'Maintenance bills, payments received and vendor bills are posted to the books '
                  'automatically — enter vouchers here only for everything else.',
                  style: TextStyle(fontSize: 12, color: AppTheme.textSecondary),
                ),
                ],
              ],
            ),
          ),
        ),
      ),
    ));
  }

  LedgerAccount? _bankLedger(AccountsSummary s) =>
      s.cashBankAccounts.where((a) => a.isDefaultBank).firstOrNull ?? s.cashBankAccounts.where((a) => a.isBank).firstOrNull;

  LedgerAccount? _cashLedger(AccountsSummary s) =>
      s.cashBankAccounts.where((a) => a.systemKey == 'cash').firstOrNull ?? s.cashBankAccounts.where((a) => a.isCash).firstOrNull;
}

class _RecurringDueBanner extends StatelessWidget {
  final int count;
  final VoidCallback onTap;
  const _RecurringDueBanner({required this.count, required this.onTap});

  @override
  Widget build(BuildContext context) => Material(
        color: AppTheme.warningSoft,
        borderRadius: BorderRadius.circular(AppTheme.radiusM),
        child: InkWell(
          borderRadius: BorderRadius.circular(AppTheme.radiusM),
          onTap: onTap,
          child: Padding(
            padding: const EdgeInsets.fromLTRB(14, 12, 10, 12),
            child: Row(children: [
              Icon(Icons.event_repeat_rounded, color: AppTheme.warning),
              const SizedBox(width: 12),
              Expanded(
                child: Text(
                  count == 1 ? '1 monthly expense is due to be recorded' : '$count monthly expenses are due to be recorded',
                  style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 13.5),
                ),
              ),
              Text('Record', style: TextStyle(color: AppTheme.primary, fontWeight: FontWeight.w600)),
              Icon(Icons.chevron_right_rounded, color: AppTheme.primary),
            ]),
          ),
        ),
      );
}

/// A likely mistake in the books (cash in credit, opening balances that
/// don't agree); tapping opens the ledger or the chart to fix it.
class _WarningBanner extends StatelessWidget {
  final String message;
  final VoidCallback onTap;
  const _WarningBanner({required this.message, required this.onTap});

  @override
  Widget build(BuildContext context) => Material(
        color: AppTheme.errorSoft,
        borderRadius: BorderRadius.circular(AppTheme.radiusM),
        child: InkWell(
          borderRadius: BorderRadius.circular(AppTheme.radiusM),
          onTap: onTap,
          child: Padding(
            padding: const EdgeInsets.fromLTRB(14, 12, 10, 12),
            child: Row(children: [
              Icon(Icons.warning_amber_rounded, color: AppTheme.error),
              const SizedBox(width: 12),
              Expanded(
                child: Text(message, style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 13.5)),
              ),
              Text('Fix', style: TextStyle(color: AppTheme.primary, fontWeight: FontWeight.w600)),
              Icon(Icons.chevron_right_rounded, color: AppTheme.primary),
            ]),
          ),
        ),
      );
}

class _ApprovalBanner extends StatelessWidget {
  final int count;
  final VoidCallback onTap;
  const _ApprovalBanner({required this.count, required this.onTap});

  @override
  Widget build(BuildContext context) => Material(
        color: AppTheme.warningSoft,
        borderRadius: BorderRadius.circular(AppTheme.radiusM),
        child: InkWell(
          borderRadius: BorderRadius.circular(AppTheme.radiusM),
          onTap: onTap,
          child: Padding(
            padding: const EdgeInsets.fromLTRB(14, 12, 10, 12),
            child: Row(children: [
              Icon(Icons.fact_check_rounded, color: AppTheme.warning),
              const SizedBox(width: 12),
              Expanded(
                child: Text(
                  count == 1
                      ? '1 payment or journal is waiting for approval and is not in the books yet'
                      : '$count payments or journals are waiting for approval and are not in the books yet',
                  style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 13.5),
                ),
              ),
              Text('Review', style: TextStyle(color: AppTheme.primary, fontWeight: FontWeight.w600)),
              Icon(Icons.chevron_right_rounded, color: AppTheme.primary),
            ]),
          ),
        ),
      );
}

class _PendingBanner extends StatelessWidget {
  final int count;
  final bool busy;
  final VoidCallback onSync;
  final VoidCallback onDetails;
  const _PendingBanner({required this.count, required this.busy, required this.onSync, required this.onDetails});

  @override
  Widget build(BuildContext context) => Container(
        padding: const EdgeInsets.fromLTRB(14, 12, 10, 12),
        decoration: BoxDecoration(
          color: AppTheme.warningSoft,
          borderRadius: BorderRadius.circular(AppTheme.radiusM),
          border: Border.all(color: AppTheme.warning.withOpacity(0.3)),
        ),
        child: Row(children: [
          Icon(Icons.sync_problem_rounded, color: AppTheme.warning),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              '$count ${count == 1 ? 'bill or payment isn\'t' : 'bills and payments aren\'t'} in the books yet '
              '(recorded before accounts were set up).',
              style: const TextStyle(fontSize: 13),
            ),
          ),
          TextButton(onPressed: onDetails, child: const Text('See which')),
          FilledButton(
            onPressed: busy ? null : onSync,
            child: busy
                ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2))
                : const Text('Post now'),
          ),
        ]),
      );
}

/// "Find a report, register or form": narrows the page to what matches as the person types.
class _FindField extends StatelessWidget {
  final TextEditingController controller;
  final ValueChanged<String> onChanged;
  const _FindField({required this.controller, required this.onChanged});

  @override
  Widget build(BuildContext context) => TextField(
        key: const Key('accounts-find'),
        controller: controller,
        onChanged: onChanged,
        textInputAction: TextInputAction.search,
        decoration: InputDecoration(
          hintText: 'Find a report, register or form — e.g. balance sheet, receipt, TDS',
          prefixIcon: const Icon(Icons.search_rounded),
          suffixIcon: controller.text.isEmpty
              ? null
              : IconButton(
                  tooltip: 'Clear',
                  icon: const Icon(Icons.close_rounded),
                  onPressed: () {
                    controller.clear();
                    onChanged('');
                  },
                ),
        ),
      );
}

/// The catalogue, section by section ([kAccountsSections]); a section with nothing in it is left out. With a [query]
/// it is the search result, and says so when nothing matches.
class _CatalogueView extends StatelessWidget {
  final List<AccountsEntry> entries;
  final String? query;
  const _CatalogueView({required this.entries, this.query});

  @override
  Widget build(BuildContext context) {
    if (entries.isEmpty) {
      return AppEmptyState(
        icon: Icons.search_off_rounded,
        title: 'Nothing called "$query"',
        subtitle: 'Try another word, such as ledger, receipt, balance sheet or register.',
      );
    }
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      for (final section in kAccountsSections)
        if (entries.where((e) => e.section == section).toList() case final inSection when inSection.isNotEmpty) ...[
          _SectionTitle(section),
          BooksGrid(items: [
            for (final e in inSection) BookItem(e.icon, e.title, e.subtitle, () => context.push(e.route)),
          ]),
          const SizedBox(height: 22),
        ],
    ]);
  }
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

class BookItem {
  final IconData icon;
  final String title;
  final String subtitle;
  final VoidCallback onTap;
  const BookItem(this.icon, this.title, this.subtitle, this.onTap);
}

class BooksGrid extends StatelessWidget {
  final List<BookItem> items;
  const BooksGrid({super.key, required this.items});

  @override
  Widget build(BuildContext context) => LayoutBuilder(builder: (context, c) {
        final columns = c.maxWidth >= 900 ? 4 : (c.maxWidth >= 520 ? 2 : 1);
        // Row by row, so a short last row shares the full width between its tiles instead of leaving an empty cell
        // beside a lone one.
        final rows = <Widget>[];
        for (var start = 0; start < items.length; start += columns) {
          final row = items.skip(start).take(columns).toList();
          rows.add(Padding(
            padding: EdgeInsets.only(top: start == 0 ? 0 : 10),
            child: SizedBox(
              height: 72,
              child: Row(children: [
                for (var k = 0; k < row.length; k++) ...[
                  if (k > 0) const SizedBox(width: 10),
                  Expanded(child: _tile(row[k])),
                ],
              ]),
            ),
          ));
        }
        return Column(children: rows);
      });

  Widget _tile(BookItem i) =>
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
                          color: AppTheme.primarySoft, borderRadius: BorderRadius.circular(AppTheme.radiusS)),
                      child: Icon(i.icon, color: AppTheme.primary, size: 20),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Column(mainAxisAlignment: MainAxisAlignment.center, crossAxisAlignment: CrossAxisAlignment.start, children: [
                        Text(i.title, style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600)),
                        Text(i.subtitle,
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
                      ]),
                    ),
                    Icon(Icons.chevron_right_rounded, color: AppTheme.textTertiary),
                  ]),
                ),
              ),
            );
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
                Icon(Icons.chevron_right_rounded, color: AppTheme.textTertiary),
              ]),
              onTap: () => context.push(ledgerRoute(a.id)),
            ),
          ],
        ]),
      );
}
