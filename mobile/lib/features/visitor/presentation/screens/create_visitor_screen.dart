import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/visitor/domain/entities/visitor_entities.dart';
import 'package:ar_society_app/features/visitor/data/repositories/visitor_repository.dart';
import 'package:ar_society_app/features/visitor/presentation/providers/visitor_providers.dart';
import 'package:ar_society_app/features/society_structure/presentation/providers/structure_providers.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';

class CreateVisitorScreen extends ConsumerStatefulWidget {
  final String societyId;
  const CreateVisitorScreen({super.key, required this.societyId});

  @override
  ConsumerState<CreateVisitorScreen> createState() => _CreateVisitorScreenState();
}

class _CreateVisitorScreenState extends ConsumerState<CreateVisitorScreen> {
  final _formKey     = GlobalKey<FormState>();
  final _nameCtrl    = TextEditingController();
  final _mobileCtrl  = TextEditingController();
  final _purposeCtrl = TextEditingController();
  VisitorType _type  = VisitorType.guest;
  String? _wingId;
  String? _flatId;
  bool _isLoading    = false;

  @override
  void dispose() {
    _nameCtrl.dispose();
    _mobileCtrl.dispose();
    _purposeCtrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppTheme.surface,
      appBar: AppBar(title: const Text('Log Visitor')),
      body: Form(
        key: _formKey,
        child: ListView(
          padding: const EdgeInsets.all(20),
          children: [
            AppTextField(
              label: 'Visitor Name *',
              hint: 'Full name of the visitor',
              controller: _nameCtrl,
              validator: (v) =>
                  (v == null || v.trim().isEmpty) ? 'Name is required' : null,
            ),
            const SizedBox(height: 14),
            AppTextField(
              label: 'Mobile Number *',
              hint: '+91 9876543210',
              controller: _mobileCtrl,
              keyboardType: TextInputType.phone,
              validator: (v) =>
                  (v == null || v.trim().isEmpty) ? 'Mobile is required' : null,
            ),
            const SizedBox(height: 14),
            // The flat being visited: its resident is asked to approve entry.
            ref.watch(wingsProvider).when(
                  loading: () => const LinearProgressIndicator(minHeight: 2),
                  error: (_, __) => const Text('Could not load wings',
                      style: TextStyle(color: AppTheme.error)),
                  data: (wings) => DropdownButtonFormField<String>(
                    value: _wingId,
                    decoration: const InputDecoration(labelText: 'Wing *'),
                    hint: const Text('Select wing'),
                    items: wings
                        .map((w) => DropdownMenuItem(value: w.id, child: Text(w.displayName)))
                        .toList(),
                    onChanged: (v) => setState(() {
                      _wingId = v;
                      _flatId = null;
                    }),
                    validator: (v) => v == null ? 'Wing is required' : null,
                  ),
                ),
            const SizedBox(height: 14),
            if (_wingId == null)
              DropdownButtonFormField<String>(
                decoration: const InputDecoration(labelText: 'Flat Number *'),
                hint: const Text('Select a wing first'),
                items: const [],
                onChanged: null,
                validator: (_) => 'Flat is required',
              )
            else
              ref.watch(flatsByWingProvider(_wingId!)).when(
                    loading: () => const LinearProgressIndicator(minHeight: 2),
                    error: (_, __) => const Text('Could not load flats',
                        style: TextStyle(color: AppTheme.error)),
                    data: (flats) => DropdownButtonFormField<String>(
                      key: ValueKey(_wingId),
                      value: _flatId,
                      decoration: const InputDecoration(labelText: 'Flat Number *'),
                      hint: Text(flats.isEmpty ? 'No flats in this wing' : 'Select flat'),
                      items: flats
                          .map((f) => DropdownMenuItem(value: f.id, child: Text(f.flatNumber)))
                          .toList(),
                      onChanged: (v) => setState(() => _flatId = v),
                      validator: (v) => v == null ? 'Flat is required' : null,
                    ),
                  ),
            const SizedBox(height: 14),
            DropdownButtonFormField<VisitorType>(
              value: _type,
              decoration: const InputDecoration(labelText: 'Visitor Type'),
              items: VisitorType.values
                  .map((t) => DropdownMenuItem(value: t, child: Text(t.label)))
                  .toList(),
              onChanged: (v) => setState(() => _type = v!),
            ),
            const SizedBox(height: 14),
            AppTextField(
              label: 'Purpose (optional)',
              hint: 'e.g., Meeting, delivery, repair work',
              controller: _purposeCtrl,
            ),
            const SizedBox(height: 32),
            AppPrimaryButton(
              label: 'Log Visitor',
              isLoading: _isLoading,
              icon: Icons.person_add_rounded,
              onPressed: _submit,
            ),
          ],
        ),
      ),
    );
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() => _isLoading = true);

    final result = await ref.read(visitorRepositoryProvider).createVisitor({
      'name': _nameCtrl.text.trim(),
      'mobile': _mobileCtrl.text.trim(),
      'visitor_type': _type.name,
      'society_id': widget.societyId,
      'flat_id': _flatId,
      if (_purposeCtrl.text.trim().isNotEmpty) 'purpose': _purposeCtrl.text.trim(),
    });

    setState(() => _isLoading = false);

    if (!mounted) return;

    switch (result) {
      case VisitorSuccess():
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
          content: Text('Visitor logged successfully'),
          backgroundColor: AppTheme.success,
          behavior: SnackBarBehavior.floating,
        ));
        Navigator.pop(context, true);
      case VisitorFailure(:final message):
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(
          content: Text(message),
          backgroundColor: AppTheme.error,
          behavior: SnackBarBehavior.floating,
        ));
    }
  }
}
