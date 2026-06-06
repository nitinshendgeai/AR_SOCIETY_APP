import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/core/router/app_router.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/features/onboarding/domain/registration_result.dart';

class TrialSuccessScreen extends ConsumerStatefulWidget {
  final RegistrationResult result;
  const TrialSuccessScreen({super.key, required this.result});

  @override
  ConsumerState<TrialSuccessScreen> createState() => _TrialSuccessScreenState();
}

class _TrialSuccessScreenState extends ConsumerState<TrialSuccessScreen> {
  bool _signingIn = false;
  String? _loginError;

  RegistrationResult get result => widget.result;

  Future<void> _signInAsAdmin() async {
    final admin = result.adminCredential;
    if (admin == null) {
      context.go(AppRoutes.login);
      return;
    }
    setState(() { _signingIn = true; _loginError = null; });
    await ref.read(authProvider.notifier).login(
      email:    admin.email,
      password: admin.password,
    );
    if (!mounted) return;
    setState(() => _signingIn = false);
    final authState = ref.read(authProvider);
    if (authState is AuthError) {
      setState(() => _loginError = authState.message);
    }
    // On success GoRouter redirect fires automatically (→ /change-password)
  }

  void _copyAllCredentials() {
    final buffer = StringBuffer();
    buffer.writeln('Society: ${result.societyName}');
    buffer.writeln('Society Code: ${result.societyCode.toLowerCase()}');
    buffer.writeln('Password for all accounts: ${result.adminCredential?.password ?? "Admin@1234"}');
    buffer.writeln();
    for (final c in result.credentials) {
      buffer.writeln('${c.role}: ${c.email}');
    }
    Clipboard.setData(ClipboardData(text: buffer.toString()));
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('All credentials copied to clipboard')),
    );
  }

  @override
  Widget build(BuildContext context) {
    final admin      = result.adminCredential;
    final code       = result.societyCode.toLowerCase();
    final others     = result.credentials.where((c) => c.role != 'Society Admin').toList();

    return Scaffold(
      backgroundColor: AppTheme.surface,
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(24),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.center,
            children: [
              const SizedBox(height: 24),

              // ── Success icon ──────────────────────────────────────────────
              Container(
                width: 72,
                height: 72,
                decoration: BoxDecoration(
                  color: AppTheme.success.withOpacity(0.12),
                  shape: BoxShape.circle,
                ),
                child: const Icon(Icons.check_circle_rounded,
                    color: AppTheme.success, size: 40),
              ),
              const SizedBox(height: 16),
              Text(
                'Society Created Successfully',
                style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                  fontWeight: FontWeight.w800,
                  color: AppTheme.textPrimary,
                ),
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 6),
              Text(
                result.societyName,
                style: const TextStyle(color: AppTheme.textSecondary, fontSize: 14),
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 24),

              // ── Society code badge ────────────────────────────────────────
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 8),
                decoration: BoxDecoration(
                  color: AppTheme.primary.withOpacity(0.08),
                  borderRadius: BorderRadius.circular(20),
                  border: Border.all(color: AppTheme.primary.withOpacity(0.25)),
                ),
                child: Row(mainAxisSize: MainAxisSize.min, children: [
                  const Text('Society Code: ',
                      style: TextStyle(
                          fontSize: 13,
                          color: AppTheme.textSecondary,
                          fontWeight: FontWeight.w500)),
                  Text(code,
                      style: const TextStyle(
                          fontSize: 14,
                          fontWeight: FontWeight.w700,
                          color: AppTheme.primary,
                          fontFamily: 'monospace')),
                ]),
              ),
              const SizedBox(height: 24),

              // ── Default admin login card ──────────────────────────────────
              if (admin != null) _AdminLoginCard(credential: admin),
              const SizedBox(height: 16),

              // ── Additional users ──────────────────────────────────────────
              _AdditionalUsersCard(credentials: others),
              const SizedBox(height: 16),

              // ── Copy all button ───────────────────────────────────────────
              SizedBox(
                width: double.infinity,
                child: OutlinedButton.icon(
                  onPressed: _copyAllCredentials,
                  icon: const Icon(Icons.copy_rounded, size: 18),
                  label: const Text('Copy All Credentials'),
                  style: OutlinedButton.styleFrom(
                    padding: const EdgeInsets.symmetric(vertical: 14),
                    side: const BorderSide(color: AppTheme.primary),
                    foregroundColor: AppTheme.primary,
                    shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(12)),
                  ),
                ),
              ),
              const SizedBox(height: 12),

              // ── Trial info ────────────────────────────────────────────────
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
                decoration: BoxDecoration(
                  color: AppTheme.warning.withOpacity(0.08),
                  borderRadius: BorderRadius.circular(10),
                  border: Border.all(color: AppTheme.warning.withOpacity(0.2)),
                ),
                child: Row(children: [
                  const Icon(Icons.timer_rounded, color: AppTheme.warning, size: 16),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      '${result.trialDays}-day free trial · Ends ${result.trialEndDate}',
                      style: const TextStyle(
                          fontSize: 12,
                          color: AppTheme.warning,
                          fontWeight: FontWeight.w600),
                    ),
                  ),
                ]),
              ),
              const SizedBox(height: 24),

              // ── Login error ───────────────────────────────────────────────
              if (_loginError != null) ...[
                Container(
                  width: double.infinity,
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: AppTheme.error.withOpacity(0.08),
                    borderRadius: BorderRadius.circular(10),
                    border: Border.all(color: AppTheme.error.withOpacity(0.3)),
                  ),
                  child: Text(_loginError!,
                      style: const TextStyle(color: AppTheme.error, fontSize: 13),
                      textAlign: TextAlign.center),
                ),
                const SizedBox(height: 12),
                TextButton(
                  onPressed: () => context.go(AppRoutes.login),
                  child: const Text('Sign in manually instead'),
                ),
                const SizedBox(height: 8),
              ],

              // ── Sign in as admin ──────────────────────────────────────────
              SizedBox(
                width: double.infinity,
                child: ElevatedButton.icon(
                  style: ElevatedButton.styleFrom(
                    backgroundColor: AppTheme.primary,
                    foregroundColor: Colors.white,
                    padding: const EdgeInsets.symmetric(vertical: 16),
                    shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(12)),
                  ),
                  icon: _signingIn
                      ? const SizedBox(
                          width: 18, height: 18,
                          child: CircularProgressIndicator(
                              strokeWidth: 2, color: Colors.white))
                      : const Icon(Icons.login_rounded),
                  label: Text(
                    _signingIn ? 'Signing in…' : 'Sign in as Admin',
                    style: const TextStyle(
                        fontWeight: FontWeight.w600, fontSize: 15),
                  ),
                  onPressed: _signingIn ? null : _signInAsAdmin,
                ),
              ),
              const SizedBox(height: 32),
            ],
          ),
        ),
      ),
    );
  }
}

