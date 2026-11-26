import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/layout/app_sheet.dart';
import 'package:ar_society_app/core/motion/loading.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/accounts/data/accounts_api.dart' show apiDate, formatAccountsDate, formatInr;
import 'package:ar_society_app/features/accounts/data/depreciation_api.dart';
import 'package:ar_society_app/features/accounts/presentation/widgets/accounts_widgets.dart';
import 'package:ar_society_app/features/accounts/presentation/widgets/register_widgets.dart';
import 'package:ar_society_app/features/assets/data/assets_api.dart' show assetCategoryIcon, assetCategoryLabel;
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/shared/widgets/app_data_table.dart' show StatusPill;
import 'package:ar_society_app/shared/widgets/app_form.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';
import 'package:ar_society_app/shared/widgets/premium.dart';

/// "2026-27" for the financial year that begins in April of [startYear].
String financialYearLabel(int startYear) => '$startYear-${((startYear + 1) % 100).toString().padLeft(2, '0')}';

/// Depreciation of the society's fixed assets: the year's schedule (with the journal that would book it, which this
/// screen never posts) and the setup it is worked out from. Only the committee changes the setup.
class DepreciationScreen extends ConsumerStatefulWidget {
  /// Today, so tests can fix the year.
  final DateTime? today;
  const DepreciationScreen({super.key, this.today});

  @override
  ConsumerState<DepreciationScreen> createState() => _DepreciationScreenState();
}

class _DepreciationScreenState extends ConsumerState<DepreciationScreen> {
  late final DateTime _today = widget.today ?? DateTime.now();
  late int _year = _today.month >= 4 ? _today.year : _today.year - 1;
  bool _setup = false;

  @override
  Widget build(BuildContext context) {
    final user = ref.watch(currentUserProvider);
    final societyId = user?.societyId;
    if (societyId == null) return const Scaffold(body: Center(child: Text('No society context')));
    final fy = financialYearLabel(_year);
    final current = _today.month >= 4 ? _today.year : _today.year - 1;
    final schedule = ref.watch(depreciationScheduleProvider((societyId: societyId, fy: fy)));
    return AppPage(
      title: 'Depreciation',
      subtitle: 'Calculated from the asset register; nothing is posted',
      actions: [
        if (!_setup)
          PdfActions(
            load: schedule.valueOrNull == null ? null : () => ref.read(depreciationApiProvider).schedulePdf(societyId, fy),
            fileName: 'Depreciation-$fy.pdf',
            subject: 'Depreciation schedule $fy',
          ),
      ],
      body: RefreshIndicator(
        onRefresh: () async {
          ref.invalidate(depreciationScheduleProvider);
          ref.invalidate(depreciationRulesProvider);
          ref.invalidate(depreciationAssetsProvider);
        },
        child: ListView(
          padding: const EdgeInsets.fromLTRB(16, 12, 16, 96),
          children: [
            SegmentedButton<bool>(
              key: const Key('dep-mode'),
              segments: const [
                ButtonSegment(value: false, label: Text('Schedule'), icon: Icon(Icons.table_chart_outlined)),
                ButtonSegment(value: true, label: Text('Setup'), icon: Icon(Icons.tune_rounded)),
              ],
              selected: {_setup},
              onSelectionChanged: (s) => setState(() => _setup = s.first),
            ),
            const SizedBox(height: 12),
            if (!_setup) ...[
              Wrap(spacing: 8, runSpacing: 8, children: [
                for (final y in [current, current - 1, current - 2])
                  ChoiceChip(
                      key: Key('dep-fy-$y'),
                      label: Text(financialYearLabel(y)),
                      selected: _year == y,
                      onSelected: (_) => setState(() => _year = y)),
              ]),
              const SizedBox(height: 14),
              ...schedule.when(
                loading: () => [const AppLoader()],
                error: (e, _) => [
                  AppErrorState(
                      compact: true,
                      message: friendlyErrorMessage(e),
                      onRetry: () => ref.invalidate(depreciationScheduleProvider((societyId: societyId, fy: fy))))
                ],
                data: (s) => _scheduleBody(s),
              ),
            ] else
              ..._setupBody(societyId, user!.isAdminOrCommittee),
          ],
        ),
      ),
    );
  }

  // ── The schedule ───────────────────────────────────────────────────────────────────────────────────────────────────

