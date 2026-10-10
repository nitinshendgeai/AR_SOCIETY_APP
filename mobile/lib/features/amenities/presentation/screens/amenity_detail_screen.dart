import 'package:flutter/material.dart';
import 'package:ar_society_app/core/motion/loading.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/layout/app_sheet.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/amenities/data/amenities_api.dart';
import 'package:ar_society_app/features/amenities/presentation/providers/amenities_providers.dart';
import 'package:ar_society_app/features/amenities/presentation/screens/amenity_sheets.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/shared/widgets/app_data_table.dart' show StatusPill;
import 'package:ar_society_app/shared/widgets/app_widgets.dart';

/// One amenity: its hours and rules, who has it when on the day you pick, and a Book button. The committee also
/// sets it up here: its details, rules, rates and closed dates.
class AmenityDetailScreen extends ConsumerStatefulWidget {
  final String amenityId;
  const AmenityDetailScreen({super.key, required this.amenityId});

  @override
  ConsumerState<AmenityDetailScreen> createState() => _AmenityDetailScreenState();
}

class _AmenityDetailScreenState extends ConsumerState<AmenityDetailScreen> {
  DateTime _day = DateUtils.dateOnly(DateTime.now());

  Future<void> _run(Future<void> Function() action, String done) async {
    try {
      await action();
      invalidateAmenities(ref);
      if (mounted) AppToast.success(context, done);
    } catch (e) {
      if (mounted) showErrorToast(context, e);
    }
  }

  @override
  Widget build(BuildContext context) {
    final user = ref.watch(currentUserProvider);
    final setup = user?.isAdminOrCommittee ?? false;
    final async = ref.watch(amenityProvider(widget.amenityId));
    return Scaffold(
      backgroundColor: AppTheme.surface,
      appBar: AppBar(
        title: Text(async.valueOrNull?.name ?? 'Amenity'),
        actions: [
          if (setup && async.valueOrNull != null)
            IconButton(
              tooltip: 'Edit',
              icon: const Icon(Icons.edit_outlined),
              onPressed: () => showAppSheet(context: context, builder: (_) => AmenityFormSheet(amenity: async.value)),
            ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: () async => invalidateAmenities(ref),
        child: async.when(
          loading: () => const AppLoader(),
          error: (e, _) => ListView(padding: const EdgeInsets.all(20), children: [AppErrorBanner(message: friendlyErrorMessage(e))]),
          data: (a) => ResponsiveBody(
            maxWidth: 760,
            child: ListView(padding: const EdgeInsets.fromLTRB(16, 16, 16, 40), children: [
              Row(children: [
                CircleAvatar(backgroundColor: AppTheme.primary.withOpacity(0.1), child: Icon(amenityTypeIcon(a.type), color: AppTheme.primary)),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    Text(amenityTypeLabel(a.type), style: const TextStyle(color: AppTheme.textSecondary, fontSize: 12.5)),
                    Text(a.hours, style: const TextStyle(fontWeight: FontWeight.w700)),
                  ]),
                ),
                if (!a.active) const StatusPill('Closed', AppTheme.textSecondary),
              ]),
              if ((a.location ?? '').isNotEmpty || a.capacity != null)
                Padding(
                  padding: const EdgeInsets.only(top: 10),
                  child: Text([if ((a.location ?? '').isNotEmpty) a.location!, if (a.capacity != null) 'Up to ${a.capacity} people at a time'].join(' · '),
                      style: const TextStyle(color: AppTheme.textSecondary)),
                ),
              if ((a.description ?? '').isNotEmpty) Padding(padding: const EdgeInsets.only(top: 10), child: Text(a.description!, style: const TextStyle(height: 1.4))),
              const SizedBox(height: 18),
              if (a.bookingRequired && a.active) _DaySchedule(amenity: a, day: _day, onDay: (d) => setState(() => _day = d))
              else
                Container(
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(color: AppTheme.cardBg, borderRadius: BorderRadius.circular(AppTheme.radiusM), border: Border.all(color: AppTheme.border)),
                  child: Text(a.active ? 'No booking needed. Just go during opening hours.' : 'This is closed and can\'t be booked.'),
                ),
              const SizedBox(height: 18),
              _Rules(amenity: a, setup: setup, onRun: _run),
              const SizedBox(height: 18),
              _Rates(amenity: a, setup: setup, onRun: _run),
              if (setup) ...[
                const SizedBox(height: 18),
                _ClosedDates(amenity: a, onRun: _run),
                const SizedBox(height: 24),
                OutlinedButton.icon(
                  onPressed: () async {
                    final ok = await showDialog<bool>(
                      context: context,
                      builder: (c) => AlertDialog(
                        title: Text(a.active ? 'Close ${a.name}?' : 'Reopen ${a.name}?'),
                        content: Text(a.active ? 'Residents will no longer see it or be able to book it. Existing bookings stay as they are.' : 'Residents will see it and be able to book it again.'),
                        actions: [
                          TextButton(onPressed: () => Navigator.of(c).pop(false), child: const Text('Not now')),
                          FilledButton(onPressed: () => Navigator.of(c).pop(true), child: Text(a.active ? 'Close it' : 'Reopen it')),
                        ],
                      ),
                    );
                    if (ok == true) await _run(() => ref.read(amenitiesApiProvider).update(a.id, {'is_active': !a.active}), a.active ? 'Closed' : 'Reopened');
                  },
                  icon: Icon(a.active ? Icons.block_rounded : Icons.restart_alt_rounded, size: 18),
                  label: Text(a.active ? 'Close this amenity' : 'Reopen this amenity'),
                ),
              ],
            ]),
          ),
        ),
      ),
    );
  }
}

