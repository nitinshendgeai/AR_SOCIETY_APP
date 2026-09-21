import 'dart:io';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:path_provider/path_provider.dart';
import 'package:share_plus/share_plus.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/features/billing/data/repositories/billing_repository.dart';
import 'package:ar_society_app/features/billing/domain/entities/billing_entities.dart';
import 'package:ar_society_app/features/billing/presentation/providers/billing_providers.dart';

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
        content: TextField(
          controller: notesCtrl,
          maxLines: 2,
          decoration: const InputDecoration(labelText: 'Notes (optional)'),
        ),
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
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text(friendlyErrorMessage(e)), backgroundColor: AppTheme.error));
      }
    } finally {
      if (mounted) setState(() => _updating = false);
    }
  }

  Future<void> _shareReceipt() async {
    setState(() => _sharingReceipt = true);
    try {
      final result = await ref.read(billingRepositoryProvider).getReceiptPdfBytes(widget.paymentId);
      switch (result) {
        case BillingSuccess(:final data):
          final dir = await getTemporaryDirectory();
          final file = File('${dir.path}/receipt_${widget.paymentId}.pdf');
          await file.writeAsBytes(data);
          await Share.shareXFiles([XFile(file.path)], subject: 'Payment Receipt');
        case BillingFailure(:final message):
          throw Exception(message);
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text(friendlyErrorMessage(e)), backgroundColor: AppTheme.error));
      }
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
      return const Scaffold(body: Center(child: CircularProgressIndicator()));
    }
    final screenshotAsync = ref.watch(onlinePaymentScreenshotProvider(widget.paymentId));

    return Scaffold(
      backgroundColor: AppTheme.surface,
      appBar: AppBar(title: Text(payment.receiptNumber)),
      body: ListView(
        padding: const EdgeInsets.all(20),
        children: [
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                _row('Flat', '${payment.wingName ?? '-'} / ${payment.flatNumber ?? '-'}'),
                _row('Amount', '₹${payment.amount}'),
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
          const Text('Screenshot', style: TextStyle(fontWeight: FontWeight.w700, fontSize: 14)),
          const SizedBox(height: 8),
          screenshotAsync.when(
            loading: () => const Center(child: CircularProgressIndicator()),
            error: (e, _) => Text(friendlyErrorMessage(e), style: const TextStyle(color: AppTheme.error)),
            data: (bytes) => ClipRRect(
              borderRadius: BorderRadius.circular(8),
              child: Image.memory(bytes, fit: BoxFit.contain),
            ),
          ),
          const SizedBox(height: 20),
          OutlinedButton.icon(
            onPressed: _sharingReceipt ? null : _shareReceipt,
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
