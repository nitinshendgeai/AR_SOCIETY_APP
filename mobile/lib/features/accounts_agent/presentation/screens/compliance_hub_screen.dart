import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/motion/loading.dart';
import 'package:ar_society_app/core/router/app_router.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/core/theme/design_tokens.dart';
import 'package:ar_society_app/features/accounts/data/accounts_api.dart' show formatInr;
import 'package:ar_society_app/features/accounts_agent/data/legal_api.dart';
import 'package:ar_society_app/features/accounts_agent/presentation/providers/accounts_agent_providers.dart';
import 'package:ar_society_app/features/accounts_agent/presentation/providers/legal_providers.dart';
import 'package:ar_society_app/features/accounts_agent/presentation/widgets/agent_widgets.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/shared/widgets/app_form.dart';
import 'package:ar_society_app/shared/widgets/app_status.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';

/// The Accounts & bye-law intelligence dashboard: every section of the society's books and governance, with what is
/// open in each and how strongly it is stated (confirmed / potential / advisory).
class ComplianceHubScreen extends ConsumerStatefulWidget {
  const ComplianceHubScreen({super.key});
  @override
  ConsumerState<ComplianceHubScreen> createState() => _ComplianceHubScreenState();
}

class _ComplianceHubScreenState extends ConsumerState<ComplianceHubScreen> {
  bool _scanning = false;

  Future<void> _scan() async {
    setState(() => _scanning = true);
    try {
      final r = await ref.read(legalApiProvider).scan();
      invalidateLegal(ref);
      invalidateAgent(ref);
      if (mounted) AppToast.success(context, 'Scan complete: ${r['new_findings']} new, ${r['auto_resolved']} resolved');
    } catch (e) {
      if (mounted) showErrorToast(context, e);
    } finally {
      if (mounted) setState(() => _scanning = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final mayDecide = ref.watch(currentUserProvider)?.isAdminOrCommittee ?? false;
    final async = ref.watch(complianceOverviewProvider);
    return AppPage(
      title: 'Accounts & Bye-law Intelligence',
      subtitle: 'Maharashtra co-operative housing society — books, governance and compliance',
      maxWidth: 1040,
      actions: [
        IconButton(tooltip: 'Ask the agent', icon: const Icon(Icons.question_answer_outlined), onPressed: () => context.push(AppRoutes.accountsAgentAsk)),
      ],
      body: RefreshIndicator(
        onRefresh: () async => invalidateLegal(ref),
        child: async.when(
          loading: () => const AppLoader(),
          error: (e, _) => AppErrorState(message: friendlyErrorMessage(e), onRetry: () => ref.invalidate(complianceOverviewProvider)),
          data: (o) => ListView(padding: const EdgeInsets.fromLTRB(16, 12, 16, 96), children: [
            AgentCard(
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                const Text(
                  'Findings are classified by how certain they are. A potential issue is never shown as a confirmed violation, and '
                  'no legal rule counts as verified until it is checked against the original Gazette or your registered bye-laws.',
                  style: TextStyle(fontSize: 13, height: 1.4),
                ),
                const SizedBox(height: 10),
                KeyValue('Last scan', stamp(o.lastScanAt)),
                KeyValue('Legal rules', '${o.legalLibrary['rules_verified'] ?? 0} verified · ${o.legalLibrary['rules_unverified'] ?? 0} pending verification'),
                KeyValue('Open legal reviews', '${o.legalLibrary['open_legal_reviews'] ?? 0}'),
                if (mayDecide) ...[
                  const SizedBox(height: 10),
                  FilledButton.icon(
                    onPressed: _scanning ? null : _scan,
                    icon: _scanning
                        ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2))
                        : const Icon(Icons.policy_outlined),
                    label: const Text('Run compliance scan'),
                  ),
                ],
              ]),
            ),
            const AgentSectionTitle('1. Financial health'),
            AgentCard(
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                KeyValue('Member dues outstanding', formatInr(double.tryParse('${o.financialHealth['member_dues_outstanding']}') ?? 0)),
                KeyValue('Defaulters (beyond period)', '${o.financialHealth['defaulters'] ?? 0}'),
                KeyValue('Pending approvals', '${o.pendingApprovals}'),
              ]),
            ),
            const AgentSectionTitle('Sections'),
            LayoutBuilder(builder: (context, c) {
              final cols = c.maxWidth > 760 ? 3 : (c.maxWidth > 480 ? 2 : 1);
              final w = (c.maxWidth - (cols - 1) * 12) / cols;
              Widget tile(String n, String key, IconData icon, {VoidCallback? onTap, String? extra}) {
                final s = o.section(key);
                return SizedBox(
                  width: w,
                  child: _SectionTile(
                    number: n,
                    title: s?.title ?? key,
                    icon: icon,
                    section: s,
                    extra: extra,
                    onTap: onTap ?? () => context.push('${AppRoutes.accountsAgentFindings}?section=$key&title=${Uri.encodeComponent(s?.title ?? 'Findings')}'),
                  ),
                );
              }

              Widget link(String n, String title, IconData icon, String sub, String route) => SizedBox(
                    width: w,
                    child: AgentCard(
                      onTap: () => context.push(route),
                      child: Row(children: [
                        Icon(icon, color: AppTheme.primary),
                        const SizedBox(width: 10),
                        Expanded(
                          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                            Text('$n. $title', style: const TextStyle(fontWeight: FontWeight.w700)),
                            Text(sub, style: const TextStyle(fontSize: 12.5, color: AppTheme.textSecondary)),
                          ]),
                        ),
                        const Icon(Icons.chevron_right_rounded),
                      ]),
                    ),
                  );

              return Wrap(spacing: 12, runSpacing: 12, children: [
                tile('2', 'accounting_audit', Icons.fact_check_outlined),
                tile('3', 'bye_law_compliance', Icons.gavel_rounded),
                tile('4', 'member_ledger', Icons.people_alt_outlined,
                    extra: 'Dues & recovery readiness', onTap: null),
                tile('5', 'vendor_expense', Icons.storefront_outlined),
                tile('6', 'funds', Icons.savings_outlined),
                tile('7', 'budget', Icons.pie_chart_outline_rounded),
                link('8', 'Governance & resolutions', Icons.how_to_vote_outlined, 'AGM, SGM and committee resolutions', AppRoutes.accountsAgentResolutions),
                link('9', 'Statutory compliance', Icons.event_note_outlined,
                    '${o.statutory['pending'] ?? 0} pending · ${o.statutory['overdue'] ?? 0} overdue', AppRoutes.accountsAgentStatutory),
                link('10', 'Pending approvals', Icons.approval_outlined, '${o.pendingApprovals} awaiting a decision', AppRoutes.accountsAgentApprovals),
                link('11', 'Legal document library', Icons.menu_book_outlined, 'Bye-laws, rules, sources, reviews', AppRoutes.accountsAgentLegalLibrary),
                link('11a', 'Element → ledger map', Icons.account_tree_outlined, 'Which ledger each charge is credited to; sign-off',
                    AppRoutes.accountsAgentLedgerMap),
                link('12', 'Learning & agent settings', Icons.tune_rounded, 'Three-month learning baseline', AppRoutes.accountsAgentLearning),
              ]);
            }),
            const SizedBox(height: 12),
            Wrap(spacing: 10, runSpacing: 10, children: [
              OutlinedButton.icon(onPressed: () => context.push('${AppRoutes.accountsAgentFindings}?section=governance&title=${Uri.encodeComponent('Approval findings')}'),
                  icon: const Icon(Icons.rule_rounded), label: const Text('Approval findings')),
              OutlinedButton.icon(onPressed: () => context.push('${AppRoutes.accountsAgentFindings}?section=statutory&title=${Uri.encodeComponent('Statutory findings')}'),
                  icon: const Icon(Icons.assignment_late_outlined), label: const Text('Statutory findings')),
              OutlinedButton.icon(onPressed: () => context.push(AppRoutes.accountsAgentRecovery),
                  icon: const Icon(Icons.account_balance_wallet_outlined), label: const Text('Member dues & recovery readiness')),
            ]),
          ]),
        ),
      ),
    );
  }
}

