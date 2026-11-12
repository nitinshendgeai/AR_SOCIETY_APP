import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/layout/app_sheet.dart';
import 'package:ar_society_app/core/motion/loading.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/features/lights_check/data/lights_api.dart';
import 'package:ar_society_app/features/maintenance_billing/presentation/widgets/billing_sheet_frame.dart';
import 'package:ar_society_app/features/society_structure/presentation/providers/structure_providers.dart';
import 'package:ar_society_app/features/stores/presentation/providers/stores_providers.dart';
import 'package:ar_society_app/shared/widgets/app_form.dart' show AppPage;
import 'package:ar_society_app/shared/widgets/app_widgets.dart';

const _working = 'working';
const _notWorking = 'not_working';

/// "5 Nov, 10:30 am" - the date and time a light was checked.
String lightStamp(DateTime d) => DateFormat('d MMM, h:mm a').format(d);

/// The monthly check of the common lights, filled in by the electrician or plumber, and the list of what to replace.
class LightsCheckScreen extends ConsumerStatefulWidget {
  const LightsCheckScreen({super.key});

  @override
  ConsumerState<LightsCheckScreen> createState() => _LightsCheckScreenState();
}

class _LightsCheckScreenState extends ConsumerState<LightsCheckScreen> with SingleTickerProviderStateMixin {
  late final _tabs = TabController(length: 3, vsync: this);

  @override
  void dispose() {
    _tabs.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final societyId = ref.watch(currentUserProvider)?.societyId;
    if (societyId == null) return const Scaffold(body: Center(child: Text('No society context')));
    final broken = ref.watch(brokenLightsProvider(societyId)).valueOrNull?.length ?? 0;
    return AppPage(
      title: 'Lights check',
      bottom: TabBar(controller: _tabs, tabs: [
        const Tab(text: 'Check'),
        Tab(text: broken == 0 ? 'To replace' : 'To replace ($broken)'),
        const Tab(text: 'Report'),
      ]),
      body: TabBarView(controller: _tabs, children: [
        _CheckTab(societyId: societyId),
        _ReplaceTab(societyId: societyId),
        _ReportTab(societyId: societyId),
      ]),
    );
  }
}

// ── Check ────────────────────────────────────────────────────────────────────

class _CheckTab extends ConsumerStatefulWidget {
  final String societyId;
  const _CheckTab({required this.societyId});

  @override
  ConsumerState<_CheckTab> createState() => _CheckTabState();
}

class _CheckTabState extends ConsumerState<_CheckTab> {
  String? _wingId;
  int? _floor;
  String _kind = 'tube';
  // what has been ticked so far: "flatId|location" -> working | not_working
  final Map<String, String> _marks = {};
  bool _saving = false;

  static String _key(String? flatId, String location) => '${flatId ?? ''}|$location';

  void _reset() => _marks.clear();

