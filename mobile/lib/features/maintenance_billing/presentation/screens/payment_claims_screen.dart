import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/api/api_client.dart' show friendlyErrorMessage;
import 'package:ar_society_app/core/motion/loading.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/features/billing/domain/entities/billing_entities.dart' show paymentModeLabel;
import 'package:ar_society_app/features/billing/presentation/providers/billing_providers.dart' show onlinePaymentsProvider;
import 'package:ar_society_app/features/maintenance_billing/data/maintenance_billing_api.dart' show formatBillDate, formatRupees;
import 'package:ar_society_app/features/maintenance_billing/data/payment_claims_api.dart';
import 'package:ar_society_app/features/staff/presentation/widgets/staff_widgets.dart' show AppCard;
import 'package:ar_society_app/shared/widgets/app_form.dart' show AppPage;
import 'package:ar_society_app/shared/widgets/app_widgets.dart';

/// A line on the online-payments screen: "N payments reported by residents are waiting for you". Tap to review them.
/// Draws nothing when there are none.
class ResidentClaimsBanner extends ConsumerWidget {
  final String societyId;
  final EdgeInsets padding;
  const ResidentClaimsBanner({super.key, required this.societyId, this.padding = EdgeInsets.zero});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final n = ref.watch(pendingPaymentClaimsProvider(societyId)).valueOrNull?.length ?? 0;
    if (n == 0) return const SizedBox.shrink();
    return Padding(
      padding: padding,
      child: InkWell(
        key: const Key('claims-banner'),
        borderRadius: BorderRadius.circular(AppTheme.radiusM),
        onTap: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => const PaymentClaimsScreen())),
        child: Container(
          padding: const EdgeInsets.all(14),
          decoration: BoxDecoration(
            color: AppTheme.primary.withOpacity(0.08),
            borderRadius: BorderRadius.circular(AppTheme.radiusM),
            border: Border.all(color: AppTheme.primary.withOpacity(0.35)),
          ),
          child: Row(children: [
            const Icon(Icons.how_to_reg_rounded, color: AppTheme.primary),
            const SizedBox(width: 10),
            Expanded(
              child: Text('$n payment${n == 1 ? '' : 's'} reported by residents ${n == 1 ? 'is' : 'are'} waiting for you to check',
                  style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 13)),
            ),
            const Icon(Icons.chevron_right_rounded, color: AppTheme.primary),
          ]),
        ),
      ),
    );
  }
}

/// The office checks what residents reported against the bank, then confirms (the payment is recorded, the bill is
/// marked paid and a receipt issued) or rejects it with a reason the resident will read.
class PaymentClaimsScreen extends ConsumerWidget {
  const PaymentClaimsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final societyId = ref.watch(currentUserProvider)?.societyId;
    if (societyId == null) {
      return const AppPage(title: 'Payments reported', body: Center(child: Text('No society')));
    }
    final claims = ref.watch(pendingPaymentClaimsProvider(societyId));
    return AppPage(
      title: 'Payments reported by residents',
      body: RefreshIndicator(
        onRefresh: () async => ref.invalidate(pendingPaymentClaimsProvider(societyId)),
        child: claims.when(
          loading: () => const SkeletonList(),
          error: (e, _) => ListView(children: [
            Padding(padding: const EdgeInsets.all(24), child: Text(friendlyErrorMessage(e), style: const TextStyle(color: AppTheme.error))),
          ]),
          data: (list) => list.isEmpty
              ? ListView(children: const [
                  Padding(
                    padding: EdgeInsets.only(top: 60),
                    child: AppEmptyState(
                      icon: Icons.task_alt_rounded,
                      title: 'Nothing waiting',
                      subtitle: 'Payments residents report from the app will appear here for you to check.',
                    ),
                  ),
                ])
              : ListView.separated(
                  padding: const EdgeInsets.all(16),
                  itemCount: list.length,
                  separatorBuilder: (_, __) => const SizedBox(height: 12),
                  itemBuilder: (_, i) => _ClaimCard(claim: list[i], societyId: societyId),
                ),
        ),
      ),
    );
  }
}

class _ClaimCard extends ConsumerStatefulWidget {
  final PaymentClaimItem claim;
  final String societyId;
  const _ClaimCard({required this.claim, required this.societyId});

  @override
  ConsumerState<_ClaimCard> createState() => _ClaimCardState();
}

