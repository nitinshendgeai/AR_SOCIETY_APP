import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/router/app_router.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/features/maintenance_billing/data/maintenance_billing_api.dart';
import 'package:ar_society_app/features/maintenance_billing/presentation/providers/maintenance_billing_providers.dart';
import 'package:ar_society_app/features/maintenance_billing/presentation/screens/billing_cycle_screen.dart';
import 'package:ar_society_app/features/maintenance_billing/presentation/widgets/billing_sheet_frame.dart';
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
  late final TabController _tabs = TabController(length: 3, vsync: this)
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
    final onRules = _tabs.index == 2;

    return Scaffold(
      backgroundColor: AppTheme.surface,
      appBar: AppBar(
        title: const Text('Maintenance Billing'),
        bottom: TabBar(controller: _tabs, tabs: const [
          Tab(text: 'Cycles'),
          Tab(text: 'Charge Heads'),
          Tab(text: 'Rules'),
        ]),
      ),
      floatingActionButton: onRules ? null : FloatingActionButton.extended(
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
        _RulesTab(societyId: societyId),
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
    return BillingSheetFrame(
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
          void loadStandard() => showModalBottomSheet(
                context: context, isScrollControlled: true, backgroundColor: Colors.transparent,
                builder: (_) => _LoadFromElementsSheet(societyId: societyId, existing: charges),
              );
          final canManageElements = ref.watch(currentUserProvider)?.isAdminOrCommittee ?? false;
          final actions = Wrap(spacing: 8, children: [
            OutlinedButton.icon(
              onPressed: loadStandard,
              icon: const Icon(Icons.playlist_add_rounded, size: 18),
              label: const Text('Add from elements'),
            ),
            if (canManageElements)
              TextButton.icon(
                onPressed: () => context.push(AppRoutes.maintenanceElements),
                icon: const Icon(Icons.tune_rounded, size: 18),
                label: const Text('Manage elements'),
              ),
          ]);
          if (charges.isEmpty) {
            return ListView(children: [
              const SizedBox(height: 60),
              AppEmptyState(
                icon: Icons.list_alt_rounded,
                title: 'No charge heads yet',
                subtitle: 'Start from the standard bye-law elements — service charges, sinking fund, '
                    'repair fund, property tax… — and just fill in your amounts.',
                actionLabel: 'Load standard charge heads',
                onAction: loadStandard,
              ),
              if (canManageElements)
                Center(
                  child: TextButton(
                    onPressed: () => context.push(AppRoutes.maintenanceElements),
                    child: const Text('Manage maintenance elements'),
                  ),
                ),
            ]);
          }
          return ListView(
            padding: const EdgeInsets.fromLTRB(16, 16, 16, 96),
            children: [
              actions,
              const SizedBox(height: 8),
              const Text(
                'Each flat\'s bill is worked out from these every cycle. Changes apply to '
                'bills generated from now on — preview a cycle to see exact amounts.',
                style: TextStyle(fontSize: 12, color: AppTheme.textSecondary),
              ),
              const SizedBox(height: 12),
              for (final c in charges)
                Card(
                  margin: const EdgeInsets.only(bottom: 10),
                  child: ListTile(
                    onTap: () => onEdit(c),
                    title: Text(c.name, style: const TextStyle(fontWeight: FontWeight.w600)),
                    subtitle: Text([
                      c.rateLabel,
                      if (c.isServiceCharge) 'Service charge',
                      if (!c.gstApplicable) 'No GST',
                    ].join(' · ')),
                    trailing: const Icon(Icons.chevron_right_rounded),
                  ),
                ),
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
  late String _basis = widget.existing?.basis ?? 'fixed';
  late bool _service = widget.existing?.isServiceCharge ?? true;
  late bool _gst = widget.existing?.gstApplicable ?? true;
  late String? _elementId = widget.existing?.elementId;
  bool _saving = false;

  bool get _editing => widget.existing != null;

  void _applyElement(MaintenanceElement el) {
    _elementId = el.id;
    _type = el.category;
    _nameCtrl.text = el.name;
    _basis = el.defaultBasis;
    _amountCtrl.text = el.defaultAmount ?? '';
    _service = el.isServiceCharge;
    _gst = el.gstApplicable;
  }

  @override
  void dispose() {
    _nameCtrl.dispose();
    _amountCtrl.dispose();
    _taxCtrl.dispose();
    super.dispose();
  }

  /// Picking a type pre-fills the usual bye-law basis/rate for it.
  void _onTypeChanged(String type) {
    _type = type;
    if (_nameCtrl.text.trim().isEmpty || !_editing) _nameCtrl.text = chargeTypeLabel(type);
    if (_editing) return;
    _service = type == 'maintenance';
    switch (type) {
      case 'sinking_fund':
        _basis = 'construction_cost_pct';
        _amountCtrl.text = '0.25';
      case 'repair_fund':
        _basis = 'construction_cost_pct';
        _amountCtrl.text = '0.75';
      case 'parking':
        _basis = 'parking';
      default:
        break;
    }
  }

  String? _number(String? v, {bool required = true}) {
    if (v == null || v.trim().isEmpty) return required ? 'Required' : null;
    final n = double.tryParse(v.trim());
    if (n == null || n < 0) return 'Enter a valid amount';
    if (_basis == 'construction_cost_pct' && required && n > 100) return 'Enter a percentage';
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
              'name': name, 'charge_type': _type, 'default_amount': amount, 'basis': _basis,
              'is_service_charge': _service, 'gst_applicable': _gst, 'tax_percent': tax,
            })
          : api.createChargeHead(
              societyId: widget.societyId, elementId: _elementId,
              chargeType: _type, name: name, amount: amount,
              basis: _basis, isServiceCharge: _service, gstApplicable: _gst, taxPercent: tax,
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
    final gstFromRules =
        ref.watch(maintenanceRulesProvider(widget.societyId)).valueOrNull?.gstEnabled ?? false;
    return BillingSheetFrame(
      title: _editing ? 'Edit Charge Head' : 'Add Charge Head',
      child: Form(
        key: _formKey,
        child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          if (!_editing) ...[
            ref.watch(maintenanceElementsProvider((societyId: widget.societyId, includeInactive: false))).when(
                  loading: () => const LinearProgressIndicator(),
                  error: (e, _) => Text(friendlyErrorMessage(e), style: const TextStyle(color: AppTheme.error)),
                  data: (elements) => DropdownButtonFormField<String>(
                    initialValue: _elementId,
                    isExpanded: true,
                    decoration: const InputDecoration(
                      labelText: 'Start from element',
                      helperText: 'Fills in the defaults below — you can still change them',
                    ),
                    items: [
                      for (final el in elements) DropdownMenuItem(value: el.id, child: Text(el.name)),
                    ],
                    onChanged: (id) => setState(() {
                      final el = elements.where((e) => e.id == id).firstOrNull;
                      if (el != null) _applyElement(el);
                    }),
                  ),
                ),
            const SizedBox(height: 14),
          ] else if (widget.existing!.elementName != null) ...[
            Text('Element: ${widget.existing!.elementName}',
                style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
            const SizedBox(height: 14),
          ],
          DropdownButtonFormField<String>(
            key: ValueKey('type-$_type'),
            initialValue: _type,
            decoration: const InputDecoration(labelText: 'Type *'),
            items: [for (final t in kChargeTypes) DropdownMenuItem(value: t.$1, child: Text(t.$2))],
            onChanged: (v) => setState(() => _onTypeChanged(v ?? _type)),
          ),
          const SizedBox(height: 14),
          TextFormField(
            controller: _nameCtrl,
            decoration: const InputDecoration(labelText: 'Name on bill *', hintText: 'e.g. Service Charges'),
            validator: (v) => (v == null || v.trim().isEmpty) ? 'Required' : null,
          ),
          const SizedBox(height: 14),
          DropdownButtonFormField<String>(
            key: ValueKey('basis-$_basis'),
            initialValue: _basis,
            isExpanded: true,
            decoration: const InputDecoration(labelText: 'How is it calculated? *'),
            items: [for (final b in kChargeBases) DropdownMenuItem(value: b.$1, child: Text(b.$2))],
            onChanged: (v) => setState(() => _basis = v ?? _basis),
          ),
          const SizedBox(height: 6),
          Text(chargeBasisHint(_basis),
              style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
          const SizedBox(height: 14),
          TextFormField(
            controller: _amountCtrl,
            keyboardType: const TextInputType.numberWithOptions(decimal: true),
            decoration: InputDecoration(labelText: '${chargeAmountFieldLabel(_basis)} *'),
            validator: _number,
          ),
          const SizedBox(height: 4),
          SwitchListTile(
            contentPadding: EdgeInsets.zero,
            title: const Text('Service charge'),
            subtitle: const Text('Non-occupancy charges for let-out flats are a % of these'),
            value: _service,
            onChanged: (v) => setState(() => _service = v),
          ),
          if (gstFromRules)
            SwitchListTile(
              contentPadding: EdgeInsets.zero,
              title: const Text('GST applicable'),
              subtitle: const Text('Included when checking the monthly GST threshold'),
              value: _gst,
              onChanged: (v) => setState(() => _gst = v),
            )
          else
            TextFormField(
              controller: _taxCtrl,
              keyboardType: const TextInputType.numberWithOptions(decimal: true),
              decoration: const InputDecoration(
                labelText: 'Tax %',
                hintText: '0',
                helperText: 'Or turn on GST in Rules to apply the ₹7,500 threshold automatically',
              ),
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

// ── Load charge heads from elements ───────────────────────────────────────────

class _LoadFromElementsSheet extends ConsumerStatefulWidget {
  final String societyId;
  final List<ChargeHead> existing;
  const _LoadFromElementsSheet({required this.societyId, required this.existing});

  @override
  ConsumerState<_LoadFromElementsSheet> createState() => _LoadFromElementsSheetState();
}

class _LoadFromElementsSheetState extends ConsumerState<_LoadFromElementsSheet> {
  // The bye-law minimum set is pre-ticked.
  static const _preselected = {'service_charges', 'repair_fund', 'sinking_fund'};
  final Set<String> _selected = {};
  final Map<String, TextEditingController> _amounts = {};
  bool _initialised = false;
  bool _saving = false;

  @override
  void dispose() {
    for (final c in _amounts.values) {
      c.dispose();
    }
    super.dispose();
  }

  TextEditingController _ctrl(MaintenanceElement el) =>
      _amounts.putIfAbsent(el.id, () => TextEditingController(text: el.defaultAmount ?? ''));

  Future<void> _save(List<MaintenanceElement> elements) async {
    final chosen = elements.where((e) => _selected.contains(e.id)).toList();
    final missing = chosen.where((e) => _ctrl(e).text.trim().isEmpty).map((e) => e.name).toList();
    if (chosen.isEmpty) {
      AppToast.warning(context, 'Tick at least one element');
      return;
    }
    if (missing.isNotEmpty) {
      AppToast.error(context, 'Enter an amount for: ${missing.join(', ')}');
      return;
    }
    if (chosen.any((e) => double.tryParse(_ctrl(e).text.trim()) == null)) {
      AppToast.error(context, 'Amounts must be numbers');
      return;
    }
    setState(() => _saving = true);
    try {
      final created = await ref.read(maintenanceBillingApiProvider).createChargesFromElements(
            widget.societyId, [for (final e in chosen) (e.id, _ctrl(e).text.trim())]);
      ref.invalidate(chargeHeadsProvider(widget.societyId));
      if (mounted) {
        AppToast.success(context, '${created.length} charge head${created.length == 1 ? '' : 's'} added');
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
    final inUse = {for (final c in widget.existing) if (c.elementId != null) c.elementId!};
    final elementsAsync =
        ref.watch(maintenanceElementsProvider((societyId: widget.societyId, includeInactive: false)));
    return BillingSheetFrame(
      title: 'Add Charge Heads from Elements',
      child: elementsAsync.when(
        loading: () => const Padding(
          padding: EdgeInsets.all(24),
          child: Center(child: CircularProgressIndicator()),
        ),
        error: (e, _) => Text(friendlyErrorMessage(e), style: const TextStyle(color: AppTheme.error)),
        data: (elements) {
          if (!_initialised) {
            _initialised = true;
            _selected.addAll(elements
                .where((e) => _preselected.contains(e.code) && !inUse.contains(e.id))
                .map((e) => e.id));
          }
          return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
            const Text(
              'Tick the elements your society charges and enter each amount. '
              'Sinking and repair fund rates follow the bye-laws — set the construction cost in Rules.',
              style: TextStyle(fontSize: 12, color: AppTheme.textSecondary),
            ),
            const SizedBox(height: 8),
            for (final el in elements)
              _ElementPickRow(
                element: el,
                added: inUse.contains(el.id),
                selected: _selected.contains(el.id),
                amountCtrl: _ctrl(el),
                onChanged: (v) => setState(() => v ? _selected.add(el.id) : _selected.remove(el.id)),
              ),
            const SizedBox(height: 16),
            ElevatedButton(
              onPressed: _saving ? null : () => _save(elements),
              child: _saving
                  ? const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2))
                  : Text('Add ${_selected.length} Charge Head${_selected.length == 1 ? '' : 's'}'),
            ),
          ]);
        },
      ),
    );
  }
}

class _ElementPickRow extends StatelessWidget {
  final MaintenanceElement element;
  final bool added;
  final bool selected;
  final TextEditingController amountCtrl;
  final ValueChanged<bool> onChanged;
  const _ElementPickRow({
    required this.element,
    required this.added,
    required this.selected,
    required this.amountCtrl,
    required this.onChanged,
  });

  @override
  Widget build(BuildContext context) {
    return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      CheckboxListTile(
        contentPadding: EdgeInsets.zero,
        controlAffinity: ListTileControlAffinity.leading,
        value: added || selected,
        onChanged: added ? null : (v) => onChanged(v ?? false),
        title: Text(element.name, style: const TextStyle(fontWeight: FontWeight.w600)),
        subtitle: Text(added ? 'Already added' : chargeBasisLabel(element.defaultBasis),
            style: const TextStyle(fontSize: 12)),
      ),
      if (selected && !added)
        Padding(
          padding: const EdgeInsets.only(left: 48, bottom: 8),
          child: TextField(
            controller: amountCtrl,
            keyboardType: const TextInputType.numberWithOptions(decimal: true),
            decoration: InputDecoration(labelText: chargeAmountFieldLabel(element.defaultBasis), isDense: true),
          ),
        ),
    ]);
  }
}

// ── Rules tab ─────────────────────────────────────────────────────────────────

class _RulesTab extends ConsumerWidget {
  final String societyId;
  const _RulesTab({required this.societyId});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return ref.watch(maintenanceRulesProvider(societyId)).when(
          loading: () => const Center(child: CircularProgressIndicator()),
          error: (e, _) => Center(
              child: Text(friendlyErrorMessage(e), style: const TextStyle(color: AppTheme.error))),
          data: (rules) => _RulesForm(societyId: societyId, rules: rules),
        );
  }
}

class _RulesForm extends ConsumerStatefulWidget {
  final String societyId;
  final MaintenanceRules rules;
  const _RulesForm({required this.societyId, required this.rules});

  @override
  ConsumerState<_RulesForm> createState() => _RulesFormState();
}

class _RulesFormState extends ConsumerState<_RulesForm> {
  final _formKey = GlobalKey<FormState>();
  late final _costCtrl = TextEditingController(text: widget.rules.constructionCostPerSqft ?? '');
  late final _interestCtrl = TextEditingController(text: _trim(widget.rules.interestRatePct));
  late final _graceCtrl = TextEditingController(text: '${widget.rules.interestGraceDays}');
  late final _nocCtrl = TextEditingController(text: _trim(widget.rules.nonOccupancyPct));
  late final _gstRateCtrl = TextEditingController(text: _trim(widget.rules.gstRatePct));
  late final _gstThresholdCtrl = TextEditingController(text: _trim(widget.rules.gstThresholdMonthly));
  late bool _gst = widget.rules.gstEnabled;
  bool _saving = false;

  static String _trim(String v) {
    final d = double.tryParse(v);
    if (d == null) return v;
    return d == d.roundToDouble() ? d.toStringAsFixed(0) : '$d';
  }

  @override
  void dispose() {
    for (final c in [_costCtrl, _interestCtrl, _graceCtrl, _nocCtrl, _gstRateCtrl, _gstThresholdCtrl]) {
      c.dispose();
    }
    super.dispose();
  }

  String? Function(String?) _range(double max, {bool required = true}) => (v) {
        if (v == null || v.trim().isEmpty) return required ? 'Required' : null;
        final n = double.tryParse(v.trim());
        if (n == null || n < 0) return 'Enter a valid number';
        if (n > max) return 'Maximum is ${_trim('$max')}';
        return null;
      };

  Future<void> _save() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() => _saving = true);
    try {
      final cost = _costCtrl.text.trim();
      await ref.read(maintenanceBillingApiProvider).updateRules(widget.societyId, {
        'construction_cost_per_sqft': cost.isEmpty ? null : cost,
        'interest_rate_pct': _interestCtrl.text.trim(),
        'interest_grace_days': int.parse(_graceCtrl.text.trim()),
        'non_occupancy_pct': _nocCtrl.text.trim(),
        'gst_enabled': _gst,
        'gst_rate_pct': _gstRateCtrl.text.trim(),
        'gst_threshold_monthly': _gstThresholdCtrl.text.trim(),
      });
      ref.invalidate(maintenanceRulesProvider(widget.societyId));
      if (mounted) AppToast.success(context, 'Rules saved — they apply to bills generated from now on');
    } catch (e) {
      if (mounted) showErrorToast(context, e);
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  Widget _section(String title, String help, List<Widget> fields) => Container(
        margin: const EdgeInsets.only(bottom: 14),
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: AppTheme.cardBg,
          borderRadius: BorderRadius.circular(16),
          boxShadow: AppTheme.cardShadow,
        ),
        child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          Text(title, style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w700)),
          const SizedBox(height: 4),
          Text(help, style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
          const SizedBox(height: 12),
          ...fields,
        ]),
      );

  @override
  Widget build(BuildContext context) {
    const number = TextInputType.numberWithOptions(decimal: true);
    return Form(
      key: _formKey,
      child: ListView(
        padding: const EdgeInsets.fromLTRB(16, 16, 16, 32),
        children: [
          _section(
            'Construction cost',
            'Architect-certified construction cost per sq ft, excluding land. Used for '
                'charge heads calculated as a % of construction cost (sinking fund, repair fund).',
            [
              TextFormField(
                controller: _costCtrl,
                keyboardType: number,
                decoration: const InputDecoration(labelText: 'Construction cost per sq ft (₹)'),
                validator: _range(1e7, required: false),
              ),
            ],
          ),
          _section(
            'Interest on late payment',
            'Simple interest on unpaid bills, from the due date until paid, added to the next bill. '
                'Maharashtra caps it at 12% p.a. (2026 amendment); older bye-laws allowed 21%.',
            [
              TextFormField(
                controller: _interestCtrl,
                keyboardType: number,
                decoration: const InputDecoration(labelText: 'Interest rate (% per year)'),
                validator: _range(21),
              ),
              const SizedBox(height: 12),
              TextFormField(
                controller: _graceCtrl,
                keyboardType: TextInputType.number,
                decoration: const InputDecoration(labelText: 'Grace period after due date (days)'),
                validator: (v) {
                  final base = _range(90)(v);
                  if (base != null) return base;
                  return int.tryParse(v!.trim()) == null ? 'Whole days only' : null;
                },
              ),
            ],
          ),
          _section(
            'Non-occupancy charges',
            'Extra charge for flats marked Tenant occupied, as a % of service charges only. '
                'Capped at 10% by law. Set 0 to turn off.',
            [
              TextFormField(
                controller: _nocCtrl,
                keyboardType: number,
                decoration: const InputDecoration(labelText: 'Non-occupancy (% of service charges)'),
                validator: _range(10),
              ),
            ],
          ),
          _section(
            'GST',
            'Turn on only if the society is GST-registered (annual turnover above ₹20 lakh). '
                'GST then applies to the whole bill once a flat\'s monthly maintenance crosses the '
                'threshold — nothing below it.',
            [
              SwitchListTile(
                contentPadding: EdgeInsets.zero,
                title: const Text('Society is GST-registered'),
                value: _gst,
                onChanged: (v) => setState(() => _gst = v),
              ),
              if (_gst) ...[
                TextFormField(
                  controller: _gstRateCtrl,
                  keyboardType: number,
                  decoration: const InputDecoration(labelText: 'GST rate (%)'),
                  validator: _range(28),
                ),
                const SizedBox(height: 12),
                TextFormField(
                  controller: _gstThresholdCtrl,
                  keyboardType: number,
                  decoration: const InputDecoration(labelText: 'Monthly threshold per flat (₹)'),
                  validator: _range(1e7),
                ),
              ],
            ],
          ),
          ElevatedButton(
            onPressed: _saving ? null : _save,
            child: _saving
                ? const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2))
                : const Text('Save Rules'),
          ),
        ],
      ),
    );
  }
}

// ── Shared sheet pieces ───────────────────────────────────────────────────────

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
