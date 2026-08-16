import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/features/resident_master/data/models/resident_master_models.dart';
import 'package:ar_society_app/features/resident_master/presentation/providers/resident_master_providers.dart';
import 'package:ar_society_app/features/resident_master/presentation/widgets/resident_master_widgets.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';

/// Add/Edit Vehicle bottom sheet, launched contextually from a Resident or
/// Tenant detail screen. Vehicle number normalization is authoritative on
/// the backend (see backend/app/utils/vehicle_number.py) — this sheet
/// displays whatever normalized value the server returns rather than
/// re-implementing normalization client-side.
Future<void> showVehicleFormSheet(
  BuildContext context,
  WidgetRef ref, {
  required String flatId,
  String? residentId,
  String? tenantId,
  VehicleModel? vehicle,
}) {
  return showModalBottomSheet(
    context: context,
    isScrollControlled: true,
    backgroundColor: Colors.transparent,
    builder: (ctx) => _VehicleFormSheetBody(
      flatId: flatId, residentId: residentId, tenantId: tenantId, vehicle: vehicle,
    ),
  );
}

class _VehicleFormSheetBody extends ConsumerStatefulWidget {
  final String flatId;
  final String? residentId;
  final String? tenantId;
  final VehicleModel? vehicle;

  const _VehicleFormSheetBody({
    required this.flatId, this.residentId, this.tenantId, this.vehicle,
  });

  @override
  ConsumerState<_VehicleFormSheetBody> createState() => _VehicleFormSheetBodyState();
}

class _VehicleFormSheetBodyState extends ConsumerState<_VehicleFormSheetBody> {
  final _formKey = GlobalKey<FormState>();
  final _numberCtrl = TextEditingController();
  final _makeCtrl = TextEditingController();
  final _modelCtrl = TextEditingController();
  final _colorCtrl = TextEditingController();
  final _slotCtrl = TextEditingController();
  VehicleType _type = VehicleType.car;
  bool _submitting = false;
  String? _error;

  bool get _isEdit => widget.vehicle != null;

  @override
  void initState() {
    super.initState();
    final v = widget.vehicle;
    if (v != null) {
      _numberCtrl.text = v.vehicleNumber;
      _makeCtrl.text = v.make ?? '';
      _modelCtrl.text = v.model ?? '';
      _colorCtrl.text = v.color ?? '';
      _slotCtrl.text = v.parkingSlot ?? '';
      _type = v.vehicleType;
    }
  }

  @override
  void dispose() {
    _numberCtrl.dispose();
    _makeCtrl.dispose();
    _modelCtrl.dispose();
    _colorCtrl.dispose();
    _slotCtrl.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    final societyId = ref.read(currentUserProvider)?.societyId;
    if (societyId == null) {
      setState(() => _error = 'Society not loaded. Please reload the app.');
      return;
    }
    setState(() { _submitting = true; _error = null; });
    try {
      final notifier = ref.read(vehiclesByFlatProvider(widget.flatId).notifier);
      if (_isEdit) {
        await notifier.edit(widget.vehicle!.id, {
          'vehicle_type': _type.value,
          if (_makeCtrl.text.trim().isNotEmpty) 'make': _makeCtrl.text.trim(),
          if (_modelCtrl.text.trim().isNotEmpty) 'model': _modelCtrl.text.trim(),
          if (_colorCtrl.text.trim().isNotEmpty) 'color': _colorCtrl.text.trim(),
          'parking_slot': _slotCtrl.text.trim().isEmpty ? null : _slotCtrl.text.trim(),
        });
      } else {
        await notifier.add({
          'society_id': societyId,
          'flat_id': widget.flatId,
          if (widget.residentId != null) 'resident_id': widget.residentId,
          if (widget.tenantId != null) 'tenant_id': widget.tenantId,
          'vehicle_number': _numberCtrl.text.trim(),
          'vehicle_type': _type.value,
          if (_makeCtrl.text.trim().isNotEmpty) 'make': _makeCtrl.text.trim(),
          if (_modelCtrl.text.trim().isNotEmpty) 'model': _modelCtrl.text.trim(),
          if (_colorCtrl.text.trim().isNotEmpty) 'color': _colorCtrl.text.trim(),
          if (_slotCtrl.text.trim().isNotEmpty) 'parking_slot': _slotCtrl.text.trim(),
        });
      }
      if (mounted) {
        Navigator.of(context).pop();
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(
          content: Text(_isEdit ? 'Vehicle updated' : 'Vehicle added'),
          backgroundColor: AppTheme.success,
          behavior: SnackBarBehavior.floating,
        ));
      }
    } catch (e) {
      if (mounted) setState(() { _submitting = false; _error = rmFriendlyError(e); });
      return;
    }
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: EdgeInsets.only(bottom: MediaQuery.of(context).viewInsets.bottom),
      child: Container(
        padding: const EdgeInsets.fromLTRB(20, 20, 20, 28),
        decoration: const BoxDecoration(
          color: AppTheme.cardBg,
          borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
        ),
        child: Form(
          key: _formKey,
          child: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Center(
                  child: Container(
                    width: 40, height: 4, margin: const EdgeInsets.only(bottom: 16),
                    decoration: BoxDecoration(color: AppTheme.border, borderRadius: BorderRadius.circular(2)),
                  ),
                ),
                Text(_isEdit ? 'Edit Vehicle' : 'Add Vehicle',
                    style: const TextStyle(fontSize: 17, fontWeight: FontWeight.w700, color: AppTheme.textPrimary)),
                const SizedBox(height: 16),
                TextFormField(
                  controller: _numberCtrl,
                  enabled: !_isEdit,
                  textCapitalization: TextCapitalization.characters,
                  decoration: const InputDecoration(labelText: 'Vehicle Number *', hintText: 'e.g. MH12AB1234'),
                  validator: (v) => (v == null || v.trim().isEmpty) ? 'Vehicle number is required' : null,
                ),
                const SizedBox(height: 14),
                DropdownButtonFormField<VehicleType>(
                  value: _type,
                  decoration: const InputDecoration(labelText: 'Vehicle Type'),
                  items: VehicleType.values
                      .map((t) => DropdownMenuItem(value: t, child: Text(t.label)))
                      .toList(),
                  onChanged: (v) => setState(() => _type = v ?? VehicleType.car),
                ),
                const SizedBox(height: 14),
                Row(children: [
                  Expanded(
                    child: TextFormField(
                      controller: _makeCtrl,
                      decoration: const InputDecoration(labelText: 'Make', hintText: 'Honda'),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: TextFormField(
                      controller: _modelCtrl,
                      decoration: const InputDecoration(labelText: 'Model', hintText: 'City'),
                    ),
                  ),
                ]),
                const SizedBox(height: 14),
                Row(children: [
                  Expanded(
                    child: TextFormField(
                      controller: _colorCtrl,
                      decoration: const InputDecoration(labelText: 'Color'),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: TextFormField(
                      controller: _slotCtrl,
                      decoration: const InputDecoration(labelText: 'Parking Slot'),
                    ),
                  ),
                ]),
                if (_error != null) ...[
                  const SizedBox(height: 12),
                  AppErrorBanner(message: _error!),
                ],
                const SizedBox(height: 20),
                AppPrimaryButton(
                  label: _isEdit ? 'Save Changes' : 'Add Vehicle',
                  isLoading: _submitting,
                  onPressed: _submit,
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
