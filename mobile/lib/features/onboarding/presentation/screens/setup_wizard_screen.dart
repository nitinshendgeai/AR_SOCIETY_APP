import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/router/app_router.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/auth/data/repositories/auth_repository.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/features/onboarding/presentation/providers/setup_wizard_provider.dart';

class SetupWizardScreen extends ConsumerStatefulWidget {
  const SetupWizardScreen({super.key});

  @override
  ConsumerState<SetupWizardScreen> createState() => _SetupWizardScreenState();
}

class _SetupWizardScreenState extends ConsumerState<SetupWizardScreen> {
  final _pageController = PageController();
  int _step = 0;
  bool _termsChecked = false;
  bool _isLoading = false;
  String? _error;
  late final bool _showSocietyStep;
  late final String? _societyId;

  @override
  void initState() {
    super.initState();
    final user = ref.read(currentUserProvider);
    _societyId = user?.societyId;
    _showSocietyStep = user != null && user.isAdminOrCommittee && _societyId != null;
  }

  int get _totalSteps => _showSocietyStep ? 3 : 2;

  void _nextPage() {
    setState(() {
      _step++;
      _error = null;
    });
    _pageController.nextPage(
      duration: const Duration(milliseconds: 350),
      curve: Curves.easeInOut,
    );
  }

  Future<void> _onAcceptTerms() async {
    if (!_termsChecked) {
      setState(() => _error = 'Please accept the Terms & Conditions to continue.');
      return;
    }
    setState(() { _isLoading = true; _error = null; });

    final result = await ref.read(authProvider.notifier).acceptTerms();

    setState(() => _isLoading = false);
    if (result is AuthSuccess) {
      _nextPage();
    } else if (result is AuthFailure) {
      setState(() => _error = result.message);
    }
  }

  Future<void> _onFinish() async {
    setState(() { _isLoading = true; _error = null; });

    if (_societyId != null && _showSocietyStep) {
      try {
        await ApiClient.instance.patch(
          '/societies/$_societyId/setup-progress',
          data: {'setup_completion_percentage': 100, 'setup_completed': true},
        );
      } catch (_) {
        // Non-critical — proceed even if this call fails.
      }
    }

    await ref.read(authProvider.notifier).refreshUser();
    setState(() => _isLoading = false);

    if (mounted) context.go(_computeRoleHome());
  }

  String _computeRoleHome() {
    final user = ref.read(currentUserProvider);
    if (user == null) return AppRoutes.login;
    switch (user.primaryRole) {
      case 'Admin':
      case 'Super Admin':
      case 'Society Admin':
        return AppRoutes.adminHome;
      case 'Committee':
        return AppRoutes.committeeHome;
      case 'Security':
        return AppRoutes.securityHome;
      case 'Staff':
        return AppRoutes.staffHome;
      default:
        return AppRoutes.residentHome;
    }
  }

