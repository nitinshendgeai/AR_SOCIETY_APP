import 'package:flutter/material.dart';
import 'package:ar_society_app/core/motion/loading.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/resident_master/data/models/resident_master_models.dart';
import 'package:ar_society_app/features/resident_master/presentation/providers/resident_master_providers.dart';
import 'package:ar_society_app/features/resident_master/presentation/widgets/resident_master_widgets.dart';
import 'package:ar_society_app/shared/widgets/app_form.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart' show AppErrorBanner;

/// Resident self-service: request a change to your own profile. Never
/// applied directly — submits a ResidentEditRequest that only takes effect
/// once an Admin or Committee member approves it (see
/// resident_edit_request_service.py). Only one pending request per resident
/// at a time; while one is outstanding, the form is replaced with its status.
class EditMyProfileScreen extends ConsumerStatefulWidget {
  const EditMyProfileScreen({super.key});

  @override
  ConsumerState<EditMyProfileScreen> createState() => _EditMyProfileScreenState();
}

class _EditMyProfileScreenState extends ConsumerState<EditMyProfileScreen> {
  final _formKey = GlobalKey<FormState>();
  final _fullNameCtrl = TextEditingController();
  final _phoneCtrl = TextEditingController();
  final _emailCtrl = TextEditingController();
  final _emergencyNameCtrl = TextEditingController();
  final _emergencyPhoneCtrl = TextEditingController();

  DateTime? _dateOfBirth;
  CommPreference _commPreference = CommPreference.appOnly;
  ResidentModel? _loadedFor;

  @override
  void dispose() {
    _fullNameCtrl.dispose();
    _phoneCtrl.dispose();
    _emailCtrl.dispose();
    _emergencyNameCtrl.dispose();
    _emergencyPhoneCtrl.dispose();
    super.dispose();
  }

  void _loadFrom(ResidentModel resident) {
    if (_loadedFor?.id == resident.id) return;
    _loadedFor = resident;
    _fullNameCtrl.text = resident.fullName;
    _phoneCtrl.text = resident.phone ?? '';
    _emailCtrl.text = resident.email ?? '';
    _emergencyNameCtrl.text = resident.emergencyContactName ?? '';
    _emergencyPhoneCtrl.text = resident.emergencyContactPhone ?? '';
    _dateOfBirth = resident.dateOfBirth != null ? DateTime.tryParse(resident.dateOfBirth!) : null;
    _commPreference = resident.commPreference;
  }

  String _dateStr(DateTime d) =>
      '${d.year.toString().padLeft(4, '0')}-${d.month.toString().padLeft(2, '0')}-${d.day.toString().padLeft(2, '0')}';

