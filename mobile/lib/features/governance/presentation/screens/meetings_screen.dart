import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';
import 'package:ar_society_app/core/layout/app_sheet.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/features/governance/data/governance_api.dart';
import 'package:ar_society_app/features/maintenance_billing/presentation/widgets/billing_sheet_frame.dart';
import 'package:ar_society_app/features/vendor/presentation/widgets/procurement_widgets.dart'
    show DateField;
import 'package:ar_society_app/shared/widgets/app_data_table.dart'
    show StatusPill;
import 'package:ar_society_app/shared/widgets/app_widgets.dart';

String _timeText(String? hhmm) {
  if (hhmm == null) return '';
  final p = hhmm.split(':');
  final t = TimeOfDay(hour: int.parse(p[0]), minute: int.parse(p[1]));
  return DateFormat('h:mm a').format(DateTime(2000, 1, 1, t.hour, t.minute));
}

/// Meetings of the society: when and where, the agenda, and (once the secretary publishes them) the minutes,
/// who attended and what was resolved.
class MeetingsScreen extends ConsumerWidget {
  const MeetingsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final user = ref.watch(currentUserProvider);
    final sid = user?.societyId ?? '';
    final office = user?.isAdminOrCommittee == true;
    final async = ref.watch(meetingsProvider(sid));
    return Scaffold(
      backgroundColor: AppTheme.surface,
      appBar: AppBar(title: const Text('Meetings')),
      floatingActionButton: office
          ? FloatingActionButton.extended(
              onPressed: () => showAppSheet(
                  context: context, builder: (_) => const _ScheduleSheet()),
              icon: const Icon(Icons.add_rounded),
              label: const Text('Schedule meeting'))
          : null,
      body: async.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (e, _) => Center(
            child: OutlinedButton(
                onPressed: () => ref.invalidate(meetingsProvider(sid)),
                child: const Text('Could not load. Try again'))),
        data: (all) {
          if (all.isEmpty) {
            return AppEmptyState(
                icon: Icons.groups_rounded,
                title: 'No meetings yet',
                subtitle: office
                    ? 'Schedule the next one and everyone is told.'
                    : 'Meetings will appear here.');
          }
          final upcoming = all.where((m) => m.upcoming).toList()
            ..sort((a, b) => a.date.compareTo(b.date));
          final past = all.where((m) => !m.upcoming).toList();
          return RefreshIndicator(
            onRefresh: () async => ref.invalidate(meetingsProvider(sid)),
            child: ListView(
                padding: const EdgeInsets.fromLTRB(16, 8, 16, 96),
                children: [
                  if (upcoming.isNotEmpty) ...[
                    const _Heading('Upcoming'),
                    for (final m in upcoming)
                      _MeetingCard(m: m, office: office),
                  ],
                  if (past.isNotEmpty) ...[
                    const _Heading('Earlier'),
                    for (final m in past) _MeetingCard(m: m, office: office),
                  ],
                ]),
          );
        },
      ),
    );
  }
}

class _Heading extends StatelessWidget {
  final String text;
  const _Heading(this.text);
  @override
  Widget build(BuildContext context) => Padding(
      padding: const EdgeInsets.fromLTRB(2, 14, 2, 8),
      child: Text(text,
          style: const TextStyle(
              fontSize: 13,
              fontWeight: FontWeight.w600,
              color: AppTheme.textSecondary)));
}

class _MeetingCard extends StatelessWidget {
  final Meeting m;
  final bool office;
  const _MeetingCard({required this.m, required this.office});