// ── Admin login card ──────────────────────────────────────────────────────────

class _AdminLoginCard extends StatefulWidget {
  final RegistrationCredential credential;
  const _AdminLoginCard({required this.credential});

  @override
  State<_AdminLoginCard> createState() => _AdminLoginCardState();
}

class _AdminLoginCardState extends State<_AdminLoginCard> {
  bool _showPwd = false;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: AppTheme.primary.withOpacity(0.05),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppTheme.primary.withOpacity(0.25)),
      ),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Container(
            padding: const EdgeInsets.all(6),
            decoration: BoxDecoration(
              color: AppTheme.primary.withOpacity(0.12),
              borderRadius: BorderRadius.circular(8),
            ),
            child: const Icon(Icons.admin_panel_settings_rounded,
                color: AppTheme.primary, size: 18),
          ),
          const SizedBox(width: 10),
          const Text('Default Login',
              style: TextStyle(
                  fontWeight: FontWeight.w700,
                  fontSize: 15,
                  color: AppTheme.textPrimary)),
        ]),
        const SizedBox(height: 14),
        _InfoRow(label: 'Email',
            value: widget.credential.email,
            canCopy: true),
        const SizedBox(height: 8),
        Row(children: [
          const SizedBox(
            width: 64,
            child: Text('Password',
                style: TextStyle(
                    fontSize: 12,
                    color: AppTheme.textSecondary,
                    fontWeight: FontWeight.w500)),
          ),
          Expanded(
            child: Text(
              _showPwd
                  ? widget.credential.password
                  : '•' * widget.credential.password.length.clamp(6, 10),
              style: const TextStyle(
                fontSize: 13,
                fontWeight: FontWeight.w600,
                color: AppTheme.textPrimary,
                fontFamily: 'monospace',
              ),
            ),
          ),
          GestureDetector(
            onTap: () => setState(() => _showPwd = !_showPwd),
            child: Icon(
              _showPwd ? Icons.visibility_off_outlined : Icons.visibility_outlined,
              size: 16, color: AppTheme.textSecondary,
            ),
          ),
          const SizedBox(width: 8),
          GestureDetector(
            onTap: () {
              Clipboard.setData(ClipboardData(text: widget.credential.password));
              ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(content: Text('Password copied')),
              );
            },
            child: const Icon(Icons.copy_rounded, size: 16, color: AppTheme.primary),
          ),
        ]),
        const SizedBox(height: 12),
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
          decoration: BoxDecoration(
            color: AppTheme.warning.withOpacity(0.08),
            borderRadius: BorderRadius.circular(6),
          ),
          child: const Text(
            'You will be asked to change this password on first login.',
            style: TextStyle(fontSize: 11, color: AppTheme.warning),
          ),
        ),
      ]),
    );
  }
}

