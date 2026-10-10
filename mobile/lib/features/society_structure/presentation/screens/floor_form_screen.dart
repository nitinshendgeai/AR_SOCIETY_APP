import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/society_settings/presentation/providers/society_settings_providers.dart';
import 'package:ar_society_app/features/society_structure/data/models/structure_models.dart';
import 'package:ar_society_app/features/society_structure/domain/flat_numbering.dart';
import 'package:ar_society_app/features/society_structure/presentation/providers/structure_providers.dart';
import 'package:ar_society_app/shared/widgets/app_form.dart';

class FloorFormScreen extends ConsumerStatefulWidget {
  final WingModel wing;
  final FloorModel? floor;
  const FloorFormScreen({super.key, required this.wing, this.floor});

  @override
  ConsumerState<FloorFormScreen> createState() => _FloorFormScreenState();
}

class _FloorFormScreenState extends ConsumerState<FloorFormScreen> {
  final _formKey     = GlobalKey<FormState>();
  final _floorNumber = TextEditingController();
  final _floorName   = TextEditingController();
  final _unitsCtrl   = TextEditingController();
  bool _saving = false;
  String? _savingLabel;

  bool get _isEdit => widget.floor != null;

  @override
  void initState() {
    super.initState();
    if (_isEdit) {
      _floorNumber.text = widget.floor!.floorNumber.toString();
      _floorName.text   = widget.floor!.floorName ?? '';
    }
  }

  @override
  void dispose() {
    _floorNumber.dispose();
    _floorName.dispose();
    _unitsCtrl.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() { _saving = true; _savingLabel = null; });
    try {
      final society = await ref.read(currentSocietyProvider.future);
      if (_isEdit) {
        final data = <String, dynamic>{
          'floor_number': int.parse(_floorNumber.text.trim()),
          'floor_name': _floorName.text.trim().isEmpty
              ? null
              : _floorName.text.trim(),
        };
        await ref
            .read(structureRepoProvider)
            .updateFloor(widget.floor!.id, data);
        ref.read(floorsByWingProvider(widget.wing.id).notifier).refresh();
        // Renumbering a floor moves its flats with it
        ref.read(flatsBySocietyProvider.notifier).refresh();
      } else {
        final floorNumber = int.parse(_floorNumber.text.trim());
        await ref.read(floorsByWingProvider(widget.wing.id).notifier).create(
              floorNumber: floorNumber,
              societyId: society.id,
              floorName: _floorName.text.trim().isEmpty
                  ? null
                  : _floorName.text.trim(),
            );

        final units = int.tryParse(_unitsCtrl.text.trim()) ?? 0;
        if (units > 0) {
          var created = 0;
          try {
            // Numbers the wing already uses are skipped, not collided with
            final existing = (await ref.read(flatsBySocietyProvider.future))
                .where((f) => f.wingId == widget.wing.id)
                .map((f) => f.flatNumber)
                .toSet();
            final numbers = nextFlatNumbers(floorNumber, units, existing);
            for (var i = 0; i < numbers.length; i++) {
              if (mounted) {
                setState(() => _savingLabel = 'Creating flat ${i + 1} of $units…');
              }
              await ref.read(flatsBySocietyProvider.notifier).create(
                    flatNumber: numbers[i],
                    wingId: widget.wing.id,
                    floor: floorNumber,
                  );
              created++;
            }
          } catch (e) {
            // The floor and any flats created before the failure already
            // exist server-side — pop back to the floor list (where the
            // partial flat count is visible) rather than stranding the user
            // on a form for a floor that was, in fact, created.
            ref.read(floorsByWingProvider(widget.wing.id).notifier).refresh();
            if (mounted) {
              Navigator.pop(context);
              ScaffoldMessenger.of(context).showSnackBar(SnackBar(
                content: Text(
                    'Floor created. $created of $units flats created before '
                    'an error: ${friendlyErrorMessage(e)}'),
                backgroundColor: AppTheme.error,
              ));
            }
            return;
          }
          ref.read(floorsByWingProvider(widget.wing.id).notifier).refresh();
        }
      }
      if (mounted) Navigator.pop(context);
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(
            content: Text(friendlyErrorMessage(e)), backgroundColor: AppTheme.error));
      }
    } finally {
      if (mounted) setState(() { _saving = false; _savingLabel = null; });
    }
  }

  @override
  Widget build(BuildContext context) {
    return AppFormPage(
      title: _isEdit ? 'Edit Floor' : 'Add Floor',
      subtitle: widget.wing.displayName,
      formKey: _formKey,
      submitLabel: _isEdit ? 'Save Changes' : 'Add Floor',
      submitIcon: _isEdit ? Icons.save_rounded : Icons.add_rounded,
      saving: _saving,
      onSubmit: _submit,
      footerNote: _savingLabel == null ? null : Text(_savingLabel!),
      children: [
        FormSection(
          title: 'Floor details',
          description: 'Use 0 for the ground floor and a negative number for a basement.',
          children: [
            FormFieldBox(
              label: 'Floor number',
              required: true,
              child: TextFormField(
                controller: _floorNumber,
                keyboardType: const TextInputType.numberWithOptions(signed: true),
                inputFormatters: [FilteringTextInputFormatter.allow(RegExp(r'^-?\d*'))],
                decoration: const InputDecoration(hintText: '0 = Ground, 1, 2, … (negative for basement)'),
                validator: (v) {
                  if (v == null || v.trim().isEmpty) return 'Floor number is required';
                  final n = int.tryParse(v.trim());
                  if (n == null) return 'Must be a number';
                  if (n < -10 || n > 200) return 'Floor must be between -10 and 200';
                  return null;
                },
              ),
            ),
            FormFieldBox(
              label: 'Floor name',
              child: TextFormField(
                controller: _floorName,
                textCapitalization: TextCapitalization.words,
                decoration: const InputDecoration(hintText: 'e.g. Ground Floor, Mezzanine (optional)'),
              ),
            ),
            if (!_isEdit)
              FormFieldBox(
                label: 'Units on this floor',
                helper: 'Optional. Flats are numbered automatically (101, 102, …) and can be renamed from the Flats list.',
                child: TextFormField(
                  controller: _unitsCtrl,
                  keyboardType: TextInputType.number,
                  inputFormatters: [FilteringTextInputFormatter.digitsOnly],
                  decoration: const InputDecoration(hintText: 'e.g. 4 — creates that many flats'),
                  validator: (v) {
                    if (v == null || v.trim().isEmpty) return null;
                    final n = int.tryParse(v.trim());
                    if (n == null || n <= 0) return 'Enter a valid number';
                    if (n > 100) return 'Add up to 100 units at a time';
                    return null;
                  },
                ),
              ),
          ],
        ),
      ],
    );
  }
}
