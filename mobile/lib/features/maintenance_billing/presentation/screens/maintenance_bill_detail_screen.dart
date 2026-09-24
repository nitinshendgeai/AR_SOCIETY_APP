import 'dart:io';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:path_provider/path_provider.dart';
import 'package:share_plus/share_plus.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/billing/domain/entities/billing_entities.dart' show paymentModeLabel;
import 'package:ar_society_app/features/billing/presentation/screens/online_payment_submit_screen.dart';
import 'package:ar_society_app/features/maintenance_billing/data/maintenance_billing_api.dart';
import 'package:ar_society_app/features/maintenance_billing/presentation/providers/maintenance_billing_providers.dart';
import 'package:ar_society_app/features/maintenance_billing/presentation/screens/billing_cycle_screen.dart' show billStatusColor;
import 'package:ar_society_app/shared/widgets/app_widgets.dart';

/// One maintenance bill. [canManage] (society side) adds Issue / Record
/// Payment / Cancel; residents get the read-only view plus PDF sharing.
class MaintenanceBillDetailScreen extends ConsumerStatefulWidget {
  final String billId;
  final String? societyId;
  final bool canManage;
  const MaintenanceBillDetailScreen({
    super.key,
    required this.billId,
    this.societyId,
    this.canManage = false,
  });

  @override
  ConsumerState<MaintenanceBillDetailScreen> createState() => _MaintenanceBillDetailScreenState();
}

class _MaintenanceBillDetailScreenState extends ConsumerState<MaintenanceBillDetailScreen> {
  bool _busy = false;

  void _refresh(MaintenanceBill bill) {
    ref.invalidate(maintenanceBillProvider(widget.billId));
    if (widget.societyId != null) invalidateCycle(ref, widget.societyId!, bill.cycleId);
    ref.invalidate(myBillsProvider);
  }

