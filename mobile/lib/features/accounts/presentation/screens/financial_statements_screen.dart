import 'package:flutter/material.dart';
import 'package:ar_society_app/core/motion/loading.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/layout/app_sheet.dart';
import 'package:ar_society_app/core/router/app_router.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/accounts/data/accounts_api.dart';
import 'package:ar_society_app/features/accounts/presentation/providers/accounts_providers.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/features/maintenance_billing/presentation/widgets/billing_sheet_frame.dart';
import 'package:ar_society_app/shared/widgets/app_data_table.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';
import 'package:ar_society_app/shared/widgets/app_form.dart';

String reportRoute(String report, String fy) =>
    Uri(path: AppRoutes.accountsReport.replaceFirst(':report', report), queryParameters: {'fy': fy}).toString();

/// The year's financial statements — Balance Sheet, Income & Expenditure,
/// Receipts & Payments, Trial Balance and Schedule of Funds — and the
/// year-end closing of the books, year by year.
class FinancialStatementsScreen extends ConsumerStatefulWidget {
  const FinancialStatementsScreen({super.key});

  @override
  ConsumerState<FinancialStatementsScreen> createState() => _FinancialStatementsScreenState();
}

class _FinancialStatementsScreenState extends ConsumerState<FinancialStatementsScreen> {
  String? _fy;

  /// The last completed year with entries — what the audit and AGM are
  /// about — else the current one.
  String _defaultYear(List<FinancialYear> years) =>
      (years.where((y) => !y.isCurrent && y.hasEntries).firstOrNull ?? years.first).fy;

  @override
  Widget build(BuildContext context) {
    final user = ref.watch(currentUserProvider);
    final societyId = user?.societyId;
    if (societyId == null) return const Scaffold(body: Center(child: Text('No society context')));
    final yearsAsync = ref.watch(financialYearsProvider(societyId));
    final canCloseBooks = user!.isAdminOrCommittee;

    return AppPage(
      title: 'Financial Statements',
      body: RefreshIndicator(
        onRefresh: () async => ref.invalidate(financialYearsProvider(societyId)),
        child: yearsAsync.when(
          loading: () => const AppLoader(),
          error: (e, _) => ListView(children: [
            Padding(
              padding: const EdgeInsets.all(24),
              child: Text(friendlyErrorMessage(e), style: const TextStyle(color: AppTheme.error)),
            ),
          ]),
          data: (years) {
            final fy = _fy != null && years.any((y) => y.fy == _fy) ? _fy! : _defaultYear(years);
            final year = years.firstWhere((y) => y.fy == fy);
            return ResponsiveBody(
              maxWidth: 1000,
              child: ListView(
                padding: const EdgeInsets.fromLTRB(16, 16, 16, 96),
                children: [
                  const Text('Financial year', style: TextStyle(fontSize: 12.5, color: AppTheme.textSecondary)),
                  const SizedBox(height: 8),
                  Wrap(spacing: 8, runSpacing: 8, children: [
                    for (final y in years)
                      ChoiceChip(
                        avatar: y.isClosed ? const Icon(Icons.lock_rounded, size: 15) : null,
                        label: Text(y.label),
                        selected: y.fy == fy,
                        onSelected: (_) => setState(() => _fy = y.fy),
                      ),
                  ]),
                  const SizedBox(height: 14),
                  _YearCard(year: year),
                  const SizedBox(height: 22),
                  const Padding(
                    padding: EdgeInsets.only(left: 2, bottom: 10),
                    child: Text('Statements', style: TextStyle(fontSize: 15, fontWeight: FontWeight.w700)),
                  ),
                  Container(
                    decoration: BoxDecoration(
                        color: AppTheme.cardBg, borderRadius: BorderRadius.circular(AppTheme.radiusM)),
                    child: Column(children: [
                      for (final (i, e) in kFinancialReports.entries.indexed) ...[
                        if (i > 0) const Divider(height: 1, indent: 60),
                        ListTile(
                          leading: CircleAvatar(
                            radius: 18,
                            backgroundColor: AppTheme.primarySoft,
                            child: Icon(_reportIcon(e.key), size: 18, color: AppTheme.primary),
                          ),
                          title: Text(e.value.$1, style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600)),
                          subtitle: Text(e.value.$2, style: const TextStyle(fontSize: 12)),
                          trailing: const Icon(Icons.chevron_right_rounded, color: AppTheme.textTertiary),
                          onTap: () => context.push(reportRoute(e.key, fy)),
                        ),
                      ],
                    ]),
                  ),
                  const SizedBox(height: 22),
                  const Padding(
                    padding: EdgeInsets.only(left: 2, bottom: 10),
                    child: Text('Year-end closing', style: TextStyle(fontSize: 15, fontWeight: FontWeight.w700)),
                  ),
                  _ClosingCard(societyId: societyId, year: year, canCloseBooks: canCloseBooks),
                ],
              ),
            );
          },
        ),
      ),
    );
  }

  IconData _reportIcon(String key) => switch (key) {
        'balance-sheet' => Icons.account_balance_rounded,
        'income-expenditure' => Icons.trending_up_rounded,
        'receipts-payments' => Icons.swap_vert_rounded,
        'trial-balance' => Icons.balance_rounded,
        _ => Icons.savings_rounded,
      };
}