  List<Widget> _scheduleBody(DepreciationSchedule s) => [
        RegisterTotals(figures: [
          ('Cost', formatInr(s.cost)),
          ('Book value at start', formatInr(s.openingWdv)),
          ('Depreciation', formatInr(s.depreciation)),
          ('Book value at end', formatInr(s.closingWdv)),
        ]),
        const SizedBox(height: 14),
        if (s.rows.isEmpty)
          const Padding(
              padding: EdgeInsets.symmetric(vertical: 24),
              child: AppEmptyState(
                  icon: Icons.inventory_2_outlined,
                  title: 'No asset is depreciated this year',
                  subtitle: 'Add the cost and purchase date of each asset in the asset register.'))
        else
          for (final r in s.rows) _RowTile(row: r),
        if (s.depreciation > 0) ...[
          const SizedBox(height: 14),
          const SectionHeading('Journal to book this year'),
          const SizedBox(height: 8),
          PremiumSurface(
            padding: const EdgeInsets.all(14),
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              _journal('Dr  ${s.debit.ledger}', s.debit.amount),
              for (final c in s.credits) _journal('      Cr  ${c.ledger}', c.amount),
              const SizedBox(height: 8),
              Text(
                  'Nothing has been posted. Review the figures, then enter this as a Journal voucher in Accounts. '
                  'The fixed-asset ledgers carry book value, so depreciation is credited to them.',
                  style: TextStyle(fontSize: 12, color: AppTheme.textSecondary, height: 1.35)),
            ]),
          ),
        ],
        if (s.problems.isNotEmpty) ...[
          const SizedBox(height: 14),
          const SectionHeading('Left out until their setup is complete'),
          const SizedBox(height: 8),
          for (final p in s.problems)
            Card(
              margin: const EdgeInsets.only(bottom: 8),
              child: ListTile(
                title: Text('${p.code} · ${p.name}', style: const TextStyle(fontWeight: FontWeight.w600)),
                subtitle: Text(p.issues.join('; ')),
                leading: Icon(Icons.warning_amber_rounded, color: AppTheme.warning),
              ),
            ),
        ],
      ];

  Widget _journal(String text, double amount) => Padding(
        padding: const EdgeInsets.symmetric(vertical: 3),
        child: Row(children: [
          Expanded(child: Text(text, style: const TextStyle(fontSize: 13, fontFeatures: [FontFeature.tabularFigures()]))),
          Text(formatInr(amount), style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 13)),
        ]),
      );

  // ── The setup ──────────────────────────────────────────────────────────────────────────────────────────────────────

  List<Widget> _setupBody(String societyId, bool committee) {
    final rules = ref.watch(depreciationRulesProvider(societyId));
    final assets = ref.watch(depreciationAssetsProvider(societyId));
    return [
      Text(
          'How each kind of asset is depreciated. These are only starting values (the usual income-tax rates on a '
          'reducing balance): have your chartered accountant confirm them. Changing a rate changes the schedule of every '
          'year, so do not change it after a year\'s depreciation has been entered in the books.',
          style: TextStyle(fontSize: 12.5, color: AppTheme.textSecondary, height: 1.35)),
      const SizedBox(height: 12),
      const SectionHeading('Kinds of asset'),
      const SizedBox(height: 8),
      ...rules.when(
        loading: () => [const AppLoader()],
        error: (e, _) => [AppErrorState(compact: true, message: friendlyErrorMessage(e), onRetry: () => ref.invalidate(depreciationRulesProvider(societyId)))],
        data: (list) => [
          for (final r in list)
            Card(
              margin: const EdgeInsets.only(bottom: 8),
              child: ListTile(
                key: Key('dep-rule-${r.category}'),
                leading: Icon(assetCategoryIcon(r.category), color: AppTheme.primary),
                title: Text(r.label, style: const TextStyle(fontWeight: FontWeight.w600)),
                subtitle: Text('${depreciationMethodLabel(r.method)} · ${_pct(r.rate)}%'
                    '${r.lifeYears != null ? ' · ${r.lifeYears} years' : ''}'
                    '${r.salvagePercent > 0 ? ' · keeps ${_pct(r.salvagePercent)}% of cost' : ''}'),
                trailing: committee ? const Icon(Icons.edit_outlined, size: 18) : null,
                onTap: !committee
                    ? null
                    : () async {
                        final saved = await showAppSheet<bool>(context: context, builder: (_) => _RuleSheet(rule: r));
                        if (saved == true) {
                          ref.invalidate(depreciationRulesProvider(societyId));
                          ref.invalidate(depreciationAssetsProvider(societyId));
                          ref.invalidate(depreciationScheduleProvider);
                        }
                      },
              ),
            ),
        ],
      ),
      const SizedBox(height: 14),
      const SectionHeading('Assets'),
      const SizedBox(height: 8),
      ...assets.when(
        loading: () => [const AppLoader()],
        error: (e, _) => [AppErrorState(compact: true, message: friendlyErrorMessage(e), onRetry: () => ref.invalidate(depreciationAssetsProvider(societyId)))],
        data: (list) => list.isEmpty
            ? [const Padding(padding: EdgeInsets.all(20), child: Center(child: Text('No assets in the register yet')))]
            : [
                for (final a in list)
                  Card(
                    margin: const EdgeInsets.only(bottom: 8),
                    child: ListTile(
                      key: Key('dep-asset-${a.code}'),
                      isThreeLine: true,
                      leading: Icon(assetCategoryIcon(a.category), color: AppTheme.primary),
                      title: Text('${a.code} · ${a.name}', style: const TextStyle(fontWeight: FontWeight.w600)),
                      subtitle: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                        Text(!a.depreciate
                            ? 'Not depreciated'
                            : '${depreciationMethodLabel(a.method)} · ${_pct(a.rate)}% · cost ${formatInr(a.cost)}'),
                        Text(
                            [
                              if (a.startOn != null) 'In use from ${formatAccountsDate(a.startOn!)}',
                              if (a.stopOn != null) 'until ${formatAccountsDate(a.stopOn!)}',
                              if (a.own != null) 'own setting',
                            ].join(' · '),
                            style: TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
                        for (final p in a.problems) Padding(padding: const EdgeInsets.only(top: 3), child: StatusPill(p, AppTheme.warning)),
                      ]),
                      trailing: committee ? const Icon(Icons.edit_outlined, size: 18) : null,
                      onTap: !committee
                          ? null
                          : () async {
                              final saved = await showAppSheet<bool>(context: context, builder: (_) => _AssetSheet(asset: a));
                              if (saved == true) {
                                ref.invalidate(depreciationAssetsProvider(societyId));
                                ref.invalidate(depreciationScheduleProvider);
                              }
                            },
                    ),
                  ),
              ],
      ),
    ];
  }
}

