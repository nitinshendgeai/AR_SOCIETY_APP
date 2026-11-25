import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/motion/loading.dart';
import 'package:ar_society_app/core/theme/design_tokens.dart';
import 'package:ar_society_app/features/accounts_agent/presentation/widgets/agent_hud.dart';
import 'package:ar_society_app/features/accounts_agent/data/legal_api.dart';
import 'package:ar_society_app/features/accounts_agent/presentation/providers/legal_providers.dart';
import 'package:ar_society_app/features/accounts_agent/presentation/widgets/agent_widgets.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/shared/widgets/app_form.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';

/// The statutory compliance calendar. The agent never assumes a tax applies: unless the society's own records show
/// it, an item says "Professional verification required".
class StatutoryCalendarScreen extends ConsumerWidget {
  const StatutoryCalendarScreen({super.key});

  Future<void> _done(BuildContext context, WidgetRef ref, ComplianceItem it) async {
    final ev = TextEditingController();
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(it.title),
        content: TextField(controller: ev, decoration: const InputDecoration(labelText: 'Evidence (acknowledgement / report no.)')),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancel')),
          FilledButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('Mark done')),
        ],
      ),
    );
    if (ok != true || !context.mounted) return;
    try {
      await ref.read(legalApiProvider).updateItem(it.id, {'completion_status': 'COMPLETED', 'evidence_ref': ev.text.trim()});
      invalidateLegal(ref);
    } catch (e) {
      if (context.mounted) showErrorToast(context, e);
    }
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final mayDecide = ref.watch(currentUserProvider)?.isAdminOrCommittee ?? false;
    final async = ref.watch(complianceCalendarProvider);
    return AppPage(
      title: 'Statutory compliance',
      subtitle: 'Accounts, audit, AGM and tax filings — with their legal basis and applicability',
      maxWidth: 960,
      body: async.when(
        loading: () => const AppLoader(),
        error: (e, _) => HudErrorState(message: friendlyErrorMessage(e), onRetry: () => ref.invalidate(complianceCalendarProvider)),
        data: (items) => ListView(padding: const EdgeInsets.fromLTRB(16, 12, 16, 96), children: [
          for (final it in items)
            Padding(
              padding: const EdgeInsets.only(bottom: 10),
              child: AgentCard(
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Wrap(spacing: 8, runSpacing: 6, children: [
                    HudChip(
                        label: titleCase(it.status),
                        tone: it.status == 'COMPLETED' ? AppTone.success : (it.overdue ? AppTone.danger : AppTone.warning)),
                    if (it.overdue) const HudChip(label: 'Past due date', tone: AppTone.danger),
                    if (it.needsProfessional) const HudChip(label: 'Professional verification required', tone: AppTone.info),
                    HudChip(label: it.period, tone: AppTone.neutral),
                  ]),
                  const SizedBox(height: 6),
                  Text(it.title, style: const TextStyle(fontWeight: FontWeight.w700)),
                  KeyValue('Due', it.due == null ? 'Not set' : day(it.due!)),
                  KeyValue('Due date basis', it.dueBasis),
                  KeyValue('Legal source', it.legalSource),
                  KeyValue('Applicability', it.applicabilityReason),
                  KeyValue('Responsible', it.role),
                  if (mayDecide && it.status == 'PENDING')
                    Align(alignment: Alignment.centerRight, child: TextButton(onPressed: () => _done(context, ref, it), child: const Text('Mark done'))),
                ]),
              ),
            ),
          const Padding(
            padding: EdgeInsets.only(top: 6),
            child: Text('Due dates are working dates to be verified against the current Act, Rules and notifications.',
                style: TextStyle(fontSize: 12, color: Hud.dim)),
          ),
        ]),
      ),
    );
  }
}
