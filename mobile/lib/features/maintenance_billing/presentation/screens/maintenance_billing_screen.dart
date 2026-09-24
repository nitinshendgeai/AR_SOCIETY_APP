import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/features/maintenance_billing/data/maintenance_billing_api.dart';
import 'package:ar_society_app/features/maintenance_billing/presentation/providers/maintenance_billing_providers.dart';
import 'package:ar_society_app/features/maintenance_billing/presentation/screens/billing_cycle_screen.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';

/// Society side of maintenance billing: set up charge heads once, then each
/// period create a cycle → generate one bill per flat → issue to residents.
class MaintenanceBillingScreen extends ConsumerStatefulWidget {
  const MaintenanceBillingScreen({super.key});

  @override
  ConsumerState<MaintenanceBillingScreen> createState() => _MaintenanceBillingScreenState();
}

class _MaintenanceBillingScreenState extends ConsumerState<MaintenanceBillingScreen>
    with SingleTickerProviderStateMixin {
  late final TabController _tabs = TabController(length: 2, vsync: this)
    ..addListener(() => setState(() {}));

  @override
  void dispose() {
    _tabs.dispose();
    super.dispose();
  }

  void _openSheet(Widget sheet) => showModalBottomSheet(
        context: context, isScrollControlled: true, backgroundColor: Colors.transparent,
        builder: (_) => sheet,
      );

  @override
  Widget build(BuildContext context) {
    final societyId = ref.watch(currentUserProvider)?.societyId;
    if (societyId == null) {
      return const Scaffold(body: Center(child: Text('No society context')));
    }
    final onCycles = _tabs.index == 0;

    return Scaffold(
      backgroundColor: AppTheme.surface,
      appBar: AppBar(
        title: const Text('Maintenance Billing'),
        bottom: TabBar(controller: _tabs, tabs: const [
          Tab(text: 'Billing Cycles'),
          Tab(text: 'Charge Heads'),
        ]),
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () => _openSheet(onCycles
            ? _NewCycleSheet(societyId: societyId)
            : _ChargeHeadSheet(societyId: societyId)),
        icon: const Icon(Icons.add_rounded),
        label: Text(onCycles ? 'New Cycle' : 'Add Charge Head'),
      ),
      body: TabBarView(controller: _tabs, children: [
        _CyclesTab(societyId: societyId, onAddChargeHeads: () => _tabs.animateTo(1)),
        _ChargeHeadsTab(societyId: societyId, onEdit: (c) => _openSheet(
            _ChargeHeadSheet(societyId: societyId, existing: c))),
      ]),
    );
  }
}

// ── Cycles tab ────────────────────────────────────────────────────────────────

class _CyclesTab extends ConsumerWidget {
  final String societyId;
  final VoidCallback onAddChargeHeads;
  const _CyclesTab({required this.societyId, required this.onAddChargeHeads});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final cyclesAsync = ref.watch(billingCyclesProvider(societyId));
    final chargesAsync = ref.watch(chargeHeadsProvider(societyId));
    final noCharges = chargesAsync.valueOrNull?.isEmpty ?? false;

    return RefreshIndicator(
      onRefresh: () async {
        ref.invalidate(billingCyclesProvider(societyId));
        ref.invalidate(chargeHeadsProvider(societyId));
      },
      child: cyclesAsync.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (e, _) => ListView(children: [
          Padding(
            padding: const EdgeInsets.all(24),
            child: Text(friendlyErrorMessage(e), style: const TextStyle(color: AppTheme.error)),
          ),
        ]),
        data: (cycles) {
          final billed = cycles.fold<double>(0, (s, c) => s + amountOf(c.totalBilled));
          final collected = cycles.fold<double>(0, (s, c) => s + amountOf(c.totalCollected));
          final outstanding = cycles.fold<double>(0, (s, c) => s + amountOf(c.totalOutstanding));
          return ListView(
            padding: const EdgeInsets.fromLTRB(16, 16, 16, 96),
            children: [
              if (noCharges) ...[
                _SetupBanner(onTap: onAddChargeHeads),
                const SizedBox(height: 12),
              ],
              KpiGrid(cards: [
                KpiCard(
                  icon: Icons.account_balance_wallet_rounded,
                  label: 'Collected',
                  value: formatRupees('$collected'),
                  color: AppTheme.success,
                  note: billed > 0 ? '${(collected / billed * 100).toStringAsFixed(0)}% of billed' : null,
                ),
                KpiCard(
                  icon: Icons.pending_actions_rounded,
                  label: 'Outstanding',
                  value: formatRupees('$outstanding'),
                  color: AppTheme.warning,
                ),
              ]),
              const SizedBox(height: 16),
              if (cycles.isEmpty)
                const Padding(
                  padding: EdgeInsets.only(top: 40),
                  child: AppEmptyState(
                    icon: Icons.receipt_long_rounded,
                    title: 'No billing cycles yet',
                    subtitle: 'Create a cycle for the period you want to bill, e.g. "October 2026".',
                  ),
                )
              else
                for (final c in cycles)
                  _CycleCard(
                    cycle: c,
                    onTap: () => Navigator.push(context, MaterialPageRoute(
                      builder: (_) => BillingCycleScreen(cycleId: c.id, societyId: societyId),
                    )),
                  ),
            ],
          );
        },
      ),
    );
  }
}