  Future<void> _run(MaintenanceBill bill, Future<void> Function() action, String done) async {
    setState(() => _busy = true);
    try {
      await action();
      _refresh(bill);
      if (mounted) AppToast.success(context, done);
    } catch (e) {
      if (mounted) showErrorToast(context, e);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _sharePdf(MaintenanceBill bill) async {
    setState(() => _busy = true);
    try {
      final bytes = await ref.read(maintenanceBillingApiProvider).billPdf(bill.id);
      final dir = await getTemporaryDirectory();
      final file = File('${dir.path}/${bill.invoiceNumber}.pdf');
      await file.writeAsBytes(bytes);
      await Share.shareXFiles([XFile(file.path)], subject: 'Maintenance Bill ${bill.invoiceNumber}');
    } catch (e) {
      if (mounted) showErrorToast(context, e);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _cancel(MaintenanceBill bill) async {
    final reasonCtrl = TextEditingController();
    final reason = await showDialog<String>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Cancel this bill?'),
        content: Column(mainAxisSize: MainAxisSize.min, children: [
          Text('${bill.flatLabel} · ${formatRupees(bill.totalAmount)}\n'
              'The amount is removed from the flat\'s dues.'),
          const SizedBox(height: 12),
          TextField(
            controller: reasonCtrl,
            autofocus: true,
            decoration: const InputDecoration(labelText: 'Reason *', hintText: 'e.g. Raised in error'),
          ),
        ]),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Keep Bill')),
          TextButton(
            style: TextButton.styleFrom(foregroundColor: AppTheme.error),
            onPressed: () {
              if (reasonCtrl.text.trim().isNotEmpty) Navigator.pop(ctx, reasonCtrl.text.trim());
            },
            child: const Text('Cancel Bill'),
          ),
        ],
      ),
    );
    if (reason == null) return;
    await _run(bill, () => ref.read(maintenanceBillingApiProvider).cancelBill(bill.id, reason),
        'Bill cancelled');
  }

  Future<void> _recordPayment(MaintenanceBill bill) async {
    await Navigator.push(context, MaterialPageRoute(
      builder: (_) => OnlinePaymentSubmitScreen(
        presetWingId: bill.wingId,
        presetFlatId: bill.flatId,
        presetBillId: bill.id,
        presetAmount: bill.outstanding,
      ),
    ));
    _refresh(bill);
  }

  @override
  Widget build(BuildContext context) {
    final billAsync = ref.watch(maintenanceBillProvider(widget.billId));
    return Scaffold(
      backgroundColor: AppTheme.surface,
      appBar: AppBar(
        title: Text(billAsync.valueOrNull?.invoiceNumber ?? 'Bill'),
        actions: [
          if (billAsync.valueOrNull != null)
            IconButton(
              tooltip: 'Share PDF',
              icon: const Icon(Icons.ios_share_rounded),
              onPressed: _busy ? null : () => _sharePdf(billAsync.value!),
            ),
        ],
      ),
      bottomNavigationBar: billAsync.valueOrNull == null ? null : _actions(billAsync.value!),
      body: billAsync.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (e, _) => Center(
            child: Padding(
          padding: const EdgeInsets.all(24),
          child: Text(friendlyErrorMessage(e), style: const TextStyle(color: AppTheme.error)),
        )),
        data: (bill) => RefreshIndicator(
          onRefresh: () async => _refresh(bill),
          child: ListView(
            padding: const EdgeInsets.all(16),
            children: [
              _Summary(bill: bill),
              const SizedBox(height: 16),
              _Section(title: 'Charges', child: _LineItems(bill: bill)),
              const SizedBox(height: 16),
              _Section(
                title: 'Payments',
                child: bill.payments.isEmpty
                    ? const Padding(
                        padding: EdgeInsets.symmetric(vertical: 8),
                        child: Text('No payments recorded yet',
                            style: TextStyle(color: AppTheme.textSecondary)),
                      )
                    : Column(children: [
                        for (final p in bill.payments)
                          ListTile(
                            contentPadding: EdgeInsets.zero,
                            leading: const Icon(Icons.check_circle_rounded, color: AppTheme.success),
                            title: Text(formatRupees(p.amount),
                                style: const TextStyle(fontWeight: FontWeight.w600)),
                            subtitle: Text([
                              formatBillDate(p.paymentDate),
                              paymentModeLabel(p.paymentMode),
                              p.receiptNumber,
                            ].join(' · ')),
                          ),
                      ]),
              ),
              if (bill.isCancelled && bill.cancellationReason != null) ...[
                const SizedBox(height: 16),
                _Section(title: 'Cancelled', child: Text(bill.cancellationReason!)),
              ],
              if (!widget.canManage && bill.canRecordPayment) ...[
                const SizedBox(height: 16),
                const Text(
                  'Pay the society office by UPI, bank transfer, cheque or cash. '
                  'Your bill updates here once the payment is recorded.',
                  style: TextStyle(fontSize: 12, color: AppTheme.textSecondary),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }

  Widget? _actions(MaintenanceBill bill) {
    if (!widget.canManage) return null;
    final buttons = <Widget>[
      if (!bill.isPaid && !bill.isCancelled)
        OutlinedButton(
          style: OutlinedButton.styleFrom(foregroundColor: AppTheme.error),
          onPressed: _busy ? null : () => _cancel(bill),
          child: const Text('Cancel Bill'),
        ),
      if (bill.isGenerated)
        ElevatedButton(
          onPressed: _busy ? null : () => _run(bill,
              () => ref.read(maintenanceBillingApiProvider).issueBill(bill.id), 'Bill issued'),
          child: const Text('Issue Bill'),
        )
      else if (bill.canRecordPayment)
        ElevatedButton(
          onPressed: _busy ? null : () => _recordPayment(bill),
          child: const Text('Record Payment'),
        ),
    ];
    if (buttons.isEmpty) return null;
    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.fromLTRB(16, 8, 16, 12),
        child: Row(children: [
          for (var i = 0; i < buttons.length; i++) ...[
            if (i > 0) const SizedBox(width: 12),
            Expanded(child: buttons[i]),
          ],
        ]),
      ),
    );
  }
}

class _Summary extends StatelessWidget {
  final MaintenanceBill bill;
  const _Summary({required this.bill});

  @override
  Widget build(BuildContext context) {
    final status = bill.displayStatus;
    final color = billStatusColor(status);
    final settled = bill.isPaid || bill.isCancelled;
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppTheme.cardBg,
        borderRadius: BorderRadius.circular(16),
        boxShadow: AppTheme.cardShadow,
      ),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Expanded(
            child: Text(bill.flatLabel.isEmpty ? '—' : bill.flatLabel,
                style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w600)),
          ),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
            decoration: BoxDecoration(
              color: color.withOpacity(0.12),
              borderRadius: BorderRadius.circular(20),
            ),
            child: Text(billStatusLabel(status),
                style: TextStyle(fontSize: 11, fontWeight: FontWeight.w600, color: color)),
          ),
        ]),
        if (bill.residentName != null)
          Text(bill.residentName!, style: const TextStyle(color: AppTheme.textSecondary)),
        const SizedBox(height: 16),
        Text(settled ? 'Bill amount' : 'Balance due',
            style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
        Text(
          formatRupees(settled ? bill.totalAmount : bill.outstanding),
          style: TextStyle(
            fontSize: 28,
            fontWeight: FontWeight.w700,
            color: bill.isOverdue ? AppTheme.error : AppTheme.textPrimary,
            fontFeatures: const [FontFeature.tabularFigures()],
          ),
        ),
        const SizedBox(height: 12),
        Wrap(spacing: 20, runSpacing: 8, children: [
          _Meta(label: 'Period', value: bill.cycleName ?? '—'),
          _Meta(label: 'Bill date', value: formatBillDate(bill.billDate)),
          _Meta(label: 'Due date', value: formatBillDate(bill.dueDate)),
          if (amountOf(bill.paidAmount) > 0)
            _Meta(label: 'Paid', value: formatRupees(bill.paidAmount)),
        ]),
      ]),
    );
  }
}

