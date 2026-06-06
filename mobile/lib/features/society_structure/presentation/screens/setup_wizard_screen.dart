import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:ar_society_app/core/router/app_router.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/society_settings/presentation/providers/society_settings_providers.dart';
import 'package:ar_society_app/features/society_structure/presentation/providers/structure_providers.dart';

class SetupWizardScreen extends ConsumerStatefulWidget {
  const SetupWizardScreen({super.key});

  @override
  ConsumerState<SetupWizardScreen> createState() => _SetupWizardScreenState();
}

class _SetupWizardScreenState extends ConsumerState<SetupWizardScreen> {
  int _step = 0;

  static const _steps = [
    _WizardStep(
      icon: Icons.apartment_rounded,
      title: 'Society Profile',
      description: 'Set your society name, address, registration, and contact details.',
      route: AppRoutes.societySettings,
      color: AppTheme.primary,
    ),
    _WizardStep(
      icon: Icons.domain_rounded,
      title: 'Add Wings',
      description: 'Create the wings or blocks of your society (e.g. A Block, Tower 1).',
      route: AppRoutes.wingsList,
      color: AppTheme.secondary,
    ),
    _WizardStep(
      icon: Icons.layers_rounded,
      title: 'Add Floors',
      description: 'Define the floors in each wing to organise flat assignment.',
      route: AppRoutes.wingsList,
      color: AppTheme.warning,
    ),
    _WizardStep(
      icon: Icons.door_front_door_rounded,
      title: 'Add Flats',
      description: 'Register all flats with their type, area, and occupancy status.',
      route: AppRoutes.flatsList,
      color: AppTheme.success,
    ),
    _WizardStep(
      icon: Icons.people_rounded,
      title: 'Users & Roles',
      description: 'Create committee members, security staff, and resident accounts.',
      route: AppRoutes.usersList,
      color: AppTheme.primary,
    ),
  ];

  @override
  Widget build(BuildContext context) {
    final societyAsync = ref.watch(currentSocietyProvider);
    final wingsAsync   = ref.watch(wingsProvider);
    final flatsAsync   = ref.watch(flatsBySocietyProvider);

    final completions = [
      societyAsync.valueOrNull?.setupCompletionPercentage != null &&
          societyAsync.valueOrNull!.setupCompletionPercentage > 0,
      (wingsAsync.valueOrNull?.length ?? 0) > 0,
      (wingsAsync.valueOrNull?.any((w) => w.floorCount > 0) ?? false),
      (flatsAsync.valueOrNull?.length ?? 0) > 0,
      false,
    ];

    final completedCount = completions.where((c) => c).length;
    final percent = (completedCount / _steps.length * 100).round();

    return Scaffold(
      backgroundColor: AppTheme.surface,
      appBar: AppBar(title: const Text('Society Setup Wizard')),
      body: ListView(
        padding: const EdgeInsets.all(20),
        children: [
          _ProgressHeader(percent: percent, completed: completedCount, total: _steps.length),
          const SizedBox(height: 24),
          ...List.generate(_steps.length, (i) {
            final step = _steps[i];
            final done = completions[i];
            return _StepCard(
              step: step,
              index: i,
              isSelected: _step == i,
              isDone: done,
              isLast: i == _steps.length - 1,
              onTap: () => setState(() => _step = i),
              onGo: () => context.push(step.route),
            );
          }),
          const SizedBox(height: 20),
          if (percent == 100) ...[
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: AppTheme.success.withOpacity(0.08),
                borderRadius: BorderRadius.circular(14),
                border: Border.all(
                    color: AppTheme.success.withOpacity(0.2)),
              ),
              child: Row(children: [
                const Icon(Icons.check_circle_rounded,
                    color: AppTheme.success, size: 26),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: const [
                      Text('Setup Complete!',
                          style: TextStyle(
                              fontWeight: FontWeight.w700,
                              color: AppTheme.success,
                              fontSize: 15)),
                      SizedBox(height: 2),
                      Text('Your society is ready to use all features.',
                          style: TextStyle(
                              fontSize: 12,
                              color: AppTheme.textSecondary)),
                    ],
                  ),
                ),
              ]),
            ),
            const SizedBox(height: 16),
            SizedBox(
              height: 48,
              child: ElevatedButton(
                onPressed: () => context.go(AppRoutes.adminHome),
                child: const Text('Go to Dashboard'),
              ),
            ),
          ],
        ],
      ),
    );
  }
}

