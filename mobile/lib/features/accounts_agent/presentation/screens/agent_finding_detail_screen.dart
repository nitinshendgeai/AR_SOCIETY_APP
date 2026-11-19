import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/motion/loading.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/core/theme/design_tokens.dart';
import 'package:ar_society_app/features/accounts/data/accounts_api.dart' show formatInr;
import 'package:ar_society_app/features/accounts_agent/data/accounts_agent_api.dart';
import 'package:ar_society_app/features/accounts_agent/presentation/providers/accounts_agent_providers.dart';
import 'package:ar_society_app/features/accounts_agent/presentation/widgets/agent_widgets.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/shared/widgets/app_form.dart';
import 'package:ar_society_app/shared/widgets/app_status.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';

/// One finding in full: the voucher, what was detected and why, expected against actual, the evidence, and what to do.
class AgentFindingDetailScreen extends ConsumerStatefulWidget {
  final String findingId;
  const AgentFindingDetailScreen({super.key, required this.findingId});

  @override
  ConsumerState<AgentFindingDetailScreen> createState() => _AgentFindingDetailScreenState();
}

class _AgentFindingDetailScreenState extends ConsumerState<AgentFindingDetailScreen> {
  bool _busy = false;

  Future<void> _run(Future<void> Function() job, String done) async {
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

  Future<void> _review(String status, {required bool needsReason}) async {
    String? note;
    if (needsReason) {
      final c = TextEditingController();
      final ok = await showDialog<bool>(
        context: context,
        builder: (ctx) => AlertDialog(
          title: Text('Mark as ${titleCase(status).toLowerCase()}'),
          content: TextField(controller: c, maxLines: 2, decoration: const InputDecoration(labelText: 'Reason (required)')),
          actions: [
            TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancel')),
            FilledButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('Save')),
          ],
        ),
      );
      if (ok != true) return;
      if (c.text.trim().isEmpty) {
        if (mounted) showErrorToast(context, Exception('Please give a short reason'));
        return;
      }
      note = c.text.trim();
    }
    await _run(() async { await ref.read(accountsAgentApiProvider).review(widget.findingId, status, note: note); }, 'Finding updated');
  }

