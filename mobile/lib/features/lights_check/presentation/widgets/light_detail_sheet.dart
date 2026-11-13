import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/l10n/app_locale.dart';
import 'package:ar_society_app/core/layout/app_sheet.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/core/theme/design_tokens.dart';
import 'package:ar_society_app/features/lights_check/data/lights_api.dart';
import 'package:ar_society_app/shared/widgets/app_form.dart' show AppSheetFrame;
import 'package:ar_society_app/shared/widgets/app_status.dart';

/// Opens the detail of one floor of the monthly report: every light on it and how it was last found.
Future<void> showFloorDetail(
  BuildContext context, {
  required String societyId,
  required String? wingId,
  required FloorReport floor,
  required String monthLabel,
  required bool currentMonth,
}) =>
    showAppSheet<void>(
      context: context,
      builder: (_) => FloorDetailSheet(
          societyId: societyId, wingId: wingId, floor: floor, monthLabel: monthLabel, currentMonth: currentMonth),
    );

/// Opens the detail of one common area of the monthly report.
Future<void> showAreaDetail(
  BuildContext context, {
  required AreaReport area,
  required String monthLabel,
  required bool currentMonth,
}) =>
    showAppSheet<void>(
      context: context,
      builder: (_) => AreaDetailSheet(area: area, monthLabel: monthLabel, currentMonth: currentMonth),
    );

/// The words and tone for a light's state: working, not working, or not checked yet.
(AppTone, IconData, String) lightState(String? status) => switch (status) {
      'working' => (AppTone.success, Icons.check_circle_outline_rounded, 'Working'),
      'not_working' => (AppTone.danger, Icons.error_outline_rounded, 'Not working'),
      _ => (AppTone.neutral, Icons.remove_circle_outline_rounded, 'Not checked'),
    };

(AppTone, String) _reportState(String status) => switch (status) {
      'done' => (AppTone.success, 'Done'),
      'partial' => (AppTone.warning, 'Partly'),
      _ => (AppTone.neutral, 'Not checked'),
    };

class FloorDetailSheet extends ConsumerWidget {
  final String societyId;
  final String? wingId;
  final FloorReport floor;
  final String monthLabel;
  final bool currentMonth;
  const FloorDetailSheet({
    super.key,
    required this.societyId,
    required this.wingId,
    required this.floor,
    required this.monthLabel,
    required this.currentMonth,
  });

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final (_, stateLabel) = _reportState(floor.status);
    final kinds = [
      ('tube', 'Tube lights', floor.tube),
      if (floor.flats > 0) ('spot', 'Spot lights', floor.spot),
      if (floor.camera.expected > 0) ('camera', 'Camera', floor.camera),
    ];
    return AppSheetFrame(
      title: '${floor.wingName} · ${floor.floorName}',
      subtitle: context.trf('{state} in {month}', {'state': context.tr(stateLabel), 'month': monthLabel}),
      child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        _SummaryRow(done: floor.status == 'done', notWorking: floor.notWorking),
        if (!currentMonth) _OlderMonthNote(monthLabel: monthLabel),
        if (wingId == null)
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 16),
            child: Text(context.tr('The lights of this wing could not be found. Pull down on the report to refresh it.'),
                style: const TextStyle(color: AppTheme.textSecondary)),
          )
        else
          for (final (kind, title, part) in kinds)
            _Section(
              title: title,
              count: context.trf('{a}/{b} checked', {'a': part.checked, 'b': part.expected}),
              sheet: ref.watch(lightSheetProvider((societyId: societyId, wingId: wingId!, floor: floor.floorNumber, kind: kind))),
              onRetry: () => ref.invalidate(lightSheetProvider((societyId: societyId, wingId: wingId!, floor: floor.floorNumber, kind: kind))),
            ),
      ]),
    );
  }
}

