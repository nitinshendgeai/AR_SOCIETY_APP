import 'package:ar_society_app/features/accounts/presentation/providers/accounts_providers.dart';
import 'package:ar_society_app/core/motion/loading.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/features/vendor/domain/entities/vendor_entities.dart';
import 'package:ar_society_app/features/vendor/presentation/providers/vendor_providers.dart';
import 'package:ar_society_app/features/vendor/presentation/widgets/procurement_widgets.dart' show DateField;
import 'package:ar_society_app/features/vendor/presentation/widgets/vendor_picker.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';
import 'package:ar_society_app/core/layout/app_sheet.dart';
import 'package:ar_society_app/shared/widgets/app_data_table.dart';
import 'package:ar_society_app/core/layout/app_shell.dart' show isDesktopLayout;

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

    return Scaffold(
      backgroundColor: AppTheme.surface,
      appBar: AppBar(
        title: const Text('Vendor Bills'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh_rounded),
            tooltip: 'Refresh',
            onPressed: () => ref.read(vendorInvoicesProvider(societyId).notifier).refresh(),
          ),
          if (desktop)
            HeaderActionButton(icon: Icons.add_rounded, label: 'Add Bill', onPressed: () => _addBill(societyId)),
        ],
      ),
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
    // Fills the side panel on desktop; a draggable part-height sheet on phones.
    final panel = isDesktopLayout(context);
    return DraggableScrollableSheet(
      initialChildSize: panel ? 1 : 0.85,
      minChildSize: 0.5,
      maxChildSize: panel ? 1 : 0.95,
      expand: false,
      builder: (context, scrollController) => Container(
        decoration: const BoxDecoration(
          color: AppTheme.cardBg,
          borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
        ),
        padding: EdgeInsets.only(
          left: 20, right: 20, top: 20,
          bottom: MediaQuery.of(context).viewInsets.bottom + 20,
        ),
        child: Form(
          key: _formKey,
          // A plain scroll view, not a lazy ListView: fields scrolled out of
          // view stay mounted, so validate() checks every one of them.
          child: SingleChildScrollView(
            controller: scrollController,
            child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              const Text('Add Vendor Bill', style: TextStyle(fontSize: 18, fontWeight: FontWeight.w700)),
              const SizedBox(height: 16),
              VendorPicker(
                societyId: widget.societyId,
                value: _vendorId,
                label: 'Vendor *',
                required: true,
                onChanged: (v) => setState(() => _vendorId = v?.id),
              ),
              const SizedBox(height: 12),
              TextFormField(
                controller: _invoiceNumberCtrl,
                inputFormatters: [LengthLimitingTextInputFormatter(50)],
                decoration: const InputDecoration(labelText: "Supplier's invoice no.", border: OutlineInputBorder()),
                validator: (v) => (v == null || v.trim().isEmpty) ? 'Required' : null,
              ),
              const SizedBox(height: 12),
              Row(children: [
                Expanded(
                  child: DateField(
                    label: 'Invoice date',
                    value: _invoiceDate,
                    required: true,
                    onChanged: (d) => setState(() => _invoiceDate = d ?? _invoiceDate),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: DateField(
                    label: 'Due date (optional)',
                    value: _dueDate,
                    onChanged: (d) => setState(() => _dueDate = d),
                  ),
                ),
              ]),
              const SizedBox(height: 12),
              TextFormField(
                controller: _amountCtrl,
                keyboardType: const TextInputType.numberWithOptions(decimal: true),
                inputFormatters: _moneyFormatters,
                decoration: const InputDecoration(labelText: 'Amount', prefixText: '₹', border: OutlineInputBorder()),
                onChanged: (_) => setState(() {}),
                validator: (v) {
                  final n = double.tryParse(v ?? '');
                  return (n == null || n <= 0) ? 'Enter a valid amount' : null;
                },
              ),
              const SizedBox(height: 12),
              TextFormField(
                controller: _gstCtrl,
                keyboardType: const TextInputType.numberWithOptions(decimal: true),
                inputFormatters: _moneyFormatters,
                decoration: const InputDecoration(labelText: 'GST Amount', prefixText: '₹', border: OutlineInputBorder()),
                onChanged: (_) => setState(() {}),
                validator: (v) => (v == null || v.trim().isEmpty || double.tryParse(v) != null) ? null : 'Enter a valid amount',
              ),
              const SizedBox(height: 8),
              Text('Total: ₹${_total.toStringAsFixed(2)}',
                  style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 15)),
              const SizedBox(height: 12),
              // The expense head the bill is booked to in the accounts.
              ref.watch(ledgersProvider(widget.societyId)).maybeWhen(
                    data: (ledgers) => DropdownButtonFormField<String?>(
                      initialValue: _expenseAccountId,
                      isExpanded: true,
                      decoration: const InputDecoration(
                        labelText: 'Expense head (optional)',
                        helperText: 'Leave as is to book it by the vendor\'s category',
                        border: OutlineInputBorder(),
                      ),
                      items: [
                        const DropdownMenuItem<String?>(value: null, child: Text('By vendor category')),
                        for (final l in ledgers.where((l) => l.nature == 'expense'))
                          DropdownMenuItem<String?>(value: l.id, child: Text(l.name, overflow: TextOverflow.ellipsis)),
                      ],
                      onChanged: (v) => setState(() => _expenseAccountId = v),
                    ),
                    orElse: () => const SizedBox.shrink(),
                  ),
              const SizedBox(height: 12),
              TextFormField(
                controller: _descCtrl,
                maxLines: 2,
                inputFormatters: [LengthLimitingTextInputFormatter(2000)],
                decoration: const InputDecoration(labelText: 'Description (optional)', border: OutlineInputBorder()),
              ),
              const SizedBox(height: 20),
              SizedBox(
                width: double.infinity,
                child: ElevatedButton(
                  onPressed: _saving ? null : _save,
                  child: _saving
                      ? const SizedBox(width: 18, height: 18,
                          child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                      : const Text('Save Bill'),
                ),
              ),
            ],
            ),
          ),
        ),
      ),
    );
  }
}