  @override
  Widget build(BuildContext context) {
    final cancelled = m.status == 'cancelled';
    final when =
        '${DateFormat('EEE, d MMM yyyy').format(m.date)}${m.startTime == null ? '' : ' · ${_timeText(m.startTime)}'}';
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: DecoratedBox(
        decoration: BoxDecoration(
            color: AppTheme.cardBg,
            borderRadius: BorderRadius.circular(AppTheme.radiusL),
            boxShadow: AppTheme.cardShadow),
        child: InkWell(
          borderRadius: BorderRadius.circular(AppTheme.radiusL),
          onTap: () => showAppSheet(
              context: context,
              builder: (_) => _MeetingSheet(id: m.id, office: office)),
          child: Padding(
            padding: const EdgeInsets.all(16),
            child:
                Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Row(children: [
                Expanded(
                    child: Text(m.title,
                        style: TextStyle(
                            fontSize: 15,
                            fontWeight: FontWeight.w700,
                            decoration:
                                cancelled ? TextDecoration.lineThrough : null,
                            color: AppTheme.textPrimary))),
                if (cancelled)
                  const StatusPill('Cancelled', AppTheme.error)
                else if (m.minutesPublished)
                  const StatusPill('Minutes', AppTheme.success),
              ]),
              const SizedBox(height: 4),
              Text(meetingTypeLabel(m.meetingType),
                  style:
                      const TextStyle(fontSize: 12.5, color: AppTheme.primary)),
              const SizedBox(height: 8),
              Row(children: [
                const Icon(Icons.event_rounded,
                    size: 16, color: AppTheme.textSecondary),
                const SizedBox(width: 6),
                Expanded(
                    child: Text(when,
                        style: const TextStyle(
                            fontSize: 13, color: AppTheme.textSecondary))),
              ]),
              if ((m.venue ?? '').isNotEmpty) ...[
                const SizedBox(height: 4),
                Row(children: [
                  const Icon(Icons.place_outlined,
                      size: 16, color: AppTheme.textSecondary),
                  const SizedBox(width: 6),
                  Expanded(
                      child: Text(m.venue!,
                          style: const TextStyle(
                              fontSize: 13, color: AppTheme.textSecondary))),
                ]),
              ],
            ]),
          ),
        ),
      ),
    );
  }
}

// ── Detail ───────────────────────────────────────────────────────────────────

class _MeetingSheet extends ConsumerWidget {
  final String id;
  final bool office;
  const _MeetingSheet({required this.id, required this.office});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final sid = ref.watch(currentUserProvider)?.societyId ?? '';
    final m = ref
        .watch(meetingsProvider(sid))
        .valueOrNull
        ?.where((x) => x.id == id)
        .firstOrNull;
    if (m == null) return const SizedBox.shrink();

    Widget label(String t) => Padding(
        padding: const EdgeInsets.only(top: 14, bottom: 6),
        child: Text(t,
            style: const TextStyle(
                fontSize: 13,
                fontWeight: FontWeight.w700,
                color: AppTheme.primary)));

