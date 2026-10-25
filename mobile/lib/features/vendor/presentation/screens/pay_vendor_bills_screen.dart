import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/motion/loading.dart';
import 'package:ar_society_app/core/router/app_router.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/accounts/data/accounts_api.dart'
    show LedgerAccount, formatAccountsDate, formatInr;
import 'package:ar_society_app/features/accounts/presentation/providers/accounts_providers.dart';
import 'package:ar_society_app/features/accounts/presentation/widgets/accounts_widgets.dart' show LedgerChooser;
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/features/vendor/data/vendors_work_api.dart' show OpenBill, OpenBills;
import 'package:ar_society_app/features/vendor/domain/entities/vendor_entities.dart' show kVendorPaymentModes;
import 'package:ar_society_app/features/vendor/presentation/providers/vendor_providers.dart';
import 'package:ar_society_app/features/vendor/presentation/providers/vendors_work_providers.dart';
import 'package:ar_society_app/features/vendor/presentation/widgets/vendor_picker.dart';
import 'package:ar_society_app/shared/widgets/app_form.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';

/// Pay a vendor the way the books owe it: choose the vendor, and the bills still to be paid to them are listed, oldest
/// due first. Tick the ones this cheque or transfer settles (a part payment is an amount lower than the balance), say
/// which bank or cash ledger it is paid from, and save. Each bill is paid — with its own TDS — and posted to the books,
/// or none is, so the vendor's ledger, the payables and every bill always agree.
class PayVendorBillsScreen extends ConsumerStatefulWidget {
  /// The vendor to start with (opened from a bill, or from a voucher naming a vendor who has bills to pay).
  final String? initialVendorId;
  const PayVendorBillsScreen({super.key, this.initialVendorId});

  @override
  ConsumerState<PayVendorBillsScreen> createState() => _PayVendorBillsScreenState();
}

class _PayVendorBillsScreenState extends ConsumerState<PayVendorBillsScreen> {
  final _formKey = GlobalKey<FormState>();
  final _ref = TextEditingController();
  final _bank = TextEditingController();
  final _amounts = <String, TextEditingController>{};
  final _picked = <String>{};

  String? _vendorId;
  String _mode = kVendorPaymentModes.where((m) => m.$1 != 'cash').first.$1;
  DateTime _paidOn = DateTime.now();
  LedgerAccount? _paidFrom;
  bool _saving = false;

  // Up to 10 digits and 2 decimals, matching what the server stores.
  static final _moneyFormatters = <TextInputFormatter>[
    FilteringTextInputFormatter.allow(RegExp(r'^\d{0,10}(\.\d{0,2})?')),
  ];

  @override
  void initState() {
    super.initState();
    _vendorId = widget.initialVendorId;
  }

  @override
  void dispose() {
    _ref.dispose();
    _bank.dispose();
    for (final c in _amounts.values) {
      c.dispose();
    }
    super.dispose();
  }

  TextEditingController _amountFor(OpenBill b) =>
      _amounts.putIfAbsent(b.invoiceId, () => TextEditingController(text: b.outstanding));

  void _chooseVendor(String? id) {
    setState(() {
      _vendorId = id;
      _picked.clear();
      for (final c in _amounts.values) {
        c.dispose();
      }
      _amounts.clear();
    });
  }

  double _amountOf(OpenBill b) => double.tryParse(_amounts[b.invoiceId]?.text ?? '') ?? 0;

  /// The sum of what is settled, added in paise so it never carries float noise.
  double _total(List<OpenBill> bills) =>
      bills.where((b) => _picked.contains(b.invoiceId)).fold<int>(0, (s, b) => s + (_amountOf(b) * 100).round()) / 100;

  /// Cash is paid from a cash ledger; every other way from a bank ledger.
  List<LedgerAccount> _ledgersFor(List<LedgerAccount> all) =>
      all.where((l) => l.isActive && (_mode == 'cash' ? l.isCash : l.isBank)).toList();

