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

const _periodWords = <String, String>{'month': 'Per month', 'quarter': 'Per quarter', 'year': 'Per year'};

class _Line {
  final int id;
  final TextEditingController name;
  final TextEditingController amount;
  String split = 'area';
  String period = 'month';
  _Line(this.id, {String name = '', String amount = ''})
      : name = TextEditingController(text: name),
        amount = TextEditingController(text: amount);

  void dispose() {
    name.dispose();
    amount.dispose();
  }
}

/// A budget planner: list what the society needs (its elements and common areas such as the Refuse Area, Gym, Podium,
/// Club house and Office), each per month, quarter or year, with the society's total area, and see the total for a
/// month, a quarter and a year, the rate per sq ft, and what any flat would pay for its own area (or an equal share,
/// per line). Nothing is saved.
class BillPlannerPanel extends ConsumerStatefulWidget {
  /// What the charge heads bill now, per element, to start a plan from.
  final List<EstimateElement> current;
  const BillPlannerPanel({super.key, this.current = const []});

  @override
  ConsumerState<BillPlannerPanel> createState() => _BillPlannerPanelState();
}

class _BillPlannerPanelState extends ConsumerState<BillPlannerPanel> {
  final List<_Line> _lines = [];
  final TextEditingController _area = TextEditingController();
  int _next = 0;
  bool _compare = true;
  bool _loading = false;
  BillPlan? _plan;
  Object? _error;
  String _search = '';
  String _period = 'monthly'; // the one shown on a narrow screen, and in the flat list
  String? _wing; // the flat picked to see on its own
  String? _flatNumber;

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
    _area.dispose();
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
        AppToast.warning(context, 'Give each line a name and an amount');
        return;
      }
      inputs.add(PlanLineInput(name, amount, split: l.split, period: l.period));
    }
    if (inputs.isEmpty) {
      AppToast.warning(context, 'Add at least one element or common area with its amount');
      return;
    }
    double? area;
    final rawArea = _area.text.trim();
    if (rawArea.isNotEmpty) {
      area = double.tryParse(rawArea.replaceAll(',', ''));
      if (area == null || area <= 0) {
        AppToast.warning(context, 'Enter the total area as a number of sq ft, or leave it empty to use the flats\' areas');
        return;
      }
    }
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final p = await ref
          .read(maintenanceBillingApiProvider)
          .planMaintenance(societyId, inputs, compare: _compare, totalAreaSqft: area);
      if (!mounted) return;
      setState(() {
        _plan = p;
        _loading = false;
        if (!p.flats.any((f) => f.wing == _wing && f.number == _flatNumber)) _flatNumber = null; // the picked flat is gone
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

  static String _periodNoun(String period) => switch (period) {
        'quarterly' => 'quarter',
        'yearly' => 'year',
        _ => 'month',
      };

  @override
  Widget build(BuildContext context) {
    final p = _plan;
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      _editor(),
      const SizedBox(height: 14),
      if (_error != null)
        Padding(
          padding: const EdgeInsets.only(bottom: 8),
          child: Text(friendlyErrorMessage(_error!), style: TextStyle(color: AppTheme.error)),
        ),
      if (_loading && p == null)
        const Padding(padding: EdgeInsets.only(top: 40), child: AppLoader())
      else if (p != null) ...[
        _summary(p),
        const SizedBox(height: 14),
        _byElement(p),
        const SizedBox(height: 14),
        _onePicked(p),
        _flats(p),
        const SizedBox(height: 12),
        for (final n in p.notes)
          Padding(
            padding: const EdgeInsets.only(top: 2),
            child: Text(n, style: TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
          ),
      ],
    ]);
  }

  // ── The budget to enter ──

  Widget _editor() => AppCard(
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          const Text('Budget', style: TextStyle(fontSize: 14, fontWeight: FontWeight.w700)),
          const SizedBox(height: 2),
          Text(
              'List what the society needs: its elements and common areas, each per month, quarter or year, and the '
              'total area of the society. Each line is shared by flat area (a flat pays its area x the rate) or equally '
              'between all flats. Then Calculate: the totals come out monthly, quarterly and yearly.',
              style: TextStyle(fontSize: 12, color: AppTheme.textSecondary, height: 1.4)),
          const SizedBox(height: 12),
          TextField(
            key: const ValueKey('plan-area'),
            controller: _area,
            keyboardType: const TextInputType.numberWithOptions(decimal: true),
            inputFormatters: [FilteringTextInputFormatter.allow(RegExp(r'[0-9.,]'))],
            decoration: InputDecoration(
              labelText: 'Total society area (sq ft)',
              isDense: true,
              helperText: _plan == null
                  ? "Leave empty to use the flats' areas added up"
                  : "Leave empty to use the flats' areas: ${_plan!.flatsAreaSqft.toStringAsFixed(0)} sq ft",
            ),
          ),
          const SizedBox(height: 12),
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
              decoration: const InputDecoration(labelText: 'Amount ₹', isDense: true),
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
        Wrap(spacing: 8, runSpacing: 6, crossAxisAlignment: WrapCrossAlignment.center, children: [
          DropdownButton<String>(
            key: ValueKey('plan-period-${l.id}'),
            value: l.period,
            isDense: true,
            items: [for (final e in _periodWords.entries) DropdownMenuItem(value: e.key, child: Text(e.value))],
            onChanged: (v) => setState(() => l.period = v ?? 'month'),
          ),
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
        ]),
      ]);

  // ── The results ──

  Widget _periodSwitch() => SegmentedButton<String>(
        key: const ValueKey('plan-period'),
        segments: [for (final (k, label) in planPeriods) ButtonSegment(value: k, label: Text(label))],
        selected: {_period},
        showSelectedIcon: false,
        style: const ButtonStyle(visualDensity: VisualDensity.compact),
        onSelectionChanged: (s) => setState(() => _period = s.first),
      );

  Widget _summary(BillPlan p) {
    final per = p.of(_period);
    final noun = _periodNoun(_period);
    final shortfall = amountOf(per.shortfall);
    final currentNow = p.compared && p.currentTotal != null ? amountOf(p.currentTotal!) * (planPeriodMonths[_period] ?? 1) : null;
    final collected = amountOf(per.collected);
    return AppCard(
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        _periodSwitch(),
        const SizedBox(height: 10),
        Text('Total the society needs each $noun', style: TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
        Text(formatRupees(per.total), key: const ValueKey('plan-total'), style: const TextStyle(fontSize: 24, fontWeight: FontWeight.w700)),
        const SizedBox(height: 6),
        Text('Rate by area: ${_rate(per.ratePerSqft)}${_period == 'monthly' ? '' : ' per $noun'}',
            key: const ValueKey('plan-rate'), style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600)),
        if (amountOf(per.perFlatEqual) > 0)
          Text('Plus an equal share: ${formatRupees(per.perFlatEqual)} per flat', style: const TextStyle(fontSize: 13)),
        Text(
            '${p.flatsCount} flats · ${p.areaTotalSqft.toStringAsFixed(0)} sq ft '
            '(${p.areaSource == 'typed' ? 'as typed' : "the flats' areas"}) · average ${_rate(per.averagePerSqft)}',
            style: TextStyle(fontSize: 13, color: AppTheme.textSecondary)),
        if (shortfall != 0) ...[
          const SizedBox(height: 8),
          Text(
              'The flats would pay ${formatRupees(per.collected)} together: '
              '${shortfall > 0 ? 'short of' : 'over'} the budget by ${formatRupees(shortfall.abs().toStringAsFixed(2))}',
              key: const ValueKey('plan-shortfall'),
              style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: AppTheme.warning)),
        ],
        if (currentNow != null) ...[
          const SizedBox(height: 8),
          Text('Charge heads now (${p.monthLabel}): ${formatRupees(currentNow.toStringAsFixed(2))}', style: const TextStyle(fontSize: 13)),
          Text(
              'Difference: ${collected - currentNow > 0 ? '+' : ''}${formatRupees((collected - currentNow).toStringAsFixed(2))} a $noun',
              style: TextStyle(
                  fontSize: 13,
                  fontWeight: FontWeight.w600,
                  color: collected - currentNow > 0 ? AppTheme.warning : AppTheme.success)),
        ],
      ]),
    );
  }

  /// A table of rows against the periods: all three side by side where there is room, else the period chosen.
  Widget _periodTable({
    required List<(String, Map<String, String>)> rows,
    required (String, Map<String, String>) total,
    (String, Map<String, String>)? rate,
    (String, Map<String, String>)? extra,
  }) =>
      LayoutBuilder(builder: (context, c) {
        final wide = c.maxWidth >= 520;
        final shown = wide ? [for (final (k, _) in planPeriods) k] : [_period];
        Widget head() => Row(children: [
              const Expanded(flex: 3, child: SizedBox()),
              for (final k in shown)
                Expanded(
                  flex: 2,
                  child: Text(planPeriods.firstWhere((e) => e.$1 == k).$2,
                      textAlign: TextAlign.right,
                      style: TextStyle(fontSize: 12, fontWeight: FontWeight.w700, color: AppTheme.textSecondary)),
                ),
            ]);
        Widget row((String, Map<String, String>) r, {bool bold = false, bool rupees = true, Color? color}) => Padding(
              padding: const EdgeInsets.symmetric(vertical: 4),
              child: Row(children: [
                Expanded(
                  flex: 3,
                  child: Text(r.$1, style: TextStyle(fontSize: 13, fontWeight: bold ? FontWeight.w700 : FontWeight.w400, color: color)),
                ),
                for (final k in shown)
                  Expanded(
                    flex: 2,
                    child: Text(
                        rupees
                            ? formatRupees(r.$2[k] ?? '0')
                            : (r.$2[k] == null || r.$2[k] == '—' ? '—' : '₹${r.$2[k]}'),
                        textAlign: TextAlign.right,
                        style: TextStyle(fontSize: 13, fontWeight: bold ? FontWeight.w700 : FontWeight.w500, color: color)),
                  ),
              ]),
            );
        return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          head(),
          const Divider(height: 10),
          for (final r in rows) row(r),
          const Divider(height: 14),
          row(total, bold: true),
          if (rate != null) row(rate, rupees: false, color: AppTheme.textSecondary),
          if (extra != null) row(extra, color: AppTheme.warning),
        ]);
      });

  Widget _byElement(BillPlan p) => AppCard(
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          const Text('The society, element by element', style: TextStyle(fontSize: 14, fontWeight: FontWeight.w700)),
          const SizedBox(height: 8),
          _periodTable(
            rows: [for (final l in p.lines) (l.name, l.byPeriod)],
            total: ('Total', {for (final (k, _) in planPeriods) k: p.of(k).total}),
            rate: ('Rate per sq ft (by area)', {for (final (k, _) in planPeriods) k: p.of(k).ratePerSqft ?? '—'}),
          ),
        ]),
      );

  // ── One flat, picked ──

  Widget _onePicked(BillPlan p) {
    final wings = <String>{for (final f in p.flats) f.wing}.toList();
    final inWing = [for (final f in p.flats) if (f.wing == _wing) f];
    final flat = inWing.where((f) => f.number == _flatNumber).firstOrNull;
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      AppCard(
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          const Text('Pick a flat', style: TextStyle(fontSize: 14, fontWeight: FontWeight.w700)),
          const SizedBox(height: 8),
          Row(children: [
            Expanded(
              child: DropdownButtonFormField<String>(
                key: const ValueKey('plan-pick-wing'),
                value: wings.contains(_wing) ? _wing : null,
                isExpanded: true,
                decoration: const InputDecoration(labelText: 'Wing', isDense: true),
                items: [for (final w in wings) DropdownMenuItem(value: w, child: Text(w.isEmpty ? '—' : w))],
                onChanged: (v) => setState(() {
                  _wing = v;
                  _flatNumber = null;
                }),
              ),
            ),
            const SizedBox(width: 10),
            Expanded(
              child: DropdownButtonFormField<String>(
                key: const ValueKey('plan-pick-flat'),
                value: inWing.any((f) => f.number == _flatNumber) ? _flatNumber : null,
                isExpanded: true,
                decoration: const InputDecoration(labelText: 'Flat', isDense: true),
                items: [for (final f in inWing) DropdownMenuItem(value: f.number, child: Text(f.number))],
                onChanged: _wing == null ? null : (v) => setState(() => _flatNumber = v),
              ),
            ),
          ]),
          if (flat != null) ...[
            const SizedBox(height: 12),
            Text(
                '${flat.flatLabel} · ${flat.areaSqft == null ? 'no area recorded' : '${flat.areaSqft!.toStringAsFixed(0)} sq ft'}',
                key: const ValueKey('plan-picked'), style: const TextStyle(fontWeight: FontWeight.w700)),
            const SizedBox(height: 6),
            _periodTable(
              rows: [
                for (var i = 0; i < p.lines.length; i++)
                  (p.lines[i].name, {
                    for (final (k, _) in planPeriods)
                      k: i < flat.of(k).shares.length ? flat.of(k).shares[i].amount : '0'
                  })
              ],
              total: ('This flat pays', {for (final (k, _) in planPeriods) k: flat.of(k).total}),
              rate: ('Rate per sq ft', {for (final (k, _) in planPeriods) k: flat.of(k).perSqft ?? '—'}),
              extra: p.compared
                  ? ('Charge heads bill it now', {for (final (k, _) in planPeriods) k: flat.of(k).current ?? '0'})
                  : null,
            ),
          ],
        ]),
      ),
      const SizedBox(height: 14),
    ]);
  }

  // ── Every flat ──

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
        for (final f in shown) _PlanFlatTile(flat: f, plan: p, period: _period),
    ]);
  }
}

