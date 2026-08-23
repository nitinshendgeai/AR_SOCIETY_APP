import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/core/router/app_router.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';

class LoginScreen extends ConsumerStatefulWidget {
  const LoginScreen({super.key});

  @override
  ConsumerState<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends ConsumerState<LoginScreen> {
  final _formKey    = GlobalKey<FormState>();
  final _emailCtrl  = TextEditingController();
  final _passCtrl   = TextEditingController();
  bool _obscurePass = true;

  @override
  void dispose() {
    _emailCtrl.dispose();
    _passCtrl.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    await ref.read(authProvider.notifier).login(
          email: _emailCtrl.text.trim(),
          password: _passCtrl.text,
        );
    // Navigation handled by GoRouter redirect on auth state change
  }

  @override
  Widget build(BuildContext context) {
    final authState = ref.watch(authProvider);
    final isLoading = authState is AuthLoading;
    final errorMsg  = authState is AuthError ? authState.message : null;

    return Scaffold(
      body: Stack(
        children: [
          const Positioned.fill(child: _LoginBackground()),
          SafeArea(
            child: AppLoadingOverlay(
              isLoading: isLoading,
              child: LayoutBuilder(
                builder: (context, constraints) {
                  final cardWidth = constraints.maxWidth < 480
                      ? constraints.maxWidth * 0.92
                      : 420.0;

                  return SingleChildScrollView(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 16,
                      vertical: 40,
                    ),
                    child: Center(
                      child: ConstrainedBox(
                        constraints: BoxConstraints(maxWidth: cardWidth),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.stretch,
                          children: [
                            // Login card
                            Container(
                              padding:
                                  const EdgeInsets.fromLTRB(28, 32, 28, 28),
                              decoration: BoxDecoration(
                                color: AppTheme.cardBg,
                                borderRadius: BorderRadius.circular(16),
                                boxShadow: [
                                  BoxShadow(
                                    color:
                                        AppTheme.primaryDark.withOpacity(0.08),
                                    blurRadius: 32,
                                    offset: const Offset(0, 16),
                                  ),
                                  BoxShadow(
                                    color: Colors.black.withOpacity(0.04),
                                    blurRadius: 4,
                                    offset: const Offset(0, 1),
                                  ),
                                ],
                              ),
                              child: Form(
                                key: _formKey,
                                child: Column(
                                  crossAxisAlignment: CrossAxisAlignment.stretch,
                                  children: [
                                    const _BrandHeader(),
                                    const SizedBox(height: 28),

                                    // Error banner
                                    if (errorMsg != null) ...[
                                      AppErrorBanner(
                                        message: errorMsg,
                                        onDismiss: () => ref
                                            .read(authProvider.notifier)
                                            .clearError(),
                                      ),
                                      const SizedBox(height: 16),
                                    ],

                                    // Email
                                    AppTextField(
                                      label: 'Email address',
                                      hint: 'admin@arsociety.com',
                                      controller: _emailCtrl,
                                      keyboardType:
                                          TextInputType.emailAddress,
                                      textInputAction: TextInputAction.next,
                                      prefixIcon: const Icon(
                                        Icons.mail_outline_rounded,
                                        color: AppTheme.textSecondary,
                                        size: 20,
                                      ),
                                      validator: (v) {
                                        if (v == null || v.trim().isEmpty) {
                                          return 'Email is required';
                                        }
                                        if (!v.contains('@')) {
                                          return 'Enter a valid email';
                                        }
                                        return null;
                                      },
                                    ),
                                    const SizedBox(height: 16),

                                    // Password
                                    AppTextField(
                                      label: 'Password',
                                      controller: _passCtrl,
                                      obscureText: _obscurePass,
                                      textInputAction: TextInputAction.done,
                                      onFieldSubmitted: _submit,
                                      prefixIcon: const Icon(
                                        Icons.lock_outline_rounded,
                                        color: AppTheme.textSecondary,
                                        size: 20,
                                      ),
                                      suffixIcon: IconButton(
                                        tooltip: _obscurePass
                                            ? 'Show password'
                                            : 'Hide password',
                                        icon: Icon(
                                          _obscurePass
                                              ? Icons.visibility_off_outlined
                                              : Icons.visibility_outlined,
                                          color: AppTheme.textSecondary,
                                          size: 20,
                                        ),
                                        onPressed: () => setState(
                                            () => _obscurePass = !_obscurePass),
                                      ),
                                      validator: (v) {
                                        if (v == null || v.isEmpty) {
                                          return 'Password is required';
                                        }
                                        if (v.length < 6) {
                                          return 'Password is too short';
                                        }
                                        return null;
                                      },
                                    ),
                                    const SizedBox(height: 26),

                                    // Login button
                                    AppPrimaryButton(
                                      label: 'Sign In',
                                      isLoading: isLoading,
                                      onPressed: _submit,
                                      icon: Icons.login_rounded,
                                    ),
                                  ],
                                ),
                              ),
                            ),

                            const SizedBox(height: 20),

                            // Register CTA
                            _RegisterCTA(),

                            const SizedBox(height: 16),

                            // Demo format hint — always visible
                            _DemoFormatHint(),

                            const SizedBox(height: 24),
                          ],
                        ),
                      ),
                    ),
                  );
                },
              ),
            ),
          ),
        ],
      ),
    );
  }
}

