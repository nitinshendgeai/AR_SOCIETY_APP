import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/staff/domain/entities/staff_entities.dart';
import 'package:ar_society_app/features/staff/presentation/providers/staff_providers.dart';
import 'package:ar_society_app/features/staff/presentation/widgets/duty_sheet_actions.dart' show isoDay;
import 'package:ar_society_app/shared/widgets/app_widgets.dart';

/// Manager / supervisor screen to give a duty to one or several staff, for one
/// day or a run of days (every day, or only the chosen weekdays). Each staff
/// member gets one duty per day with its own copy of the checklist, ready to be
/// printed as a sheet or ticked in the app.
class DutyAssignScreen extends ConsumerStatefulWidget {
  final String societyId;
  final String? preSelectedStaffId;
  const DutyAssignScreen({super.key, required this.societyId, this.preSelectedStaffId});

  @override
  ConsumerState<DutyAssignScreen> createState() => _DutyAssignScreenState();
}

class _DutyAssignScreenState extends ConsumerState<DutyAssignScreen> {
  final _formKey = GlobalKey<FormState>();
  final _dutyNameCtrl  = TextEditingController();
  final _descCtrl      = TextEditingController();
  final _locationCtrl  = TextEditingController();
  final _startTimeCtrl = TextEditingController();
  final _endTimeCtrl   = TextEditingController();

  DateTime _fromDate = DateTime.now();
  DateTime? _untilDate;
  bool _repeat = false;
  final Set<int> _weekdays = {0, 1, 2, 3, 4, 5, 6}; // 0 = Monday
  final Set<String> _staffIds = {};
  String? _selectedTemplateId;

  static const _weekdayLabels = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

  // Predefined duty options by department
  static const _dutyOptions = [
    // Security
    'Main Gate',
    'Visitor Gate',
    'Parking Gate',
    'Night Patrol',
    // Housekeeping
    'Wing A',
    'Wing B',
    'Club House',
    'Garden',
    'Parking Area',
    // Technical
    'Electrical',
    'Plumbing',
    'Lift Maintenance',
    'Generator Room',
    // Custom
    'Custom',
  ];