    return BillingSheetFrame(
      title: m.title,
      child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        Text(
            '${meetingTypeLabel(m.meetingType)} · ${DateFormat('d MMM yyyy').format(m.date)}'
            '${m.startTime == null ? '' : ' · ${_timeText(m.startTime)}'}'
            '${(m.venue ?? '').isEmpty ? '' : '\n${m.venue}'}',
            style: const TextStyle(
                fontSize: 13.5, color: AppTheme.textSecondary, height: 1.4)),
        if ((m.agenda ?? '').isNotEmpty) ...[
          label('Agenda'),
          Text(m.agenda!, style: const TextStyle(height: 1.45))
        ],
        if (m.hasMinutes) ...[
          label(m.minutesPublished
              ? 'Minutes'
              : 'Minutes (not yet shared with members)'),
          if ((m.minutes ?? '').isNotEmpty)
            Text(m.minutes!, style: const TextStyle(height: 1.45)),
          if (m.resolutions.isNotEmpty) ...[
            label('Resolutions'),
            for (final r in m.resolutions)
              Padding(
                padding: const EdgeInsets.only(bottom: 8),
                child: Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text('${r.number}. ',
                          style: const TextStyle(fontWeight: FontWeight.w700)),
                      Expanded(
                          child: Text(
                              '${r.text}'
                              '${(r.proposedBy ?? '').isEmpty ? '' : '\nProposed by ${r.proposedBy}'}'
                              '${(r.secondedBy ?? '').isEmpty ? '' : ', seconded by ${r.secondedBy}'}',
                              style: const TextStyle(height: 1.4))),
                      const SizedBox(width: 8),
                      StatusPill(
                          kOutcomes
                              .firstWhere((o) => o.$1 == r.outcome,
                                  orElse: () => (r.outcome, r.outcome))
                              .$2,
                          r.outcome == 'carried'
                              ? AppTheme.success
                              : r.outcome == 'rejected'
                                  ? AppTheme.error
                                  : AppTheme.warning),
                    ]),
              ),
          ],
          if (m.attendees.isNotEmpty) ...[
            label('Present (${m.attendees.where((a) => a.present).length})'),
            Text(
                [
                  for (final a in m.attendees.where((a) => a.present))
                    '${a.name}${(a.flatLabel ?? '').isEmpty ? '' : ' (${a.flatLabel})'}${(a.designation ?? '').isEmpty ? '' : ', ${a.designation}'}'
                ].join('\n'),
                style: const TextStyle(height: 1.5)),
          ],
        ],
        if (office) ...[
          const SizedBox(height: 18),
          FilledButton.icon(
            onPressed: () {
              Navigator.pop(context);
              showAppSheet(
                  context: context, builder: (_) => _MinutesSheet(meeting: m));
            },
            icon: const Icon(Icons.edit_note_rounded),
            label: Text(m.hasMinutes ? 'Edit minutes' : 'Record minutes'),
          ),
          if (m.status == 'scheduled')
            TextButton(
              onPressed: () async {
                await ref
                    .read(governanceApiProvider)
                    .updateMeeting(m.id, {'status': 'cancelled'});
                ref.invalidate(meetingsProvider(sid));
                if (context.mounted) Navigator.pop(context);
              },
              child: const Text('Cancel this meeting',
                  style: TextStyle(color: AppTheme.error)),
            ),
        ],
      ]),
    );
  }
}

// ── Schedule ─────────────────────────────────────────────────────────────────

class _ScheduleSheet extends ConsumerStatefulWidget {
  const _ScheduleSheet();
  @override
  ConsumerState<_ScheduleSheet> createState() => _ScheduleSheetState();
}

class _ScheduleSheetState extends ConsumerState<_ScheduleSheet> {
  final _form = GlobalKey<FormState>();
  final _title = TextEditingController();
  final _venue = TextEditingController();
  final _agenda = TextEditingController();
  String _type = 'committee';
  DateTime? _date;
  TimeOfDay? _time;
  bool _announce = true, _saving = false;

