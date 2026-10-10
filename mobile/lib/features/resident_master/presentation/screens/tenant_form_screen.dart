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

/// Add / Edit Tenant — single screen handling both, mirroring
/// ResidentFormScreen. Edit mode never exposes flat_id or the agreement
/// fields (start/end date, rent, deposit) — those are owned by the
/// canonical renewal workflow (AgreementRenewalSheet), never a generic
/// PATCH, matching backend/app/schemas/tenant.py's TenantUpdate exclusions.
class TenantFormScreen extends ConsumerStatefulWidget {
  final TenantModel? tenant;
  final FlatModel? defaultFlat;
  const TenantFormScreen({super.key, this.tenant, this.defaultFlat});

  @override
  ConsumerState<TenantFormScreen> createState() => _TenantFormScreenState();
}

class _TenantFormScreenState extends ConsumerState<TenantFormScreen> {
  final _formKey = GlobalKey<FormState>();
  final _nameCtrl = TextEditingController();
  final _phoneCtrl = TextEditingController();
  final _emailCtrl = TextEditingController();
  final _idProofNumberCtrl = TextEditingController();
  final _emergencyNameCtrl = TextEditingController();
  final _emergencyPhoneCtrl = TextEditingController();
  final _remarksCtrl = TextEditingController();
  final _rentCtrl = TextEditingController();
  final _depositCtrl = TextEditingController();

  String? _selectedWingId;
  String? _selectedFlatId;
  bool _kycVerified = false;
  String? _idProofType;
  PoliceVerificationStatus _policeStatus = PoliceVerificationStatus.pending;
  DateTime? _agreementStart;
  DateTime? _agreementEnd;
  bool _recordMoveIn = false;
  DateTime? _moveInDate;

  bool get _isEdit => widget.tenant != null;

  static const _idProofTypes = ['Aadhaar', 'PAN', 'Passport', 'Driving License', 'Voter ID'];

  // Up to 10 digits and 2 decimals, matching what the server stores.
  static final _moneyFormatters = <TextInputFormatter>[
    FilteringTextInputFormatter.allow(RegExp(r'^\d{0,10}(\.\d{0,2})?')),
  ];

