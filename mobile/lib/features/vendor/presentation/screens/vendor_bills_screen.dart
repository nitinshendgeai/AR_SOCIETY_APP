import 'dart:async';

import 'package:ar_society_app/features/accounts/presentation/providers/accounts_providers.dart';
import 'package:ar_society_app/core/motion/loading.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/router/app_router.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/features/accounts/data/accounts_api.dart' show LedgerAccount, formatInr;
import 'package:ar_society_app/features/accounts/presentation/widgets/accounts_widgets.dart' show LedgerChooser;
import 'package:ar_society_app/features/vendor/data/vendors_work_api.dart' show BillPayment, PaymentTdsPreview;
import 'package:ar_society_app/features/vendor/domain/entities/vendor_entities.dart';
import 'package:ar_society_app/features/vendor/presentation/providers/vendor_providers.dart';
import 'package:ar_society_app/features/vendor/presentation/providers/vendors_work_providers.dart' show billPaymentsProvider, vendorOpenBillsProvider, vendorsWorkApiProvider;
import 'package:ar_society_app/features/vendor/presentation/widgets/payment_tds_card.dart';
import 'package:ar_society_app/features/vendor/presentation/widgets/procurement_widgets.dart' show DateField, askReason;
import 'package:ar_society_app/features/vendor/presentation/widgets/vendor_picker.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';
import 'package:ar_society_app/core/layout/app_sheet.dart';
import 'package:ar_society_app/shared/widgets/app_data_table.dart';
import 'package:ar_society_app/core/layout/app_shell.dart' show isDesktopLayout;
import 'package:ar_society_app/shared/widgets/app_form.dart';

/// FMC Manager/Admin/Committee: bills owed to vendors and payments made
/// against them — the society's payable side, the mirror of the
/// resident-facing Payments screen (billing module).
class VendorBillsScreen extends ConsumerStatefulWidget {
  const VendorBillsScreen({super.key});

  @override
  ConsumerState<VendorBillsScreen> createState() => _VendorBillsScreenState();
}

class _VendorBillsScreenState extends ConsumerState<VendorBillsScreen> {
  bool? _paidFilter; // null = all, false = unpaid, true = paid

  void _addBill(String societyId) => showAppSheet(
        context: context,
        builder: (_) => _AddBillSheet(societyId: societyId),
      );

  void _openBill(String societyId, VendorInvoiceEntity inv) => showAppSheet(
        context: context,
        builder: (_) => _BillDetailSheet(invoice: inv, societyId: societyId),
      );

