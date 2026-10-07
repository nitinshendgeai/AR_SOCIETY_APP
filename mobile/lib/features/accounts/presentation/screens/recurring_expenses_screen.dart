import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/layout/app_shell.dart' show isDesktopLayout;
import 'package:ar_society_app/core/layout/app_sheet.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/accounts/data/accounts_api.dart' show LedgerAccount, formatInr;
import 'package:ar_society_app/features/accounts/data/recurring_api.dart';
import 'package:ar_society_app/features/accounts/presentation/providers/accounts_providers.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/features/maintenance_billing/presentation/widgets/billing_sheet_frame.dart';
import 'package:ar_society_app/features/vendor/presentation/widgets/procurement_widgets.dart';
import 'package:ar_society_app/shared/widgets/app_data_table.dart' show HeaderActionButton, StatusPill;
import 'package:ar_society_app/shared/widgets/app_widgets.dart';

const _monthNames = [
  'January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'
];
String monthLabel(DateTime d) => '${_monthNames[d.month - 1]} ${d.year}';
DateTime _today() {
  final n = DateTime.now();
  return DateTime(n.year, n.month, n.day);
}

String? _trimmed(TextEditingController c) => c.text.trim().isEmpty ? null : c.text.trim();

/// The expenses a society pays every month — the security agency, the lift AMC, the office rent. Nothing is
/// posted by itself: each month they come up as due here, the amount is confirmed (or entered, for a bill that
/// changes) and it goes into the books as a payment under the right maintenance element.
class RecurringExpensesScreen extends ConsumerWidget {
  const RecurringExpensesScreen({super.key});

  void _add(BuildContext context) => showAppSheet(context: context, builder: (_) => const RecurringFormSheet());

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final societyId = ref.watch(currentUserProvider)?.societyId;
    if (societyId == null) return const Scaffold(body: Center(child: Text('No society context')));
    final desktop = isDesktopLayout(context);
    final due = ref.watch(recurringDueProvider(societyId));
    final all = ref.watch(recurringListProvider(societyId));

    return Scaffold(
      backgroundColor: AppTheme.surface,
      appBar: AppBar(
        title: const Text('Monthly expenses'),
        actions: [
          if (desktop) HeaderActionButton(icon: Icons.add_rounded, label: 'Add monthly expense', onPressed: () => _add(context)),
        ],
      ),
      floatingActionButton: desktop
          ? null
          : FloatingActionButton.extended(
              onPressed: () => _add(context), icon: const Icon(Icons.add_rounded), label: const Text('Add monthly expense')),
      body: RefreshIndicator(
        onRefresh: () async => invalidateBooks(ref),
        child: ResponsiveBody(
          maxWidth: 820,
          child: ListView(padding: const EdgeInsets.fromLTRB(16, 16, 16, 96), children: [
            const Text(
              'Bills that come every month. Each month they appear below as due. Confirm the amount, or enter it '
              'for a bill that changes, and it is booked as a payment under its maintenance element.',
              style: TextStyle(fontSize: 13, color: AppTheme.textSecondary, height: 1.4),
            ),
            const SizedBox(height: 16),
            const _Title('Due now'),
            due.when(
              loading: () => const Padding(padding: EdgeInsets.all(24), child: Center(child: CircularProgressIndicator())),
              error: (e, _) => AppErrorBanner(message: friendlyErrorMessage(e)),
              data: (rows) => rows.isEmpty
                  ? Card(
                      child: Padding(
                        padding: const EdgeInsets.all(16),
                        child: Row(children: [
                          const Icon(Icons.check_circle_rounded, color: AppTheme.success),
                          const SizedBox(width: 12),
                          Expanded(child: Text(all.valueOrNull?.isEmpty ?? true ? 'Nothing set up yet.' : 'Nothing due. You are up to date.')),
                        ]),
                      ),
                    )
                  : Column(children: [for (final d in rows) _DueCard(due: d, societyId: societyId)]),
            ),
            const SizedBox(height: 20),
            const _Title('All monthly expenses'),
            all.when(
              loading: () => const SizedBox.shrink(),
              error: (e, _) => AppErrorBanner(message: friendlyErrorMessage(e)),
              data: (rows) => rows.isEmpty
                  ? AppEmptyState(
                      icon: Icons.event_repeat_rounded,
                      title: 'No monthly expenses yet',
                      subtitle: 'Add the ones you pay every month: the security agency, housekeeping, the lift contract, '
                          'electricity. You will be reminded each month.',
                      actionLabel: 'Add the first one',
                      onAction: () => _add(context),
                    )
                  : Column(children: [for (final r in rows) _TemplateTile(r: r)]),
            ),
          ]),
        ),
      ),
    );
  }
}

