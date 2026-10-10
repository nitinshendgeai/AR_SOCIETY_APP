import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/resident_master/data/models/resident_master_models.dart';
import 'package:ar_society_app/features/resident_master/presentation/providers/resident_master_providers.dart';
import 'package:ar_society_app/features/resident_master/presentation/widgets/resident_master_widgets.dart';
import 'package:ar_society_app/features/society_structure/data/models/structure_models.dart';
import 'package:ar_society_app/features/society_structure/presentation/providers/structure_providers.dart';
import 'package:ar_society_app/shared/widgets/app_form.dart';

/// Add / Edit Resident — single screen handling both, mirroring
/// FlatFormScreen's create/edit split (society_structure module).
///
/// Edit mode never exposes flat_id (immutable — a "move" is a move-out +
/// new Resident, handled via the Occupancy actions, not this form) and
/// never exposes family_member_count (server-computed).
class ResidentFormScreen extends ConsumerStatefulWidget {
  final ResidentModel? resident;
  final FlatModel? defaultFlat;
  const ResidentFormScreen({super.key, this.resident, this.defaultFlat});

  @override
  ConsumerState<ResidentFormScreen> createState() => _ResidentFormScreenState();
}

class _ResidentFormScreenState extends ConsumerState<ResidentFormScreen> {
  final _formKey = GlobalKey<FormState>();
  final _nameCtrl = TextEditingController();
  final _phoneCtrl = TextEditingController();
  final _emailCtrl = TextEditingController();
  final _idProofNumberCtrl = TextEditingController();
  final _emergencyNameCtrl = TextEditingController();
  final _emergencyPhoneCtrl = TextEditingController();

  String? _selectedWingId;
  String? _selectedFlatId;
  ResidentType _residentType = ResidentType.owner;
  bool _isPrimary = false;
  bool _kycVerified = false;
  String? _idProofType;
  CommPreference _commPreference = CommPreference.appOnly;
  DateTime? _dateOfBirth;
  bool _recordMoveIn = false;
  DateTime? _moveInDate;

  bool get _isEdit => widget.resident != null;

  static const _idProofTypes = ['Aadhaar', 'PAN', 'Passport', 'Driving License', 'Voter ID'];

  @override
  void initState() {
    super.initState();
    final r = widget.resident;
    if (r != null) {
      _nameCtrl.text = r.fullName;
      _phoneCtrl.text = r.phone ?? '';
      _emailCtrl.text = r.email ?? '';
      _idProofNumberCtrl.text = r.idProofNumber ?? '';
      _emergencyNameCtrl.text = r.emergencyContactName ?? '';
      _emergencyPhoneCtrl.text = r.emergencyContactPhone ?? '';
      _residentType = r.residentType;
      _isPrimary = r.isPrimary;
      _kycVerified = r.kycVerified;
      _idProofType = r.idProofType;
      _commPreference = r.commPreference;
      _dateOfBirth = r.dateOfBirth != null ? DateTime.tryParse(r.dateOfBirth!) : null;
      _selectedFlatId = r.flatId;
    } else if (widget.defaultFlat != null) {
      _selectedFlatId = widget.defaultFlat!.id;
      _selectedWingId = widget.defaultFlat!.wingId;
    }
  }

  @override
  void dispose() {
    _nameCtrl.dispose();
    _phoneCtrl.dispose();
    _emailCtrl.dispose();
    _idProofNumberCtrl.dispose();
    _emergencyNameCtrl.dispose();
    _emergencyPhoneCtrl.dispose();
    super.dispose();
  }

  String _dateStr(DateTime d) =>
      '${d.year}-${d.month.toString().padLeft(2, '0')}-${d.day.toString().padLeft(2, '0')}';

