import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/motion/loading.dart';
import 'package:ar_society_app/core/theme/design_tokens.dart';
import 'package:ar_society_app/features/accounts_agent/presentation/widgets/agent_hud.dart';
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
                initialValue: sev,
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

  Future<void> _editBudget(int current) async {
    final c = TextEditingController(text: '$current');
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Monthly AI token budget'),
        content: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
          const Text('The most tokens the agent may spend on AI wording in a calendar month. Past it, answers come from '
              'the bye-laws and books without AI. 0 means never call the AI. Your plan\'s allowance is the upper limit: '
              'a higher number here has no effect.'),
          const SizedBox(height: 12),
          TextField(
            controller: c,
            keyboardType: TextInputType.number,
            decoration: const InputDecoration(labelText: 'Tokens per month', helperText: 'A worded bye-law answer uses about 1,000–2,500'),
          ),
        ]),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancel')),
          FilledButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('Save')),
        ],
      ),
    );
    final v = int.tryParse(c.text.replaceAll(',', '').trim());
    c.dispose();
    if (ok != true || v == null || v < 0) return;
    await _do(() async { await ref.read(accountsAgentApiProvider).updateSettings(aiMonthlyTokenBudget: v); }, 'Budget saved');
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
          error: (e, _) => HudErrorState(message: friendlyErrorMessage(e), onRetry: () => ref.invalidate(agentLearningStatusProvider)),
          data: (l) {
            final run = l.lastRun;
            return ListView(padding: const EdgeInsets.fromLTRB(16, 12, 16, 96), children: [
              AgentCard(
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  const Text('Learning window', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700)),
                  const SizedBox(height: 6),
                  Text('${day(l.windowStart)} – ${day(l.windowEnd)} · the most recent 3 months, rolling. Older records are never changed or hidden.',
                      style: const TextStyle(fontSize: 13.5, color: Hud.dim, height: 1.4)),
                  const SizedBox(height: 12),
                  Text('Learning confidence: ${titleCase(run?.confidenceLabel ?? 'none')}', style: const TextStyle(fontWeight: FontWeight.w600)),
                  const SizedBox(height: 6),
                  LinearProgressIndicator(value: run?.confidenceScore ?? 0, minHeight: 8, borderRadius: BorderRadius.circular(6)),
                  const SizedBox(height: 8),
                  Text(l.message, style: TextStyle(fontSize: 13, color: l.limited ? Hud.amber : Hud.dim)),
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
                error: (e, _) => HudErrorState(message: friendlyErrorMessage(e), compact: true, onRetry: () => ref.invalidate(agentSettingsProvider)),
                data: (s) => AgentCard(
                  child: Column(children: [
                    SwitchListTile(
                      contentPadding: EdgeInsets.zero,
                      title: const Text('Monitor new transactions'),
                      subtitle: Text(s.monitoringEnabled ? 'Every committed voucher is checked in the background.' : 'Off — new vouchers are not being checked.'),
                      value: s.monitoringEnabled,
                      onChanged: (!mayEdit || _busy) ? null : (v) => _do(() async { await ref.read(accountsAgentApiProvider).setMonitoring(v); }, v ? 'Monitoring on' : 'Monitoring off'),
                    ),
                    SwitchListTile(
                      contentPadding: EdgeInsets.zero,
                      title: const Text('AI wording (Claude)'),
                      subtitle: Text(!s.aiConfigured
                          ? 'Not available: the server has no Anthropic API key. Bye-law answers list the matching clauses.'
                          : !s.aiIncluded
                              ? '${s.aiPlanReason ?? 'Your subscription does not include AI.'} Bye-law answers list the matching clauses.'
                              : s.aiProvider == 'anthropic'
                                  ? 'On: bye-law answers are worded by Claude from the clauses found, and entry descriptions are read by Claude. Nothing is posted or published without a person.'
                                  : 'Off: bye-law answers list the matching clauses; entries are filled from your choices and past postings.'),
                      value: s.aiProvider == 'anthropic' && s.aiIncluded,
                      onChanged: (!mayEdit || _busy || !s.aiConfigured || !s.aiIncluded)
                          ? null
                          : (v) => _do(() async {
                                await ref.read(accountsAgentApiProvider).updateSettings(aiProvider: v ? 'anthropic' : 'disabled');
                              }, v ? 'AI wording on' : 'AI wording off'),
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
              const AgentSectionTitle('AI token use'),
              _AiUsageCard(mayEdit: mayEdit, busy: _busy, run: _do, editBudget: _editBudget),
              if (mayEdit) ...[
                const AgentSectionTitle('Failed monitoring jobs'),
                _DeadEvents(busy: _busy, run: _do),
              ],
              const AgentSectionTitle('Learning history'),
              history.when(
                loading: () => const AppLoader(),
                error: (e, _) => HudErrorState(message: friendlyErrorMessage(e), compact: true, onRetry: () => ref.invalidate(agentLearningHistoryProvider)),
                data: (rows) => rows.isEmpty
                    ? const AgentCard(child: Text('No learning runs yet.'))
                    : Column(children: [
                        for (final r in rows)
                          Padding(
                            padding: const EdgeInsets.only(bottom: 8),
                            child: AgentCard(
                              child: Row(children: [
                                Expanded(child: Text('${stamp(r.finishedAt)} · ${r.voucherCount} vouchers', style: const TextStyle(fontSize: 13.5))),
                                Text('${titleCase(r.status)} · ${titleCase(r.confidenceLabel)}', style: const TextStyle(fontSize: 12.5, color: Hud.dim)),
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


/// Monitoring jobs that failed repeatedly and were parked (D-10). An administrator can retry one (a limited number of
/// times) or acknowledge it with a note; both are recorded in the audit log. Acknowledged failures stay listed but no
/// longer mark monitoring as degraded.
class _DeadEvents extends ConsumerWidget {
  final bool busy;
  final Future<void> Function(Future<void> Function() job, String done) run;
  const _DeadEvents({required this.busy, required this.run});

  Future<void> _acknowledge(BuildContext context, WidgetRef ref, DeadEvent e) async {
    final c = TextEditingController();
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Acknowledge failed job'),
        content: TextField(controller: c, maxLines: 2, decoration: const InputDecoration(labelText: 'Why (required)')),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancel')),
          FilledButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('Acknowledge')),
        ],
      ),
    );
    if (ok != true) return;
    final note = c.text.trim();
    if (note.length < 5) {
      if (context.mounted) showErrorToast(context, Exception('Please say why, in a few words'));
      return;
    }
    await run(() async { await ref.read(accountsAgentApiProvider).acknowledgeEvent(e.id, note); }, 'Acknowledged');
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final async = ref.watch(agentDeadEventsProvider);
    return async.when(
      loading: () => const AppLoader(),
      error: (e, _) => HudErrorState(message: friendlyErrorMessage(e), compact: true, onRetry: () => ref.invalidate(agentDeadEventsProvider)),
      data: (rows) => AgentCard(
        child: rows.isEmpty
            ? const Text('No failed jobs.', style: TextStyle(color: Hud.dim))
            : Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                for (final e in rows)
                  Padding(
                    padding: const EdgeInsets.symmetric(vertical: 6),
                    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                      Text('${titleCase(e.eventType.replaceAll('.', ' '))}${e.deadAt == null ? '' : ' · failed ${day(e.deadAt!)}'}',
                          style: const TextStyle(fontSize: 13.5, fontWeight: FontWeight.w600)),
                      if (e.lastError != null)
                        Text(e.lastError!, style: const TextStyle(fontSize: 12, color: Hud.dim)),
                      if (e.acknowledged)
                        Text('Acknowledged: ${e.acknowledgeNote ?? ''}', style: const TextStyle(fontSize: 12, color: Hud.dim))
                      else
                        Wrap(spacing: 8, children: [
                          if (e.requeuesLeft > 0)
                            TextButton(
                                onPressed: busy ? null : () => run(() async { await ref.read(accountsAgentApiProvider).requeueEvent(e.id); },
                                    'Queued again'),
                                child: Text('Retry (${e.requeuesLeft} left)')),
                          TextButton(onPressed: busy ? null : () => _acknowledge(context, ref, e), child: const Text('Acknowledge')),
                        ]),
                    ]),
                  ),
              ]),
      ),
    );
  }
}


String _tokens(int n) => n >= 1000000
    ? '${(n / 1000000).toStringAsFixed(n % 1000000 == 0 ? 0 : 1)}M'
    : n >= 1000
        ? '${(n / 1000).toStringAsFixed(n % 1000 == 0 || n >= 100000 ? 0 : 1)}k'
        : '$n';

/// This month's AI tokens against the budget, and how often the app answered without the AI (the saving).
class _AiUsageCard extends ConsumerWidget {
  final bool mayEdit;
  final bool busy;
  final Future<void> Function(Future<void> Function() job, String done) run;
  final Future<void> Function(int current) editBudget;
  const _AiUsageCard({required this.mayEdit, required this.busy, required this.run, required this.editBudget});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final usage = ref.watch(agentAiUsageProvider);
    return usage.when(
      loading: () => const AppLoader(),
      error: (e, _) => HudErrorState(message: friendlyErrorMessage(e), compact: true, onRetry: () => ref.invalidate(agentAiUsageProvider)),
      data: (u) {
        final pct = u.budgetTokens == 0 ? 1.0 : (u.spentTokens / u.budgetTokens).clamp(0.0, 1.0);
        final color = pct >= 0.9 ? Hud.red : (pct >= 0.7 ? Hud.amber : Hud.cyan);
        return AgentCard(
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Row(children: [
              Expanded(
                child: Text('${_tokens(u.spentTokens)} of ${_tokens(u.budgetTokens)} tokens · ${u.month}',
                    style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w700, fontFeatures: Hud.tabular)),
              ),
              HudChip(label: u.aiEnabled ? 'AI on' : 'AI off', tone: u.aiEnabled ? AppTone.success : AppTone.neutral),
            ]),
            const SizedBox(height: 8),
            ClipRRect(
              borderRadius: BorderRadius.circular(3),
              child: LinearProgressIndicator(value: pct, minHeight: 6, color: color, backgroundColor: Hud.line),
            ),
            const SizedBox(height: 6),
            Text(
                !u.planAllowed
                    ? (u.planReason ?? 'Your subscription does not include AI.')
                    : u.budgetTokens == 0
                        ? 'Budget 0: the AI is never called.'
                        : '${_tokens(u.leftTokens)} left ${u.period == 'trial' ? 'in the free trial' : 'this month'}'
                            '${u.planLabel == null ? '' : ' · ${u.planLabel} plan'}',
                style: TextStyle(fontSize: 12.5, color: u.planAllowed ? Hud.dim : Hud.amber)),
            const SizedBox(height: 12),
            if (u.planAllowed)
              KeyValue('Plan allowance', '${_tokens(u.planTokens)} ${u.period == 'trial' ? 'for the trial' : 'a month'}'),
            if (u.planAllowed && u.committeeBudget < u.planTokens)
              KeyValue('Committee limit', '${_tokens(u.committeeBudget)} a month'),
            KeyValue('Answered without AI', u.requests == 0
                ? 'No questions yet this month'
                : '${u.answeredWithoutAi} of ${u.requests} (${u.withoutAiPct.toStringAsFixed(0)}%)'),
            KeyValue('From saved answers', '${u.reusedAnswers}'),
            KeyValue('From the app\'s own data', '${u.answeredLocally}'),
            if (u.overBudget > 0) KeyValue('Held back by the budget', '${u.overBudget}'),
            if (u.notIncluded > 0) KeyValue('Not in the plan', '${u.notIncluded}'),
            KeyValue('AI requests sent', '${u.aiCalls}${u.failedCalls > 0 ? ' (${u.failedCalls} failed)' : ''}'),
            for (final f in u.byFeature)
              KeyValue(f.label, '${f.aiCalls} requests · ${_tokens(f.tokens)} tokens · ${f.withoutAi} without AI'),
            const SizedBox(height: 8),
            const Text(
                'Every question is cleaned up first and its Hindi or Marathi words matched to the bye-laws on the app '
                'itself. The AI is asked only when the library and the books cannot answer alone, then with only the '
                'few clauses that matter, and its answer is kept so the same question costs nothing next time.',
                style: TextStyle(fontSize: 12.5, color: Hud.dim, height: 1.4)),
            if (mayEdit) ...[
              const SizedBox(height: 8),
              Wrap(spacing: 8, runSpacing: 8, children: [
                OutlinedButton.icon(
                  onPressed: busy ? null : () => editBudget(u.budgetTokens),
                  icon: const Icon(Icons.tune_rounded, size: 18),
                  label: const Text('Change monthly budget'),
                ),
                if (u.keptAnswers > 0)
                  TextButton.icon(
                    onPressed: busy
                        ? null
                        : () => run(() async { await ref.read(accountsAgentApiProvider).forgetAiAnswers(); },
                            'Saved answers cleared'),
                    icon: const Icon(Icons.delete_sweep_outlined, size: 18),
                    label: Text('Clear ${u.keptAnswers} saved answer${u.keptAnswers == 1 ? '' : 's'}'),
                  ),
              ]),
            ],
          ]),
        );
      },
    );
  }
}