class _YearCard extends StatelessWidget {
  final FinancialYear year;
  const _YearCard({required this.year});

  @override
  Widget build(BuildContext context) {
    final (status, color) = year.isClosed
        ? ('Books closed', AppTheme.success)
        : year.isCurrent
            ? ('Running year', AppTheme.primary)
            : ('Open — not closed yet', AppTheme.warning);
    final surplus = year.surplus;
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(color: AppTheme.cardBg, borderRadius: BorderRadius.circular(AppTheme.radiusM)),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Expanded(
            child: Text('${year.label}  ·  ${formatAccountsDate(year.start)} – ${formatAccountsDate(year.end)}',
                style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w700)),
          ),
          StatusPill(status, color),
        ]),
        const SizedBox(height: 14),
        Wrap(spacing: 28, runSpacing: 12, children: [
          _figure('Income', formatInr(year.income)),
          _figure('Expenditure', formatInr(year.expenditure)),
          _figure(surplus >= 0 ? 'Surplus' : 'Deficit', formatInr(surplus.abs()),
              color: surplus >= 0 ? AppTheme.success : AppTheme.error),
        ]),
        if (year.isClosed) ...[
          const SizedBox(height: 12),
          Text(
            [
              'Closed${year.closedAt == null ? '' : ' on ${formatAccountsDate(year.closedAt!)}'}'
                  '${year.closedByName == null ? '' : ' by ${year.closedByName}'}',
              if ((year.reserveTransfer ?? 0) > 0)
                '${formatInr(year.reserveTransfer!)} (${_pctLabel(year.reservePct!)}%) carried to the Reserve Fund',
            ].join(' · '),
            style: const TextStyle(fontSize: 12.5, color: AppTheme.textSecondary),
          ),
        ],
      ]),
    );
  }

  Widget _figure(String label, String value, {Color? color}) => Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(label, style: const TextStyle(fontSize: 11.5, color: AppTheme.textSecondary, fontWeight: FontWeight.w600)),
          const SizedBox(height: 3),
          Text(value,
              style: TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.w700,
                  color: color ?? AppTheme.textPrimary,
                  fontFeatures: const [FontFeature.tabularFigures()])),
        ],
      );
}

String _pctLabel(double v) => v == v.roundToDouble() ? v.toStringAsFixed(0) : v.toStringAsFixed(2);

class _ClosingCard extends ConsumerStatefulWidget {
  final String societyId;
  final FinancialYear year;
  final bool canCloseBooks;
  const _ClosingCard({required this.societyId, required this.year, required this.canCloseBooks});

  @override
  ConsumerState<_ClosingCard> createState() => _ClosingCardState();
}

class _ClosingCardState extends ConsumerState<_ClosingCard> {
  bool _busy = false;

  Future<void> _close() async {
    final pct = await showAppSheet<double>(context: context, builder: (_) => _CloseSheet(year: widget.year));
    if (pct == null) return;
    setState(() => _busy = true);
    try {
      await ref.read(accountsApiProvider).closeYear(widget.societyId, widget.year.fy, reservePct: pct);
      invalidateBooks(ref);
      if (mounted) AppToast.success(context, 'Books for ${widget.year.label} closed');
    } catch (e) {
      if (mounted) showErrorToast(context, e);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _reopen() async {
    final reason = TextEditingController();
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text('Reopen ${widget.year.label}?'),
        content: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
          const Text(
            'The closing entry is cancelled and the year can be changed again. '
            'Close it again once the corrections are made — the statements already shared will change.',
            style: TextStyle(fontSize: 13, color: AppTheme.textSecondary),
          ),
          const SizedBox(height: 12),
          FormFieldBox(label: 'Reason', child: TextField(
            controller: reason,
            autofocus: true,
            decoration: const InputDecoration(hintText: 'e.g. Audit adjustments'),
          )),
        ]),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Keep closed')),
          FilledButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('Reopen')),
        ],
      ),
    );
    if (ok != true) return;
    if (reason.text.trim().length < 3) {
      if (mounted) AppToast.warning(context, 'Give a reason for reopening');
      return;
    }
    setState(() => _busy = true);
    try {
      await ref.read(accountsApiProvider).reopenYear(widget.societyId, widget.year.fy, reason.text.trim());
      invalidateBooks(ref);
      if (mounted) AppToast.success(context, '${widget.year.label} reopened');
    } catch (e) {
      if (mounted) showErrorToast(context, e);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final y = widget.year;
    final String text;
    Widget? action;
    if (y.isClosed) {
      text = 'Income and expenditure were transferred to the Income & Expenditure Account and the year is locked: '
          'nothing can be entered in it or cancelled. Bills and payments of this year recorded later are '
          'posted in the next year.';
      if (widget.canCloseBooks && y.canReopen) {
        action = OutlinedButton.icon(
          onPressed: _busy ? null : _reopen,
          icon: const Icon(Icons.lock_open_rounded, size: 18),
          label: const Text('Reopen year'),
        );
      }
    } else if (y.canClose) {
      text = 'Once the year\'s entries are complete and checked, close the books: income and expenditure are '
          'transferred to the Income & Expenditure Account, a share of the surplus to the Reserve Fund, and '
          'the year is locked.';
      if (widget.canCloseBooks) {
        action = FilledButton.icon(
          onPressed: _busy ? null : _close,
          icon: const Icon(Icons.lock_rounded, size: 18),
          label: Text('Close books for ${y.label}'),
        );
      }
    } else {
      text = '${y.closeBlockedReason ?? 'This year can\'t be closed yet'}.';
    }
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(color: AppTheme.cardBg, borderRadius: BorderRadius.circular(AppTheme.radiusM)),
      child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Icon(y.isClosed ? Icons.lock_rounded : Icons.lock_open_rounded,
              color: y.isClosed ? AppTheme.success : AppTheme.textSecondary),
          const SizedBox(width: 10),
          Expanded(child: Text(text, style: const TextStyle(fontSize: 13))),
        ]),
        if (!widget.canCloseBooks && (y.canClose || y.canReopen))
          const Padding(
            padding: EdgeInsets.only(top: 10),
            child: Text('The Society Admin or the committee (Treasurer / Secretary) closes the year\'s books.',
                style: TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
          ),
        if (action != null) ...[
          const SizedBox(height: 14),
          Align(alignment: Alignment.centerLeft, child: action),
        ],
      ]),
    );
  }
}