class AreaDetailSheet extends ConsumerWidget {
  final AreaReport area;
  final String monthLabel;
  final bool currentMonth;
  const AreaDetailSheet({super.key, required this.area, required this.monthLabel, required this.currentMonth});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final (_, stateLabel) = _reportState(area.status);
    return AppSheetFrame(
      title: area.wingName == null ? area.name : '${area.name} · ${area.wingName}',
      subtitle: context.trf('{state} in {month}', {'state': context.tr(stateLabel), 'month': monthLabel}),
      child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        _SummaryRow(done: area.status == 'done', notWorking: area.notWorking),
        if (!currentMonth) _OlderMonthNote(monthLabel: monthLabel),
        // An area's sheet already has one group per kind of light it holds, so it needs no section titles.
        _Section(
          title: null,
          sheet: ref.watch(lightAreaSheetProvider(area.id)),
          onRetry: () => ref.invalidate(lightAreaSheetProvider(area.id)),
        ),
      ]),
    );
  }
}

/// The headline under the title: how many lights need replacing, or that everything checked is working. The state
/// itself (partly checked, and so on) is already in the subtitle, so it is not repeated here.
class _SummaryRow extends StatelessWidget {
  final bool done;
  final int notWorking;
  const _SummaryRow({required this.done, required this.notWorking});

  @override
  Widget build(BuildContext context) {
    if (notWorking == 0 && !done) return const SizedBox.shrink();
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Align(
        alignment: Alignment.centerLeft,
        child: notWorking > 0
            ? AppStatusChip(
                label: context.trf('{n} not working', {'n': notWorking}), tone: AppTone.danger, icon: Icons.error_outline_rounded)
            : AppStatusChip(label: context.tr('All working'), tone: AppTone.success, icon: Icons.check_circle_outline_rounded),
      ),
    );
  }
}

/// The sheet shows each light as it was last found, not as it stood in a past month; say so when the report is on one.
class _OlderMonthNote extends StatelessWidget {
  final String monthLabel;
  const _OlderMonthNote({required this.monthLabel});

  @override
  Widget build(BuildContext context) => Container(
        margin: const EdgeInsets.only(bottom: 12),
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(color: AppTheme.primarySoft, borderRadius: BorderRadius.circular(AppTheme.radiusM)),
        child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
          const Icon(Icons.info_outline_rounded, size: 18, color: AppTheme.primary),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              context.trf('Each light is shown as it was last found, which can be later than {month}.', {'month': monthLabel}),
              key: const Key('older-month-note'),
              style: const TextStyle(fontSize: 13),
            ),
          ),
        ]),
      );
}

class _Section extends StatelessWidget {
  final String? title;

  /// "4/4 checked", shown at the right of the title.
  final String? count;
  final AsyncValue<LightSheet> sheet;
  final VoidCallback onRetry;
  const _Section({required this.title, this.count, required this.sheet, required this.onRetry});

  @override
  Widget build(BuildContext context) {
    final body = sheet.when(
      loading: () => const Padding(padding: EdgeInsets.all(16), child: Center(child: CircularProgressIndicator())),
      error: (e, _) => Row(children: [
        Expanded(child: Text(friendlyErrorMessage(e), style: const TextStyle(color: AppTheme.textSecondary))),
        TextButton(
          onPressed: onRetry,
          style: TextButton.styleFrom(minimumSize: const Size(AppSpacing.minTouch, AppSpacing.minTouch)),
          child: Text(context.tr('Try again')),
        ),
      ]),
      data: (s) => _Groups(groups: s.groups),
    );
    // A common area's sheet already has one group per kind of light, so it has no section header or box.
    if (title == null) return body;
    // One bordered box per kind of light: a bold header band, then the lights inside it.
    return Container(
      margin: const EdgeInsets.only(top: 4, bottom: 14),
      clipBehavior: Clip.antiAlias,
      decoration: BoxDecoration(
        color: AppTheme.cardBg,
        borderRadius: BorderRadius.circular(AppTheme.radiusM),
        border: Border.all(color: AppTheme.fieldBorder, width: 1.5),
      ),
      child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        Container(
          color: AppTheme.primarySoft,
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
          child: Row(children: [
            Expanded(
              child: Semantics(
                header: true,
                child: Text(context.tr(title!),
                    style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w800, color: AppTheme.textPrimary)),
              ),
            ),
            if (count != null)
              Text(count!,
                  style: const TextStyle(fontSize: 12.5, fontWeight: FontWeight.w600, color: AppTheme.textSecondary)),
          ]),
        ),
        const Divider(height: 1, thickness: 1.5, color: AppTheme.fieldBorder),
        Padding(padding: const EdgeInsets.fromLTRB(12, 10, 12, 4), child: body),
      ]),
    );
  }
}