class _Title extends StatelessWidget {
  final String text;
  const _Title(this.text);

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.only(bottom: 8),
        child: Text(text, style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w700)),
      );
}

class _DueCard extends ConsumerWidget {
  final DueExpense due;
  final String societyId;
  const _DueCard({required this.due, required this.societyId});

  Future<void> _skip(BuildContext context, WidgetRef ref) async {
    final reason = TextEditingController();
    final ok = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: Text('Skip ${due.name} for ${monthLabel(due.month)}?'),
        content: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
          const Text('Nothing is booked. Use it when the month was paid another way or does not apply.'),
          const SizedBox(height: 12),
          TextField(controller: reason, decoration: const InputDecoration(labelText: 'Why (optional)')),
        ]),
        actions: [
          TextButton(onPressed: () => Navigator.of(dialogContext).pop(false), child: const Text('Cancel')),
          FilledButton(onPressed: () => Navigator.of(dialogContext).pop(true), child: const Text('Skip this month')),
        ],
      ),
    );
    final text = reason.text.trim();
    reason.dispose();
    if (ok != true) return;
    try {
      await ref.read(recurringApiProvider).skip(due.recurringId, due.month, reason: text);
      invalidateBooks(ref);
    } catch (e) {
      if (context.mounted) showErrorToast(context, e);
    }
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) => Card(
        margin: const EdgeInsets.only(bottom: 8),
        child: Padding(
          padding: const EdgeInsets.all(14),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Expanded(
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Text(due.name, style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 15)),
                  const SizedBox(height: 2),
                  Text(monthLabel(due.month), style: const TextStyle(color: AppTheme.textSecondary, fontSize: 13)),
                ]),
              ),
              Text(due.amount == null ? 'Amount varies' : formatInr(due.amount!),
                  style: TextStyle(fontWeight: FontWeight.w700, fontSize: 15, color: due.amount == null ? AppTheme.textSecondary : null)),
            ]),
            const SizedBox(height: 6),
            Wrap(spacing: 8, runSpacing: 4, crossAxisAlignment: WrapCrossAlignment.center, children: [
              if (due.daysLate > 0)
                StatusPill('${due.daysLate} day${due.daysLate == 1 ? '' : 's'} late', due.daysLate > 30 ? AppTheme.error : AppTheme.warning)
              else
                const StatusPill('Due today', AppTheme.primary),
              Text(
                [
                  if ((due.expenseAccountName ?? '').isNotEmpty) due.expenseAccountName!,
                  if ((due.elementName ?? '').isNotEmpty) 'counts towards ${due.elementName}',
                  if ((due.payee ?? '').isNotEmpty) due.payee!,
                ].join(' · '),
                style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary),
              ),
            ]),
            const SizedBox(height: 10),
            Row(children: [
              FilledButton.icon(
                onPressed: () => showAppSheet(context: context, builder: (_) => RecordDueSheet(due: due, societyId: societyId)),
                icon: const Icon(Icons.check_rounded, size: 18),
                label: const Text('Record'),
              ),
              const SizedBox(width: 8),
              TextButton(onPressed: () => _skip(context, ref), child: const Text('Skip')),
            ]),
          ]),
        ),
      );
}

class _TemplateTile extends StatelessWidget {
  final RecurringExpense r;
  const _TemplateTile({required this.r});

