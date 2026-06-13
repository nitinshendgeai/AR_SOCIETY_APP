import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/features/staff/domain/entities/staff_entities.dart';
import 'package:ar_society_app/features/staff/presentation/providers/staff_providers.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';

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

    return Scaffold(
      backgroundColor: AppTheme.surface,
      appBar: AppBar(title: const Text('Add Staff')),
      body: Form(
        key: _formKey,
        child: ListView(
          padding: const EdgeInsets.all(20),
          children: [
            // ── Personal details ────────────────────────────────────────────
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

            // ── Employment details ──────────────────────────────────────────
            const SizedBox(height: 8),
            const _SectionHeader('Employment Details'),
            const SizedBox(height: 10),

            _FormField(
              label: 'Department *',
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
                validator: (v) => v == null ? 'Select a department' : null,
              ),
            ),

            _FormField(
              label: 'Designation',
              child: allDesignations.isEmpty
                  ? Container(
                      padding: const EdgeInsets.all(12),
                      decoration: BoxDecoration(
                        color: AppTheme.cardBg,
                        borderRadius: BorderRadius.circular(12),
                        border: Border.all(color: AppTheme.border),
                      ),
                      child: const Text(
                        'No designations configured. Ask your admin to set up designations first.',
                        style: TextStyle(color: AppTheme.textSecondary, fontSize: 13),
                      ),
                    )
                  : DropdownButtonFormField<String>(
                      value: _selectedDesignationId,
                      decoration: const InputDecoration(hintText: 'Select designation'),
                      items: deptDesignations
                          .map((d) => DropdownMenuItem(value: d.id, child: Text(d.name)))
                          .toList(),
                      onChanged: (v) => setState(() => _selectedDesignationId = v),
                    ),
            ),

            _FormField(
              label: 'Shift',
              child: DropdownButtonFormField<String>(
                value: _selectedShiftId,
                decoration: const InputDecoration(hintText: 'Select shift'),
                items: allShifts
                    .map((s) => DropdownMenuItem(value: s.id, child: Text('${s.name} (${s.startTime}–${s.endTime})')))
                    .toList(),
                onChanged: (v) => setState(() => _selectedShiftId = v),
              ),
            ),

            _FormField(
              label: 'Joining Date',
              child: InkWell(
                onTap: _pickJoiningDate,
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
                      const Icon(Icons.calendar_today_rounded, size: 18, color: AppTheme.primary),
                      const SizedBox(width: 10),
                      Text(
                        _joiningDate != null
                            ? '${_joiningDate!.day}/${_joiningDate!.month}/${_joiningDate!.year}'
                            : 'Select joining date',
                        style: TextStyle(
                          fontSize: 14,
                          color: _joiningDate != null ? AppTheme.textPrimary : AppTheme.textSecondary,
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ),

            // ── Reporting structure ─────────────────────────────────────────
            const SizedBox(height: 8),
            const _SectionHeader('Reporting Structure'),
            const SizedBox(height: 10),

            _FormField(
              label: 'Reporting Manager',
              child: DropdownButtonFormField<String>(
                value: _selectedReportingManagerId,
                decoration: const InputDecoration(hintText: 'Select reporting manager'),
                items: managers
                    .map((s) => DropdownMenuItem(
                          value: s.userId,
                          child: Text('${s.fullName} (${s.departmentLabel})',
                              overflow: TextOverflow.ellipsis),
                        ))
                    .toList(),
                onChanged: (v) => setState(() => _selectedReportingManagerId = v),
              ),
            ),

            // ── Emergency contact ───────────────────────────────────────────
            const SizedBox(height: 8),
            const _SectionHeader('Emergency Contact'),
            const SizedBox(height: 10),

            _FormField(
              label: 'Contact Name',
              child: TextFormField(
                controller: _emergencyNameCtrl,
                decoration: const InputDecoration(hintText: 'e.g. Father / Spouse'),
                textCapitalization: TextCapitalization.words,
              ),
            ),

            _FormField(
              label: 'Contact Phone',
              child: TextFormField(
                controller: _emergencyPhoneCtrl,
                decoration: const InputDecoration(hintText: '10-digit mobile number'),
                keyboardType: TextInputType.phone,
              ),
            ),

            // ── Additional info ─────────────────────────────────────────────
            const SizedBox(height: 8),
            const _SectionHeader('Additional Info'),
            const SizedBox(height: 10),

            _FormField(
              label: 'Residential Address',
              child: TextFormField(
                controller: _addressCtrl,
                decoration: const InputDecoration(hintText: 'Full address'),
                maxLines: 2,
                textCapitalization: TextCapitalization.sentences,
              ),
            ),

            _FormField(
              label: 'Admin Notes',
              child: TextFormField(
                controller: _notesCtrl,
                decoration: const InputDecoration(hintText: 'Internal notes (not visible to staff)'),
                maxLines: 2,
                textCapitalization: TextCapitalization.sentences,
              ),
            ),

            const SizedBox(height: 32),

            AppPrimaryButton(
              label: 'Add Staff',
              icon: Icons.person_add_rounded,
              isLoading: isLoading,
              onPressed: () => _submit(societyId),
            ),
          ],
        ),
      ),
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

/// Dead class — kept to avoid orphan reference until full cleanup.
// ignore: unused_element
class _FallbackDesignationDropdown extends StatelessWidget {
  final String? dept;
  final void Function(String?) onChanged;
  const _FallbackDesignationDropdown({this.dept, required this.onChanged});

  @override
  Widget build(BuildContext context) {
    return DropdownButtonFormField<String>(
      decoration: const InputDecoration(hintText: 'Select designation'),
      items: const [],
      onChanged: onChanged,
    );
  }
}