/// Confirms closing a year and asks what share of the surplus goes to
/// the Reserve Fund; returns that percentage.
class _CloseSheet extends StatefulWidget {
  final FinancialYear year;
  const _CloseSheet({required this.year});

  @override
  State<_CloseSheet> createState() => _CloseSheetState();
}

class _CloseSheetState extends State<_CloseSheet> {
  late final _pct = TextEditingController(text: _pctLabel(widget.year.suggestedReservePct));

  @override
  void dispose() {
    _pct.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final y = widget.year;
    final pct = double.tryParse(_pct.text.trim()) ?? 0;
    final valid = pct >= 0 && pct <= 100;
    final transfer = y.surplus > 0 ? y.surplus * pct / 100 : 0.0;
    return BillingSheetFrame(
      title: 'Close books for ${y.label}',
      child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        Container(
          padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(color: AppTheme.surface, borderRadius: BorderRadius.circular(AppTheme.radiusS)),
          child: Column(children: [
            _line('Income', formatInr(y.income)),
            _line('Expenditure', formatInr(y.expenditure)),
            const Divider(height: 14),
            _line(y.surplus >= 0 ? 'Surplus for the year' : 'Deficit for the year', formatInr(y.surplus.abs()),
                bold: true),
          ]),
        ),
        const SizedBox(height: 16),
        if (y.surplus > 0) ...[
          FormFieldBox(label: 'Share of surplus to Reserve Fund (%)', child: TextField(
            controller: _pct,
            onChanged: (_) => setState(() {}),
            keyboardType: const TextInputType.numberWithOptions(decimal: true),
            inputFormatters: [FilteringTextInputFormatter.allow(RegExp(r'^\d{0,3}(\.\d{0,2})?'))],
            decoration: InputDecoration(
              helperText: valid ? '${formatInr(transfer)} to the Reserve Fund' : 'Between 0 and 100',
              helperMaxLines: 2,
            ),
          )),
          const SizedBox(height: 6),
          const Text(
            'Under the MCS Act at least 25% of the year\'s net surplus is carried to the Reserve Fund; '
            'use the share your general body or auditor has fixed.',
            style: TextStyle(fontSize: 12, color: AppTheme.textSecondary),
          ),
          const SizedBox(height: 14),
        ],
        const Text('Closing the books will:', style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600)),
        const SizedBox(height: 6),
        for (final t in [
          'Post any bills and payments of the year not yet in the books',
          'Transfer every income and expenditure ledger to the Income & Expenditure Account (dated 31 March)',
          'Lock the year — nothing can be entered or cancelled in it; later entries go in the next year',
        ])
          Padding(
            padding: const EdgeInsets.only(bottom: 4),
            child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
              const Text('•  ', style: TextStyle(fontSize: 13)),
              Expanded(child: Text(t, style: const TextStyle(fontSize: 13))),
            ]),
          ),
        const SizedBox(height: 16),
        AppPrimaryButton(
          label: 'Close books',
          icon: Icons.lock_rounded,
          onPressed: valid ? () => Navigator.pop(context, y.surplus > 0 ? pct : 0.0) : null,
        ),
      ]),
    );
  }

  Widget _line(String label, String value, {bool bold = false}) => Padding(
        padding: const EdgeInsets.symmetric(vertical: 2),
        child: Row(children: [
          Expanded(child: Text(label, style: TextStyle(fontSize: 13.5, fontWeight: bold ? FontWeight.w700 : null))),
          Text(value,
              style: TextStyle(
                  fontSize: 13.5,
                  fontWeight: bold ? FontWeight.w700 : FontWeight.w500,
                  fontFeatures: const [FontFeature.tabularFigures()])),
        ]),
      );
}
