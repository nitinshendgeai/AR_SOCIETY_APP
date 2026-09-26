import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/resident_master/presentation/widgets/resident_master_widgets.dart'
    show rmPhoneValidator;

/// "Forgot password?" — asks the society office to reset the password.
/// Residents sign in by mobile and have no real email on file, so there's no
/// self-service link: the request reaches the society's admins, who give the
/// member a temporary password (changed at the next sign-in).
Future<void> showForgotPasswordDialog(BuildContext context, {String initialIdentifier = ''}) =>
    showDialog(
      context: context,
      builder: (_) => _ForgotPasswordDialog(initialIdentifier: initialIdentifier),
    );

class _ForgotPasswordDialog extends StatefulWidget {
  final String initialIdentifier;
  const _ForgotPasswordDialog({required this.initialIdentifier});

  @override
  State<_ForgotPasswordDialog> createState() => _ForgotPasswordDialogState();
}

class _ForgotPasswordDialogState extends State<_ForgotPasswordDialog> {
  final _formKey = GlobalKey<FormState>();
  late final _ctrl = TextEditingController(text: widget.initialIdentifier.trim());
  bool _sending = false;
  String? _sentMessage;
  String? _error;

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  Future<void> _send() async {
    if (_sending || !_formKey.currentState!.validate()) return;
    setState(() {
      _sending = true;
      _error = null;
    });
    try {
      final r = await ApiClient.instance
          .post('/auth/forgot-password', data: {'identifier': _ctrl.text.trim()});
      if (mounted) setState(() => _sentMessage = (r.data as Map)['message'] as String?);
    } on DioException catch (e) {
      if (mounted) setState(() => _error = parseApiError(e));
    } catch (_) {
      if (mounted) setState(() => _error = 'Could not send the request. Please try again.');
    } finally {
      if (mounted) setState(() => _sending = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final sent = _sentMessage != null;
    return AlertDialog(
      title: Text(sent ? 'Request sent' : 'Forgot password?'),
      content: SizedBox(
        width: 400,
        child: sent
            ? Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                const Icon(Icons.mark_email_read_rounded, color: AppTheme.success),
                const SizedBox(width: 12),
                Expanded(child: Text(_sentMessage!)),
              ])
            : Form(
                key: _formKey,
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text(
                      'Enter the email or mobile number you sign in with. Your society office will '
                      'reset your password and give you a temporary one.',
                      style: TextStyle(fontSize: 13, color: AppTheme.textSecondary),
                    ),
                    const SizedBox(height: 16),
                    TextFormField(
                      controller: _ctrl,
                      autofocus: true,
                      decoration: const InputDecoration(labelText: 'Email or Mobile Number'),
                      textInputAction: TextInputAction.send,
                      onFieldSubmitted: (_) => _send(),
                      validator: (v) {
                        final input = (v ?? '').trim();
                        if (input.isEmpty) return 'Email or mobile number is required';
                        if (input.contains('@')) return input.contains('.') ? null : 'Enter a valid email';
                        return rmPhoneValidator(input);
                      },
                    ),
                    if (_error != null) ...[
                      const SizedBox(height: 12),
                      Text(_error!, style: const TextStyle(color: AppTheme.error, fontSize: 13)),
                    ],
                  ],
                ),
              ),
      ),
      actions: sent
          ? [ElevatedButton(onPressed: () => Navigator.pop(context), child: const Text('OK'))]
          : [
              TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancel')),
              ElevatedButton(
                onPressed: _sending ? null : _send,
                child: _sending
                    ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2))
                    : const Text('Send request'),
              ),
            ],
    );
  }
}
