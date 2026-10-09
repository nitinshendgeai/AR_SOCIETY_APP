import 'package:flutter/material.dart';
import 'package:ar_society_app/shared/widgets/app_data_table.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/router/app_router.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/accounts/data/accounts_api.dart';
import 'package:ar_society_app/features/accounts/presentation/providers/accounts_providers.dart';
import 'package:ar_society_app/features/accounts/presentation/widgets/accounts_widgets.dart' show NextVoucherNumber;
import 'package:ar_society_app/features/vendor/data/vendors_work_api.dart' show VendorRecord;
import 'package:ar_society_app/features/vendor/presentation/widgets/vendor_picker.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/features/maintenance_billing/data/maintenance_billing_api.dart';
import 'package:ar_society_app/features/maintenance_billing/presentation/providers/maintenance_billing_providers.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';

/// "Other": an expense that is not recovered through the monthly maintenance bill.
const _otherElement = '__other__';

/// Record an expense the way a treasurer thinks of it: what it was for (the maintenance element),
/// which expense head, how much, and whether it was paid from cash or the bank. It becomes a Payment
/// voucher in the books. An expense head that does not yet count towards the chosen element is linked
/// to it when the expense is saved, so the next one lands under the same element on its own and the
/// element's spend feeds its budget in the monthly maintenance calculation.
class ExpenseFormScreen extends ConsumerStatefulWidget {
  /// Start from an amount and a note (an asset's service that cost money, for instance).
  final double? initialAmount;
  final String? initialNote;
  const ExpenseFormScreen({super.key, this.initialAmount, this.initialNote});

  @override
  ConsumerState<ExpenseFormScreen> createState() => _ExpenseFormScreenState();
}

class _ExpenseFormScreenState extends ConsumerState<ExpenseFormScreen> {
  DateTime _date = DateTime.now();
  String? _elementKey; // an element id, or _otherElement
  LedgerAccount? _head;
  LedgerAccount? _paidFrom;
  late final _amount = TextEditingController(
      text: widget.initialAmount == null ? '' : widget.initialAmount!.toStringAsFixed(widget.initialAmount! % 1 == 0 ? 0 : 2));
  VendorRecord? _vendor;
  final _reference = TextEditingController();
  late final _note = TextEditingController(text: widget.initialNote);
  bool _saving = false;
  String? _lastSaved;

  @override
  void dispose() {
    _amount.dispose();
    _reference.dispose();
    _note.dispose();
    super.dispose();
  }

  /// The expense heads to offer for the chosen element: those that already count towards it; when there
  /// are none, the heads that count towards nothing yet (one of them is linked on save).
  List<LedgerAccount> _headsFor(List<LedgerAccount> expense) {
    if (_elementKey == null) return const [];
    if (_elementKey == _otherElement) return expense.where((l) => l.maintenanceElementId == null).toList();
    final linked = expense.where((l) => l.maintenanceElementId == _elementKey).toList();
    return linked.isNotEmpty ? linked : expense.where((l) => l.maintenanceElementId == null).toList();
  }

  bool _willLink(LedgerAccount? head) =>
      head != null && _elementKey != null && _elementKey != _otherElement && head.maintenanceElementId == null;

  void _chooseElement(String? key, List<LedgerAccount> expense) {
    setState(() {
      _elementKey = key;
      final heads = _headsFor(expense);
      _head = heads.length == 1 ? heads.first : null;
    });
  }

  Future<void> _pickDate() async {
    final d = await showDatePicker(
      context: context,
      initialDate: _date,
      firstDate: DateTime(DateTime.now().year - 2),
      lastDate: DateTime.now().add(const Duration(days: 31)),
    );
    if (d != null) setState(() => _date = d);
  }

  String? _problem(double amount) {
    if (_elementKey == null) return 'Choose what the expense was for';
    if (_head == null) return 'Choose the expense head';
    if (amount <= 0) return 'Enter the amount';
    if (_paidFrom == null) return 'Choose cash or the bank account it was paid from';
    return null;
  }