  @override
  void initState() {
    super.initState();
    if (widget.preSelectedStaffId != null) _staffIds.add(widget.preSelectedStaffId!);
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (widget.societyId.isNotEmpty) {
        ref.read(staffListProvider.notifier).load(widget.societyId);
      }
    });
  }

  @override
  void dispose() {
    _dutyNameCtrl.dispose();
    _descCtrl.dispose();
    _locationCtrl.dispose();
    _startTimeCtrl.dispose();
    _endTimeCtrl.dispose();
    super.dispose();
  }

  /// The days the plan covers: [_fromDate].._untilDate, only the chosen weekdays.
  List<DateTime> get _days {
    if (!_repeat || _untilDate == null) return [_fromDate];
    final out = <DateTime>[];
    for (var d = _fromDate; !d.isAfter(_untilDate!); d = d.add(const Duration(days: 1))) {
      if (_weekdays.contains(d.weekday - 1)) out.add(d);
    }
    return out;
  }

  @override
  Widget build(BuildContext context) {
    final assignState = ref.watch(dutyAssignProvider);
    final staffState  = ref.watch(staffListProvider);
    final isLoading   = assignState is DutyAssignLoading;

    ref.listen(dutyAssignProvider, (_, next) {
      if (next is DutyAssignSuccess) {
        ref.read(dutyAssignProvider.notifier).reset();
        _showResult(next.result);
      } else if (next is DutyAssignError) {
        AppToast.error(context, next.message);
      }
    });

    // New staff start on probation and work like anyone else; only people who
    // have left or been made inactive are left out (as the server does).
    final staffList = staffState is StaffListLoaded
        ? staffState.staff.where((s) => s.status != 'inactive' && s.status != 'terminated').toList()
        : <StaffEntity>[];
    final selected = staffList.where((s) => _staffIds.contains(s.id)).toList();
    final days = _days;

    return Scaffold(
      backgroundColor: AppTheme.surface,
      appBar: AppBar(title: const Text('Assign Duty')),
      body: Form(
        key: _formKey,
        // A plain scroll view, not a lazy ListView: fields scrolled out of
        // view stay mounted, so validate() checks every one of them.
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(20),
          child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            _Label('Assign to  (${_staffIds.length} selected)'),
            const SizedBox(height: 8),
            if (staffState is StaffListLoading)
              const Center(child: CircularProgressIndicator(color: AppTheme.primary))
            else
              _StaffPicker(
                staff: staffList,
                selectedIds: _staffIds,
                onChanged: (ids) => setState(() {
                  _staffIds
                    ..clear()
                    ..addAll(ids);
                  _selectedTemplateId = null;
                }),
              ),
            const SizedBox(height: 16),

            // Checklist template (optional) — the departments of the chosen
            // staff; picking one copies its items onto every duty made.
            if (selected.isNotEmpty) ...[
              const _Label('Checklist Template (optional)'),
              const SizedBox(height: 8),
              _ChecklistTemplateDropdown(
                societyId: widget.societyId,
                departments: selected.map((s) => s.department).toSet(),
                selectedId: _selectedTemplateId,
                onChanged: (t) => setState(() {
                  _selectedTemplateId = t?.id;
                  if (t != null && _dutyNameCtrl.text.trim().isEmpty) {
                    _dutyNameCtrl.text = t.name;
                  }
                }),
              ),
              const SizedBox(height: 16),
            ],

            // Duty name (predefined + custom)
            const _Label('Duty'),
            const SizedBox(height: 8),
            DropdownButtonFormField<String>(
              value: _dutyOptions.contains(_dutyNameCtrl.text) ? _dutyNameCtrl.text : null,
              decoration: const InputDecoration(hintText: 'Select duty type'),
              items: _dutyOptions.map((d) => DropdownMenuItem(value: d, child: Text(d))).toList(),
              onChanged: (v) {
                if (v == 'Custom') {
                  _dutyNameCtrl.clear();
                } else {
                  _dutyNameCtrl.text = v ?? '';
                }
                setState(() {});
              },
            ),
            if (_dutyNameCtrl.text.isEmpty) ...[
              const SizedBox(height: 8),
              TextFormField(
                controller: _dutyNameCtrl,
                inputFormatters: [LengthLimitingTextInputFormatter(255)],
                decoration: const InputDecoration(hintText: 'Enter custom duty name'),
                validator: (v) => (v == null || v.trim().isEmpty) ? 'Duty name required' : null,
              ),
            ],
            const SizedBox(height: 16),

            // Description
            const _Label('Description (optional)'),
            const SizedBox(height: 8),
            TextFormField(
              controller: _descCtrl,
              inputFormatters: [LengthLimitingTextInputFormatter(2000)],
              maxLines: 2,
              decoration: const InputDecoration(hintText: 'Add details about this duty'),
            ),
            const SizedBox(height: 16),

            // Location
            const _Label('Location (optional)'),
            const SizedBox(height: 8),
            TextFormField(
              controller: _locationCtrl,
              inputFormatters: [LengthLimitingTextInputFormatter(255)],
              decoration: const InputDecoration(hintText: 'e.g. Gate 1, Wing B'),
            ),
            const SizedBox(height: 16),

            // Date
            _Label(_repeat ? 'From' : 'Duty Date'),
            const SizedBox(height: 8),
            _DateBox(date: _fromDate, onTap: _pickFrom),
            const SizedBox(height: 4),
            SwitchListTile(
              contentPadding: EdgeInsets.zero,
              dense: true,
              title: const Text('Repeat on more days', style: TextStyle(fontSize: 14)),
              subtitle: const Text('A daily round, or the same duty on certain weekdays',
                  style: TextStyle(fontSize: 12)),
              value: _repeat,
              onChanged: (v) => setState(() {
                _repeat = v;
                if (v) _untilDate ??= _fromDate.add(const Duration(days: 6));
              }),
            ),
            if (_repeat) ...[
              const SizedBox(height: 8),
              const _Label('Until'),
              const SizedBox(height: 8),
              _DateBox(date: _untilDate ?? _fromDate, onTap: _pickUntil),
              const SizedBox(height: 12),
              const _Label('On these days'),
              const SizedBox(height: 8),
              Wrap(
                spacing: 8,
                children: [
                  for (var i = 0; i < 7; i++)
                    FilterChip(
                      label: Text(_weekdayLabels[i]),
                      selected: _weekdays.contains(i),
                      onSelected: (on) => setState(() => on ? _weekdays.add(i) : _weekdays.remove(i)),
                    ),
                ],
              ),
            ],
            const SizedBox(height: 16),

            // Times
            Row(
              children: [
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const _Label('Start Time'),
                      const SizedBox(height: 8),
                      TextFormField(
                        controller: _startTimeCtrl,
                        decoration: const InputDecoration(hintText: '09:00'),
                        keyboardType: TextInputType.datetime,
                        inputFormatters: [LengthLimitingTextInputFormatter(5)],
                        validator: _timeValidator,
                      ),
                    ],
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const _Label('End Time'),
                      const SizedBox(height: 8),
                      TextFormField(
                        controller: _endTimeCtrl,
                        decoration: const InputDecoration(hintText: '17:00'),
                        keyboardType: TextInputType.datetime,
                        inputFormatters: [LengthLimitingTextInputFormatter(5)],
                        validator: _timeValidator,
                      ),
                    ],
                  ),
                ),
              ],
            ),
            const SizedBox(height: 20),

            _Summary(staff: _staffIds.length, days: days.length),
            const SizedBox(height: 16),

            AppPrimaryButton(
              label: _staffIds.length * days.length > 1 ? 'Assign Duties' : 'Assign Duty',
              isLoading: isLoading,
              icon: Icons.assignment_turned_in_rounded,
              onPressed: _submit,
            ),
          ],
          ),
        ),
      ),
    );
  }

  /// "9:30" as the server wants it, "09:30".
  static String? _padTime(String text) {
    final t = text.trim();
    if (t.isEmpty) return null;
    final parts = t.split(':');
    return '${parts[0].padLeft(2, '0')}:${parts[1]}';
  }

  /// "HH:MM" (24-hour) or empty.
  static String? _timeValidator(String? v) {
    final t = (v ?? '').trim();
    if (t.isEmpty) return null;
    return RegExp(r'^([01]?\d|2[0-3]):[0-5]\d$').hasMatch(t) ? null : 'Use HH:MM, e.g. 09:00';
  }

  Future<void> _pickFrom() async {
    final today = DateTime.now();
    final picked = await showDatePicker(
      context: context,
      initialDate: _fromDate,
      firstDate: DateTime(today.year, today.month, today.day),
      lastDate: today.add(const Duration(days: 90)),
    );
    if (picked == null) return;
    setState(() {
      _fromDate = picked;
      if (_untilDate != null && _untilDate!.isBefore(picked)) _untilDate = picked;
    });
  }

  Future<void> _pickUntil() async {
    final picked = await showDatePicker(
      context: context,
      initialDate: _untilDate ?? _fromDate,
      firstDate: _fromDate,
      lastDate: _fromDate.add(const Duration(days: 61)),
    );
    if (picked != null) setState(() => _untilDate = picked);
  }

  void _submit() {
    if (widget.societyId.isEmpty) {
      AppToast.error(context, 'Society context is missing. Please go back and try again.');
      return;
    }
    if (_staffIds.isEmpty) {
      AppToast.error(context, 'Please select at least one staff member');
      return;
    }
    if (_repeat && _weekdays.isEmpty) {
      AppToast.error(context, 'Choose at least one day of the week');
      return;
    }
    if (!_formKey.currentState!.validate()) return;
    final days = _days;
    if (days.isEmpty) {
      AppToast.error(context, 'None of the days in that range fall on the chosen weekdays');
      return;
    }
    if (_staffIds.length * days.length > 600) {
      AppToast.error(context, 'That is ${_staffIds.length * days.length} duties; at most 600 at a time. '
          'Choose fewer staff or days.');
      return;
    }

    ref.read(dutyAssignProvider.notifier).assignPlan(
      societyId: widget.societyId,
      staffIds: _staffIds.toList(),
      dutyName: _dutyNameCtrl.text.trim(),
      fromDate: isoDay(_fromDate),
      toDate: _repeat ? isoDay(_untilDate ?? _fromDate) : null,
      weekdays: _repeat && _weekdays.length < 7 ? (_weekdays.toList()..sort()) : null,
      description: _descCtrl.text.trim().isEmpty ? null : _descCtrl.text.trim(),
      location: _locationCtrl.text.trim().isEmpty ? null : _locationCtrl.text.trim(),
      startTime: _padTime(_startTimeCtrl.text),
      endTime: _padTime(_endTimeCtrl.text),
      checklistTemplateId: _selectedTemplateId,
    );
  }

  /// Says what was made and, when some days were left out, which and why.
  Future<void> _showResult(DutyPlanResultEntity result) async {
    if (result.skipped.isEmpty) {
      AppToast.success(context, result.created == 1 ? 'Duty assigned' : '${result.created} duties assigned');
      Navigator.pop(context, true);
      return;
    }
    final byReason = <String, List<DutyPlanSkipEntity>>{};
    for (final s in result.skipped) {
      byReason.putIfAbsent(s.reason, () => []).add(s);
    }
    await showDialog<void>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(result.created == 0 ? 'Nothing was assigned' : '${result.created} duties assigned'),
        content: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('${result.skipped.length} left out:',
                  style: const TextStyle(fontWeight: FontWeight.w600)),
              const SizedBox(height: 8),
              for (final e in byReason.entries) ...[
                Text(e.key, style: const TextStyle(fontSize: 13, color: AppTheme.textSecondary)),
                for (final s in e.value.take(12))
                  Padding(
                    padding: const EdgeInsets.only(left: 8, top: 2),
                    child: Text('${s.staffName} · ${s.dutyDate}', style: const TextStyle(fontSize: 13)),
                  ),
                if (e.value.length > 12)
                  Padding(
                    padding: const EdgeInsets.only(left: 8, top: 2),
                    child: Text('…and ${e.value.length - 12} more', style: const TextStyle(fontSize: 13)),
                  ),
                const SizedBox(height: 8),
              ],
            ],
          ),
        ),
        actions: [TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('OK'))],
      ),
    );
    if (mounted && result.created > 0) Navigator.pop(context, true);
  }
}

