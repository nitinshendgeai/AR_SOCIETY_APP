import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/l10n/app_locale.dart';
import 'package:ar_society_app/core/layout/app_sheet.dart';
import 'package:ar_society_app/core/motion/loading.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/core/theme/design_tokens.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/features/lights_check/data/lights_api.dart';
import 'package:ar_society_app/features/lights_check/presentation/widgets/light_detail_sheet.dart';
import 'package:ar_society_app/features/maintenance_billing/presentation/widgets/billing_sheet_frame.dart';
import 'package:ar_society_app/features/society_structure/data/models/structure_models.dart' show FlatModel;
import 'package:ar_society_app/features/society_structure/presentation/providers/structure_providers.dart';
import 'package:ar_society_app/features/stores/presentation/providers/stores_providers.dart';
import 'package:ar_society_app/shared/widgets/app_form.dart' show AppPage;
import 'package:ar_society_app/shared/widgets/app_status.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';

// `lightStamp` lives with the light models; re-exported so existing imports of this screen still find it.
export 'package:ar_society_app/features/lights_check/data/lights_api.dart' show lightStamp;

const _working = 'working';
const _notWorking = 'not_working';


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
  bool _areasMode = false; // floors and flats, or the common areas
  String? _wingId, _areaId;
  int? _floor;
  String _kind = 'tube';
  // what has been ticked so far: "flatId|location" -> working | not_working
  final Map<String, String> _marks = {};
  bool _saving = false;

  static String _key(String? flatId, String location) => '${flatId ?? ''}|$location';

  void _reset() => _marks.clear();

  /// Saves what has been ticked on [sheet] with [post] (which returns how many were not working), then reloads with [refresh].
  Future<void> _save(LightSheet sheet, Future<int> Function(List<Map<String, dynamic>> results) post, VoidCallback refresh) async {
    final results = <Map<String, dynamic>>[
      for (final g in sheet.groups)
        for (final p in g.points)
          if (_marks[_key(g.flatId, p.location)] != null)
            {'location': p.location, 'status': _marks[_key(g.flatId, p.location)], if (g.flatId != null) 'flat_id': g.flatId},
    ];
    if (results.isEmpty) return;
    setState(() => _saving = true);
    try {
      final bad = await post(results);
      if (!mounted) return;
      refresh();
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
    return ListView(padding: const EdgeInsets.fromLTRB(16, 16, 16, 96), children: [
      Wrap(spacing: 8, runSpacing: 8, children: [
        AppFilterPill(
            label: 'Floors and flats',
            selected: !_areasMode,
            onTap: () => setState(() {
                  _areasMode = false;
                  _reset();
                })),
        AppFilterPill(
            label: 'Common areas',
            selected: _areasMode,
            onTap: () => setState(() {
                  _areasMode = true;
                  _reset();
                })),
      ]),
      const SizedBox(height: 16),
      ..._areasMode ? _areaChildren() : _floorChildren(),
    ]);
  }

  // ── Floors and flats ──

  List<Widget> _floorChildren() {
    final wings = ref.watch(wingsProvider);
    return wings.when(
      loading: () => [const Padding(padding: EdgeInsets.all(24), child: AppLoader())],
      error: (e, _) => [AppErrorState(compact: true, message: friendlyErrorMessage(e), onRetry: () => ref.invalidate(wingsProvider))],
      data: (list) {
        final wingList = list.where((w) => w.isActive).toList();
        if (wingList.isEmpty) {
          return [
            const AppEmptyState(
              icon: Icons.apartment_rounded,
              title: 'No wings yet',
              subtitle: 'Add the wings, floors and flats in the setup wizard first.',
            )
          ];
        }
        final floors = _wingId == null ? null : ref.watch(lightFloorsProvider((societyId: widget.societyId, wingId: _wingId!)));
        final key = (_wingId != null && _floor != null)
            ? (societyId: widget.societyId, wingId: _wingId!, floor: _floor!, kind: _kind)
            : null;
        return [
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
                  data: (sheet) => _sheet(
                    sheet,
                    emptyTitle: 'No flats on this floor',
                    emptySubtitle: 'Add the flats in the setup wizard.',
                    post: (r) => ref
                        .read(lightsApiProvider)
                        .check(widget.societyId, wingId: key.wingId, floor: key.floor, kind: key.kind, results: r),
                    refresh: () => ref.invalidate(lightSheetProvider(key)),
                  ),
                ),
        ];
      },
    );
  }

  // ── Common areas ──

  List<Widget> _areaChildren() {
    final user = ref.watch(currentUserProvider);
    final canSetUp = user != null && (user.isManager || user.isAdminOrCommittee);
    return ref.watch(lightAreasProvider(widget.societyId)).when(
          loading: () => [const Padding(padding: EdgeInsets.all(24), child: AppLoader())],
          error: (e, _) => [
            AppErrorState(
                compact: true, message: friendlyErrorMessage(e), onRetry: () => ref.invalidate(lightAreasProvider(widget.societyId)))
          ],
          data: (areas) {
            final id = areas.any((a) => a.id == _areaId) ? _areaId : null;
            return [
              if (areas.isNotEmpty)
                DropdownButtonFormField<String>(
                  key: const Key('light-area'),
                  value: id,
                  isExpanded: true,
                  decoration: const InputDecoration(labelText: 'Area'),
                  items: [
                    for (final a in areas)
                      DropdownMenuItem(value: a.id, child: Text(a.name, overflow: TextOverflow.ellipsis)),
                  ],
                  onChanged: (v) => setState(() {
                    _areaId = v;
                    _reset();
                  }),
                ),
              if (canSetUp)
                Align(
                  alignment: Alignment.centerRight,
                  child: TextButton.icon(
                    key: const Key('manage-areas'),
                    onPressed: () => showAppSheet<void>(context: context, builder: (_) => _ManageAreasSheet(societyId: widget.societyId)),
                    icon: const Icon(Icons.tune_rounded, size: 18),
                    label: const Text('Set up areas'),
                  ),
                ),
              const SizedBox(height: 8),
              if (areas.isEmpty)
                AppEmptyState(
                  icon: Icons.local_parking_rounded,
                  title: 'No common areas yet',
                  subtitle: canSetUp
                      ? 'Tap "Set up areas" to add Parking, Lobby, Gym, Podium and the rest, with what each has.'
                      : 'The Manager or Admin sets up the common areas first.',
                )
              else if (id == null)
                const AppEmptyState(
                  icon: Icons.lightbulb_outline_rounded,
                  title: 'Choose an area',
                  subtitle: 'Then mark each light and camera Working or Not working.',
                )
              else
                ref.watch(lightAreaSheetProvider(id)).when(
                      loading: () => const Padding(padding: EdgeInsets.all(24), child: AppLoader()),
                      error: (e, _) => AppErrorState(
                          compact: true, message: friendlyErrorMessage(e), onRetry: () => ref.invalidate(lightAreaSheetProvider(id))),
                      data: (sheet) => _sheet(
                        sheet,
                        emptyTitle: 'Nothing to check here',
                        emptySubtitle: 'Add lights or cameras to this area in "Set up areas".',
                        post: (r) => ref.read(lightsApiProvider).checkArea(id, r),
                        refresh: () => ref.invalidate(lightAreaSheetProvider(id)),
                      ),
                    ),
            ];
          },
        );
  }

  Widget _sheet(
    LightSheet sheet, {
    required String emptyTitle,
    required String emptySubtitle,
    required Future<int> Function(List<Map<String, dynamic>> results) post,
    required VoidCallback refresh,
  }) {
    if (sheet.groups.isEmpty) {
      return AppEmptyState(icon: Icons.meeting_room_outlined, title: emptyTitle, subtitle: emptySubtitle);
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
        onPressed: _marks.isEmpty || _saving ? null : () => _save(sheet, post, refresh),
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
          boxShadow: AppTheme.cardShadow,
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

  /// A camera that was put right needs no tube or bulb from the store.
  bool get _isCamera => widget.light.kind == 'camera';

  @override
  void dispose() {
    _note.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    setState(() => _busy = true);
    try {
      await ref.read(lightsApiProvider).replace(widget.light.id, itemId: _itemId, note: _note.text.trim());
      ref.invalidate(brokenLightsProvider(widget.societyId));
      ref.invalidate(storeItemsProvider(widget.societyId));
      if (!mounted) return;
      AppToast.success(context, _itemId == null ? 'Marked working' : 'Replaced - taken from the store');
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
      subtitle: _isCamera ? '${widget.light.where}.' : '${widget.light.where}. One is taken from the store.',
      child: items.when(
        loading: () => const Padding(padding: EdgeInsets.all(24), child: AppLoader()),
        error: (e, _) => AppErrorState(
            compact: true, message: friendlyErrorMessage(e), onRetry: () => ref.invalidate(storeItemsProvider(widget.societyId))),
        data: (all) {
          // electrical things first: tubes and bulbs are kept there
          final sorted = [...all]..sort((a, b) => (a.category == 'electrical' ? 0 : 1).compareTo(b.category == 'electrical' ? 0 : 1));
          if (sorted.isEmpty && !_isCamera) {
            return const Text('The store has no items yet. Add the tube or bulb in Stores first.');
          }
          return Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.stretch, children: [
            DropdownButtonFormField<String>(
              key: const Key('replace-item'),
              value: _itemId,
              isExpanded: true,
              decoration: InputDecoration(labelText: _isCamera ? 'Spare used from the store (optional)' : 'Tube or bulb used'),
              items: [
                if (_isCamera) const DropdownMenuItem<String>(value: null, child: Text('None - put right')),
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
              onPressed: (_itemId == null && !_isCamera) || _busy ? null : _submit,
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
  String? _wingId, _flatId;
  int? _floor;

  ReportKey get _key => (societyId: widget.societyId, month: _month, wingId: _wingId, floor: _floor, flatId: _flatId);

  /// Whether [shown] is the month the server counts as the current one (the sheet only knows how lights stand now).
  bool _isCurrent(String shown) => _month == null || shown == _monthKey(DateTime.now());

  /// Opens a floor's lights.
  void _openFloor(FloorReport f, String shown) {
    showFloorDetail(context,
        societyId: widget.societyId,
        wingId: f.wingId,
        floor: f,
        monthLabel: monthTitle(shown),
        currentMonth: _isCurrent(shown));
  }

  void _step(String shown, int by) {
    final p = shown.split('-');
    setState(() => _month = _monthKey(DateTime(int.parse(p[0]), int.parse(p[1]) + by)));
  }

  @override
  Widget build(BuildContext context) {
    final async = ref.watch(lightReportProvider(_key));
    // The month bar and the filters stay on screen while a changed filter or month reloads the report below them.
    final shown = async.valueOrNull?.month ?? _month ?? _monthKey(DateTime.now());
    return RefreshIndicator(
      onRefresh: () async => ref.invalidate(lightReportProvider(_key)),
      child: ListView(padding: const EdgeInsets.fromLTRB(16, 12, 16, 48), children: [
        _monthBar(shown),
        const SizedBox(height: 4),
        _filters(),
        const SizedBox(height: 12),
        ...async.when(
          loading: () => [const Padding(padding: EdgeInsets.all(32), child: AppLoader())],
          error: (e, _) => [
            AppErrorState(compact: true, message: friendlyErrorMessage(e), onRetry: () => ref.invalidate(lightReportProvider(_key))),
          ],
          data: (r) => [
            _tiles(r),
            const SizedBox(height: 12),
            if (r.flatLabel != null) _FlatCard(label: r.flatLabel!, lights: r.flatLights),
            if (r.floors.isEmpty && r.areas.isEmpty)
              const AppEmptyState(
                  icon: Icons.apartment_rounded, title: 'No floors yet', subtitle: 'Add the wings and floors in the setup wizard.')
            else ...[
              if (r.floorsNotChecked + r.floorsPartlyChecked + r.areasNotChecked + r.areasPartlyChecked > 0) _attention(r),
              for (final f in r.floors) _FloorRow(floor: f, onTap: () => _openFloor(f, shown)),
              if (r.areas.isNotEmpty) ...[
                const Padding(
                  padding: EdgeInsets.only(top: 8, bottom: 8),
                  child: Text('Common areas', style: TextStyle(fontSize: 13, fontWeight: FontWeight.w700, color: AppTheme.textSecondary)),
                ),
                for (final a in r.areas)
                  _AreaRow(
                      area: a,
                      onTap: () => showAreaDetail(context, area: a, monthLabel: monthTitle(shown), currentMonth: _isCurrent(shown))),
              ],
            ],
          ],
        ),
      ]),
    );
  }

  /// Wing, then a floor of it, then a flat on that floor; each one narrows the report and resets the ones after it.
  Widget _filters() {
    final wings = (ref.watch(wingsProvider).valueOrNull ?? const []).where((w) => w.isActive).toList();
    final floors = _wingId == null
        ? const <FloorOption>[]
        : ref.watch(lightFloorsProvider((societyId: widget.societyId, wingId: _wingId!))).valueOrNull ?? const <FloorOption>[];
    final List<FlatModel> flats = (_wingId == null || _floor == null)
        ? const <FlatModel>[]
        : (ref.watch(flatsByWingProvider(_wingId!)).valueOrNull ?? const <FlatModel>[]).where((f) => f.floor == _floor).toList();
    final any = _wingId != null;
    return Column(children: [
      Row(children: [
        Expanded(
          child: DropdownButtonFormField<String?>(
            key: const Key('report-wing'),
            value: wings.any((w) => w.id == _wingId) ? _wingId : null,
            isExpanded: true,
            decoration: const InputDecoration(labelText: 'Wing'),
            items: [
              const DropdownMenuItem<String?>(value: null, child: Text('All wings')),
              for (final w in wings) DropdownMenuItem<String?>(value: w.id, child: Text(w.name, overflow: TextOverflow.ellipsis)),
            ],
            onChanged: (v) => setState(() {
              _wingId = v;
              _floor = null;
              _flatId = null;
            }),
          ),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: DropdownButtonFormField<int?>(
            key: const Key('report-floor'),
            value: floors.any((f) => f.number == _floor) ? _floor : null,
            isExpanded: true,
            decoration: const InputDecoration(labelText: 'Floor'),
            items: [
              const DropdownMenuItem<int?>(value: null, child: Text('All floors')),
              for (final f in floors) DropdownMenuItem<int?>(value: f.number, child: Text(f.name, overflow: TextOverflow.ellipsis)),
            ],
            onChanged: _wingId == null
                ? null
                : (v) => setState(() {
                      _floor = v;
                      _flatId = null;
                    }),
          ),
        ),
      ]),
      if (_floor != null) ...[
        const SizedBox(height: 12),
        DropdownButtonFormField<String?>(
          key: const Key('report-flat'),
          value: flats.any((f) => f.id == _flatId) ? _flatId : null,
          isExpanded: true,
          decoration: const InputDecoration(labelText: 'Flat'),
          items: [
            const DropdownMenuItem<String?>(value: null, child: Text('All flats')),
            for (final f in flats) DropdownMenuItem<String?>(value: f.id, child: Text('Flat ${f.flatNumber}')),
          ],
          onChanged: (v) => setState(() => _flatId = v),
        ),
      ],
      if (any)
        Align(
          alignment: Alignment.centerRight,
          child: TextButton(
            key: const Key('report-clear'),
            onPressed: () => setState(() {
              _wingId = null;
              _floor = null;
              _flatId = null;
            }),
            child: const Text('Clear filters'),
          ),
        ),
    ]);
  }

  Widget _monthBar(String shown) => Row(children: [
        IconButton(key: const Key('report-prev'), onPressed: () => _step(shown, -1), icon: const Icon(Icons.chevron_left_rounded)),
        Expanded(
            child: Text(monthTitle(shown),
                textAlign: TextAlign.center, style: const TextStyle(fontSize: 17, fontWeight: FontWeight.w800))),
        // no later than the month the server is in
        IconButton(
            key: const Key('report-next'),
            onPressed: shown.compareTo(_monthKey(DateTime.now())) >= 0 ? null : () => _step(shown, 1),
            icon: const Icon(Icons.chevron_right_rounded)),
      ]);

  Widget _tiles(LightReport r) {
    // The tint and outline use the bright colour; the number uses the readable tone of the same meaning.
    Widget tile(String label, int value, Color color, AppTone tone) => Expanded(
          child: Container(
            padding: const EdgeInsets.symmetric(vertical: 12, horizontal: 8),
            decoration: BoxDecoration(
              color: color.withOpacity(0.08),
              borderRadius: BorderRadius.circular(AppTheme.radiusM),
              border: Border.all(color: color.withOpacity(0.3)),
            ),
            child: Column(children: [
              Text('$value',
                  style: TextStyle(fontSize: 22, fontWeight: FontWeight.w800, color: kToneColors[tone]!.foreground)),
              const SizedBox(height: 2),
              Text(label, textAlign: TextAlign.center, style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
            ]),
          ),
        );
    return Column(children: [
      // Equal-height tiles: "Not working" wraps to two lines on a narrow phone and would otherwise stand taller.
      IntrinsicHeight(
        child: Row(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          tile('Checked', r.checked, AppTheme.primary, AppTone.info),
          const SizedBox(width: 8),
          tile('Working', r.working, AppTheme.success, AppTone.success),
          const SizedBox(width: 8),
          tile('Not working', r.notWorking, AppTheme.error, AppTone.danger),
          const SizedBox(width: 8),
          tile('Replaced', r.replaced, AppTheme.warning, AppTone.warning),
        ]),
      ),
      if (r.stillNotWorking > 0)
        Padding(
          padding: const EdgeInsets.only(top: 8),
          child: Align(
            alignment: Alignment.centerLeft,
            child: Text('${r.stillNotWorking} light${r.stillNotWorking == 1 ? '' : 's'} still waiting to be replaced',
                style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: kToneColors[AppTone.danger]!.foreground)),
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
                if (r.areasNotChecked > 0) '${r.areasNotChecked} area${r.areasNotChecked == 1 ? '' : 's'} not checked',
                if (r.areasPartlyChecked > 0) '${r.areasPartlyChecked} area${r.areasPartlyChecked == 1 ? '' : 's'} partly checked',
              ].join(' · '),
              style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600),
            ),
          ),
        ]),
      );
}

/// A report card that opens its detail: the card is one outer box (colour and outline) with the ink on a transparent
/// Material inside it, and reads as a button to a screen reader.
class _TapCard extends StatelessWidget {
  final VoidCallback onTap;
  final String semanticLabel;
  final Widget child;
  const _TapCard({required this.onTap, required this.semanticLabel, required this.child});

  @override
  Widget build(BuildContext context) => Semantics(
        button: true,
        label: '$semanticLabel. ${context.tr('Opens the lights')}',
        excludeSemantics: true,
        onTap: onTap,
        child: Container(
          margin: const EdgeInsets.only(bottom: 10),
          decoration: BoxDecoration(
            color: AppTheme.cardBg,
            borderRadius: BorderRadius.circular(AppTheme.radiusL),
            boxShadow: AppTheme.cardShadow,
          ),
          child: Material(
            type: MaterialType.transparency,
            child: InkWell(
              borderRadius: BorderRadius.circular(AppTheme.radiusL),
              onTap: onTap,
              child: Padding(padding: const EdgeInsets.all(14), child: child),
            ),
          ),
        ),
      );
}

class _FloorRow extends StatelessWidget {
  final FloorReport floor;
  final VoidCallback onTap;
  const _FloorRow({required this.floor, required this.onTap});

  @override
  Widget build(BuildContext context) {
    final (label, tone) = switch (floor.status) {
      'done' => ('Done', AppTone.success),
      'partial' => ('Partly', AppTone.warning),
      _ => ('Not checked', AppTone.neutral),
    };
    return _TapCard(
      onTap: onTap,
      semanticLabel: '${floor.wingName} · ${floor.floorName}, $label'
          '${floor.notWorking > 0 ? ', ${floor.notWorking} not working' : ''}',
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Expanded(
              child: Text('${floor.wingName} · ${floor.floorName}',
                  style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w800))),
          AppStatusChip(label: label, tone: tone),
          const SizedBox(width: 4),
          const Icon(Icons.chevron_right_rounded, color: AppTheme.textSecondary),
        ]),
        const SizedBox(height: 6),
        Text(
          'Tube lights ${floor.tube.checked}/${floor.tube.expected}'
          '  ·  Spot lights ${floor.spot.checked}/${floor.spot.expected}'
          '${floor.flats == 0 ? '' : ' (${floor.flats} flat${floor.flats == 1 ? '' : 's'})'}'
          '${floor.camera.expected == 0 ? '' : '  ·  Camera ${floor.camera.checked}/${floor.camera.expected}'}',
          style: const TextStyle(fontSize: 13, color: AppTheme.textSecondary),
        ),
        if (floor.notWorking > 0) ...[
          const SizedBox(height: 4),
          Text('${floor.notWorking} not working',
              style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: kToneColors[AppTone.danger]!.foreground)),
        ],
      ]),
    );
  }
}

