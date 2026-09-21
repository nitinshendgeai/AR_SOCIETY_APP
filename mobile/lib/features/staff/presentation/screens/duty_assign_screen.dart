import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/staff/domain/entities/staff_entities.dart';
import 'package:ar_society_app/features/staff/presentation/providers/staff_providers.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';

/// Supervisor screen to assign a duty to a staff member.
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

  DateTime _dutyDate = DateTime.now();
  String? _selectedStaffId;
  String? _selectedTemplateId;

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
    _selectedStaffId = widget.preSelectedStaffId;
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

  @override
  Widget build(BuildContext context) {
    final assignState = ref.watch(dutyAssignProvider);
    final staffState  = ref.watch(staffListProvider);
    final isLoading   = assignState is DutyAssignLoading;

    ref.listen(dutyAssignProvider, (_, next) {
      if (next is DutyAssignSuccess) {
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
          content: Text('Duty assigned successfully'),
          backgroundColor: AppTheme.success,
          behavior: SnackBarBehavior.floating,
        ));
        ref.read(dutyAssignProvider.notifier).reset();
        Navigator.pop(context, true);
      } else if (next is DutyAssignError) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(
          content: Text(next.message),
          backgroundColor: AppTheme.error,
          behavior: SnackBarBehavior.floating,
        ));
      }
    });

    final staffList = staffState is StaffListLoaded
        ? staffState.staff.where((s) => s.status == 'active').toList()
        : <StaffEntity>[];

    return Scaffold(
      backgroundColor: AppTheme.surface,
      appBar: AppBar(title: const Text('Assign Duty')),
      body: Form(
        key: _formKey,
        child: ListView(
          padding: const EdgeInsets.all(20),
          children: [
            // Staff selector
            const _Label('Assign To'),
            const SizedBox(height: 8),
            if (staffState is StaffListLoading)
              const Center(child: CircularProgressIndicator(color: AppTheme.primary))
            else
              _StaffDropdown(
                staff: staffList,
                selectedId: _selectedStaffId,
                onChanged: (s) => setState(() {
                  _selectedStaffId = s?.id;
                  _selectedTemplateId = null;
                }),
              ),
            const SizedBox(height: 16),

            // Checklist template (optional) — filtered to the selected
            // staff member's department; picking one snapshots its items
            // onto the duty (see StaffService.assign_duty on the backend).
            if (_selectedStaffId != null) ...[
              const _Label('Checklist Template (optional)'),
              const SizedBox(height: 8),
              _ChecklistTemplateDropdown(
                societyId: widget.societyId,
                department: staffList.where((s) => s.id == _selectedStaffId).firstOrNull?.department,
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
                decoration: const InputDecoration(hintText: 'Enter custom duty name'),
                validator: (v) => (v == null || v.isEmpty) ? 'Duty name required' : null,
              ),
            ],
            const SizedBox(height: 16),

            // Description
            const _Label('Description (optional)'),
            const SizedBox(height: 8),
            TextFormField(
              controller: _descCtrl,
              maxLines: 2,
              decoration: const InputDecoration(hintText: 'Add details about this duty'),
            ),
            const SizedBox(height: 16),

            // Location
            const _Label('Location (optional)'),
            const SizedBox(height: 8),
            TextFormField(
              controller: _locationCtrl,
              decoration: const InputDecoration(hintText: 'e.g. Gate 1, Wing B'),
            ),
            const SizedBox(height: 16),

            // Date
            const _Label('Duty Date'),
            const SizedBox(height: 8),
            InkWell(
              onTap: _pickDate,
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
                      '${_dutyDate.day}/${_dutyDate.month}/${_dutyDate.year}',
                      style: const TextStyle(fontSize: 14, color: AppTheme.textPrimary),
                    ),
                  ],
                ),
              ),
            ),
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
                      ),
                    ],
                  ),
                ),
              ],
            ),
            const SizedBox(height: 28),

            AppPrimaryButton(
              label: 'Assign Duty',
              isLoading: isLoading,
              icon: Icons.assignment_turned_in_rounded,
              onPressed: _submit,
            ),
          ],
        ),
      ),
    );
  }

  Future<void> _pickDate() async {
    final picked = await showDatePicker(
      context: context,
      initialDate: _dutyDate,
      firstDate: DateTime.now(),
      lastDate: DateTime.now().add(const Duration(days: 30)),
    );
    if (picked != null) setState(() => _dutyDate = picked);
  }

  void _submit() {
    if (widget.societyId.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
        content: Text('Society context is missing. Please go back and try again.'),
        backgroundColor: AppTheme.error,
        behavior: SnackBarBehavior.floating,
      ));
      return;
    }
    if (_selectedStaffId == null) {
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
        content: Text('Please select a staff member'),
        backgroundColor: AppTheme.error,
      ));
      return;
    }
    if (!_formKey.currentState!.validate()) return;

    final dateStr = '${_dutyDate.year}-${_dutyDate.month.toString().padLeft(2,'0')}-${_dutyDate.day.toString().padLeft(2,'0')}';

    ref.read(dutyAssignProvider.notifier).assign(
      staffId: _selectedStaffId!,
      societyId: widget.societyId,
      dutyName: _dutyNameCtrl.text.trim(),
      dutyDate: dateStr,
      description: _descCtrl.text.trim().isEmpty ? null : _descCtrl.text.trim(),
      location: _locationCtrl.text.trim().isEmpty ? null : _locationCtrl.text.trim(),
      startTime: _startTimeCtrl.text.trim().isEmpty ? null : _startTimeCtrl.text.trim(),
      endTime: _endTimeCtrl.text.trim().isEmpty ? null : _endTimeCtrl.text.trim(),
      checklistTemplateId: _selectedTemplateId,
    );
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

class _ChecklistTemplateDropdown extends ConsumerWidget {
  final String societyId;
  final String? department;
  final String? selectedId;
  final void Function(ChecklistTemplateEntity?) onChanged;

  const _ChecklistTemplateDropdown({
    required this.societyId, this.department, this.selectedId, required this.onChanged,
  });

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final templatesAsync = ref.watch(checklistTemplatesProvider(societyId));
    return templatesAsync.when(
      loading: () => const LinearProgressIndicator(),
      error: (_, __) => const SizedBox.shrink(), // optional field — fail silently
      data: (all) {
        final templates = department == null
            ? all
            : all.where((t) => t.department == department).toList();
        if (templates.isEmpty) {
          return Text('No checklist templates for this department yet.',
              style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary));
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

class _StaffDropdown extends StatelessWidget {
  final List<StaffEntity> staff;
  final String? selectedId;
  final void Function(StaffEntity?) onChanged;

  const _StaffDropdown({required this.staff, this.selectedId, required this.onChanged});

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
        child: const Text('No staff found. Load staff list first.',
            style: TextStyle(color: AppTheme.textSecondary, fontSize: 13)),
      );
    }
    return DropdownButtonFormField<StaffEntity>(
      value: staff.where((s) => s.id == selectedId).firstOrNull,
      decoration: const InputDecoration(hintText: 'Select staff member'),
      items: staff.map((s) => DropdownMenuItem(
        value: s,
        child: Text('${s.fullName} (${s.departmentLabel})', overflow: TextOverflow.ellipsis),
      )).toList(),
      onChanged: onChanged,
      validator: (_) => selectedId == null ? 'Select a staff member' : null,
    );
  }
}
