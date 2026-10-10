import 'package:dio/dio.dart';
import 'package:ar_society_app/core/motion/loading.dart';
import 'package:flutter/material.dart';
import 'package:ar_society_app/core/l10n/app_locale.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/features/automation/data/automation_api.dart';
import 'package:ar_society_app/shared/widgets/app_form.dart';

/// Reminders and alerts that run on their own: what each one does, whether it is on, what it did last, and a
/// button to run it now.
class AutomationScreen extends ConsumerStatefulWidget {
  const AutomationScreen({super.key});

  @override
  ConsumerState<AutomationScreen> createState() => _AutomationScreenState();
}

class _AutomationScreenState extends ConsumerState<AutomationScreen> {
  String? _busy; // job key being switched or run

  String get _sid => ref.read(currentUserProvider)?.societyId ?? '';

  String _problem(Object e) {
    if (e is DioException) {
      final d = e.response?.data;
      if (d is Map && d['detail'] is String) return d['detail'] as String;
    }
    return 'That did not work. Please try again.';
  }

  void _say(String m) => ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(m)));

  Future<void> _toggle(AutomationJob job, bool on) async {
    setState(() => _busy = job.key);
    try {
      await ref.read(automationApiProvider).update(_sid, {job.key: on});
      ref.invalidate(automationProvider(_sid));
    } catch (e) {
      _say(_problem(e));
    } finally {
      if (mounted) setState(() => _busy = null);
    }
  }

  Future<void> _run(AutomationJob job) async {
    setState(() => _busy = job.key);
    try {
      final summary = await ref.read(automationApiProvider).runNow(_sid, job.key);
      ref.invalidate(automationProvider(_sid));
      _say(summary);
    } catch (e) {
      _say(_problem(e));
    } finally {
      if (mounted) setState(() => _busy = null);
    }
  }

  Future<void> _setNumber(String field, int value) async {
    try {
      await ref.read(automationApiProvider).update(_sid, {field: value});
      ref.invalidate(automationProvider(_sid));
    } catch (e) {
      _say(_problem(e));
    }
  }

  @override
  Widget build(BuildContext context) {
    final sid = ref.watch(currentUserProvider)?.societyId ?? '';
    final async = ref.watch(automationProvider(sid));
    return AppPage(
      title: 'Automatic tasks',
      body: async.when(
        loading: () => const AppLoader(),
        error: (e, _) => Center(
          child: Padding(
            padding: const EdgeInsets.all(24),
            child: Column(mainAxisSize: MainAxisSize.min, children: [
              const Text('Could not load the automatic tasks.'),
              const SizedBox(height: 10),
              OutlinedButton(onPressed: () => ref.invalidate(automationProvider(sid)), child: const Text('Try again')),
            ]),
          ),
        ),
        data: (o) => ListView(
          padding: const EdgeInsets.fromLTRB(16, 12, 16, 32),
          children: [
            const Padding(
              padding: EdgeInsets.only(bottom: 14),
              child: Text(
                'These run by themselves each morning (weekly ones once a week). Switch off any you do not want.',
                style: TextStyle(fontSize: 13, color: AppTheme.textSecondary, height: 1.4),
              ),
            ),
            for (final j in o.jobs) ...[
              _JobCard(
                job: j,
                busy: _busy == j.key,
                onToggle: (v) => _toggle(j, v),
                onRun: () => _run(j),
                extra: j.key == 'dues_reminders' && j.enabled
                    ? _DuesSettings(
                        everyDays: o.reminderEveryDays,
                        minMonths: o.reminderMinMonths,
                        onEvery: (v) => _setNumber('reminder_every_days', v),
                        onMin: (v) => _setNumber('reminder_min_months', v),
                      )
                    : null,
              ),
              const SizedBox(height: 12),
            ],
          ],
        ),
      ),
    );
  }
}

class _JobCard extends StatelessWidget {
  final AutomationJob job;
  final bool busy;
  final ValueChanged<bool> onToggle;
  final VoidCallback onRun;
  final Widget? extra;
  const _JobCard({required this.job, required this.busy, required this.onToggle, required this.onRun, this.extra});

