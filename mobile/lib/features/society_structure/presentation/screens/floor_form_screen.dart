import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/society_settings/presentation/providers/society_settings_providers.dart';
import 'package:ar_society_app/features/society_structure/data/models/structure_models.dart';
import 'package:ar_society_app/features/society_structure/domain/flat_numbering.dart';
import 'package:ar_society_app/features/society_structure/presentation/providers/structure_providers.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';

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
            for (var i = 1; i <= units; i++) {
              if (mounted) {
                setState(() => _savingLabel = 'Creating flat $i of $units…');
              }
              await ref.read(flatsBySocietyProvider.notifier).create(
                    flatNumber: autoFlatNumber(floorNumber, i),
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
    return Scaffold(
      backgroundColor: AppTheme.surface,
      appBar: AppBar(
        title: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(_isEdit ? 'Edit Floor' : 'Add Floor'),
            Text(
              widget.wing.name,
              style: Theme.of(context).textTheme.bodySmall,
            ),
          ],
        ),
      ),
      body: ResponsiveBody(child: Form(
        key: _formKey,
        child: ListView(
          padding: const EdgeInsets.all(20),
          children: [
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: AppTheme.primary.withOpacity(0.06),
                borderRadius: BorderRadius.circular(10),
                border: Border.all(color: AppTheme.primary.withOpacity(0.15)),
              ),
              child: Row(children: [
                Icon(Icons.apartment_rounded,
                    size: 16, color: AppTheme.primary),
                const SizedBox(width: 8),
                Text('Wing: ${widget.wing.displayName}',
                    style: const TextStyle(
                        fontSize: 13, color: AppTheme.textPrimary)),
              ]),
            ),
            const SizedBox(height: 20),
            TextFormField(
              controller: _floorNumber,
              keyboardType: TextInputType.numberWithOptions(signed: true),
              inputFormatters: [
                FilteringTextInputFormatter.allow(RegExp(r'^-?\d*')),
              ],
              decoration: const InputDecoration(
                labelText: 'Floor Number *',
                hintText: '0 = Ground, 1, 2, ... (negative for basement)',
              ),
              validator: (v) {
                if (v == null || v.trim().isEmpty) return 'Floor number is required';
                if (int.tryParse(v.trim()) == null) return 'Must be a number';
                return null;
              },
            ),
            const SizedBox(height: 16),
            TextFormField(
              controller: _floorName,
              textCapitalization: TextCapitalization.words,
              decoration: const InputDecoration(
                labelText: 'Floor Name',
                hintText: 'e.g. Ground Floor, Mezzanine (optional)',
              ),
            ),
            if (!_isEdit) ...[
              const SizedBox(height: 16),
              TextFormField(
                controller: _unitsCtrl,
                keyboardType: TextInputType.number,
                inputFormatters: [FilteringTextInputFormatter.digitsOnly],
                decoration: const InputDecoration(
                  labelText: 'Units on this Floor',
                  hintText: 'e.g. 4 (optional — auto-creates that many flats)',
                ),
                validator: (v) {
                  if (v == null || v.trim().isEmpty) return null;
                  final n = int.tryParse(v.trim());
                  if (n == null || n <= 0) return 'Enter a valid number';
                  if (n > 100) return 'Add up to 100 units at a time';
                  return null;
                },
              ),
              const SizedBox(height: 6),
              const Text(
                'Flats will be auto-numbered (e.g. 101, 102, …) and can be '
                'renamed individually afterwards from the Flats list.',
                style: TextStyle(fontSize: 12, color: AppTheme.textSecondary),
              ),
            ],
            const SizedBox(height: 32),
            if (_savingLabel != null) ...[
              Text(_savingLabel!,
                  textAlign: TextAlign.center,
                  style: const TextStyle(
                      fontSize: 12, color: AppTheme.textSecondary)),
              const SizedBox(height: 10),
            ],
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
                    : Text(_isEdit ? 'Save Changes' : 'Add Floor'),
              ),
            ),
          ],
        ),
      )),
    );
  }
}
