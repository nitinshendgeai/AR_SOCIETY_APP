import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/complaint/domain/entities/complaint_entities.dart';
import 'package:ar_society_app/features/complaint/presentation/providers/complaint_providers.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';

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
    return Scaffold(
      backgroundColor: AppTheme.surface,
      appBar: AppBar(title: const Text('New Complaint')),
      body: AppLoadingOverlay(
        isLoading: _isLoading,
        child: Form(
          key: _formKey,
          child: ListView(
            padding: const EdgeInsets.all(20),
            children: [
              if (_errorMessage != null) ...[
                AppErrorBanner(
                  message: _errorMessage!,
                  onDismiss: () => setState(() => _errorMessage = null),
                ),
                const SizedBox(height: 14),
              ],

              // Title
              AppTextField(
                label: 'Title *',
                hint: 'Brief description of the issue',
                controller: _titleCtrl,
                validator: (v) =>
                    (v == null || v.trim().isEmpty) ? 'Title is required' : null,
              ),
              const SizedBox(height: 14),

              // Description
              TextFormField(
                controller: _descCtrl,
                maxLines: 4,
                validator: (v) => (v == null || v.trim().isEmpty)
                    ? 'Description is required'
                    : null,
                decoration: const InputDecoration(
                  labelText: 'Description *',
                  hintText: 'Describe the issue in detail...',
                  alignLabelWithHint: true,
                ),
              ),
              const SizedBox(height: 14),

              // Category
              DropdownButtonFormField<ComplaintCategory>(
                value: _selectedCategory,
                decoration: const InputDecoration(labelText: 'Category *'),
                hint: const Text('Select a category'),
                items: ComplaintCategory.values
                    .map(
                      (c) => DropdownMenuItem(value: c, child: Text(c.label)),
                    )
                    .toList(),
                onChanged: (v) => setState(() {
                  _selectedCategory = v;
                  _errorMessage = null;
                }),
                validator: (v) =>
                    v == null ? 'Category is required' : null,
              ),
              const SizedBox(height: 14),

              // Priority
              DropdownButtonFormField<ComplaintPriority>(
                value: _selectedPriority,
                decoration: const InputDecoration(labelText: 'Priority'),
                items: ComplaintPriority.values
                    .map(
                      (p) => DropdownMenuItem(
                        value: p,
                        child: Row(
                          children: [
                            Container(
                              width: 10,
                              height: 10,
                              decoration: BoxDecoration(
                                color: p.color,
                                shape: BoxShape.circle,
                              ),
                            ),
                            const SizedBox(width: 8),
                            Text(p.label),
                          ],
                        ),
                      ),
                    )
                    .toList(),
                onChanged: (v) {
                  if (v != null) setState(() => _selectedPriority = v);
                },
              ),
              const SizedBox(height: 32),

              AppPrimaryButton(
                label: 'Submit Complaint',
                icon: Icons.send_rounded,
                isLoading: _isLoading,
                onPressed: _isLoading ? null : _submit,
              ),
            ],
          ),
        ),
      ),
    );
  }
}