  /// Desktop: payables summary above a sortable bills register.
  Widget _table(String societyId, AsyncValue<List<VendorInvoiceEntity>> invoicesAsync) {
    final invoices = invoicesAsync.valueOrNull ?? const <VendorInvoiceEntity>[];
    final rows = _paidFilter == null ? invoices : invoices.where((i) => i.isPaid == _paidFilter).toList();
    final unpaid = invoices.where((i) => !i.isPaid).toList();
    final outstandingTotal = unpaid.fold<double>(0, (sum, i) => sum + (double.tryParse(i.outstanding) ?? 0));
    double money(String v) => double.tryParse(v) ?? 0;
    return RefreshIndicator(
      onRefresh: () => ref.read(vendorInvoicesProvider(societyId).notifier).refresh(),
      child: ListView(padding: const EdgeInsets.fromLTRB(24, 8, 24, 32), children: [
        if (invoicesAsync.hasValue) ...[
          KpiGrid(cards: [
            KpiCard(
              icon: Icons.pending_actions_rounded,
              label: 'Unpaid Bills',
              value: '${unpaid.length}',
              color: AppTheme.warning,
            ),
            KpiCard(
              icon: Icons.account_balance_wallet_rounded,
              label: 'Outstanding',
              value: tableMoney(outstandingTotal),
              color: AppTheme.error,
            ),
          ]),
          const SizedBox(height: 16),
        ],
        AppDataTable<VendorInvoiceEntity>(
          toolbar: Wrap(spacing: 8, children: [
            _FilterChip(label: 'All', selected: _paidFilter == null, onTap: () => setState(() => _paidFilter = null)),
            _FilterChip(label: 'Unpaid', selected: _paidFilter == false, onTap: () => setState(() => _paidFilter = false)),
            _FilterChip(label: 'Paid', selected: _paidFilter == true, onTap: () => setState(() => _paidFilter = true)),
          ]),
          rows: rows,
          loading: invoicesAsync.isLoading && !invoicesAsync.hasValue,
          error: invoicesAsync.hasError ? friendlyErrorMessage(invoicesAsync.error!) : null,
          onRetry: () => ref.read(vendorInvoicesProvider(societyId).notifier).refresh(),
          onRowTap: (inv) => _openBill(societyId, inv),
          empty: const AppEmptyState(
            icon: Icons.storefront_rounded,
            title: 'No vendor bills yet',
            subtitle: 'Use "Add Bill" to log one.',
          ),
          columns: [
            AppDataColumn.text('Invoice', (i) => i.invoiceNumber, flex: 2, bold: true),
            AppDataColumn.text('Vendor', (i) => i.vendorName ?? '—', flex: 3),
            AppDataColumn.text('Date', (i) => tableDate(i.invoiceDate),
                flex: 2, sortKey: (i) => i.invoiceDate.millisecondsSinceEpoch),
            AppDataColumn.text('Due', (i) => tableDate(i.dueDate),
                flex: 2, sortKey: (i) => i.dueDate?.millisecondsSinceEpoch),
            AppDataColumn.text('Total', (i) => tableMoney(i.totalAmount),
                flex: 2, numeric: true, sortKey: (i) => money(i.totalAmount)),
            AppDataColumn.text('Outstanding', (i) => i.isPaid ? '—' : tableMoney(i.outstanding),
                flex: 2, numeric: true, bold: true, sortKey: (i) => money(i.outstanding)),
            AppDataColumn(
              label: 'Status',
              width: 120,
              sortKey: (i) => i.isPaid ? 1 : 0,
              cell: (i) => StatusPill(i.isPaid ? 'Paid' : 'Unpaid', i.isPaid ? AppTheme.success : AppTheme.warning),
            ),
          ],
        ),
      ]),
    );
  }

