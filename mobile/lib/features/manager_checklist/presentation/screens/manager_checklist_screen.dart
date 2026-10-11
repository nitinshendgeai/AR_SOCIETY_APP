import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/layout/app_shell.dart' show isDesktopLayout;
import 'package:ar_society_app/core/layout/app_sheet.dart';
import 'package:ar_society_app/core/motion/loading.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/accounts/presentation/widgets/accounts_widgets.dart' show PdfActions;
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/features/manager_checklist/data/checklist_api.dart';
import 'package:ar_society_app/features/manager_checklist/presentation/widgets/checklist_sheets.dart';
import 'package:ar_society_app/features/manager_checklist/presentation/widgets/checklist_widgets.dart';
import 'package:ar_society_app/shared/widgets/app_data_table.dart';
import 'package:ar_society_app/shared/widgets/app_form.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';

/// The society manager's daily work in one place: today's routine (by what the society has — its assets and its
/// staff), what the records say needs attention, the statutory dates, and the list itself.
class ManagerChecklistScreen extends ConsumerStatefulWidget {
  const ManagerChecklistScreen({super.key});

  @override
  ConsumerState<ManagerChecklistScreen> createState() => _ManagerChecklistScreenState();
}

class _ManagerChecklistScreenState extends ConsumerState<ManagerChecklistScreen> with SingleTickerProviderStateMixin {
  late final _tabs = TabController(length: 3, vsync: this);

  @override
  void initState() {
    super.initState();
    _tabs.addListener(() {
      if (!_tabs.indexIsChanging) setState(() {});
    });
  }

  @override
  void dispose() {
    _tabs.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final societyId = ref.watch(currentUserProvider)?.societyId;
    if (societyId == null) return const Scaffold(body: Center(child: Text('No society context')));
    final today = ref.watch(todayChecklistProvider(societyId)).valueOrNull;
    final desktop = isDesktopLayout(context);
    final onItems = _tabs.index == 2;

    Future<void> addItem() async {
      final options = await ref.read(checklistItemsProvider(societyId).future);
      if (!context.mounted) return;
      await showAppSheet(context: context, builder: (_) => ItemFormSheet(societyId: societyId, options: options));
    }

    return AppPage(
      title: "Manager's Checklist",
      subtitle: today == null ? 'Your daily work, by your assets and staff' : dayName(today.asOf),
      actions: [
        PdfActions(
          load: today == null ? null : () => ref.read(checklistApiProvider).todayPdf(societyId),
          fileName: 'Manager-Checklist.pdf',
          subject: "Manager's daily checklist",
        ),
        if (desktop && onItems) HeaderActionButton(icon: Icons.add_rounded, label: 'Add item', onPressed: addItem),
      ],
      bottom: TabBar(controller: _tabs, tabs: const [Tab(text: 'Today'), Tab(text: 'Compliance'), Tab(text: 'The list')]),
      floatingActionButton: !desktop && onItems
          ? FloatingActionButton.extended(onPressed: addItem, icon: const Icon(Icons.add_rounded), label: const Text('Add item'))
          : null,
      body: TabBarView(controller: _tabs, children: [
        _TodayTab(societyId: societyId),
        _ComplianceTab(societyId: societyId),
        _ListTab(societyId: societyId),
      ]),
    );
  }
}

Widget _error(Object e) =>
    ListView(padding: const EdgeInsets.all(24), children: [Text(friendlyErrorMessage(e), style: const TextStyle(color: AppTheme.error))]);

// ── Today ────────────────────────────────────────────────────────────────────

