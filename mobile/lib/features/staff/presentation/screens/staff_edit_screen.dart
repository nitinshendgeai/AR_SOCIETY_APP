import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/features/staff/domain/entities/staff_entities.dart';
import 'package:ar_society_app/features/staff/presentation/providers/staff_providers.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';

/// Form to edit an existing staff member's record.
/// Receives [StaffEntity] via GoRouter extra.
class StaffEditScreen extends ConsumerStatefulWidget {
  final StaffEntity staff;
  const StaffEditScreen({super.key, required this.staff});

  @override
  ConsumerState<StaffEditScreen> createState() => _StaffEditScreenState();
}

class _StaffEditScreenState extends ConsumerState<StaffEditScreen> {
  final _formKey = GlobalKey<FormState>();

  late final TextEditingController _nameCtrl;
  late final TextEditingController _mobileCtrl;
  late final TextEditingController _emailCtrl;

  String? _selectedDept;
  String? _selectedDesignationId;
  String? _selectedShiftId;
  String? _selectedStatus;
  String? _selectedReportingManagerId;

  static const _departments = [
    ('security',     'Security'),
    ('housekeeping', 'Housekeeping'),
    ('technical',    'Technical'),
    ('gym',          'Gym'),
    ('admin',        'Administration'),
  ];

  static const _statuses = [
    ('active',     'Active'),
    ('probation',  'Probation'),
    ('on_leave',   'On Leave'),
    ('inactive',   'Inactive'),
    ('terminated', 'Terminated'),
  ];

  @override
  void initState() {
    super.initState();
    _nameCtrl   = TextEditingController(text: widget.staff.fullName);
    _mobileCtrl = TextEditingController(text: widget.staff.mobile);
    _emailCtrl  = TextEditingController(text: widget.staff.email ?? '');
    _selectedDept             = widget.staff.department;
    _selectedDesignationId    = widget.staff.designationId;
    _selectedShiftId          = widget.staff.shiftId;
    _selectedStatus           = widget.staff.status;
    _selectedReportingManagerId = widget.staff.reportingManagerId;
  }

