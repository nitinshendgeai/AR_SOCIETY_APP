import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/l10n/app_locale.dart';
import 'package:ar_society_app/core/motion/loading.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/core/theme/design_tokens.dart';
import 'package:ar_society_app/features/maintenance_billing/data/maintenance_billing_api.dart';
import 'package:ar_society_app/features/maintenance_billing/presentation/providers/maintenance_billing_providers.dart';
import 'package:ar_society_app/shared/widgets/app_form.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';
import 'package:ar_society_app/shared/widgets/premium.dart';

/// The words for a balance. "Dr" is the accountant's way of saying the member owes the society, "Cr" that they are
/// in credit; a resident reads it in plain language.
String ledgerBalanceWords(MyLedgerFlat f) => f.settled
    ? 'Nothing due'
    : (f.drCr == 'Cr' ? 'You are in credit' : 'You owe the society');

/// A resident's account with the society for each flat they live in: the balance in plain words, what makes it up
/// (dues, and any advance paid ahead), and the latest entries. Read-only; the full books stay on the web app.
class MyLedgerScreen extends ConsumerWidget {
  const MyLedgerScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final async = ref.watch(myLedgerProvider);
    return AppPage(
      title: 'My Ledger',
      body: RefreshIndicator(
        onRefresh: () async => ref.invalidate(myLedgerProvider),
        child: async.when(
          loading: () => const SkeletonList(),
          error: (e, _) => AppErrorState(message: friendlyErrorMessage(e), onRetry: () => ref.invalidate(myLedgerProvider)),
          data: (ledger) => ledger.flats.isEmpty
              ? ListView(children: const [
                  SizedBox(height: 40),
                  AppEmptyState(
                    icon: Icons.account_balance_wallet_outlined,
                    title: 'No flat is linked to your account yet — contact your society admin.',
                  ),
                ])
              : ListView(
                  padding: const EdgeInsets.fromLTRB(16, 8, 16, 32),
                  children: [
                    for (final f in ledger.flats) ...[_FlatLedger(flat: f), const SizedBox(height: 20)],
                    Text(
                      context.trf('As of {date}. This is your account in the society\'s books; the bills screen lists each bill.',
                          {'date': _day(ledger.asOf)}),
                      style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary),
                    ),
                  ],
                ),
        ),
      ),
    );
  }
}

String _day(String iso) {
  final d = DateTime.tryParse(iso);
  return d == null ? iso : DateFormat('d MMM yyyy').format(d);
}

class _FlatLedger extends StatelessWidget {
  final MyLedgerFlat flat;
  const _FlatLedger({required this.flat});

  @override
  Widget build(BuildContext context) {
    final tone = flat.settled ? AppTone.success : (flat.drCr == 'Cr' ? AppTone.info : AppTone.warning);
    final colors = kToneColors[tone]!;
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      SectionHeading(flat.flatLabel),
      const SizedBox(height: 10),
      Container(
        width: double.infinity,
        padding: const EdgeInsets.all(18),
        decoration: BoxDecoration(
          color: solidTint(colors.accent),
          borderRadius: BorderRadius.circular(AppTheme.radiusXl),
          boxShadow: AppTheme.cardShadow,
        ),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(context.tr(ledgerBalanceWords(flat)),
              key: const Key('ledger-words'),
              style: TextStyle(fontSize: 13, fontWeight: FontWeight.w700, color: colors.foreground)),
          const SizedBox(height: 4),
          Semantics(
            label: '${context.tr(ledgerBalanceWords(flat))} ${formatRupees(flat.balance)}',
            excludeSemantics: true,
            child: Text(formatRupees(flat.balance),
                key: const Key('ledger-balance'),
                style: const TextStyle(
                    fontSize: 32,
                    fontWeight: FontWeight.w800,
                    letterSpacing: -0.6,
                    color: AppTheme.textPrimary,
                    fontFeatures: [FontFeature.tabularFigures()])),
          ),
          const SizedBox(height: 12),
          _kv(context, 'Dues', formatRupees(flat.dues)),
          _kv(context, 'Advance paid ahead', formatRupees(flat.advance)),
        ]),
      ),
      const SizedBox(height: 14),
      if (flat.lines.isEmpty)
        Padding(
          padding: const EdgeInsets.symmetric(vertical: 8),
          child: Text(context.tr('Nothing has been entered in this account yet.'),
              style: const TextStyle(color: AppTheme.textSecondary)),
        )
      else ...[
        Text(context.tr('Latest entries'), style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w700)),
        const SizedBox(height: 8),
        for (final l in flat.lines) _LineTile(line: l),
      ],
    ]);
  }

  Widget _kv(BuildContext context, String label, String value) => Padding(
        padding: const EdgeInsets.only(top: 4),
        child: Row(children: [
          Expanded(child: Text(context.tr(label), style: const TextStyle(fontSize: 13, color: AppTheme.textSecondary))),
          Text(value, style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600)),
        ]),
      );
}

class _LineTile extends StatelessWidget {
  final MyLedgerLine line;
  const _LineTile({required this.line});

  @override
  Widget build(BuildContext context) {
    final isBill = amountOf(line.debit) > 0;
    final amount = formatRupees(isBill ? line.debit : line.credit);
    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(color: AppTheme.cardBg, borderRadius: BorderRadius.circular(AppTheme.radiusM), boxShadow: AppTheme.cardShadow),
      child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
        AccentBadge(
            icon: isBill ? Icons.receipt_long_rounded : Icons.payments_rounded,
            accent: isBill ? kAccents[3] : kAccents[5],
            size: 36),
        const SizedBox(width: 12),
        Expanded(
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(line.narration.isEmpty ? context.tr(isBill ? 'Bill' : 'Payment') : line.narration,
                maxLines: 2, overflow: TextOverflow.ellipsis, style: const TextStyle(fontWeight: FontWeight.w600)),
            const SizedBox(height: 2),
            Text(_day(line.date), style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
          ]),
        ),
        const SizedBox(width: 8),
        Column(crossAxisAlignment: CrossAxisAlignment.end, children: [
          Text(isBill ? '+ $amount' : '− $amount',
              style: TextStyle(fontWeight: FontWeight.w700, color: kToneColors[isBill ? AppTone.warning : AppTone.success]!.foreground)),
          const SizedBox(height: 2),
          Text('${context.tr('Balance')} ${formatRupees(line.balance)} ${line.drCr}',
              style: const TextStyle(fontSize: 11, color: AppTheme.textSecondary)),
        ]),
      ]),
    );
  }
}
