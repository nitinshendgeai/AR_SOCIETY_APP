import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/motion/loading.dart';
import 'package:ar_society_app/core/theme/design_tokens.dart';
import 'package:ar_society_app/features/accounts/data/accounts_api.dart' show formatInr;
import 'package:ar_society_app/features/accounts_agent/presentation/widgets/agent_hud.dart';
import 'package:ar_society_app/features/accounts_agent/data/accounts_agent_api.dart';
import 'package:ar_society_app/features/accounts_agent/presentation/providers/accounts_agent_providers.dart';
import 'package:ar_society_app/features/accounts_agent/presentation/widgets/agent_widgets.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/shared/widgets/app_form.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';

/// The approval screen: current values, proposed values, the debit/credit effect and the explanation. Nothing changes in
/// the books until an authorised person explicitly confirms; the buttons are not shown to anyone else.
class AgentProposalScreen extends ConsumerStatefulWidget {
  final String proposalId;
  const AgentProposalScreen({super.key, required this.proposalId});

  @override
  ConsumerState<AgentProposalScreen> createState() => _AgentProposalScreenState();
}

class _AgentProposalScreenState extends ConsumerState<AgentProposalScreen> {
  bool _busy = false;

  Future<void> _approve(AgentProposal p) async {
    final applies = p.executable;
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(applies ? 'Apply this correction?' : 'Confirm the review?'),
        content: Text(applies
            ? 'This changes the books through the normal accounting rules: "${p.title}". It is recorded in the audit trail with your name. '
                'If the voucher was edited since the proposal was made, nothing will be applied.'
            : 'Records that the source has been reviewed. No books are changed.'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancel')),
          FilledButton(onPressed: () => Navigator.pop(ctx, true), child: Text(applies ? 'Yes, apply it' : 'Confirm')),
        ],
      ),
    );
    if (ok != true) return;
    await _decide(() => ref.read(accountsAgentApiProvider).approve(p.id), applies ? 'Correction applied' : 'Review recorded');
  }

  Future<void> _reject(AgentProposal p) async {
    final c = TextEditingController();
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Reject this proposal?'),
        content: TextField(controller: c, maxLines: 2, decoration: const InputDecoration(labelText: 'Reason (required)')),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancel')),
          FilledButton(style: FilledButton.styleFrom(backgroundColor: Hud.red), onPressed: () => Navigator.pop(ctx, true), child: const Text('Reject')),
        ],
      ),
    );
    if (ok != true) return;
    if (c.text.trim().length < 3) {
      if (mounted) showErrorToast(context, Exception('Give a reason for rejecting'));
      return;
    }
    await _decide(() => ref.read(accountsAgentApiProvider).reject(p.id, c.text.trim()), 'Proposal rejected');
  }

  Future<void> _decide(Future<AgentProposal> Function() job, String done) async {
    setState(() => _busy = true);
    try {
      await job();
      invalidateAgent(ref);
      if (mounted) AppToast.success(context, done);
    } catch (e) {
      invalidateAgent(ref);
      if (mounted) showErrorToast(context, e);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final mayDecide = ref.watch(currentUserProvider)?.isAdminOrCommittee ?? false;
    final me = ref.watch(currentUserProvider)?.id;
    final async = ref.watch(agentProposalProvider(widget.proposalId));
    return AppPage(
      title: 'Correction proposal',
      maxWidth: 960,
      body: async.when(
        loading: () => const AppLoader(),
        error: (e, _) => HudErrorState(message: friendlyErrorMessage(e), onRetry: () => ref.invalidate(agentProposalProvider(widget.proposalId))),
        data: (p) => ListView(padding: const EdgeInsets.fromLTRB(16, 12, 16, 96), children: [
          AgentCard(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              HudChip(
                  label: titleCase(p.status),
                  tone: switch (p.status) {
                    'PENDING' => AppTone.warning,
                    'EXECUTED' || 'ACKNOWLEDGED' => AppTone.success,
                    'FAILED' || 'STALE' => AppTone.danger,
                    _ => AppTone.neutral,
                  }),
              const SizedBox(height: 8),
              Text(p.title, style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w800)),
              const SizedBox(height: 8),
              Text(p.explanation, style: const TextStyle(fontSize: 14, height: 1.45)),
              if (p.status == 'STALE')
                const Padding(
                  padding: EdgeInsets.only(top: 8),
                  child: Text('The voucher changed after this proposal was made, so it was not applied. Open the finding and propose again.',
                      style: TextStyle(color: Hud.red, fontSize: 13)),
                ),
              if (p.error != null) Padding(padding: const EdgeInsets.only(top: 8), child: Text(p.error!, style: const TextStyle(color: Hud.red, fontSize: 13))),
              if (p.verificationNote != null) Padding(padding: const EdgeInsets.only(top: 8), child: Text(p.verificationNote!, style: const TextStyle(fontSize: 13))),
              if (p.decisionNote != null) KeyValue('Note', p.decisionNote),
            ]),
          ),
          const AgentSectionTitle('Current accounting values'),
          AgentCard(child: LinesTable(lines: p.before, strike: p.cancelsVoucher)),
          const AgentSectionTitle('Proposed accounting values'),
          AgentCard(
            child: p.cancelsVoucher
                ? const Text('The voucher is cancelled (kept on record, struck out). Every line above stops counting in the books.',
                    style: TextStyle(fontSize: 13.5))
                : p.after == null
                    ? const Text('No change to the books. This asks for the source document or posting mapping to be corrected.',
                        style: TextStyle(fontSize: 13.5))
                    : LinesTable(lines: p.after!),
          ),
          if (p.impact.isNotEmpty) ...[
            const AgentSectionTitle('Debit / credit impact by ledger'),
            AgentCard(
              child: Column(children: [
                for (final i in p.impact)
                  Padding(
                    padding: const EdgeInsets.symmetric(vertical: 5),
                    child: Row(children: [
                      Expanded(child: Text(i.account, style: const TextStyle(fontSize: 13.5, fontWeight: FontWeight.w600))),
                      Text('Dr ${formatInr(i.debitBefore)} Cr ${formatInr(i.creditBefore)}  →  Dr ${formatInr(i.debitAfter)} Cr ${formatInr(i.creditAfter)}',
                          style: const TextStyle(fontSize: 12.5)),
                      const SizedBox(width: 8),
                      Text(i.net, style: const TextStyle(fontSize: 12.5, fontWeight: FontWeight.w700)),
                    ]),
                  ),
              ]),
            ),
          ],
          if (mayDecide && p.status == 'PENDING') ...[
            const SizedBox(height: 20),
            Row(children: [
              Expanded(
                child: OutlinedButton(
                    style: OutlinedButton.styleFrom(foregroundColor: Hud.red),
                    onPressed: _busy ? null : () => _reject(p),
                    child: const Text('Reject')),
              ),
              if (!(p.requiresOtherApprover && p.proposedBy(me))) const SizedBox(width: 12),
              // Maker–checker (D-09): the person who proposed a correction to the books cannot approve it.
              if (!(p.requiresOtherApprover && p.proposedBy(me)))
                Expanded(
                  child: FilledButton(onPressed: _busy ? null : () => _approve(p), child: Text(p.executable ? 'Approve & apply' : 'Confirm review')),
                ),
            ]),
            if (p.requiresOtherApprover && p.proposedBy(me))
              const Padding(
                padding: EdgeInsets.only(top: 12),
                child: Text('You proposed this correction, so another administrator or committee member must approve it. '
                    'You can still withdraw it with Reject.', style: TextStyle(color: Hud.dim, fontSize: 13)),
              ),
          ] else if (!mayDecide && p.status == 'PENDING')
            const Padding(
              padding: EdgeInsets.only(top: 16),
              child: Text('Only an admin or committee member can approve or reject this.', style: TextStyle(color: Hud.dim, fontSize: 13)),
            ),
          const SizedBox(height: 12),
          TextButton(onPressed: () => context.push(agentFindingRoute(p.findingId)), child: const Text('Open the finding')),
        ]),
      ),
    );
  }
}