class _SectionTile extends StatelessWidget {
  final String number, title;
  final IconData icon;
  final OverviewSection? section;
  final String? extra;
  final VoidCallback onTap;
  const _SectionTile({required this.number, required this.title, required this.icon, required this.section, required this.onTap, this.extra});

  @override
  Widget build(BuildContext context) {
    final s = section;
    final confirmed = (s?.byClass['CONFIRMED_ACCOUNTING_ERROR'] ?? 0) + (s?.byClass['CONFIRMED_STATUTORY_VALIDATION_FAILURE'] ?? 0);
    final potential = (s?.byClass['POTENTIAL_NON_COMPLIANCE'] ?? 0) + (s?.byClass['SUSPECTED_ACCOUNTING_ANOMALY'] ?? 0) + (s?.byClass['LEGAL_SOURCE_CONFLICT'] ?? 0);
    final other = (s?.open ?? 0) - confirmed - potential;
    return AgentCard(
      onTap: onTap,
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Icon(icon, color: AppTheme.primary),
          const SizedBox(width: 10),
          Expanded(child: Text('$number. $title', style: const TextStyle(fontWeight: FontWeight.w700))),
          Text('${s?.open ?? 0}', style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w800)),
        ]),
        const SizedBox(height: 8),
        Wrap(spacing: 6, runSpacing: 6, children: [
          if (confirmed > 0) AppStatusChip(label: '$confirmed confirmed', tone: AppTone.danger),
          if (potential > 0) AppStatusChip(label: '$potential to review', tone: AppTone.warning),
          if (other > 0) AppStatusChip(label: '$other advisory / documents', tone: AppTone.info),
          if ((s?.open ?? 0) == 0) const AppStatusChip(label: 'Nothing open', tone: AppTone.success),
        ]),
        if (extra != null) ...[
          const SizedBox(height: 6),
          Text(extra!, style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
        ],
      ]),
    );
  }
}