  @override
  void dispose() {
    _pageController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppTheme.surface,
      body: SafeArea(
        child: Column(
          children: [
            _WizardHeader(step: _step, totalSteps: _totalSteps),
            Expanded(
              child: PageView(
                controller: _pageController,
                physics: const NeverScrollableScrollPhysics(),
                children: [
                  _TermsStep(
                    checked: _termsChecked,
                    isLoading: _isLoading,
                    error: _error,
                    onChanged: (v) => setState(() {
                      _termsChecked = v ?? false;
                      _error = null;
                    }),
                    onNext: _onAcceptTerms,
                  ),
                  if (_showSocietyStep)
                    _SocietyStep(
                      societyId: _societyId!,
                      onNext: _nextPage,
                    ),
                  _DoneStep(
                    isLoading: _isLoading,
                    onFinish: _onFinish,
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

// ── Wizard header with step progress ─────────────────────────────────────────

class _WizardHeader extends StatelessWidget {
  final int step;
  final int totalSteps;

  const _WizardHeader({required this.step, required this.totalSteps});

  static const _stepTitles = ['Terms & Conditions', 'Your Society', 'All Done!'];
  static const _stepTitlesFallback = ['Terms & Conditions', 'All Done!'];

  @override
  Widget build(BuildContext context) {
    final titles = totalSteps == 3 ? _stepTitles : _stepTitlesFallback;
    final title = step < titles.length ? titles[step] : titles.last;

    return Container(
      padding: const EdgeInsets.fromLTRB(24, 20, 24, 16),
      color: AppTheme.cardBg,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.apartment_rounded, color: AppTheme.primary, size: 22),
              const SizedBox(width: 8),
              Text(
                'Setup Wizard',
                style: TextStyle(
                  color: AppTheme.textSecondary,
                  fontSize: 13,
                  fontWeight: FontWeight.w500,
                ),
              ),
              const Spacer(),
              Text(
                'Step ${step + 1} of $totalSteps',
                style: const TextStyle(
                  color: AppTheme.textSecondary,
                  fontSize: 12,
                ),
              ),
            ],
          ),
          const SizedBox(height: 10),
          Text(
            title,
            style: Theme.of(context).textTheme.titleLarge?.copyWith(
              fontWeight: FontWeight.w700,
              color: AppTheme.textPrimary,
            ),
          ),
          const SizedBox(height: 12),
          ClipRRect(
            borderRadius: BorderRadius.circular(4),
            child: LinearProgressIndicator(
              value: (step + 1) / totalSteps,
              backgroundColor: AppTheme.border,
              color: AppTheme.primary,
              minHeight: 4,
            ),
          ),
        ],
      ),
    );
  }
}

// ── Step 0: Terms & Conditions ────────────────────────────────────────────────

class _TermsStep extends StatelessWidget {
  final bool checked;
  final bool isLoading;
  final String? error;
  final ValueChanged<bool?> onChanged;
  final VoidCallback onNext;

  const _TermsStep({
    required this.checked,
    required this.isLoading,
    required this.error,
    required this.onChanged,
    required this.onNext,
  });

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const SizedBox(height: 8),
          Container(
            width: 60,
            height: 60,
            decoration: BoxDecoration(
              color: AppTheme.primary.withOpacity(0.10),
              shape: BoxShape.circle,
            ),
            child: const Icon(
              Icons.gavel_rounded,
              color: AppTheme.primary,
              size: 30,
            ),
          ),
          const SizedBox(height: 20),
          Text(
            'Welcome to AR Society',
            style: Theme.of(context).textTheme.headlineSmall?.copyWith(
              fontWeight: FontWeight.w800,
              color: AppTheme.textPrimary,
            ),
          ),
          const SizedBox(height: 8),
          const Text(
            'Please review and accept our Terms of Service before getting started.',
            style: TextStyle(color: AppTheme.textSecondary, fontSize: 14, height: 1.5),
          ),
          const SizedBox(height: 24),
          _TermsCard(),
          const SizedBox(height: 20),
          GestureDetector(
            onTap: () => onChanged(!checked),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Checkbox(
                  value: checked,
                  onChanged: onChanged,
                  activeColor: AppTheme.primary,
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(4),
                  ),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: Padding(
                    padding: const EdgeInsets.only(top: 12),
                    child: RichText(
                      text: const TextSpan(
                        style: TextStyle(
                          color: AppTheme.textPrimary,
                          fontSize: 14,
                          height: 1.4,
                        ),
                        children: [
                          TextSpan(text: 'I have read and agree to the '),
                          TextSpan(
                            text: 'Terms & Conditions',
                            style: TextStyle(
                              color: AppTheme.primary,
                              fontWeight: FontWeight.w600,
                            ),
                          ),
                          TextSpan(text: ' and '),
                          TextSpan(
                            text: 'Privacy Policy',
                            style: TextStyle(
                              color: AppTheme.primary,
                              fontWeight: FontWeight.w600,
                            ),
                          ),
                          TextSpan(text: ' of AR Society.'),
                        ],
                      ),
                    ),
                  ),
                ),
              ],
            ),
          ),
          if (error != null) ...[
            const SizedBox(height: 12),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
              decoration: BoxDecoration(
                color: AppTheme.error.withOpacity(0.08),
                borderRadius: BorderRadius.circular(8),
                border: Border.all(color: AppTheme.error.withOpacity(0.3)),
              ),
              child: Row(
                children: [
                  const Icon(Icons.error_outline_rounded,
                      color: AppTheme.error, size: 16),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(error!,
                        style: const TextStyle(
                            color: AppTheme.error, fontSize: 13)),
                  ),
                ],
              ),
            ),
          ],
          const SizedBox(height: 24),
          SizedBox(
            width: double.infinity,
            child: ElevatedButton(
              onPressed: isLoading ? null : onNext,
              child: isLoading
                  ? const SizedBox(
                      height: 20,
                      width: 20,
                      child: CircularProgressIndicator(
                          strokeWidth: 2, color: Colors.white),
                    )
                  : const Text('Accept & Continue'),
            ),
          ),
        ],
      ),
    );
  }
}

class _TermsCard extends StatefulWidget {
  @override
  State<_TermsCard> createState() => _TermsCardState();
}

class _TermsCardState extends State<_TermsCard> {
  bool _expanded = false;

