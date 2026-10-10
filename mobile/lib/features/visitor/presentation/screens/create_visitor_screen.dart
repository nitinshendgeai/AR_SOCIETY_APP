import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/visitor/domain/entities/visitor_entities.dart';
import 'package:ar_society_app/features/visitor/data/repositories/visitor_repository.dart';
import 'package:ar_society_app/features/visitor/presentation/providers/visitor_providers.dart';
import 'package:ar_society_app/features/society_structure/presentation/providers/structure_providers.dart';
import 'package:ar_society_app/shared/widgets/app_form.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/features/resident_master/presentation/providers/resident_master_providers.dart' show myResidentProvider;

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
  void initState() {
    super.initState();
    // A resident expecting a visitor almost always means their own flat
    if (ref.read(currentUserProvider)?.isResident ?? false) _prefillMyFlat();
  }

  Future<void> _prefillMyFlat() async {
    try {
      final resident = await ref.read(myResidentProvider.future);
      if (resident == null) return;
      final flat = await ref.read(flatByIdProvider(resident.flatId).future);
      if (!mounted || _wingId != null) return;
      setState(() {
        _wingId = flat.wingId;
        _flatId = flat.id;
      });
    } catch (_) {
      // Leave the pickers empty; the resident can still choose.
    }
  }

  @override
  void dispose() {
    _nameCtrl.dispose();
    _mobileCtrl.dispose();
    _purposeCtrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AppFormPage(
      title: 'Log Visitor',
      subtitle: 'The resident of the flat is asked to approve entry',
      formKey: _formKey,
      submitLabel: 'Log Visitor',
      submitIcon: Icons.person_add_rounded,
      saving: _isLoading,
      onSubmit: _submit,
      children: [
        FormSection(
          title: 'Visitor',
          description: 'Who is at the gate.',
          children: [
            FormFieldBox(
              label: 'Visitor name',
              required: true,
              child: TextFormField(
                controller: _nameCtrl,
                inputFormatters: [LengthLimitingTextInputFormatter(255)],
                textCapitalization: TextCapitalization.words,
                decoration: const InputDecoration(hintText: 'Full name of the visitor'),
                validator: (v) => (v == null || v.trim().isEmpty) ? 'Name is required' : null,
              ),
            ),
            FormFieldBox(
              label: 'Mobile number',
              required: true,
              child: TextFormField(
                controller: _mobileCtrl,
                keyboardType: TextInputType.phone,
                inputFormatters: [LengthLimitingTextInputFormatter(20)],
                decoration: const InputDecoration(hintText: '+91 9876543210'),
                validator: (v) {
                  final t = (v ?? '').trim();
                  if (t.isEmpty) return 'Mobile is required';
                  final digits = t.replaceAll(RegExp(r'[\s\-()]'), '');
                  return RegExp(r'^\+?\d{7,15}$').hasMatch(digits) ? null : 'Enter a valid mobile number';
                },
              ),
            ),
            FormFieldBox(
              label: 'Visitor type',
              child: DropdownButtonFormField<VisitorType>(
                isExpanded: true,
                value: _type,
                items: VisitorType.values.map((t) => DropdownMenuItem(value: t, child: Text(t.label))).toList(),
                onChanged: (v) => setState(() => _type = v!),
              ),
            ),
            FormFieldBox(
              label: 'Purpose',
              child: TextFormField(
                controller: _purposeCtrl,
                inputFormatters: [LengthLimitingTextInputFormatter(500)],
                decoration: const InputDecoration(hintText: 'e.g. Meeting, delivery, repair work (optional)'),
              ),
            ),
          ],
        ),
        FormSection(
          title: 'Visiting',
          description: 'The flat being visited. Its resident approves or refuses entry.',
          children: [
            FormFieldBox(
              label: 'Wing',
              required: true,
              child: ref.watch(wingsProvider).when(
                    loading: () => const LinearProgressIndicator(minHeight: 2),
                    error: (_, __) => const Text('Could not load wings', style: TextStyle(color: AppTheme.error)),
                    data: (wings) => DropdownButtonFormField<String>(
                isExpanded: true,
                      value: _wingId,
                      hint: const Text('Select wing'),
                      items: wings.map((w) => DropdownMenuItem(value: w.id, child: Text(w.displayName))).toList(),
                      onChanged: (v) => setState(() {
                        _wingId = v;
                        _flatId = null;
                      }),
                      validator: (v) => v == null ? 'Wing is required' : null,
                    ),
                  ),
            ),
            FormFieldBox(
              label: 'Flat number',
              required: true,
              child: _wingId == null
                  ? DropdownButtonFormField<String>(
                isExpanded: true,
                      hint: const Text('Select a wing first'),
                      items: const [],
                      onChanged: null,
                      validator: (_) => 'Flat is required',
                    )
                  : ref.watch(flatsByWingProvider(_wingId!)).when(
                        loading: () => const LinearProgressIndicator(minHeight: 2),
                        error: (_, __) => const Text('Could not load flats', style: TextStyle(color: AppTheme.error)),
                        data: (flats) => DropdownButtonFormField<String>(
                isExpanded: true,
                          key: ValueKey(_wingId),
                          value: _flatId,
                          hint: Text(flats.isEmpty ? 'No flats in this wing' : 'Select flat'),
                          items: flats.map((f) => DropdownMenuItem(value: f.id, child: Text(f.flatNumber))).toList(),
                          onChanged: (v) => setState(() => _flatId = v),
                          validator: (v) => v == null ? 'Flat is required' : null,
                        ),
                      ),
            ),
          ],
        ),
      ],
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
