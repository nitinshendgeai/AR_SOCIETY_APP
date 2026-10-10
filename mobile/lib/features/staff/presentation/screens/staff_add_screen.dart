import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:ar_society_app/features/resident_master/presentation/widgets/resident_master_widgets.dart' show rmPhoneValidator, rmEmailValidator;
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/features/staff/domain/entities/staff_entities.dart';
import 'package:ar_society_app/features/staff/presentation/providers/staff_providers.dart';
import 'package:ar_society_app/shared/widgets/app_form.dart';

/// Form to create a new staff member.
class StaffAddScreen extends ConsumerStatefulWidget {
  const StaffAddScreen({super.key});

  @override
  ConsumerState<StaffAddScreen> createState() => _StaffAddScreenState();
}

class _StaffAddScreenState extends ConsumerState<StaffAddScreen> {
  final _formKey = GlobalKey<FormState>();

  final _nameCtrl              = TextEditingController();
  final _mobileCtrl            = TextEditingController();
  final _emailCtrl             = TextEditingController();
  final _emergencyNameCtrl     = TextEditingController();
  final _emergencyPhoneCtrl    = TextEditingController();
  final _addressCtrl           = TextEditingController();
  final _notesCtrl             = TextEditingController();

  String? _selectedDept;
  String? _selectedDesignationId;
  String? _selectedShiftId;
  String? _selectedReportingManagerId;
  DateTime? _joiningDate;

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

