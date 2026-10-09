import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/staff/data/repositories/staff_repository.dart';
import 'package:ar_society_app/features/staff/domain/entities/staff_entities.dart';
import 'package:ar_society_app/features/staff/presentation/providers/staff_providers.dart';
import 'package:ar_society_app/features/staff/presentation/widgets/duty_sheet_actions.dart' show isoDay;
import 'package:ar_society_app/features/staff/presentation/widgets/staff_widgets.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';

/// A supervisor enters a staff member's filled-in printed sheet for one day:
/// the checklist items ticked, which duties were completed, and the in / out
/// times. Only what changed from what the app already holds is sent, and each
/// of those items is kept as "entered from paper" with who entered it.
class PaperSheetEntryScreen extends ConsumerStatefulWidget {
  final String societyId;
  final String staffId;
  final String staffName;
  final DateTime date;
  const PaperSheetEntryScreen({
    super.key,
    required this.societyId,
    required this.staffId,
    required this.staffName,
    required this.date,
  });

  @override
  ConsumerState<PaperSheetEntryScreen> createState() => _PaperSheetEntryScreenState();
}

class _PaperSheetEntryScreenState extends ConsumerState<PaperSheetEntryScreen> {
  final _formKey = GlobalKey<FormState>();
  final _inCtrl = TextEditingController();
  final _outCtrl = TextEditingController();

  late DateTime _date = widget.date;
  List<DutyEntity> _duties = [];
  bool _loading = true;
  bool _saving = false;
  String? _error;

  // What the sheet says, keyed by checklist item id. Items start as the app has them.
  final Map<String, bool> _ticked = {};
  final Map<String, TextEditingController> _remarks = {};
  final Map<String, bool> _complete = {}; // duty id -> completed
  String? _status; // null = the sheet doesn't say

  static const _statusOptions = <(String?, String)>[
    (null, "Not on the sheet — leave attendance as it is"),
    ('present', 'Present'),
    ('half_day', 'Half day'),
    ('absent', 'Absent'),
    ('leave', 'On leave'),
    ('off_duty', 'Off duty'),
  ];

