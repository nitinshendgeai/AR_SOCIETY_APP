import 'package:flutter/material.dart';
import 'package:ar_society_app/features/maintenance_billing/data/maintenance_billing_api.dart' show formatBillDate;
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/society_structure/data/models/structure_models.dart';
import 'package:ar_society_app/features/society_structure/presentation/providers/structure_providers.dart';
import 'package:ar_society_app/shared/widgets/app_form.dart';

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
  final _meter        = TextEditingController();
  final _consumer     = TextEditingController();
  DateTime? _possession;

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
      _possession        = widget.flat!.possessionDate;
      _meter.text        = widget.flat!.electricMeterNo ?? '';
      _consumer.text     = widget.flat!.electricConsumerNo ?? '';
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
    _meter.dispose();
    _consumer.dispose();
    super.dispose();
  }

  static String _iso(DateTime d) =>
      '${d.year.toString().padLeft(4, '0')}-${d.month.toString().padLeft(2, '0')}-${d.day.toString().padLeft(2, '0')}';

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
          // The possession date and the electricity numbers are always sent too, so they can be cleared
          'possession_date': _possession == null ? null : _iso(_possession!),
          'electric_meter_no': _meter.text.trim().isEmpty ? null : _meter.text.trim(),
          'electric_consumer_no': _consumer.text.trim().isEmpty ? null : _consumer.text.trim(),
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
          possessionDate: _possession == null ? null : _iso(_possession!),
          electricMeterNo: _meter.text.trim(),
          electricConsumerNo: _consumer.text.trim(),
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

    return AppFormPage(
      title: _isEdit ? 'Edit Flat' : 'Add Flat',
      subtitle: _isEdit
          ? '${widget.flat!.wingName != null ? '${widget.flat!.wingName} — ' : ''}${widget.flat!.flatNumber}'
          : 'A flat in one of the society\'s wings',
      formKey: _formKey,
      submitLabel: _isEdit ? 'Save Changes' : 'Add Flat',
      submitIcon: _isEdit ? Icons.save_rounded : Icons.add_rounded,
      saving: _saving,
      onSubmit: _submit,
      children: [
        FormSection(
          title: 'Location',
          description: 'Where the flat is. A flat cannot move to another wing once it exists.',
          children: [
            FormFieldBox(
              label: 'Wing',
              required: !_isEdit,
              child: _isEdit
                  ? InputDecorator(
                      decoration: const InputDecoration(),
                      child: Text(widget.flat!.wingName ?? '—'),
                    )
                  : wingsAsync.when(
                      loading: () => const LinearProgressIndicator(),
                      error: (_, __) => const SizedBox.shrink(),
                      data: (wings) {
                        final active = wings.where((w) => w.isActive).toList();
                        return DropdownButtonFormField<String>(
                isExpanded: true,
                          value: _selectedWingId,
                          hint: const Text('Select wing'),
                          items: active.map((w) => DropdownMenuItem(value: w.id, child: Text(w.displayName))).toList(),
                          onChanged: (v) => setState(() {
                            _selectedWingId = v;
                            _selectedFloor = null;
                            _floor.clear();
                          }),
                          validator: (v) => v == null ? 'Wing is required' : null,
                        );
                      },
                    ),
            ),
            FormFieldBox(
              label: 'Flat number',
              required: true,
              child: TextFormField(
                controller: _flatNumber,
                decoration: const InputDecoration(hintText: 'e.g. 101, A-101'),
                validator: (v) => v == null || v.trim().isEmpty ? 'Flat number is required' : null,
              ),
            ),
            FormFieldBox(
              label: 'Floor number',
              helper: '0 = ground, negative for a basement',
              child: TextFormField(
                controller: _floor,
                keyboardType: TextInputType.number,
                inputFormatters: [FilteringTextInputFormatter.allow(RegExp(r'^-?\d*'))],
                decoration: const InputDecoration(hintText: 'Optional'),
                validator: (v) {
                  final t = (v ?? '').trim();
                  if (t.isEmpty) return null;
                  final n = int.tryParse(t);
                  if (n == null) return 'Must be a number';
                  if (n < -10 || n > 200) return 'Floor must be between -10 and 200';
                  return null;
                },
                onChanged: (v) => _selectedFloor = v.trim().isEmpty ? null : int.tryParse(v.trim()),
              ),
            ),
          ],
        ),
        FormSection(
          title: 'Size and type',
          description: 'Used for area-based charges and for reports.',
          children: [
            FormFieldBox(
              label: 'Flat type',
              child: DropdownButtonFormField<String>(
                isExpanded: true,
                value: _selectedFlatType,
                hint: const Text('Select type (optional)'),
                // A type the list doesn't know (an older record) stays selectable
                items: [
                  ..._flatTypes,
                  if (_selectedFlatType != null && !_flatTypes.contains(_selectedFlatType)) _selectedFlatType!,
                ].map((t) => DropdownMenuItem(value: t, child: Text(t))).toList(),
                onChanged: (v) => setState(() => _selectedFlatType = v),
              ),
            ),
            FormFieldBox(
              label: 'Area (sq ft)',
              child: TextFormField(
                controller: _area,
                keyboardType: const TextInputType.numberWithOptions(decimal: true),
                inputFormatters: [FilteringTextInputFormatter.allow(RegExp(r'^\d*\.?\d*'))],
                decoration: const InputDecoration(hintText: 'e.g. 850 (optional)'),
                validator: (v) {
                  final t = (v ?? '').trim();
                  if (t.isEmpty) return null;
                  final n = double.tryParse(t);
                  return n == null || n <= 0 ? 'Enter an area above zero' : null;
                },
              ),
            ),
            FormFieldBox(
              label: 'Possession date',
              child: FormDateField(
                value: _possession,
                hint: 'Optional',
                format: formatBillDate,
                onClear: () => setState(() => _possession = null),
                onTap: () async {
                  final d = await showDatePicker(
                    context: context,
                    initialDate: _possession ?? DateTime.now(),
                    firstDate: DateTime(2000),
                    lastDate: DateTime.now().add(const Duration(days: 366)),
                  );
                  if (d != null) setState(() => _possession = d);
                },
              ),
            ),
            // Occupancy status is display-only once a flat exists — it is changed exclusively through the
            // Occupancy move-in/move-out workflow (Resident/Tenant detail screens), never by editing the
            // flat directly. See Phase M1.3 §5 / M1.4 §5.
            if (_isEdit)
              FormFieldBox(
                label: 'Occupancy status',
                helper: 'Change this with Move In / Move Out on the resident or tenant, not here.',
                child: InputDecorator(
                  decoration: const InputDecoration(),
                  child: Text(_occupancyLabel(widget.flat!.occupancyStatus ?? 'vacant')),
                ),
              )
            else
              FormFieldBox(
                label: 'Occupancy status',
                child: DropdownButtonFormField<String>(
                isExpanded: true,
                  value: _selectedOccupancy,
                  hint: const Text('Select status (optional)'),
                  items: _occupancyStatuses.map((s) => DropdownMenuItem(value: s, child: Text(_occupancyLabel(s)))).toList(),
                  onChanged: (v) => setState(() => _selectedOccupancy = v),
                ),
              ),
          ],
        ),
        FormSection(
          title: 'Billing and utilities',
          description: 'Printed on this flat\'s maintenance bills.',
          children: [
            FormFieldBox(
              label: 'Virtual A/c No. (VAN)',
              helper: 'From the society\'s bank, for NEFT payments',
              child: TextFormField(
                controller: _van,
                textCapitalization: TextCapitalization.characters,
                inputFormatters: [
                  FilteringTextInputFormatter.allow(RegExp(r'[A-Za-z0-9 -]')),
                  LengthLimitingTextInputFormatter(40),
                ],
                decoration: const InputDecoration(hintText: 'Optional'),
                validator: (v) {
                  final van = (v ?? '').replaceAll(RegExp(r'[\s-]'), '');
                  if (van.isEmpty) return null;
                  return RegExp(r'^[A-Za-z0-9]{4,30}$').hasMatch(van) ? null : 'Use 4-30 letters or digits';
                },
              ),
            ),
            FormFieldBox(
              label: 'Electric meter no.',
              child: TextFormField(controller: _meter, inputFormatters: [LengthLimitingTextInputFormatter(40)]),
            ),
            FormFieldBox(
              label: 'Consumer no.',
              helper: 'Electricity account',
              child: TextFormField(controller: _consumer, inputFormatters: [LengthLimitingTextInputFormatter(40)]),
            ),
            FormFull(
              child: FormFieldBox(
                label: 'Remarks',
                child: TextFormField(
                  controller: _remarks,
                  maxLines: 3,
                  decoration: const InputDecoration(hintText: 'Optional notes about this flat'),
                ),
              ),
            ),
          ],
        ),
      ],
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
