import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/motion/loading.dart';
import 'package:ar_society_app/core/router/app_router.dart';
import 'package:ar_society_app/core/theme/design_tokens.dart';
import 'package:ar_society_app/features/accounts_agent/presentation/widgets/agent_hud.dart';
import 'package:ar_society_app/features/accounts_agent/data/accounts_agent_api.dart';
import 'package:ar_society_app/features/accounts_agent/presentation/providers/accounts_agent_providers.dart';
import 'package:ar_society_app/features/accounts_agent/presentation/widgets/agent_widgets.dart';
import 'package:ar_society_app/shared/widgets/app_form.dart';

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
          error: (e, _) => HudErrorState(message: friendlyErrorMessage(e), onRetry: () => ref.invalidate(agentDashboardProvider)),
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
    final accent = Hud.tone(tone);
    return ListView(padding: const EdgeInsets.fromLTRB(16, 12, 16, 96), children: [
      AgentCard(
        accent: accent,
        padding: const EdgeInsets.all(20),
        child: LayoutBuilder(builder: (context, c) {
          final wide = c.maxWidth > 560;
          final head = Row(children: [
            HudCore(color: accent, icon: icon, size: wide ? 96 : 72),
            const SizedBox(width: 18),
            Expanded(
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text('AGENT STATUS', style: Hud.label(color: Hud.dim)),
                const SizedBox(height: 4),
                Text(label,
                    style: TextStyle(
                      fontSize: wide ? 24 : 19,
                      fontWeight: FontWeight.w800,
                      letterSpacing: 0.4,
                      color: Hud.text,
                      shadows: [Shadow(color: accent.withValues(alpha: 0.6), blurRadius: 18)],
                    )),
                const SizedBox(height: 8),
                Wrap(spacing: 8, runSpacing: 6, children: [
                  HudChip(label: d.status.monitoringEnabled ? 'Monitoring on' : 'Monitoring off', tone: d.status.monitoringEnabled ? AppTone.success : AppTone.neutral),
                  HudChip(label: 'Learning: ${d.status.learningConfidence}', tone: AppTone.info, icon: Icons.psychology_outlined),
                ]),
              ]),
            ),
          ]);
          return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            head,
            const SizedBox(height: 16),
            Container(height: 1, color: accent.withValues(alpha: 0.18)),
            const SizedBox(height: 12),
            KeyValue('Last monitored', stamp(d.status.lastMonitoredAt)),
            KeyValue('Last learning', stamp(d.status.lastLearningAt)),
            KeyValue('Learning period', run == null ? 'Not learned yet' : '${day(run.windowStart)} – ${day(run.windowEnd)} (last ${d.windowMonths} months)'),
            KeyValue('Transactions analysed', '${d.transactionsAnalysed}'),
            if (d.status.lastError != null) KeyValue('Last problem', d.status.lastError),
            if (d.status.learningConfidence == 'none' || d.status.learningConfidence == 'limited') ...[
              const SizedBox(height: 8),
              const Text('Limited learning confidence: there is little history in the last three months, so statistical checks are conservative.',
                  style: TextStyle(fontSize: 12.5, color: Hud.amber)),
            ],
          ]);
        }),
      ),
      const AgentSectionTitle('Open findings'),
      LayoutBuilder(builder: (context, c) {
        final cols = c.maxWidth > 700 ? 3 : 2;
        final w = (c.maxWidth - (cols - 1) * 12) / cols;
        Widget tile(String label, int v, Color color, VoidCallback onTap) =>
            SizedBox(width: w, child: AgentStat(label: label, value: v, color: color, onTap: onTap));
        return Wrap(spacing: 12, runSpacing: 12, children: [
          tile('Critical', d.open['CRITICAL'] ?? 0, Hud.red, () => findings('CRITICAL')),
          tile('High severity', d.open['HIGH'] ?? 0, Hud.red, () => findings('HIGH')),
          tile('Medium', d.open['MEDIUM'] ?? 0, Hud.amber, () => findings('MEDIUM')),
          tile('Resolved', d.resolved, Hud.green, () => context.push('${AppRoutes.accountsAgentFindings}?status=RESOLVED')),
          tile('Pending approvals', d.pendingApprovals, Hud.cyan, () => context.push(AppRoutes.accountsAgentApprovals)),
        ]);
      }),
      const AgentSectionTitle('Command console'),
      LayoutBuilder(builder: (context, c) {
        final cols = c.maxWidth > 700 ? 3 : (c.maxWidth > 420 ? 2 : 1);
        final w = (c.maxWidth - (cols - 1) * 12) / cols;
        Widget cmd(IconData i, String title, String sub, String route, {Color color = Hud.cyan}) =>
            SizedBox(width: w, child: _Command(icon: i, title: title, subtitle: sub, color: color, onTap: () => context.push(route)));
        return Wrap(spacing: 12, runSpacing: 12, children: [
          cmd(Icons.fact_check_outlined, 'All findings', 'Everything the agent flagged', AppRoutes.accountsAgentFindings),
          cmd(Icons.approval_outlined, 'Proposals', 'Corrections awaiting approval', AppRoutes.accountsAgentApprovals, color: Hud.violetText),
          cmd(Icons.gavel_rounded, 'Bye-law & compliance', 'Rules, deadlines, recovery', AppRoutes.accountsAgentCompliance),
          cmd(Icons.menu_book_outlined, 'Ask about bye-laws', 'Answers with clause references', AppRoutes.accountsAgentAsk, color: Hud.green),
          cmd(Icons.edit_note_rounded, 'Draft an entry', 'A voucher prepared for approval', AppRoutes.accountsAgentEntryDraft, color: Hud.green),
          cmd(Icons.campaign_outlined, 'Notices & agendas', 'Meeting notices and dues reminders', AppRoutes.accountsAgentNotices, color: Hud.green),
          cmd(Icons.school_outlined, 'Learning & settings', 'What the agent learned, AI wording', AppRoutes.accountsAgentLearning, color: Hud.violetText),
        ]);
      }),
    ]);
  }
}

class _Command extends StatelessWidget {
  final IconData icon;
  final String title;
  final String subtitle;
  final Color color;
  final VoidCallback onTap;
  const _Command({required this.icon, required this.title, required this.subtitle, required this.color, required this.onTap});
  @override
  Widget build(BuildContext context) => AgentCard(
        onTap: onTap,
        accent: color,
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 14),
        child: Semantics(
          button: true,
          label: '$title. $subtitle',
          child: ExcludeSemantics(
            child: Row(children: [
              Container(
                width: 40,
                height: 40,
                decoration: BoxDecoration(
                  borderRadius: BorderRadius.circular(8),
                  color: color.withValues(alpha: 0.1),
                  border: Border.all(color: color.withValues(alpha: 0.45)),
                ),
                child: Icon(icon, size: 20, color: color),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Text(title, maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w700, color: Hud.text)),
                  const SizedBox(height: 2),
                  Text(subtitle, maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 12, color: Hud.dim)),
                ]),
              ),
              Icon(Icons.chevron_right_rounded, color: color.withValues(alpha: 0.7)),
            ]),
          ),
        ),
      );
}