  LedgerAccount? _defaultLedger(List<LedgerAccount> options) =>
      options.where((l) => l.isDefaultBank).firstOrNull ?? options.firstOrNull;

  void _chooseMode(String mode, List<LedgerAccount> all) {
    setState(() {
      _mode = mode;
      final options = _ledgersFor(all);
      if (_paidFrom == null || !options.any((l) => l.id == _paidFrom!.id)) _paidFrom = _defaultLedger(options);
    });
  }

  void _toggleAll(List<OpenBill> bills, bool on) => setState(() {
        _picked.clear();
        if (on) _picked.addAll(bills.map((b) => b.invoiceId));
        if (on) {
          for (final b in bills) {
            _amountFor(b).text = b.outstanding;
          }
        }
      });

  Future<void> _pickDate(List<OpenBill> bills) async {
    final chosen = bills.where((b) => _picked.contains(b.invoiceId));
    // A payment can't be dated before the bill it settles.
    final earliest = chosen.isEmpty
        ? DateTime(DateTime.now().year - 2)
        : chosen.map((b) => b.invoiceDate).reduce((a, b) => a.isAfter(b) ? a : b);
    final d = await showDatePicker(
      context: context,
      initialDate: _paidOn.isBefore(earliest) ? earliest : _paidOn,
      firstDate: earliest,
      lastDate: DateTime.now(),
    );
    if (d != null) setState(() => _paidOn = d);
  }

