import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/auth/biometric_preference.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/auth/data/repositories/auth_repository.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/shared/widgets/app_form.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';
import 'package:ar_society_app/shared/widgets/auth_page.dart';

class ChangePasswordScreen extends ConsumerStatefulWidget {
  const ChangePasswordScreen({super.key});

  @override
  ConsumerState<ChangePasswordScreen> createState() => _ChangePasswordScreenState();
}

class _ChangePasswordScreenState extends ConsumerState<ChangePasswordScreen> {
  final _formKey = GlobalKey<FormState>();
  final _currentCtrl = TextEditingController();
  final _newCtrl     = TextEditingController();
  final _confirmCtrl = TextEditingController();
  bool _loading = false;
  String? _error;

  @override
  void dispose() {
    _currentCtrl.dispose();
    _newCtrl.dispose();
    _confirmCtrl.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() { _loading = true; _error = null; });

    final result = await ref.read(authProvider.notifier).changePassword(
      currentPassword: _currentCtrl.text.trim(),
      newPassword: _newCtrl.text.trim(),
    );

    if (!mounted) return;
    setState(() => _loading = false);

    if (result is AuthFailure) {
      setState(() => _error = result.message);
      return;
    }
    // On success, router redirect will navigate away (mustChangePassword =
    // false). Flag a one-time biometric-unlock offer for whichever screen
    // the user lands on next (see BiometricEnrollTrigger in role_dashboards
    // .dart) — this is the one guaranteed moment every auto-provisioned
    // resident/tenant account passes through.
    await BiometricPreference.setPromptPending(true);
  }

  @override
  Widget build(BuildContext context) {
    return AuthPage(
      title: 'Set a new password',
      subtitle: 'You must set a new password before continuing.',
      child: Form(
        key: _formKey,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            _PasswordField(
              controller: _currentCtrl,
              label: 'Current password',
              validator: (v) => (v == null || v.isEmpty) ? 'Required' : null,
            ),
            const SizedBox(height: 16),
            _PasswordField(
              controller: _newCtrl,
              label: 'New password',
              validator: (v) {
                if (v == null || v.isEmpty) return 'Required';
                if (v.length < 8) return 'At least 8 characters';
                return null;
              },
            ),
            const SizedBox(height: 16),
            _PasswordField(
              controller: _confirmCtrl,
              label: 'Confirm new password',
              validator: (v) {
                if (v != _newCtrl.text) return 'Passwords do not match';
                return null;
              },
            ),
            if (_error != null) ...[
              const SizedBox(height: 16),
              AppErrorBanner(message: _error!),
            ],
            const SizedBox(height: 24),
            AppPrimaryButton(label: 'Update Password', isLoading: _loading, onPressed: _submit),
            const SizedBox(height: 8),
            TextButton(
              onPressed: _loading ? null : () => ref.read(authProvider.notifier).logout(),
              child: const Text('Sign out', style: TextStyle(color: AppTheme.textSecondary)),
            ),
          ],
        ),
      ),
    );
  }
}

class _PasswordField extends StatefulWidget {
  final TextEditingController controller;
  final String label;
  final String? Function(String?)? validator;

  const _PasswordField({
    required this.controller,
    required this.label,
    this.validator,
  });

  @override
  State<_PasswordField> createState() => _PasswordFieldState();
}

class _PasswordFieldState extends State<_PasswordField> {
  bool _obscure = true;

  @override
  Widget build(BuildContext context) {
    return FormFieldBox(
      label: widget.label,
      child: TextFormField(
        controller: widget.controller,
        obscureText: _obscure,
        validator: widget.validator,
        decoration: InputDecoration(
          suffixIcon: IconButton(
            icon: Icon(_obscure ? Icons.visibility_off_outlined : Icons.visibility_outlined,
                size: 20, color: AppTheme.textSecondary),
            tooltip: _obscure ? 'Show password' : 'Hide password',
            onPressed: () => setState(() => _obscure = !_obscure),
          ),
        ),
      ),
    );
  }
}