  void _submit() {
    if (!_formKey.currentState!.validate()) return;
    if (!_isEdit && _selectedFlatId == null) {
      ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Please select a flat')));
      return;
    }
    if (_isPrimary && !_residentType.canBePrimary) {
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
          content: Text('Only Owner or Co-Owner can be marked Primary')));
      return;
    }

    if (_isEdit) {
      final data = <String, dynamic>{
        'full_name': _nameCtrl.text.trim(),
        'resident_type': _residentType.value,
        'is_primary': _isPrimary,
        'phone': _phoneCtrl.text.trim().isEmpty ? null : _phoneCtrl.text.trim(),
        'email': _emailCtrl.text.trim().isEmpty ? null : _emailCtrl.text.trim(),
        'date_of_birth': _dateOfBirth != null ? _dateStr(_dateOfBirth!) : null,
        'id_proof_type': _idProofType,
        'id_proof_number': _idProofNumberCtrl.text.trim().isEmpty ? null : _idProofNumberCtrl.text.trim(),
        'kyc_verified': _kycVerified,
        'emergency_contact_name': _emergencyNameCtrl.text.trim().isEmpty ? null : _emergencyNameCtrl.text.trim(),
        'emergency_contact_phone': _emergencyPhoneCtrl.text.trim().isEmpty ? null : _emergencyPhoneCtrl.text.trim(),
        'comm_preference': _commPreference.value,
      };
      ref.read(residentFormProvider.notifier).update(widget.resident!.id, data);
    } else {
      final data = <String, dynamic>{
        'flat_id': _selectedFlatId,
        'full_name': _nameCtrl.text.trim(),
        'resident_type': _residentType.value,
        'is_primary': _isPrimary,
        'phone': _phoneCtrl.text.trim().isEmpty ? null : _phoneCtrl.text.trim(),
        'email': _emailCtrl.text.trim().isEmpty ? null : _emailCtrl.text.trim(),
        if (_dateOfBirth != null) 'date_of_birth': _dateStr(_dateOfBirth!),
        if (_idProofType != null) 'id_proof_type': _idProofType,
        if (_idProofNumberCtrl.text.trim().isNotEmpty) 'id_proof_number': _idProofNumberCtrl.text.trim(),
        'kyc_verified': _kycVerified,
        if (_emergencyNameCtrl.text.trim().isNotEmpty) 'emergency_contact_name': _emergencyNameCtrl.text.trim(),
        if (_emergencyPhoneCtrl.text.trim().isNotEmpty) 'emergency_contact_phone': _emergencyPhoneCtrl.text.trim(),
        'comm_preference': _commPreference.value,
        if (_recordMoveIn && _moveInDate != null) 'move_in_date': _dateStr(_moveInDate!),
      };
      ref.read(residentFormProvider.notifier).create(data);
    }
  }

  @override
  Widget build(BuildContext context) {
    final formState = ref.watch(residentFormProvider);
    final isLoading = formState is ResidentFormLoading;
    final wingsAsync = ref.watch(wingsProvider);
    final flatsAsync = ref.watch(flatsBySocietyProvider);

    ref.listen(residentFormProvider, (_, next) {
      if (next is ResidentFormSuccess) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(
          content: Text(next.message),
          backgroundColor: AppTheme.success,
          behavior: SnackBarBehavior.floating,
        ));
        ref.read(residentListProvider.notifier).refresh();
        ref.invalidate(residentsByFlatProvider(next.resident.flatId));
        if (_isEdit) ref.invalidate(residentDetailProvider(next.resident.id));
        ref.read(residentFormProvider.notifier).reset();
        context.pop();
      } else if (next is ResidentFormError) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(
          content: Text(rmFriendlyError(next.message)),
          backgroundColor: AppTheme.error,
          behavior: SnackBarBehavior.floating,
        ));
      }
    });

    final flats = (flatsAsync.valueOrNull ?? <FlatModel>[])
        .where((f) => _selectedWingId == null || f.wingId == _selectedWingId)
        .toList();

    return AppFormPage(
      title: _isEdit ? 'Edit Resident' : 'Add Resident',
      subtitle: _isEdit ? widget.resident!.fullName : 'Add a person to a flat in the society',
      formKey: _formKey,
      submitLabel: _isEdit ? 'Save Changes' : 'Add Resident',
      submitIcon: _isEdit ? Icons.save_rounded : Icons.person_add_rounded,
      saving: isLoading,
      onSubmit: _submit,
      children: [
        FormSection(
          title: 'Personal information',
          description: 'Who the person is and how they relate to the flat.',
          children: [
            FormFieldBox(
              label: 'Full name',
              required: true,
              child: TextFormField(
                controller: _nameCtrl,
                textCapitalization: TextCapitalization.words,
                inputFormatters: [LengthLimitingTextInputFormatter(255)],
                decoration: const InputDecoration(hintText: 'Enter full name'),
                validator: (v) => (v == null || v.trim().isEmpty) ? 'Name is required' : null,
              ),
            ),
            FormFieldBox(
              label: 'Resident type',
              required: true,
              child: DropdownButtonFormField<ResidentType>(
                isExpanded: true,
                value: _residentType,
                items: ResidentType.values.map((t) => DropdownMenuItem(value: t, child: Text(t.label))).toList(),
                onChanged: (v) => setState(() {
                  _residentType = v ?? ResidentType.owner;
                  if (!_residentType.canBePrimary) _isPrimary = false;
                }),
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
        FormSection(
          title: 'Contact',
          description: 'How the society reaches this person.',
          children: [
            FormFieldBox(
              label: 'Mobile',
              child: TextFormField(
                controller: _phoneCtrl,
                keyboardType: TextInputType.phone,
                textInputAction: TextInputAction.next,
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
                inputFormatters: [LengthLimitingTextInputFormatter(255)],
                decoration: const InputDecoration(hintText: 'name@example.com'),
                validator: rmEmailValidator,
              ),
            ),
            FormFieldBox(
              label: 'Emergency contact name',
              child: TextFormField(
                controller: _emergencyNameCtrl,
                textCapitalization: TextCapitalization.words,
                inputFormatters: [LengthLimitingTextInputFormatter(255)],
              ),
            ),
            FormFieldBox(
              label: 'Emergency contact phone',
              child: TextFormField(
                controller: _emergencyPhoneCtrl,
                keyboardType: TextInputType.phone,
                inputFormatters: [FilteringTextInputFormatter.digitsOnly, LengthLimitingTextInputFormatter(10)],
                validator: rmPhoneValidator,
              ),
            ),
          ],
        ),
        if (!_isEdit)
          FormSection(
            title: 'Flat',
            description: 'Which flat this person belongs to. Pick a wing first to shorten the flat list.',
            children: [
              FormFieldBox(
                label: 'Wing',
                child: wingsAsync.when(
                  loading: () => const LinearProgressIndicator(),
                  error: (_, __) => const SizedBox.shrink(),
                  data: (wings) => DropdownButtonFormField<String>(
                isExpanded: true,
                    value: _selectedWingId,
                    hint: const Text('All wings'),
                    items: wings
                        .where((w) => w.isActive)
                        .map((w) => DropdownMenuItem(value: w.id, child: Text(w.displayName)))
                        .toList(),
                    onChanged: (v) => setState(() {
                      _selectedWingId = v;
                      _selectedFlatId = null;
                    }),
                  ),
                ),
              ),
              FormFieldBox(
                label: 'Flat',
                required: true,
                child: DropdownButtonFormField<String>(
                isExpanded: true,
                  value: _selectedFlatId,
                  hint: const Text('Select flat'),
                  items: flats
                      .map((f) => DropdownMenuItem(
                            value: f.id,
                            child: Text(f.wingName != null ? '${f.wingName} — ${f.flatNumber}' : f.flatNumber),
                          ))
                      .toList(),
                  onChanged: (v) => setState(() => _selectedFlatId = v),
                  validator: (v) => v == null ? 'Flat is required' : null,
                ),
              ),
              FormFull(
                child: FormSwitchTile(
                  title: 'Already moved in',
                  subtitle: 'Record a move-in date now',
                  value: _recordMoveIn,
                  onChanged: (v) => setState(() {
                    _recordMoveIn = v;
                    if (v) _moveInDate ??= DateTime.now();
                  }),
                ),
              ),
              if (_recordMoveIn)
                FormFieldBox(
                  label: 'Move-in date',
                  child: FormDateField(
                    value: _moveInDate,
                    hint: 'Select date',
                    format: _dateStr,
                    onTap: () async {
                      final picked = await showDatePicker(
                        context: context,
                        initialDate: _moveInDate ?? DateTime.now(),
                        firstDate: DateTime(2000),
                        lastDate: DateTime.now(),
                      );
                      if (picked != null) setState(() => _moveInDate = picked);
                    },
                  ),
                ),
            ],
          ),
        FormSection(
          title: 'Status',
          description: 'Primary contact and verification.',
          children: [
            FormSwitchTile(
              title: 'Primary resident',
              subtitle: _residentType.canBePrimary
                  ? 'The main contact for the flat'
                  : 'Only an Owner or Co-Owner can be primary',
              value: _isPrimary,
              onChanged: _residentType.canBePrimary ? (v) => setState(() => _isPrimary = v) : null,
            ),
            FormSwitchTile(
              title: 'KYC verified',
              subtitle: 'Identity documents have been checked',
              value: _kycVerified,
              onChanged: (v) => setState(() => _kycVerified = v),
            ),
          ],
        ),
        FormSection(
          title: 'Identity',
          description: 'Optional. An ID proof the society keeps on record.',
          children: [
            FormFieldBox(
              label: 'ID proof type',
              child: DropdownButtonFormField<String>(
                isExpanded: true,
                value: _idProofType,
                hint: const Text('Select ID type'),
                items: [
                  if (_idProofType != null) const DropdownMenuItem(value: rmNoneOption, child: Text(rmNoneOption)),
                  ..._idProofTypes.map((t) => DropdownMenuItem(value: t, child: Text(t))),
                ],
                onChanged: (v) => setState(() => _idProofType = v == rmNoneOption ? null : v),
              ),
            ),
            FormFieldBox(
              label: 'ID proof number',
              child: TextFormField(
                  controller: _idProofNumberCtrl, inputFormatters: [LengthLimitingTextInputFormatter(100)]),
            ),
          ],
        ),
      ],
    );
  }
}
