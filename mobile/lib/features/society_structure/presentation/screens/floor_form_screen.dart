import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/society_settings/presentation/providers/society_settings_providers.dart';
import 'package:ar_society_app/features/society_structure/data/models/structure_models.dart';
import 'package:ar_society_app/features/society_structure/presentation/providers/structure_providers.dart';

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
  bool _saving = false;

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
    super.dispose();
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() => _saving = true);
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
        await ref.read(floorsByWingProvider(widget.wing.id).notifier).create(
              floorNumber: int.parse(_floorNumber.text.trim()),
              societyId: society.id,
              floorName: _floorName.text.trim().isEmpty
                  ? null
                  : _floorName.text.trim(),
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
    return Scaffold(
      backgroundColor: AppTheme.surface,
      appBar: AppBar(
        title: Text(_isEdit ? 'Edit Floor' : 'Add Floor'),
        subtitle: Text(widget.wing.name,
            style: const TextStyle(
                fontSize: 12, color: AppTheme.textSecondary)),
      ),
      body: Form(
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
                    : Text(_isEdit ? 'Save Changes' : 'Add Floor'),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