class _SetupBanner extends StatelessWidget {
  final VoidCallback onTap;
  const _SetupBanner({required this.onTap});

  @override
  Widget build(BuildContext context) => Material(
        color: AppTheme.warningSoft,
        borderRadius: BorderRadius.circular(12),
        child: InkWell(
          borderRadius: BorderRadius.circular(12),
          onTap: onTap,
          child: const Padding(
            padding: EdgeInsets.all(14),
            child: Row(children: [
              Icon(Icons.info_outline_rounded, color: AppTheme.warning),
              SizedBox(width: 12),
              Expanded(
                child: Text(
                  'Add at least one charge head (e.g. Maintenance ₹2,500) before generating bills.',
                  style: TextStyle(fontSize: 13, color: AppTheme.textPrimary),
                ),
              ),
              Icon(Icons.chevron_right_rounded, color: AppTheme.textSecondary),
            ]),
          ),
        ),
      );
}

class _CycleCard extends StatelessWidget {
  final BillingCycle cycle;
  final VoidCallback onTap;
  const _CycleCard({required this.cycle, required this.onTap});

  (String, Color) get _stage {
    if (!cycle.isFinalized) return ('Bills not generated', AppTheme.textSecondary);
    if (cycle.awaitingIssue) return ('${cycle.generatedCount} to issue', AppTheme.warning);
    if (cycle.overdueCount > 0) return ('${cycle.overdueCount} overdue', AppTheme.error);
    return ('Issued', AppTheme.success);
  }

  @override
  Widget build(BuildContext context) {
    final billed = amountOf(cycle.totalBilled);
    final collected = amountOf(cycle.totalCollected);
    final progress = billed > 0 ? (collected / billed).clamp(0.0, 1.0) : 0.0;
    final (stageLabel, stageColor) = _stage;

    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      child: InkWell(
        borderRadius: BorderRadius.circular(12),
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Row(children: [
              Expanded(
                child: Text(cycle.name,
                    style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w600)),
              ),
              _Pill(label: stageLabel, color: stageColor),
            ]),
            const SizedBox(height: 4),
            Text(
              '${formatBillDate(cycle.cycleStart)} – ${formatBillDate(cycle.cycleEnd)} · Due ${formatBillDate(cycle.dueDate)}',
              style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary),
            ),
            if (cycle.isFinalized) ...[
              const SizedBox(height: 12),
              ClipRRect(
                borderRadius: BorderRadius.circular(4),
                child: LinearProgressIndicator(
                  value: progress, minHeight: 6,
                  backgroundColor: AppTheme.border,
                  color: AppTheme.success,
                ),
              ),
              const SizedBox(height: 8),
              Row(children: [
                Expanded(
                  child: Text('${formatRupees(cycle.totalCollected)} of ${formatRupees(cycle.totalBilled)}',
                      style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w500)),
                ),
                Text('${cycle.paidCount}/${cycle.billsCount} flats paid',
                    style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
              ]),
            ],
          ]),
        ),
      ),
    );
  }
}

class _Pill extends StatelessWidget {
  final String label;
  final Color color;
  const _Pill({required this.label, required this.color});

  @override
  Widget build(BuildContext context) => Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
        decoration: BoxDecoration(
          color: color.withOpacity(0.12),
          borderRadius: BorderRadius.circular(20),
        ),
        child: Text(label, style: TextStyle(fontSize: 11, fontWeight: FontWeight.w600, color: color)),
      );
}

// ── New cycle sheet ───────────────────────────────────────────────────────────