  @override
  Widget build(BuildContext context) => Card(
        margin: const EdgeInsets.only(bottom: 8),
        child: ListTile(
          onTap: () => showAppSheet(context: context, builder: (_) => RecurringFormSheet(existing: r)),
          title: Text(r.name, style: const TextStyle(fontWeight: FontWeight.w600)),
          subtitle: Text([
            r.amount == null ? 'Amount varies' : '${formatInr(r.amount!)} a month',
            'day ${r.dayOfMonth}',
            if ((r.expenseAccountName ?? '').isNotEmpty) r.expenseAccountName!,
            if ((r.elementName ?? '').isNotEmpty) '→ ${r.elementName}',
          ].join(' · ')),
          trailing: !r.isActive
              ? const StatusPill('Paused', AppTheme.textSecondary)
              : r.dueMonths > 0
                  ? StatusPill('${r.dueMonths} due', AppTheme.warning)
                  : null,
        ),
      );
}

// ── Add or change a monthly expense ──────────────────────────────────────────

class RecurringFormSheet extends ConsumerStatefulWidget {
  final RecurringExpense? existing;
  const RecurringFormSheet({super.key, this.existing});

  @override
  ConsumerState<RecurringFormSheet> createState() => _RecurringFormSheetState();
}

class _RecurringFormSheetState extends ConsumerState<RecurringFormSheet> {
  final _form = GlobalKey<FormState>();
  late final _name = TextEditingController(text: e?.name);
  late final _amount = TextEditingController(text: e?.amount == null ? '' : e!.amount!.toStringAsFixed(e!.amount! % 1 == 0 ? 0 : 2));
  late final _payee = TextEditingController(text: e?.payee);
  late final _note = TextEditingController(text: e?.note);
  late int _dayOfMonth = e?.dayOfMonth ?? 1;
  late String? _head = e?.expenseAccountId;
  late String? _paidFrom = e?.paidFromId;
  late DateTime _start = e?.startMonth ?? DateTime(DateTime.now().year, DateTime.now().month, 1);
  late DateTime? _end = e?.endMonth;
  late bool _active = e?.isActive ?? true;
  bool _saving = false;

  RecurringExpense? get e => widget.existing;

  @override
  void dispose() {
    for (final c in [_name, _amount, _payee, _note]) {
      c.dispose();
    }
    super.dispose();
  }

  Future<void> _save() async {
    if (!_form.currentState!.validate()) return;
    setState(() => _saving = true);
    try {
      final api = ref.read(recurringApiProvider);
      final body = <String, dynamic>{
        'name': _name.text.trim(),
        'expense_account_id': _head,
        'paid_from_id': _paidFrom,
        'amount': parseMoney(_amount.text),
        'day_of_month': _dayOfMonth,
        'start_month': _iso(_start),
        'end_month': _end == null ? null : _iso(_end!),
        'payee': _trimmed(_payee),
        'note': _trimmed(_note),
      };
      if (e == null) {
        body.removeWhere((_, v) => v == null);
        await api.create(body);
      } else {
        body['is_active'] = _active;
        await api.update(e!.id, body);
      }
      invalidateBooks(ref);
      if (!mounted) return;
      AppToast.success(context, e == null ? 'Monthly expense added' : 'Changes saved');
      Navigator.of(context).pop();
    } catch (err) {
      if (mounted) {
        setState(() => _saving = false);
        showErrorToast(context, err);
      }
    }
  }

  static String _iso(DateTime d) =>
      '${d.year.toString().padLeft(4, '0')}-${d.month.toString().padLeft(2, '0')}-${d.day.toString().padLeft(2, '0')}';

