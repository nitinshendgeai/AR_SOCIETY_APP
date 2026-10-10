import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/features/users/data/models/user_admin_models.dart';
import 'package:ar_society_app/features/users/presentation/providers/user_providers.dart';
import 'package:ar_society_app/shared/widgets/app_form.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart' show AppErrorBanner;

class EditUserScreen extends ConsumerStatefulWidget {
  final AdminUserModel user;
  const EditUserScreen({super.key, required this.user});

  @override
  ConsumerState<EditUserScreen> createState() => _EditUserScreenState();
}

class _EditUserScreenState extends ConsumerState<EditUserScreen> {
  final _formKey   = GlobalKey<FormState>();
  late final TextEditingController _nameCtrl;
  late final TextEditingController _phoneCtrl;
  String? _status;
  bool _loading = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _nameCtrl  = TextEditingController(text: widget.user.fullName);
    _phoneCtrl = TextEditingController(text: widget.user.phone ?? '');
    _status    = widget.user.status;
  }

  @override
  void dispose() {
    _nameCtrl.dispose();
    _phoneCtrl.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() { _loading = true; _error = null; });

    final data = <String, dynamic>{};
    if (_nameCtrl.text.trim() != widget.user.fullName) {
      data['full_name'] = _nameCtrl.text.trim();
    }
    final phone = _phoneCtrl.text.trim();
    if (phone != (widget.user.phone ?? '')) {
      data['phone'] = phone.isEmpty ? null : phone;
    }
    if (_status != widget.user.status) {
      data['status'] = _status;
    }

    if (data.isEmpty) {
      context.pop(false);
      return;
    }

    try {
      await ref.read(userAdminRepoProvider).updateUser(widget.user.id, data);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('User updated')),
        );
        context.pop(true);
      }
    } catch (e) {
      setState(() => _error = friendlyErrorMessage(e));
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return AppFormPage(
      title: 'Edit User',
      subtitle: widget.user.email,
      formKey: _formKey,
      submitLabel: 'Save Changes',
      submitIcon: Icons.save_rounded,
      saving: _loading,
      onSubmit: _submit,
      children: [
        if (_error != null) AppErrorBanner(message: _error!, onDismiss: () => setState(() => _error = null)),
        FormSection(
          title: 'Account',
          description: 'A suspended or inactive user cannot sign in.',
          children: [
            FormFieldBox(
              label: 'Full name',
              required: true,
              child: TextFormField(
                controller: _nameCtrl,
                validator: (v) => (v == null || v.trim().isEmpty) ? 'Required' : null,
                decoration: const InputDecoration(hintText: 'e.g. Rahul Sharma'),
              ),
            ),
            FormFieldBox(
              label: 'Phone',
              child: TextFormField(
                controller: _phoneCtrl,
                keyboardType: TextInputType.phone,
                decoration: const InputDecoration(hintText: '+91 9876543210 (optional)'),
              ),
            ),
            FormFieldBox(
              label: 'Status',
              child: DropdownButtonFormField<String>(
                isExpanded: true,
                value: _status,
                items: ['active', 'inactive', 'suspended']
                    .map((s) => DropdownMenuItem(value: s, child: Text(s)))
                    .toList(),
                onChanged: (v) => setState(() => _status = v),
              ),
            ),
          ],
        ),
      ],
    );
  }
}