class _TodayTab extends ConsumerWidget {
  final String societyId;
  const _TodayTab({required this.societyId});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final async = ref.watch(todayChecklistProvider(societyId));
    return RefreshIndicator(
      onRefresh: () async => ref.invalidate(todayChecklistProvider(societyId)),
      child: async.when(
        loading: () => const AppLoader(),
        error: (e, _) => _error(e),
        data: (t) {
          final groups = [
            ('daily', 'Daily routine'),
            ('periodic', 'Due this week or month'),
            ('compliance', 'Statutory and compliance dates'),
          ];
          return ResponsiveBody(
            maxWidth: 900,
            child: ListView(padding: const EdgeInsets.fromLTRB(16, 12, 16, 96), children: [
              _ProgressCard(today: t, societyId: societyId),
              if (!t.jurisdiction.statePackLoaded) ...[const SizedBox(height: 12), JurisdictionNote(t.jurisdiction)],
              if (t.live.isNotEmpty) ...[
                const SectionTitle('Needs your attention', trailing: 'from your records'),
                ChecklistCard(
                  padding: EdgeInsets.zero,
                  child: Column(children: [
                    for (final (i, l) in t.live.indexed) ...[
                      if (i > 0) const Divider(height: 1),
                      _LiveTile(line: l, societyId: societyId),
                    ],
                  ]),
                ),
              ] else ...[
                const SizedBox(height: 12),
                const ChecklistCard(
                  child: Row(children: [
                    Icon(Icons.check_circle_rounded, color: AppTheme.success),
                    SizedBox(width: 10),
                    Expanded(child: Text('Nothing is flagged from your records right now.')),
                  ]),
                ),
              ],
              for (final (key, label) in groups)
                if (t.items.any((i) => i.group == key)) ...[
                  SectionTitle(label,
                      trailing: '${t.items.where((i) => i.group == key && i.isDone).length} of ${t.items.where((i) => i.group == key).length}'),
                  ChecklistCard(
                    padding: EdgeInsets.zero,
                    child: Column(children: [
                      for (final (i, item) in t.items.where((i) => i.group == key).toList().indexed) ...[
                        if (i > 0) const Divider(height: 1),
                        ItemTile(entry: item, societyId: societyId),
                      ],
                    ]),
                  ),
                ],
              if (t.summary.complianceUnrecorded + t.summary.complianceUnconfirmed > 0) ...[
                const SizedBox(height: 12),
                ChecklistCard(
                  child: Row(children: [
                    const Icon(Icons.assignment_late_rounded, color: AppTheme.warning),
                    const SizedBox(width: 10),
                    Expanded(
                        child: Text(
                            '${[
                              if (t.summary.complianceUnconfirmed > 0)
                                '${t.summary.complianceUnconfirmed} statutory date(s) have passed — confirm whether each was met',
                              if (t.summary.complianceUnrecorded > 0)
                                '${t.summary.complianceUnrecorded} licence or certificate date(s) are not recorded yet',
                            ].join('; ')} — see the Compliance tab.',
                            style: const TextStyle(fontSize: 13.5))),
                  ]),
                ),
              ],
            ]),
          );
        },
      ),
    );
  }
}

class _ProgressCard extends ConsumerWidget {
  final TodayChecklist today;
  final String societyId;
  const _ProgressCard({required this.today, required this.societyId});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final s = today.summary;
    final fraction = s.total == 0 ? 1.0 : s.done / s.total;
    final signed = today.signoff;
    return ChecklistCard(
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Expanded(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text('${s.done} of ${s.total} done',
                  style: const TextStyle(fontSize: 22, fontWeight: FontWeight.w700, fontFeatures: [FontFeature.tabularFigures()])),
              const SizedBox(height: 2),
              Text(
                  [
                    if (s.overdue > 0) '${s.overdue} overdue',
                    if (s.liveOpen > 0) '${s.liveOpen} flagged from records',
                    if (s.overdue == 0 && s.liveOpen == 0) 'Nothing overdue',
                  ].join(' · '),
                  style: TextStyle(fontSize: 13, color: s.overdue > 0 ? AppTheme.error : AppTheme.textSecondary)),
            ]),
          ),
          FilledButton.icon(
            onPressed: () => showAppSheet(context: context, builder: (_) => SignoffSheet(societyId: societyId, today: today)),
            icon: Icon(signed == null ? Icons.edit_note_rounded : Icons.check_rounded, size: 18),
            label: Text(signed == null ? 'Close the day' : 'Update'),
            style: FilledButton.styleFrom(minimumSize: const Size(0, 42)),
          ),
        ]),
        const SizedBox(height: 12),
        ClipRRect(
          borderRadius: BorderRadius.circular(6),
          child: LinearProgressIndicator(
              value: fraction, minHeight: 8, backgroundColor: AppTheme.surface, color: fraction >= 1 ? AppTheme.success : AppTheme.primary),
        ),
        if (signed != null) ...[
          const SizedBox(height: 10),
          Text('Signed off by ${signed.signedBy ?? '—'}${(signed.remarks ?? '').isEmpty ? '' : ' · ${signed.remarks}'}',
              style: const TextStyle(fontSize: 12.5, color: AppTheme.textSecondary)),
        ],
      ]),
    );
  }
}

