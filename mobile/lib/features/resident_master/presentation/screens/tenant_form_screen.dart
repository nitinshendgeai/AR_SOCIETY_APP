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
import 'package:ar_society_app/shared/widgets/app_widgets.dart';

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

    return Scaffold(
      backgroundColor: AppTheme.surface,
      appBar: AppBar(title: Text(_isEdit ? 'Edit Tenant' : 'Add Tenant')),
      body: ResponsiveBody(child: Form(
        key: _formKey,
        child: ListView(
          padding: const EdgeInsets.all(20),
          children: [
            const RmSectionHeader('Tenant Information'),
            const SizedBox(height: 10),
            RmFormField(
              label: 'Full Name *',
              child: TextFormField(
                controller: _nameCtrl,
                textCapitalization: TextCapitalization.words,
                decoration: const InputDecoration(hintText: 'Enter full name'),
                validator: (v) => (v == null || v.trim().isEmpty) ? 'Name is required' : null,
              ),
            ),

            const SizedBox(height: 8),
            const RmSectionHeader('Contact'),
            const SizedBox(height: 10),
            RmFormField(
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
            RmFormField(
              label: 'Email',
              child: TextFormField(controller: _emailCtrl, keyboardType: TextInputType.emailAddress),
            ),

            if (!_isEdit) ...[
              const SizedBox(height: 8),
              const RmSectionHeader('Flat'),
              const SizedBox(height: 10),
              RmFormField(
                label: 'Wing',
                child: wingsAsync.when(
                  loading: () => const LinearProgressIndicator(),
                  error: (_, __) => const SizedBox.shrink(),
                  data: (wings) => DropdownButtonFormField<String>(
                    value: _selectedWingId,
                    hint: const Text('Select wing (optional filter)'),
                    items: wings.where((w) => w.isActive)
                        .map((w) => DropdownMenuItem(value: w.id, child: Text(w.displayName)))
                        .toList(),
                    onChanged: (v) => setState(() {
                      _selectedWingId = v;
                      _selectedFlatId = null;
                    }),
                  ),
                ),
              ),
              RmFormField(
                label: 'Flat *',
                child: DropdownButtonFormField<String>(
                  value: _selectedFlatId,
                  hint: const Text('Select flat'),
                  items: flats.map((f) => DropdownMenuItem(
                        value: f.id,
                        child: Text(f.wingName != null ? '${f.wingName} — ${f.flatNumber}' : f.flatNumber),
                      )).toList(),
                  onChanged: (v) => setState(() => _selectedFlatId = v),
                  validator: (v) => v == null ? 'Flat is required' : null,
                ),
              ),

              const SizedBox(height: 8),
              const RmSectionHeader('Agreement (optional)'),
              const SizedBox(height: 10),
              Row(children: [
                Expanded(
                  child: RmFormField(
                    label: 'Start Date',
                    child: InkWell(
                      onTap: () async {
                        final picked = await showDatePicker(
                          context: context, initialDate: _agreementStart ?? DateTime.now(),
                          firstDate: DateTime(2000), lastDate: DateTime.now().add(const Duration(days: 365 * 5)),
                        );
                        if (picked != null) setState(() => _agreementStart = picked);
                      },
                      child: _DatePillDisplay(date: _agreementStart),
                    ),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: RmFormField(
                    label: 'End Date',
                    child: InkWell(
                      onTap: () async {
                        final picked = await showDatePicker(
                          context: context, initialDate: _agreementEnd ?? DateTime.now().add(const Duration(days: 365)),
                          firstDate: DateTime(2000), lastDate: DateTime.now().add(const Duration(days: 365 * 5)),
                        );
                        if (picked != null) setState(() => _agreementEnd = picked);
                      },
                      child: _DatePillDisplay(date: _agreementEnd),
                    ),
                  ),
                ),
              ]),
              RmFormField(
                label: 'Monthly Rent',
                child: TextFormField(controller: _rentCtrl, keyboardType: const TextInputType.numberWithOptions(decimal: true)),
              ),
              RmFormField(
                label: 'Security Deposit',
                child: TextFormField(controller: _depositCtrl, keyboardType: const TextInputType.numberWithOptions(decimal: true)),
              ),
            ],

            const SizedBox(height: 8),
            const RmSectionHeader('Verification'),
            const SizedBox(height: 10),
            RmFormField(
              label: 'KYC Verified',
              child: SwitchListTile(
                value: _kycVerified,
                onChanged: (v) => setState(() => _kycVerified = v),
                contentPadding: EdgeInsets.zero,
                title: const Text('Identity documents verified', style: TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
              ),
            ),
            RmFormField(
              label: 'Police Verification',
              child: DropdownButtonFormField<PoliceVerificationStatus>(
                value: _policeStatus,
                items: PoliceVerificationStatus.values
                    .map((s) => DropdownMenuItem(value: s, child: Text(s.label)))
                    .toList(),
                onChanged: (v) => setState(() => _policeStatus = v ?? PoliceVerificationStatus.pending),
              ),
            ),
            RmFormField(
              label: 'ID Proof Type',
              child: DropdownButtonFormField<String>(
                value: _idProofType,
                hint: const Text('Select ID type'),
                items: _idProofTypes.map((t) => DropdownMenuItem(value: t, child: Text(t))).toList(),
                onChanged: (v) => setState(() => _idProofType = v),
              ),
            ),
            RmFormField(label: 'ID Proof Number', child: TextFormField(controller: _idProofNumberCtrl)),

            const SizedBox(height: 8),
            const RmSectionHeader('Emergency Contact'),
            const SizedBox(height: 10),
            RmFormField(
              label: 'Contact Name',
              child: TextFormField(controller: _emergencyNameCtrl, textCapitalization: TextCapitalization.words),
            ),
            RmFormField(
              label: 'Contact Phone',
              child: TextFormField(
                controller: _emergencyPhoneCtrl,
                keyboardType: TextInputType.phone,
                inputFormatters: [FilteringTextInputFormatter.digitsOnly, LengthLimitingTextInputFormatter(10)],
                validator: rmPhoneValidator,
              ),
            ),

            const SizedBox(height: 8),
            const RmSectionHeader('Financial Information'),
            const SizedBox(height: 10),
            RmFormField(
              label: 'Remarks',
              child: TextFormField(controller: _remarksCtrl, maxLines: 2),
            ),

            if (!_isEdit) ...[
              const SizedBox(height: 8),
              const RmSectionHeader('Occupancy'),
              const SizedBox(height: 10),
              RmFormField(
                label: 'Already Moved In?',
                child: SwitchListTile(
                  value: _recordMoveIn,
                  onChanged: (v) => setState(() {
                    _recordMoveIn = v;
                    if (v) _moveInDate ??= DateTime.now();
                  }),
                  contentPadding: EdgeInsets.zero,
                  title: const Text('Record a move-in date now', style: TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
                ),
              ),
              if (_recordMoveIn)
                RmFormField(
                  label: 'Move-in Date',
                  child: InkWell(
                    onTap: () async {
                      final picked = await showDatePicker(
                        context: context, initialDate: _moveInDate ?? DateTime.now(),
                        firstDate: DateTime(2000), lastDate: DateTime.now().add(const Duration(days: 365)),
                      );
                      if (picked != null) setState(() => _moveInDate = picked);
                    },
                    child: _DatePillDisplay(date: _moveInDate),
                  ),
                ),
            ],

            const SizedBox(height: 32),
            AppPrimaryButton(
              label: _isEdit ? 'Save Changes' : 'Add Tenant',
              icon: _isEdit ? Icons.save_rounded : Icons.person_add_alt_1_rounded,
              isLoading: isLoading,
              onPressed: _submit,
            ),
          ],
        ),
      )),
    );
  }
}

class _DatePillDisplay extends StatelessWidget {
  final DateTime? date;
  const _DatePillDisplay({this.date});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 14),
      decoration: BoxDecoration(
        color: AppTheme.cardBg, borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppTheme.border),
      ),
      child: Row(children: [
        const Icon(Icons.calendar_today_rounded, size: 16, color: AppTheme.primary),
        const SizedBox(width: 8),
        Expanded(
          child: Text(
            date != null ? '${date!.day}/${date!.month}/${date!.year}' : 'Select',
            style: TextStyle(fontSize: 13, color: date != null ? AppTheme.textPrimary : AppTheme.textSecondary),
            overflow: TextOverflow.ellipsis,
          ),
        ),
      ]),
    );
  }
}
