import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/motion/loading.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/features/maintenance_billing/data/maintenance_billing_api.dart';
import 'package:ar_society_app/features/maintenance_billing/presentation/providers/maintenance_billing_providers.dart' show maintenanceBillingApiProvider;
import 'package:ar_society_app/features/staff/presentation/widgets/staff_widgets.dart' show AppCard, EmptyState;
import 'package:ar_society_app/shared/widgets/app_form.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';

/// An estimate of a month's maintenance bills: what every flat would be billed, element by element, and a what-if to
/// try out a rise (or a cut) in any element, showing the new bill per flat and the rate per sq ft. The figures come
/// from the same calculation as the real bills, so what it shows is what Generate Bills would make; nothing is saved.
class BillEstimateScreen extends ConsumerStatefulWidget {
  const BillEstimateScreen({super.key});

  @override
  ConsumerState<BillEstimateScreen> createState() => _BillEstimateScreenState();
}

class _BillEstimateScreenState extends ConsumerState<BillEstimateScreen> {
  late DateTime _month = DateTime(DateTime.now().year, DateTime.now().month + 1);
  final Map<String, TextEditingController> _pct = {};
  final Map<String, TextEditingController> _total = {};
  final Map<String, TextEditingController> _rate = {};
  final Set<String> _byArea = {}; // elements to be shared out by flat area
  BillEstimate? _data;
  Object? _error;
  bool _loading = true;
  String _search = '';
  int _request = 0; // only the latest answer is shown

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _load());
  }

  @override
  void dispose() {
    for (final c in [..._pct.values, ..._total.values, ..._rate.values]) {
      c.dispose();
    }
    super.dispose();
  }

  TextEditingController _pctFor(String element) => _pct.putIfAbsent(element, TextEditingController.new);
  TextEditingController _totalFor(String element) => _total.putIfAbsent(element, TextEditingController.new);
  TextEditingController _rateFor(String element) => _rate.putIfAbsent(element, TextEditingController.new);

  /// The what-if typed in, per element: a rate per sq ft, or a percentage, or a new monthly total (the first one
  /// filled, in that order), shared out by area when "By area" is on. "By area" alone keeps the society's total.
  List<EstimateChange>? _changes() {
    final out = <EstimateChange>[];
    for (final element in {..._pct.keys, ..._total.keys, ..._rate.keys, ..._byArea}) {
      final r = _rate[element]?.text.trim() ?? '';
      final p = _pct[element]?.text.trim() ?? '';
      final t = _total[element]?.text.trim() ?? '';
      final byArea = _byArea.contains(element);
      if (r.isNotEmpty) {
        final v = double.tryParse(r.replaceAll(',', ''));
        if (v == null || v < 0) {
          AppToast.warning(context, 'Enter the rate per sq ft for $element as an amount, e.g. 2.5');
          return null;
        }
        out.add(EstimateChange(element, perSqft: v));
      } else if (p.isNotEmpty) {
        final v = double.tryParse(p);
        if (v == null || v < -100) {
          AppToast.warning(context, 'Enter the change for $element as a percentage, e.g. 10 or -5');
          return null;
        }
        out.add(EstimateChange(element, percent: v, byArea: byArea));
      } else if (t.isNotEmpty) {
        final v = double.tryParse(t.replaceAll(',', ''));
        if (v == null || v < 0) {
          AppToast.warning(context, 'Enter the new monthly total for $element as an amount');
          return null;
        }
        out.add(EstimateChange(element, targetTotal: v, byArea: byArea));
      } else if (byArea) {
        out.add(EstimateChange(element, byArea: true));
      }
    }
    return out;
  }

  Future<void> _load({bool keepChanges = true}) async {
    final societyId = ref.read(currentUserProvider)?.societyId;
    if (societyId == null) return;
    final changes = keepChanges ? _changes() : <EstimateChange>[];
    if (changes == null) return;
    final id = ++_request;
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final d = await ref
          .read(maintenanceBillingApiProvider)
          .estimateBills(societyId, month: DateFormat('yyyy-MM').format(_month), changes: changes);
      if (!mounted || id != _request) return;
      setState(() {
        _data = d;
        _loading = false;
      });
    } catch (e) {
      if (!mounted || id != _request) return;
      setState(() {
        _error = e;
        _loading = false;
      });
    }
  }

  void _reset() {
    for (final c in [..._pct.values, ..._total.values, ..._rate.values]) {
      c.clear();
    }
    _byArea.clear();
    _load(keepChanges: false);
  }

  /// Every element billed by flat area with the society's total kept: what each flat would pay if maintenance went
  /// per sq ft without the society collecting any more or less.
  void _allByArea() {
    final names = _data?.elements.map((e) => e.element) ?? const <String>[];
    for (final c in [..._pct.values, ..._total.values, ..._rate.values]) {
      c.clear();
    }
    setState(() {
      _byArea
        ..clear()
        ..addAll(names);
    });
    _load();
  }

  void _moveMonth(int by) {
    setState(() => _month = DateTime(_month.year, _month.month + by));
    _load();
  }

  static String _rate(String? v) => v == null ? '—' : '₹$v / sq ft';

  static String _signed(String v) {
    final n = amountOf(v);
    return '${n > 0 ? '+' : ''}${formatRupees(v)}';
  }

  @override
  Widget build(BuildContext context) {
    final d = _data;
    return AppPage(
      title: 'Bill estimate',
      subtitle: 'What each flat would be billed, element by element',
      body: ResponsiveBody(
        maxWidth: 900,
        child: RefreshIndicator(
          onRefresh: () => _load(),
          child: ListView(
            padding: const EdgeInsets.fromLTRB(16, 12, 16, 60),
            children: [
              _monthBar(),
              const SizedBox(height: 10),
              if (_error != null && d == null)
                AppErrorState(compact: true, message: friendlyErrorMessage(_error!), onRetry: _load)
              else if (d == null)
                const Padding(padding: EdgeInsets.only(top: 80), child: AppLoader())
              else ...[
                if (_error != null)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 8),
                    child: Text(friendlyErrorMessage(_error!), style: const TextStyle(color: AppTheme.error)),
                  ),
                _summary(d),
                const SizedBox(height: 14),
                _elements(d),
                const SizedBox(height: 14),
                _flats(d),
                const SizedBox(height: 12),
                for (final n in d.notes)
                  Padding(
                    padding: const EdgeInsets.only(top: 2),
                    child: Text(n, style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
                  ),
              ],
            ],
          ),
        ),
      ),
    );
  }

  Widget _monthBar() => Row(mainAxisAlignment: MainAxisAlignment.center, children: [
        IconButton(
          key: const ValueKey('estimate-month-prev'),
          tooltip: 'Previous month',
          icon: const Icon(Icons.chevron_left_rounded),
          onPressed: _loading ? null : () => _moveMonth(-1),
        ),
        Text(DateFormat('MMMM yyyy').format(_month),
            key: const ValueKey('estimate-month'), style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w700)),
        IconButton(
          key: const ValueKey('estimate-month-next'),
          tooltip: 'Next month',
          icon: const Icon(Icons.chevron_right_rounded),
          onPressed: _loading ? null : () => _moveMonth(1),
        ),
      ]);

  Widget _summary(BillEstimate d) => AppCard(
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(d.adjusted ? 'Estimated total with your changes' : 'Estimated total for ${d.monthLabel}',
              style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
          Text(formatRupees(d.estimate),
              key: const ValueKey('estimate-total'), style: const TextStyle(fontSize: 24, fontWeight: FontWeight.w700)),
          const SizedBox(height: 4),
          Text('${_rate(d.estimatePerSqft)} on average · ${d.flatsCount} flats · ${d.totalAreaSqft.toStringAsFixed(0)} sq ft',
              style: const TextStyle(fontSize: 13, color: AppTheme.textSecondary)),
          if (d.adjusted) ...[
            const SizedBox(height: 8),
            Text('As it stands: ${formatRupees(d.current)} · ${_rate(d.currentPerSqft)}',
                style: const TextStyle(fontSize: 13)),
            Text('Change: ${_signed(d.change)} for the society each month',
                style: TextStyle(
                    fontSize: 13,
                    fontWeight: FontWeight.w600,
                    color: amountOf(d.change) > 0 ? AppTheme.warning : AppTheme.success)),
          ],
        ]),
      );

  Widget _elements(BillEstimate d) => AppCard(
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          const Text('Elements — what if?', style: TextStyle(fontSize: 14, fontWeight: FontWeight.w700)),
          const SizedBox(height: 2),
          const Text(
              'Try a rise or a cut: a change in % (10 raises it by a tenth, -5 cuts it), or the new monthly total you '
              'want from an element. To bill an element by flat area, give a rate per sq ft, or tick By area to share '
              'its total over the flats by their areas (a flat pays its area x the rate). Then Calculate.',
              style: TextStyle(fontSize: 12, color: AppTheme.textSecondary, height: 1.4)),
          const SizedBox(height: 10),
          OutlinedButton.icon(
            key: const ValueKey('estimate-all-by-area'),
            onPressed: _loading ? null : _allByArea,
            icon: const Icon(Icons.square_foot_rounded, size: 18),
            label: const Text('Bill every element by area (same society total)'),
          ),
          const SizedBox(height: 14),
          for (final e in d.elements) ...[
            Row(children: [
              Expanded(child: Text(e.element, style: const TextStyle(fontWeight: FontWeight.w600))),
              Text(formatRupees(e.adjusted ? e.estimateTotal : e.currentTotal),
                  style: const TextStyle(fontWeight: FontWeight.w700)),
            ]),
            Text(
                e.adjusted
                    ? 'Was ${formatRupees(e.currentTotal)} (${_rate(e.currentPerSqft)}) · now ${_rate(e.estimatePerSqft)}'
                        '${e.changePct == null || amountOf(e.change) == 0 ? '' : ' · ${amountOf(e.changePct!) > 0 ? '+' : ''}${e.changePct}%'}'
                        '${e.byArea ? ' · by area' : ''}'
                    : _rate(e.currentPerSqft),
                style: TextStyle(fontSize: 12, color: e.adjusted ? AppTheme.warning : AppTheme.textSecondary)),
            const SizedBox(height: 6),
            Row(children: [
              Expanded(
                child: TextField(
                  key: ValueKey('estimate-pct-${e.element}'),
                  controller: _pctFor(e.element),
                  keyboardType: const TextInputType.numberWithOptions(decimal: true, signed: true),
                  inputFormatters: [FilteringTextInputFormatter.allow(RegExp(r'[-0-9.]'))],
                  decoration: const InputDecoration(labelText: 'Change %', isDense: true),
                  onSubmitted: (_) => _load(),
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: TextField(
                  key: ValueKey('estimate-total-${e.element}'),
                  controller: _totalFor(e.element),
                  keyboardType: const TextInputType.numberWithOptions(decimal: true),
                  inputFormatters: [FilteringTextInputFormatter.allow(RegExp(r'[0-9.,]'))],
                  decoration: const InputDecoration(labelText: 'Or new total ₹', isDense: true),
                  onSubmitted: (_) => _load(),
                ),
              ),
            ]),
            const SizedBox(height: 8),
            Row(children: [
              Expanded(
                child: TextField(
                  key: ValueKey('estimate-rate-${e.element}'),
                  controller: _rateFor(e.element),
                  keyboardType: const TextInputType.numberWithOptions(decimal: true),
                  inputFormatters: [FilteringTextInputFormatter.allow(RegExp(r'[0-9.,]'))],
                  decoration: const InputDecoration(labelText: 'Or ₹ per sq ft', isDense: true),
                  onSubmitted: (_) => _load(),
                ),
              ),
              const SizedBox(width: 10),
              FilterChip(
                key: ValueKey('estimate-area-${e.element}'),
                label: const Text('By area'),
                avatar: const Icon(Icons.square_foot_rounded, size: 16),
                selected: _byArea.contains(e.element),
                onSelected: (on) => setState(() => on ? _byArea.add(e.element) : _byArea.remove(e.element)),
              ),
            ]),
            const SizedBox(height: 12),
          ],
          Row(children: [
            Expanded(
              child: FilledButton.icon(
                key: const ValueKey('estimate-calc'),
                onPressed: _loading ? null : () => _load(),
                icon: _loading
                    ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2))
                    : const Icon(Icons.calculate_outlined, size: 18),
                label: const Text('Calculate'),
              ),
            ),
            const SizedBox(width: 10),
            OutlinedButton(
              key: const ValueKey('estimate-reset'),
              onPressed: _loading ? null : _reset,
              child: const Text('Reset'),
            ),
          ]),
        ]),
      );

  Widget _flats(BillEstimate d) {
    final q = _search.toLowerCase();
    final shown = [for (final f in d.flats) if (q.isEmpty || f.flatLabel.toLowerCase().contains(q)) f];
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Text('Each flat (${d.flats.length})', style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w700)),
      const SizedBox(height: 8),
      TextField(
        key: const ValueKey('estimate-search'),
        onChanged: (v) => setState(() => _search = v.trim()),
        decoration: const InputDecoration(prefixIcon: Icon(Icons.search_rounded), hintText: 'Search a flat'),
      ),
      const SizedBox(height: 8),
      if (shown.isEmpty)
        const Padding(
          padding: EdgeInsets.only(top: 24),
          child: EmptyState(
              icon: Icons.apartment_rounded, title: 'No flats to show', subtitle: 'Nothing matches, or no flat is billed.'),
        )
      else
        for (final f in shown) _FlatTile(flat: f, adjusted: d.adjusted),
    ]);
  }
}

