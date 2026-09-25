import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:ar_society_app/core/router/app_router.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/visitor/presentation/providers/visitor_providers.dart';

/// "Visitor at the gate" call-out for residents: who is waiting and for which
/// flat, with a button to the approvals screen. Renders nothing when no one
/// is waiting.
class PendingVisitorsBanner extends ConsumerWidget {
  final EdgeInsetsGeometry padding;
  const PendingVisitorsBanner({super.key, this.padding = EdgeInsets.zero});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final pending = ref.watch(pendingVisitorApprovalsProvider).valueOrNull ?? const [];
    if (pending.isEmpty) return const SizedBox.shrink();

    final first = pending.first;
    final title = pending.length == 1
        ? '${first.name} is at the gate'
        : '${pending.length} visitors are waiting at the gate';
    final subtitle = pending.length == 1
        ? [first.visitorType.label, if (first.flatLabel != null) first.flatLabel!, if (first.purpose != null) first.purpose!]
            .join('  ·  ')
        : 'Approve or reject their entry';

    return Padding(
      padding: padding,
      child: Material(
        color: AppTheme.warningSoft,
        borderRadius: BorderRadius.circular(14),
        child: InkWell(
          borderRadius: BorderRadius.circular(14),
          onTap: () => context.push(AppRoutes.visitorsPending),
          child: Container(
            padding: const EdgeInsets.all(14),
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(14),
              border: Border.all(color: AppTheme.warning.withValues(alpha: 0.45)),
            ),
            child: Row(children: [
              Container(
                width: 40,
                height: 40,
                decoration: BoxDecoration(
                  color: AppTheme.warning.withValues(alpha: 0.18),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: const Icon(Icons.notifications_active_rounded, color: AppTheme.warning),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Text(title,
                      style: const TextStyle(
                          fontSize: 14, fontWeight: FontWeight.w700, color: AppTheme.textPrimary)),
                  const SizedBox(height: 2),
                  Text(subtitle,
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
                ]),
              ),
              const SizedBox(width: 8),
              FilledButton(
                onPressed: () => context.push(AppRoutes.visitorsPending),
                style: FilledButton.styleFrom(backgroundColor: AppTheme.warning),
                child: const Text('Review'),
              ),
            ]),
          ),
        ),
      ),
    );
  }
}