/// The three spot lights of the flat the report is narrowed to, as they stood at the end of the month.
class _FlatCard extends StatelessWidget {
  final String label;
  final List<FlatLight> lights;
  const _FlatCard({required this.label, required this.lights});

  @override
  Widget build(BuildContext context) => Container(
        margin: const EdgeInsets.only(bottom: 12),
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          color: AppTheme.cardBg,
          borderRadius: BorderRadius.circular(AppTheme.radiusL),
          boxShadow: AppTheme.cardShadow,
        ),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text('Flat $label', style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w800)),
          for (final l in lights)
            Padding(
              padding: const EdgeInsets.only(top: 8),
              child: Row(children: [
                Expanded(child: Text(l.label, style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600))),
                Text(
                  switch (l.status) {
                    'working' => 'Working',
                    'not_working' => 'Not working',
                    _ => 'Not checked',
                  },
                  style: TextStyle(
                    fontSize: 13,
                    fontWeight: FontWeight.w700,
                    color: switch (l.status) {
                      'working' => AppTheme.success,
                      'not_working' => AppTheme.error,
                      _ => AppTheme.textSecondary,
                    },
                  ),
                ),
                if (l.checkedAt != null) ...[
                  const SizedBox(width: 8),
                  Text(lightStamp(l.checkedAt!), style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
                ],
              ]),
            ),
        ]),
      );
}

