import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/society_structure/data/models/structure_models.dart';
import 'package:ar_society_app/features/society_structure/presentation/providers/structure_providers.dart';

class WingFormScreen extends ConsumerStatefulWidget {
  final WingModel? wing;
  const WingFormScreen({super.key, this.wing});

  @override
  ConsumerState<WingFormScreen> createState() => _WingFormScreenState();
}

class _WingFormScreenState extends ConsumerState<WingFormScreen> {
  final _formKey   = GlobalKey<FormState>();
  final _name      = TextEditingController();
  final _code      = TextEditingController();
  final _desc      = TextEditingController();
  final _floors    = TextEditingController();
  bool _saving = false;

  bool get _isEdit => widget.wing != null;

  @override
  void initState() {
    super.initState();
    if (_isEdit) {
      _name.text   = widget.wing!.name;
      _code.text   = widget.wing!.code ?? '';
      _desc.text   = widget.wing!.description ?? '';
      _floors.text = widget.wing!.totalFloors?.toString() ?? '';
    }
  }

  @override
  void dispose() {
    _name.dispose();
    _code.dispose();
    _desc.dispose();
    _floors.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() => _saving = true);
    try {
      if (_isEdit) {
        final data = <String, dynamic>{
          'name': _name.text.trim(),
          if (_code.text.isNotEmpty) 'code': _code.text.trim().toUpperCase(),
          'description': _desc.text.trim().isEmpty ? null : _desc.text.trim(),
          if (_floors.text.isNotEmpty)
            'total_floors': int.parse(_floors.text.trim()),
        };
        await ref.read(wingsProvider.notifier).update(widget.wing!.id, data);
      } else {
        await ref.read(wingsProvider.notifier).create(
          name: _name.text.trim(),
          code: _code.text.trim().isEmpty
              ? null
              : _code.text.trim().toUpperCase(),
          description: _desc.text.trim().isEmpty ? null : _desc.text.trim(),
          totalFloors: _floors.text.trim().isEmpty
              ? null
              : int.parse(_floors.text.trim()),
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
      appBar: AppBar(title: Text(_isEdit ? 'Edit Wing' : 'Add Wing')),
      body: Form(
        key: _formKey,
        child: ListView(
          padding: const EdgeInsets.all(20),
          children: [
            TextFormField(
              controller: _name,
              textCapitalization: TextCapitalization.words,
              decoration: const InputDecoration(
                labelText: 'Wing Name *',
                hintText: 'e.g. A Block, Tower 1',
              ),
              validator: (v) =>
                  v == null || v.trim().isEmpty ? 'Name is required' : null,
            ),
            const SizedBox(height: 16),
            TextFormField(
              controller: _code,
              textCapitalization: TextCapitalization.characters,
              decoration: const InputDecoration(
                labelText: 'Wing Code',
                hintText: 'e.g. A, T1 (optional)',
              ),
            ),
            const SizedBox(height: 16),
            TextFormField(
              controller: _desc,
              maxLines: 2,
              decoration: const InputDecoration(
                labelText: 'Description',
                hintText: 'Optional note about this wing',
                alignLabelWithHint: true,
              ),
            ),
            const SizedBox(height: 16),
            TextFormField(
              controller: _floors,
              keyboardType: TextInputType.number,
              inputFormatters: [FilteringTextInputFormatter.digitsOnly],
              decoration: const InputDecoration(
                labelText: 'Total Floors',
                hintText: 'e.g. 10 (optional)',
              ),
              validator: (v) {
                if (v == null || v.trim().isEmpty) return null;
                final n = int.tryParse(v.trim());
                if (n == null || n <= 0) return 'Enter a valid number';
                return null;
              },
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
                    : Text(_isEdit ? 'Save Changes' : 'Add Wing'),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