  bool get _hasTimes => _status == null || _status == 'present' || _status == 'half_day' || _status == 'overtime';

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _load());
  }

  @override
  void dispose() {
    _inCtrl.dispose();
    _outCtrl.dispose();
    for (final c in _remarks.values) {
      c.dispose();
    }
    super.dispose();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    final result = await ref.read(staffRepositoryProvider).getDailyDuties(widget.societyId, isoDay(_date));
    if (!mounted) return;
    switch (result) {
      case StaffSuccess(:final data):
        final mine = data.where((d) => d.staffId == widget.staffId).toList();
        _ticked.clear();
        _complete.clear();
        for (final c in _remarks.values) {
          c.dispose();
        }
        _remarks.clear();
        for (final d in mine) {
          _complete[d.id] = d.isCompleted;
          for (final i in d.checklistItems) {
            _ticked[i.id] = i.isCompleted;
            _remarks[i.id] = TextEditingController(text: i.notes ?? '');
          }
        }
        setState(() {
          _duties = mine;
          _loading = false;
        });
      case StaffFailure(:final message):
        setState(() {
          _error = message;
          _loading = false;
        });
    }
  }

  Future<void> _pickDate() async {
    final today = DateTime.now();
    final picked = await showDatePicker(
      context: context,
      initialDate: _date,
      firstDate: today.subtract(const Duration(days: 90)),
      lastDate: today,
    );
    if (picked != null && picked != _date) {
      setState(() => _date = picked);
      _load();
    }
  }

  static String? _timeValidator(String? v) {
    final t = (v ?? '').trim();
    if (t.isEmpty) return null;
    return RegExp(r'^([01]?\d|2[0-3]):[0-5]\d$').hasMatch(t) ? null : 'Use HH:MM, e.g. 09:00';
  }

  static String _pad(String t) {
    final p = t.trim().split(':');
    return '${p[0].padLeft(2, '0')}:${p[1]}';
  }

  /// Required items still unticked on a duty marked completed.
  List<String> _missingRequired(DutyEntity d) =>
      d.checklistItems.where((i) => i.isRequired && !(_ticked[i.id] ?? false)).map((i) => i.title).toList();

  Future<void> _save() async {
    if (!_formKey.currentState!.validate()) return;
    final checkIn = _inCtrl.text.trim();
    final checkOut = _outCtrl.text.trim();
    if (checkOut.isNotEmpty && checkIn.isEmpty) {
      AppToast.error(context, 'Enter the in time as well as the out time');
      return;
    }
    for (final d in _duties) {
      if (_complete[d.id] == true && !d.isCompleted && _missingRequired(d).isNotEmpty) {
        AppToast.error(context,
            "Tick all required items before completing '${d.dutyName}': ${_missingRequired(d).join(', ')}");
        return;
      }
    }

    final duties = <Map<String, dynamic>>[];
    for (final d in _duties) {
      if (d.isVerified) continue;
      final items = <Map<String, dynamic>>[];
      for (final i in d.checklistItems) {
        final remark = _remarks[i.id]!.text.trim();
        final changed = (_ticked[i.id] ?? false) != i.isCompleted || remark != (i.notes ?? '');
        if (changed) {
          items.add({
            'item_id': i.id,
            'is_completed': _ticked[i.id] ?? false,
            if (remark.isNotEmpty) 'notes': remark,
          });
        }
      }
      final completing = _complete[d.id] == true && !d.isCompleted;
      if (items.isNotEmpty || completing) {
        duties.add({'duty_id': d.id, 'mark_complete': completing, 'items': items});
      }
    }

    final status = _status ?? ((checkIn.isNotEmpty) ? 'present' : null);
    if (status == null && duties.isEmpty) {
      AppToast.warning(context, 'Nothing to save yet — tick items, mark a duty completed or enter the times.');
      return;
    }

    setState(() => _saving = true);
    final result = await ref.read(staffRepositoryProvider).enterPaperSheet(
          staffId: widget.staffId,
          sheetDate: isoDay(_date),
          attendanceStatus: _status != null || checkIn.isNotEmpty ? status : null,
          checkIn: _hasTimes && checkIn.isNotEmpty ? _pad(checkIn) : null,
          checkOut: _hasTimes && checkOut.isNotEmpty ? _pad(checkOut) : null,
          duties: duties,
        );
    if (!mounted) return;
    setState(() => _saving = false);
    switch (result) {
      case StaffSuccess():
        ref.invalidate(societyDutiesProvider(widget.societyId));
        AppToast.success(context, 'Sheet saved');
        Navigator.pop(context, true);
      case StaffFailure(:final message):
        AppToast.error(context, message);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppTheme.surface,
      appBar: AppBar(title: const Text('Enter from sheet')),
      body: _loading
          ? const Center(child: CircularProgressIndicator(color: AppTheme.primary))
          : _error != null
              ? Center(
                  child: Column(mainAxisSize: MainAxisSize.min, children: [
                    AppErrorBanner(message: _error!),
                    const SizedBox(height: 12),
                    TextButton(onPressed: _load, child: const Text('Retry')),
                  ]),
                )
              : Form(
                  key: _formKey,
                  child: SingleChildScrollView(
                    padding: const EdgeInsets.all(20),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        _header(),
                        const SizedBox(height: 16),
                        _attendanceCard(),
                        const SizedBox(height: 16),
                        if (_duties.isEmpty)
                          const EmptyState(
                            icon: Icons.assignment_outlined,
                            title: 'No duties on this day',
                            subtitle: 'Only the in / out times can be entered.',
                          )
                        else
                          for (final d in _duties) ...[
                            _dutyCard(d),
                            const SizedBox(height: 12),
                          ],
                        const SizedBox(height: 12),
                        AppPrimaryButton(
                          label: 'Save sheet',
                          isLoading: _saving,
                          icon: Icons.save_rounded,
                          onPressed: _save,
                        ),
                      ],
                    ),
                  ),
                ),
    );
  }

  Widget _header() {
    const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    const days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
    final who = Row(children: [
      const Icon(Icons.person_rounded, color: AppTheme.primary),
      const SizedBox(width: 10),
      Expanded(
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(widget.staffName, style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w700)),
          const Text('Enter what is written on the printed sheet',
              style: TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
        ]),
      ),
    ]);
    final dateButton = OutlinedButton.icon(
      onPressed: _pickDate,
      icon: const Icon(Icons.calendar_today_rounded, size: 16),
      label: Text('${days[_date.weekday - 1]}, ${_date.day} ${months[_date.month - 1]} ${_date.year}'),
    );
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: _box(),
      // On a phone the date button would squeeze the name to nothing, so it goes underneath.
      child: LayoutBuilder(builder: (context, c) {
        if (c.maxWidth < 520) {
          return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
            who,
            const SizedBox(height: 10),
            dateButton,
          ]);
        }
        return Row(children: [Expanded(child: who), const SizedBox(width: 10), dateButton]);
      }),
    );
  }

  Widget _attendanceCard() {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: _box(),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        const Text('Attendance', style: TextStyle(fontSize: 14, fontWeight: FontWeight.w700)),
        const SizedBox(height: 10),
        DropdownButtonFormField<String?>(
          value: _status,
          isExpanded: true,
          decoration: const InputDecoration(labelText: 'Status on the sheet'),
          items: [
            for (final o in _statusOptions) DropdownMenuItem<String?>(value: o.$1, child: Text(o.$2)),
          ],
          onChanged: (v) => setState(() => _status = v),
        ),
        if (_hasTimes) ...[
          const SizedBox(height: 12),
          Row(children: [
            Expanded(
              child: TextFormField(
                controller: _inCtrl,
                decoration: const InputDecoration(labelText: 'IN time', hintText: '09:00'),
                keyboardType: TextInputType.datetime,
                inputFormatters: [LengthLimitingTextInputFormatter(5)],
                validator: _timeValidator,
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: TextFormField(
                controller: _outCtrl,
                decoration: const InputDecoration(labelText: 'OUT time', hintText: '17:30'),
                keyboardType: TextInputType.datetime,
                inputFormatters: [LengthLimitingTextInputFormatter(5)],
                validator: _timeValidator,
              ),
            ),
          ]),
          const SizedBox(height: 6),
          const Text(
            'Times as written (24-hour). An out time before the in time means the next morning, for a night shift. '
            'Entering the sheet records the attendance as approved.',
            style: TextStyle(fontSize: 12, color: AppTheme.textSecondary),
          ),
        ],
      ]),
    );
  }

  Widget _dutyCard(DutyEntity d) {
    final locked = d.isVerified;
    final window = [d.startTime, d.endTime].whereType<String>().map((t) => t.length >= 5 ? t.substring(0, 5) : t).join(' – ');
    final subtitle = [if (d.location != null) d.location!, if (window.isNotEmpty) window].join(' · ');
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: _box(),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text(d.dutyName, style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w700)),
        if (subtitle.isNotEmpty)
          Text(subtitle, style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
        if (locked)
          const Padding(
            padding: EdgeInsets.only(top: 6),
            child: Text('Already verified — it can no longer be changed.',
                style: TextStyle(fontSize: 12, color: AppTheme.warning)),
          ),
        const SizedBox(height: 6),
        for (final i in d.checklistItems)
          Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            CheckboxListTile(
              dense: true,
              contentPadding: EdgeInsets.zero,
              controlAffinity: ListTileControlAffinity.leading,
              value: _ticked[i.id] ?? false,
              onChanged: locked ? null : (v) => setState(() => _ticked[i.id] = v ?? false),
              title: Text('${i.title}${i.isRequired ? ' *' : ''}', style: const TextStyle(fontSize: 14)),
              subtitle: i.enteredFromPaper
                  ? const Text('Entered from a sheet earlier', style: TextStyle(fontSize: 11))
                  : (i.isCompleted ? const Text('Ticked in the app', style: TextStyle(fontSize: 11)) : null),
            ),
            Padding(
              padding: const EdgeInsets.only(left: 40, bottom: 6),
              child: TextField(
                controller: _remarks[i.id],
                enabled: !locked,
                maxLength: 1000,
                buildCounter: (_, {required currentLength, required isFocused, maxLength}) => null,
                style: const TextStyle(fontSize: 13),
                decoration: const InputDecoration(hintText: 'Remark from the sheet (optional)', isDense: true),
              ),
            ),
          ]),
        SwitchListTile(
          contentPadding: EdgeInsets.zero,
          dense: true,
          value: _complete[d.id] ?? false,
          onChanged: (locked || d.isCompleted) ? null : (v) => setState(() => _complete[d.id] = v),
          title: Text(d.isCompleted ? 'Duty completed' : 'Mark duty completed', style: const TextStyle(fontSize: 14)),
          subtitle: d.checklistItems.isNotEmpty && (_complete[d.id] ?? false) && !d.isCompleted && _missingRequired(d).isNotEmpty
              ? Text('Required items still unticked: ${_missingRequired(d).join(', ')}',
                  style: const TextStyle(fontSize: 12, color: AppTheme.error))
              : null,
        ),
      ]),
    );
  }

  BoxDecoration _box() => BoxDecoration(
        color: AppTheme.cardBg,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppTheme.border),
      );
}