class _ProgressHeader extends StatelessWidget {
  final int percent;
  final int completed;
  final int total;
  const _ProgressHeader(
      {required this.percent,
      required this.completed,
      required this.total});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          colors: [AppTheme.primary, AppTheme.primaryDark],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(16),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('Setup Progress',
              style: TextStyle(
                  color: Colors.white,
                  fontSize: 16,
                  fontWeight: FontWeight.w700)),
          const SizedBox(height: 4),
          Text('$completed of $total steps completed',
              style: TextStyle(
                  color: Colors.white.withOpacity(0.75), fontSize: 13)),
          const SizedBox(height: 14),
          ClipRRect(
            borderRadius: BorderRadius.circular(6),
            child: LinearProgressIndicator(
              value: percent / 100,
              minHeight: 8,
              backgroundColor: Colors.white.withOpacity(0.25),
              valueColor: const AlwaysStoppedAnimation<Color>(Colors.white),
            ),
          ),
          const SizedBox(height: 8),
          Align(
            alignment: Alignment.centerRight,
            child: Text('$percent%',
                style: const TextStyle(
                    color: Colors.white,
                    fontWeight: FontWeight.w700,
                    fontSize: 13)),
          ),
        ],
      ),
    );
  }
}

@immutable
class _WizardStep {
  final IconData icon;
  final String title;
  final String description;
  final String route;
  final Color color;
  const _WizardStep({
    required this.icon,
    required this.title,
    required this.description,
    required this.route,
    required this.color,
  });
}

class _StepCard extends StatelessWidget {
  final _WizardStep step;
  final int index;
  final bool isSelected;
  final bool isDone;
  final bool isLast;
  final VoidCallback onTap;
  final VoidCallback onGo;

  const _StepCard({
    required this.step,
    required this.index,
    required this.isSelected,
    required this.isDone,
    required this.isLast,
    required this.onTap,
    required this.onGo,
  });

  @override
  Widget build(BuildContext context) {
    return IntrinsicHeight(
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Stepper connector
          Column(children: [
            Container(
              width: 32,
              height: 32,
              decoration: BoxDecoration(
                color: isDone
                    ? AppTheme.success
                    : isSelected
                        ? step.color
                        : AppTheme.border,
                shape: BoxShape.circle,
              ),
              child: Center(
                child: isDone
                    ? const Icon(Icons.check, color: Colors.white, size: 16)
                    : Text('${index + 1}',
                        style: TextStyle(
                            fontSize: 13,
                            fontWeight: FontWeight.w700,
                            color: isSelected
                                ? Colors.white
                                : AppTheme.textSecondary)),
              ),
            ),
            if (!isLast)
              Expanded(
                child: Container(
                  width: 2,
                  color: isDone
                      ? AppTheme.success.withOpacity(0.3)
                      : AppTheme.border,
                ),
              ),
          ]),
          const SizedBox(width: 14),
          Expanded(
            child: Padding(
              padding: const EdgeInsets.only(bottom: 16),
              child: GestureDetector(
                onTap: onTap,
                child: AnimatedContainer(
                  duration: const Duration(milliseconds: 200),
                  padding: const EdgeInsets.all(14),
                  decoration: BoxDecoration(
                    color: isSelected
                        ? step.color.withOpacity(0.06)
                        : AppTheme.cardBg,
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(
                      color: isSelected
                          ? step.color.withOpacity(0.3)
                          : AppTheme.border,
                    ),
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(children: [
                        Icon(step.icon, color: step.color, size: 18),
                        const SizedBox(width: 8),
                        Expanded(
                          child: Text(step.title,
                              style: const TextStyle(
                                  fontSize: 14,
                                  fontWeight: FontWeight.w600,
                                  color: AppTheme.textPrimary)),
                        ),
                        if (isDone)
                          Container(
                            padding: const EdgeInsets.symmetric(
                                horizontal: 8, vertical: 2),
                            decoration: BoxDecoration(
                              color: AppTheme.success.withOpacity(0.12),
                              borderRadius: BorderRadius.circular(6),
                            ),
                            child: const Text('Done',
                                style: TextStyle(
                                    fontSize: 10,
                                    fontWeight: FontWeight.w600,
                                    color: AppTheme.success)),
                          ),
                      ]),
                      const SizedBox(height: 6),
                      Text(step.description,
                          style: const TextStyle(
                              fontSize: 12,
                              color: AppTheme.textSecondary)),
                      if (isSelected) ...[
                        const SizedBox(height: 10),
                        Align(
                          alignment: Alignment.centerRight,
                          child: TextButton.icon(
                            onPressed: onGo,
                            icon: Icon(Icons.arrow_forward_rounded,
                                size: 14, color: step.color),
                            label: Text(isDone ? 'View / Edit' : 'Start',
                                style: TextStyle(
                                    fontSize: 12, color: step.color)),
                          ),
                        ),
                      ],
                    ],
                  ),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}