// ── Additional users card ─────────────────────────────────────────────────────

class _AdditionalUsersCard extends StatefulWidget {
  final List<RegistrationCredential> credentials;
  const _AdditionalUsersCard({required this.credentials});

  @override
  State<_AdditionalUsersCard> createState() => _AdditionalUsersCardState();
}

class _AdditionalUsersCardState extends State<_AdditionalUsersCard> {
  bool _expanded = false;

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: AppTheme.cardBg,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppTheme.border),
      ),
      child: Column(children: [
        InkWell(
          borderRadius: BorderRadius.circular(16),
          onTap: () => setState(() => _expanded = !_expanded),
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Row(children: [
              const Icon(Icons.people_outline_rounded,
                  color: AppTheme.textSecondary, size: 20),
              const SizedBox(width: 10),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text('Additional Users Created',
                        style: TextStyle(
                            fontWeight: FontWeight.w600,
                            fontSize: 14,
                            color: AppTheme.textPrimary)),
                    Text('${widget.credentials.length} accounts · All use same password',
                        style: const TextStyle(
                            fontSize: 12, color: AppTheme.textSecondary)),
                  ],
                ),
              ),
              Icon(
                _expanded ? Icons.expand_less_rounded : Icons.expand_more_rounded,
                color: AppTheme.textSecondary,
              ),
            ]),
          ),
        ),
        if (_expanded) ...[
          const Divider(height: 1),
          ...widget.credentials.map((c) => Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
            child: Row(children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(c.role,
                        style: const TextStyle(
                            fontSize: 12,
                            fontWeight: FontWeight.w600,
                            color: AppTheme.textPrimary)),
                    const SizedBox(height: 2),
                    Text(c.email,
                        style: const TextStyle(
                            fontSize: 12,
                            color: AppTheme.textSecondary,
                            fontFamily: 'monospace')),
                  ],
                ),
              ),
              GestureDetector(
                onTap: () {
                  Clipboard.setData(ClipboardData(text: c.email));
                  ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(content: Text('Email copied')),
                  );
                },
                child: const Icon(Icons.copy_rounded,
                    size: 16, color: AppTheme.primary),
              ),
            ]),
          )),
          const SizedBox(height: 8),
        ],
      ]),
    );
  }
}

// ── Shared row widget ─────────────────────────────────────────────────────────

class _InfoRow extends StatelessWidget {
  final String label;
  final String value;
  final bool canCopy;
  const _InfoRow({required this.label, required this.value, this.canCopy = false});

  @override
  Widget build(BuildContext context) {
    return Row(children: [
      SizedBox(
        width: 64,
        child: Text(label,
            style: const TextStyle(
                fontSize: 12,
                color: AppTheme.textSecondary,
                fontWeight: FontWeight.w500)),
      ),
      Expanded(
        child: Text(value,
            style: const TextStyle(
                fontSize: 13,
                fontWeight: FontWeight.w600,
                color: AppTheme.textPrimary,
                fontFamily: 'monospace')),
      ),
      if (canCopy)
        GestureDetector(
          onTap: () {
            Clipboard.setData(ClipboardData(text: value));
            ScaffoldMessenger.of(context).showSnackBar(
              const SnackBar(content: Text('Copied')),
            );
          },
          child: const Icon(Icons.copy_rounded, size: 16, color: AppTheme.primary),
        ),
    ]);
  }
}