// ── Setting up the common areas (Manager / Admin) ────────────────────────────

void _refreshAreas(WidgetRef ref, String societyId) {
  ref.invalidate(lightAreasProvider(societyId));
  ref.invalidate(lightAreaSheetProvider);
  ref.invalidate(brokenLightsProvider(societyId));
  ref.invalidate(lightReportProvider);
}

class _ManageAreasSheet extends ConsumerWidget {
  final String societyId;
  const _ManageAreasSheet({required this.societyId});

  Future<void> _confirmDelete(BuildContext context, WidgetRef ref, CommonAreaInfo a) async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (dialog) => AlertDialog(
        title: Text('Remove ${a.name}?'),
        content: const Text('It leaves the lists and the report. What was checked before is kept.'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(dialog, false), child: const Text('Keep')),
          TextButton(key: const Key('confirm-remove-area'), onPressed: () => Navigator.pop(dialog, true), child: const Text('Remove')),
        ],
      ),
    );
    if (ok != true) return;
    try {
      await ref.read(lightsApiProvider).deleteArea(a.id);
      _refreshAreas(ref, societyId);
      if (context.mounted) AppToast.success(context, '${a.name} removed');
    } catch (e) {
      if (context.mounted) AppToast.error(context, friendlyErrorMessage(e));
    }
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final async = ref.watch(lightAreasProvider(societyId));
    return BillingSheetFrame(
      title: 'Common areas',
      subtitle: 'Say what each area has. The staff then check it every month.',
      child: async.when(
        loading: () => const Padding(padding: EdgeInsets.all(24), child: AppLoader()),
        error: (e, _) => AppErrorState(
            compact: true, message: friendlyErrorMessage(e), onRetry: () => ref.invalidate(lightAreasProvider(societyId))),
        data: (areas) => Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          for (final a in areas)
            ListTile(
              contentPadding: EdgeInsets.zero,
              title: Text(a.name, style: const TextStyle(fontWeight: FontWeight.w700)),
              subtitle: Text([a.summary, if (a.wingName != null) a.wingName!].join(' · ')),
              trailing: Row(mainAxisSize: MainAxisSize.min, children: [
                IconButton(
                    key: Key('edit-area-${a.id}'),
                    icon: const Icon(Icons.edit_rounded),
                    onPressed: () => showAppSheet<void>(
                        context: context, builder: (_) => _AreaFormSheet(societyId: societyId, area: a))),
                IconButton(
                    key: Key('remove-area-${a.id}'),
                    icon: const Icon(Icons.delete_outline_rounded),
                    onPressed: () => _confirmDelete(context, ref, a)),
              ]),
            ),
          if (areas.isEmpty)
            const Padding(
              padding: EdgeInsets.symmetric(vertical: 12),
              child: Text('No areas yet. Add Parking, Lobby, Gym, Podium or Refuse Area.',
                  style: TextStyle(color: AppTheme.textSecondary)),
            ),
          const SizedBox(height: 8),
          ElevatedButton.icon(
            key: const Key('add-area'),
            onPressed: () =>
                showAppSheet<void>(context: context, builder: (_) => _AreaFormSheet(societyId: societyId)),
            icon: const Icon(Icons.add_rounded, size: 18),
            label: const Text('Add an area'),
          ),
        ]),
      ),
    );
  }
}

