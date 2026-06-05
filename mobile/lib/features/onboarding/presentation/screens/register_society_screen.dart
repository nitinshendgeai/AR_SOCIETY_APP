import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/core/router/app_router.dart';
import 'package:ar_society_app/features/onboarding/presentation/providers/onboarding_providers.dart';
import 'package:ar_society_app/features/onboarding/domain/registration_result.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';

class RegisterSocietyScreen extends ConsumerStatefulWidget {
  const RegisterSocietyScreen({super.key});

  @override
  ConsumerState<RegisterSocietyScreen> createState() =>
      _RegisterSocietyScreenState();
}

class _RegisterSocietyScreenState
    extends ConsumerState<RegisterSocietyScreen> {
  final _formKey   = GlobalKey<FormState>();
  final _pageCtrl  = PageController();
  int _page = 0;

  // Page 1 — Society info
  final _nameCtrl  = TextEditingController();
  final _codeCtrl  = TextEditingController();
  final _cityCtrl  = TextEditingController();
  final _stateCtrl = TextEditingController();

  // Page 2 — Contact
  final _personCtrl  = TextEditingController();
  final _emailCtrl   = TextEditingController();
  final _mobileCtrl  = TextEditingController();

  // Page 3 — Details
  int _totalWings = 1;
  int _totalFlats = 1;

  @override
  void dispose() {
    _pageCtrl.dispose();
    _nameCtrl.dispose(); _codeCtrl.dispose();
    _cityCtrl.dispose(); _stateCtrl.dispose();
    _personCtrl.dispose(); _emailCtrl.dispose(); _mobileCtrl.dispose();
    super.dispose();
  }

  @override
  void initState() {
    super.initState();
    // Auto-uppercase society code
    _codeCtrl.addListener(() {
      final upper = _codeCtrl.text.toUpperCase();
      if (_codeCtrl.text != upper) {
        _codeCtrl.value = _codeCtrl.value.copyWith(
          text: upper,
          selection: TextSelection.collapsed(offset: upper.length),
        );
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(onboardingProvider);

    ref.listen<OnboardingState>(onboardingProvider, (_, next) {
      if (next is OnboardingSuccess) {
        context.go(AppRoutes.trialSuccess, extra: next.result);
      }
    });

    final isLoading = state is OnboardingLoading;

    return Scaffold(
      backgroundColor: AppTheme.surface,
      appBar: AppBar(
        title: const Text('Register Society'),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_ios_new_rounded),
          onPressed: () {
            if (_page > 0) {
              _goPage(_page - 1);
            } else {
              context.pop();
            }
          },
        ),
      ),
      body: AppLoadingOverlay(
        isLoading: isLoading,
        child: Column(
          children: [
            _StepIndicator(current: _page, total: 3),
            Expanded(
              child: PageView(
                controller: _pageCtrl,
                physics: const NeverScrollableScrollPhysics(),
                children: [
                  _Page1(
                    nameCtrl:  _nameCtrl,
                    codeCtrl:  _codeCtrl,
                    cityCtrl:  _cityCtrl,
                    stateCtrl: _stateCtrl,
                    onNext:    () => _goPage(1),
                  ),
                  _Page2(
                    personCtrl: _personCtrl,
                    emailCtrl:  _emailCtrl,
                    mobileCtrl: _mobileCtrl,
                    onNext:     () => _goPage(2),
                  ),
                  _Page3(
                    totalWings: _totalWings,
                    totalFlats: _totalFlats,
                    onWingsChanged: (v) => setState(() => _totalWings = v),
                    onFlatsChanged: (v) => setState(() => _totalFlats = v),
                    error: state is OnboardingError ? state.message : null,
                    onSubmit: _submit,
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  void _goPage(int page) {
    setState(() => _page = page);
    _pageCtrl.animateToPage(
      page,
      duration: const Duration(milliseconds: 300),
      curve: Curves.easeInOut,
    );
  }

  Future<void> _submit() async {
    await ref.read(onboardingProvider.notifier).register(
          societyName:       _nameCtrl.text.trim(),
          societyCode:       _codeCtrl.text.trim(),
          contactPersonName: _personCtrl.text.trim(),
          contactEmail:      _emailCtrl.text.trim(),
          contactMobile:     _mobileCtrl.text.trim(),
          city:              _cityCtrl.text.trim(),
          state:             _stateCtrl.text.trim(),
          totalWings:        _totalWings,
          totalFlats:        _totalFlats,
        );
  }
}

// ── Step indicator ─────────────────────────────────────────────────────────────

class _StepIndicator extends StatelessWidget {
  final int current;
  final int total;
  const _StepIndicator({required this.current, required this.total});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 12),
      child: Row(
        children: List.generate(total, (i) {
          final active   = i == current;
          final done     = i < current;
          return Expanded(
            child: Container(
              margin: const EdgeInsets.symmetric(horizontal: 3),
              height: 4,
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(2),
                color: (active || done)
                    ? AppTheme.primary
                    : AppTheme.border,
              ),
            ),
          );
        }),
      ),
    );
  }
}

// ── Page 1: Society info ───────────────────────────────────────────────────────

class _Page1 extends StatelessWidget {
  final TextEditingController nameCtrl, codeCtrl, cityCtrl, stateCtrl;
  final VoidCallback onNext;

  const _Page1({
    required this.nameCtrl,
    required this.codeCtrl,
    required this.cityCtrl,
    required this.stateCtrl,
    required this.onNext,
  });

  @override
  Widget build(BuildContext context) {
    final formKey = GlobalKey<FormState>();
    return SingleChildScrollView(
      padding: const EdgeInsets.all(24),
      child: Form(
        key: formKey,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _SectionTitle('Society Details',
                'Tell us about your residential society'),
            const SizedBox(height: 24),
            AppTextField(
              label: 'Society Name',
              hint: 'e.g. Sunrise Heights',
              controller: nameCtrl,
              validator: (v) => (v == null || v.trim().length < 3)
                  ? 'Enter a valid society name'
                  : null,
            ),
            const SizedBox(height: 16),
            AppTextField(
              label: 'Society Code',
              hint: 'e.g. SRH001 (3-10 chars)',
              controller: codeCtrl,
              validator: (v) {
                if (v == null || v.trim().isEmpty) return 'Code is required';
                if (!RegExp(r'^[A-Z0-9]{3,10}$').hasMatch(v.trim())) {
                  return 'Use 3-10 uppercase letters/numbers only';
                }
                return null;
              },
            ),
            const SizedBox(height: 16),
            AppTextField(
              label: 'City',
              hint: 'e.g. Mumbai',
              controller: cityCtrl,
              validator: (v) =>
                  (v == null || v.trim().isEmpty) ? 'City is required' : null,
            ),
            const SizedBox(height: 16),
            AppTextField(
              label: 'State',
              hint: 'e.g. Maharashtra',
              controller: stateCtrl,
              validator: (v) =>
                  (v == null || v.trim().isEmpty) ? 'State is required' : null,
            ),
            const SizedBox(height: 32),
            AppPrimaryButton(
              label: 'Continue',
              icon: Icons.arrow_forward_rounded,
              onPressed: () {
                if (formKey.currentState!.validate()) onNext();
              },
            ),
          ],
        ),
      ),
    );
  }
}

// ── Page 2: Contact info ───────────────────────────────────────────────────────

class _Page2 extends StatelessWidget {
  final TextEditingController personCtrl, emailCtrl, mobileCtrl;
  final VoidCallback onNext;

  const _Page2({
    required this.personCtrl,
    required this.emailCtrl,
    required this.mobileCtrl,
    required this.onNext,
  });

  @override
  Widget build(BuildContext context) {
    final formKey = GlobalKey<FormState>();
    return SingleChildScrollView(
      padding: const EdgeInsets.all(24),
      child: Form(
        key: formKey,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _SectionTitle(
                'Contact Details', 'Who is the primary contact person?'),
            const SizedBox(height: 24),
            AppTextField(
              label: 'Contact Person Name',
              hint: 'e.g. Rajesh Kumar',
              controller: personCtrl,
              validator: (v) => (v == null || v.trim().isEmpty)
                  ? 'Contact name is required'
                  : null,
            ),
            const SizedBox(height: 16),
            AppTextField(
              label: 'Email Address',
              hint: 'e.g. rajesh@example.com',
              controller: emailCtrl,
              keyboardType: TextInputType.emailAddress,
              validator: (v) {
                if (v == null || v.trim().isEmpty) return 'Email is required';
                if (!v.contains('@') || !v.contains('.')) {
                  return 'Enter a valid email address';
                }
                return null;
              },
            ),
            const SizedBox(height: 16),
            AppTextField(
              label: 'Mobile Number',
              hint: '10-digit number',
              controller: mobileCtrl,
              keyboardType: TextInputType.phone,
              validator: (v) {
                if (v == null || v.trim().isEmpty) return 'Mobile is required';
                final digits = v.replaceAll(RegExp(r'\D'), '');
                if (digits.length != 10) {
                  return 'Enter a valid 10-digit mobile number';
                }
                return null;
              },
            ),
            const SizedBox(height: 32),
            AppPrimaryButton(
              label: 'Continue',
              icon: Icons.arrow_forward_rounded,
              onPressed: () {
                if (formKey.currentState!.validate()) onNext();
              },
            ),
          ],
        ),
      ),
    );
  }
}

// ── Page 3: Society size + submit ──────────────────────────────────────────────

class _Page3 extends StatelessWidget {
  final int totalWings;
  final int totalFlats;
  final ValueChanged<int> onWingsChanged;
  final ValueChanged<int> onFlatsChanged;
  final String? error;
  final VoidCallback onSubmit;

  const _Page3({
    required this.totalWings,
    required this.totalFlats,
    required this.onWingsChanged,
    required this.onFlatsChanged,
    required this.onSubmit,
    this.error,
  });

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _SectionTitle('Society Size', 'Approximate wing and flat count'),
          const SizedBox(height: 24),
          _Counter(
            label: 'Total Wings',
            value: totalWings,
            min: 1,
            max: 100,
            onChanged: onWingsChanged,
          ),
          const SizedBox(height: 20),
          _Counter(
            label: 'Total Flats',
            value: totalFlats,
            min: 1,
            max: 10000,
            step: 10,
            onChanged: onFlatsChanged,
          ),
          const SizedBox(height: 24),
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: AppTheme.primary.withOpacity(0.06),
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: AppTheme.primary.withOpacity(0.2)),
            ),
            child: Row(
              children: [
                Icon(Icons.info_outline_rounded,
                    color: AppTheme.primary, size: 18),
                const SizedBox(width: 10),
                Expanded(
                  child: Text(
                    'You get a 30-day free trial with up to 50 users and 100 flats.',
                    style: TextStyle(
                      fontSize: 13,
                      color: AppTheme.textSecondary,
                    ),
                  ),
                ),
              ],
            ),
          ),
          if (error != null) ...[
            const SizedBox(height: 16),
            AppErrorBanner(message: error!),
          ],
          const SizedBox(height: 32),
          AppPrimaryButton(
            label: 'Start Free Trial',
            icon: Icons.rocket_launch_rounded,
            onPressed: onSubmit,
          ),
          const SizedBox(height: 16),
          Center(
            child: Text(
              'By registering you agree to our Terms & Conditions.',
              style: TextStyle(fontSize: 12, color: AppTheme.textSecondary),
              textAlign: TextAlign.center,
            ),
          ),
        ],
      ),
    );
  }
}