class _Label extends StatelessWidget {
  final String text;
  const _Label(this.text);

  @override
  Widget build(BuildContext context) => Text(
    text,
    style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: AppTheme.textSecondary),
  );
}

class _DateBox extends StatelessWidget {
  final DateTime date;
  final VoidCallback onTap;
  const _DateBox({required this.date, required this.onTap});

  @override
  Widget build(BuildContext context) => InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(12),
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 14),
          decoration: BoxDecoration(
            color: AppTheme.cardBg,
            borderRadius: BorderRadius.circular(12),
            border: Border.all(color: AppTheme.border),
          ),
          child: Row(
            children: [
              const Icon(Icons.calendar_today_rounded, color: AppTheme.primary, size: 18),
              const SizedBox(width: 10),
              Text(
                '${date.day}/${date.month}/${date.year}',
                style: const TextStyle(fontSize: 14, color: AppTheme.textPrimary),
              ),
            ],
          ),
        ),
      );
}

class _Summary extends StatelessWidget {
  final int staff;
  final int days;
  const _Summary({required this.staff, required this.days});

  @override
  Widget build(BuildContext context) {
    final total = staff * days;
    final text = staff == 0
        ? 'Choose who the duty is for.'
        : days == 0
            ? 'None of the chosen days fall in that range.'
            : total == 1
                ? 'Makes 1 duty.'
                : 'Makes $total duties ($staff staff × $days ${days == 1 ? 'day' : 'days'}). '
                    'Days on approved leave or already planned are left out.';
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: AppTheme.primary.withOpacity(0.06),
        borderRadius: BorderRadius.circular(10),
      ),
      child: Row(children: [
        const Icon(Icons.info_outline_rounded, size: 16, color: AppTheme.primary),
        const SizedBox(width: 8),
        Expanded(child: Text(text, style: const TextStyle(fontSize: 12.5, color: AppTheme.textSecondary))),
      ]),
    );
  }
}