  Future<void> _save(SheetKey key, LightSheet sheet) async {
    final results = <Map<String, dynamic>>[
      for (final g in sheet.groups)
        for (final p in g.points)
          if (_marks[_key(g.flatId, p.location)] != null)
            {'location': p.location, 'status': _marks[_key(g.flatId, p.location)], if (g.flatId != null) 'flat_id': g.flatId},
    ];
    if (results.isEmpty) return;
    setState(() => _saving = true);
    try {
      final bad = await ref
          .read(lightsApiProvider)
          .check(widget.societyId, wingId: key.wingId, floor: key.floor, kind: key.kind, results: results);
      if (!mounted) return;
      ref.invalidate(lightSheetProvider(key));
      ref.invalidate(brokenLightsProvider(widget.societyId));
      setState(_reset);
      AppToast.success(context, bad == 0 ? 'Saved - all working' : 'Saved - $bad to replace');
    } catch (e) {
      if (mounted) AppToast.error(context, friendlyErrorMessage(e));
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final wings = ref.watch(wingsProvider);
    return wings.when(
      loading: () => const AppLoader(),
      error: (e, _) => AppErrorState(message: friendlyErrorMessage(e), onRetry: () => ref.invalidate(wingsProvider)),
      data: (list) {
        final wingList = list.where((w) => w.isActive).toList();
        if (wingList.isEmpty) {
          return const AppEmptyState(
            icon: Icons.apartment_rounded,
            title: 'No wings yet',
            subtitle: 'Add the wings, floors and flats in the setup wizard first.',
          );
        }
        final floors = _wingId == null
            ? null
            : ref.watch(lightFloorsProvider((societyId: widget.societyId, wingId: _wingId!)));
        final key = (_wingId != null && _floor != null)
            ? (societyId: widget.societyId, wingId: _wingId!, floor: _floor!, kind: _kind)
            : null;
        return ListView(padding: const EdgeInsets.fromLTRB(16, 16, 16, 96), children: [
          DropdownButtonFormField<String>(
            key: const Key('light-wing'),
            value: _wingId,
            decoration: const InputDecoration(labelText: 'Wing'),
            items: [for (final w in wingList) DropdownMenuItem(value: w.id, child: Text(w.name))],
            onChanged: (v) => setState(() {
              _wingId = v;
              _floor = null;
              _reset();
            }),
          ),
          const SizedBox(height: 12),
          if (floors != null)
            floors.when(
              loading: () => const Padding(padding: EdgeInsets.all(12), child: LinearProgressIndicator()),
              error: (e, _) => AppErrorState(
                  compact: true,
                  message: friendlyErrorMessage(e),
                  onRetry: () => ref.invalidate(lightFloorsProvider((societyId: widget.societyId, wingId: _wingId!)))),
              data: (fl) => DropdownButtonFormField<int>(
                key: const Key('light-floor'),
                value: _floor,
                decoration: const InputDecoration(labelText: 'Floor'),
                items: [for (final f in fl) DropdownMenuItem(value: f.number, child: Text(f.name))],
                onChanged: (v) => setState(() {
                  _floor = v;
                  _reset();
                }),
              ),
            ),
          const SizedBox(height: 12),
          Wrap(spacing: 8, runSpacing: 8, children: [
            for (final (value, label) in kLightKinds)
              AppFilterPill(
                  label: label,
                  selected: _kind == value,
                  onTap: () => setState(() {
                        _kind = value;
                        _reset();
                      })),
          ]),
          const SizedBox(height: 16),
          if (key == null)
            const Padding(
              padding: EdgeInsets.only(top: 32),
              child: AppEmptyState(
                icon: Icons.lightbulb_outline_rounded,
                title: 'Choose a wing and a floor',
                subtitle: 'Then mark each light Working or Not working.',
              ),
            )
          else
            ref.watch(lightSheetProvider(key)).when(
                  loading: () => const Padding(padding: EdgeInsets.all(24), child: AppLoader()),
                  error: (e, _) => AppErrorState(
                      compact: true, message: friendlyErrorMessage(e), onRetry: () => ref.invalidate(lightSheetProvider(key))),
                  data: (sheet) => _sheet(key, sheet),
                ),
        ]);
      },
    );
  }

  Widget _sheet(SheetKey key, LightSheet sheet) {
    if (sheet.groups.isEmpty) {
      return const AppEmptyState(
          icon: Icons.meeting_room_outlined, title: 'No flats on this floor', subtitle: 'Add the flats in the setup wizard.');
    }
    final total = sheet.groups.fold<int>(0, (n, g) => n + g.points.length);
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Row(children: [
        Expanded(
            child: Text('${_marks.length} of $total marked',
                style: const TextStyle(fontSize: 13, color: AppTheme.textSecondary, fontWeight: FontWeight.w600))),
        TextButton.icon(
          key: const Key('mark-all-working'),
          onPressed: () => setState(() {
            for (final g in sheet.groups) {
              for (final p in g.points) {
                _marks[_key(g.flatId, p.location)] = _working;
              }
            }
          }),
          icon: const Icon(Icons.done_all_rounded, size: 18),
          label: const Text('Mark all working'),
        ),
      ]),
      for (final g in sheet.groups) _GroupCard(group: g, marks: _marks, keyOf: _key, onChanged: () => setState(() {})),
      const SizedBox(height: 8),
      ElevatedButton.icon(
        key: const Key('save-light-check'),
        onPressed: _marks.isEmpty || _saving ? null : () => _save(key, sheet),
        icon: _saving
            ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2))
            : const Icon(Icons.save_rounded, size: 18),
        label: Text(_saving ? 'Saving…' : 'Save check'),
      ),
    ]);
  }
}

