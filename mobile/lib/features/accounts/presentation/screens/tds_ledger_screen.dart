import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/motion/loading.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/accounts/data/accounts_api.dart' show formatAccountsDate, formatInr;
import 'package:ar_society_app/features/accounts/data/tds_ledger_api.dart';
import 'package:ar_society_app/features/accounts/presentation/widgets/accounts_widgets.dart';
import 'package:ar_society_app/features/accounts/presentation/widgets/register_widgets.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/shared/widgets/app_form.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';
import 'package:ar_society_app/shared/widgets/premium.dart';

/// What the society has to deposit with the government and what it can claim back, read from the two TDS ledgers.
/// Nothing here changes the books; the amounts are the balances of TDS Payable and TDS Receivable.
class TdsLedgerScreen extends ConsumerStatefulWidget {
  const TdsLedgerScreen({super.key});

  @override
  ConsumerState<TdsLedgerScreen> createState() => _TdsLedgerScreenState();
}

class _TdsLedgerScreenState extends ConsumerState<TdsLedgerScreen> {
  RegisterPeriod _period = RegisterPeriod.thisYear;

  @override
  Widget build(BuildContext context) {
    final societyId = ref.watch(currentUserProvider)?.societyId ?? '';
    final (from, to) = _period.range;
    final key = (societyId: societyId, from: from, to: to);
    final async = ref.watch(tdsLedgerProvider(key));
    return AppPage(
      title: 'TDS Ledger',
      subtitle: 'What to deposit and what to claim back',
      actions: [
        PdfActions(
          load: async.valueOrNull == null ? null : () => ref.read(tdsLedgerApiProvider).pdf(societyId, from: from, to: to),
          fileName: 'TDS-Ledger.pdf',
          subject: 'TDS ledger',
        ),
      ],
      body: RefreshIndicator(
        onRefresh: () async => ref.invalidate(tdsLedgerProvider),
        child: ListView(
          padding: const EdgeInsets.fromLTRB(16, 12, 16, 96),
          children: [
            RegisterPeriodBar(value: _period, onChanged: (p) => setState(() => _period = p)),
            const SizedBox(height: 14),
            ...async.when(
              loading: () => [const AppLoader()],
              error: (e, _) => [
                AppErrorState(
                    compact: true, message: friendlyErrorMessage(e), onRetry: () => ref.invalidate(tdsLedgerProvider(key)))
              ],
              data: (r) => [
                _Headline(report: r),
                const SizedBox(height: 18),
                _Quarters(title: 'TDS payable by quarter', rows: r.payableQuarters, creditLabel: 'Deducted', debitLabel: 'Deposited'),
                _Quarters(title: 'TDS receivable by quarter', rows: r.receivableQuarters, creditLabel: 'Adjusted', debitLabel: 'Booked'),
                _Statement(statement: r.payable, hint: 'Credit: TDS held back from payments. Debit: TDS deposited with the government.'),
                const SizedBox(height: 18),
                _Statement(statement: r.receivable, hint: 'Debit: TDS deducted by others from our income. Credit: adjusted against tax.'),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _Headline extends StatelessWidget {
  final TdsLedger report;
  const _Headline({required this.report});

  @override
  Widget build(BuildContext context) {
    Widget card(String label, double amount, String note, Color color, IconData icon, Key k) => Expanded(
          child: PremiumSurface(
            padding: const EdgeInsets.all(14),
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Icon(icon, color: color, size: 22),
              const SizedBox(height: 8),
              Text(label, style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: AppTheme.textSecondary)),
              const SizedBox(height: 3),
              Text(formatInr(amount), key: k, style: TextStyle(fontSize: 20, fontWeight: FontWeight.w800, color: color)),
              const SizedBox(height: 4),
              Text(note, style: const TextStyle(fontSize: 11.5, color: AppTheme.textSecondary, height: 1.3)),
            ]),
          ),
        );
    return Column(children: [
      Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
        card('To pay', report.toPay, 'Deducted, not yet deposited', AppTheme.error, Icons.north_east_rounded, const Key('tds-to-pay')),
        const SizedBox(width: 12),
        card('To receive', report.toReceive, 'Deducted by others, to claim', AppTheme.success, Icons.south_west_rounded,
            const Key('tds-to-receive')),
      ]),
      if (report.excessDeposited > 0)
        Padding(
          padding: const EdgeInsets.only(top: 10),
          child: Text('${formatInr(report.excessDeposited)} more was deposited than was deducted.',
              key: const Key('tds-excess'), style: const TextStyle(fontSize: 12.5, color: AppTheme.warning, fontWeight: FontWeight.w600)),
        ),
    ]);
  }
}

class _Quarters extends StatelessWidget {
  final String title, creditLabel, debitLabel;
  final List<TdsQuarter> rows;
  const _Quarters({required this.title, required this.rows, required this.creditLabel, required this.debitLabel});

  @override
  Widget build(BuildContext context) {
    if (rows.isEmpty) return const SizedBox.shrink();
    return Padding(
      padding: const EdgeInsets.only(bottom: 18),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        SectionHeading(title),
        const SizedBox(height: 8),
        PremiumSurface(
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
          child: Column(children: [
            for (final q in rows)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 8),
                child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Expanded(child: Text(q.quarter, style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 13))),
                  Column(crossAxisAlignment: CrossAxisAlignment.end, children: [
                    Text('$creditLabel ${formatInr(q.credit)}', style: const TextStyle(fontSize: 12.5)),
                    Text('$debitLabel ${formatInr(q.debit)}', style: const TextStyle(fontSize: 12.5, color: AppTheme.textSecondary)),
                  ]),
                ]),
              ),
          ]),
        ),
      ]),
    );
  }
}

class _Statement extends StatelessWidget {
  final TdsStatement statement;
  final String hint;
  const _Statement({required this.statement, required this.hint});

  @override
  Widget build(BuildContext context) {
    final s = statement;
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      SectionHeading(s.name),
      const SizedBox(height: 4),
      Text(hint, style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary, height: 1.3)),
      const SizedBox(height: 8),
      RegisterTotals(figures: [
        ('Opening', s.opening.label),
        ('Debit', formatInr(s.totalDebit)),
        ('Credit', formatInr(s.totalCredit)),
        ('Closing', s.closing.label),
      ]),
      const SizedBox(height: 8),
      if (s.lines.isEmpty)
        const Padding(padding: EdgeInsets.symmetric(vertical: 16), child: Center(child: Text('No entries in this period')))
      else
        PremiumSurface(
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 4),
          child: Column(children: [
            for (final (i, l) in s.lines.indexed) ...[
              if (i > 0) const Divider(height: 1),
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 10),
                child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Expanded(
                    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                      Text(l.particulars, style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 13)),
                      Text('${formatAccountsDate(l.date)} · ${l.voucherNumber}',
                          style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
                      if ((l.narration ?? '').isNotEmpty)
                        Text(l.narration!, style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
                    ]),
                  ),
                  const SizedBox(width: 10),
                  Column(crossAxisAlignment: CrossAxisAlignment.end, children: [
                    Text(l.debit > 0 ? 'Dr ${formatInr(l.debit)}' : 'Cr ${formatInr(l.credit)}',
                        style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 13)),
                    Text(l.balance.label, style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
                  ]),
                ]),
              ),
            ],
          ]),
        ),
    ]);
  }
}