  static const _summary = [
    ('Data Usage', 'Your society data is stored securely and used only to deliver AR Society services.'),
    ('Privacy', 'We do not sell or share your personal information with third parties.'),
    ('Fair Use', 'The platform must be used for legitimate society management purposes only.'),
    ('Trial', 'Free trial accounts have a 30-day evaluation period after which a subscription is required.'),
    ('Termination', 'Accounts that violate our policies may be suspended or terminated.'),
  ];

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: AppTheme.cardBg,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: AppTheme.border),
      ),
      child: Column(
        children: [
          ListTile(
            leading: const Icon(Icons.description_outlined,
                color: AppTheme.primary, size: 20),
            title: const Text(
              'Terms Summary',
              style: TextStyle(fontWeight: FontWeight.w600, fontSize: 14),
            ),
            subtitle: Text(
              _expanded ? 'Tap to collapse' : 'Tap to read key terms',
              style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary),
            ),
            trailing: Icon(
              _expanded ? Icons.expand_less_rounded : Icons.expand_more_rounded,
              color: AppTheme.textSecondary,
            ),
            onTap: () => setState(() => _expanded = !_expanded),
          ),
          if (_expanded) ...[
            const Divider(height: 1),
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 12, 16, 16),
              child: Column(
                children: _summary
                    .map((item) => Padding(
                          padding: const EdgeInsets.only(bottom: 12),
                          child: Row(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Container(
                                width: 6,
                                height: 6,
                                margin: const EdgeInsets.only(top: 6, right: 10),
                                decoration: const BoxDecoration(
                                  color: AppTheme.primary,
                                  shape: BoxShape.circle,
                                ),
                              ),
                              Expanded(
                                child: Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    Text(
                                      item.$1,
                                      style: const TextStyle(
                                        fontWeight: FontWeight.w600,
                                        fontSize: 13,
                                        color: AppTheme.textPrimary,
                                      ),
                                    ),
                                    const SizedBox(height: 2),
                                    Text(
                                      item.$2,
                                      style: const TextStyle(
                                        fontSize: 12,
                                        color: AppTheme.textSecondary,
                                        height: 1.4,
                                      ),
                                    ),
                                  ],
                                ),
                              ),
                            ],
                          ),
                        ))
                    .toList(),
              ),
            ),
          ],
        ],
      ),
    );
  }
}

// ── Step 1: Society Details ───────────────────────────────────────────────────

class _SocietyStep extends ConsumerWidget {
  final String societyId;
  final VoidCallback onNext;

  const _SocietyStep({required this.societyId, required this.onNext});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final societyAsync = ref.watch(societyDetailsProvider(societyId));