class _GroupCard extends StatelessWidget {
  final LightGroup group;
  final Map<String, String> marks;
  final String Function(String?, String) keyOf;
  final VoidCallback onChanged;
  const _GroupCard({required this.group, required this.marks, required this.keyOf, required this.onChanged});

  @override
  Widget build(BuildContext context) => Container(
        margin: const EdgeInsets.only(bottom: 12),
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          color: AppTheme.cardBg,
          borderRadius: BorderRadius.circular(AppTheme.radiusL),
          border: Border.all(color: AppTheme.border),
        ),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(group.label, style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w800)),
          const SizedBox(height: 6),
          for (final p in group.points) _row(p),
        ]),
      );

  Widget _row(LightCell p) {
    final k = keyOf(group.flatId, p.location);
    final mark = marks[k];
    void set(String v) {
      marks[k] = v;
      onChanged();
    }

    final last = p.lastCheckedAt == null
        ? 'Not checked yet'
        : 'Last: ${p.status == _working ? 'working' : 'not working'} · ${lightStamp(p.lastCheckedAt!)}'
            '${p.lastCheckedBy == null ? '' : ' · ${p.lastCheckedBy}'}';
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text(p.label, style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600)),
        const SizedBox(height: 2),
        Text(last, style: TextStyle(fontSize: 12, color: p.status == _notWorking ? AppTheme.error : AppTheme.textSecondary)),
        const SizedBox(height: 8),
        Row(children: [
          Expanded(
              child: _Bubble(
                  key: Key('${k}_working'),
                  label: 'Working',
                  icon: Icons.check_circle_rounded,
                  color: AppTheme.success,
                  selected: mark == _working,
                  onTap: () => set(_working))),
          const SizedBox(width: 10),
          Expanded(
              child: _Bubble(
                  key: Key('${k}_not_working'),
                  label: 'Not working',
                  icon: Icons.cancel_rounded,
                  color: AppTheme.error,
                  selected: mark == _notWorking,
                  onTap: () => set(_notWorking))),
        ]),
      ]),
    );
  }
}

/// A rounded "bubble" choice button.
class _Bubble extends StatelessWidget {
  final String label;
  final IconData icon;
  final Color color;
  final bool selected;
  final VoidCallback onTap;
  const _Bubble({super.key, required this.label, required this.icon, required this.color, required this.selected, required this.onTap});

  @override
  Widget build(BuildContext context) => Semantics(
        button: true,
        selected: selected,
        label: label,
        child: InkWell(
          onTap: onTap,
          borderRadius: BorderRadius.circular(999),
          child: Container(
            height: 44,
            alignment: Alignment.center,
            decoration: BoxDecoration(
              color: selected ? color : Colors.transparent,
              borderRadius: BorderRadius.circular(999),
              border: Border.all(color: selected ? color : AppTheme.border),
            ),
            child: Row(mainAxisSize: MainAxisSize.min, children: [
              Icon(icon, size: 18, color: selected ? Colors.white : color),
              const SizedBox(width: 6),
              Text(label,
                  style: TextStyle(fontSize: 13, fontWeight: FontWeight.w700, color: selected ? Colors.white : AppTheme.textPrimary)),
            ]),
          ),
        ),
      );
}