class _Meta extends StatelessWidget {
  final String label;
  final String value;
  const _Meta({required this.label, required this.value});

  @override
  Widget build(BuildContext context) => Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(label, style: const TextStyle(fontSize: 11, color: AppTheme.textSecondary)),
          Text(value, style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w500)),
        ],
      );
}

class _Section extends StatelessWidget {
  final String title;
  final Widget child;
  const _Section({required this.title, required this.child});

  @override
  Widget build(BuildContext context) => Container(
        width: double.infinity,
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: AppTheme.cardBg,
          borderRadius: BorderRadius.circular(16),
          boxShadow: AppTheme.cardShadow,
        ),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(title, style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w700)),
          const SizedBox(height: 8),
          child,
        ]),
      );
}

class _LineItems extends StatelessWidget {
  final MaintenanceBill bill;
  const _LineItems({required this.bill});

  Widget _row(String label, String value, {bool bold = false, Color? color}) => Padding(
        padding: const EdgeInsets.symmetric(vertical: 5),
        child: Row(children: [
          Expanded(
            child: Text(label,
                style: TextStyle(fontWeight: bold ? FontWeight.w700 : FontWeight.w400, color: color)),
          ),
          Text(formatRupees(value),
              style: TextStyle(fontWeight: bold ? FontWeight.w700 : FontWeight.w500, color: color)),
        ]),
      );

  @override
  Widget build(BuildContext context) => Column(children: [
        for (final li in bill.lineItems)
          _row(
            amountOf(li.taxAmount) > 0
                ? '${li.description} (incl. ${formatRupees(li.taxAmount)} tax)'
                : li.description,
            li.total,
          ),
        const Divider(height: 20),
        if (amountOf(bill.penaltyAmount) > 0) _row('Late fee', bill.penaltyAmount),
        _row('Total', bill.totalAmount, bold: true),
        if (amountOf(bill.paidAmount) > 0) _row('Paid', bill.paidAmount, color: AppTheme.success),
      ]);
}