String _pct(double v) => v == v.roundToDouble() ? v.toStringAsFixed(0) : v.toStringAsFixed(2);

class _RowTile extends StatelessWidget {
  final DepreciationRow row;
  const _RowTile({required this.row});

  @override
  Widget build(BuildContext context) {
    final r = row;
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: PremiumSurface(
        padding: const EdgeInsets.all(14),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Expanded(
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text(r.name, style: const TextStyle(fontWeight: FontWeight.w700)),
                Text('${r.code} · ${assetCategoryLabel(r.category)}',
                    style: TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
              ]),
            ),
            const SizedBox(width: 10),
            Column(crossAxisAlignment: CrossAxisAlignment.end, children: [
              Text(formatInr(r.depreciation), style: const TextStyle(fontWeight: FontWeight.w800, fontSize: 15)),
              Text('depreciation', style: TextStyle(fontSize: 11, color: AppTheme.textSecondary)),
            ]),
          ]),
          const SizedBox(height: 8),
          Text(
              '${r.method == 'wdv' ? 'Reducing balance' : 'Straight line'} ${_pct(r.rate)}% · in use from ${formatAccountsDate(r.start)}'
              '${r.days < 365 ? ' · ${r.days} days this year' : ''}',
              style: TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
          Text('Cost ${formatInr(r.cost)} · book value ${formatInr(r.openingWdv)} → ${formatInr(r.closingWdv)}',
              style: const TextStyle(fontSize: 12.5)),
        ]),
      ),
    );
  }
}

final _percent = [FilteringTextInputFormatter.allow(RegExp(r'^\d{0,3}(\.\d{0,4})?'))];
final _amount = [FilteringTextInputFormatter.allow(RegExp(r'^\d{0,12}(\.\d{0,2})?'))];
const _decimal = TextInputType.numberWithOptions(decimal: true);

/// Change how one kind of asset is depreciated. Pops true once saved.
class _RuleSheet extends ConsumerStatefulWidget {
  final DepreciationRule rule;
  const _RuleSheet({required this.rule});

  @override
  ConsumerState<_RuleSheet> createState() => _RuleSheetState();
}