class _NewCycleSheet extends ConsumerStatefulWidget {
  final String societyId;
  const _NewCycleSheet({required this.societyId});

  @override
  ConsumerState<_NewCycleSheet> createState() => _NewCycleSheetState();
}

class _NewCycleSheetState extends ConsumerState<_NewCycleSheet> {
  final _formKey = GlobalKey<FormState>();
  late DateTime _start;
  late DateTime _end;
  late DateTime _due;
  late final TextEditingController _nameCtrl;
  bool _nameEdited = false;
  bool _saving = false;

  @override
  void initState() {
    super.initState();
    final now = DateTime.now();
    _setPeriod(DateTime(now.year, now.month, 1));
    _nameCtrl = TextEditingController(text: _defaultName);
  }

  @override
  void dispose() {
    _nameCtrl.dispose();
    super.dispose();
  }

  String get _defaultName => '${DateFormat('MMMM yyyy').format(_start)} Maintenance';

  void _setPeriod(DateTime monthStart) {
    _start = monthStart;
    _end = DateTime(monthStart.year, monthStart.month + 1, 0);
    _due = DateTime(monthStart.year, monthStart.month, 10);
  }

  Future<void> _pick(DateTime current, void Function(DateTime) apply) async {
    final picked = await showDatePicker(
      context: context,
      initialDate: current,
      firstDate: DateTime(2020),
      lastDate: DateTime(DateTime.now().year + 2, 12, 31),
    );
    if (picked != null) setState(() => apply(picked));
  }

  Future<void> _save() async {
    if (!_formKey.currentState!.validate()) return;
    if (_end.isBefore(_start)) {
      AppToast.error(context, 'End date must be on or after the start date');
      return;
    }
    setState(() => _saving = true);
    try {
      await ref.read(maintenanceBillingApiProvider).createCycle(
            societyId: widget.societyId, name: _nameCtrl.text.trim(),
            start: _start, end: _end, dueDate: _due,
          );
      ref.invalidate(billingCyclesProvider(widget.societyId));
      if (mounted) {
        AppToast.success(context, 'Cycle created — open it to generate bills');
        Navigator.pop(context);
      }
    } catch (e) {
      if (mounted) showErrorToast(context, e);
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return _SheetFrame(
      title: 'New Billing Cycle',
      child: Form(
        key: _formKey,
        child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          _DateField(
            label: 'Billing month',
            value: DateFormat('MMMM yyyy').format(_start),
            onTap: () => _pick(_start, (d) {
              _setPeriod(DateTime(d.year, d.month, 1));
              if (!_nameEdited) _nameCtrl.text = _defaultName;
            }),
          ),
          const SizedBox(height: 14),
          TextFormField(
            controller: _nameCtrl,
            decoration: const InputDecoration(labelText: 'Cycle name *'),
            onChanged: (_) => _nameEdited = true,
            validator: (v) => (v == null || v.trim().isEmpty) ? 'Required' : null,
          ),
          const SizedBox(height: 14),
          Row(children: [
            Expanded(child: _DateField(label: 'From', value: formatBillDate(_start),
                onTap: () => _pick(_start, (d) => _start = d))),
            const SizedBox(width: 12),
            Expanded(child: _DateField(label: 'To', value: formatBillDate(_end),
                onTap: () => _pick(_end, (d) => _end = d))),
          ]),
          const SizedBox(height: 14),
          _DateField(label: 'Payment due by *', value: formatBillDate(_due),
              onTap: () => _pick(_due, (d) => _due = d)),
          const SizedBox(height: 24),
          ElevatedButton(
            onPressed: _saving ? null : _save,
            child: _saving
                ? const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2))
                : const Text('Create Cycle'),
          ),
        ]),
      ),
    );
  }
}

// ── Charge heads tab ──────────────────────────────────────────────────────────