class _PlanFlatTile extends StatelessWidget {
  final PlanFlat flat;
  final BillPlan plan;
  final String period;
  const _PlanFlatTile({required this.flat, required this.plan, required this.period});

  @override
  Widget build(BuildContext context) {
    final f = flat.of(period);
    final change = amountOf(f.change ?? '0');
    final noun = _BillPlannerPanelState._periodNoun(period);
    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      child: ExpansionTile(
        key: ValueKey('plan-flat-${flat.flatLabel}'),
        shape: const Border(),
        title: Text(flat.flatLabel, style: const TextStyle(fontWeight: FontWeight.w700)),
        subtitle: Text(
            [
              if (flat.areaSqft != null) '${flat.areaSqft!.toStringAsFixed(0)} sq ft',
              if (f.perSqft != null) '₹${f.perSqft} / sq ft',
            ].join(' · '),
            style: const TextStyle(fontSize: 12.5)),
        trailing: Column(mainAxisAlignment: MainAxisAlignment.center, crossAxisAlignment: CrossAxisAlignment.end, children: [
          Text(formatRupees(f.total), style: const TextStyle(fontWeight: FontWeight.w700)),
          if (plan.compared && change != 0)
            Text('${change > 0 ? '+' : ''}${formatRupees(f.change!)}',
                style: TextStyle(fontSize: 11.5, color: change > 0 ? AppTheme.warning : AppTheme.success)),
        ]),
        childrenPadding: const EdgeInsets.fromLTRB(16, 0, 16, 12),
        children: [
          for (final s in f.shares)
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 3),
              child: Row(children: [
                Expanded(child: Text(s.name, style: const TextStyle(fontSize: 13))),
                Text(formatRupees(s.amount), style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w500)),
              ]),
            ),
          const Divider(height: 14),
          _row('Maintenance for the $noun', f.total, bold: true),
          if (plan.compared && f.current != null) _row('Charge heads now', f.current!),
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