  Future<void> _submit(ResidentModel current) async {
    if (!_formKey.currentState!.validate()) return;

    // Only the fields that actually changed — an empty diff means nothing
    // to submit, and the backend rejects a request with no changes anyway.
    final changes = <String, dynamic>{};
    if (_fullNameCtrl.text.trim() != current.fullName) {
      changes['full_name'] = _fullNameCtrl.text.trim();
    }
    final phone = _phoneCtrl.text.trim();
    if (phone != (current.phone ?? '')) changes['phone'] = phone.isEmpty ? null : phone;
    final email = _emailCtrl.text.trim();
    if (email != (current.email ?? '')) changes['email'] = email.isEmpty ? null : email;
    final emName = _emergencyNameCtrl.text.trim();
    if (emName != (current.emergencyContactName ?? '')) {
      changes['emergency_contact_name'] = emName.isEmpty ? null : emName;
    }
    final emPhone = _emergencyPhoneCtrl.text.trim();
    if (emPhone != (current.emergencyContactPhone ?? '')) {
      changes['emergency_contact_phone'] = emPhone.isEmpty ? null : emPhone;
    }
    final dobStr = _dateOfBirth != null ? _dateStr(_dateOfBirth!) : null;
    if (dobStr != current.dateOfBirth) changes['date_of_birth'] = dobStr;
    if (_commPreference != current.commPreference) changes['comm_preference'] = _commPreference.value;
    changes.removeWhere((_, v) => v == null);

    if (changes.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('No changes to submit')));
      return;
    }

    await ref.read(editRequestActionProvider.notifier).submit(changes);
    final state = ref.read(editRequestActionProvider);
    if (!mounted) return;
    switch (state) {
      case EditRequestActionSuccess(:final message):
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(
          content: Text(message), backgroundColor: AppTheme.success,
        ));
        ref.invalidate(myEditRequestsProvider);
      case EditRequestActionError(:final message):
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(
          content: Text(message), backgroundColor: AppTheme.error,
        ));
      default:
        break;
    }
    ref.read(editRequestActionProvider.notifier).reset();
  }

  @override
  Widget build(BuildContext context) {
    final residentAsync = ref.watch(myResidentProvider);
    final requestsAsync = ref.watch(myEditRequestsProvider);
    final actionState = ref.watch(editRequestActionProvider);

    Widget waiting(Widget body) => AppPage(
      title: 'Edit My Info',
      body: body,
    );

    return residentAsync.when(
      loading: () => waiting(const AppLoader()),
      error: (e, _) => waiting(Center(
        child: Padding(padding: const EdgeInsets.all(24), child: Text(rmFriendlyError(e), textAlign: TextAlign.center)),
      )),
      data: (resident) {
        if (resident == null) {
          return waiting(const Center(
            child: Padding(padding: EdgeInsets.all(24), child: Text('No resident profile is linked to your account.')),
          ));
        }
        _loadFrom(resident);

        final pending = requestsAsync.valueOrNull?.where((r) => r.status == ResidentEditRequestStatus.pending).firstOrNull;
        final saving = actionState is EditRequestActionLoading;
        final locked = pending != null;

        return AppFormPage(
          title: 'Edit My Info',
          subtitle: 'Changes are sent to the society office for approval',
          formKey: _formKey,
          submitLabel: 'Submit for Approval',
          submitIcon: Icons.send_rounded,
          saving: saving,
          onSubmit: locked || saving ? null : () => _submit(resident),
          children: [
            if (pending != null)
              DecoratedBox(
                decoration: BoxDecoration(
                  color: AppTheme.warningSoft,
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(color: AppTheme.warning.withOpacity(0.3)),
                ),
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(children: [
                        const Icon(Icons.pending_actions_rounded, color: AppTheme.warning, size: 18),
                        const SizedBox(width: 8),
                        const Expanded(
                          child: Text('Change request pending approval',
                              style: TextStyle(fontWeight: FontWeight.w700, fontSize: 14)),
                        ),
                      ]),
                      const SizedBox(height: 8),
                      ...pending.changes.entries.map((e) => Padding(
                            padding: const EdgeInsets.symmetric(vertical: 2),
                            child: Text('${_fieldLabel(e.key)}: ${e.value ?? '—'}',
                                style: const TextStyle(fontSize: 13, color: AppTheme.textSecondary)),
                          )),
                      const SizedBox(height: 6),
                      const Text(
                        'You can send a new request once this one is reviewed by an Admin or Committee member.',
                        style: TextStyle(fontSize: 12, color: AppTheme.textSecondary),
                      ),
                    ],
                  ),
                ),
              )
            else if (requestsAsync.valueOrNull?.firstOrNull case final last? when last.status == ResidentEditRequestStatus.rejected)
              AppErrorBanner(message: 'Your last request was rejected: ${last.rejectionReason ?? 'No reason given'}'),
            AbsorbPointer(
              absorbing: locked,
              child: Opacity(
                opacity: locked ? 0.5 : 1,
                child: FormSection(
                  title: 'Your details',
                  description: 'How the society knows and reaches you.',
                  children: [
                    FormFieldBox(
                      label: 'Full name',
                      required: true,
                      child: TextFormField(
                        controller: _fullNameCtrl,
                        validator: (v) => (v == null || v.trim().isEmpty) ? 'Full name is required' : null,
                      ),
                    ),
                    FormFieldBox(
                      label: 'Mobile',
                      child: TextFormField(
                        controller: _phoneCtrl,
                        keyboardType: TextInputType.phone,
                        inputFormatters: [FilteringTextInputFormatter.digitsOnly, LengthLimitingTextInputFormatter(10)],
                        decoration: const InputDecoration(hintText: '10-digit mobile number'),
                        validator: rmPhoneValidator,
                      ),
                    ),
                    FormFieldBox(
                      label: 'Email',
                      child: TextFormField(
                        controller: _emailCtrl,
                        keyboardType: TextInputType.emailAddress,
                        decoration: const InputDecoration(hintText: 'name@example.com'),
                      ),
                    ),
                    FormFieldBox(
                      label: 'Date of birth',
                      child: FormDateField(
                        value: _dateOfBirth,
                        hint: 'Optional',
                        icon: Icons.cake_outlined,
                        format: _dateStr,
                        onClear: () => setState(() => _dateOfBirth = null),
                        onTap: () async {
                          final picked = await showDatePicker(
                            context: context,
                            initialDate: _dateOfBirth ?? DateTime(1990),
                            firstDate: DateTime(1900),
                            lastDate: DateTime.now(),
                          );
                          if (picked != null) setState(() => _dateOfBirth = picked);
                        },
                      ),
                    ),
                    FormFieldBox(
                      label: 'Emergency contact name',
                      child: TextFormField(controller: _emergencyNameCtrl),
                    ),
                    FormFieldBox(
                      label: 'Emergency contact phone',
                      child: TextFormField(
                        controller: _emergencyPhoneCtrl,
                        keyboardType: TextInputType.phone,
                        inputFormatters: [FilteringTextInputFormatter.digitsOnly, LengthLimitingTextInputFormatter(10)],
                      ),
                    ),
                    FormFieldBox(
                      label: 'Communication preference',
                      child: DropdownButtonFormField<CommPreference>(
                        isExpanded: true,
                        value: _commPreference,
                        items: CommPreference.values.map((c) => DropdownMenuItem(value: c, child: Text(c.label))).toList(),
                        onChanged: (v) => setState(() => _commPreference = v ?? CommPreference.appOnly),
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ],
        );
      },
    );
  }

  String _fieldLabel(String field) => switch (field) {
        'full_name' => 'Full Name',
        'phone' => 'Mobile',
        'email' => 'Email',
        'date_of_birth' => 'Date of Birth',
        'emergency_contact_name' => 'Emergency Contact Name',
        'emergency_contact_phone' => 'Emergency Contact Phone',
        'comm_preference' => 'Communication Preference',
        _ => field,
      };
}
