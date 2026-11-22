import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/motion/loading.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/features/maintenance_billing/data/maintenance_billing_api.dart';
import 'package:ar_society_app/features/maintenance_billing/presentation/providers/maintenance_billing_providers.dart'
    show maintenanceBillingApiProvider;
import 'package:ar_society_app/features/staff/presentation/widgets/staff_widgets.dart' show AppCard, EmptyState;
import 'package:ar_society_app/shared/widgets/app_widgets.dart';

/// The common areas a society usually has to maintain, offered as quick additions.
const commonAreas = ['Refuse Area', 'Gym', 'Podium', 'Club house', 'Office'];

class _Line {
  final int id;
  final TextEditingController name;
  final TextEditingController amount;
  String split = 'area';
  _Line(this.id, {String name = '', String amount = ''})
      : name = TextEditingController(text: name),
        amount = TextEditingController(text: amount);

  void dispose() {
    name.dispose();
    amount.dispose();
  }
}

/// A budget planner: list what the society needs each month (its elements and common areas such as the Refuse Area,
/// Gym, Podium, Club house and Office), and see the total, the rate per sq ft, and what each flat would pay for its
/// own area (or an equal share, per line). Nothing is saved.
class BillPlannerPanel extends ConsumerStatefulWidget {
  /// What the charge heads bill now, per element, to start a plan from.
  final List<EstimateElement> current;
  const BillPlannerPanel({super.key, this.current = const []});

  @override
  ConsumerState<BillPlannerPanel> createState() => _BillPlannerPanelState();
}

class _BillPlannerPanelState extends ConsumerState<BillPlannerPanel> {
  final List<_Line> _lines = [];
  int _next = 0;
  bool _compare = true;
  bool _loading = false;
  BillPlan? _plan;
  Object? _error;
  String _search = '';

  @override
  void initState() {
    super.initState();
    _lines.add(_Line(_next++));
  }

  @override
  void dispose() {
    for (final l in _lines) {
      l.dispose();
    }
    super.dispose();
  }

  void _add({String name = '', String amount = ''}) => setState(() => _lines.add(_Line(_next++, name: name, amount: amount)));

  void _addCommon(String name) {
    if (_lines.any((l) => l.name.text.trim().toLowerCase() == name.toLowerCase())) return;
    // an empty first line is filled rather than left behind
    final empty = _lines.where((l) => l.name.text.trim().isEmpty && l.amount.text.trim().isEmpty);
    if (empty.isNotEmpty) {
      setState(() => empty.first.name.text = name);
    } else {
      _add(name: name);
    }
  }

  void _remove(_Line l) {
    setState(() {
      _lines.remove(l);
      if (_lines.isEmpty) _lines.add(_Line(_next++));
    });
    WidgetsBinding.instance.addPostFrameCallback((_) => l.dispose()); // once its fields have left the screen
  }

  void _fromCurrent() {
    final old = [..._lines];
    WidgetsBinding.instance.addPostFrameCallback((_) {
      for (final l in old) {
        l.dispose();
      }
    });
    setState(() {
      _lines
        ..clear()
        ..addAll([
          for (final e in widget.current)
            if (amountOf(e.currentTotal) > 0) _Line(_next++, name: e.element, amount: e.currentTotal)
        ]);
      if (_lines.isEmpty) _lines.add(_Line(_next++));
    });
  }