// ── One day ──────────────────────────────────────────────────────────────────

class _DaySchedule extends ConsumerWidget {
  final AmenityItem amenity;
  final DateTime day;
  final ValueChanged<DateTime> onDay;
  const _DaySchedule({required this.amenity, required this.day, required this.onDay});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final view = ref.watch(amenityDayProvider((amenityId: amenity.id, date: apiDate(day))));
    final today = DateUtils.dateOnly(DateTime.now());
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(color: AppTheme.cardBg, borderRadius: BorderRadius.circular(AppTheme.radiusM), border: Border.all(color: AppTheme.border)),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          IconButton(
            tooltip: 'Previous day',
            onPressed: day.isAfter(today) ? () => onDay(day.subtract(const Duration(days: 1))) : null,
            icon: const Icon(Icons.chevron_left_rounded),
          ),
          Expanded(
            child: TextButton(
              onPressed: () async {
                final d = await showDatePicker(context: context, initialDate: day, firstDate: today, lastDate: today.add(const Duration(days: 365)));
                if (d != null) onDay(DateUtils.dateOnly(d));
              },
              child: Text(dayLabel(day), style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 15)),
            ),
          ),
          IconButton(tooltip: 'Next day', onPressed: () => onDay(day.add(const Duration(days: 1))), icon: const Icon(Icons.chevron_right_rounded)),
        ]),
        view.when(
          loading: () => const Padding(padding: EdgeInsets.all(12), child: LinearProgressIndicator()),
          error: (e, _) => AppErrorBanner(message: friendlyErrorMessage(e)),
          data: (v) => Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            if (v.closed)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 8),
                child: Row(children: [
                  const Icon(Icons.block_rounded, color: AppTheme.error, size: 18),
                  const SizedBox(width: 8),
                  Expanded(child: Text('Closed this day${(v.closedReason ?? '').isEmpty ? '' : ': ${v.closedReason}'}', style: const TextStyle(color: AppTheme.error, fontWeight: FontWeight.w600))),
                ]),
              )
            else if (v.taken.isEmpty)
              const Padding(padding: EdgeInsets.symmetric(vertical: 8), child: Text('Free all day.', style: TextStyle(color: AppTheme.success, fontWeight: FontWeight.w600)))
            else ...[
              const Padding(padding: EdgeInsets.only(top: 4, bottom: 4), child: Text('Already taken', style: TextStyle(fontSize: 12.5, color: AppTheme.textSecondary))),
              for (final s in v.taken)
                ListTile(
                  dense: true,
                  contentPadding: EdgeInsets.zero,
                  leading: Icon(s.mine ? Icons.person_rounded : Icons.lock_clock_rounded, size: 20, color: s.mine ? AppTheme.primary : AppTheme.textSecondary),
                  title: Text('${timeLabel(s.start)} – ${timeLabel(s.end)}', style: const TextStyle(fontWeight: FontWeight.w600)),
                  subtitle: Text([
                    if (s.mine) 'Yours',
                    if (!s.mine && (s.who ?? '').isNotEmpty) s.who!,
                    if ((s.flat ?? '').isNotEmpty) s.flat!,
                    if (s.status == 'pending') 'waiting for approval',
                  ].join(' · ')),
                ),
            ],
            const SizedBox(height: 10),
            FilledButton.icon(
              onPressed: v.closed
                  ? null
                  : () => showAppSheet(context: context, builder: (_) => BookingSheet(amenity: amenity, date: day)),
              icon: const Icon(Icons.event_available_rounded, size: 18),
              label: Text('Book on ${DateFormat0.short(day)}'),
            ),
          ]),
        ),
      ]),
    );
  }
}

class DateFormat0 {
  static const _m = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  static String short(DateTime d) => '${d.day} ${_m[d.month - 1]}';
}