    return SingleChildScrollView(
      padding: const EdgeInsets.all(24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const SizedBox(height: 8),
          Container(
            width: 60,
            height: 60,
            decoration: BoxDecoration(
              color: AppTheme.primary.withOpacity(0.10),
              shape: BoxShape.circle,
            ),
            child: const Icon(
              Icons.apartment_rounded,
              color: AppTheme.primary,
              size: 30,
            ),
          ),
          const SizedBox(height: 20),
          Text(
            'Confirm Your Society',
            style: Theme.of(context).textTheme.headlineSmall?.copyWith(
              fontWeight: FontWeight.w800,
              color: AppTheme.textPrimary,
            ),
          ),
          const SizedBox(height: 8),
          const Text(
            'Review the society details set up for your account.',
            style: TextStyle(color: AppTheme.textSecondary, fontSize: 14, height: 1.5),
          ),
          const SizedBox(height: 24),
          societyAsync.when(
            loading: () => const Center(
              child: Padding(
                padding: EdgeInsets.all(40),
                child: CircularProgressIndicator(),
              ),
            ),
            error: (e, _) => Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: AppTheme.error.withOpacity(0.08),
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: AppTheme.error.withOpacity(0.3)),
              ),
              child: Row(
                children: [
                  const Icon(Icons.error_outline_rounded, color: AppTheme.error),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Text(
                      'Could not load society details. You can still continue.',
                      style: const TextStyle(color: AppTheme.textSecondary, fontSize: 13),
                    ),
                  ),
                ],
              ),
            ),
            data: (society) => _SocietyCard(society: society),
          ),
          const SizedBox(height: 28),
          SizedBox(
            width: double.infinity,
            child: ElevatedButton(
              onPressed: onNext,
              child: const Text('Looks Good — Continue'),
            ),
          ),
          const SizedBox(height: 12),
          SizedBox(
            width: double.infinity,
            child: TextButton(
              onPressed: onNext,
              child: const Text(
                'Skip for now',
                style: TextStyle(color: AppTheme.textSecondary),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _SocietyCard extends StatelessWidget {
  final SocietyDetails society;
  const _SocietyCard({required this.society});

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
          Row(
            children: [
              Container(
                width: 44,
                height: 44,
                decoration: BoxDecoration(
                  gradient: const LinearGradient(
                    colors: [AppTheme.primary, AppTheme.primaryDark],
                  ),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: const Icon(Icons.apartment_rounded,
                    color: Colors.white, size: 22),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Text(
                  society.name,
                  style: const TextStyle(
                    fontWeight: FontWeight.w700,
                    fontSize: 16,
                    color: AppTheme.textPrimary,
                  ),
                ),
              ),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                decoration: BoxDecoration(
                  color: AppTheme.success.withOpacity(0.1),
                  borderRadius: BorderRadius.circular(20),
                ),
                child: const Text(
                  'Active',
                  style: TextStyle(
                    color: AppTheme.success,
                    fontSize: 12,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ),
            ],
          ),
          const Divider(height: 24),
          ..._buildRows(society),
        ],
      ),
    );
  }

  List<Widget> _buildRows(SocietyDetails s) {
    final rows = <(IconData, String, String?)>[
      (Icons.location_on_outlined,  'Address', s.address),
      (Icons.location_city_outlined, 'City',    s.city),
      (Icons.map_outlined,           'State',   s.state),
      (Icons.pin_outlined,           'Pincode', s.pincode),
      (Icons.email_outlined,         'Email',   s.contactEmail),
      (Icons.phone_outlined,         'Phone',   s.contactPhone),
    ];

    return rows
        .where((r) => r.$3 != null && r.$3!.isNotEmpty)
        .map((r) => Padding(
              padding: const EdgeInsets.only(bottom: 10),
              child: Row(
                children: [
                  Icon(r.$1, size: 16, color: AppTheme.textSecondary),
                  const SizedBox(width: 10),
                  SizedBox(
                    width: 72,
                    child: Text(
                      r.$2,
                      style: const TextStyle(
                          fontSize: 12,
                          color: AppTheme.textSecondary,
                          fontWeight: FontWeight.w500),
                    ),
                  ),
                  Expanded(
                    child: Text(
                      r.$3!,
                      style: const TextStyle(
                          fontSize: 13, color: AppTheme.textPrimary),
                    ),
                  ),
                ],
              ),
            ))
        .toList();
  }
}

// ── Final step: All Done! ─────────────────────────────────────────────────────

class _DoneStep extends StatelessWidget {
  final bool isLoading;
  final VoidCallback onFinish;

  const _DoneStep({required this.isLoading, required this.onFinish});

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.center,
        children: [
          const SizedBox(height: 32),
          Container(
            width: 88,
            height: 88,
            decoration: BoxDecoration(
              color: AppTheme.success.withOpacity(0.12),
              shape: BoxShape.circle,
            ),
            child: const Icon(
              Icons.check_circle_rounded,
              color: AppTheme.success,
              size: 48,
            ),
          ),
          const SizedBox(height: 24),
          Text(
            'You\'re All Set!',
            style: Theme.of(context).textTheme.headlineMedium?.copyWith(
              fontWeight: FontWeight.w800,
              color: AppTheme.textPrimary,
              letterSpacing: -0.5,
            ),
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: 12),
          const Text(
            'Your account setup is complete. Welcome to AR Society — your smart society management platform.',
            style: TextStyle(
              color: AppTheme.textSecondary,
              fontSize: 15,
              height: 1.5,
            ),
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: 32),
          _QuickTipsCard(),
          const SizedBox(height: 32),
          SizedBox(
            width: double.infinity,
            child: ElevatedButton.icon(
              onPressed: isLoading ? null : onFinish,
              icon: isLoading
                  ? const SizedBox(
                      width: 18,
                      height: 18,
                      child: CircularProgressIndicator(
                          strokeWidth: 2, color: Colors.white),
                    )
                  : const Icon(Icons.dashboard_rounded),
              label: const Text('Go to Dashboard'),
            ),
          ),
        ],
      ),
    );
  }
}

class _QuickTipsCard extends StatelessWidget {
  static const _tips = [
    (Icons.people_outline_rounded,   'Add your residents and assign flats'),
    (Icons.security_rounded,         'Configure security and gate access'),
    (Icons.receipt_long_outlined,    'Set up billing and maintenance charges'),
    (Icons.campaign_outlined,        'Post notices for your community'),
  ];

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
          const Text(
            'What\'s Next?',
            style: TextStyle(
              fontWeight: FontWeight.w700,
              fontSize: 15,
              color: AppTheme.textPrimary,
            ),
          ),
          const SizedBox(height: 14),
          ..._tips.map(
            (tip) => Padding(
              padding: const EdgeInsets.only(bottom: 12),
              child: Row(
                children: [
                  Container(
                    width: 36,
                    height: 36,
                    decoration: BoxDecoration(
                      color: AppTheme.primary.withOpacity(0.08),
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: Icon(tip.$1, color: AppTheme.primary, size: 18),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Text(
                      tip.$2,
                      style: const TextStyle(
                        fontSize: 13,
                        color: AppTheme.textPrimary,
                        height: 1.4,
                      ),
                    ),
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