  Future<void> _calculate() async {
    final societyId = ref.read(currentUserProvider)?.societyId;
    if (societyId == null) return;
    final inputs = <PlanLineInput>[];
    for (final l in _lines) {
      final name = l.name.text.trim();
      final raw = l.amount.text.trim();
      if (name.isEmpty && raw.isEmpty) continue;
      final amount = double.tryParse(raw.replaceAll(',', ''));
      if (name.isEmpty || amount == null || amount < 0) {
        AppToast.warning(context, 'Give each line a name and a monthly amount');
        return;
      }
      inputs.add(PlanLineInput(name, amount, split: l.split));
    }
    if (inputs.isEmpty) {
      AppToast.warning(context, 'Add at least one element or common area with its monthly amount');
      return;
    }
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final p = await ref.read(maintenanceBillingApiProvider).planMaintenance(societyId, inputs, compare: _compare);
      if (!mounted) return;
      setState(() {
        _plan = p;
        _loading = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _error = e;
        _loading = false;
      });
    }
  }

  static String _rate(String? v) => v == null ? '—' : '₹$v / sq ft';

  @override
  Widget build(BuildContext context) {
    final p = _plan;
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      _editor(),
      const SizedBox(height: 14),
      if (_error != null)
        Padding(
          padding: const EdgeInsets.only(bottom: 8),
          child: Text(friendlyErrorMessage(_error!), style: const TextStyle(color: AppTheme.error)),
        ),
      if (_loading && p == null)
        const Padding(padding: EdgeInsets.only(top: 40), child: AppLoader())
      else if (p != null) ...[
        _summary(p),
        const SizedBox(height: 14),
        _lineTotals(p),
        const SizedBox(height: 14),
        _flats(p),
        const SizedBox(height: 12),
        for (final n in p.notes)
          Padding(
            padding: const EdgeInsets.only(top: 2),
            child: Text(n, style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
          ),
      ],
    ]);
  }

  Widget _editor() => AppCard(
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          const Text('Monthly budget', style: TextStyle(fontSize: 14, fontWeight: FontWeight.w700)),
          const SizedBox(height: 2),
          const Text(
              'List what the society needs each month: its elements and common areas. Each line is shared by flat '
              'area (a flat pays its area x the rate) or equally between all flats. Then Calculate.',
              style: TextStyle(fontSize: 12, color: AppTheme.textSecondary, height: 1.4)),
          const SizedBox(height: 10),
          Wrap(spacing: 8, runSpacing: 8, children: [
            for (final c in commonAreas)
              ActionChip(
                key: ValueKey('plan-common-$c'),
                avatar: const Icon(Icons.add_rounded, size: 16),
                label: Text(c),
                onPressed: () => _addCommon(c),
              ),
            if (widget.current.isNotEmpty)
              ActionChip(
                key: const ValueKey('plan-from-current'),
                avatar: const Icon(Icons.download_rounded, size: 16),
                label: const Text('Start from current elements'),
                onPressed: _fromCurrent,
              ),
          ]),
          const SizedBox(height: 12),
          for (final l in _lines) ...[_lineEditor(l), const SizedBox(height: 10)],
          Row(children: [
            TextButton.icon(
              key: const ValueKey('plan-add'),
              onPressed: _add,
              icon: const Icon(Icons.add_rounded, size: 18),
              label: const Text('Add line'),
            ),
            const Spacer(),
            const Text('Compare with current bills', style: TextStyle(fontSize: 12.5)),
            Switch(
              key: const ValueKey('plan-compare'),
              value: _compare,
              onChanged: (v) => setState(() => _compare = v),
            ),
          ]),
          const SizedBox(height: 4),
          SizedBox(
            width: double.infinity,
            child: FilledButton.icon(
              key: const ValueKey('plan-calc'),
              onPressed: _loading ? null : _calculate,
              icon: _loading
                  ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2))
                  : const Icon(Icons.calculate_outlined, size: 18),
              label: const Text('Calculate'),
            ),
          ),
        ]),
      );

  Widget _lineEditor(_Line l) => Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Expanded(
            flex: 3,
            child: TextField(
              key: ValueKey('plan-name-${l.id}'),
              controller: l.name,
              textCapitalization: TextCapitalization.words,
              decoration: const InputDecoration(labelText: 'Element or common area', isDense: true),
            ),
          ),
          const SizedBox(width: 10),
          Expanded(
            flex: 2,
            child: TextField(
              key: ValueKey('plan-amount-${l.id}'),
              controller: l.amount,
              keyboardType: const TextInputType.numberWithOptions(decimal: true),
              inputFormatters: [FilteringTextInputFormatter.allow(RegExp(r'[0-9.,]'))],
              decoration: const InputDecoration(labelText: 'Monthly ₹', isDense: true),
            ),
          ),
          IconButton(
            key: ValueKey('plan-remove-${l.id}'),
            tooltip: 'Remove',
            icon: const Icon(Icons.close_rounded, size: 18),
            onPressed: () => _remove(l),
          ),
        ]),
        const SizedBox(height: 6),
        SegmentedButton<String>(
          key: ValueKey('plan-split-${l.id}'),
          segments: const [
            ButtonSegment(value: 'area', label: Text('By flat area')),
            ButtonSegment(value: 'equal', label: Text('Equal per flat')),
          ],
          selected: {l.split},
          showSelectedIcon: false,
          style: const ButtonStyle(visualDensity: VisualDensity.compact),
          onSelectionChanged: (s) => setState(() => l.split = s.first),
        ),
      ]);

  Widget _summary(BillPlan p) => AppCard(
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          const Text('Total the society needs each month', style: TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
          Text(formatRupees(p.total), key: const ValueKey('plan-total'), style: const TextStyle(fontSize: 24, fontWeight: FontWeight.w700)),
          const SizedBox(height: 6),
          Text('Rate by area: ${_rate(p.ratePerSqft)}', key: const ValueKey('plan-rate'),
              style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600)),
          if (amountOf(p.perFlatEqual) > 0)
            Text('Plus an equal share: ${formatRupees(p.perFlatEqual)} per flat', style: const TextStyle(fontSize: 13)),
          Text('${p.flatsCount} flats · ${p.areaTotalSqft.toStringAsFixed(0)} sq ft · average ${_rate(p.averagePerSqft)}',
              style: const TextStyle(fontSize: 13, color: AppTheme.textSecondary)),
          if (p.compared && p.currentTotal != null) ...[
            const SizedBox(height: 8),
            Text('Charge heads now (${p.monthLabel}): ${formatRupees(p.currentTotal!)}', style: const TextStyle(fontSize: 13)),
            Text(
                'Difference: ${amountOf(p.changeTotal ?? '0') > 0 ? '+' : ''}${formatRupees(p.changeTotal ?? '0')} a month',
                style: TextStyle(
                    fontSize: 13,
                    fontWeight: FontWeight.w600,
                    color: amountOf(p.changeTotal ?? '0') > 0 ? AppTheme.warning : AppTheme.success)),
          ],
        ]),
      );

  Widget _lineTotals(BillPlan p) => AppCard(
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          const Text('Each line', style: TextStyle(fontSize: 14, fontWeight: FontWeight.w700)),
          const SizedBox(height: 6),
          for (final l in p.lines) ...[
            Row(children: [
              Expanded(child: Text(l.name, style: const TextStyle(fontWeight: FontWeight.w600))),
              Text(formatRupees(l.amount), style: const TextStyle(fontWeight: FontWeight.w700)),
            ]),
            Text(
                l.split == 'area'
                    ? 'By area: ${l.ratePerSqft == null ? '—' : '₹${l.ratePerSqft} / sq ft'}'
                    : 'Equal: ${formatRupees(l.perFlat ?? '0')} per flat',
                style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
            const SizedBox(height: 8),
          ],
        ]),
      );

  Widget _flats(BillPlan p) {
    final q = _search.toLowerCase();
    final shown = [for (final f in p.flats) if (q.isEmpty || f.flatLabel.toLowerCase().contains(q)) f];
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Text('Each flat (${p.flats.length})', style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w700)),
      const SizedBox(height: 8),
      TextField(
        key: const ValueKey('plan-search'),
        onChanged: (v) => setState(() => _search = v.trim()),
        decoration: const InputDecoration(prefixIcon: Icon(Icons.search_rounded), hintText: 'Search a flat'),
      ),
      const SizedBox(height: 8),
      if (shown.isEmpty)
        const Padding(
          padding: EdgeInsets.only(top: 24),
          child: EmptyState(icon: Icons.apartment_rounded, title: 'No flats to show', subtitle: 'Nothing matches.'),
        )
      else
        for (final f in shown) _PlanFlatTile(flat: f, compared: p.compared),
    ]);
  }
}