class _LiveTile extends StatelessWidget {
  final LiveLine line;
  final String societyId;
  const _LiveTile({required this.line, required this.societyId});

  @override
  Widget build(BuildContext context) {
    final color = severityColor(line.severity);
    return InkWell(
      onTap: line.linkKey == null ? null : () => openLink(context, line.linkKey, societyId),
      child: Padding(
        padding: const EdgeInsets.fromLTRB(16, 12, 12, 12),
        child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Padding(padding: const EdgeInsets.only(top: 5), child: Icon(Icons.circle, size: 10, color: color)),
          const SizedBox(width: 12),
          Expanded(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text(line.title, style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600)),
              if ((line.detail ?? '').isNotEmpty)
                Padding(
                    padding: const EdgeInsets.only(top: 2),
                    child: Text(line.detail!, style: const TextStyle(fontSize: 12.5, color: AppTheme.textSecondary))),
            ]),
          ),
          if (line.linkKey != null) const Icon(Icons.chevron_right_rounded, color: AppTheme.textTertiary),
        ]),
      ),
    );
  }
}

/// One line of the checklist: a box to tick, the title, why it is here, and — opened — its details and legal basis.
class ItemTile extends ConsumerStatefulWidget {
  final ChecklistEntry entry;
  final String societyId;
  const ItemTile({super.key, required this.entry, required this.societyId});

  @override
  ConsumerState<ItemTile> createState() => _ItemTileState();
}

class _ItemTileState extends ConsumerState<ItemTile> {
  bool _open = false;
  bool _busy = false;

  ChecklistEntry get e => widget.entry;

  Future<void> _toggle() async {
    if (_busy) return;
    if (e.needsRecord && !e.isDone) {
      await showAppSheet(context: context, builder: (_) => RecordSheet(entry: e));
      return;
    }
    setState(() => _busy = true);
    final api = ref.read(checklistApiProvider);
    try {
      if (e.isDone) {
        await api.undo(e.id, e.log!.forDate);
      } else {
        await api.complete(e.id);
      }
      invalidateChecklist(ref);
    } catch (err) {
      if (mounted) showErrorToast(context, err);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final done = e.isDone;
    final look = stateLook(e);
    final notes = <String>[
      if (e.group != 'daily' && !done) e.schedule,
      if (e.appliesBecause != null) e.appliesBecause!,
    ];
    return InkWell(
      onTap: () => setState(() => _open = !_open),
      child: Padding(
        padding: const EdgeInsets.fromLTRB(8, 6, 12, 6),
        child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
          IconButton(
            tooltip: done ? 'Undo' : (e.needsRecord ? 'Record' : 'Mark done'),
            onPressed: _busy ? null : _toggle,
            icon: Icon(
                done
                    ? (e.state == 'skipped' ? Icons.remove_circle_outline_rounded : Icons.check_box_rounded)
                    : (e.needsRecord ? Icons.edit_calendar_rounded : Icons.check_box_outline_blank_rounded),
                color: done ? look.color : (e.state == 'overdue' ? AppTheme.error : AppTheme.textSecondary)),
          ),
          Expanded(
            child: Padding(
              padding: const EdgeInsets.only(top: 10, bottom: 4),
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text(e.title,
                    style: TextStyle(
                        fontSize: 14.5,
                        fontWeight: FontWeight.w600,
                        decoration: done ? TextDecoration.lineThrough : null,
                        color: done ? AppTheme.textSecondary : AppTheme.textPrimary)),
                if (e.group != 'daily' || done) ...[
                  const SizedBox(height: 5),
                  StatePill(e),
                ],
                if (notes.isNotEmpty)
                  Padding(
                      padding: const EdgeInsets.only(top: 4),
                      child: Text(notes.join(' · '), style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary))),
                if (done && e.log != null)
                  Padding(
                    padding: const EdgeInsets.only(top: 4),
                    child: Text(
                        'By ${e.log!.doneBy ?? '—'} on ${shortDate(e.log!.doneOn)}${(e.log!.note ?? '').isEmpty ? '' : ' · ${e.log!.note}'}',
                        style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
                  ),
                if (_open) ...[
                  if ((e.detail ?? '').isNotEmpty)
                    Padding(
                        padding: const EdgeInsets.only(top: 8),
                        child: Text(e.detail!, style: const TextStyle(fontSize: 13, height: 1.4))),
                  if ((e.legalBasis ?? '').isNotEmpty)
                    Padding(
                        padding: const EdgeInsets.only(top: 6),
                        child: Text('Basis: ${e.legalBasis}', style: const TextStyle(fontSize: 12.5, height: 1.4, color: AppTheme.textSecondary))),
                  Padding(
                    padding: const EdgeInsets.only(top: 6),
                    child: Wrap(spacing: 8, children: [
                      if (e.linkKey != null)
                        ActionChip(
                            avatar: const Icon(Icons.open_in_new_rounded, size: 14),
                            label: const Text('Open the screen'),
                            onPressed: () => openLink(context, e.linkKey, widget.societyId)),
                      if (!done && !e.needsRecord)
                        ActionChip(
                            avatar: const Icon(Icons.not_interested_rounded, size: 14),
                            label: const Text('Skip with a reason'),
                            onPressed: () => showAppSheet(context: context, builder: (_) => RecordSheet(entry: e))),
                      if (e.needsRecord && done)
                        ActionChip(
                            label: const Text('Change the record'),
                            onPressed: () => showAppSheet(context: context, builder: (_) => RecordSheet(entry: e))),
                    ]),
                  ),
                ],
              ]),
            ),
          ),
          Padding(
              padding: const EdgeInsets.only(top: 12),
              child: Icon(_open ? Icons.expand_less_rounded : Icons.expand_more_rounded, size: 20, color: AppTheme.textTertiary)),
        ]),
      ),
    );
  }
}