// ── Helpers ───────────────────────────────────────────────────────────────────

class _SectionTitle extends StatelessWidget {
  final String title;
  final String subtitle;
  const _SectionTitle(this.title, this.subtitle);

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(title,
            style: Theme.of(context).textTheme.titleLarge?.copyWith(
                  fontWeight: FontWeight.w700,
                  color: AppTheme.textPrimary,
                )),
        const SizedBox(height: 4),
        Text(subtitle,
            style: TextStyle(
                color: AppTheme.textSecondary, fontSize: 14)),
      ],
    );
  }
}

class _Counter extends StatelessWidget {
  final String label;
  final int value;
  final int min;
  final int max;
  final int step;
  final ValueChanged<int> onChanged;

  const _Counter({
    required this.label,
    required this.value,
    required this.min,
    required this.max,
    required this.onChanged,
    this.step = 1,
  });

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Expanded(
          child: Text(label,
              style: const TextStyle(
                  fontWeight: FontWeight.w500,
                  color: AppTheme.textPrimary)),
        ),
        IconButton(
          icon: const Icon(Icons.remove_circle_outline_rounded),
          color: value > min ? AppTheme.primary : AppTheme.textSecondary,
          onPressed: value > min ? () => onChanged(value - step) : null,
        ),
        SizedBox(
          width: 48,
          child: Text(
            '$value',
            textAlign: TextAlign.center,
            style: const TextStyle(
                fontSize: 18, fontWeight: FontWeight.w700,
                color: AppTheme.textPrimary),
          ),
        ),
        IconButton(
          icon: const Icon(Icons.add_circle_outline_rounded),
          color: value < max ? AppTheme.primary : AppTheme.textSecondary,
          onPressed: value < max ? () => onChanged(value + step) : null,
        ),
      ],
    );
  }
}