  @override
  Widget build(BuildContext context) {
    final societyId = ref.watch(currentUserProvider)?.societyId ?? '';
    final ledgers = ref.watch(ledgersProvider(societyId));
    return BillingSheetFrame(
      title: e == null ? 'Add a monthly expense' : 'Edit ${e!.name}',
      child: Form(
        key: _form,
        autovalidateMode: AutovalidateMode.onUserInteraction,
        child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          TextFormField(
            controller: _name,
            maxLength: 150,
            textCapitalization: TextCapitalization.sentences,
            decoration: const InputDecoration(labelText: 'What is it *', hintText: 'e.g. Security agency, Lift AMC', counterText: ''),
            validator: (v) => (v ?? '').trim().isEmpty ? 'Give it a name' : null,
          ),
          const SizedBox(height: 12),
          ledgers.when(
            loading: () => const LinearProgressIndicator(),
            error: (err, _) => AppErrorBanner(message: friendlyErrorMessage(err)),
            data: (all) {
              final heads = all.where((l) => l.nature == 'expense' && l.isActive).toList()
                ..sort((a, b) => a.name.compareTo(b.name));
              final cashBank = all.where((l) => l.isCashOrBank && l.isActive).toList();
              return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
                DropdownButtonFormField<String>(
                  initialValue: heads.any((h) => h.id == _head) ? _head : null,
                  isExpanded: true,
                  decoration: InputDecoration(
                    labelText: 'Expense head *',
                    helperText: _helper(heads),
                    helperMaxLines: 2,
                  ),
                  validator: (v) => v == null ? 'Choose the expense head' : null,
                  items: [
                    for (final h in heads)
                      DropdownMenuItem(
                        value: h.id,
                        child: Text(
                            h.maintenanceElementName == null ? h.name : '${h.name} → ${h.maintenanceElementName}',
                            overflow: TextOverflow.ellipsis),
                      ),
                  ],
                  onChanged: (v) => setState(() => _head = v),
                ),
                const SizedBox(height: 12),
                DropdownButtonFormField<String?>(
                  initialValue: cashBank.any((c) => c.id == _paidFrom) ? _paidFrom : null,
                  isExpanded: true,
                  decoration: const InputDecoration(labelText: 'Usually paid from'),
                  items: [
                    const DropdownMenuItem<String?>(value: null, child: Text('Cash in hand')),
                    for (final c in cashBank.where((c) => !c.isCash)) DropdownMenuItem<String?>(value: c.id, child: Text(c.name)),
                  ],
                  onChanged: (v) => setState(() => _paidFrom = v),
                ),
              ]);
            },
          ),
          const SizedBox(height: 12),
          Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Expanded(
              flex: 3,
              child: TextFormField(
                controller: _amount,
                keyboardType: const TextInputType.numberWithOptions(decimal: true),
                inputFormatters: moneyInput,
                decoration: const InputDecoration(
                    labelText: 'Amount (₹)', prefixText: '₹ ', helperText: 'Blank if it changes each month', helperMaxLines: 2),
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              flex: 2,
              child: DropdownButtonFormField<int>(
                initialValue: _dayOfMonth,
                decoration: const InputDecoration(labelText: 'Due on day', helperText: ' '),
                items: [for (var d = 1; d <= 31; d++) DropdownMenuItem(value: d, child: Text('$d'))],
                onChanged: (v) => setState(() => _dayOfMonth = v ?? 1),
              ),
            ),
          ]),
          const SizedBox(height: 12),
          Row(children: [
            Expanded(
              child: DateField(
                  label: 'From month', value: _start, required: true,
                  onChanged: (d) => setState(() => _start = DateTime((d ?? _start).year, (d ?? _start).month, 1))),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: DateField(
                  label: 'Until (optional)', value: _end,
                  onChanged: (d) => setState(() => _end = d == null ? null : DateTime(d.year, d.month, 1))),
            ),
          ]),
          const SizedBox(height: 12),
          TextFormField(
            controller: _payee,
            maxLength: 255,
            decoration: const InputDecoration(labelText: 'Paid to', hintText: 'e.g. Shield Security Services', counterText: ''),
          ),
          const SizedBox(height: 12),
          TextFormField(controller: _note, minLines: 1, maxLines: 3, decoration: const InputDecoration(labelText: 'Note')),
          if (e != null)
            SwitchListTile(
              contentPadding: EdgeInsets.zero,
              value: _active,
              onChanged: (v) => setState(() => _active = v),
              title: const Text('Running'),
              subtitle: const Text('Turn off to pause it. Nothing comes up as due while it is paused.'),
            ),
          const SizedBox(height: 16),
          AppPrimaryButton(label: e == null ? 'Add monthly expense' : 'Save changes', isLoading: _saving, onPressed: _saving ? null : _save),
        ]),
      ),
    );
  }

  String? _helper(List<LedgerAccount> heads) {
    final h = heads.where((l) => l.id == _head).firstOrNull;
    if (h == null) return 'Where each month is booked';
    return h.maintenanceElementName == null
        ? 'Not linked to a maintenance element yet'
        : 'Counts towards ${h.maintenanceElementName}';
  }
}

// ── Record a due month ───────────────────────────────────────────────────────