  @override
  void initState() {
    super.initState();
    final t = widget.tenant;
    if (t != null) {
      _nameCtrl.text = t.fullName;
      _phoneCtrl.text = t.phone ?? '';
      _emailCtrl.text = t.email ?? '';
      _idProofNumberCtrl.text = t.idProofNumber ?? '';
      _emergencyNameCtrl.text = t.emergencyContactName ?? '';
      _emergencyPhoneCtrl.text = t.emergencyContactPhone ?? '';
      _remarksCtrl.text = t.remarks ?? '';
      _kycVerified = t.kycVerified;
      _idProofType = t.idProofType;
      _policeStatus = t.policeVerificationStatus;
      _selectedFlatId = t.flatId;
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
    _remarksCtrl.dispose();
    _rentCtrl.dispose();
    _depositCtrl.dispose();
    super.dispose();
  }

  String _dateStr(DateTime d) =>
      '${d.year}-${d.month.toString().padLeft(2, '0')}-${d.day.toString().padLeft(2, '0')}';

  void _submit() {
    if (!_formKey.currentState!.validate()) return;
    if (!_isEdit && _selectedFlatId == null) {
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Please select a flat')));
      return;
    }
    if (!_isEdit && (_agreementStart == null) != (_agreementEnd == null)) {
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
          content: Text('Provide both agreement start and end dates, or neither')));
      return;
    }
    if (!_isEdit && _agreementStart != null && !_agreementEnd!.isAfter(_agreementStart!)) {
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
          content: Text('The agreement end date must be after the start date')));
      return;
    }

    if (_isEdit) {
      final data = <String, dynamic>{
        'full_name': _nameCtrl.text.trim(),
        'phone': _phoneCtrl.text.trim().isEmpty ? null : _phoneCtrl.text.trim(),
        'email': _emailCtrl.text.trim().isEmpty ? null : _emailCtrl.text.trim(),
        'id_proof_type': _idProofType,
        'id_proof_number': _idProofNumberCtrl.text.trim().isEmpty ? null : _idProofNumberCtrl.text.trim(),
        'kyc_verified': _kycVerified,
        'police_verification_status': _policeStatus.value,
        'emergency_contact_name': _emergencyNameCtrl.text.trim().isEmpty ? null : _emergencyNameCtrl.text.trim(),
        'emergency_contact_phone': _emergencyPhoneCtrl.text.trim().isEmpty ? null : _emergencyPhoneCtrl.text.trim(),
        'remarks': _remarksCtrl.text.trim().isEmpty ? null : _remarksCtrl.text.trim(),
      };
      ref.read(tenantFormProvider.notifier).update(widget.tenant!.id, data);
    } else {
      final data = <String, dynamic>{
        'flat_id': _selectedFlatId,
        'full_name': _nameCtrl.text.trim(),
        'phone': _phoneCtrl.text.trim().isEmpty ? null : _phoneCtrl.text.trim(),
        'email': _emailCtrl.text.trim().isEmpty ? null : _emailCtrl.text.trim(),
        if (_agreementStart != null) 'agreement_start_date': _dateStr(_agreementStart!),
        if (_agreementEnd != null) 'agreement_end_date': _dateStr(_agreementEnd!),
        if (_rentCtrl.text.trim().isNotEmpty) 'monthly_rent': _rentCtrl.text.trim(),
        if (_depositCtrl.text.trim().isNotEmpty) 'security_deposit': _depositCtrl.text.trim(),
        if (_idProofType != null) 'id_proof_type': _idProofType,
        if (_idProofNumberCtrl.text.trim().isNotEmpty) 'id_proof_number': _idProofNumberCtrl.text.trim(),
        'kyc_verified': _kycVerified,
        'police_verification_status': _policeStatus.value,
        if (_emergencyNameCtrl.text.trim().isNotEmpty) 'emergency_contact_name': _emergencyNameCtrl.text.trim(),
        if (_emergencyPhoneCtrl.text.trim().isNotEmpty) 'emergency_contact_phone': _emergencyPhoneCtrl.text.trim(),
        if (_remarksCtrl.text.trim().isNotEmpty) 'remarks': _remarksCtrl.text.trim(),
        if (_recordMoveIn && _moveInDate != null) 'move_in_date': _dateStr(_moveInDate!),
      };
      ref.read(tenantFormProvider.notifier).create(data);
    }
  }

  @override
  Widget build(BuildContext context) {
    final formState = ref.watch(tenantFormProvider);
    final isLoading = formState is TenantFormLoading;
    final wingsAsync = ref.watch(wingsProvider);
    final flatsAsync = ref.watch(flatsBySocietyProvider);

    ref.listen(tenantFormProvider, (_, next) {
      if (next is TenantFormSuccess) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(
          content: Text(next.message), backgroundColor: AppTheme.success, behavior: SnackBarBehavior.floating,
        ));
        ref.read(tenantListProvider.notifier).refresh();
        ref.invalidate(tenantsByFlatProvider(next.tenant.flatId));
        if (_isEdit) ref.invalidate(tenantDetailProvider(next.tenant.id));
        ref.invalidate(tenantAgreementsProvider(next.tenant.id));
        ref.read(tenantFormProvider.notifier).reset();
        context.pop();
      } else if (next is TenantFormError) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(
          content: Text(rmFriendlyError(next.message)), backgroundColor: AppTheme.error, behavior: SnackBarBehavior.floating,
        ));
      }
    });

    final flats = (flatsAsync.valueOrNull ?? <FlatModel>[])
        .where((f) => _selectedWingId == null || f.wingId == _selectedWingId)
        .toList();

    Future<void> pick({required DateTime? current, required DateTime first, required DateTime last, required DateTime fallback, required ValueChanged<DateTime> set}) async {
      final picked = await showDatePicker(context: context, initialDate: current ?? fallback, firstDate: first, lastDate: last);
      if (picked != null) setState(() => set(picked));
    }

    return AppFormPage(
      title: _isEdit ? 'Edit Tenant' : 'Add Tenant',
      subtitle: _isEdit ? widget.tenant!.fullName : 'Add a tenant to a rented flat',
      formKey: _formKey,
      submitLabel: _isEdit ? 'Save Changes' : 'Add Tenant',
      submitIcon: _isEdit ? Icons.save_rounded : Icons.person_add_alt_1_rounded,
      saving: isLoading,
      onSubmit: _submit,
      children: [
        FormSection(
          title: 'Tenant information',
          description: 'Who is renting, and how to reach them.',
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
          ],
        ),
        if (!_isEdit)
          FormSection(
            title: 'Flat and agreement',
            description: 'The flat being rented and the rent agreement (the agreement is optional).',
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
              FormFieldBox(
                label: 'Agreement start',
                child: FormDateField(
                  value: _agreementStart,
                  hint: 'Optional',
                  format: _dateStr,
                  onClear: () => setState(() => _agreementStart = null),
                  onTap: () => pick(
                    current: _agreementStart,
                    fallback: DateTime.now(),
                    first: DateTime(2000),
                    last: DateTime.now().add(const Duration(days: 365 * 5)),
                    set: (d) => _agreementStart = d,
                  ),
                ),
              ),
              FormFieldBox(
                label: 'Agreement end',
                child: FormDateField(
                  value: _agreementEnd,
                  hint: 'Optional',
                  format: _dateStr,
                  onClear: () => setState(() => _agreementEnd = null),
                  onTap: () => pick(
                    current: _agreementEnd,
                    fallback: DateTime.now().add(const Duration(days: 365)),
                    first: DateTime(2000),
                    last: DateTime.now().add(const Duration(days: 365 * 5)),
                    set: (d) => _agreementEnd = d,
                  ),
                ),
              ),
              FormFieldBox(
                label: 'Monthly rent',
                child: TextFormField(
                  controller: _rentCtrl,
                  keyboardType: const TextInputType.numberWithOptions(decimal: true),
                  inputFormatters: _moneyFormatters,
                  decoration: const InputDecoration(prefixText: '₹ '),
                ),
              ),
              FormFieldBox(
                label: 'Security deposit',
                child: TextFormField(
                  controller: _depositCtrl,
                  keyboardType: const TextInputType.numberWithOptions(decimal: true),
                  inputFormatters: _moneyFormatters,
                  decoration: const InputDecoration(prefixText: '₹ '),
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
                    onTap: () => pick(
                      current: _moveInDate,
                      fallback: DateTime.now(),
                      first: DateTime(2000),
                      last: DateTime.now(),
                      set: (d) => _moveInDate = d,
                    ),
                  ),
                ),
            ],
          ),
        FormSection(
          title: 'Verification',
          description: 'Identity and police verification the society keeps on record.',
          children: [
            FormFull(
              child: FormSwitchTile(
                title: 'KYC verified',
                subtitle: 'Identity documents have been checked',
                value: _kycVerified,
                onChanged: (v) => setState(() => _kycVerified = v),
              ),
            ),
            FormFieldBox(
              label: 'Police verification',
              child: DropdownButtonFormField<PoliceVerificationStatus>(
                isExpanded: true,
                value: _policeStatus,
                items: PoliceVerificationStatus.values.map((s) => DropdownMenuItem(value: s, child: Text(s.label))).toList(),
                onChanged: (v) => setState(() => _policeStatus = v ?? PoliceVerificationStatus.pending),
              ),
            ),
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
              child: TextFormField(controller: _idProofNumberCtrl, inputFormatters: [LengthLimitingTextInputFormatter(100)]),
            ),
          ],
        ),
        FormSection(
          title: 'Emergency contact and notes',
          children: [
            FormFieldBox(
              label: 'Contact name',
              child: TextFormField(
                controller: _emergencyNameCtrl,
                textCapitalization: TextCapitalization.words,
                inputFormatters: [LengthLimitingTextInputFormatter(255)],
              ),
            ),
            FormFieldBox(
              label: 'Contact phone',
              child: TextFormField(
                controller: _emergencyPhoneCtrl,
                keyboardType: TextInputType.phone,
                inputFormatters: [FilteringTextInputFormatter.digitsOnly, LengthLimitingTextInputFormatter(10)],
                validator: rmPhoneValidator,
              ),
            ),
            FormFull(
              child: FormFieldBox(
                label: 'Notes',
                child: TextFormField(controller: _remarksCtrl, maxLines: 3, maxLength: 1000),
              ),
            ),
          ],
        ),
      ],
    );
  }
}

