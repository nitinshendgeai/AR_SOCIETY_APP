import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/society_structure/data/models/structure_models.dart';
import 'package:ar_society_app/features/society_structure/presentation/providers/structure_providers.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';

class FlatFormScreen extends ConsumerStatefulWidget {
  final FlatModel? flat;
  final WingModel? defaultWing;
  final FloorModel? defaultFloor;
  const FlatFormScreen({super.key, this.flat, this.defaultWing, this.defaultFloor});

  @override
  ConsumerState<FlatFormScreen> createState() => _FlatFormScreenState();
}

class _FlatFormScreenState extends ConsumerState<FlatFormScreen> {
  final _formKey      = GlobalKey<FormState>();
  final _flatNumber   = TextEditingController();
  final _area         = TextEditingController();
  final _remarks      = TextEditingController();
  final _van          = TextEditingController();
  final _floor        = TextEditingController();

  String? _selectedWingId;
  String? _selectedFlatType;
  String? _selectedOccupancy;
  int?    _selectedFloor;
  bool _saving = false;

  bool get _isEdit => widget.flat != null;

  static const _flatTypes = [
    '1BHK', '2BHK', '3BHK', '4BHK', 'Studio', 'Duplex', 'Penthouse', 'Shop', 'Office', 'Other',
  ];

  static const _occupancyStatuses = [
    'vacant', 'owner_occupied', 'tenant_occupied',
  ];

  @override
  void initState() {
    super.initState();
    if (_isEdit) {
      _flatNumber.text   = widget.flat!.flatNumber;
      _area.text         = widget.flat!.areaSqft?.toStringAsFixed(0) ?? '';
      _remarks.text      = widget.flat!.remarks ?? '';
      _van.text          = widget.flat!.virtualAccountNumber ?? '';
      _selectedWingId    = widget.flat!.wingId;
      _selectedFlatType  = widget.flat!.flatType;
      // Occupancy status is deliberately NOT loaded here — it is display-only
      // in edit mode. See the removed dropdown below and
      // backend/app/schemas/flat.py's FlatUpdate (Phase M1.3 §5 / M1.4 §5):
      // a flat's occupancy is changed only through the canonical
      // Occupancy move-in/move-out workflow, never a generic Flat PATCH.
      _selectedFloor     = widget.flat!.floor;
    } else {
      _selectedWingId    = widget.defaultWing?.id;
      _selectedFloor     = widget.defaultFloor?.floorNumber;
    }
    _floor.text = _selectedFloor?.toString() ?? '';
  }