class RecordDueSheet extends ConsumerStatefulWidget {
  final DueExpense due;
  final String societyId;
  const RecordDueSheet({super.key, required this.due, required this.societyId});

  @override
  ConsumerState<RecordDueSheet> createState() => _RecordDueSheetState();
}

class _RecordDueSheetState extends ConsumerState<RecordDueSheet> {
  final _form = GlobalKey<FormState>();
  late final _amount = TextEditingController(
      text: widget.due.amount == null ? '' : widget.due.amount!.toStringAsFixed(widget.due.amount! % 1 == 0 ? 0 : 2));
  final _reference = TextEditingController();
  final _note = TextEditingController();
  late DateTime _paidOn = _today();
  late String? _paidFrom = widget.due.paidFromId;
  bool _saving = false;

  @override
  void dispose() {
    _amount.dispose();
    _reference.dispose();
    _note.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    if (!_form.currentState!.validate()) return;
    setState(() => _saving = true);
    try {
      final amount = parseMoney(_amount.text)!;
      final v = await ref.read(recurringApiProvider).record(widget.due.recurringId,
          month: widget.due.month,
          amount: amount,
          date: _paidOn,
          paidFromId: _paidFrom,
          reference: _reference.text.trim(),
          note: _note.text.trim());
      invalidateBooks(ref);
      if (!mounted) return;
      AppToast.success(context, '${formatInr(amount)} saved as ${v.voucherNumber}');
      Navigator.of(context).pop();
    } catch (err) {
      if (mounted) {
        setState(() => _saving = false);
        showErrorToast(context, err);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final ledgers = ref.watch(ledgersProvider(widget.societyId));
    return BillingSheetFrame(
      title: 'Record ${widget.due.name}',
      child: Form(
        key: _form,
        child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          Text('${monthLabel(widget.due.month)} · ${widget.due.expenseAccountName ?? ''}'
              '${(widget.due.elementName ?? '').isEmpty ? '' : ' · counts towards ${widget.due.elementName}'}',
              style: const TextStyle(color: AppTheme.textSecondary, fontSize: 13)),
          const SizedBox(height: 14),
          TextFormField(
            controller: _amount,
            autofocus: widget.due.amount == null,
            keyboardType: const TextInputType.numberWithOptions(decimal: true),
            inputFormatters: moneyInput,
            decoration: InputDecoration(
              labelText: 'Amount for this month (₹) *',
              prefixText: '₹ ',
              helperText: widget.due.amount == null ? 'Enter the amount on this month\'s bill' : 'Change it if this month was different',
            ),
            validator: (v) => (parseMoney(v ?? '') ?? 0) <= 0 ? 'Enter the amount' : null,
          ),
          const SizedBox(height: 12),
          DateField(label: 'Paid on', value: _paidOn, required: true, lastDate: _today(), onChanged: (d) => setState(() => _paidOn = d ?? _paidOn)),
          const SizedBox(height: 12),
          ledgers.when(
            loading: () => const LinearProgressIndicator(),
            error: (err, _) => const SizedBox.shrink(),
            data: (all) {
              final cashBank = all.where((l) => l.isCashOrBank && l.isActive).toList();
              return DropdownButtonFormField<String?>(
                initialValue: cashBank.any((c) => c.id == _paidFrom) ? _paidFrom : null,
                isExpanded: true,
                decoration: const InputDecoration(labelText: 'Paid from'),
                items: [
                  const DropdownMenuItem<String?>(value: null, child: Text('Cash in hand')),
                  for (final c in cashBank.where((c) => !c.isCash)) DropdownMenuItem<String?>(value: c.id, child: Text(c.name)),
                ],
                onChanged: (v) => setState(() => _paidFrom = v),
              );
            },
          ),
          const SizedBox(height: 12),
          TextFormField(controller: _reference, maxLength: 100, decoration: const InputDecoration(labelText: 'Bill / cheque no.', counterText: '')),
          const SizedBox(height: 12),
          TextFormField(controller: _note, minLines: 1, maxLines: 3, decoration: const InputDecoration(labelText: 'Note')),
          const SizedBox(height: 20),
          AppPrimaryButton(label: 'Record payment', isLoading: _saving, onPressed: _saving ? null : _save),
        ]),
      ),
    );
  }
}
