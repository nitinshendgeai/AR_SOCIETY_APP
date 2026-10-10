import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/users/presentation/providers/user_providers.dart';
import 'package:ar_society_app/features/users/presentation/widgets/temp_password_dialog.dart';
import 'package:ar_society_app/shared/widgets/app_form.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart' show AppErrorBanner;

class CreateUserScreen extends ConsumerStatefulWidget {
  const CreateUserScreen({super.key});

  @override
  ConsumerState<CreateUserScreen> createState() => _CreateUserScreenState();
}

class _CreateUserScreenState extends ConsumerState<CreateUserScreen> {
  final _formKey    = GlobalKey<FormState>();
  final _emailCtrl  = TextEditingController();
  final _nameCtrl   = TextEditingController();
  final _phoneCtrl  = TextEditingController();
  String? _selectedRole;
  bool _loading = false;
  String? _error;

  @override
  void dispose() {
    _emailCtrl.dispose();
    _nameCtrl.dispose();
    _phoneCtrl.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() { _loading = true; _error = null; });

    try {
      final created = await ref.read(userAdminRepoProvider).createUser(
        email: _emailCtrl.text.trim().toLowerCase(),
        fullName: _nameCtrl.text.trim(),
        phone: _phoneCtrl.text.trim().isEmpty ? null : _phoneCtrl.text.trim(),
        roleName: _selectedRole,
      );
      if (mounted) {
        // The new user has no way in without this: show it before leaving
        await showTempPasswordDialog(context, created.temporaryPassword, who: created.user.fullName);
      }
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('User created successfully')),
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
    final rolesAsync = ref.watch(rolesListProvider);

    return AppFormPage(
      title: 'Create User',
      subtitle: 'Add a login for a person in the society',
      formKey: _formKey,
      submitLabel: 'Create User',
      submitIcon: Icons.person_add_alt_1_rounded,
      saving: _loading,
      onSubmit: _submit,
      children: [
        if (_error != null) AppErrorBanner(message: _error!, onDismiss: () => setState(() => _error = null)),
        FormSection(
          title: 'Account',
          description: 'A temporary password is generated. The person must change it the first time they sign in.',
          children: [
            FormFieldBox(
              label: 'Full name',
              required: true,
              child: TextFormField(
                controller: _nameCtrl,
                decoration: const InputDecoration(hintText: 'e.g. Rahul Sharma'),
                validator: (v) => (v == null || v.trim().isEmpty) ? 'Required' : null,
              ),
            ),
            FormFieldBox(
              label: 'Email address',
              required: true,
              child: TextFormField(
                controller: _emailCtrl,
                keyboardType: TextInputType.emailAddress,
                decoration: const InputDecoration(hintText: 'user@example.com'),
                validator: (v) {
                  if (v == null || v.trim().isEmpty) return 'Required';
                  if (!RegExp(r'^[^@\s]+@[^@\s]+\.[^@\s]+$').hasMatch(v.trim())) return 'Enter a valid email';
                  return null;
                },
              ),
            ),
            FormFieldBox(
              label: 'Phone',
              child: TextFormField(
                controller: _phoneCtrl,
                keyboardType: TextInputType.phone,
                decoration: const InputDecoration(hintText: '+91 9876543210 (optional)'),
                validator: (v) {
                  final t = (v ?? '').replaceAll(RegExp(r'[ \-()]'), '');
                  if (t.isEmpty) return null;
                  return RegExp(r'^\+?[0-9]{7,15}$').hasMatch(t) ? null : 'Enter a valid phone number';
                },
              ),
            ),
            FormFieldBox(
              label: 'Role',
              helper: 'Optional. The role decides which screens the person sees.',
              child: rolesAsync.when(
                loading: () => const LinearProgressIndicator(),
                error: (_, __) => const Text('Could not load roles', style: TextStyle(color: AppTheme.error, fontSize: 12)),
                data: (roles) => DropdownButtonFormField<String?>(
                isExpanded: true,
                  value: _selectedRole,
                  decoration: const InputDecoration(hintText: 'Select a role'),
                  items: [
                    const DropdownMenuItem<String?>(value: null, child: Text('No role')),
                    ...roles.map((r) => DropdownMenuItem<String>(value: r.name, child: Text(r.name))),
                  ],
                  onChanged: (v) => setState(() => _selectedRole = v),
                ),
              ),
            ),
          ],
        ),
      ],
    );
  }
}