  Future<void> _save(String societyId, OpenBills open) async {
    if (!_formKey.currentState!.validate()) return;
    final chosen = open.bills.where((b) => _picked.contains(b.invoiceId)).toList();
    if (chosen.isEmpty) {
      AppToast.warning(context, 'Tick at least one bill to pay');
      return;
    }
    if (_paidFrom == null) {
      AppToast.warning(context,
          _mode == 'cash' ? 'Choose the cash ledger it is paid from' : 'Choose the bank account it is paid from');
      return;
    }
    final latestBill = chosen.map((b) => b.invoiceDate).reduce((a, b) => a.isAfter(b) ? a : b);
    if (_paidOn.isBefore(DateTime(latestBill.year, latestBill.month, latestBill.day))) {
      AppToast.warning(context, 'The payment can\'t be dated before the bill it settles');
      return;
    }
    setState(() => _saving = true);
    try {
      final r = await ref.read(vendorsWorkApiProvider).payBills(
            vendorId: open.vendorId,
            items: [for (final b in chosen) (invoiceId: b.invoiceId, amount: _amountOf(b))],
            paidDate: _paidOn,
            paymentMode: _mode,
            paymentRef: _ref.text.trim(),
            bankName: _bank.text.trim(),
            bankAccountId: _paidFrom!.id,
          );
      ref.invalidate(vendorOpenBillsProvider(open.vendorId));
      ref.invalidate(vendorInvoicesProvider(societyId));
      invalidateBooks(ref);
      if (!mounted) return;
      final tds = (double.tryParse(r.tdsHeld) ?? 0) > 0 ? ' · TDS ${formatInr(double.parse(r.tdsHeld))} held' : '';
      AppToast.success(context,
          '${r.billsPaid} ${r.billsPaid == 1 ? 'bill' : 'bills'} paid · ${formatInr(double.tryParse(r.settled) ?? 0)}$tds');
      setState(() {
        _picked.clear();
        for (final c in _amounts.values) {
          c.dispose();
        }
        _amounts.clear();
        _ref.clear();
      });
    } catch (e) {
      if (mounted) showErrorToast(context, e);
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final societyId = ref.watch(currentUserProvider)?.societyId;
    if (societyId == null) return const Scaffold(body: Center(child: Text('No society context')));
    final ledgersAsync = ref.watch(ledgersProvider(societyId));
    final all = ledgersAsync.valueOrNull ?? const <LedgerAccount>[];
    // Until the ledgers are known the "paid from" choice is empty; fill it once they arrive.
    if (_paidFrom == null && all.isNotEmpty) _paidFrom = _defaultLedger(_ledgersFor(all));

    final open = _vendorId == null ? null : ref.watch(vendorOpenBillsProvider(_vendorId!));
    final bills = open?.valueOrNull?.bills ?? const <OpenBill>[];
    final canSave = open?.valueOrNull != null && bills.isNotEmpty && !_saving;

    return AppFormPage(
      title: 'Pay Vendor',
      subtitle: 'Choose the bills this payment settles. Each bill is marked paid and posted to the books.',
      formKey: _formKey,
      submitLabel: 'Pay bills',
      submitIcon: Icons.payments_rounded,
      saving: _saving,
      onSubmit: canSave ? () => _save(societyId, open!.requireValue) : null,
      children: [
        FormSection(
          title: 'Who is paid',
          description: 'The vendor\'s unpaid bills are listed below, oldest due first.',
          columns: 1,
          children: [
            FormFieldBox(
              label: 'Vendor',
              required: true,
              child: VendorPicker(
                  societyId: societyId,
                  value: _vendorId,
                  label: '',
                  required: true,
                  onChanged: (v) => _chooseVendor(v?.id)),
            ),
          ],
        ),
        if (open != null)
          open.when(
            loading: () => const Padding(padding: EdgeInsets.symmetric(vertical: 24), child: AppLoader()),
            error: (e, _) => AppErrorBanner(message: friendlyErrorMessage(e)),
            data: (o) => _billsSection(o),
          ),
        if (open?.valueOrNull != null && bills.isNotEmpty) _paymentSection(all, bills),
      ],
    );
  }

  Widget _billsSection(OpenBills o) {
    if (o.bills.isEmpty) {
      return const AppEmptyState(
        icon: Icons.check_circle_outline_rounded,
        title: 'Nothing to pay',
        subtitle: 'This vendor has no unpaid bills. Add a bill first from Vendor Bills.',
      );
    }
    final allPicked = _picked.length == o.bills.length;
    return FormSection(
      title: 'Bills to pay',
      description:
          '${o.vendorName} is owed ${formatInr(o.total)} across ${o.bills.length} ${o.bills.length == 1 ? 'bill' : 'bills'}. '
          'Lower an amount to part-pay a bill.',
      columns: 1,
      trailing: TextButton(
        onPressed: () => _toggleAll(o.bills, !allPicked),
        child: Text(allPicked ? 'Clear all' : 'Select all'),
      ),
      children: [
        for (final b in o.bills)
          _BillRow(
            bill: b,
            picked: _picked.contains(b.invoiceId),
            controller: _amountFor(b),
            formatters: _moneyFormatters,
            onPicked: (v) => setState(() => v ? _picked.add(b.invoiceId) : _picked.remove(b.invoiceId)),
            onAmountChanged: () => setState(() {}),
          ),
        Align(
          alignment: Alignment.centerRight,
          child: Text('Paying ${formatInr(_total(o.bills))}',
              key: const ValueKey('paying-total'), style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 15)),
        ),
      ],
    );
  }

  Widget _paymentSection(List<LedgerAccount> all, List<OpenBill> bills) {
    final options = _ledgersFor(all);
    return FormSection(
      title: 'Payment',
      description:
          'How it is paid and from which account. TDS, where it applies, is held on each bill and shown after saving.',
      children: [
        FormFieldBox(
          label: 'Paid on',
          child: FormDateField(
              value: _paidOn, hint: 'Pick a date', format: formatAccountsDate, onTap: () => _pickDate(bills)),
        ),
        FormFieldBox(
          label: 'Payment mode',
          child: DropdownButtonFormField<String>(
            initialValue: _mode,
            isExpanded: true,
            items: [for (final m in kVendorPaymentModes) DropdownMenuItem(value: m.$1, child: Text(m.$2))],
            onChanged: (v) => _chooseMode(v!, all),
          ),
        ),
        LedgerChooser(
          label: 'Paid from',
          value: _paidFrom,
          options: options,
          sheetTitle: _mode == 'cash' ? 'Cash account' : 'Bank account',
          helper: options.isEmpty
              ? (_mode == 'cash'
                  ? 'No cash ledger yet — add one in the Chart of Accounts'
                  : 'No bank ledger yet — add one in the Chart of Accounts')
              : null,
          onChanged: (l) => setState(() => _paidFrom = l),
        ),
        FormFieldBox(
          label: 'Cheque / UTR no.',
          child: TextFormField(controller: _ref, inputFormatters: [LengthLimitingTextInputFormatter(100)]),
        ),
        FormFieldBox(
          label: 'Bank name (optional)',
          child: TextFormField(controller: _bank, inputFormatters: [LengthLimitingTextInputFormatter(100)]),
        ),
      ],
    );
  }
}