/// Every proposal still waiting for a decision.
class AgentApprovalsScreen extends ConsumerWidget {
  const AgentApprovalsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final async = ref.watch(agentPendingProposalsProvider);
    return AppPage(
      title: 'Proposals awaiting approval',
      maxWidth: 960,
      body: RefreshIndicator(
        onRefresh: () async => ref.invalidate(agentPendingProposalsProvider),
        child: async.when(
          loading: () => const AppLoader(),
          error: (e, _) => HudErrorState(message: friendlyErrorMessage(e), onRetry: () => ref.invalidate(agentPendingProposalsProvider)),
          data: (rows) => rows.isEmpty
              ? ListView(children: const [
                  SizedBox(height: 60),
                  HudEmptyState(icon: Icons.approval_outlined, title: 'Nothing is waiting', subtitle: 'Correction proposals appear here until someone decides.'),
                ])
              : ListView(padding: const EdgeInsets.fromLTRB(16, 12, 16, 96), children: [
                  for (final p in rows)
                    Padding(
                      padding: const EdgeInsets.only(bottom: 10),
                      child: AgentCard(
                        onTap: () => context.push(agentProposalRoute(p.id)),
                        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                          Text(p.title, style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w700)),
                          const SizedBox(height: 4),
                          Text(p.explanation, maxLines: 2, overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 13, color: Hud.dim)),
                        ]),
                      ),
                    ),
                ]),
        ),
      ),
    );
  }
}