class _ClaimCardState extends ConsumerState<_ClaimCard> {
  bool _busy = false;

  void _done() {
    ref.invalidate(pendingPaymentClaimsProvider(widget.societyId));
    ref.invalidate(onlinePaymentsProvider(widget.societyId));
  }

  Future<void> _viewShot() async {
    try {
      final bytes = await ref.read(paymentClaimsApiProvider).screenshot(widget.claim.id);
      if (!mounted) return;
      await showDialog<void>(
        context: context,
        builder: (ctx) => Dialog(
          child: InteractiveViewer(child: Image.memory(bytes, fit: BoxFit.contain)),
        ),
      );
    } catch (e) {
      if (mounted) showErrorToast(context, e);
    }
  }

  Future<void> _confirm() async {
    final note = TextEditingController();
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Confirm this payment?'),
        content: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text('${formatRupees(widget.claim.amount)} from ${widget.claim.flatLabel}. '
              'It is recorded, the bill is marked paid and a receipt is issued. Check it is in the bank first.'),
          const SizedBox(height: 12),
          TextField(controller: note, decoration: const InputDecoration(hintText: 'Note (optional)')),
        ]),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Not yet')),
          ElevatedButton(key: const Key('claim-confirm-go'), onPressed: () => Navigator.pop(ctx, true), child: const Text('Confirm')),
        ],
      ),
    );
    final text = note.text.trim();
    if (ok != true) return;
    setState(() => _busy = true);
    try {
      final c = await ref.read(paymentClaimsApiProvider).confirm(widget.claim.id, notes: text);
      _done();
      if (mounted) AppToast.success(context, 'Recorded. Receipt ${c.receiptNumber ?? ''}'.trim());
    } catch (e) {
      if (mounted) showErrorToast(context, e);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _reject() async {
    final reason = TextEditingController();
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Reject this payment?'),
        content: TextField(
          key: const Key('claim-reject-reason'),
          controller: reason,
          autofocus: true,
          decoration: const InputDecoration(hintText: 'Why? The resident will read this'),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancel')),
          TextButton(
            style: TextButton.styleFrom(foregroundColor: AppTheme.error),
            onPressed: () {
              if (reason.text.trim().isNotEmpty) Navigator.pop(ctx, true);
            },
            child: const Text('Reject'),
          ),
        ],
      ),
    );
    final text = reason.text.trim();
    if (ok != true) return;
    setState(() => _busy = true);
    try {
      await ref.read(paymentClaimsApiProvider).reject(widget.claim.id, text);
      _done();
    } catch (e) {
      if (mounted) showErrorToast(context, e);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final c = widget.claim;
    return AppCard(
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Expanded(
            child: Text('${c.flatLabel}  ·  ${formatRupees(c.amount)}',
                style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w800)),
          ),
          Text(paymentModeLabel(c.paymentMode), style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
        ]),
        const SizedBox(height: 6),
        Text(
          [
            'Paid ${formatBillDate(c.paymentDate)}',
            if (c.claimedByName != null) 'reported by ${c.claimedByName}',
            if (c.billInvoiceNumber != null) 'bill ${c.billInvoiceNumber}',
          ].join('  ·  '),
          style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary),
        ),
        if (c.transactionRef != null) ...[
          const SizedBox(height: 4),
          SelectableText('Reference: ${c.transactionRef}', style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600)),
        ],
        if (c.notes != null) ...[
          const SizedBox(height: 4),
          Text(c.notes!, style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
        ],
        const SizedBox(height: 10),
        Row(children: [
          if (c.hasScreenshot)
            TextButton.icon(onPressed: _viewShot, icon: const Icon(Icons.image_outlined, size: 18), label: const Text('Screenshot')),
          const Spacer(),
          OutlinedButton(
            key: const Key('claim-reject'),
            style: OutlinedButton.styleFrom(foregroundColor: AppTheme.error, minimumSize: const Size(0, 44)),
            onPressed: _busy ? null : _reject,
            child: const Text('Reject'),
          ),
          const SizedBox(width: 8),
          ElevatedButton(
            key: const Key('claim-confirm'),
            style: ElevatedButton.styleFrom(minimumSize: const Size(0, 44)),
            onPressed: _busy ? null : _confirm,
            child: const Text('Confirm'),
          ),
        ]),
      ]),
    );
  }
}