// ── Rules, rates, closed dates ───────────────────────────────────────────────

typedef _Run = Future<void> Function(Future<void> Function() action, String done);

Widget _sectionHeader(String title, {VoidCallback? onAdd, String addLabel = 'Add'}) => Row(children: [
      Expanded(child: Text(title, style: const TextStyle(fontWeight: FontWeight.w800, fontSize: 15))),
      if (onAdd != null) TextButton.icon(onPressed: onAdd, icon: const Icon(Icons.add_rounded, size: 18), label: Text(addLabel)),
    ]);

class _Rules extends ConsumerWidget {
  final AmenityItem amenity;
  final bool setup;
  final _Run onRun;
  const _Rules({required this.amenity, required this.setup, required this.onRun});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final rules = ref.watch(amenityRulesProvider(amenity.id)).valueOrNull ?? const <AmenityRule>[];
    if (rules.isEmpty && !setup) return const SizedBox.shrink();
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      _sectionHeader('Rules', onAdd: setup ? () => showAppSheet(context: context, builder: (_) => RuleSheet(amenityId: amenity.id)) : null, addLabel: 'Add a rule'),
      if (rules.isEmpty) const Text('No rules yet.', style: TextStyle(color: AppTheme.textSecondary)),
      for (final r in rules)
        ListTile(
          dense: true,
          contentPadding: EdgeInsets.zero,
          leading: const Icon(Icons.rule_rounded, size: 20, color: AppTheme.textSecondary),
          title: Text(ruleText(r)),
          trailing: setup
              ? IconButton(
                  tooltip: 'Remove',
                  icon: const Icon(Icons.delete_outline_rounded, size: 20),
                  onPressed: () => onRun(() => ref.read(amenitiesApiProvider).deleteRule(r.id), 'Rule removed'),
                )
              : null,
        ),
    ]);
  }
}

class _Rates extends ConsumerWidget {
  final AmenityItem amenity;
  final bool setup;
  final _Run onRun;
  const _Rates({required this.amenity, required this.setup, required this.onRun});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    if (!amenity.chargeable && !setup) return const SizedBox.shrink();
    final rates = ref.watch(amenityRatesProvider(amenity.id)).valueOrNull ?? const <AmenityRate>[];
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      _sectionHeader('Rates', onAdd: setup ? () => showAppSheet(context: context, builder: (_) => RateSheet(amenityId: amenity.id)) : null, addLabel: 'Add a rate'),
      if (rates.isEmpty) Text(amenity.chargeable ? 'No rate set yet.' : 'Free to use.', style: const TextStyle(color: AppTheme.textSecondary)),
      for (final r in rates)
        ListTile(
          dense: true,
          contentPadding: EdgeInsets.zero,
          leading: const Icon(Icons.currency_rupee_rounded, size: 20, color: AppTheme.textSecondary),
          title: Row(children: [Flexible(child: Text(r.label)), if (r.isDefault) const Padding(padding: EdgeInsets.only(left: 8), child: StatusPill('Used', AppTheme.success))]),
          subtitle: Text(r.text),
          trailing: setup
              ? IconButton(
                  tooltip: 'Remove',
                  icon: const Icon(Icons.delete_outline_rounded, size: 20),
                  onPressed: () => onRun(() => ref.read(amenitiesApiProvider).deleteRate(r.id), 'Rate removed'),
                )
              : null,
        ),
    ]);
  }
}

class _ClosedDates extends ConsumerWidget {
  final AmenityItem amenity;
  final _Run onRun;
  const _ClosedDates({required this.amenity, required this.onRun});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final dates = (ref.watch(amenityClosedDatesProvider(amenity.id)).valueOrNull ?? const <ClosedDate>[])
        .where((d) => !d.date.isBefore(DateUtils.dateOnly(DateTime.now())))
        .toList();
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      _sectionHeader('Closed dates', onAdd: () => showAppSheet(context: context, builder: (_) => ClosedDateSheet(amenityId: amenity.id)), addLabel: 'Close a date'),
      if (dates.isEmpty) const Text('Open every day.', style: TextStyle(color: AppTheme.textSecondary)),
      for (final d in dates)
        ListTile(
          dense: true,
          contentPadding: EdgeInsets.zero,
          leading: const Icon(Icons.event_busy_rounded, size: 20, color: AppTheme.textSecondary),
          title: Text(dayLabel(d.date)),
          subtitle: (d.reason ?? '').isEmpty ? null : Text(d.reason!),
          trailing: IconButton(
            tooltip: 'Open it again',
            icon: const Icon(Icons.delete_outline_rounded, size: 20),
            onPressed: () => onRun(() => ref.read(amenitiesApiProvider).reopenDate(d.id), 'Open again'),
          ),
        ),
    ]);
  }
}