class _FlatTile extends StatelessWidget {
  final EstimateFlat flat;
  final bool adjusted;
  const _FlatTile({required this.flat, required this.adjusted});

  @override
  Widget build(BuildContext context) {
    final change = amountOf(flat.change);
    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      child: ExpansionTile(
        key: ValueKey('estimate-flat-${flat.flatLabel}'),
        shape: const Border(),
        title: Text(flat.flatLabel, style: const TextStyle(fontWeight: FontWeight.w700)),
        subtitle: Text(
            [
              if (flat.areaSqft != null) '${flat.areaSqft!.toStringAsFixed(0)} sq ft',
              if (flat.estimatePerSqft != null) '₹${flat.estimatePerSqft} / sq ft',
            ].join(' · '),
            style: const TextStyle(fontSize: 12.5)),
        trailing: Column(mainAxisAlignment: MainAxisAlignment.center, crossAxisAlignment: CrossAxisAlignment.end, children: [
          Text(formatRupees(flat.estimateTotal), style: const TextStyle(fontWeight: FontWeight.w700)),
          if (adjusted && change != 0)
            Text('${change > 0 ? '+' : ''}${formatRupees(flat.change)}',
                style: TextStyle(fontSize: 11.5, color: change > 0 ? AppTheme.warning : AppTheme.success)),
        ]),
        childrenPadding: const EdgeInsets.fromLTRB(16, 0, 16, 12),
        children: [
          for (final l in flat.lines)
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 3),
              child: Row(children: [
                Expanded(child: Text(l.element, style: const TextStyle(fontSize: 13))),
                if (adjusted && l.current != l.estimate) ...[
                  Text(formatRupees(l.current),
                      style: const TextStyle(
                          fontSize: 12, color: AppTheme.textSecondary, decoration: TextDecoration.lineThrough)),
                  const SizedBox(width: 8),
                ],
                Text(formatRupees(l.estimate), style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w500)),
              ]),
            ),
          if (amountOf(flat.tax) > 0) _row('Tax', flat.tax),
          if (amountOf(flat.roundOff) != 0) _row('Round off', flat.roundOff),
          const Divider(height: 14),
          _row('Estimated bill', flat.estimateTotal, bold: true),
          if (adjusted) _row('As it stands', flat.currentTotal),
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