  @override
  Widget build(BuildContext context) {
    final societyId = ref.watch(currentUserProvider)?.societyId;
    if (societyId == null) {
      return const Scaffold(body: Center(child: Text('No society context')));
    }
    final invoicesAsync = ref.watch(vendorInvoicesProvider(societyId));
    final desktop = isDesktopLayout(context);

    return AppPage(
      title: 'Vendor Bills',
      actions: [
          IconButton(
            icon: const Icon(Icons.refresh_rounded),
            tooltip: 'Refresh',
            onPressed: () => ref.read(vendorInvoicesProvider(societyId).notifier).refresh(),
          ),
          if (!desktop)
            IconButton(
              icon: const Icon(Icons.payments_rounded),
              tooltip: 'Pay Vendor',
              onPressed: () => context.push(AppRoutes.payVendorBills),
            ),
          if (desktop)
            HeaderActionButton(icon: Icons.payments_rounded, label: 'Pay Vendor', onPressed: () => context.push(AppRoutes.payVendorBills)),
          if (desktop)
            HeaderActionButton(icon: Icons.add_rounded, label: 'Add Bill', onPressed: () => _addBill(societyId)),
        ],
      floatingActionButton: desktop
          ? null
          : FloatingActionButton.extended(
              onPressed: () => _addBill(societyId),
              icon: const Icon(Icons.add_rounded),
              label: const Text('Add Bill'),
            ),
      body: desktop ? _table(societyId, invoicesAsync) : Column(
        children: [
          invoicesAsync.when(
            loading: () => const SizedBox.shrink(),
            error: (_, __) => const SizedBox.shrink(),
            data: (invoices) {
              final unpaid = invoices.where((i) => !i.isPaid).toList();
              final outstandingTotal = unpaid.fold<double>(
                  0, (sum, i) => sum + (double.tryParse(i.outstanding) ?? 0));
              return Padding(
                padding: const EdgeInsets.fromLTRB(16, 12, 16, 0),
                child: KpiGrid(cards: [
                  KpiCard(
                    icon: Icons.pending_actions_rounded,
                    label: 'Unpaid Bills',
                    value: '${unpaid.length}',
                    color: AppTheme.warning,
                  ),
                  KpiCard(
                    icon: Icons.account_balance_wallet_rounded,
                    label: 'Outstanding',
                    value: tableMoney(outstandingTotal),
                    color: AppTheme.error,
                  ),
                ]),
              );
            },
          ),
          SizedBox(
            height: 48,
            child: ListView(
              scrollDirection: Axis.horizontal,
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
              children: [
                _FilterChip(label: 'All', selected: _paidFilter == null,
                    onTap: () => setState(() => _paidFilter = null)),
                Padding(
                  padding: const EdgeInsets.only(left: 8),
                  child: _FilterChip(label: 'Unpaid', selected: _paidFilter == false,
                      onTap: () => setState(() => _paidFilter = false)),
                ),
                Padding(
                  padding: const EdgeInsets.only(left: 8),
                  child: _FilterChip(label: 'Paid', selected: _paidFilter == true,
                      onTap: () => setState(() => _paidFilter = true)),
                ),
              ],
            ),
          ),
          Expanded(
            child: invoicesAsync.when(
              loading: () => const SkeletonList(),
              error: (e, _) => Center(
                  child: Text(friendlyErrorMessage(e), style: const TextStyle(color: AppTheme.error))),
              data: (invoices) {
                final filtered = _paidFilter == null
                    ? invoices
                    : invoices.where((i) => i.isPaid == _paidFilter).toList();
                if (filtered.isEmpty) {
                  return const AppEmptyState(
                    icon: Icons.storefront_rounded,
                    title: 'No vendor bills yet',
                    subtitle: 'Tap "Add Bill" to log one.',
                  );
                }
                return RefreshIndicator(
                  onRefresh: () => ref.read(vendorInvoicesProvider(societyId).notifier).refresh(),
                  child: ListView.builder(
                    padding: const EdgeInsets.fromLTRB(16, 8, 16, 88),
                    itemCount: filtered.length,
                    itemBuilder: (_, i) => _BillCard(
                      invoice: filtered[i],
                      onTap: () => showAppSheet(
                        context: context,
                        builder: (_) => _BillDetailSheet(invoice: filtered[i], societyId: societyId),
                      ),
                    ),
                  ),
                );
              },
            ),
          ),
        ],
      ),
    );
  }
}

class _FilterChip extends StatelessWidget {
  final String label;
  final bool selected;
  final VoidCallback onTap;
  const _FilterChip({required this.label, required this.selected, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return ChoiceChip(
      label: Text(label, style: const TextStyle(fontSize: 12)),
      selected: selected,
      onSelected: (_) => onTap(),
      selectedColor: AppTheme.primary.withOpacity(0.15),
      labelStyle: TextStyle(color: selected ? AppTheme.primary : AppTheme.textSecondary),
    );
  }
}

class _BillCard extends StatelessWidget {
  final VendorInvoiceEntity invoice;
  final VoidCallback onTap;
  const _BillCard({required this.invoice, required this.onTap});

  @override
  Widget build(BuildContext context) {
    final statusColor = invoice.isPaid ? AppTheme.success : AppTheme.warning;
    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      child: ListTile(
        onTap: onTap,
        contentPadding: const EdgeInsets.fromLTRB(16, 8, 16, 8),
        title: Text(invoice.vendorName ?? 'Vendor',
            maxLines: 1, overflow: TextOverflow.ellipsis,
            style: const TextStyle(fontWeight: FontWeight.w600)),
        subtitle: Padding(
          padding: const EdgeInsets.only(top: 2),
          child: Text('${invoice.invoiceNumber} · ${tableDate(invoice.invoiceDate)}',
              maxLines: 1, overflow: TextOverflow.ellipsis),
        ),
        trailing: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          crossAxisAlignment: CrossAxisAlignment.end,
          children: [
            Text(tableMoney(invoice.isPaid ? invoice.totalAmount : invoice.outstanding),
                style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 14)),
            const SizedBox(height: 4),
            StatusPill(invoice.isPaid ? 'Paid' : 'Unpaid', statusColor),
          ],
        ),
      ),
    );
  }
}

// ── Add Bill ─────────────────────────────────────────────────────────────────