// ── Replace ──────────────────────────────────────────────────────────────────

class _ReplaceTab extends ConsumerWidget {
  final String societyId;
  const _ReplaceTab({required this.societyId});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final async = ref.watch(brokenLightsProvider(societyId));
    return RefreshIndicator(
      onRefresh: () async => ref.invalidate(brokenLightsProvider(societyId)),
      child: async.when(
        loading: () => const AppLoader(),
        error: (e, _) =>
            AppErrorState(message: friendlyErrorMessage(e), onRetry: () => ref.invalidate(brokenLightsProvider(societyId))),
        data: (rows) => rows.isEmpty
            ? ListView(children: const [
                SizedBox(height: 60),
                AppEmptyState(
                  icon: Icons.lightbulb_rounded,
                  title: 'Nothing to replace',
                  subtitle: 'Every light checked so far is working.',
                ),
              ])
            : ListView(padding: const EdgeInsets.all(16), children: [
                for (final r in rows) _BrokenCard(societyId: societyId, light: r),
              ]),
      ),
    );
  }
}

class _BrokenCard extends ConsumerWidget {
  final String societyId;
  final BrokenLight light;
  const _BrokenCard({required this.societyId, required this.light});

  @override
  Widget build(BuildContext context, WidgetRef ref) => Container(
        margin: const EdgeInsets.only(bottom: 12),
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          color: AppTheme.cardBg,
          borderRadius: BorderRadius.circular(AppTheme.radiusL),
          border: Border.all(color: AppTheme.error.withOpacity(0.35)),
        ),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(light.label, style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w800)),
          const SizedBox(height: 2),
          Text(light.where, style: const TextStyle(fontSize: 13, color: AppTheme.textSecondary)),
          const SizedBox(height: 4),
          Text(
            light.since == null ? 'Not working' : 'Not working since ${lightStamp(light.since!)}',
            style: const TextStyle(fontSize: 12, color: AppTheme.error, fontWeight: FontWeight.w600),
          ),
          const SizedBox(height: 10),
          ElevatedButton.icon(
            key: Key('replace-${light.id}'),
            onPressed: () => showAppSheet<bool>(
                context: context, builder: (_) => _ReplaceSheet(societyId: societyId, light: light)),
            icon: const Icon(Icons.build_circle_rounded, size: 18),
            label: const Text('Replaced'),
          ),
        ]),
      );
}

class _ReplaceSheet extends ConsumerStatefulWidget {
  final String societyId;
  final BrokenLight light;
  const _ReplaceSheet({required this.societyId, required this.light});

  @override
  ConsumerState<_ReplaceSheet> createState() => _ReplaceSheetState();
}

class _ReplaceSheetState extends ConsumerState<_ReplaceSheet> {
  String? _itemId;
  final _note = TextEditingController();
  bool _busy = false;