  @override
  void dispose() {
    _title.dispose();
    _venue.dispose();
    _agenda.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    if (!_form.currentState!.validate()) return;
    setState(() => _saving = true);
    try {
      final sid = ref.read(currentUserProvider)?.societyId ?? '';
      await ref.read(governanceApiProvider).createMeeting(sid, {
        'title': _title.text.trim(),
        'meeting_type': _type,
        'meeting_date': apiDay(_date!),
        if (_time != null)
          'start_time':
              '${_time!.hour.toString().padLeft(2, '0')}:${_time!.minute.toString().padLeft(2, '0')}',
        if (_venue.text.trim().isNotEmpty) 'venue': _venue.text.trim(),
        if (_agenda.text.trim().isNotEmpty) 'agenda': _agenda.text.trim(),
        'announce': _announce,
      });
      ref.invalidate(meetingsProvider(sid));
      if (mounted) {
        AppToast.success(
            context,
            _announce
                ? 'Meeting scheduled and members told'
                : 'Meeting scheduled');
        Navigator.pop(context);
      }
    } catch (e) {
      if (mounted) {
        setState(() => _saving = false);
        showErrorToast(context, e);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return BillingSheetFrame(
      title: 'Schedule a meeting',
      child: Form(
        key: _form,
        child:
            Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          TextFormField(
              controller: _title,
              decoration: const InputDecoration(labelText: 'Title *'),
              validator: (v) =>
                  (v ?? '').trim().length < 2 ? 'Enter a title' : null),
          const SizedBox(height: 12),
          DropdownButtonFormField<String>(
            initialValue: _type,
            decoration: const InputDecoration(labelText: 'Kind of meeting'),
            items: [
              for (final t in kMeetingTypes)
                DropdownMenuItem(value: t.$1, child: Text(t.$2))
            ],
            onChanged: (v) => setState(() => _type = v ?? _type),
          ),
          const SizedBox(height: 12),
          Row(children: [
            Expanded(
                child: DateField(
                    label: 'Date',
                    required: true,
                    value: _date,
                    onChanged: (d) => setState(() => _date = d))),
            const SizedBox(width: 12),
            Expanded(
              child: InkWell(
                onTap: () async {
                  final t = await showTimePicker(
                      context: context,
                      initialTime:
                          _time ?? const TimeOfDay(hour: 18, minute: 0));
                  if (t != null) setState(() => _time = t);
                },
                child: InputDecorator(
                  decoration: const InputDecoration(labelText: 'Time'),
                  child: Text(_time == null ? '—' : _time!.format(context)),
                ),
              ),
            ),
          ]),
          const SizedBox(height: 12),
          TextFormField(
              controller: _venue,
              decoration: const InputDecoration(labelText: 'Venue')),
          const SizedBox(height: 12),
          TextFormField(
              controller: _agenda,
              minLines: 3,
              maxLines: 6,
              decoration: const InputDecoration(labelText: 'Agenda')),
          SwitchListTile(
              contentPadding: EdgeInsets.zero,
              title: const Text('Tell residents now'),
              subtitle: const Text(
                  'Sends a notification to every resident and tenant with the app'),
              value: _announce,
              onChanged: (v) => setState(() => _announce = v)),
          const SizedBox(height: 8),
          AppPrimaryButton(
              label: 'Schedule', isLoading: _saving, onPressed: _save),
        ]),
      ),
    );
  }
}

// ── Minutes ──────────────────────────────────────────────────────────────────

class _MinutesSheet extends ConsumerStatefulWidget {
  final Meeting meeting;
  const _MinutesSheet({required this.meeting});
  @override
  ConsumerState<_MinutesSheet> createState() => _MinutesSheetState();
}

class _ResolutionRow {
  final text = TextEditingController();
  final proposer = TextEditingController();
  String outcome = 'carried';
}

class _MinutesSheetState extends ConsumerState<_MinutesSheet> {
  late final _minutes = TextEditingController(text: widget.meeting.minutes);
  late final _present = TextEditingController(
      text: [
    for (final a in widget.meeting.attendees.where((a) => a.present)) _line(a)
  ].join('\n'));
  late final List<_ResolutionRow> _rows = [
    for (final r in widget.meeting.resolutions)
      _ResolutionRow()
        ..text.text = r.text
        ..proposer.text = r.proposedBy ?? ''
        ..outcome = r.outcome,
  ];
  late bool _publish = widget.meeting.minutesPublished;
  bool _saving = false;

  static String _line(Attendee a) => [
        a.name,
        a.flatLabel ?? '',
        a.designation ?? ''
      ].join(', ').replaceAll(RegExp(r'(, )+$'), '');

  @override
  void dispose() {
    _minutes.dispose();
    _present.dispose();
    for (final r in _rows) {
      r.text.dispose();
      r.proposer.dispose();
    }
    super.dispose();
  }

