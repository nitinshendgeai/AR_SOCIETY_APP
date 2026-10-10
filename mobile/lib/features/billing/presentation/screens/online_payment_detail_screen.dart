import 'package:flutter/material.dart';
import 'package:ar_society_app/core/motion/loading.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:share_plus/share_plus.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/features/billing/data/repositories/billing_repository.dart';
import 'package:ar_society_app/features/billing/domain/entities/billing_entities.dart';
import 'package:ar_society_app/features/billing/presentation/providers/billing_providers.dart';
import 'package:ar_society_app/shared/widgets/app_data_table.dart' show tableMoney;
import 'package:ar_society_app/shared/widgets/app_widgets.dart';
import 'package:ar_society_app/shared/widgets/app_form.dart';

class OnlinePaymentDetailScreen extends ConsumerStatefulWidget {
  final String paymentId;
  const OnlinePaymentDetailScreen({super.key, required this.paymentId});

  @override
  ConsumerState<OnlinePaymentDetailScreen> createState() => _OnlinePaymentDetailScreenState();
}

class _OnlinePaymentDetailScreenState extends ConsumerState<OnlinePaymentDetailScreen> {
  bool _updating = false;
  bool _sharingReceipt = false;

  OnlinePaymentEntity? _findPayment(String societyId) {
    final list = ref.watch(onlinePaymentsProvider(societyId)).valueOrNull;
    if (list == null) return null;
    for (final p in list) {
      if (p.id == widget.paymentId) return p;
    }
    return null;
  }

  Future<void> _updateStatus(String societyId, String status) async {
    final notesCtrl = TextEditingController();
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(status == 'reconciled' ? 'Mark Reconciled?' : 'Reject Submission?'),
        content: FormFieldBox(label: 'Notes (optional)', child: TextField(
          controller: notesCtrl,
          maxLines: 2,
          decoration: const InputDecoration(),
        )),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancel')),
          ElevatedButton(
            style: ElevatedButton.styleFrom(
                backgroundColor: status == 'rejected' ? AppTheme.error : AppTheme.success),
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('Confirm'),
          ),
        ],
      ),
    );
    if (confirmed != true) return;

    setState(() => _updating = true);
    try {
      await ref.read(onlinePaymentsProvider(societyId).notifier).updateStatus(
            widget.paymentId, status,
            reviewNotes: notesCtrl.text.trim().isEmpty ? null : notesCtrl.text.trim(),
          );
    } catch (e) {
      if (mounted) showErrorToast(context, e);
    } finally {
      if (mounted) setState(() => _updating = false);
    }
  }

  Future<void> _shareReceipt(String receiptNumber) async {
    setState(() => _sharingReceipt = true);
    try {
      final result = await ref.read(billingRepositoryProvider).getReceiptPdfBytes(widget.paymentId);
      switch (result) {
        case BillingSuccess(:final data):
          // From memory, not a temp file, so it works on the web too.
          final fileName = 'Receipt-$receiptNumber.pdf';
          await Share.shareXFiles(
            [XFile.fromData(data, name: fileName, mimeType: 'application/pdf')],
            fileNameOverrides: [fileName],
            subject: 'Payment Receipt',
          );
        case BillingFailure(:final message):
          throw Exception(message);
      }
    } catch (e) {
      if (mounted) showErrorToast(context, e);
    } finally {
      if (mounted) setState(() => _sharingReceipt = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final societyId = ref.watch(currentUserProvider)?.societyId;
    if (societyId == null) {
      return const Scaffold(body: Center(child: Text('No society context')));
    }
    final payment = _findPayment(societyId);
    if (payment == null) {
      return const Scaffold(body: const AppLoader());
    }

    return AppPage(
      title: payment.receiptNumber,
      body: ListView(
        padding: const EdgeInsets.all(20),
        children: [
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                _row('Flat', '${payment.wingName ?? '-'} / ${payment.flatNumber ?? '-'}'),
                _row('Amount', '₹${payment.amount}'),
                if (!payment.isOnBill) _row('On Account Of', onlinePaymentPurposeLabel(payment.purpose)),
                _row('Payment Date',
                    '${payment.paymentDate.day}/${payment.paymentDate.month}/${payment.paymentDate.year}'),
                _row('Payment Mode', paymentModeLabel(payment.paymentMode)),
                _row('Transaction Ref', payment.transactionRef ?? '-'),
                _row('Bank', payment.bankName ?? '-'),
                _row('Status', reconciliationStatusLabel(payment.status)),
                if (payment.notes != null) _row('Notes', payment.notes!),
                if (payment.reviewNotes != null) _row('Review Notes', payment.reviewNotes!),
              ]),
            ),
          ),
          const SizedBox(height: 16),
          _SetOffCard(payment),
          const SizedBox(height: 16),
          const Text('Screenshot', style: TextStyle(fontWeight: FontWeight.w700, fontSize: 14)),
          const SizedBox(height: 8),
          if (!payment.hasScreenshot)
            const Text('No screenshot attached', style: TextStyle(color: AppTheme.textSecondary, fontSize: 13))
          else
            Consumer(builder: (context, ref, _) {
              final screenshotAsync = ref.watch(onlinePaymentScreenshotProvider(widget.paymentId));
              return screenshotAsync.when(
                loading: () => const AppLoader(),
                error: (e, _) => Text(friendlyErrorMessage(e), style: const TextStyle(color: AppTheme.error)),
                data: (bytes) => ClipRRect(
                  borderRadius: BorderRadius.circular(8),
                  child: Image.memory(bytes, fit: BoxFit.contain),
                ),
              );
            }),
          const SizedBox(height: 20),
          OutlinedButton.icon(
            onPressed: _sharingReceipt ? null : () => _shareReceipt(payment.receiptNumber),
            icon: _sharingReceipt
                ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2))
                : const Icon(Icons.receipt_long_outlined),
            label: const Text('View / Share Receipt'),
          ),
          if (payment.isPending) ...[
            const SizedBox(height: 20),
            const Text('Reconciliation', style: TextStyle(fontWeight: FontWeight.w700, fontSize: 14)),
            const SizedBox(height: 8),
            Row(children: [
              Expanded(
                child: ElevatedButton.icon(
                  style: ElevatedButton.styleFrom(backgroundColor: AppTheme.success),
                  onPressed: _updating ? null : () => _updateStatus(societyId, 'reconciled'),
                  icon: const Icon(Icons.check_circle_outline),
                  label: const Text('Reconciled'),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: ElevatedButton.icon(
                  style: ElevatedButton.styleFrom(backgroundColor: AppTheme.error),
                  onPressed: _updating ? null : () => _updateStatus(societyId, 'rejected'),
                  icon: const Icon(Icons.cancel_outlined),
                  label: const Text('Reject'),
                ),
              ),
            ]),
          ],
        ],
      ),
    );
  }

  Widget _row(String label, String value) => Padding(
        padding: const EdgeInsets.only(bottom: 8),
        child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
          SizedBox(width: 120, child: Text(label, style: const TextStyle(color: AppTheme.textSecondary))),
          Expanded(child: Text(value, style: const TextStyle(fontWeight: FontWeight.w500))),
        ]),
      );
}