// ── Bill Detail / Record Payment ────────────────────────────────────────────

class _BillDetailSheet extends StatelessWidget {
  final VendorInvoiceEntity invoice;
  final String societyId;
  const _BillDetailSheet({required this.invoice, required this.societyId});

  Widget _row(String label, String value) => Padding(
        padding: const EdgeInsets.only(bottom: 8),
        child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
          SizedBox(width: 110, child: Text(label, style: const TextStyle(color: AppTheme.textSecondary))),
          Expanded(child: Text(value, style: const TextStyle(fontWeight: FontWeight.w500))),
        ]),
      );

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: const BoxDecoration(
        color: AppTheme.cardBg,
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      padding: const EdgeInsets.all(20),
      child: SafeArea(
        top: false,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(invoice.vendorName ?? 'Vendor', style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w700)),
            const SizedBox(height: 12),
            _row('Invoice No', invoice.invoiceNumber),
            _row('Invoice Date',
                '${invoice.invoiceDate.day}/${invoice.invoiceDate.month}/${invoice.invoiceDate.year}'),
            if (invoice.dueDate != null)
              _row('Due Date', '${invoice.dueDate!.day}/${invoice.dueDate!.month}/${invoice.dueDate!.year}'),
            _row('Total', '₹${invoice.totalAmount}'),
            _row('Paid', '₹${invoice.paidAmount}'),
            _row('Outstanding', '₹${invoice.outstanding}'),
            if (invoice.paymentMode != null) _row('Last Mode', vendorPaymentModeLabel(invoice.paymentMode!)),
            if (invoice.paymentRef != null) _row('Reference', invoice.paymentRef!),
            if (invoice.description != null) _row('Notes', invoice.description!),
            const SizedBox(height: 12),
            if (!invoice.isPaid)
              SizedBox(
                width: double.infinity,
                child: ElevatedButton.icon(
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
              ),
          ],
        ),
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
  DateTime _paidDate = DateTime.now();
  bool _saving = false;

  @override
  void initState() {
    super.initState();
    _amountCtrl = TextEditingController(text: widget.invoice.outstanding);
  }

  Future<void> _pickDate() async {
    final picked = await showDatePicker(
      context: context, initialDate: _paidDate,
      firstDate: widget.invoice.invoiceDate, lastDate: DateTime.now(),
    );
    if (picked != null) setState(() => _paidDate = picked);
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
          );
      invalidateBooks(ref);
      if (mounted) {
        Navigator.pop(context);
        AppToast.success(context, 'Payment recorded');
      }
    } catch (e) {
      if (mounted) showErrorToast(context, e);
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: const BoxDecoration(
        color: AppTheme.cardBg,
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      padding: EdgeInsets.only(
        left: 20, right: 20, top: 20,
        bottom: MediaQuery.of(context).viewInsets.bottom + 20,
      ),
      child: Form(
        key: _formKey,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Pay ${widget.invoice.vendorName ?? 'Vendor'}',
                style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w700)),
            Text('Outstanding: ₹${widget.invoice.outstanding}',
                style: const TextStyle(color: AppTheme.textSecondary)),
            const SizedBox(height: 16),
            TextFormField(
              controller: _amountCtrl,
              keyboardType: const TextInputType.numberWithOptions(decimal: true),
              inputFormatters: [FilteringTextInputFormatter.allow(RegExp(r'^\d{0,10}(\.\d{0,2})?'))],
              decoration: const InputDecoration(labelText: 'Amount', prefixText: '₹', border: OutlineInputBorder()),
              validator: (v) {
                final n = double.tryParse(v ?? '');
                if (n == null || n <= 0) return 'Enter a valid amount';
                final outstanding = double.tryParse(widget.invoice.outstanding) ?? 0;
                if (n > outstanding) return 'Cannot exceed outstanding (₹$outstanding)';
                return null;
              },
            ),
            const SizedBox(height: 12),
            OutlinedButton(
              onPressed: _pickDate,
              child: Text('Paid On: ${_paidDate.day}/${_paidDate.month}/${_paidDate.year}'),
            ),
            const SizedBox(height: 12),
            DropdownButtonFormField<String>(
              initialValue: _mode,
              decoration: const InputDecoration(labelText: 'Payment Mode', border: OutlineInputBorder()),
              items: kVendorPaymentModes
                  .map((m) => DropdownMenuItem(value: m.$1, child: Text(m.$2)))
                  .toList(),
              onChanged: (v) => setState(() => _mode = v!),
            ),
            const SizedBox(height: 12),
            TextFormField(
              controller: _refCtrl,
              inputFormatters: [LengthLimitingTextInputFormatter(100)],
              decoration: const InputDecoration(labelText: 'Reference (optional)', border: OutlineInputBorder()),
            ),
            const SizedBox(height: 12),
            TextFormField(
              controller: _bankCtrl,
              inputFormatters: [LengthLimitingTextInputFormatter(100)],
              decoration: const InputDecoration(labelText: 'Bank Name (optional)', border: OutlineInputBorder()),
            ),
            const SizedBox(height: 20),
            SizedBox(
              width: double.infinity,
              child: ElevatedButton(
                onPressed: _saving ? null : _save,
                child: _saving
                    ? const SizedBox(width: 18, height: 18,
                        child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                    : const Text('Record Payment'),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