/// One unpaid bill: a tick to include it, what is owed and how late, and — once ticked — the amount to settle.
class _BillRow extends StatelessWidget {
  final OpenBill bill;
  final bool picked;
  final TextEditingController controller;
  final List<TextInputFormatter> formatters;
  final ValueChanged<bool> onPicked;
  final VoidCallback onAmountChanged;
  const _BillRow({
    required this.bill,
    required this.picked,
    required this.controller,
    required this.formatters,
    required this.onPicked,
    required this.onAmountChanged,
  });

  @override
  Widget build(BuildContext context) {
    final late = bill.daysOverdue > 0;
    return DecoratedBox(
      decoration: BoxDecoration(
        color: picked ? AppTheme.primary.withValues(alpha: 0.05) : null,
        border: Border.all(color: picked ? AppTheme.primary : AppTheme.border),
        borderRadius: BorderRadius.circular(AppTheme.radiusS),
      ),
      child: Padding(
        padding: const EdgeInsets.fromLTRB(4, 4, 12, 8),
        child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          Material(
              type: MaterialType.transparency, // a ListTile paints on its nearest Material, not on the card around it
              child: CheckboxListTile(
                key: ValueKey('bill-${bill.invoiceNumber}'),
                value: picked,
                onChanged: (v) => onPicked(v ?? false),
                controlAffinity: ListTileControlAffinity.leading,
                contentPadding: EdgeInsets.zero,
                title: Text(bill.invoiceNumber, style: const TextStyle(fontWeight: FontWeight.w600)),
                subtitle: Text(
                  '${formatAccountsDate(bill.invoiceDate)} · due ${formatAccountsDate(bill.dueDate)}'
                  '${late ? ' · ${bill.daysOverdue} days late' : ''}'
                  '${(bill.description ?? '').isEmpty ? '' : '\n${bill.description}'}',
                  style: TextStyle(color: late ? AppTheme.error : AppTheme.textSecondary, fontSize: 12),
                ),
                secondary: Text(formatInr(bill.outstandingAmount), style: const TextStyle(fontWeight: FontWeight.w700)),
              )),
          if (picked)
            Padding(
              padding: const EdgeInsets.only(left: 48),
              child: TextFormField(
                key: ValueKey('amount-${bill.invoiceNumber}'),
                controller: controller,
                keyboardType: const TextInputType.numberWithOptions(decimal: true),
                inputFormatters: formatters,
                decoration: const InputDecoration(labelText: 'Amount settled', prefixText: '₹'),
                onChanged: (_) => onAmountChanged(),
                validator: (v) {
                  final n = double.tryParse(v ?? '');
                  if (n == null || n <= 0) return 'Enter a valid amount';
                  if (n > bill.outstandingAmount + 0.001) {
                    return 'Cannot exceed what is owed (${formatInr(bill.outstandingAmount)})';
                  }
                  return null;
                },
              ),
            ),
        ]),
      ),
    );
  }
}

/// Opens the pay-vendor screen, with [vendorId] chosen when it is known.
void openPayVendor(BuildContext context, {String? vendorId}) =>
    context.push(vendorId == null ? AppRoutes.payVendorBills : '${AppRoutes.payVendorBills}?vendor=$vendorId');