// ── Compliance ───────────────────────────────────────────────────────────────

class _ComplianceTab extends ConsumerWidget {
  final String societyId;
  const _ComplianceTab({required this.societyId});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final async = ref.watch(complianceProvider(societyId));
    return RefreshIndicator(
      onRefresh: () async => ref.invalidate(complianceProvider(societyId)),
      child: async.when(
        loading: () => const AppLoader(),
        error: (e, _) => _error(e),
        data: (c) {
          final s = c.summary;
          return ResponsiveBody(
            maxWidth: 900,
            child: ListView(padding: const EdgeInsets.fromLTRB(16, 12, 16, 96), children: [
              JurisdictionNote(c.jurisdiction),
              const SizedBox(height: 12),
              ChecklistCard(
                child: Wrap(spacing: 28, runSpacing: 10, children: [
                  _Figure('Overdue', '${s.overdue}', s.overdue > 0 ? AppTheme.error : AppTheme.textPrimary),
                  _Figure('To confirm', '${s.unconfirmed}', s.unconfirmed > 0 ? AppTheme.warning : AppTheme.textPrimary),
                  _Figure('Falling due', '${s.soon}', s.soon > 0 ? AppTheme.warning : AppTheme.textPrimary),
                  _Figure('Not recorded', '${s.unrecorded}', s.unrecorded > 0 ? AppTheme.warning : AppTheme.textPrimary),
                  _Figure('In the calendar', '${s.total}', AppTheme.textPrimary),
                ]),
              ),
              const SizedBox(height: 12),
              if (c.items.isEmpty)
                const AppEmptyState(icon: Icons.gavel_rounded, title: 'No statutory dates', subtitle: 'Add your own in The list tab.')
              else
                ChecklistCard(
                  padding: EdgeInsets.zero,
                  child: Column(children: [
                    for (final (i, item) in c.items.indexed) ...[
                      if (i > 0) const Divider(height: 1),
                      _ComplianceTile(entry: item),
                    ],
                  ]),
                ),
            ]),
          );
        },
      ),
    );
  }
}

class _Figure extends StatelessWidget {
  final String label, value;
  final Color color;
  const _Figure(this.label, this.value, this.color);

  @override
  Widget build(BuildContext context) => Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text(label, style: const TextStyle(fontSize: 11.5, color: AppTheme.textSecondary, fontWeight: FontWeight.w600)),
        const SizedBox(height: 3),
        Text(value, style: TextStyle(fontSize: 18, fontWeight: FontWeight.w700, color: color)),
      ]);
}

class _ComplianceTile extends StatelessWidget {
  final ChecklistEntry entry;
  const _ComplianceTile({required this.entry});