/// One area: its name, the wing it belongs to (if any), and how many of each light or camera it has.
class _AreaFormSheet extends ConsumerStatefulWidget {
  final String societyId;
  final CommonAreaInfo? area;
  const _AreaFormSheet({required this.societyId, this.area});

  @override
  ConsumerState<_AreaFormSheet> createState() => _AreaFormSheetState();
}

class _AreaFormSheetState extends ConsumerState<_AreaFormSheet> {
  late final _name = TextEditingController(text: widget.area?.name);
  late String? _wingId = widget.area?.wingId;
  late final Map<String, int> _counts = {for (final (kind, _) in kAreaKinds) kind: widget.area?.countOf(kind) ?? 0};
  bool _busy = false;

  @override
  void dispose() {
    _name.dispose();
    super.dispose();
  }

  bool get _valid => _name.text.trim().length >= 2 && _counts.values.any((n) => n > 0);

  Future<void> _save() async {
    setState(() => _busy = true);
    final items = [
      for (final (kind, _) in kAreaKinds)
        if ((_counts[kind] ?? 0) > 0) AreaItem(kind, _counts[kind]!),
    ];
    try {
      final api = ref.read(lightsApiProvider);
      if (widget.area == null) {
        await api.createArea(widget.societyId, name: _name.text.trim(), wingId: _wingId, items: items);
      } else {
        await api.updateArea(widget.area!.id, name: _name.text.trim(), wingId: _wingId, items: items);
      }
      _refreshAreas(ref, widget.societyId);
      if (!mounted) return;
      AppToast.success(context, widget.area == null ? 'Area added' : 'Area saved');
      Navigator.of(context).pop();
    } catch (e) {
      if (mounted) {
        setState(() => _busy = false);
        AppToast.error(context, friendlyErrorMessage(e));
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final wings = (ref.watch(wingsProvider).valueOrNull ?? const []).where((w) => w.isActive).toList();
    return BillingSheetFrame(
      title: widget.area == null ? 'Add an area' : 'Change ${widget.area!.name}',
      subtitle: 'A lobby in every wing is one area per wing, for example "Lobby - Wing A".',
      child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        TextField(
          key: const Key('area-name'),
          controller: _name,
          textCapitalization: TextCapitalization.words,
          decoration: const InputDecoration(labelText: 'Name', hintText: 'Parking'),
          onChanged: (_) => setState(() {}),
        ),
        const SizedBox(height: 12),
        if (wings.isNotEmpty)
          DropdownButtonFormField<String?>(
            key: const Key('area-wing'),
            value: wings.any((w) => w.id == _wingId) ? _wingId : null,
            isExpanded: true,
            decoration: const InputDecoration(labelText: 'Wing (if it belongs to one)'),
            items: [
              const DropdownMenuItem<String?>(value: null, child: Text('Whole society')),
              for (final w in wings) DropdownMenuItem<String?>(value: w.id, child: Text(w.name)),
            ],
            onChanged: (v) => setState(() => _wingId = v),
          ),
        const SizedBox(height: 12),
        const Text('How many are there?', style: TextStyle(fontWeight: FontWeight.w700)),
        for (final (kind, label) in kAreaKinds)
          Padding(
            padding: const EdgeInsets.only(top: 4),
            child: Row(children: [
              Expanded(child: Text(label)),
              IconButton(
                  key: Key('less-$kind'),
                  icon: const Icon(Icons.remove_circle_outline_rounded),
                  onPressed: (_counts[kind] ?? 0) == 0 ? null : () => setState(() => _counts[kind] = _counts[kind]! - 1)),
              SizedBox(
                  width: 32,
                  child: Text('${_counts[kind]}', textAlign: TextAlign.center, style: const TextStyle(fontWeight: FontWeight.w800))),
              IconButton(
                  key: Key('more-$kind'),
                  icon: const Icon(Icons.add_circle_outline_rounded),
                  onPressed: (_counts[kind] ?? 0) >= 100 ? null : () => setState(() => _counts[kind] = _counts[kind]! + 1)),
            ]),
          ),
        const SizedBox(height: 16),
        ElevatedButton(
          key: const Key('save-area'),
          onPressed: _valid && !_busy ? _save : null,
          child: Text(_busy ? 'Saving…' : 'Save'),
        ),
      ]),
    );
  }
}