class _AddBillSheet extends ConsumerStatefulWidget {
  final String societyId;
  const _AddBillSheet({required this.societyId});

  @override
  ConsumerState<_AddBillSheet> createState() => _AddBillSheetState();
}

class _AddBillSheetState extends ConsumerState<_AddBillSheet> {
  final _formKey = GlobalKey<FormState>();
  final _invoiceNumberCtrl = TextEditingController();
  final _amountCtrl = TextEditingController();
  final _gstCtrl = TextEditingController(text: '0');
  final _descCtrl = TextEditingController();
  String? _vendorId;
  String? _expenseAccountId;
  DateTime _invoiceDate = DateTime.now();
  DateTime? _dueDate;
  bool _saving = false;

  // Up to 10 digits and 2 decimals, matching what the server stores.
  static final _moneyFormatters = <TextInputFormatter>[
    FilteringTextInputFormatter.allow(RegExp(r'^\d{0,10}(\.\d{0,2})?')),
  ];

  /// Amount + GST, added in paise so it never carries float noise.
  double get _total {
    final amount = double.tryParse(_amountCtrl.text) ?? 0;
    final gst = double.tryParse(_gstCtrl.text) ?? 0;
    return ((amount * 100).round() + (gst * 100).round()) / 100;
  }

  Future<void> _save() async {
    if (!_formKey.currentState!.validate()) return;
    if (_vendorId == null) {
      AppToast.error(context, 'Pick a vendor');
      return;
    }
    if (_dueDate != null && _dueDate!.isBefore(DateTime(_invoiceDate.year, _invoiceDate.month, _invoiceDate.day))) {
      AppToast.error(context, 'The due date can\'t be before the invoice date');
      return;
    }
    setState(() => _saving = true);
    try {
      await ref.read(vendorInvoicesProvider(widget.societyId).notifier).createInvoice(
            vendorId: _vendorId!,
            invoiceNumber: _invoiceNumberCtrl.text.trim(),
            invoiceDate: _invoiceDate,
            dueDate: _dueDate,
            amount: double.parse(_amountCtrl.text),
            gstAmount: double.tryParse(_gstCtrl.text) ?? 0,
            totalAmount: _total,
            description: _descCtrl.text.trim().isEmpty ? null : _descCtrl.text.trim(),
            expenseAccountId: _expenseAccountId,
          );
      invalidateBooks(ref);
      if (mounted) {
        Navigator.pop(context);
        AppToast.success(context, 'Bill added');
      }
    } catch (e) {
      if (mounted) showErrorToast(context, e);
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return AppSheetFrame(
      title: 'Add Vendor Bill',
      child: Form(
        key: _formKey,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
              FormFieldBox(
                label: 'Vendor',
                required: true,
                child: VendorPicker(
                  societyId: widget.societyId,
                  value: _vendorId,
                  label: '',
                  required: true,
                  onChanged: (v) => setState(() => _vendorId = v?.id),
                ),
              ),
              const SizedBox(height: 12),
              FormFieldBox(label: "Supplier's invoice no.", child: TextFormField(
                controller: _invoiceNumberCtrl,
                inputFormatters: [LengthLimitingTextInputFormatter(50)],
                decoration: const InputDecoration(border: OutlineInputBorder()),
                validator: (v) => (v == null || v.trim().isEmpty) ? 'Required' : null,
              )),
              const SizedBox(height: 12),
              Row(children: [
                Expanded(
                  child: FormFieldBox(label: 'Invoice date', child: DateField(
                    label: '',value: _invoiceDate,
                    required: true,
                    onChanged: (d) => setState(() => _invoiceDate = d ?? _invoiceDate),
                  )),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: FormFieldBox(label: 'Due date (optional)', child: DateField(
                    label: '',value: _dueDate,
                    onChanged: (d) => setState(() => _dueDate = d),
                  )),
                ),
              ]),
              const SizedBox(height: 12),
              FormFieldBox(label: 'Amount', child: TextFormField(
                controller: _amountCtrl,
                keyboardType: const TextInputType.numberWithOptions(decimal: true),
                inputFormatters: _moneyFormatters,
                decoration: const InputDecoration(prefixText: '₹', border: OutlineInputBorder()),
                onChanged: (_) => setState(() {}),
                validator: (v) {
                  final n = double.tryParse(v ?? '');
                  return (n == null || n <= 0) ? 'Enter a valid amount' : null;
                },
              )),
              const SizedBox(height: 12),
              FormFieldBox(label: 'GST Amount', child: TextFormField(
                controller: _gstCtrl,
                keyboardType: const TextInputType.numberWithOptions(decimal: true),
                inputFormatters: _moneyFormatters,
                decoration: const InputDecoration(prefixText: '₹', border: OutlineInputBorder()),
                onChanged: (_) => setState(() {}),
                validator: (v) => (v == null || v.trim().isEmpty || double.tryParse(v) != null) ? null : 'Enter a valid amount',
              )),
              const SizedBox(height: 8),
              Text('Total: ₹${_total.toStringAsFixed(2)}',
                  style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 15)),
              const SizedBox(height: 12),
              // The expense head the bill is booked to in the accounts.
              ref.watch(ledgersProvider(widget.societyId)).maybeWhen(
                    data: (ledgers) => FormFieldBox(label: 'Expense head (optional)', child: DropdownButtonFormField<String?>(
                      initialValue: _expenseAccountId,
                      isExpanded: true,
                      decoration: const InputDecoration(
                        helperText: 'Leave as is to book it by the vendor\'s category',
                        border: OutlineInputBorder(),
                      ),
                      items: [
                        const DropdownMenuItem<String?>(value: null, child: Text('By vendor category')),
                        for (final l in ledgers.where((l) => l.nature == 'expense'))
                          DropdownMenuItem<String?>(value: l.id, child: Text(l.name, overflow: TextOverflow.ellipsis)),
                      ],
                      onChanged: (v) => setState(() => _expenseAccountId = v),
                    )),
                    orElse: () => const SizedBox.shrink(),
                  ),
              const SizedBox(height: 12),
              FormFieldBox(label: 'Description (optional)', child: TextFormField(
                controller: _descCtrl,
                maxLines: 2,
                inputFormatters: [LengthLimitingTextInputFormatter(2000)],
                decoration: const InputDecoration(border: OutlineInputBorder()),
              )),
              const SizedBox(height: 20),
              AppPrimaryButton(label: 'Save Bill', isLoading: _saving, onPressed: _saving ? null : _save),
          ],
        ),
      ),
    );
  }
}