  @override
  void dispose() {
    _note.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    setState(() => _busy = true);
    try {
      await ref.read(lightsApiProvider).replace(widget.light.id, itemId: _itemId!, note: _note.text.trim());
      ref.invalidate(brokenLightsProvider(widget.societyId));
      ref.invalidate(storeItemsProvider(widget.societyId));
      if (!mounted) return;
      AppToast.success(context, 'Replaced - taken from the store');
      Navigator.of(context).pop(true);
    } catch (e) {
      if (mounted) {
        setState(() => _busy = false);
        AppToast.error(context, friendlyErrorMessage(e));
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final items = ref.watch(storeItemsProvider(widget.societyId));
    return BillingSheetFrame(
      title: 'Replaced ${widget.light.label.toLowerCase()}',
      subtitle: '${widget.light.where}. One is taken from the store.',
      child: items.when(
        loading: () => const Padding(padding: EdgeInsets.all(24), child: AppLoader()),
        error: (e, _) => AppErrorState(
            compact: true, message: friendlyErrorMessage(e), onRetry: () => ref.invalidate(storeItemsProvider(widget.societyId))),
        data: (all) {
          // electrical things first: tubes and bulbs are kept there
          final sorted = [...all]..sort((a, b) => (a.category == 'electrical' ? 0 : 1).compareTo(b.category == 'electrical' ? 0 : 1));
          if (sorted.isEmpty) {
            return const Text('The store has no items yet. Add the tube or bulb in Stores first.');
          }
          return Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.stretch, children: [
            DropdownButtonFormField<String>(
              key: const Key('replace-item'),
              value: _itemId,
              isExpanded: true,
              decoration: const InputDecoration(labelText: 'Tube or bulb used'),
              items: [
                for (final i in sorted)
                  DropdownMenuItem(value: i.id, child: Text('${i.name} (${_qty(i.stock)} in stock)', overflow: TextOverflow.ellipsis)),
              ],
              onChanged: (v) => setState(() => _itemId = v),
            ),
            const SizedBox(height: 12),
            TextField(controller: _note, decoration: const InputDecoration(labelText: 'Note (optional)')),
            const SizedBox(height: 16),
            ElevatedButton(
              key: const Key('confirm-replace'),
              onPressed: _itemId == null || _busy ? null : _submit,
              child: Text(_busy ? 'Saving…' : 'Mark replaced'),
            ),
          ]);
        },
      ),
    );
  }

  static String _qty(double q) => q == q.roundToDouble() ? q.toInt().toString() : q.toString();
}

// ── Report ───────────────────────────────────────────────────────────────────

/// "November 2026" for a "2026-11" month.
String monthTitle(String month) {
  final p = month.split('-');
  return DateFormat('MMMM yyyy').format(DateTime(int.parse(p[0]), int.parse(p[1])));
}

String _monthKey(DateTime d) => '${d.year.toString().padLeft(4, '0')}-${d.month.toString().padLeft(2, '0')}';

class _ReportTab extends ConsumerStatefulWidget {
  final String societyId;
  const _ReportTab({required this.societyId});

  @override
  ConsumerState<_ReportTab> createState() => _ReportTabState();
}

class _ReportTabState extends ConsumerState<_ReportTab> {
  String? _month; // null: the current month, as the server counts it

  ReportKey get _key => (societyId: widget.societyId, month: _month);

  void _step(LightReport r, int by) {
    final p = r.month.split('-');
    setState(() => _month = _monthKey(DateTime(int.parse(p[0]), int.parse(p[1]) + by)));
  }

  @override
  Widget build(BuildContext context) {
    final async = ref.watch(lightReportProvider(_key));
    return RefreshIndicator(
      onRefresh: () async => ref.invalidate(lightReportProvider(_key)),
      child: async.when(
        loading: () => const AppLoader(),
        error: (e, _) => AppErrorState(message: friendlyErrorMessage(e), onRetry: () => ref.invalidate(lightReportProvider(_key))),
        data: (r) => ListView(padding: const EdgeInsets.fromLTRB(16, 12, 16, 48), children: [
          _monthBar(r),
          const SizedBox(height: 12),
          _tiles(r),
          const SizedBox(height: 12),
          if (r.floors.isEmpty)
            const AppEmptyState(
                icon: Icons.apartment_rounded, title: 'No floors yet', subtitle: 'Add the wings and floors in the setup wizard.')
          else ...[
            if (r.floorsNotChecked > 0 || r.floorsPartlyChecked > 0) _attention(r),
            for (final f in r.floors) _FloorRow(floor: f),
          ],
        ]),
      ),
    );
  }

  Widget _monthBar(LightReport r) => Row(children: [
        IconButton(key: const Key('report-prev'), onPressed: () => _step(r, -1), icon: const Icon(Icons.chevron_left_rounded)),
        Expanded(
            child: Text(monthTitle(r.month),
                textAlign: TextAlign.center, style: const TextStyle(fontSize: 17, fontWeight: FontWeight.w800))),
        // no later than the month the server is in
        IconButton(
            key: const Key('report-next'),
            onPressed: _month == null || _month!.compareTo(_monthKey(DateTime.now())) >= 0 ? null : () => _step(r, 1),
            icon: const Icon(Icons.chevron_right_rounded)),
      ]);