class _AreaRow extends StatelessWidget {
  final AreaReport area;
  final VoidCallback onTap;
  const _AreaRow({required this.area, required this.onTap});

  @override
  Widget build(BuildContext context) {
    final (label, tone) = switch (area.status) {
      'done' => ('Done', AppTone.success),
      'partial' => ('Partly', AppTone.warning),
      _ => ('Not checked', AppTone.neutral),
    };
    return _TapCard(
      onTap: onTap,
      semanticLabel: '${area.wingName == null ? area.name : '${area.name} · ${area.wingName}'}, $label'
          '${area.notWorking > 0 ? ', ${area.notWorking} not working' : ''}',
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Expanded(
              child: Text(area.wingName == null ? area.name : '${area.name} · ${area.wingName}',
                  style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w800))),
          AppStatusChip(label: label, tone: tone),
          const SizedBox(width: 4),
          const Icon(Icons.chevron_right_rounded, color: AppTheme.textSecondary),
        ]),
        const SizedBox(height: 6),
        Text(
          [for (final i in area.items) '${i.label} ${i.part.checked}/${i.part.expected}'].join('  ·  '),
          style: const TextStyle(fontSize: 13, color: AppTheme.textSecondary),
        ),
        if (area.notWorking > 0) ...[
          const SizedBox(height: 4),
          Text('${area.notWorking} not working',
              style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: kToneColors[AppTone.danger]!.foreground)),
        ],
      ]),
    );
  }
}
