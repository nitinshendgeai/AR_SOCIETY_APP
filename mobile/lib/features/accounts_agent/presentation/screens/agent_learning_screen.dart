import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/motion/loading.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/accounts_agent/data/accounts_agent_api.dart';
import 'package:ar_society_app/features/accounts_agent/presentation/providers/accounts_agent_providers.dart';
import 'package:ar_society_app/features/accounts_agent/presentation/widgets/agent_widgets.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/shared/widgets/app_form.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';

/// What the agent has learned from the last three months of the society's own books, and the settings that tune it.
class AgentLearningScreen extends ConsumerStatefulWidget {
  const AgentLearningScreen({super.key});

  @override
  ConsumerState<AgentLearningScreen> createState() => _AgentLearningScreenState();
}

class _AgentLearningScreenState extends ConsumerState<AgentLearningScreen> {
  bool _busy = false;

  Future<void> _do(Future<void> Function() job, String done) async {
    setState(() => _busy = true);
    try {
      await job();
      invalidateAgent(ref);
      if (mounted) AppToast.success(context, done);
    } catch (e) {
      if (mounted) showErrorToast(context, e);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _editThresholds(AgentSettings s) async {
    final z = TextEditingController(text: s.zThreshold.toString());
    final tol = TextEditingController(text: s.recurringTolerancePct.toString());
    final dup = TextEditingController(text: s.duplicateWindowDays.toString());
    var sev = s.notifyMinSeverity;
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setS) => AlertDialog(
          title: const Text('Detection settings'),
          content: SingleChildScrollView(
            child: Column(mainAxisSize: MainAxisSize.min, children: [
              TextField(controller: z, keyboardType: TextInputType.number, decoration: const InputDecoration(labelText: 'Outlier threshold (modified z-score, 2.5 – 6)', helperText: '3.5 is the standard for "potential outlier"')),
              TextField(controller: tol, keyboardType: TextInputType.number, decoration: const InputDecoration(labelText: 'Recurring expense tolerance (%)')),
              TextField(controller: dup, keyboardType: TextInputType.number, decoration: const InputDecoration(labelText: 'Duplicate window (days)')),
              const SizedBox(height: 8),
              DropdownButtonFormField<String>(
                value: sev,
                decoration: const InputDecoration(labelText: 'Notify me from this severity'),
                items: [for (final x in severities) DropdownMenuItem(value: x, child: Text(titleCase(x)))],
                onChanged: (v) => setS(() => sev = v ?? sev),
              ),
            ]),
          ),
          actions: [
            TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancel')),
            FilledButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('Save')),
          ],
        ),
      ),
    );
    if (ok != true) return;
    await _do(
        () async {
          await ref.read(accountsAgentApiProvider).updateSettings(
                zThreshold: double.tryParse(z.text),
                recurringTolerancePct: double.tryParse(tol.text),
                duplicateWindowDays: int.tryParse(dup.text),
                notifyMinSeverity: sev,
              );
        },
        'Settings saved');
  }

  @override
  Widget build(BuildContext context) {
    final mayEdit = ref.watch(currentUserProvider)?.isAdminOrCommittee ?? false;
    final status = ref.watch(agentLearningStatusProvider);
    final settings = ref.watch(agentSettingsProvider);
    final history = ref.watch(agentLearningHistoryProvider);
    return AppPage(
      title: 'Learning & settings',
      maxWidth: 960,
      body: RefreshIndicator(
        onRefresh: () async => invalidateAgent(ref),
        child: status.when(
          loading: () => const AppLoader(),
          error: (e, _) => AppErrorState(message: friendlyErrorMessage(e), onRetry: () => ref.invalidate(agentLearningStatusProvider)),
          data: (l) {
            final run = l.lastRun;
            return ListView(padding: const EdgeInsets.fromLTRB(16, 12, 16, 96), children: [
              AgentCard(
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  const Text('Learning window', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700)),
                  const SizedBox(height: 6),
                  Text('${day(l.windowStart)} – ${day(l.windowEnd)} · the most recent 3 months, rolling. Older records are never changed or hidden.',
                      style: const TextStyle(fontSize: 13.5, color: AppTheme.textSecondary, height: 1.4)),
                  const SizedBox(height: 12),
                  Text('Learning confidence: ${titleCase(run?.confidenceLabel ?? 'none')}', style: const TextStyle(fontWeight: FontWeight.w600)),
                  const SizedBox(height: 6),
                  LinearProgressIndicator(value: run?.confidenceScore ?? 0, minHeight: 8, borderRadius: BorderRadius.circular(6)),
                  const SizedBox(height: 8),
                  Text(l.message, style: TextStyle(fontSize: 13, color: l.limited ? AppTheme.warning : AppTheme.textSecondary)),
                ]),
              ),
              const AgentSectionTitle('Data coverage'),
              AgentCard(
                child: run == null
                    ? const Text('The agent has not learned from this society yet.')
                    : Column(children: [
                        KeyValue('Last successful run', stamp(run.finishedAt)),
                        KeyValue('Vouchers learned from', '${run.voucherCount}'),
                        KeyValue('Months with activity', '${run.monthsCovered}'),
                        KeyValue('Days covered', '${run.daysCovered} of about 90'),
                        KeyValue('Patterns learned', '${run.patternCount}'),
                      ]),
              ),
              if (mayEdit) ...[
                const SizedBox(height: 12),
                FilledButton.icon(
                  onPressed: _busy ? null : () => _do(() async { await ref.read(accountsAgentApiProvider).runLearning(); }, 'Learning completed'),
                  icon: const Icon(Icons.school_outlined),
                  label: const Text('Learn again now'),
                ),
              ],
              const AgentSectionTitle('Monitoring'),
              settings.when(
                loading: () => const AppLoader(),
                error: (e, _) => AppErrorState(message: friendlyErrorMessage(e), compact: true, onRetry: () => ref.invalidate(agentSettingsProvider)),
                data: (s) => AgentCard(
                  child: Column(children: [
                    SwitchListTile(
                      contentPadding: EdgeInsets.zero,
                      title: const Text('Monitor new transactions'),
                      subtitle: Text(s.monitoringEnabled ? 'Every committed voucher is checked in the background.' : 'Off — new vouchers are not being checked.'),
                      value: s.monitoringEnabled,
                      onChanged: (!mayEdit || _busy) ? null : (v) => _do(() async { await ref.read(accountsAgentApiProvider).setMonitoring(v); }, v ? 'Monitoring on' : 'Monitoring off'),
                    ),
                    const Divider(),
                    KeyValue('Outlier threshold', '${s.zThreshold} (modified z-score)'),
                    KeyValue('Recurring tolerance', '${s.recurringTolerancePct}%'),
                    KeyValue('Duplicate window', '${s.duplicateWindowDays} days'),
                    KeyValue('Notify from', titleCase(s.notifyMinSeverity)),
                    if (mayEdit) Align(alignment: Alignment.centerLeft, child: TextButton(onPressed: _busy ? null : () => _editThresholds(s), child: const Text('Change settings'))),
                  ]),
                ),
              ),
              const AgentSectionTitle('Learning history'),
              history.when(
                loading: () => const AppLoader(),
                error: (e, _) => AppErrorState(message: friendlyErrorMessage(e), compact: true, onRetry: () => ref.invalidate(agentLearningHistoryProvider)),
                data: (rows) => rows.isEmpty
                    ? const AgentCard(child: Text('No learning runs yet.'))
                    : Column(children: [
                        for (final r in rows)
                          Padding(
                            padding: const EdgeInsets.only(bottom: 8),
                            child: AgentCard(
                              child: Row(children: [
                                Expanded(child: Text('${stamp(r.finishedAt)} · ${r.voucherCount} vouchers', style: const TextStyle(fontSize: 13.5))),
                                Text('${titleCase(r.status)} · ${titleCase(r.confidenceLabel)}', style: const TextStyle(fontSize: 12.5, color: AppTheme.textSecondary)),
                              ]),
                            ),
                          ),
                      ]),
              ),
            ]);
          },
        ),
      ),
    );
  }
}
