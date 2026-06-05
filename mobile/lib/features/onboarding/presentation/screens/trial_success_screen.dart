import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:go_router/go_router.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/core/router/app_router.dart';
import 'package:ar_society_app/features/onboarding/domain/registration_result.dart';

class TrialSuccessScreen extends StatelessWidget {
  final RegistrationResult result;

  const TrialSuccessScreen({super.key, required this.result});

  @override
  Widget build(BuildContext context) {
    final admin = result.adminCredential;

    return Scaffold(
      backgroundColor: AppTheme.surface,
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(24),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.center,
            children: [
              const SizedBox(height: 32),

              // Success icon
              Container(
                width: 80,
                height: 80,
                decoration: BoxDecoration(
                  color: AppTheme.success.withOpacity(0.12),
                  shape: BoxShape.circle,
                ),
                child: const Icon(
                  Icons.check_circle_rounded,
                  color: AppTheme.success,
                  size: 44,
                ),
              ),
              const SizedBox(height: 20),

              Text(
                'You\'re all set!',
                style: Theme.of(context).textTheme.headlineMedium?.copyWith(
                      fontWeight: FontWeight.w800,
                      color: AppTheme.textPrimary,
                      letterSpacing: -0.5,
                    ),
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 8),
              Text(
                '${result.societyName} is registered with a ${result.trialDays}-day free trial.',
                style: TextStyle(
                  color: AppTheme.textSecondary,
                  fontSize: 15,
                ),
                textAlign: TextAlign.center,
              ),

              const SizedBox(height: 28),

              // Trial badge
              Container(
                padding:
                    const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
                decoration: BoxDecoration(
                  gradient: const LinearGradient(
                    colors: [AppTheme.primary, AppTheme.primaryDark],
                  ),
                  borderRadius: BorderRadius.circular(14),
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    const Icon(Icons.timer_rounded,
                        color: Colors.white, size: 20),
                    const SizedBox(width: 8),
                    Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          '${result.trialDays} days remaining',
                          style: const TextStyle(
                            color: Colors.white,
                            fontWeight: FontWeight.w700,
                            fontSize: 15,
                          ),
                        ),
                        Text(
                          'Trial ends ${result.trialEndDate}',
                          style: TextStyle(
                            color: Colors.white.withOpacity(0.85),
                            fontSize: 12,
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
              ),

              const SizedBox(height: 28),

              // Admin credentials card
              if (admin != null) ...[
                _CredentialCard(
                  title: 'Admin Login Credentials',
                  subtitle: 'Use these to sign in for the first time',
                  credential: admin,
                ),
                const SizedBox(height: 16),
              ],

              // All credentials
              if (result.credentials.length > 1) ...[
                _AllCredentialsExpanded(credentials: result.credentials),
                const SizedBox(height: 16),
              ],

              // Next steps card
              _NextStepsCard(),

              const SizedBox(height: 28),

              // Go to login button
              SizedBox(
                width: double.infinity,
                child: ElevatedButton.icon(
                  style: ElevatedButton.styleFrom(
                    backgroundColor: AppTheme.primary,
                    foregroundColor: Colors.white,
                    padding: const EdgeInsets.symmetric(vertical: 16),
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(12),
                    ),
                  ),
                  icon: const Icon(Icons.login_rounded),
                  label: const Text(
                    'Sign in as Admin',
                    style: TextStyle(
                        fontWeight: FontWeight.w600, fontSize: 15),
                  ),
                  onPressed: () => context.go(AppRoutes.login),
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

// ── Admin credential card ──────────────────────────────────────────────────────

class _CredentialCard extends StatelessWidget {
  final String title;
  final String subtitle;
  final RegistrationCredential credential;

  const _CredentialCard({
    required this.title,
    required this.subtitle,
    required this.credential,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: AppTheme.cardBg,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppTheme.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title,
              style: const TextStyle(
                  fontWeight: FontWeight.w700,
                  fontSize: 15,
                  color: AppTheme.textPrimary)),
          const SizedBox(height: 4),
          Text(subtitle,
              style:
                  const TextStyle(color: AppTheme.textSecondary, fontSize: 12)),
          const Divider(height: 20),
          _CredRow(label: 'Role',     value: credential.role),
          const SizedBox(height: 8),
          _CredRow(label: 'Email',    value: credential.email),
          const SizedBox(height: 8),
          _CredRow(
            label:  'Password',
            value:  credential.password,
            masked: true,
            onCopy: () {
              Clipboard.setData(ClipboardData(text: credential.password));
              ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(content: Text('Password copied!')),
              );
            },
          ),
        ],
      ),
    );
  }
}

class _CredRow extends StatefulWidget {
  final String label;
  final String value;
  final bool masked;
  final VoidCallback? onCopy;

  const _CredRow({
    required this.label,
    required this.value,
    this.masked = false,
    this.onCopy,
  });

  @override
  State<_CredRow> createState() => _CredRowState();
}

class _CredRowState extends State<_CredRow> {
  bool _show = false;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        SizedBox(
          width: 72,
          child: Text(widget.label,
              style: TextStyle(
                  color: AppTheme.textSecondary,
                  fontSize: 12,
                  fontWeight: FontWeight.w500)),
        ),
        Expanded(
          child: Text(
            widget.masked && !_show
                ? '•' * widget.value.length.clamp(8, 12)
                : widget.value,
            style: const TextStyle(
                fontFamily: 'monospace',
                fontSize: 13,
                color: AppTheme.textPrimary,
                fontWeight: FontWeight.w500),
          ),
        ),
        if (widget.masked)
          GestureDetector(
            onTap: () => setState(() => _show = !_show),
            child: Icon(
                _show
                    ? Icons.visibility_off_outlined
                    : Icons.visibility_outlined,
                size: 16,
                color: AppTheme.textSecondary),
          ),
        if (widget.onCopy != null)
          GestureDetector(
            onTap: widget.onCopy,
            child: Padding(
              padding: const EdgeInsets.only(left: 8),
              child: Icon(Icons.copy_rounded,
                  size: 16, color: AppTheme.primary),
            ),
          ),
      ],
    );
  }
}