class _ChargeHeadsTab extends ConsumerWidget {
  final String societyId;
  final void Function(ChargeHead) onEdit;
  const _ChargeHeadsTab({required this.societyId, required this.onEdit});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final chargesAsync = ref.watch(chargeHeadsProvider(societyId));
    return RefreshIndicator(
      onRefresh: () async => ref.invalidate(chargeHeadsProvider(societyId)),
      child: chargesAsync.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (e, _) => ListView(children: [
          Padding(
            padding: const EdgeInsets.all(24),
            child: Text(friendlyErrorMessage(e), style: const TextStyle(color: AppTheme.error)),
          ),
        ]),
        data: (charges) {
          if (charges.isEmpty) {
            return ListView(children: const [
              SizedBox(height: 60),
              AppEmptyState(
                icon: Icons.list_alt_rounded,
                title: 'No charge heads yet',
                subtitle: 'Charge heads are the lines on every bill — maintenance, water, sinking fund…',
              ),
            ]);
          }
          final flatTotal = charges.where((c) => !c.isPerSqft).fold<double>(0, (s, c) {
            final amt = amountOf(c.defaultAmount ?? '0');
            return s + amt + amt * amountOf(c.taxPercent) / 100;
          });
          return ListView(
            padding: const EdgeInsets.fromLTRB(16, 16, 16, 96),
            children: [
              Text(
                'Every flat is billed these each cycle. Changes apply to bills generated from now on.',
                style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary),
              ),
              const SizedBox(height: 12),
              for (final c in charges)
                Card(
                  margin: const EdgeInsets.only(bottom: 10),
                  child: ListTile(
                    onTap: () => onEdit(c),
                    title: Text(c.name, style: const TextStyle(fontWeight: FontWeight.w600)),
                    subtitle: Text([
                      chargeTypeLabel(c.chargeType),
                      if (amountOf(c.taxPercent) > 0) '+${c.taxPercent}% tax',
                    ].join(' · ')),
                    trailing: Text(
                      c.isPerSqft
                          ? '${formatRupees(c.defaultAmount ?? '0')}/sq ft'
                          : formatRupees(c.defaultAmount ?? '0'),
                      style: const TextStyle(fontWeight: FontWeight.w700),
                    ),
                  ),
                ),
              const SizedBox(height: 4),
              Row(children: [
                const Expanded(
                  child: Text('Fixed charges per flat, incl. tax',
                      style: TextStyle(color: AppTheme.textSecondary)),
                ),
                Text(formatRupees('$flatTotal'),
                    style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 16)),
              ]),
            ],
          );
        },
      ),
    );
  }
}

class _ChargeHeadSheet extends ConsumerStatefulWidget {
  final String societyId;
  final ChargeHead? existing;
  const _ChargeHeadSheet({required this.societyId, this.existing});

  @override
  ConsumerState<_ChargeHeadSheet> createState() => _ChargeHeadSheetState();
}

class _ChargeHeadSheetState extends ConsumerState<_ChargeHeadSheet> {
  final _formKey = GlobalKey<FormState>();
  late final _nameCtrl = TextEditingController(text: widget.existing?.name ?? '');
  late final _amountCtrl = TextEditingController(text: widget.existing?.defaultAmount ?? '');
  late final _taxCtrl = TextEditingController(text: widget.existing?.taxPercent ?? '0');
  late String _type = widget.existing?.chargeType ?? 'maintenance';
  late bool _perSqft = widget.existing?.isPerSqft ?? false;
  bool _saving = false;

  bool get _editing => widget.existing != null;

  @override
  void dispose() {
    _nameCtrl.dispose();
    _amountCtrl.dispose();
    _taxCtrl.dispose();
    super.dispose();
  }

  String? _number(String? v, {bool required = true}) {
    if (v == null || v.trim().isEmpty) return required ? 'Required' : null;
    final n = double.tryParse(v.trim());
    if (n == null || n < 0) return 'Enter a valid amount';
    return null;
  }