// ── Bill Detail / Record Payment ────────────────────────────────────────────

class _BillDetailSheet extends ConsumerWidget {
  final VendorInvoiceEntity invoice;
  final String societyId;
  const _BillDetailSheet({required this.invoice, required this.societyId});

  bool get _hasPayments => (double.tryParse(invoice.paidAmount) ?? 0) > 0;

  Future<void> _refreshAfter(WidgetRef ref) async {
    ref.invalidate(billPaymentsProvider(invoice.id));
    ref.invalidate(vendorOpenBillsProvider(invoice.vendorId));
    await ref.read(vendorInvoicesProvider(societyId).notifier).refresh();
    invalidateBooks(ref);
  }

  /// Takes a wrongly entered bill out of the books and the payables: only the admin or committee (the server checks).
  /// A bill with payments is cancelled together with them: every payment is reversed, all or nothing.
  Future<void> _cancel(BuildContext context, WidgetRef ref) async {
    final reason = await askReason(
      context,
      title: _hasPayments ? 'Cancel this bill and reverse its payments?' : 'Cancel this bill?',
      message: _hasPayments
          ? 'Bill ${invoice.invoiceNumber} of ${invoice.vendorName ?? 'the vendor'} is taken out of the books, and '
              '₹${invoice.paidAmount} paid on it goes back to the bank or cash it was paid from. Check the bank '
              'statement first: if the vendor really was paid, this is not what you want.'
          : 'Bill ${invoice.invoiceNumber} of ${invoice.vendorName ?? 'the vendor'} is taken out of the books and '
              'what is owed. Enter it again, correctly, if the vendor is still to be paid.',
      action: _hasPayments ? 'Reverse and cancel' : 'Cancel bill',
    );
    if (reason == null || !context.mounted) return;
    try {
      await ref.read(vendorsWorkApiProvider).cancelInvoice(invoice.id, reason, reversePayments: _hasPayments);
      await _refreshAfter(ref);
      if (context.mounted) {
        AppToast.success(context, _hasPayments ? 'Bill cancelled and payments reversed' : 'Bill cancelled');
        Navigator.pop(context);
      }
    } catch (e) {
      if (context.mounted) showErrorToast(context, e);
    }
  }

