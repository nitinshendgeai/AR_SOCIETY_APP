import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/features/auth/presentation/providers/biometric_provider.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';
import 'package:ar_society_app/shared/widgets/auth_page.dart';

/// Shown when a restored session (app reopened, not a fresh password login)
/// needs biometric re-confirmation — see AuthNotifier.checkSession() and the
/// redirect gate in app_router.dart. Auto-prompts once on open so the common
/// case is a single fingerprint tap with no extra button press.
class BiometricLockScreen extends ConsumerStatefulWidget {
  const BiometricLockScreen({super.key});

  @override
  ConsumerState<BiometricLockScreen> createState() => _BiometricLockScreenState();
}

class _BiometricLockScreenState extends ConsumerState<BiometricLockScreen> {
  bool _authenticating = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _tryUnlock());
  }

  Future<void> _tryUnlock() async {
    if (_authenticating) return;
    setState(() { _authenticating = true; _error = null; });
    final ok = await ref
        .read(biometricServiceProvider)
        .authenticate('Unlock DUX OS to continue');
    if (!mounted) return;
    if (ok) {
      ref.read(biometricLockProvider.notifier).unlock();
    } else {
      setState(() {
        _authenticating = false;
        _error = 'Authentication failed or was cancelled.';
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final user = ref.watch(currentUserProvider);
    return AuthPage(
      title: user != null ? 'Welcome back, ${user.fullName}' : 'Welcome back',
      subtitle: 'Unlock with fingerprint or face to continue',
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          if (_error != null) ...[
            AppErrorBanner(message: _error!),
            const SizedBox(height: 16),
          ],
          AppPrimaryButton(
            label: _authenticating ? 'Waiting…' : 'Unlock',
            icon: Icons.fingerprint_rounded,
            isLoading: _authenticating,
            onPressed: _authenticating ? null : _tryUnlock,
          ),
          const SizedBox(height: 8),
          TextButton(
            onPressed: () => ref.read(authProvider.notifier).logout(),
            child: const Text('Use password instead', style: TextStyle(color: AppTheme.textSecondary)),
          ),
        ],
      ),
    );
  }
}
