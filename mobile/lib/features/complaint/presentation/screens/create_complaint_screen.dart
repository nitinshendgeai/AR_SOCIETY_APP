import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/features/complaint/domain/entities/complaint_entities.dart';
import 'package:ar_society_app/features/complaint/data/repositories/complaint_repository.dart';
import 'package:ar_society_app/features/complaint/presentation/providers/complaint_providers.dart';
import 'package:ar_society_app/features/resident_master/presentation/providers/resident_master_providers.dart';
import 'package:ar_society_app/features/society_structure/presentation/providers/structure_providers.dart';
import 'package:ar_society_app/shared/widgets/app_form.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart' show AppErrorBanner;

class CreateComplaintScreen extends ConsumerStatefulWidget {
  final String societyId;

  const CreateComplaintScreen({super.key, required this.societyId});

  @override
  ConsumerState<CreateComplaintScreen> createState() =>
      _CreateComplaintScreenState();
}

class _CreateComplaintScreenState
    extends ConsumerState<CreateComplaintScreen> {
  final _formKey = GlobalKey<FormState>();
  final _titleCtrl = TextEditingController();
  final _descCtrl = TextEditingController();

  ComplaintCategory? _selectedCategory;
  ComplaintPriority _selectedPriority = ComplaintPriority.medium;
  String? _selectedWingId;
  String? _selectedFlatId;
  bool _isLoading = false;
  String? _errorMessage;

  @override
  void dispose() {
    _titleCtrl.dispose();
    _descCtrl.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    if (_selectedCategory == null) {
      setState(() => _errorMessage = 'Please select a category');
      return;
    }

    // Residents/tenants file against their own flat only — the backend
    // enforces this regardless (never trusts a client-supplied flat_id for
    // these roles), but resolving it here too keeps the UI consistent and
    // lets us block submission with a clear message if no flat is linked.
    final currentUser = ref.read(currentUserProvider);
    String? flatId = _selectedFlatId;
    if (currentUser?.isResident ?? false) {
      final resident = ref.read(myResidentProvider).valueOrNull;
      if (resident == null) {
        setState(() => _errorMessage =
            'No flat is linked to your account yet — contact your society admin.');
        return;
      }
      flatId = resident.flatId;
    }

    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });

    final data = {
      'title': _titleCtrl.text.trim(),
      'description': _descCtrl.text.trim(),
      'category': _selectedCategory!.name,
      'priority': _selectedPriority.name,
      'society_id': widget.societyId,
      if (flatId != null) 'flat_id': flatId,
    };

    final result =
        await ref.read(complaintRepositoryProvider).createComplaint(data);

    if (!mounted) return;

    switch (result) {
      case ComplaintSuccess():
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Complaint raised successfully'),
            backgroundColor: AppTheme.success,
            behavior: SnackBarBehavior.floating,
          ),
        );
        Navigator.of(context).pop(true);
      case ComplaintFailure(:final message):
        setState(() {
          _isLoading = false;
          _errorMessage = message;
        });
    }
  }

  @override
  Widget build(BuildContext context) {
    final isResident = ref.watch(currentUserProvider)?.isResident ?? false;
    final wingsAsync = ref.watch(wingsProvider);

    return AppFormPage(
      title: 'New Complaint',
      subtitle: 'Tell the society office what needs attention',
      formKey: _formKey,
      submitLabel: 'Submit Complaint',
      submitIcon: Icons.send_rounded,
      saving: _isLoading,
      onSubmit: _isLoading ? null : _submit,
      children: [
        if (_errorMessage != null)
          AppErrorBanner(message: _errorMessage!, onDismiss: () => setState(() => _errorMessage = null)),
        FormSection(
          title: 'The problem',
          description: 'A short title and what is wrong, so the right person can act on it.',
          columns: 1,
          children: [
            FormFieldBox(
              label: 'Title',
              required: true,
              child: TextFormField(
                controller: _titleCtrl,
                inputFormatters: [LengthLimitingTextInputFormatter(255)],
                decoration: const InputDecoration(hintText: 'Brief description of the issue'),
                validator: (v) => (v == null || v.trim().isEmpty) ? 'Title is required' : null,
              ),
            ),
            FormFieldBox(
              label: 'Description',
              required: true,
              child: TextFormField(
                controller: _descCtrl,
                maxLines: 5,
                inputFormatters: [LengthLimitingTextInputFormatter(5000)],
                validator: (v) => (v == null || v.trim().isEmpty) ? 'Description is required' : null,
                decoration: const InputDecoration(hintText: 'Describe the issue in detail…'),
              ),
            ),
          ],
        ),
        FormSection(
          title: 'Category and place',
          description: 'What kind of problem, how urgent, and where.',
          children: [
            FormFieldBox(
              label: 'Category',
              required: true,
              child: DropdownButtonFormField<ComplaintCategory>(
                isExpanded: true,
                value: _selectedCategory,
                hint: const Text('Select a category'),
                items: ComplaintCategory.values.map((c) => DropdownMenuItem(value: c, child: Text(c.label))).toList(),
                onChanged: (v) => setState(() {
                  _selectedCategory = v;
                  _errorMessage = null;
                }),
                validator: (v) => v == null ? 'Category is required' : null,
              ),
            ),
            FormFieldBox(
              label: 'Priority',
              child: DropdownButtonFormField<ComplaintPriority>(
                isExpanded: true,
                value: _selectedPriority,
                items: ComplaintPriority.values
                    .map((p) => DropdownMenuItem(
                          value: p,
                          child: Row(children: [
                            Container(width: 10, height: 10, decoration: BoxDecoration(color: p.color, shape: BoxShape.circle)),
                            const SizedBox(width: 8),
                            Text(p.label),
                          ]),
                        ))
                    .toList(),
                onChanged: (v) {
                  if (v != null) setState(() => _selectedPriority = v);
                },
              ),
            ),
            // Residents file against their own flat only — shown read-only, not a picker. Everyone else
            // (Admin/Committee/Manager/Staff) keeps the free Wing/Flat picker for filing on someone's behalf or
            // a society-wide/common-area issue.
            if (isResident)
              FormFieldBox(
                label: 'Flat',
                child: Consumer(builder: (context, ref, _) {
                  final residentAsync = ref.watch(myResidentProvider);
                  return residentAsync.when(
                    loading: () => const LinearProgressIndicator(minHeight: 2),
                    error: (_, __) => const SizedBox.shrink(),
                    data: (resident) {
                      if (resident == null) {
                        return const Text(
                          'No flat is linked to your account yet — contact your society admin.',
                          style: TextStyle(color: AppTheme.error, fontSize: 12),
                        );
                      }
                      final flatAsync = ref.watch(flatByIdProvider(resident.flatId));
                      return InputDecorator(
                        decoration: const InputDecoration(),
                        child: flatAsync.when(
                          loading: () => const Text('Loading...'),
                          error: (_, __) => Text(resident.flatId),
                          data: (flat) => Text('${flat.wingName ?? ''} / ${flat.flatNumber}'.trim(),
                              style: const TextStyle(fontWeight: FontWeight.w600)),
                        ),
                      );
                    },
                  );
                }),
              )
            else ...[
              FormFieldBox(
                label: 'Wing',
                helper: 'Leave blank for a society-wide issue',
                child: wingsAsync.when(
                  loading: () => const LinearProgressIndicator(minHeight: 2),
                  error: (_, __) => const SizedBox.shrink(),
                  data: (wings) => DropdownButtonFormField<String>(
                isExpanded: true,
                    value: _selectedWingId,
                    hint: const Text('Select wing (optional)'),
                    items: wings.map((w) => DropdownMenuItem(value: w.id, child: Text(w.displayName))).toList(),
                    onChanged: (v) => setState(() {
                      _selectedWingId = v;
                      _selectedFlatId = null;
                    }),
                  ),
                ),
              ),
              if (_selectedWingId != null)
                FormFieldBox(
                  label: 'Flat number',
                  child: Consumer(builder: (context, ref, _) {
                    final flatsAsync = ref.watch(flatsByWingProvider(_selectedWingId!));
                    return flatsAsync.when(
                      loading: () => const LinearProgressIndicator(minHeight: 2),
                      error: (_, __) => const SizedBox.shrink(),
                      data: (flats) => DropdownButtonFormField<String>(
                isExpanded: true,
                        value: _selectedFlatId,
                        hint: const Text('Select flat number'),
                        items: flats.map((f) => DropdownMenuItem(value: f.id, child: Text(f.flatNumber))).toList(),
                        onChanged: (v) => setState(() => _selectedFlatId = v),
                      ),
                    );
                  }),
                ),
            ],
          ],
        ),
      ],
    );
  }
}