  @override
  void dispose() {
    _nameCtrl.dispose();
    _mobileCtrl.dispose();
    _emailCtrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final user      = ref.watch(currentUserProvider);
    final societyId = user?.societyId ?? '';
    final formState = ref.watch(staffFormProvider);
    final isLoading = formState is StaffFormLoading;

    final designationsAsync = ref.watch(designationsProvider(societyId));
    final shiftsAsync       = ref.watch(shiftsProvider(societyId));
    final staffAsync        = ref.watch(staffListProvider);

    final allDesignations = designationsAsync.valueOrNull ?? <DesignationEntity>[];
    final deptDesignations = _selectedDept == null
        ? allDesignations
        : allDesignations.where((d) => d.department == _selectedDept).toList();
    final allShifts = shiftsAsync.valueOrNull ?? <ShiftEntity>[];

    final allStaff = staffAsync is StaffListLoaded ? staffAsync.staff : <StaffEntity>[];
    final managers = allStaff
        .where((s) => s.id != widget.staff.id)
        .where((s) =>
          s.department == 'admin' ||
          (s.designationName?.toLowerCase().contains('manager') ?? false) ||
          (s.designationName?.toLowerCase().contains('supervisor') ?? false))
        .toList();

    ref.listen(staffFormProvider, (_, next) {
      if (next is StaffFormSuccess) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(
          content: Text(next.message),
          backgroundColor: AppTheme.success,
          behavior: SnackBarBehavior.floating,
        ));
        ref.read(staffListProvider.notifier).load(societyId);
        ref.read(staffFormProvider.notifier).reset();
        // Pop edit, then pop detail → back to list
        context.pop();
        context.pop();
      } else if (next is StaffFormError) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(
          content: Text(next.message),
          backgroundColor: AppTheme.error,
          behavior: SnackBarBehavior.floating,
        ));
      }
    });

    return Scaffold(
      backgroundColor: AppTheme.surface,
      appBar: AppBar(
        title: Text('Edit — ${widget.staff.fullName}'),
      ),
      body: Form(
        key: _formKey,
        child: ListView(
          padding: const EdgeInsets.all(20),
          children: [
            // Employee code badge (read-only)
            Container(
              padding: const EdgeInsets.all(14),
              margin: const EdgeInsets.only(bottom: 20),
              decoration: BoxDecoration(
                color: AppTheme.primary.withOpacity(0.06),
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: AppTheme.primary.withOpacity(0.2)),
              ),
              child: Row(
                children: [
                  const Icon(Icons.badge_rounded, color: AppTheme.primary, size: 18),
                  const SizedBox(width: 10),
                  Text('Employee Code: ${widget.staff.employeeCode}',
                      style: const TextStyle(fontWeight: FontWeight.w700,
                          fontSize: 13, color: AppTheme.primary)),
                ],
              ),
            ),

            // ── Personal ──────────────────────────────────────────────────
            const _SectionHeader('Personal Details'),
            const SizedBox(height: 10),

            _FormField(
              label: 'Full Name *',
              child: TextFormField(
                controller: _nameCtrl,
                decoration: const InputDecoration(hintText: 'Enter full name'),
                textCapitalization: TextCapitalization.words,
                validator: (v) => (v == null || v.trim().isEmpty) ? 'Name is required' : null,
              ),
            ),

            _FormField(
              label: 'Mobile Number *',
              child: TextFormField(
                controller: _mobileCtrl,
                decoration: const InputDecoration(hintText: '10-digit mobile number'),
                keyboardType: TextInputType.phone,
                validator: (v) {
                  if (v == null || v.trim().isEmpty) return 'Mobile is required';
                  if (v.trim().length < 10) return 'Enter a valid mobile number';
                  return null;
                },
              ),
            ),

            _FormField(
              label: 'Email (optional)',
              child: TextFormField(
                controller: _emailCtrl,
                decoration: const InputDecoration(hintText: 'staff@example.com'),
                keyboardType: TextInputType.emailAddress,
              ),
            ),

            // ── Employment ────────────────────────────────────────────────
            const SizedBox(height: 8),
            const _SectionHeader('Employment Details'),
            const SizedBox(height: 10),

            _FormField(
              label: 'Department',
              child: DropdownButtonFormField<String>(
                value: _selectedDept,
                decoration: const InputDecoration(hintText: 'Select department'),
                items: _departments
                    .map((d) => DropdownMenuItem(value: d.$1, child: Text(d.$2)))
                    .toList(),
                onChanged: (v) => setState(() {
                  _selectedDept = v;
                  _selectedDesignationId = null;
                }),
              ),
            ),

            if (deptDesignations.isNotEmpty)
              _FormField(
                label: 'Designation',
                child: DropdownButtonFormField<String>(
                  value: deptDesignations.any((d) => d.id == _selectedDesignationId)
                      ? _selectedDesignationId
                      : null,
                  decoration: const InputDecoration(hintText: 'Select designation'),
                  items: deptDesignations
                      .map((d) => DropdownMenuItem(value: d.id, child: Text(d.name)))
                      .toList(),
                  onChanged: (v) => setState(() => _selectedDesignationId = v),
                ),
              ),

            if (allShifts.isNotEmpty)
              _FormField(
                label: 'Shift',
                child: DropdownButtonFormField<String>(
                  value: allShifts.any((s) => s.id == _selectedShiftId) ? _selectedShiftId : null,
                  decoration: const InputDecoration(hintText: 'Select shift'),
                  items: allShifts
                      .map((s) => DropdownMenuItem(
                            value: s.id,
                            child: Text('${s.name} (${s.startTime}–${s.endTime})'),
                          ))
                      .toList(),
                  onChanged: (v) => setState(() => _selectedShiftId = v),
                ),
              ),

            _FormField(
              label: 'Employment Status',
              child: DropdownButtonFormField<String>(
                value: _selectedStatus,
                decoration: const InputDecoration(hintText: 'Select status'),
                items: _statuses
                    .map((s) => DropdownMenuItem(value: s.$1, child: Text(s.$2)))
                    .toList(),
                onChanged: (v) => setState(() => _selectedStatus = v),
              ),
            ),

            // ── Reporting ─────────────────────────────────────────────────
            const SizedBox(height: 8),
            const _SectionHeader('Reporting Structure'),
            const SizedBox(height: 10),

            _FormField(
              label: 'Reporting Manager',
              child: DropdownButtonFormField<String>(
                value: managers.any((s) => s.userId == _selectedReportingManagerId)
                    ? _selectedReportingManagerId
                    : null,
                decoration: const InputDecoration(hintText: 'Select reporting manager'),
                items: [
                  const DropdownMenuItem(value: null, child: Text('No reporting manager')),
                  ...managers.map((s) => DropdownMenuItem(
                        value: s.userId,
                        child: Text('${s.fullName} (${s.departmentLabel})',
                            overflow: TextOverflow.ellipsis),
                      )),
                ],
                onChanged: (v) => setState(() => _selectedReportingManagerId = v),
              ),
            ),

            const SizedBox(height: 32),

            // Deactivate shortcut
            if (_selectedStatus != 'inactive' && _selectedStatus != 'terminated')
              OutlinedButton.icon(
                onPressed: () {
                  setState(() => _selectedStatus = 'inactive');
                  ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
                    content: Text('Status set to Inactive — tap Save to confirm'),
                    behavior: SnackBarBehavior.floating,
                  ));
                },
                icon: const Icon(Icons.person_off_rounded, size: 18),
                label: const Text('Deactivate Staff'),
                style: OutlinedButton.styleFrom(
                  foregroundColor: AppTheme.error,
                  side: const BorderSide(color: AppTheme.error),
                  padding: const EdgeInsets.symmetric(vertical: 12),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                ),
              ),

            const SizedBox(height: 12),

            AppPrimaryButton(
              label: 'Save Changes',
              icon: Icons.save_rounded,
              isLoading: isLoading,
              onPressed: _submit,
            ),
          ],
        ),
      ),
    );
  }

  void _submit() {
    if (!_formKey.currentState!.validate()) return;

    final data = <String, dynamic>{
      if (_nameCtrl.text.trim().isNotEmpty)   'full_name': _nameCtrl.text.trim(),
      if (_mobileCtrl.text.trim().isNotEmpty) 'mobile':    _mobileCtrl.text.trim(),
      if (_emailCtrl.text.trim().isNotEmpty)  'email':     _emailCtrl.text.trim(),
      if (_selectedDept != null)              'department': _selectedDept,
      if (_selectedDesignationId != null)     'designation_id': _selectedDesignationId,
      if (_selectedShiftId != null)           'shift_id': _selectedShiftId,
      if (_selectedStatus != null)            'status': _selectedStatus,
      'reporting_manager_id': _selectedReportingManagerId,
    };

    ref.read(staffFormProvider.notifier).update(widget.staff.id, data);
  }
}

class _SectionHeader extends StatelessWidget {
  final String text;
  const _SectionHeader(this.text);

  @override
  Widget build(BuildContext context) => Text(
    text,
    style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w700,
        color: AppTheme.primary, letterSpacing: 0.4),
  );
}

class _FormField extends StatelessWidget {
  final String label;
  final Widget child;
  const _FormField({required this.label, required this.child});

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.only(bottom: 16),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(label, style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600,
            color: AppTheme.textSecondary)),
        const SizedBox(height: 6),
        child,
      ],
    ),
  );
}