  /// Reverses one payment (the bill is owed again and the payment's entry in the books is reversed).
  Future<void> _reversePayment(BuildContext context, WidgetRef ref, BillPayment p) async {
    final reason = await askReason(
      context,
      title: 'Reverse payment ${p.paymentNumber}?',
      message: '₹${p.amount} paid on ${p.paymentDate.day}/${p.paymentDate.month}/${p.paymentDate.year} goes back to '
          'the bank or cash it was paid from, and the bill is owed again by that amount.',
      action: 'Reverse payment',
    );
    if (reason == null || !context.mounted) return;
    try {
      await ref.read(vendorsWorkApiProvider).reversePayment(p.id, reason);
      await _refreshAfter(ref);
      if (context.mounted) {
        AppToast.success(context, 'Payment reversed');
        Navigator.pop(context);
      }
    } catch (e) {
      if (context.mounted) showErrorToast(context, e);
    }
  }

  Widget _payments(BuildContext context, WidgetRef ref) {
    final payments = ref.watch(billPaymentsProvider(invoice.id));
    return payments.when(
      loading: () => const Padding(padding: EdgeInsets.symmetric(vertical: 8), child: LinearProgressIndicator()),
      error: (_, __) => const SizedBox.shrink(),
      data: (list) {
        if (list.isEmpty) return const SizedBox.shrink();
        return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          const SizedBox(height: 8),
          const Text('Payments', style: TextStyle(fontWeight: FontWeight.w700)),
          const SizedBox(height: 6),
          for (final p in list)
            Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Expanded(
                  child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    Text(
                      '${p.paymentNumber} · ₹${p.amount}',
                      style: TextStyle(
                        fontWeight: FontWeight.w500,
                        decoration: p.isReversed ? TextDecoration.lineThrough : null,
                      ),
                    ),
                    Text(
                      '${p.paymentDate.day}/${p.paymentDate.month}/${p.paymentDate.year} · '
                      '${vendorPaymentModeLabel(p.paymentMode)}'
                      '${p.transactionRef != null && p.transactionRef!.isNotEmpty ? ' · ${p.transactionRef}' : ''}',
                      style: const TextStyle(color: AppTheme.textSecondary, fontSize: 12),
                    ),
                    if (p.isReversed)
                      Text('Reversed${p.reversalReason != null ? ': ${p.reversalReason}' : ''}',
                          style: const TextStyle(color: AppTheme.error, fontSize: 12)),
                  ]),
                ),
                if (!p.isReversed)
                  TextButton(
                    onPressed: () => _reversePayment(context, ref, p),
                    style: TextButton.styleFrom(foregroundColor: AppTheme.error),
                    child: const Text('Reverse'),
                  ),
              ]),
            ),
        ]);
      },
    );
  }

  Widget _row(String label, String value) => Padding(
        padding: const EdgeInsets.only(bottom: 8),
        child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
          SizedBox(width: 110, child: Text(label, style: const TextStyle(color: AppTheme.textSecondary))),
          Expanded(child: Text(value, style: const TextStyle(fontWeight: FontWeight.w500))),
        ]),
      );

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final canCancel = ref.watch(currentUserProvider)?.isAdminOrCommittee == true;
    return AppSheetFrame(
      title: invoice.vendorName ?? 'Vendor',
      subtitle: 'Bill details',
      footer: invoice.isPaid && !canCancel
          ? null
          : Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.stretch, children: [
              if (!invoice.isPaid) ...[
                ElevatedButton.icon(
                  onPressed: () {
                    Navigator.pop(context);
                    showAppSheet(
                      context: context,
                      builder: (_) => _RecordPaymentSheet(invoice: invoice, societyId: societyId),
                    );
                  },
                  icon: const Icon(Icons.payments_rounded),
                  label: const Text('Record Payment'),
                ),
                const SizedBox(height: 8),
                OutlinedButton.icon(
                  onPressed: () {
                    final router = GoRouter.of(context);          // the sheet's own context is gone once it closes
                    Navigator.pop(context);
                    router.push('${AppRoutes.payVendorBills}?vendor=${invoice.vendorId}');
                  },
                  icon: const Icon(Icons.checklist_rounded),
                  label: const Text('Pay several bills of this vendor'),
                ),
              ],
              if (canCancel)
                TextButton.icon(
                  onPressed: () => _cancel(context, ref),
                  style: TextButton.styleFrom(foregroundColor: AppTheme.error),
                  icon: const Icon(Icons.cancel_outlined),
                  label: Text(_hasPayments ? 'Cancel bill and reverse payments' : 'Cancel this bill'),
                ),
            ]),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _row('Invoice No', invoice.invoiceNumber),
          _row('Invoice Date', '${invoice.invoiceDate.day}/${invoice.invoiceDate.month}/${invoice.invoiceDate.year}'),
          if (invoice.dueDate != null)
            _row('Due Date', '${invoice.dueDate!.day}/${invoice.dueDate!.month}/${invoice.dueDate!.year}'),
          _row('Total', '₹${invoice.totalAmount}'),
          _row('Paid', '₹${invoice.paidAmount}'),
          _row('Outstanding', '₹${invoice.outstanding}'),
          if (invoice.paymentMode != null) _row('Last Mode', vendorPaymentModeLabel(invoice.paymentMode!)),
          if (invoice.paymentRef != null) _row('Reference', invoice.paymentRef!),
          if (invoice.description != null) _row('Notes', invoice.description!),
          if (_hasPayments) _payments(context, ref),
        ],
      ),
    );
  }
}