  Future<void> _save() async {
    final attendees = <Map<String, dynamic>>[];
    for (final raw in _present.text.split('\n')) {
      final parts = raw.split(',').map((s) => s.trim()).toList();
      if (parts.first.isEmpty) continue;
      attendees.add({
        'name': parts[0],
        if (parts.length > 1 && parts[1].isNotEmpty) 'flat_label': parts[1],
        if (parts.length > 2 && parts[2].isNotEmpty) 'designation': parts[2],
        'present': true,
      });
    }
    setState(() => _saving = true);
    try {
      final sid = ref.read(currentUserProvider)?.societyId ?? '';
      await ref.read(governanceApiProvider).saveMinutes(widget.meeting.id, {
        'minutes': _minutes.text.trim().isEmpty ? null : _minutes.text.trim(),
        'attendees': attendees,
        'resolutions': [
          for (final r in _rows)
            if (r.text.text.trim().isNotEmpty)
              {
                'text': r.text.text.trim(),
                'proposed_by': r.proposer.text.trim().isEmpty
                    ? null
                    : r.proposer.text.trim(),
                'outcome': r.outcome,
              }
        ],
        'publish': _publish,
      });
      ref.invalidate(meetingsProvider(sid));
      if (mounted) {
        AppToast.success(
            context, _publish ? 'Minutes saved and shared' : 'Minutes saved');
        Navigator.pop(context);
      }
    } catch (e) {
      if (mounted) {
        setState(() => _saving = false);
        showErrorToast(context, e);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return BillingSheetFrame(
      title: 'Minutes: ${widget.meeting.title}',
      child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        TextField(
            controller: _minutes,
            minLines: 5,
            maxLines: 12,
            decoration: const InputDecoration(
                labelText: 'Minutes', alignLabelWithHint: true)),
        const SizedBox(height: 12),
        TextField(
            controller: _present,
            minLines: 3,
            maxLines: 10,
            decoration: const InputDecoration(
                labelText: 'Present',
                helperText:
                    'One per line: name, flat, designation (flat and designation are optional)',
                alignLabelWithHint: true)),
        const SizedBox(height: 14),
        const Text('Resolutions',
            style: TextStyle(
                fontSize: 13,
                fontWeight: FontWeight.w700,
                color: AppTheme.primary)),
        for (var i = 0; i < _rows.length; i++)
          Padding(
            padding: const EdgeInsets.only(top: 10),
            child: Column(children: [
              TextField(
                  controller: _rows[i].text,
                  minLines: 1,
                  maxLines: 4,
                  decoration:
                      InputDecoration(labelText: 'Resolution ${i + 1}')),
              const SizedBox(height: 8),
              Row(children: [
                Expanded(
                    child: TextField(
                        controller: _rows[i].proposer,
                        decoration:
                            const InputDecoration(labelText: 'Proposed by'))),
                const SizedBox(width: 10),
                SizedBox(
                  width: 130,
                  child: DropdownButtonFormField<String>(
                    initialValue: _rows[i].outcome,
                    items: [
                      for (final o in kOutcomes)
                        DropdownMenuItem(value: o.$1, child: Text(o.$2))
                    ],
                    onChanged: (v) =>
                        setState(() => _rows[i].outcome = v ?? 'carried'),
                  ),
                ),
                IconButton(
                    onPressed: () => setState(() => _rows.removeAt(i)),
                    icon: const Icon(Icons.close_rounded, size: 20)),
              ]),
            ]),
          ),
        Align(
          alignment: Alignment.centerLeft,
          child: TextButton.icon(
              onPressed: () => setState(() => _rows.add(_ResolutionRow())),
              icon: const Icon(Icons.add_rounded),
              label: const Text('Add a resolution')),
        ),
        SwitchListTile(
            contentPadding: EdgeInsets.zero,
            title: const Text('Share with members'),
            subtitle: const Text(
                'Until then only the committee can read the minutes'),
            value: _publish,
            onChanged: (v) => setState(() => _publish = v)),
        const SizedBox(height: 8),
        AppPrimaryButton(
            label: 'Save minutes', isLoading: _saving, onPressed: _save),
      ]),
    );
  }
}