class _RuleSheetState extends ConsumerState<_RuleSheet> {
  final _form = GlobalKey<FormState>();
  late String _method = widget.rule.method;
  late final _rate = TextEditingController(text: _pct(widget.rule.rate));
  late final _life = TextEditingController(text: widget.rule.lifeYears?.toString() ?? '');
  late final _salvage = TextEditingController(text: _pct(widget.rule.salvagePercent));
  bool _busy = false;

  @override
  void dispose() {
    _rate.dispose();
    _life.dispose();
    _salvage.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    if (!_form.currentState!.validate()) return;
    setState(() => _busy = true);
    try {
      final life = int.tryParse(_life.text.trim());
      await ref.read(depreciationApiProvider).updateRule(widget.rule.id,
          method: _method,
          rate: _rate.text.trim().isEmpty ? '0' : _rate.text.trim(),
          lifeYears: life,
          salvagePercent: _salvage.text.trim().isEmpty ? '0' : _salvage.text.trim());
      if (!mounted) return;
      AppToast.success(context, 'Saved');
      Navigator.of(context).pop(true);
    } catch (e) {
      if (mounted) {
        setState(() => _busy = false);
        showErrorToast(context, e);
      }
    }
  }

  @override
  Widget build(BuildContext context) => AppSheetFrame(
        title: widget.rule.label,
        subtitle: 'How this kind of asset is depreciated',
        child: Form(
          key: _form,
          child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
            FormFieldBox(
              label: 'Method',
              child: DropdownButtonFormField<String>(
                key: const Key('dep-method'),
                isExpanded: true,
                initialValue: _method,
                items: [for (final (v, l) in kDepreciationMethods) DropdownMenuItem(value: v, child: Text(l))],
                onChanged: (v) => setState(() => _method = v ?? _method),
              ),
            ),
            FormFieldBox(
              label: 'Rate a year (%)',
              helper: _method == 'slm' ? 'Leave empty to use 100 divided by the life' : null,
              child: TextFormField(
                key: const Key('dep-rate'),
                controller: _rate,
                keyboardType: _decimal,
                inputFormatters: _percent,
                decoration: const InputDecoration(suffixText: '%'),
                validator: (v) {
                  final d = double.tryParse((v ?? '').trim());
                  if ((v ?? '').trim().isEmpty && _method == 'slm' && int.tryParse(_life.text.trim()) != null) return null;
                  return d == null || d <= 0 || d > 100 ? 'Enter a rate above 0 and up to 100' : null;
                },
              ),
            ),
            if (_method == 'slm')
              FormFieldBox(
                label: 'Life (years)',
                child: TextFormField(
                    controller: _life,
                    keyboardType: TextInputType.number,
                    inputFormatters: [FilteringTextInputFormatter.digitsOnly],
                    validator: (v) => (v ?? '').trim().isEmpty || (int.tryParse(v!.trim()) ?? 0) >= 1 ? null : 'Enter years'),
              ),
            FormFieldBox(
              label: 'Value kept at the end (% of cost)',
              child: TextFormField(
                controller: _salvage,
                keyboardType: _decimal,
                inputFormatters: _percent,
                decoration: const InputDecoration(suffixText: '%'),
                validator: (v) {
                  final d = double.tryParse((v ?? '').trim().isEmpty ? '0' : v!.trim());
                  return d == null || d < 0 || d >= 100 ? 'Enter a percentage under 100' : null;
                },
              ),
            ),
            const SizedBox(height: 8),
            FilledButton(onPressed: _busy ? null : _save, child: const Text('Save')),
          ]),
        ),
      );
}

/// One asset's own setting where it differs from its kind's. An empty field uses the kind's value. Pops true once saved.
class _AssetSheet extends ConsumerStatefulWidget {
  final AssetDepreciationSetting asset;
  const _AssetSheet({required this.asset});

  @override
  ConsumerState<_AssetSheet> createState() => _AssetSheetState();
}

class _AssetSheetState extends ConsumerState<_AssetSheet> {
  final _form = GlobalKey<FormState>();
  late bool _depreciate = widget.asset.depreciate;
  late String? _method = widget.asset.own?['method'] as String?;
  late final _rate = TextEditingController(text: _plain(widget.asset.own?['rate']));
  late final _salvage = TextEditingController(text: _plain(widget.asset.own?['salvage_value']));
  late DateTime? _start = DateTime.tryParse('${widget.asset.own?['start_on'] ?? ''}');
  late DateTime? _stop = DateTime.tryParse('${widget.asset.own?['stop_on'] ?? ''}');
  bool _busy = false;