class _ChecklistTemplateDropdown extends ConsumerWidget {
  final String societyId;
  final Set<String> departments;
  final String? selectedId;
  final void Function(ChecklistTemplateEntity?) onChanged;

  const _ChecklistTemplateDropdown({
    required this.societyId, required this.departments, this.selectedId, required this.onChanged,
  });

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final templatesAsync = ref.watch(checklistTemplatesProvider(societyId));
    return templatesAsync.when(
      loading: () => const LinearProgressIndicator(),
      error: (_, __) => const SizedBox.shrink(), // optional field — fail silently
      data: (all) {
        final templates = all.where((t) => departments.contains(t.department)).toList();
        if (templates.isEmpty) {
          return const Text('No checklist templates for the chosen staff yet.',
              style: TextStyle(fontSize: 12, color: AppTheme.textSecondary));
        }
        return DropdownButtonFormField<ChecklistTemplateEntity>(
          value: templates.where((t) => t.id == selectedId).firstOrNull,
          decoration: const InputDecoration(hintText: 'None — free-text duty'),
          items: templates
              .map((t) => DropdownMenuItem(
                    value: t,
                    child: Text('${t.name} (${t.items.length} items)', overflow: TextOverflow.ellipsis),
                  ))
              .toList(),
          onChanged: onChanged,
        );
      },
    );
  }
}

