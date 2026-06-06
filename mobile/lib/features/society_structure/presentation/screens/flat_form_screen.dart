import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/society_structure/data/models/structure_models.dart';
import 'package:ar_society_app/features/society_structure/presentation/providers/structure_providers.dart';

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

  String? _selectedWingId;
  String? _selectedFlatType;
  String? _selectedOccupancy;
  int?    _selectedFloor;
  bool _saving = false;

  bool get _isEdit => widget.flat != null;

  static const _flatTypes = [
    '1BHK', '2BHK', '3BHK', '4BHK', 'Studio', 'Duplex', 'Penthouse', 'Shop', 'Office',
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
      _selectedWingId    = widget.flat!.wingId;
      _selectedFlatType  = widget.flat!.flatType;
      _selectedOccupancy = widget.flat!.occupancyStatus;
      _selectedFloor     = widget.flat!.floor;
    } else {
      _selectedWingId    = widget.defaultWing?.id;
      _selectedFloor     = widget.defaultFloor?.floorNumber;
    }
  }

  @override
  void dispose() {
    _flatNumber.dispose();
    _area.dispose();
    _remarks.dispose();
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
        final data = <String, dynamic>{
          'flat_number': _flatNumber.text.trim(),
          'wing_id': _selectedWingId!,
          if (_selectedFloor != null) 'floor': _selectedFloor,
          if (_selectedFlatType != null) 'flat_type': _selectedFlatType,
          if (_area.text.trim().isNotEmpty)
            'area_sqft': double.parse(_area.text.trim()),
          if (_selectedOccupancy != null) 'occupancy_status': _selectedOccupancy,
          'remarks': _remarks.text.trim().isEmpty
              ? null
              : _remarks.text.trim(),
        };
        await ref.read(flatsBySocietyProvider.notifier).update(widget.flat!.id, data);
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
        );
      }
      if (mounted) Navigator.pop(context);
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(
            content: Text('Error: $e'), backgroundColor: AppTheme.error));
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
      body: Form(
        key: _formKey,
        child: ListView(
          padding: const EdgeInsets.all(20),
          children: [
            // Wing selector
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
              initialValue: _selectedFloor?.toString(),
              keyboardType: TextInputType.number,
              inputFormatters: [
                FilteringTextInputFormatter.allow(RegExp(r'^-?\d*')),
              ],
              decoration: const InputDecoration(
                labelText: 'Floor Number',
                hintText: '0 = Ground (optional)',
              ),
              onChanged: (v) =>
                  _selectedFloor = v.trim().isEmpty ? null : int.tryParse(v.trim()),
            ),
            const SizedBox(height: 16),
            DropdownButtonFormField<String>(
              value: _selectedFlatType,
              decoration: const InputDecoration(labelText: 'Flat Type'),
              hint: const Text('Select type (optional)'),
              items: _flatTypes
                  .map((t) => DropdownMenuItem(value: t, child: Text(t)))
                  .toList(),
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
            ),
            const SizedBox(height: 16),
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