  @override
  void initState() {
    super.initState();
    // Ensure staff list is loaded so the reporting manager dropdown is populated.
    WidgetsBinding.instance.addPostFrameCallback((_) {
      final user = ref.read(currentUserProvider);
      if (user?.societyId != null) {
        final listState = ref.read(staffListProvider);
        if (listState is StaffListInitial) {
          ref.read(staffListProvider.notifier).load(user!.societyId!);
        }
      }
    });
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

    // Load designations and shifts
    final designationsAsync = ref.watch(designationsProvider(societyId));
    final shiftsAsync       = ref.watch(shiftsProvider(societyId));
    final staffAsync        = ref.watch(staffListProvider);

    // Available designations filtered by dept (prefer backend; fallback to defaults)
    final allDesignations = designationsAsync.valueOrNull ?? <DesignationEntity>[];
    final deptDesignations = _selectedDept == null
        ? allDesignations
        : allDesignations.where((d) => d.department == _selectedDept).toList();

    final allShifts = shiftsAsync.valueOrNull ?? <ShiftEntity>[];

    // Managers for reporting manager dropdown
    final allStaff = staffAsync is StaffListLoaded ? staffAsync.staff : <StaffEntity>[];
    final managers = allStaff.where((s) =>
      s.department == 'admin' ||
      (s.designationName?.toLowerCase().contains('manager') ?? false) ||
      (s.designationName?.toLowerCase().contains('supervisor') ?? false)
    ).toList();

    ref.listen(staffFormProvider, (_, next) {
      if (next is StaffFormSuccess) {
        ref.read(staffListProvider.notifier).load(societyId);
        ref.read(staffFormProvider.notifier).reset();
        final staff = next.staff;
        if (staff.tempPassword != null && staff.email != null) {
          _showCredentialsDialog(context, staff.fullName, staff.email!, staff.tempPassword!);
        } else {
          ScaffoldMessenger.of(context).showSnackBar(SnackBar(
            content: Text(next.message),
            backgroundColor: AppTheme.success,
            behavior: SnackBarBehavior.floating,
          ));
          context.pop();
        }
      } else if (next is StaffFormError) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(
          content: Text(next.message),
          backgroundColor: AppTheme.error,
          behavior: SnackBarBehavior.floating,
        ));
      }
    });

    return AppFormPage(
      title: 'Add Staff',
      subtitle: 'Add a staff member to the society',
      formKey: _formKey,
      submitLabel: 'Add Staff',
      submitIcon: Icons.person_add_rounded,
      saving: isLoading,
      onSubmit: () => _submit(societyId),
      children: [
        FormSection(
          title: 'Personal details',
          description: 'An email creates a login for the person (password Staff@1234).',
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
              helper: 'Optional. Giving one creates a login account for this person.',
              child: TextFormField(
                controller: _emailCtrl,
                decoration: const InputDecoration(hintText: 'e.g. security1@artsociety.com'),
                keyboardType: TextInputType.emailAddress,
                inputFormatters: [LengthLimitingTextInputFormatter(255)],
                validator: rmEmailValidator,
              ),
            ),
            FormFieldBox(
              label: 'Joining date',
              child: FormDateField(
                value: _joiningDate,
                hint: 'Select joining date',
                format: (d) => '${d.day}/${d.month}/${d.year}',
                onClear: () => setState(() => _joiningDate = null),
                onTap: _pickJoiningDate,
              ),
            ),
          ],
        ),
        FormSection(
          title: 'Employment',
          description: 'Where the person works and who they report to.',
          children: [
            FormFieldBox(
              label: 'Department',
              required: true,
              child: DropdownButtonFormField<String>(
                isExpanded: true,
                value: _selectedDept,
                decoration: const InputDecoration(hintText: 'Select department'),
                items: _departments.map((d) => DropdownMenuItem(value: d.$1, child: Text(d.$2))).toList(),
                onChanged: (v) => setState(() {
                  _selectedDept = v;
                  _selectedDesignationId = null;
                }),
                validator: (v) => v == null ? 'Select a department' : null,
              ),
            ),
            FormFieldBox(
              label: 'Designation',
              child: allDesignations.isEmpty
                  ? InputDecorator(
                      decoration: const InputDecoration(),
                      child: const Text(
                        'No designations set up yet',
                        style: TextStyle(color: AppTheme.textSecondary, fontSize: 13),
                      ),
                    )
                  : DropdownButtonFormField<String>(
                isExpanded: true,
                      value: _selectedDesignationId,
                      decoration: const InputDecoration(hintText: 'Select designation'),
                      items: deptDesignations.map((d) => DropdownMenuItem(value: d.id, child: Text(d.name))).toList(),
                      onChanged: (v) => setState(() => _selectedDesignationId = v),
                    ),
            ),
            FormFieldBox(
              label: 'Shift',
              child: DropdownButtonFormField<String>(
                isExpanded: true,
                value: _selectedShiftId,
                decoration: const InputDecoration(hintText: 'Select shift'),
                items: allShifts
                    .map((s) => DropdownMenuItem(value: s.id, child: Text('${s.name} (${s.startTime}–${s.endTime})')))
                    .toList(),
                onChanged: (v) => setState(() => _selectedShiftId = v),
              ),
            ),
            FormFieldBox(
              label: 'Reporting manager',
              child: DropdownButtonFormField<String>(
                isExpanded: true,
                value: _selectedReportingManagerId,
                decoration: const InputDecoration(hintText: 'Select reporting manager'),
                items: managers
                    .map((s) => DropdownMenuItem(
                          value: s.userId,
                          child: Text('${s.fullName} (${s.departmentLabel})', overflow: TextOverflow.ellipsis),
                        ))
                    .toList(),
                onChanged: (v) => setState(() => _selectedReportingManagerId = v),
              ),
            ),
          ],
        ),
        FormSection(
          title: 'Emergency contact',
          description: 'Who to call if something happens at work.',
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

  void _showCredentialsDialog(BuildContext context, String name, String email, String password) {
    showDialog<void>(
      context: context,
      barrierDismissible: false,
      builder: (_) => AlertDialog(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        title: Row(
          children: const [
            Icon(Icons.check_circle_rounded, color: AppTheme.success, size: 22),
            SizedBox(width: 8),
            Text('Staff Account Created', style: TextStyle(fontSize: 16)),
          ],
        ),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('$name can now log in with:', style: const TextStyle(fontSize: 13, color: AppTheme.textSecondary)),
            const SizedBox(height: 12),
            _CredentialRow(label: 'Email', value: email),
            const SizedBox(height: 8),
            _CredentialRow(label: 'Password', value: password),
            const SizedBox(height: 12),
            Container(
              padding: const EdgeInsets.all(10),
              decoration: BoxDecoration(
                color: AppTheme.warning.withOpacity(0.1),
                borderRadius: BorderRadius.circular(8),
                border: Border.all(color: AppTheme.warning.withOpacity(0.3)),
              ),
              child: const Text(
                'They will be prompted to change their password on first login.',
                style: TextStyle(fontSize: 12, color: AppTheme.textSecondary),
              ),
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () {
              Navigator.of(context).pop();
              context.pop();
            },
            child: const Text('Done'),
          ),
        ],
      ),
    );
  }

  Future<void> _pickJoiningDate() async {
    final picked = await showDatePicker(
      context: context,
      initialDate: _joiningDate ?? DateTime.now(),
      firstDate: DateTime(2000),
      lastDate: DateTime.now(),
    );
    if (picked != null) setState(() => _joiningDate = picked);
  }

  void _submit(String societyId) {
    if (!_formKey.currentState!.validate()) return;
    if (societyId.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
        content: Text('Society not loaded. Please reload the app.'),
        backgroundColor: AppTheme.error,
        behavior: SnackBarBehavior.floating,
      ));
      return;
    }

    final joiningStr = _joiningDate != null
        ? '${_joiningDate!.year}-${_joiningDate!.month.toString().padLeft(2, '0')}-${_joiningDate!.day.toString().padLeft(2, '0')}'
        : null;

    final data = <String, dynamic>{
      'society_id':   societyId,
      'full_name':    _nameCtrl.text.trim(),
      'mobile':       _mobileCtrl.text.trim(),
      'department':   _selectedDept!,
      if (_emailCtrl.text.trim().isNotEmpty) 'email': _emailCtrl.text.trim(),
      if (_selectedDesignationId != null) 'designation_id': _selectedDesignationId,
      if (_selectedShiftId != null) 'shift_id': _selectedShiftId,
      if (joiningStr != null) 'joining_date': joiningStr,
      if (_selectedReportingManagerId != null) 'reporting_manager_id': _selectedReportingManagerId,
      if (_emergencyNameCtrl.text.trim().isNotEmpty) 'emergency_contact_name': _emergencyNameCtrl.text.trim(),
      if (_emergencyPhoneCtrl.text.trim().isNotEmpty) 'emergency_contact_phone': _emergencyPhoneCtrl.text.trim(),
      if (_addressCtrl.text.trim().isNotEmpty) 'address': _addressCtrl.text.trim(),
      if (_notesCtrl.text.trim().isNotEmpty) 'notes': _notesCtrl.text.trim(),
    };

    ref.read(staffFormProvider.notifier).create(data);
  }
}



class _CredentialRow extends StatelessWidget {
  final String label;
  final String value;
  const _CredentialRow({required this.label, required this.value});

  @override
  Widget build(BuildContext context) => Row(
    children: [
      SizedBox(
        width: 70,
        child: Text(label, style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600,
            color: AppTheme.textSecondary)),
      ),
      Expanded(
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
          decoration: BoxDecoration(
            color: AppTheme.cardBg,
            borderRadius: BorderRadius.circular(8),
            border: Border.all(color: AppTheme.border),
          ),
          child: Text(value, style: const TextStyle(fontSize: 13, fontFamily: 'monospace',
              fontWeight: FontWeight.w600)),
        ),
      ),
    ],
  );
}