  @override
  Widget build(BuildContext context) {
    final run = job.lastRun;
    final failed = run?.status == 'error';
    return DecoratedBox(
      decoration: BoxDecoration(
        color: AppTheme.cardBg,
        borderRadius: BorderRadius.circular(AppTheme.radiusL),
        boxShadow: AppTheme.cardShadow,
      ),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            Expanded(
              child: Text(job.title,
                  style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w700, color: AppTheme.textPrimary)),
            ),
            Switch(value: job.enabled, onChanged: busy ? null : onToggle),
          ]),
          Text(job.description, style: const TextStyle(fontSize: 13, color: AppTheme.textSecondary, height: 1.4)),
          const SizedBox(height: 10),
          Row(children: [
            _Chip(job.schedule == 'weekly' ? 'Weekly' : 'Daily'),
            const Spacer(),
            TextButton(
              onPressed: busy ? null : onRun,
              child: busy
                  ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2))
                  : const Text('Run now'),
            ),
          ]),
          Text(
            run == null
                ? 'Has not run yet'
                : '${failed ? 'Failed' : 'Last run'} ${_when(run.at)}${run.manual ? ' (run by hand)' : ''}'
                    '${run.summary == null ? '' : ': ${run.summary}'}',
            style: TextStyle(fontSize: 12.5, height: 1.35, color: failed ? AppTheme.error : AppTheme.textSecondary),
          ),
          if (extra != null) ...[const Divider(height: 22), extra!],
        ]),
      ),
    );
  }

  static String _when(DateTime? d) => d == null ? '' : DateFormat('d MMM, h:mm a').format(d);
}

class _Chip extends StatelessWidget {
  final String text;
  const _Chip(this.text);
  @override
  Widget build(BuildContext context) => Container(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
        decoration: BoxDecoration(color: AppTheme.primary.withOpacity(0.10), borderRadius: BorderRadius.circular(6)),
        child: Text(text, style: const TextStyle(fontSize: 11.5, fontWeight: FontWeight.w600, color: AppTheme.primary)),
      );
}

class _DuesSettings extends StatelessWidget {
  final int everyDays, minMonths;
  final ValueChanged<int> onEvery, onMin;
  const _DuesSettings({required this.everyDays, required this.minMonths, required this.onEvery, required this.onMin});

  @override
  Widget build(BuildContext context) {
    return Column(children: [
      _Stepper(
        label: 'Remind a flat again after',
        value: everyDays,
        unit: everyDays == 1 ? 'day' : 'days',
        min: 1,
        max: 90,
        onChanged: onEvery,
      ),
      const SizedBox(height: 6),
      _Stepper(
        label: 'Only dues older than',
        value: minMonths,
        unit: minMonths == 1 ? 'month' : 'months',
        min: 0,
        max: 24,
        onChanged: onMin,
      ),
    ]);
  }
}

class _Stepper extends StatelessWidget {
  final String label, unit;
  final int value, min, max;
  final ValueChanged<int> onChanged;
  const _Stepper({
    required this.label,
    required this.value,
    required this.unit,
    required this.min,
    required this.max,
    required this.onChanged,
  });

  @override
  Widget build(BuildContext context) {
    return Row(children: [
      Expanded(child: Text(label, style: const TextStyle(fontSize: 13, color: AppTheme.textPrimary))),
      IconButton(
          visualDensity: VisualDensity.compact,
          onPressed: value <= min ? null : () => onChanged(value - 1),
          icon: const Icon(Icons.remove_circle_outline_rounded)),
      SizedBox(
        width: 74,
        child: Text('$value $unit', textAlign: TextAlign.center, style: const TextStyle(fontWeight: FontWeight.w600)),
      ),
      IconButton(
          visualDensity: VisualDensity.compact,
          onPressed: value >= max ? null : () => onChanged(value + 1),
          icon: const Icon(Icons.add_circle_outline_rounded)),
    ]);
  }
}