  @override
  void dispose() {
    _flatNumber.dispose();
    _area.dispose();
    _remarks.dispose();
    _van.dispose();
    _floor.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    if (_selectedWingId == null) {
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
          content: Text('Please select a wing')));
      return;
    }
    setState(() => _saving = true);
    try {
      if (_isEdit) {
        // The wing isn't sent: a flat stays in its wing (shown read-only below)
        final data = <String, dynamic>{
          'flat_number': _flatNumber.text.trim(),
          if (_selectedFloor != null) 'floor': _selectedFloor,
          if (_selectedFlatType != null) 'flat_type': _selectedFlatType,
          if (_area.text.trim().isNotEmpty)
            'area_sqft': double.parse(_area.text.trim()),
          // occupancy_status intentionally omitted — FlatUpdate no longer
          // accepts it (Phase M1.3). Occupancy changes go through the
          // Occupancy move-in/move-out actions on Resident/Tenant detail.
          'remarks': _remarks.text.trim().isEmpty
              ? null
              : _remarks.text.trim(),
          // Always sent, so clearing the field removes the VAN
          'virtual_account_number': _van.text.trim(),
        };
        await ref.read(flatsBySocietyProvider.notifier).updateFlat(widget.flat!.id, data);
      } else {
        await ref.read(flatsBySocietyProvider.notifier).create(
          flatNumber: _flatNumber.text.trim(),
          wingId: _selectedWingId!,
          floor: _selectedFloor,
          flatType: _selectedFlatType,
          areaSqft: _area.text.trim().isEmpty
              ? null
              : double.parse(_area.text.trim()),
          occupancyStatus: _selectedOccupancy,
          remarks: _remarks.text.trim().isEmpty
              ? null
              : _remarks.text.trim(),
          virtualAccountNumber: _van.text.trim(),
        );
      }
      if (mounted) Navigator.pop(context);
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(
            content: Text(friendlyErrorMessage(e)), backgroundColor: AppTheme.error));
      }
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final wingsAsync = ref.watch(wingsProvider);

    return Scaffold(
      backgroundColor: AppTheme.surface,
      appBar: AppBar(title: Text(_isEdit ? 'Edit Flat' : 'Add Flat')),
      body: ResponsiveBody(child: Form(
        key: _formKey,
        // A plain scroll view, not a lazy ListView: fields scrolled out of
        // view stay mounted, so validate() checks every one of them.
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(20),
          child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            // Wing selector — a flat can't move to another wing, so when
            // editing it is shown, not chosen
            if (_isEdit)
              InputDecorator(
                decoration: const InputDecoration(labelText: 'Wing'),
                child: Text(widget.flat!.wingName ?? '—'),
              )
            else
            wingsAsync.when(
              loading: () => const LinearProgressIndicator(),
              error: (_, __) => const SizedBox.shrink(),
              data: (wings) {
                final active = wings.where((w) => w.isActive).toList();
                return DropdownButtonFormField<String>(
                  value: _selectedWingId,
                  decoration: const InputDecoration(labelText: 'Wing *'),
                  hint: const Text('Select wing'),
                  items: active
                      .map((w) => DropdownMenuItem(
                          value: w.id, child: Text(w.displayName)))
                      .toList(),
                  onChanged: (v) => setState(() {
                    _selectedWingId = v;
                    _selectedFloor  = null;
                    _floor.clear();
                  }),
                  validator: (v) =>
                      v == null ? 'Wing is required' : null,
                );
              },
            ),
            const SizedBox(height: 16),
            TextFormField(
              controller: _flatNumber,
              decoration: const InputDecoration(
                labelText: 'Flat Number *',
                hintText: 'e.g. 101, A-101',
              ),
              validator: (v) =>
                  v == null || v.trim().isEmpty ? 'Flat number is required' : null,
            ),
            const SizedBox(height: 16),
            TextFormField(
              controller: _floor,
              keyboardType: TextInputType.number,
              inputFormatters: [
                FilteringTextInputFormatter.allow(RegExp(r'^-?\d*')),
              ],
              decoration: const InputDecoration(
                labelText: 'Floor Number',
                hintText: '0 = Ground, negative for basement (optional)',
              ),
              validator: (v) {
                final t = (v ?? '').trim();
                if (t.isEmpty) return null;
                final n = int.tryParse(t);
                if (n == null) return 'Must be a number';
                if (n < -10 || n > 200) return 'Floor must be between -10 and 200';
                return null;
              },
              onChanged: (v) =>
                  _selectedFloor = v.trim().isEmpty ? null : int.tryParse(v.trim()),
            ),
            const SizedBox(height: 16),
            DropdownButtonFormField<String>(
              value: _selectedFlatType,
              decoration: const InputDecoration(labelText: 'Flat Type'),
              hint: const Text('Select type (optional)'),
              // A type the list doesn't know (an older record) stays selectable
              items: [
                ..._flatTypes,
                if (_selectedFlatType != null && !_flatTypes.contains(_selectedFlatType)) _selectedFlatType!,
              ].map((t) => DropdownMenuItem(value: t, child: Text(t))).toList(),
              onChanged: (v) => setState(() => _selectedFlatType = v),
            ),
            const SizedBox(height: 16),
            TextFormField(
              controller: _area,
              keyboardType: const TextInputType.numberWithOptions(decimal: true),
              inputFormatters: [
                FilteringTextInputFormatter.allow(RegExp(r'^\d*\.?\d*')),
              ],
              decoration: const InputDecoration(
                labelText: 'Area (sq ft)',
                hintText: 'e.g. 850 (optional)',
              ),
              validator: (v) {
                final t = (v ?? '').trim();
                if (t.isEmpty) return null;
                final n = double.tryParse(t);
                return n == null || n <= 0 ? 'Enter an area above zero' : null;
              },
            ),
            const SizedBox(height: 16),
            if (_isEdit) ...[
              // Occupancy status is display-only once a flat exists — it is
              // changed exclusively through the Occupancy move-in/move-out
              // workflow (Resident/Tenant detail screens), never by editing
              // the flat directly. See Phase M1.3 §5 / M1.4 §5.
              Container(
                padding: const EdgeInsets.all(14),
                decoration: BoxDecoration(
                  color: AppTheme.surface,
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(color: AppTheme.border),
                ),
                child: Row(children: [
                  const Icon(Icons.info_outline_rounded, size: 18, color: AppTheme.textSecondary),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Text(
                      'Occupancy status: ${_occupancyLabel(widget.flat!.occupancyStatus ?? 'vacant')} '
                      '— change this via Move In / Move Out on the resident or tenant, not here.',
                      style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary),
                    ),
                  ),
                ]),
              ),
            ] else
              DropdownButtonFormField<String>(
                value: _selectedOccupancy,
                decoration: const InputDecoration(labelText: 'Occupancy Status'),
                hint: const Text('Select status (optional)'),
                items: _occupancyStatuses
                    .map((s) => DropdownMenuItem(
                        value: s, child: Text(_occupancyLabel(s))))
                    .toList(),
                onChanged: (v) => setState(() => _selectedOccupancy = v),
              ),
            const SizedBox(height: 16),
            TextFormField(
              controller: _van,
              textCapitalization: TextCapitalization.characters,
              inputFormatters: [
                FilteringTextInputFormatter.allow(RegExp(r'[A-Za-z0-9 -]')),
                LengthLimitingTextInputFormatter(40),
              ],
              decoration: const InputDecoration(
                labelText: 'Virtual A/c No. (VAN)',
                hintText: 'From the society\'s bank, for NEFT payments (optional)',
                helperText: 'Printed on this flat\'s maintenance bills',
              ),
              validator: (v) {
                final van = (v ?? '').replaceAll(RegExp(r'[\s-]'), '');
                if (van.isEmpty) return null;
                return RegExp(r'^[A-Za-z0-9]{4,30}$').hasMatch(van)
                    ? null
                    : 'Use 4-30 letters or digits';
              },
            ),
            const SizedBox(height: 16),
            TextFormField(
              controller: _remarks,
              maxLines: 2,
              decoration: const InputDecoration(
                labelText: 'Remarks',
                hintText: 'Optional notes about this flat',
                alignLabelWithHint: true,
              ),
            ),
            const SizedBox(height: 32),
            SizedBox(
              height: 48,
              child: ElevatedButton(
                onPressed: _saving ? null : _submit,
                child: _saving
                    ? const SizedBox(
                        width: 22,
                        height: 22,
                        child: CircularProgressIndicator(
                            strokeWidth: 2, color: Colors.white))
                    : Text(_isEdit ? 'Save Changes' : 'Add Flat'),
              ),
            ),
          ],
          ),
        ),
      )),
    );
  }

  String _occupancyLabel(String s) {
    switch (s) {
      case 'owner_occupied': return 'Owner Occupied';
      case 'tenant_occupied': return 'Tenant Occupied';
      case 'vacant': return 'Vacant';
      default: return s;
    }
  }
}