class _RecordPaymentSheet extends ConsumerStatefulWidget {
  final VendorInvoiceEntity invoice;
  final String societyId;
  const _RecordPaymentSheet({required this.invoice, required this.societyId});

  @override
  ConsumerState<_RecordPaymentSheet> createState() => _RecordPaymentSheetState();
}

class _RecordPaymentSheetState extends ConsumerState<_RecordPaymentSheet> {
  final _formKey = GlobalKey<FormState>();
  late final TextEditingController _amountCtrl;
  final _refCtrl = TextEditingController();
  final _bankCtrl = TextEditingController();
  String _mode = kVendorPaymentModes.first.$1;
  LedgerAccount? _paidFrom;
  DateTime _paidDate = DateTime.now();
  bool _saving = false;
  PaymentTdsPreview? _preview;
  bool _previewing = false;
  Timer? _debounce;

  @override
  void initState() {
    super.initState();
    _amountCtrl = TextEditingController(text: widget.invoice.outstanding);
    WidgetsBinding.instance.addPostFrameCallback((_) => _refreshPreview());
  }

  @override
  void dispose() {
    _debounce?.cancel();
    super.dispose();
  }

  /// The TDS this payment would carry, checked as the amount or date changes. Nothing is saved.
  void _refreshPreview() {
    _debounce?.cancel();
    final amount = double.tryParse(_amountCtrl.text);
    if (amount == null || amount <= 0) {
      setState(() => _preview = null);
      return;
    }
    _debounce = Timer(const Duration(milliseconds: 350), () async {
      if (!mounted) return;
      setState(() => _previewing = true);
      try {
        final p = await ref.read(vendorsWorkApiProvider).paymentPreview(widget.invoice.id, amount, _paidDate);
        if (mounted) setState(() => _preview = p);
      } catch (_) {
        if (mounted) setState(() => _preview = null);     // the payment itself still works; only the preview is missing
      } finally {
        if (mounted) setState(() => _previewing = false);
      }
    });
  }

  Future<void> _pickDate() async {
    final picked = await showDatePicker(
      context: context, initialDate: _paidDate,
      firstDate: widget.invoice.invoiceDate, lastDate: DateTime.now(),
    );
    if (picked != null) {
      setState(() => _paidDate = picked);
      _refreshPreview();
    }
  }