/// The bills a payment was set off against, oldest first, and the advance
/// left over. Set-offs undone by a rejection or a cancelled bill are shown
/// struck out with the reason.
class _SetOffCard extends StatelessWidget {
  final OnlinePaymentEntity payment;
  const _SetOffCard(this.payment);

  static String _rs(double v) => tableMoney(v);

  @override
  Widget build(BuildContext context) {
    final live = payment.liveSetOffs;
    final released = payment.setOffs.where((a) => !a.isLive).toList();
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          const Text('Set off against bills', style: TextStyle(fontWeight: FontWeight.w700, fontSize: 14)),
          const SizedBox(height: 4),
          const Text('A payment settles the flat\'s open bills, oldest first. Anything over is kept as an '
              'advance and set off against the next bill.',
              style: TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
          const SizedBox(height: 10),
          if (live.isEmpty && payment.unappliedAmount <= 0)
            Text(payment.isRejected ? 'Rejected — not set off against any bill.' : 'Not set off against any bill.',
                style: const TextStyle(fontSize: 13, color: AppTheme.textSecondary)),
          for (final a in live)
            Padding(
              padding: const EdgeInsets.only(bottom: 6),
              child: Row(children: [
                const Icon(Icons.check_circle_rounded, size: 16, color: AppTheme.success),
                const SizedBox(width: 8),
                Expanded(child: Text('Bill ${a.invoiceNumber ?? a.billId}', style: const TextStyle(fontSize: 13.5))),
                Text(_rs(a.amount), style: const TextStyle(fontSize: 13.5, fontWeight: FontWeight.w600)),
              ]),
            ),
          if (payment.unappliedAmount > 0)
            Padding(
              padding: const EdgeInsets.only(bottom: 6),
              child: Row(children: [
                const Icon(Icons.savings_outlined, size: 16, color: AppTheme.primary),
                const SizedBox(width: 8),
                const Expanded(
                    child: Text('Advance — for the next bill', style: TextStyle(fontSize: 13.5))),
                Text(_rs(payment.unappliedAmount), style: const TextStyle(fontSize: 13.5, fontWeight: FontWeight.w600)),
              ]),
            ),
          for (final a in released)
            Padding(
              padding: const EdgeInsets.only(bottom: 6),
              child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                const Icon(Icons.undo_rounded, size: 16, color: AppTheme.textTertiary),
                const SizedBox(width: 8),
                Expanded(
                  child: Text('Bill ${a.invoiceNumber ?? a.billId} — undone${a.releasedReason == null ? '' : ': ${a.releasedReason}'}',
                      style: const TextStyle(fontSize: 12.5, color: AppTheme.textSecondary)),
                ),
                Text(_rs(a.amount),
                    style: const TextStyle(
                        fontSize: 12.5, color: AppTheme.textTertiary, decoration: TextDecoration.lineThrough)),
              ]),
            ),
        ]),
      ),
    );
  }
}