// ── All credentials expanded ───────────────────────────────────────────────────

class _AllCredentialsExpanded extends StatefulWidget {
  final List<RegistrationCredential> credentials;
  const _AllCredentialsExpanded({required this.credentials});

  @override
  State<_AllCredentialsExpanded> createState() =>
      _AllCredentialsExpandedState();
}

class _AllCredentialsExpandedState extends State<_AllCredentialsExpanded> {
  bool _expanded = false;

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: AppTheme.cardBg,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppTheme.border),
      ),
      child: Column(
        children: [
          ListTile(
            title: const Text('All Credentials',
                style: TextStyle(fontWeight: FontWeight.w600, fontSize: 14)),
            subtitle: Text('${widget.credentials.length} accounts created',
                style: const TextStyle(fontSize: 12)),
            trailing: Icon(_expanded
                ? Icons.expand_less_rounded
                : Icons.expand_more_rounded),
            onTap: () => setState(() => _expanded = !_expanded),
          ),
          if (_expanded)
            ...widget.credentials.map(
              (c) => Padding(
                padding:
                    const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                child: Row(
                  children: [
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(c.role,
                              style: const TextStyle(
                                  fontWeight: FontWeight.w600,
                                  fontSize: 13,
                                  color: AppTheme.textPrimary)),
                          Text(c.email,
                              style: const TextStyle(
                                  fontSize: 12,
                                  color: AppTheme.textSecondary)),
                        ],
                      ),
                    ),
                    GestureDetector(
                      onTap: () {
                        Clipboard.setData(
                            ClipboardData(text: '${c.email}\n${c.password}'));
                        ScaffoldMessenger.of(context).showSnackBar(
                          const SnackBar(
                              content: Text('Credentials copied!')),
                        );
                      },
                      child: const Icon(Icons.copy_rounded,
                          size: 16, color: AppTheme.primary),
                    ),
                  ],
                ),
              ),
            ),
        ],
      ),
    );
  }
}

// ── Next steps card ────────────────────────────────────────────────────────────

class _NextStepsCard extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    const steps = [
      (Icons.login_rounded,         'Sign in with your admin credentials'),
      (Icons.password_rounded,      'Change your password on first login'),
      (Icons.apartment_rounded,     'Complete the society setup wizard'),
      (Icons.people_outline_rounded,'Add residents and committee members'),
    ];

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: AppTheme.cardBg,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppTheme.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('Next Steps',
              style: TextStyle(
                  fontWeight: FontWeight.w700,
                  fontSize: 15,
                  color: AppTheme.textPrimary)),
          const SizedBox(height: 12),
          ...List.generate(steps.length, (i) {
            final stepText = steps[i].$2;
            return Padding(
              padding: const EdgeInsets.only(bottom: 10),
              child: Row(
                children: [
                  Container(
                    width: 28,
                    height: 28,
                    decoration: BoxDecoration(
                      color: AppTheme.primary.withOpacity(0.1),
                      shape: BoxShape.circle,
                    ),
                    child: Center(
                      child: Text('${i + 1}',
                          style: const TextStyle(
                              color: AppTheme.primary,
                              fontSize: 12,
                              fontWeight: FontWeight.w700)),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Text(stepText,
                        style: const TextStyle(
                            fontSize: 13, color: AppTheme.textPrimary)),
                  ),
                ],
              ),
            );
          }),
        ],
      ),
    );
  }
}
