import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:ar_society_app/features/resident_master/presentation/widgets/resident_master_widgets.dart' show rmPhoneValidator, rmEmailValidator;
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:ar_society_app/core/router/app_router.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/features/staff/domain/entities/staff_entities.dart';
import 'package:ar_society_app/features/staff/presentation/providers/staff_providers.dart';
import 'package:ar_society_app/shared/widgets/app_form.dart';

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
  late final TextEditingController _emergencyNameCtrl;
  late final TextEditingController _emergencyPhoneCtrl;
  late final TextEditingController _addressCtrl;
  late final TextEditingController _notesCtrl;

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
    ('maintenance',  'Maintenance'),
    ('electrical',   'Electrical'),
    ('plumbing',     'Plumbing'),
    ('gardening',    'Gardening'),
    ('amenities',    'Amenities'),
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
    _nameCtrl           = TextEditingController(text: widget.staff.fullName);
    _mobileCtrl         = TextEditingController(text: widget.staff.mobile);
    _emailCtrl          = TextEditingController(text: widget.staff.email ?? '');
    _emergencyNameCtrl  = TextEditingController(text: widget.staff.emergencyContactName ?? '');
    _emergencyPhoneCtrl = TextEditingController(text: widget.staff.emergencyContactPhone ?? '');
    _addressCtrl        = TextEditingController(text: widget.staff.address ?? '');
    _notesCtrl          = TextEditingController(text: widget.staff.notes ?? '');
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
    _emergencyNameCtrl.dispose();
    _emergencyPhoneCtrl.dispose();
    _addressCtrl.dispose();
    _notesCtrl.dispose();
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
        context.go(AppRoutes.staffList);
      } else if (next is StaffFormError) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(
          content: Text(next.message),
          backgroundColor: AppTheme.error,
          behavior: SnackBarBehavior.floating,
        ));
      }
    });

    return AppFormPage(
      title: 'Edit Staff',
      subtitle: '${widget.staff.fullName} · Employee code ${widget.staff.employeeCode}',
      formKey: _formKey,
      submitLabel: 'Save Changes',
      submitIcon: Icons.save_rounded,
      saving: isLoading,
      onSubmit: _submit,
      children: [
        FormSection(
          title: 'Personal details',
          children: [
            FormFieldBox(
              label: 'Full name',
              required: true,
              child: TextFormField(
                controller: _nameCtrl,
                decoration: const InputDecoration(hintText: 'Enter full name'),
                textCapitalization: TextCapitalization.words,
                inputFormatters: [LengthLimitingTextInputFormatter(255)],
                validator: (v) => (v == null || v.trim().isEmpty) ? 'Name is required' : null,
              ),
            ),
            FormFieldBox(
              label: 'Mobile number',
              required: true,
              child: TextFormField(
                controller: _mobileCtrl,
                decoration: const InputDecoration(hintText: '10-digit mobile number'),
                keyboardType: TextInputType.phone,
                inputFormatters: [LengthLimitingTextInputFormatter(20)],
                validator: (v) => (v == null || v.trim().isEmpty) ? 'Mobile is required' : rmPhoneValidator(v),
              ),
            ),
            FormFieldBox(
              label: 'Email',
              child: TextFormField(
                controller: _emailCtrl,
                decoration: const InputDecoration(hintText: 'staff@example.com'),
                keyboardType: TextInputType.emailAddress,
                inputFormatters: [LengthLimitingTextInputFormatter(255)],
                validator: rmEmailValidator,
              ),
            ),
          ],
        ),
        FormSection(
          title: 'Employment',
          description: 'Where the person works, their shift and status.',
          children: [
            FormFieldBox(
              label: 'Department',
              child: DropdownButtonFormField<String>(
                isExpanded: true,
                value: _selectedDept,
                decoration: const InputDecoration(hintText: 'Select department'),
                items: _departments.map((d) => DropdownMenuItem(value: d.$1, child: Text(d.$2))).toList(),
                onChanged: (v) => setState(() {
                  _selectedDept = v;
                  _selectedDesignationId = null;
                }),
              ),
            ),
            if (deptDesignations.isNotEmpty)
              FormFieldBox(
                label: 'Designation',
                child: DropdownButtonFormField<String>(
                isExpanded: true,
                  value: deptDesignations.any((d) => d.id == _selectedDesignationId) ? _selectedDesignationId : null,
                  decoration: const InputDecoration(hintText: 'Select designation'),
                  items: deptDesignations.map((d) => DropdownMenuItem(value: d.id, child: Text(d.name))).toList(),
                  onChanged: (v) => setState(() => _selectedDesignationId = v),
                ),
              ),
            if (allShifts.isNotEmpty)
              FormFieldBox(
                label: 'Shift',
                child: DropdownButtonFormField<String>(
                isExpanded: true,
                  value: allShifts.any((s) => s.id == _selectedShiftId) ? _selectedShiftId : null,
                  decoration: const InputDecoration(hintText: 'Select shift'),
                  items: allShifts
                      .map((s) => DropdownMenuItem(value: s.id, child: Text('${s.name} (${s.startTime}–${s.endTime})')))
                      .toList(),
                  onChanged: (v) => setState(() => _selectedShiftId = v),
                ),
              ),
            FormFieldBox(
              label: 'Employment status',
              child: DropdownButtonFormField<String>(
                isExpanded: true,
                value: _selectedStatus,
                decoration: const InputDecoration(hintText: 'Select status'),
                items: _statuses.map((s) => DropdownMenuItem(value: s.$1, child: Text(s.$2))).toList(),
                onChanged: (v) => setState(() => _selectedStatus = v),
              ),
            ),
            FormFieldBox(
              label: 'Reporting manager',
              child: DropdownButtonFormField<String>(
                isExpanded: true,
                value: managers.any((s) => s.userId == _selectedReportingManagerId) ? _selectedReportingManagerId : null,
                decoration: const InputDecoration(hintText: 'Select reporting manager'),
                items: [
                  const DropdownMenuItem(value: null, child: Text('No reporting manager')),
                  ...managers.map((s) => DropdownMenuItem(
                        value: s.userId,
                        child: Text('${s.fullName} (${s.departmentLabel})', overflow: TextOverflow.ellipsis),
                      )),
                ],
                onChanged: (v) => setState(() => _selectedReportingManagerId = v),
              ),
            ),
            // Deactivate shortcut
            if (_selectedStatus != 'inactive' && _selectedStatus != 'terminated')
              Align(
                alignment: Alignment.centerLeft,
                child: OutlinedButton.icon(
                  onPressed: () {
                    setState(() => _selectedStatus = 'inactive');
                    ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
                      content: Text('Status set to Inactive — tap Save to confirm'),
                      behavior: SnackBarBehavior.floating,
                    ));
                  },
                  icon: const Icon(Icons.person_off_rounded, size: 18),
                  label: const Text('Deactivate staff'),
                  style: OutlinedButton.styleFrom(
                    foregroundColor: AppTheme.error,
                    side: const BorderSide(color: AppTheme.error),
                  ),
                ),
              ),
          ],
        ),
        FormSection(
          title: 'Emergency contact',
          children: [
            FormFieldBox(
              label: 'Contact name',
              child: TextFormField(
                controller: _emergencyNameCtrl,
                decoration: const InputDecoration(hintText: 'e.g. Father / Spouse'),
                textCapitalization: TextCapitalization.words,
                inputFormatters: [LengthLimitingTextInputFormatter(255)],
              ),
            ),
            FormFieldBox(
              label: 'Contact phone',
              child: TextFormField(
                controller: _emergencyPhoneCtrl,
                decoration: const InputDecoration(hintText: '10-digit mobile number'),
                keyboardType: TextInputType.phone,
                inputFormatters: [LengthLimitingTextInputFormatter(20)],
                validator: rmPhoneValidator,
              ),
            ),
          ],
        ),
        FormSection(
          title: 'Additional information',
          columns: 1,
          children: [
            FormFieldBox(
              label: 'Residential address',
              child: TextFormField(
                controller: _addressCtrl,
                decoration: const InputDecoration(hintText: 'Full address'),
                inputFormatters: [LengthLimitingTextInputFormatter(1000)],
                maxLines: 2,
                textCapitalization: TextCapitalization.sentences,
              ),
            ),
            FormFieldBox(
              label: 'Admin notes',
              helper: 'Internal notes, not visible to the staff member.',
              child: TextFormField(
                controller: _notesCtrl,
                decoration: const InputDecoration(hintText: 'Notes'),
                inputFormatters: [LengthLimitingTextInputFormatter(2000)],
                maxLines: 2,
                textCapitalization: TextCapitalization.sentences,
              ),
            ),
          ],
        ),
      ],
    );
  }

  void _submit() {
    if (!_formKey.currentState!.validate()) return;

    final data = <String, dynamic>{
      if (_nameCtrl.text.trim().isNotEmpty)        'full_name':  _nameCtrl.text.trim(),
      if (_mobileCtrl.text.trim().isNotEmpty)      'mobile':     _mobileCtrl.text.trim(),
      // Optional fields are sent as null when emptied, which clears them.
      'email': _emailCtrl.text.trim().isEmpty ? null : _emailCtrl.text.trim(),
      if (_selectedDept != null)                   'department': _selectedDept,
      if (_selectedDesignationId != null)          'designation_id': _selectedDesignationId,
      if (_selectedShiftId != null)                'shift_id':   _selectedShiftId,
      if (_selectedStatus != null)                 'status':     _selectedStatus,
      'reporting_manager_id': _selectedReportingManagerId,
      'emergency_contact_name': _emergencyNameCtrl.text.trim().isEmpty ? null : _emergencyNameCtrl.text.trim(),
      'emergency_contact_phone': _emergencyPhoneCtrl.text.trim().isEmpty ? null : _emergencyPhoneCtrl.text.trim(),
      'address': _addressCtrl.text.trim().isEmpty ? null : _addressCtrl.text.trim(),
      'notes':   _notesCtrl.text.trim().isEmpty   ? null : _notesCtrl.text.trim(),
    };

    ref.read(staffFormProvider.notifier).update(widget.staff.id, data);
  }
}