  Future<void> _save(String societyId, {required bool another}) async {
    final amount = double.tryParse(_amount.text.trim()) ?? 0;
    final problem = _problem(amount);
    if (problem != null) {
      AppToast.warning(context, problem);
      return;
    }
    setState(() => _saving = true);
    try {
      final api = ref.read(accountsApiProvider);
      final head = _head!;
      String? counted = head.maintenanceElementName;
      if (_willLink(head)) {
        // Remember the link for next time: this head now counts towards the element.
        final updated = await api.updateLedger(head.id, {'maintenance_element_id': _elementKey});
        counted = updated.maintenanceElementName;
      }
      final narration = [_vendor?.companyName ?? '', _note.text.trim()].where((s) => s.isNotEmpty).join(' — ');
      final v = await api.createVoucher(
        societyId: societyId,
        type: 'payment',
        date: _date,
        lines: [
          VoucherLineInput(accountId: head.id, debit: amount),
          VoucherLineInput(accountId: _paidFrom!.id, credit: amount),
        ],
        narration: narration,
        reference: _reference.text.trim(),
        vendorId: _vendor?.id,
      );
      invalidateBooks(ref);
      if (!mounted) return;
      final where = counted == null ? '' : ' — counts towards $counted';
      AppToast.success(context, '${formatInr(amount)} saved as ${v.voucherNumber}$where');
      if (another) {
        setState(() {
          _saving = false;
          _lastSaved = '${head.name} ${formatInr(amount)}';
          _amount.clear();
          _vendor = null;
          _reference.clear();
          _note.clear();
        });
      } else {
        context.canPop() ? context.pop() : context.go(AppRoutes.accounts);
      }
    } catch (e) {
      if (mounted) {
        setState(() => _saving = false);
        showErrorToast(context, e);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final societyId = ref.watch(currentUserProvider)?.societyId;
    if (societyId == null) return const Scaffold(body: Center(child: Text('No society context')));
    final ledgersAsync = ref.watch(ledgersProvider(societyId));
    final elementsAsync = ref.watch(maintenanceElementsProvider((societyId: societyId, includeInactive: false)));

    return Scaffold(
      backgroundColor: AppTheme.surface,
      appBar: AppBar(title: const Text('Add Expense'), actions: [
        AppBarTextAction(
          onPressed: () => context.push(AppRoutes.accountsExpenses),
          icon: Icons.pie_chart_outline_rounded,
          label: 'Spend by element',
        ),
      ]),
      body: ResponsiveBody(
        maxWidth: 640,
        child: ledgersAsync.when(
          loading: () => const Center(child: CircularProgressIndicator(color: AppTheme.primary)),
          error: (e, _) => ListView(padding: const EdgeInsets.all(20), children: [
            AppErrorBanner(message: friendlyErrorMessage(e)),
          ]),
          data: (all) => elementsAsync.when(
            loading: () => const Center(child: CircularProgressIndicator(color: AppTheme.primary)),
            error: (e, _) => ListView(padding: const EdgeInsets.all(20), children: [
              AppErrorBanner(message: friendlyErrorMessage(e)),
            ]),
            data: (elements) => _form(societyId, all, elements),
          ),
        ),
      ),
    );
  }

  Widget _form(String societyId, List<LedgerAccount> all, List<MaintenanceElement> allElements) {
    final expense = all.where((l) => l.nature == 'expense' && l.isActive).toList();
    final cashBank = all.where((l) => l.isCashOrBank && l.isActive).toList();
    _paidFrom ??= cashBank.where((l) => l.isCash).firstOrNull ?? cashBank.firstOrNull;
    // Contributions to the funds are not running expenses.
    final elements = allElements.where((e) => e.category != 'sinking_fund' && e.category != 'repair_fund').toList()
      ..sort((a, b) {
        final ah = expense.any((l) => l.maintenanceElementId == a.id) ? 0 : 1;
        final bh = expense.any((l) => l.maintenanceElementId == b.id) ? 0 : 1;
        return ah != bh ? ah - bh : a.name.compareTo(b.name);
      });
    final heads = _headsFor(expense);
    final element = elements.where((e) => e.id == _elementKey).firstOrNull;
    final head = heads.contains(_head) ? _head : null;

    return ListView(
      padding: const EdgeInsets.fromLTRB(16, 16, 16, 40),
      children: [
        const Text(
          'Record any expense — a daily petty-cash purchase or the month\'s bill for security, electricity or the lift. '
          'It is posted to the books as a payment and counts towards the maintenance element it belongs to.',
          style: TextStyle(fontSize: 13, color: AppTheme.textSecondary, height: 1.4),
        ),
        if (_lastSaved != null) ...[
          const SizedBox(height: 10),
          Container(
            padding: const EdgeInsets.all(10),
            decoration: BoxDecoration(
              color: AppTheme.success.withOpacity(0.1), borderRadius: BorderRadius.circular(8)),
            child: Row(children: [
              const Icon(Icons.check_circle_rounded, size: 18, color: AppTheme.success),
              const SizedBox(width: 8),
              Expanded(child: Text('Saved: $_lastSaved. Add the next one below.', style: const TextStyle(fontSize: 13))),
            ]),
          ),
        ],
        const SizedBox(height: 16),
        InkWell(
          onTap: _pickDate,
          child: InputDecorator(
            decoration: const InputDecoration(labelText: 'Date', suffixIcon: Icon(Icons.calendar_today_rounded, size: 18)),
            child: Text(apiDate(_date)),
          ),
        ),
        const SizedBox(height: 14),
        DropdownButtonFormField<String>(
          value: _elementKey,
          isExpanded: true,
          decoration: const InputDecoration(labelText: 'What is it for? (maintenance element)'),
          items: [
            for (final e in elements) DropdownMenuItem(value: e.id, child: Text(e.name, overflow: TextOverflow.ellipsis)),
            const DropdownMenuItem(value: _otherElement, child: Text('Other — not billed through maintenance')),
          ],
          onChanged: (v) => _chooseElement(v, expense),
        ),
        const SizedBox(height: 14),
        DropdownButtonFormField<LedgerAccount>(
          key: ValueKey('head/$_elementKey/${heads.length}'),
          value: head,
          isExpanded: true,
          decoration: InputDecoration(
            labelText: 'Expense head',
            helperText: _elementKey == null
                ? 'Choose what it is for first'
                : _willLink(head)
                    ? 'Not linked to an element yet — it will be linked to ${element?.name} when you save, '
                        'so the next one counts automatically.'
                    : head?.maintenanceElementName != null
                        ? 'Counts towards ${head!.maintenanceElementName}'
                        : null,
            helperMaxLines: 3,
          ),
          items: [for (final l in heads) DropdownMenuItem(value: l, child: Text(l.name, overflow: TextOverflow.ellipsis))],
          onChanged: _elementKey == null ? null : (v) => setState(() => _head = v),
        ),
        if (_elementKey != null && heads.isEmpty)
          Padding(
            padding: const EdgeInsets.only(top: 6),
            child: TextButton.icon(
              onPressed: () => context.push(AppRoutes.accountsChart),
              icon: const Icon(Icons.add_rounded, size: 18),
              label: const Text('No expense head for this yet — add one in the Chart of Accounts'),
            ),
          ),
        const SizedBox(height: 14),
        TextField(
          controller: _amount,
          keyboardType: const TextInputType.numberWithOptions(decimal: true),
          inputFormatters: [FilteringTextInputFormatter.allow(RegExp(r'[0-9.]'))],
          decoration: const InputDecoration(labelText: 'Amount (₹)', prefixText: '₹ '),
        ),
        Align(
          alignment: Alignment.centerLeft,
          child: TextButton.icon(
            onPressed: () => context.push(AppRoutes.accountsRecurring),
            icon: const Icon(Icons.event_repeat_rounded, size: 16),
            label: const Text('Comes every month? Set it up as a monthly expense'),
          ),
        ),
        const SizedBox(height: 14),
        DropdownButtonFormField<LedgerAccount>(
          value: _paidFrom,
          isExpanded: true,
          decoration: const InputDecoration(labelText: 'Paid from'),
          items: [for (final l in cashBank) DropdownMenuItem(value: l, child: Text(l.name, overflow: TextOverflow.ellipsis))],
          onChanged: (v) => setState(() => _paidFrom = v),
        ),
        const SizedBox(height: 14),
        VendorPicker(
          societyId: societyId,
          value: _vendor?.id,
          label: 'Paid to (optional)',
          onChanged: (v) => setState(() => _vendor = v),
        ),
        const SizedBox(height: 14),
        TextField(
          controller: _reference,
          decoration: const InputDecoration(
            labelText: "Supplier's bill / cheque no. (optional)",
            helperText: 'The number on their bill or your cheque — ours is given automatically',
            helperMaxLines: 2,
          ),
        ),
        const SizedBox(height: 14),
        NextVoucherNumber(societyId: societyId, type: 'payment', date: _date),
        const SizedBox(height: 14),
        TextField(controller: _note, decoration: const InputDecoration(labelText: 'Note (optional)'), maxLines: 2),
        const SizedBox(height: 22),
        AppPrimaryButton(label: 'Save expense', isLoading: _saving, onPressed: _saving ? null : () => _save(societyId, another: false)),
        const SizedBox(height: 10),
        OutlinedButton(
          onPressed: _saving ? null : () => _save(societyId, another: true),
          child: const Text('Save and add another'),
        ),
      ],
    );
  }
}