// ── Background ───────────────────────────────────────────────────────────────

class _LoginBackground extends StatelessWidget {
  const _LoginBackground();

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final showDots = constraints.maxWidth >= 480;
        return Container(
          decoration: const BoxDecoration(
            gradient: LinearGradient(
              begin: Alignment.topCenter,
              end: Alignment.bottomCenter,
              colors: [Color(0xFFF2F6FF), Color(0xFFFAFBFF)],
            ),
          ),
          child: showDots
              ? CustomPaint(
                  painter: const _DotGridPainter(),
                  size: Size.infinite,
                )
              : null,
        );
      },
    );
  }
}

class _DotGridPainter extends CustomPainter {
  const _DotGridPainter();

  static const double _spacing = 28;
  static const double _dotRadius = 1.1;

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()..color = AppTheme.primary.withOpacity(0.05);
    for (double y = 0; y < size.height; y += _spacing) {
      for (double x = 0; x < size.width; x += _spacing) {
        canvas.drawCircle(Offset(x, y), _dotRadius, paint);
      }
    }
  }

  @override
  bool shouldRepaint(covariant _DotGridPainter oldDelegate) => false;
}

// ── Brand header (inside card) ─────────────────────────────────────────────────

class _BrandHeader extends StatelessWidget {
  const _BrandHeader();

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.center,
      children: [
        Container(
          width: 56,
          height: 56,
          decoration: BoxDecoration(
            color: AppTheme.primary.withOpacity(0.1),
            borderRadius: BorderRadius.circular(14),
          ),
          child: const Icon(
            Icons.apartment_rounded,
            color: AppTheme.primary,
            size: 30,
          ),
        ),
        const SizedBox(height: 14),
        Text(
          'DuxOS Society',
          textAlign: TextAlign.center,
          style: Theme.of(context).textTheme.titleLarge?.copyWith(
                fontWeight: FontWeight.w700,
                color: AppTheme.textPrimary,
                letterSpacing: -0.3,
              ),
        ),
        const SizedBox(height: 4),
        Text(
          'ENTERPRISE OPERATIONS PLATFORM',
          textAlign: TextAlign.center,
          style: TextStyle(
            fontSize: 10.5,
            fontWeight: FontWeight.w600,
            color: AppTheme.textSecondary,
            letterSpacing: 1.4,
          ),
        ),
        const SizedBox(height: 24),
        Text(
          'Welcome back',
          textAlign: TextAlign.center,
          style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                fontWeight: FontWeight.w700,
                color: AppTheme.textPrimary,
                letterSpacing: -0.4,
              ),
        ),
        const SizedBox(height: 6),
        Text(
          'Sign in to continue',
          textAlign: TextAlign.center,
          style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                color: AppTheme.textSecondary,
              ),
        ),
      ],
    );
  }
}

// ── Register CTA ──────────────────────────────────────────────────────────────