/// Staff as chips, grouped by department, with "all / none" for each group.
class _StaffPicker extends StatelessWidget {
  final List<StaffEntity> staff;
  final Set<String> selectedIds;
  final void Function(Set<String>) onChanged;

  const _StaffPicker({required this.staff, required this.selectedIds, required this.onChanged});

  @override
  Widget build(BuildContext context) {
    if (staff.isEmpty) {
      return Container(
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          color: AppTheme.cardBg,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: AppTheme.border),
        ),
        child: const Text('No staff found. Add staff first.',
            style: TextStyle(color: AppTheme.textSecondary, fontSize: 13)),
      );
    }
    final byDept = <String, List<StaffEntity>>{};
    for (final s in staff) {
      byDept.putIfAbsent(s.department, () => []).add(s);
    }
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: AppTheme.cardBg,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppTheme.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          for (final e in byDept.entries) ...[
            Row(children: [
              Text(e.value.first.departmentLabel,
                  style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w700, color: AppTheme.textSecondary)),
              const Spacer(),
              TextButton(
                style: TextButton.styleFrom(
                    visualDensity: VisualDensity.compact, padding: const EdgeInsets.symmetric(horizontal: 8)),
                onPressed: () {
                  final ids = e.value.map((s) => s.id).toSet();
                  final all = ids.every(selectedIds.contains);
                  onChanged(all ? (selectedIds.toSet()..removeAll(ids)) : (selectedIds.toSet()..addAll(ids)));
                },
                child: Text(e.value.every((s) => selectedIds.contains(s.id)) ? 'Clear' : 'Select all',
                    style: const TextStyle(fontSize: 12)),
              ),
            ]),
            Wrap(
              spacing: 8,
              runSpacing: 4,
              children: [
                for (final s in e.value)
                  FilterChip(
                    label: Text(s.fullName),
                    selected: selectedIds.contains(s.id),
                    onSelected: (on) =>
                        onChanged(on ? (selectedIds.toSet()..add(s.id)) : (selectedIds.toSet()..remove(s.id))),
                  ),
              ],
            ),
            const SizedBox(height: 8),
          ],
        ],
      ),
    );
  }
}