class _PlanFlatTile extends StatelessWidget {
  final PlanFlat flat;
  final bool compared;
  const _PlanFlatTile({required this.flat, required this.compared});

  @override
  Widget build(BuildContext context) {
    final change = amountOf(flat.change ?? '0');
    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      child: ExpansionTile(
        key: ValueKey('plan-flat-${flat.flatLabel}'),
        shape: const Border(),
        title: Text(flat.flatLabel, style: const TextStyle(fontWeight: FontWeight.w700)),
        subtitle: Text(
            [
              if (flat.areaSqft != null) '${flat.areaSqft!.toStringAsFixed(0)} sq ft',
              if (flat.perSqft != null) '₹${flat.perSqft} / sq ft',
            ].join(' · '),
            style: const TextStyle(fontSize: 12.5)),
        trailing: Column(mainAxisAlignment: MainAxisAlignment.center, crossAxisAlignment: CrossAxisAlignment.end, children: [
          Text(formatRupees(flat.total), style: const TextStyle(fontWeight: FontWeight.w700)),
          if (compared && change != 0)
            Text('${change > 0 ? '+' : ''}${formatRupees(flat.change!)}',
                style: TextStyle(fontSize: 11.5, color: change > 0 ? AppTheme.warning : AppTheme.success)),
        ]),
        childrenPadding: const EdgeInsets.fromLTRB(16, 0, 16, 12),
        children: [
          for (final s in flat.shares)
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 3),
              child: Row(children: [
                Expanded(child: Text(s.name, style: const TextStyle(fontSize: 13))),
                Text(formatRupees(s.amount), style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w500)),
              ]),
            ),
          const Divider(height: 14),
          _row('Maintenance for the month', flat.total, bold: true),
          if (compared && flat.current != null) _row('Charge heads now', flat.current!),
        ],
      ),
    );
  }

  static Widget _row(String label, String value, {bool bold = false}) => Padding(
        padding: const EdgeInsets.symmetric(vertical: 3),
        child: Row(children: [
          Expanded(child: Text(label, style: TextStyle(fontSize: 13, fontWeight: bold ? FontWeight.w700 : FontWeight.w400))),
          Text(formatRupees(value), style: TextStyle(fontSize: 13, fontWeight: bold ? FontWeight.w700 : FontWeight.w500)),
        ]),
      );
}