class _RegisterCTA extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: () => context.push(AppRoutes.registerSociety),
      child: Container(
        width: double.infinity,
        padding: const EdgeInsets.all(18),
        decoration: BoxDecoration(
          gradient: LinearGradient(
            colors: [
              AppTheme.primary.withOpacity(0.08),
              AppTheme.primaryDark.withOpacity(0.05),
            ],
          ),
          borderRadius: BorderRadius.circular(14),
          border: Border.all(color: AppTheme.primary.withOpacity(0.25)),
        ),
        child: Row(
          children: [
            Container(
              padding: const EdgeInsets.all(10),
              decoration: BoxDecoration(
                color: AppTheme.primary.withOpacity(0.12),
                shape: BoxShape.circle,
              ),
              child: const Icon(Icons.rocket_launch_rounded,
                  color: AppTheme.primary, size: 20),
            ),
            const SizedBox(width: 14),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text(
                    'Register Your Society',
                    style: TextStyle(
                      fontWeight: FontWeight.w700,
                      fontSize: 14,
                      color: AppTheme.textPrimary,
                    ),
                  ),
                  const SizedBox(height: 2),
                  Text(
                    'Start a 30-day free trial — no credit card needed',
                    style: TextStyle(
                      fontSize: 12,
                      color: AppTheme.textSecondary,
                    ),
                  ),
                ],
              ),
            ),
            Icon(Icons.arrow_forward_ios_rounded,
                size: 14, color: AppTheme.primary),
          ],
        ),
      ),
    );
  }
}

// ── Demo format hint ──────────────────────────────────────────────────────────

class _DemoFormatHint extends StatefulWidget {
  @override
  State<_DemoFormatHint> createState() => _DemoFormatHintState();
}

class _DemoFormatHintState extends State<_DemoFormatHint> {
  bool _expanded = false;

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: AppTheme.primary.withOpacity(0.04),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppTheme.primary.withOpacity(0.18)),
      ),
      child: Column(children: [
        InkWell(
          borderRadius: BorderRadius.circular(12),
          onTap: () => setState(() => _expanded = !_expanded),
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
            child: Row(children: [
              Icon(Icons.help_outline_rounded,
                  color: AppTheme.primary, size: 16),
              const SizedBox(width: 8),
              const Expanded(
                child: Text(
                  'Demo Login Format',
                  style: TextStyle(
                    fontSize: 13,
                    fontWeight: FontWeight.w600,
                    color: AppTheme.primary,
                  ),
                ),
              ),
              Icon(
                _expanded
                    ? Icons.expand_less_rounded
                    : Icons.expand_more_rounded,
                color: AppTheme.primary,
                size: 18,
              ),
            ]),
          ),
        ),
        if (_expanded) ...[
          const Divider(height: 1),
          Padding(
            padding: const EdgeInsets.all(14),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'After registering, your login credentials follow this format:',
                  style: TextStyle(fontSize: 12, color: AppTheme.textSecondary),
                ),
                const SizedBox(height: 10),
                _HintRow(label: 'Society Code', value: 'greenpark'),
                const SizedBox(height: 6),
                _HintRow(label: 'Admin Login',  value: 'admin@greenpark.com'),
                const SizedBox(height: 6),
                _HintRow(label: 'Password',     value: 'Admin@1234'),
                const SizedBox(height: 10),
                const Text(
                  'Replace "greenpark" with your society code (lowercase).\nYou must change this password on first login.',
                  style: TextStyle(
                    fontSize: 11,
                    color: AppTheme.textSecondary,
                    fontStyle: FontStyle.italic,
                  ),
                ),
              ],
            ),
          ),
        ],
      ]),
    );
  }
}

class _HintRow extends StatelessWidget {
  final String label;
  final String value;
  const _HintRow({required this.label, required this.value});

  @override
  Widget build(BuildContext context) {
    return Row(children: [
      SizedBox(
        width: 90,
        child: Text(label,
            style: const TextStyle(
                fontSize: 12,
                color: AppTheme.textSecondary,
                fontWeight: FontWeight.w500)),
      ),
      Expanded(
        child: Text(
          value,
          style: const TextStyle(
            fontSize: 12,
            color: AppTheme.textPrimary,
            fontFamily: 'monospace',
            fontWeight: FontWeight.w600,
          ),
        ),
      ),
    ]);
  }
}