  @override
  Widget build(BuildContext context) {
    final e = entry;
    return InkWell(
      onTap: () => showAppSheet(context: context, builder: (_) => RecordSheet(entry: e)),
      child: Padding(
        padding: const EdgeInsets.fromLTRB(16, 12, 12, 12),
        child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Expanded(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text(e.title, style: const TextStyle(fontSize: 14.5, fontWeight: FontWeight.w600)),
              const SizedBox(height: 5),
              Wrap(spacing: 8, runSpacing: 4, crossAxisAlignment: WrapCrossAlignment.center, children: [
                StatePill(e),
                Text(e.schedule, style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
              ]),
              if ((e.legalBasis ?? '').isNotEmpty)
                Padding(
                    padding: const EdgeInsets.only(top: 5),
                    child: Text(e.legalBasis!, style: const TextStyle(fontSize: 12, height: 1.35, color: AppTheme.textSecondary))),
              if (e.lastDoneOn != null)
                Padding(
                  padding: const EdgeInsets.only(top: 4),
                  child: Text(
                      'Last recorded ${shortDate(e.lastDoneOn!)}${(e.lastReference ?? '').isEmpty ? '' : ' · ${e.lastReference}'}',
                      style: const TextStyle(fontSize: 12, color: AppTheme.textTertiary)),
                ),
            ]),
          ),
          const Padding(padding: EdgeInsets.only(top: 2), child: Icon(Icons.edit_calendar_rounded, size: 20, color: AppTheme.primary)),
        ]),
      ),
    );
  }
}

// ── The list ─────────────────────────────────────────────────────────────────

class _ListTab extends ConsumerWidget {
  final String societyId;
  const _ListTab({required this.societyId});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final async = ref.watch(checklistItemsProvider(societyId));
    return RefreshIndicator(
      onRefresh: () async => ref.invalidate(checklistItemsProvider(societyId)),
      child: async.when(
        loading: () => const AppLoader(),
        error: (e, _) => _error(e),
        data: (list) {
          final byCategory = <String, List<ChecklistEntry>>{};
          for (final i in list.items) {
            byCategory.putIfAbsent(i.categoryLabel, () => []).add(i);
          }
          return ResponsiveBody(
            maxWidth: 900,
            child: ListView(padding: const EdgeInsets.fromLTRB(16, 12, 16, 96), children: [
              const ChecklistCard(
                child: Text(
                    'Every item here is on your checklist when it applies. Items tied to an asset or to staff appear only while your society has them. Switch off what you do not need, or add your own.',
                    style: TextStyle(fontSize: 13, height: 1.4, color: AppTheme.textSecondary)),
              ),
              for (final entry in byCategory.entries) ...[
                SectionTitle(entry.key, trailing: '${entry.value.length}'),
                ChecklistCard(
                  padding: EdgeInsets.zero,
                  child: Column(children: [
                    for (final (i, item) in entry.value.indexed) ...[
                      if (i > 0) const Divider(height: 1),
                      _ListRow(entry: item, options: list, societyId: societyId),
                    ],
                  ]),
                ),
              ],
            ]),
          );
        },
      ),
    );
  }
}

class _ListRow extends ConsumerWidget {
  final ChecklistEntry entry;
  final ItemList options;
  final String societyId;
  const _ListRow({required this.entry, required this.options, required this.societyId});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final e = entry;
    final muted = !e.applicable || !e.isEnabled;
    return InkWell(
      onTap: () => showAppSheet(context: context, builder: (_) => ItemFormSheet(societyId: societyId, existing: e, options: options)),
      child: Padding(
        padding: const EdgeInsets.fromLTRB(16, 10, 8, 10),
        child: Row(children: [
          Expanded(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text(e.title,
                  style: TextStyle(fontSize: 14, fontWeight: FontWeight.w600, color: muted ? AppTheme.textSecondary : AppTheme.textPrimary)),
              const SizedBox(height: 2),
              Text(
                  [
                    e.schedule,
                    if (e.statutory) 'Statutory',
                    if (!e.applicable) e.appliesBecause ?? 'Does not apply',
                    if (e.applicable && e.appliesBecause != null) e.appliesBecause!,
                    if (!e.isStandard) 'Your own item',
                  ].join(' · '),
                  style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
            ]),
          ),
          Switch(
            value: e.isEnabled,
            onChanged: (v) async {
              try {
                await ref.read(checklistApiProvider).update(e.id, {'is_enabled': v});
                invalidateChecklist(ref);
              } catch (err) {
                if (context.mounted) showErrorToast(context, err);
              }
            },
          ),
        ]),
      ),
    );
  }
}
