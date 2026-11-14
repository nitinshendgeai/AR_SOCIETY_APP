import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/layout/app_sheet.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/billing/domain/entities/billing_entities.dart' show paymentModeLabel;
import 'package:ar_society_app/features/maintenance_billing/data/maintenance_billing_api.dart';
import 'package:ar_society_app/features/maintenance_billing/data/payment_claims_api.dart';
import 'package:ar_society_app/features/maintenance_billing/presentation/screens/claim_payment_screen.dart';

/// Opens the "I have paid" form and returns whether the resident sent it.
Future<bool> openClaimPayment(BuildContext context, {MaintenanceBill? bill}) async =>
    await Navigator.of(context).push<bool>(MaterialPageRoute(builder: (_) => ClaimPaymentScreen(bill: bill))) ?? false;

/// "How to pay" in a sheet: the society's UPI id and bank account with Copy, and an "I have paid" button.
Future<void> showHowToPaySheet(BuildContext context, {MaintenanceBill? bill}) => showAppSheet<void>(
      context: context,
      builder: (ctx) => SafeArea(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(20, 8, 20, 20),
          child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.stretch, children: [
            const Text('How to pay', style: TextStyle(fontSize: 20, fontWeight: FontWeight.w800)),
            const SizedBox(height: 4),
            Text(
              bill == null
                  ? 'Pay the society using the details below, then tell the office.'
                  : 'Pay ${formatRupees(bill.outstanding)} using the details below, then tell the office.',
              style: const TextStyle(fontSize: 13, color: AppTheme.textSecondary),
            ),
            const SizedBox(height: 14),
            const HowToPayCard(),
            const SizedBox(height: 14),
            ElevatedButton.icon(
              key: const Key('i-have-paid'),
              onPressed: () {
                Navigator.of(ctx).pop();
                openClaimPayment(context, bill: bill);
              },
              icon: const Icon(Icons.check_circle_outline_rounded),
              label: const Text('I have paid'),
            ),
          ]),
        ),
      ),
    );

/// The society's UPI id and bank details, each with a copy button.
class HowToPayCard extends ConsumerWidget {
  const HowToPayCard({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final info = ref.watch(paymentInfoProvider);
    return info.when(
      loading: () => const Padding(padding: EdgeInsets.all(12), child: LinearProgressIndicator()),
      error: (_, __) => const _Plain('Could not load the payment details. Ask the society office where to pay.'),
      data: (i) {
        if (i.isEmpty) {
          return const _Plain('The society has not put its UPI or bank details here yet. Ask the office where to pay.');
        }
        return Container(
          padding: const EdgeInsets.all(14),
          decoration: BoxDecoration(
            color: AppTheme.cardBg,
            borderRadius: BorderRadius.circular(AppTheme.radiusM),
            boxShadow: AppTheme.cardShadow,
          ),
          child: Column(children: [
            if (i.hasUpi) _CopyRow('UPI ID', i.upiId!, Icons.qr_code_2_rounded),
            if (i.accountName != null && i.accountName!.isNotEmpty) _CopyRow('Account name', i.accountName!, Icons.badge_outlined),
            if (i.bankName != null && i.bankName!.isNotEmpty) _CopyRow('Bank', i.bankName!, Icons.account_balance_outlined),
            if (i.hasBank) _CopyRow('Account number', i.accountNumber!, Icons.numbers_rounded),
            if (i.ifsc != null && i.ifsc!.isNotEmpty) _CopyRow('IFSC', i.ifsc!, Icons.pin_outlined),
            if (i.notes != null && i.notes!.isNotEmpty)
              Padding(
                padding: const EdgeInsets.only(top: 8),
                child: Text(i.notes!, style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
              ),
          ]),
        );
      },
    );
  }
}

class _Plain extends StatelessWidget {
  final String text;
  const _Plain(this.text);

  @override
  Widget build(BuildContext context) => Container(
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          color: AppTheme.warningSoft,
          borderRadius: BorderRadius.circular(AppTheme.radiusM),
        ),
        child: Text(text, style: const TextStyle(fontSize: 13)),
      );
}

class _CopyRow extends StatelessWidget {
  final String label;
  final String value;
  final IconData icon;
  const _CopyRow(this.label, this.value, this.icon);

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.symmetric(vertical: 4),
        child: Row(children: [
          Icon(icon, size: 18, color: AppTheme.textSecondary),
          const SizedBox(width: 10),
          Expanded(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text(label, style: const TextStyle(fontSize: 11, color: AppTheme.textSecondary)),
              SelectableText(value, style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w700)),
            ]),
          ),
          IconButton(
            tooltip: 'Copy $label',
            icon: const Icon(Icons.copy_rounded, size: 18),
            onPressed: () {
              Clipboard.setData(ClipboardData(text: value));
              ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$label copied')));
            },
          ),
        ]),
      );
}

/// On My Bills: payments the resident reported that the office has not confirmed yet, and ones it could not, with why.
/// Draws nothing when there are none (or while loading / on failure).
class PaymentClaimsStrip extends ConsumerWidget {
  const PaymentClaimsStrip({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final open = (ref.watch(myPaymentClaimsProvider).valueOrNull ?? const <PaymentClaimItem>[])
        .where((c) => c.status != 'confirmed')
        .take(4)
        .toList();
    if (open.isEmpty) return const SizedBox.shrink();
    return Padding(
      padding: const EdgeInsets.only(bottom: 16),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        const Padding(
          padding: EdgeInsets.only(bottom: 8),
          child: Text('Payments you reported',
              style: TextStyle(fontSize: 13, fontWeight: FontWeight.w700, color: AppTheme.textSecondary)),
        ),
        for (final c in open) _ClaimTile(c),
      ]),
    );
  }
}

class _ClaimTile extends StatelessWidget {
  final PaymentClaimItem claim;
  const _ClaimTile(this.claim);

  @override
  Widget build(BuildContext context) {
    final rejected = claim.isRejected;
    final color = rejected ? AppTheme.error : AppTheme.warning;
    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: color.withOpacity(0.07),
        borderRadius: BorderRadius.circular(AppTheme.radiusM),
        border: Border.all(color: color.withOpacity(0.35)),
      ),
      child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Icon(rejected ? Icons.error_outline_rounded : Icons.hourglass_top_rounded, color: color, size: 20),
        const SizedBox(width: 10),
        Expanded(
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text('${formatRupees(claim.amount)}  ·  ${paymentModeLabel(claim.paymentMode)}'
                '${claim.billInvoiceNumber != null ? '  ·  ${claim.billInvoiceNumber}' : ''}',
                style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w700)),
            const SizedBox(height: 2),
            Text(
              rejected
                  ? 'The office could not confirm it: ${claim.reviewNotes ?? 'no reason given'}'
                  : 'Waiting for the office to check it against the bank',
              style: TextStyle(fontSize: 12, color: color, fontWeight: FontWeight.w600),
            ),
          ]),
        ),
      ]),
    );
  }
}