class _Groups extends StatelessWidget {
  final List<LightGroup> groups;
  const _Groups({required this.groups});

  static int _notWorking(LightGroup g) => g.points.where((p) => p.status == 'not_working').length;

  @override
  Widget build(BuildContext context) {
    if (groups.isEmpty) {
      return Text(context.tr('Nothing to show.'), style: const TextStyle(color: AppTheme.textSecondary));
    }
    // A floor's own lights ("This floor") or a single group read as plain rows; one card per flat when there are several.
    if (groups.length == 1 && groups.first.flatId == null) return _Rows(points: groups.first.points);
    // Flats with something not working come first, so the lights to replace are the first thing seen.
    final ordered = [...groups]..sort((a, b) => _notWorking(b).compareTo(_notWorking(a)));
    return Column(children: [for (final g in ordered) _GroupCard(group: g)]);
  }
}

class _GroupCard extends StatelessWidget {
  final LightGroup group;
  const _GroupCard({required this.group});

  @override
  Widget build(BuildContext context) {
    final bad = group.points.where((p) => p.status == 'not_working').length;
    final checked = group.points.where((p) => p.status != null).length;
    final (tone, summary) = bad > 0
        ? (AppTone.danger, context.trf('{n} not working', {'n': bad}))
        : checked == 0
            ? (AppTone.neutral, context.tr('Not checked'))
            : checked < group.points.length
                ? (AppTone.warning, context.trf('{a} of {b} checked', {'a': checked, 'b': group.points.length}))
                : (AppTone.success, context.tr('All working'));
    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      decoration: BoxDecoration(
        color: AppTheme.cardBg,
        borderRadius: BorderRadius.circular(AppTheme.radiusM),
        border: Border.all(color: AppTheme.border),
      ),
      // A flat with a light to replace opens on its lights; the rest stay folded. The tile paints its tap highlight on
      // the nearest Material, so it gets its own transparent one above the coloured box.
      child: Material(
        type: MaterialType.transparency,
        child: Theme(
        data: Theme.of(context).copyWith(dividerColor: Colors.transparent),
        child: ExpansionTile(
          key: PageStorageKey<String>('group-${group.flatId ?? group.label}'),
          initiallyExpanded: bad > 0,
          tilePadding: const EdgeInsets.symmetric(horizontal: 14),
          childrenPadding: const EdgeInsets.fromLTRB(14, 0, 14, 10),
          title: Text(group.label, style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w700)),
          trailing: AppStatusChip(label: summary, tone: tone),
          children: [_Rows(points: group.points)],
        ),
        ),
      ),
    );
  }
}

class _Rows extends StatelessWidget {
  final List<LightCell> points;
  const _Rows({required this.points});

  @override
  Widget build(BuildContext context) => Column(children: [for (final p in points) _Row(cell: p)]);
}

class _Row extends StatelessWidget {
  final LightCell cell;
  const _Row({required this.cell});

  @override
  Widget build(BuildContext context) {
    final (tone, icon, label) = lightState(cell.status);
    final detail = [
      if (cell.lastCheckedAt != null)
        context.trf('Checked {when}', {'when': lightStamp(cell.lastCheckedAt!)})
      else
        context.tr('Not checked yet'),
      // "by Eli" stays together when the line wraps (a non-breaking space), instead of leaving the name alone.
      if (cell.lastCheckedBy != null) context.trf('by {name}', {'name': cell.lastCheckedBy!}).replaceAll(' ', '\u00A0'),
    ].join(' ');
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Expanded(
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(cell.label, style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600)),
            const SizedBox(height: 2),
            Text(detail, style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
            if (cell.status == 'not_working' && cell.notWorkingSince != null)
              Text(context.trf('Not working since {when}', {'when': lightDay(cell.notWorkingSince!)}),
                  style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: kToneColors[AppTone.danger]!.foreground)),
          ]),
        ),
        const SizedBox(width: 8),
        AppStatusChip(label: context.tr(label), tone: tone, icon: icon),
      ]),
    );
  }
}
