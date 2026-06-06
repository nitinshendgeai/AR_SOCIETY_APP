import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/users/data/models/user_admin_models.dart';
import 'package:ar_society_app/features/users/presentation/providers/user_providers.dart';

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
      setState(() => _error = e.toString());
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppTheme.surface,
      appBar: AppBar(title: const Text('Edit User')),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(20),
        child: Form(
          key: _formKey,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              if (_error != null)
                Container(
                  margin: const EdgeInsets.only(bottom: 16),
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: AppTheme.error.withOpacity(0.08),
                    borderRadius: BorderRadius.circular(10),
                    border:
                        Border.all(color: AppTheme.error.withOpacity(0.3)),
                  ),
                  child: Text(_error!,
                      style: const TextStyle(
                          color: AppTheme.error, fontSize: 12)),
                ),

              _fieldLabel('Full Name'),
              const SizedBox(height: 6),
              TextFormField(
                controller: _nameCtrl,
                validator: (v) =>
                    (v == null || v.trim().isEmpty) ? 'Required' : null,
                decoration: _decoration('e.g. Rahul Sharma'),
              ),
              const SizedBox(height: 16),

              _fieldLabel('Phone (optional)'),
              const SizedBox(height: 6),
              TextFormField(
                controller: _phoneCtrl,
                keyboardType: TextInputType.phone,
                decoration: _decoration('+91 9876543210'),
              ),
              const SizedBox(height: 16),

              _fieldLabel('Status'),
              const SizedBox(height: 6),
              DropdownButtonFormField<String>(
                value: _status,
                decoration: _decoration(''),
                items: ['active', 'inactive', 'suspended']
                    .map((s) => DropdownMenuItem(
                        value: s, child: Text(s)))
                    .toList(),
                onChanged: (v) => setState(() => _status = v),
              ),
              const SizedBox(height: 28),

              ElevatedButton(
                onPressed: _loading ? null : _submit,
                child: _loading
                    ? const SizedBox(
                        width: 20,
                        height: 20,
                        child: CircularProgressIndicator(
                            strokeWidth: 2, color: Colors.white))
                    : const Text('Save Changes'),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _fieldLabel(String text) => Text(text,
      style: const TextStyle(
          fontSize: 13,
          fontWeight: FontWeight.w600,
          color: AppTheme.textPrimary));

  InputDecoration _decoration(String hint) => InputDecoration(
        hintText: hint,
        hintStyle:
            const TextStyle(color: AppTheme.textSecondary, fontSize: 14),
        contentPadding:
            const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
        filled: true,
        fillColor: AppTheme.cardBg,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: const BorderSide(color: AppTheme.border),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: const BorderSide(color: AppTheme.border),
        ),
      );
}
