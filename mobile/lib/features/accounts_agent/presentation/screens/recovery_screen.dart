import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/motion/loading.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/core/theme/design_tokens.dart';
import 'package:ar_society_app/features/accounts/data/accounts_api.dart' show formatInr;
import 'package:ar_society_app/features/accounts_agent/data/legal_api.dart';
import 'package:ar_society_app/features/accounts_agent/presentation/providers/legal_providers.dart';
import 'package:ar_society_app/features/accounts_agent/presentation/widgets/agent_widgets.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/shared/widgets/app_form.dart';
import 'package:ar_society_app/shared/widgets/app_status.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';

/// Member dues ageing and the recovery-readiness checklist (Section 154B-29 / Rule 106C-14). A review only: the agent
/// never issues notices or starts recovery.
class RecoveryScreen extends ConsumerWidget {
  const RecoveryScreen({super.key});

  Future<void> _checklist(BuildContext context, WidgetRef ref, ArrearsRow row) async {
    try {
      final c = await ref.read(legalApiProvider).checklist(row.flatId);
      if (!context.mounted) return;
      final items = (c['checklist'] as List).cast<Map>();
      await showDialog<void>(
        context: context,
        builder: (ctx) => AlertDialog(
          title: Text('Recovery readiness — ${row.flat}'),
          content: SingleChildScrollView(
            child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
              AppStatusChip(
                  label: titleCase('${c['readiness']}'), tone: c['readiness'] == 'READY_FOR_PROFESSIONAL_REVIEW' ? AppTone.success : AppTone.warning),
              const SizedBox(height: 8),
              for (final i in items)
                Padding(
                  padding: const EdgeInsets.symmetric(vertical: 4),
                  child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    Icon(
                      i['status'] == 'OK' ? Icons.check_circle_rounded : (i['status'] == 'MANUAL' ? Icons.help_outline_rounded : Icons.cancel_rounded),
                      size: 18,
                      color: i['status'] == 'OK' ? AppTheme.success : (i['status'] == 'MANUAL' ? AppTheme.warning : AppTheme.error),
                    ),
                    const SizedBox(width: 8),
                    Expanded(child: Text('${i['item']}\n${i['detail']}', style: const TextStyle(fontSize: 12.5))),
                  ]),
                ),
              const SizedBox(height: 8),
              Text('${c['note']}', style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
            ]),
          ),
          actions: [TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Close'))],
        ),
      );
    } catch (e) {
      if (context.mounted) showErrorToast(context, e);
    }
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final mayDecide = ref.watch(currentUserProvider)?.isAdminOrCommittee ?? false;
    final async = ref.watch(arrearsProvider);
    return AppPage(
      title: 'Member dues & recovery readiness',
      subtitle: 'Flat-wise ageing of unpaid bills',
      maxWidth: 960,
      body: async.when(
        loading: () => const AppLoader(),
        error: (e, _) => AppErrorState(message: friendlyErrorMessage(e), onRetry: () => ref.invalidate(arrearsProvider)),
        data: (r) => ListView(padding: const EdgeInsets.fromLTRB(16, 12, 16, 96), children: [
          AgentCard(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              KeyValue('Total outstanding', formatInr(r.total)),
              KeyValue('Defaulter after', '${r.defaulterAfterMonths} months'),
              for (final e in r.ageingTotals.entries) KeyValue('${e.key} days', formatInr(double.tryParse('${e.value}') ?? 0)),
              const SizedBox(height: 6),
              Text(r.note, style: const TextStyle(fontSize: 12.5, color: AppTheme.textSecondary)),
            ]),
          ),
          if (r.rule != null) ...[const AgentSectionTitle('Legal basis'), LegalSourceCard(source: r.rule!)],
          const AgentSectionTitle('Flats with unpaid bills'),
          if (r.flats.isEmpty) const AppEmptyState(icon: Icons.verified_outlined, title: 'No unpaid bills'),
          for (final f in r.flats)
            Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: AgentCard(
                onTap: mayDecide ? () => _checklist(context, ref, f) : null,
                child: Row(children: [
                  Expanded(
                    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                      Text(f.flat, style: const TextStyle(fontWeight: FontWeight.w700)),
                      Text('${f.overdueDays} days overdue', style: const TextStyle(fontSize: 12.5, color: AppTheme.textSecondary)),
                    ]),
                  ),
                  if (f.defaulter) const Padding(padding: EdgeInsets.only(right: 8), child: AppStatusChip(label: 'Defaulter', tone: AppTone.danger)),
                  Text(formatInr(f.outstanding), style: const TextStyle(fontWeight: FontWeight.w700)),
                ]),
              ),
            ),
        ]),
      ),
    );
  }
}