  Widget _tiles(LightReport r) {
    Widget tile(String label, int value, Color color) => Expanded(
          child: Container(
            padding: const EdgeInsets.symmetric(vertical: 12, horizontal: 8),
            decoration: BoxDecoration(
              color: color.withOpacity(0.08),
              borderRadius: BorderRadius.circular(AppTheme.radiusM),
              border: Border.all(color: color.withOpacity(0.3)),
            ),
            child: Column(children: [
              Text('$value', style: TextStyle(fontSize: 22, fontWeight: FontWeight.w800, color: color)),
              const SizedBox(height: 2),
              Text(label, textAlign: TextAlign.center, style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
            ]),
          ),
        );
    return Column(children: [
      Row(children: [
        tile('Checked', r.checked, AppTheme.primary),
        const SizedBox(width: 8),
        tile('Working', r.working, AppTheme.success),
        const SizedBox(width: 8),
        tile('Not working', r.notWorking, AppTheme.error),
        const SizedBox(width: 8),
        tile('Replaced', r.replaced, AppTheme.warning),
      ]),
      if (r.stillNotWorking > 0)
        Padding(
          padding: const EdgeInsets.only(top: 8),
          child: Align(
            alignment: Alignment.centerLeft,
            child: Text('${r.stillNotWorking} light${r.stillNotWorking == 1 ? '' : 's'} still waiting to be replaced',
                style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: AppTheme.error)),
          ),
        ),
    ]);
  }

  Widget _attention(LightReport r) => Container(
        margin: const EdgeInsets.only(bottom: 12),
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: AppTheme.warningSoft,
          borderRadius: BorderRadius.circular(AppTheme.radiusM),
        ),
        child: Row(children: [
          const Icon(Icons.info_outline_rounded, size: 18, color: AppTheme.warning),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              [
                if (r.floorsNotChecked > 0) '${r.floorsNotChecked} floor${r.floorsNotChecked == 1 ? '' : 's'} not checked',
                if (r.floorsPartlyChecked > 0) '${r.floorsPartlyChecked} partly checked',
              ].join(' · '),
              style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600),
            ),
          ),
        ]),
      );
}

class _FloorRow extends StatelessWidget {
  final FloorReport floor;
  const _FloorRow({required this.floor});

  @override
  Widget build(BuildContext context) {
    final (label, color) = switch (floor.status) {
      'done' => ('Done', AppTheme.success),
      'partial' => ('Partly', AppTheme.warning),
      _ => ('Not checked', AppTheme.textSecondary),
    };
    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: AppTheme.cardBg,
        borderRadius: BorderRadius.circular(AppTheme.radiusL),
        border: Border.all(color: AppTheme.border),
      ),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Expanded(
              child: Text('${floor.wingName} · ${floor.floorName}',
                  style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w800))),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
            decoration: BoxDecoration(color: color.withOpacity(0.12), borderRadius: BorderRadius.circular(999)),
            child: Text(label, style: TextStyle(fontSize: 12, fontWeight: FontWeight.w700, color: color)),
          ),
        ]),
        const SizedBox(height: 6),
        Text(
          'Tube lights ${floor.tube.checked}/${floor.tube.expected}'
          '  ·  Spot lights ${floor.spot.checked}/${floor.spot.expected}'
          '${floor.flats == 0 ? '' : ' (${floor.flats} flat${floor.flats == 1 ? '' : 's'})'}',
          style: const TextStyle(fontSize: 13, color: AppTheme.textSecondary),
        ),
        if (floor.notWorking > 0) ...[
          const SizedBox(height: 4),
          Text('${floor.notWorking} not working',
              style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: AppTheme.error)),
        ],
      ]),
    );
  }
}