  Future<void> _propose() async {
    setState(() => _busy = true);
    try {
      final p = await ref.read(accountsAgentApiProvider).propose(widget.findingId);
      invalidateAgent(ref);
      if (mounted) context.push(agentProposalRoute(p.id));
    } catch (e) {
      if (mounted) showErrorToast(context, e);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final mayDecide = ref.watch(currentUserProvider)?.isAdminOrCommittee ?? false;
    final async = ref.watch(agentFindingProvider(widget.findingId));
    return AppPage(
      title: 'Finding',
      maxWidth: 960,
      body: async.when(
        loading: () => const AppLoader(),
        error: (e, _) => AppErrorState(message: friendlyErrorMessage(e), onRetry: () => ref.invalidate(agentFindingProvider(widget.findingId))),
        data: (f) => RefreshIndicator(
          onRefresh: () async => ref.invalidate(agentFindingProvider(widget.findingId)),
          child: ListView(padding: const EdgeInsets.fromLTRB(16, 12, 16, 96), children: [
            AgentCard(
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Wrap(spacing: 8, runSpacing: 6, children: [
                  SeverityChip(f.severity),
                  AppStatusChip(label: titleCase(f.status), tone: f.isOpen ? AppTone.warning : AppTone.neutral),
                  AppStatusChip(label: findingClassLabel(f.findingClass), tone: AppTone.neutral),
                ]),
                const SizedBox(height: 10),
                Text(f.title, style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w800)),
                const SizedBox(height: 6),
                KeyValue('Confidence', '${(f.confidence * 100).round()}%'),
                KeyValue('Category', titleCase(f.category)),
                KeyValue('Rule', f.ruleCode),
                if (f.learningConfidence == 'none' || f.learningConfidence == 'limited')
                  const Padding(
                    padding: EdgeInsets.only(top: 6),
                    child: Text('Raised with limited learning confidence.', style: TextStyle(fontSize: 12.5, color: AppTheme.warning)),
                  ),
              ]),
            ),
            if (f.voucher != null) ...[
              const AgentSectionTitle('Original voucher'),
              _VoucherCard(v: f.voucher!),
            ],
            const AgentSectionTitle('What was detected and why'),
            AgentCard(child: Text(f.explanation, style: const TextStyle(fontSize: 14, height: 1.45))),
            const AgentSectionTitle('Expected versus actual'),
            AgentCard(
              child: Column(children: [
                Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Expanded(child: _Compare(label: 'Expected', text: f.expected ?? '—', color: AppTheme.success)),
                  const SizedBox(width: 12),
                  Expanded(child: _Compare(label: 'Actual', text: f.actual ?? '—', color: AppTheme.error)),
                ]),
              ]),
            ),
            if (f.evidence.isNotEmpty) ...[
              const AgentSectionTitle('Evidence'),
              AgentCard(
                child: Column(children: [
                  for (final e in f.evidence.entries)
                    if (e.value != null && e.value is! Map && e.value is! List) KeyValue(titleCase(e.key), _plain(e.value))
                    else if (e.value is List) KeyValue(titleCase(e.key), (e.value as List).map(_plain).join(', ')),
                ]),
              ),
            ],
            if (f.recommendedAction != null) ...[
              const AgentSectionTitle('Suggested action'),
              AgentCard(child: Text(f.recommendedAction!, style: const TextStyle(fontSize: 14, height: 1.4))),
            ],
            if (f.aiExplanation != null) ...[
              const AgentSectionTitle('Additional explanation (AI-generated, advisory)'),
              AgentCard(child: Text(f.aiExplanation!)),
            ],
            if (f.proposals.isNotEmpty) ...[
              const AgentSectionTitle('Correction proposals'),
              for (final p in f.proposals)
                Padding(
                  padding: const EdgeInsets.only(bottom: 8),
                  child: AgentCard(
                    onTap: () => context.push(agentProposalRoute(p.id)),
                    child: Row(children: [
                      Expanded(child: Text(p.title, style: const TextStyle(fontWeight: FontWeight.w600))),
                      AppStatusChip(label: titleCase(p.status), tone: p.status == 'PENDING' ? AppTone.warning : AppTone.neutral),
                    ]),
                  ),
                ),
            ],
            if (f.resolutionNote != null) ...[
              const AgentSectionTitle('Resolution'),
              AgentCard(child: Text(f.resolutionNote!)),
            ],
            // Only people who may decide see the action buttons.
            if (mayDecide && f.isOpen) ...[
              const AgentSectionTitle('Review'),
              Wrap(spacing: 10, runSpacing: 10, children: [
                if (!f.proposals.any((p) => p.status == 'PENDING'))
                  FilledButton.icon(onPressed: _busy ? null : _propose, icon: const Icon(Icons.build_circle_outlined), label: const Text('Propose a correction')),
                if (f.status == 'NEW')
                  OutlinedButton(onPressed: _busy ? null : () => _review('UNDER_REVIEW', needsReason: false), child: const Text('Start review')),
                OutlinedButton(onPressed: _busy ? null : () => _review('RESOLVED', needsReason: true), child: const Text('Mark resolved')),
                OutlinedButton(onPressed: _busy ? null : () => _review('REJECTED', needsReason: true), child: const Text('Not an issue')),
                TextButton(onPressed: _busy ? null : () => _review('IGNORED', needsReason: true), child: const Text('Ignore')),
              ]),
            ],
          ]),
        ),
      ),
    );
  }

  static String _plain(Object? v) => v is double ? (v == v.roundToDouble() ? v.toStringAsFixed(0) : v.toStringAsFixed(2)) : '$v';
}

class _Compare extends StatelessWidget {
  final String label;
  final String text;
  final Color color;
  const _Compare({required this.label, required this.text, required this.color});
  @override
  Widget build(BuildContext context) => Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text(label, style: TextStyle(fontSize: 12, fontWeight: FontWeight.w700, color: color)),
        const SizedBox(height: 4),
        Text(text, style: const TextStyle(fontSize: 13.5, height: 1.35)),
      ]);
}

class _VoucherCard extends StatelessWidget {
  final AgentVoucher v;
  const _VoucherCard({required this.v});
  @override
  Widget build(BuildContext context) => AgentCard(
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            Expanded(child: Text(v.number, style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w700))),
            Text(formatInr(v.amount), style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w700)),
          ]),
          const SizedBox(height: 4),
          Text('${titleCase(v.type)} · ${day(v.date)} · ${titleCase(v.approvalStatus)}${v.cancelled ? ' · Cancelled' : ''}',
              style: const TextStyle(fontSize: 12.5, color: AppTheme.textSecondary)),
          if ((v.narration ?? '').isNotEmpty) Padding(padding: const EdgeInsets.only(top: 6), child: Text(v.narration!, style: const TextStyle(fontSize: 13))),
          if ((v.reference ?? '').isNotEmpty) KeyValue('Reference', v.reference),
          if (v.sourceType != null) KeyValue('Posted from', titleCase(v.sourceType!)),
          const Divider(height: 20),
          LinesTable(lines: [for (final l in v.lines) ProposalLine(l.vendor == null ? l.account : '${l.account} — ${l.vendor}', l.debit, l.credit)]),
        ]),
      );
}