  Future<void> _run(Future<void> Function() action, String message) async {
    setState(() => _saving = true);
    try {
      await action();
      ref.invalidate(chargeHeadsProvider(widget.societyId));
      if (mounted) {
        AppToast.success(context, message);
        Navigator.pop(context);
      }
    } catch (e) {
      if (mounted) showErrorToast(context, e);
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  Future<void> _save() async {
    if (!_formKey.currentState!.validate()) return;
    final api = ref.read(maintenanceBillingApiProvider);
    final name = _nameCtrl.text.trim();
    final amount = _amountCtrl.text.trim();
    final tax = _taxCtrl.text.trim().isEmpty ? '0' : _taxCtrl.text.trim();
    await _run(
      () => _editing
          ? api.updateChargeHead(widget.existing!.id, {
              'name': name, 'charge_type': _type, 'default_amount': amount,
              'tax_percent': tax, 'is_per_sqft': _perSqft,
            })
          : api.createChargeHead(
              societyId: widget.societyId, chargeType: _type, name: name,
              amount: amount, taxPercent: tax, isPerSqft: _perSqft,
            ),
      _editing ? 'Charge head updated' : 'Charge head added',
    );
  }

  Future<void> _remove() async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Remove charge head?'),
        content: Text('"${widget.existing!.name}" won\'t be added to future bills. '
            'Bills already generated keep it.'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancel')),
          TextButton(
            onPressed: () => Navigator.pop(ctx, true),
            style: TextButton.styleFrom(foregroundColor: AppTheme.error),
            child: const Text('Remove'),
          ),
        ],
      ),
    );
    if (ok != true) return;
    await _run(
      () => ref.read(maintenanceBillingApiProvider)
          .updateChargeHead(widget.existing!.id, {'is_active': false}),
      'Charge head removed',
    );
  }

  @override
  Widget build(BuildContext context) {
    return _SheetFrame(
      title: _editing ? 'Edit Charge Head' : 'Add Charge Head',
      child: Form(
        key: _formKey,
        child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          DropdownButtonFormField<String>(
            initialValue: _type,
            decoration: const InputDecoration(labelText: 'Type *'),
            items: [for (final t in kChargeTypes) DropdownMenuItem(value: t.$1, child: Text(t.$2))],
            onChanged: (v) => setState(() {
              _type = v ?? _type;
              if (_nameCtrl.text.trim().isEmpty) _nameCtrl.text = chargeTypeLabel(_type);
            }),
          ),
          const SizedBox(height: 14),
          TextFormField(
            controller: _nameCtrl,
            decoration: const InputDecoration(labelText: 'Name on bill *', hintText: 'e.g. Monthly Maintenance'),
            validator: (v) => (v == null || v.trim().isEmpty) ? 'Required' : null,
          ),
          const SizedBox(height: 14),
          TextFormField(
            controller: _amountCtrl,
            keyboardType: const TextInputType.numberWithOptions(decimal: true),
            decoration: InputDecoration(labelText: _perSqft ? 'Rate per sq ft (₹) *' : 'Amount per flat (₹) *'),
            validator: _number,
          ),
          const SizedBox(height: 4),
          SwitchListTile(
            contentPadding: EdgeInsets.zero,
            title: const Text('Charge by flat area'),
            subtitle: const Text('Amount × the flat\'s area in sq ft'),
            value: _perSqft,
            onChanged: (v) => setState(() => _perSqft = v),
          ),
          const SizedBox(height: 4),
          TextFormField(
            controller: _taxCtrl,
            keyboardType: const TextInputType.numberWithOptions(decimal: true),
            decoration: const InputDecoration(labelText: 'Tax / GST %', hintText: '0'),
            validator: (v) => _number(v, required: false),
          ),
          const SizedBox(height: 24),
          ElevatedButton(
            onPressed: _saving ? null : _save,
            child: _saving
                ? const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2))
                : Text(_editing ? 'Save Changes' : 'Add Charge Head'),
          ),
          if (_editing) ...[
            const SizedBox(height: 8),
            TextButton.icon(
              onPressed: _saving ? null : _remove,
              style: TextButton.styleFrom(foregroundColor: AppTheme.error),
              icon: const Icon(Icons.delete_outline_rounded),
              label: const Text('Remove Charge Head'),
            ),
          ],
        ]),
      ),
    );
  }
}

// ── Shared sheet pieces ───────────────────────────────────────────────────────

class _SheetFrame extends StatelessWidget {
  final String title;
  final Widget child;
  const _SheetFrame({required this.title, required this.child});

  @override
  Widget build(BuildContext context) => Container(
        decoration: const BoxDecoration(
          color: AppTheme.cardBg,
          borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
        ),
        padding: EdgeInsets.only(
          left: 20, right: 20, top: 20,
          bottom: MediaQuery.of(context).viewInsets.bottom + 20,
        ),
        child: SafeArea(
          top: false,
          child: SingleChildScrollView(
            child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, mainAxisSize: MainAxisSize.min, children: [
              Text(title, style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w700)),
              const SizedBox(height: 16),
              child,
            ]),
          ),
        ),
      );
}

class _DateField extends StatelessWidget {
  final String label;
  final String value;
  final VoidCallback onTap;
  const _DateField({required this.label, required this.value, required this.onTap});

  @override
  Widget build(BuildContext context) => InkWell(
        onTap: onTap,
        child: InputDecorator(
          decoration: InputDecoration(
            labelText: label,
            suffixIcon: const Icon(Icons.calendar_today_rounded, size: 18),
          ),
          child: Text(value),
        ),
      );
}
