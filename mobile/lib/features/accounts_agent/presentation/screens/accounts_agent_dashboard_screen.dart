import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/motion/loading.dart';
import 'package:ar_society_app/core/router/app_router.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/core/theme/design_tokens.dart';
import 'package:ar_society_app/features/accounts_agent/data/accounts_agent_api.dart';
import 'package:ar_society_app/features/accounts_agent/presentation/providers/accounts_agent_providers.dart';
import 'package:ar_society_app/features/accounts_agent/presentation/widgets/agent_widgets.dart';
import 'package:ar_society_app/shared/widgets/app_form.dart';
import 'package:ar_society_app/shared/widgets/app_status.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';

/// The Accounts Agent's front page: is it watching, what has it found, what is waiting for a decision.
class AccountsAgentDashboardScreen extends ConsumerWidget {
  const AccountsAgentDashboardScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final async = ref.watch(agentDashboardProvider);
    return AppPage(
      title: 'Accounts Agent',
      subtitle: 'Watches the books, explains what looks wrong, proposes corrections — you decide',
      maxWidth: 960,
      actions: [
        IconButton(
          tooltip: 'Compliance & bye-laws',
          icon: const Icon(Icons.gavel_rounded),
          onPressed: () => context.push(AppRoutes.accountsAgentCompliance),
        ),
        IconButton(
          tooltip: 'Learning & settings',
          icon: const Icon(Icons.tune_rounded),
          onPressed: () => context.push(AppRoutes.accountsAgentLearning),
        ),
      ],
      body: RefreshIndicator(
        onRefresh: () async => invalidateAgent(ref),
        child: async.when(
          loading: () => const AppLoader(),
          error: (e, _) => AppErrorState(message: friendlyErrorMessage(e), onRetry: () => ref.invalidate(agentDashboardProvider)),
          data: (d) => _Body(d: d),
        ),
      ),
    );
  }
}

class _Body extends StatelessWidget {
  final AgentDashboard d;
  const _Body({required this.d});

  (String, AppTone, IconData) get _state => switch (d.status.state) {
        'operational' => ('Operational', AppTone.success, Icons.check_circle_rounded),
        'delayed' => ('Delayed — ${d.status.pendingEvents} waiting', AppTone.warning, Icons.schedule_rounded),
        'degraded' => ('Degraded — ${d.status.failedEvents} job(s) failed'
            '${d.status.recentFailedEvents < d.status.failedEvents ? ' (${d.status.recentFailedEvents} this week)' : ''}',
            AppTone.danger, Icons.error_rounded),
        _ => ('Monitoring is off', AppTone.neutral, Icons.pause_circle_rounded),
      };

  @override
  Widget build(BuildContext context) {
    final (label, tone, icon) = _state;
    final run = d.lastRun;
    void findings([String? sev]) => context.push(sev == null ? AppRoutes.accountsAgentFindings : '${AppRoutes.accountsAgentFindings}?severity=$sev');
    return ListView(padding: const EdgeInsets.fromLTRB(16, 12, 16, 96), children: [
      AgentCard(
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            Icon(icon, color: kToneColors[tone]!.accent),
            const SizedBox(width: 8),
            Expanded(child: Text(label, style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w700))),
            AppStatusChip(label: d.status.monitoringEnabled ? 'Monitoring on' : 'Monitoring off', tone: d.status.monitoringEnabled ? AppTone.success : AppTone.neutral),
          ]),
          const SizedBox(height: 10),
          KeyValue('Last monitored', stamp(d.status.lastMonitoredAt)),
          KeyValue('Last learning', stamp(d.status.lastLearningAt)),
          KeyValue('Learning period', run == null ? 'Not learned yet' : '${day(run.windowStart)} – ${day(run.windowEnd)} (last ${d.windowMonths} months)'),
          KeyValue('Transactions analysed', '${d.transactionsAnalysed}'),
          if (d.status.lastError != null) KeyValue('Last problem', d.status.lastError),
          if (d.status.learningConfidence == 'none' || d.status.learningConfidence == 'limited') ...[
            const SizedBox(height: 8),
            const Text('Limited learning confidence: there is little history in the last three months, so statistical checks are conservative.',
                style: TextStyle(fontSize: 12.5, color: AppTheme.warning)),
          ],
        ]),
      ),
      const AgentSectionTitle('Open findings'),
      LayoutBuilder(builder: (context, c) {
        final cols = c.maxWidth > 700 ? 3 : 2;
        final w = (c.maxWidth - (cols - 1) * 12) / cols;
        Widget tile(String label, int v, Color color, VoidCallback onTap) =>
            SizedBox(width: w, child: AgentStat(label: label, value: v, color: color, onTap: onTap));
        return Wrap(spacing: 12, runSpacing: 12, children: [
          tile('Critical', d.open['CRITICAL'] ?? 0, AppTheme.error, () => findings('CRITICAL')),
          tile('High severity', d.open['HIGH'] ?? 0, AppTheme.error, () => findings('HIGH')),
          tile('Medium', d.open['MEDIUM'] ?? 0, AppTheme.warning, () => findings('MEDIUM')),
          tile('Resolved', d.resolved, AppTheme.success, () => context.push('${AppRoutes.accountsAgentFindings}?status=RESOLVED')),
          tile('Pending approvals', d.pendingApprovals, AppTheme.primary, () => context.push(AppRoutes.accountsAgentApprovals)),
        ]);
      }),
      const SizedBox(height: 16),
      Wrap(spacing: 10, runSpacing: 10, children: [
        FilledButton.icon(onPressed: () => findings(), icon: const Icon(Icons.fact_check_outlined), label: const Text('All findings')),
        FilledButton.tonalIcon(
            onPressed: () => context.push(AppRoutes.accountsAgentCompliance),
            icon: const Icon(Icons.gavel_rounded),
            label: const Text('Bye-law & compliance intelligence')),
        OutlinedButton.icon(
            onPressed: () => context.push(AppRoutes.accountsAgentApprovals), icon: const Icon(Icons.approval_outlined), label: const Text('Proposals awaiting approval')),
        OutlinedButton.icon(
            onPressed: () => context.push(AppRoutes.accountsAgentLearning), icon: const Icon(Icons.school_outlined), label: const Text('Learning & settings')),
      ]),
    ]);
  }
}