  static String _plain(Object? v) {
    final d = double.tryParse('${v ?? ''}');
    return d == null ? '' : (d == d.roundToDouble() ? d.toStringAsFixed(0) : d.toString());
  }

  @override
  void dispose() {
    _rate.dispose();
    _salvage.dispose();
    super.dispose();
  }

  Future<void> _pick(bool start) async {
    final a = widget.asset;
    final initial = (start ? _start : _stop) ?? a.startOn ?? DateTime.now();
    final d = await showDatePicker(context: context, initialDate: initial, firstDate: DateTime(1990), lastDate: DateTime(2100));
    if (d != null) setState(() => start ? _start = d : _stop = d);
  }

  Future<void> _save() async {
    if (!_form.currentState!.validate()) return;
    setState(() => _busy = true);
    try {
      await ref.read(depreciationApiProvider).setAsset(widget.asset.assetId, {
        'depreciate': _depreciate,
        'method': _method,
        'rate': _rate.text.trim().isEmpty ? null : _rate.text.trim(),
        'salvage_value': _salvage.text.trim().isEmpty ? null : _salvage.text.trim(),
        'start_on': _start == null ? null : apiDate(_start!),
        'stop_on': _stop == null ? null : apiDate(_stop!),
      });
      if (!mounted) return;
      AppToast.success(context, 'Saved');
      Navigator.of(context).pop(true);
    } catch (e) {
      if (mounted) {
        setState(() => _busy = false);
        showErrorToast(context, e);
      }
    }
  }

  Widget _dateField(String label, DateTime? value, bool start, String hint) => FormFieldBox(
        label: label,
        child: Row(children: [
          Expanded(
            child: OutlinedButton(
              onPressed: () => _pick(start),
              child: Align(alignment: Alignment.centerLeft, child: Text(value == null ? hint : formatAccountsDate(value))),
            ),
          ),
          if (value != null) IconButton(onPressed: () => setState(() => start ? _start = null : _stop = null), icon: const Icon(Icons.close_rounded)),
        ]),
      );

  @override
  Widget build(BuildContext context) => AppSheetFrame(
        title: widget.asset.name,
        subtitle: '${widget.asset.code} · ${assetCategoryLabel(widget.asset.category)}',
        child: Form(
          key: _form,
          child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
            SwitchListTile(
              contentPadding: EdgeInsets.zero,
              value: _depreciate,
              onChanged: (v) => setState(() => _depreciate = v),
              title: const Text('Depreciate this asset'),
              subtitle: const Text('Turn off for land, or anything that does not wear out'),
            ),
            if (_depreciate) ...[
              FormFieldBox(
                label: 'Method',
                child: DropdownButtonFormField<String?>(
                  isExpanded: true,
                  initialValue: _method,
                  items: [
                    const DropdownMenuItem(value: null, child: Text("Same as the kind of asset")),
                    for (final (v, l) in kDepreciationMethods) DropdownMenuItem(value: v, child: Text(l)),
                  ],
                  onChanged: (v) => setState(() => _method = v),
                ),
              ),
              FormFieldBox(
                label: 'Rate a year (%)',
                helper: 'Empty: the kind of asset\'s rate',
                child: TextFormField(
                  controller: _rate,
                  keyboardType: _decimal,
                  inputFormatters: _percent,
                  decoration: const InputDecoration(suffixText: '%'),
                  validator: (v) {
                    if ((v ?? '').trim().isEmpty) return null;
                    final d = double.tryParse(v!.trim());
                    return d == null || d <= 0 || d > 100 ? 'Enter a rate above 0 and up to 100' : null;
                  },
                ),
              ),
              FormFieldBox(
                label: 'Value kept at the end',
                helper: 'Empty: the kind of asset\'s percentage of cost',
                child: TextFormField(
                    controller: _salvage,
                    keyboardType: _decimal,
                    inputFormatters: _amount,
                    decoration: const InputDecoration(prefixText: '₹ ')),
              ),
              _dateField('Put to use on', _start, true, 'Purchase date'),
              _dateField('Stopped being used on', _stop, false, 'Still in use'),
            ],
            const SizedBox(height: 8),
            FilledButton(onPressed: _busy ? null : _save, child: const Text('Save')),
          ]),
        ),
      );
}