  Future<void> _save() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() => _saving = true);
    try {
      await ref.read(vendorInvoicesProvider(widget.societyId).notifier).recordPayment(
            invoiceId: widget.invoice.id,
            amount: double.parse(_amountCtrl.text),
            paidDate: _paidDate,
            paymentMode: _mode,
            paymentRef: _refCtrl.text.trim().isEmpty ? null : _refCtrl.text.trim(),
            bankName: _bankCtrl.text.trim().isEmpty ? null : _bankCtrl.text.trim(),
            bankAccountId: _paidFrom?.id,
          );
      invalidateBooks(ref);
      ref.invalidate(vendorOpenBillsProvider(widget.invoice.vendorId));
      if (mounted) {
        Navigator.pop(context);
        final tds = _preview?.applies == true ? ' · TDS ${formatInr(double.tryParse(_preview!.tdsAmount) ?? 0)} deducted' : '';
        AppToast.success(context, 'Payment recorded$tds');
      }
    } catch (e) {
      if (mounted) showErrorToast(context, e);
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  /// The cash or bank ledger the money leaves: cash from a cash ledger, any other way from a bank ledger.
  Widget _paidFromField() {
    final all = ref.watch(ledgersProvider(widget.societyId)).valueOrNull ?? const <LedgerAccount>[];
    final options = all.where((l) => l.isActive && (_mode == 'cash' ? l.isCash : l.isBank)).toList();
    _paidFrom ??= options.where((l) => l.isDefaultBank).firstOrNull ?? options.firstOrNull;
    return LedgerChooser(
      label: 'Paid from',
      value: _paidFrom,
      options: options,
      sheetTitle: _mode == 'cash' ? 'Cash account' : 'Bank account',
      onChanged: (l) => setState(() => _paidFrom = l),
    );
  }

  @override
  Widget build(BuildContext context) {
    return AppSheetFrame(
      title: 'Pay ${widget.invoice.vendorName ?? 'Vendor'}',
      subtitle: 'Outstanding: ₹${widget.invoice.outstanding}',
      child: Form(
        key: _formKey,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            FormFieldBox(label: 'Amount', required: true, child: TextFormField(
              controller: _amountCtrl,
              keyboardType: const TextInputType.numberWithOptions(decimal: true),
              inputFormatters: [FilteringTextInputFormatter.allow(RegExp(r'^\d{0,10}(\.\d{0,2})?'))],
              decoration: const InputDecoration(prefixText: '₹'),
              onChanged: (_) => _refreshPreview(),
              validator: (v) {
                final n = double.tryParse(v ?? '');
                if (n == null || n <= 0) return 'Enter a valid amount';
                final outstanding = double.tryParse(widget.invoice.outstanding) ?? 0;
                if (n > outstanding) return 'Cannot exceed outstanding (₹$outstanding)';
                return null;
              },
            )),
            PaymentTdsCard(preview: _preview, loading: _previewing),
            const SizedBox(height: 14),
            FormFieldBox(label: 'Paid On', child: FormDateField(
              value: _paidDate,
              hint: 'Pick a date',
              format: (d) => '${d.day}/${d.month}/${d.year}',
              onTap: _pickDate,
            )),
            const SizedBox(height: 14),
            FormFieldBox(label: 'Payment Mode', child: DropdownButtonFormField<String>(
              initialValue: _mode,
              isExpanded: true,
              decoration: const InputDecoration(),
              items: kVendorPaymentModes
                  .map((m) => DropdownMenuItem(value: m.$1, child: Text(m.$2)))
                  .toList(),
              onChanged: (v) => setState(() {
                _mode = v!;
                _paidFrom = null;                       // a cash payment is from a cash ledger, any other from a bank
              }),
            )),
            const SizedBox(height: 14),
            _paidFromField(),
            const SizedBox(height: 14),
            FormFieldBox(label: 'Reference (optional)', child: TextFormField(
              controller: _refCtrl,
              inputFormatters: [LengthLimitingTextInputFormatter(100)],
            )),
            const SizedBox(height: 14),
            FormFieldBox(label: 'Bank Name (optional)', child: TextFormField(
              controller: _bankCtrl,
              inputFormatters: [LengthLimitingTextInputFormatter(100)],
            )),
            const SizedBox(height: 20),
            AppPrimaryButton(label: 'Record Payment', isLoading: _saving, onPressed: _saving ? null : _save),
          ],
        ),
      ),
    );
  }
}
