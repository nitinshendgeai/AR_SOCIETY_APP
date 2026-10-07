import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:ar_society_app/core/router/app_router.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/notices/data/notices_api.dart';
import 'package:ar_society_app/features/notices/presentation/providers/notices_providers.dart';

String clockTime(DateTime utc) {
  final d = utc.toLocal();
  final h = d.hour % 12 == 0 ? 12 : d.hour % 12;
  return '$h:${d.minute.toString().padLeft(2, '0')} ${d.hour >= 12 ? 'pm' : 'am'}';
}

/// Shown above every page while an emergency alert is in force, so nobody has to go looking for it.
/// Tapping it opens the notices, where the people who can end the alert will find it.
class EmergencyBanner extends ConsumerWidget {
  const EmergencyBanner({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final alerts = ref.watch(activeAlertsProvider).valueOrNull ?? const <EmergencyAlertItem>[];
    if (alerts.isEmpty) return const SizedBox.shrink();
    final a = alerts.first;
    return Material(
      color: AppTheme.error,
      child: SafeArea(
        bottom: false,
        child: InkWell(
          onTap: () => context.go(AppRoutes.notices),
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
            child: Row(children: [
              Icon(alertTypeIcon(a.type), color: Colors.white, size: 22),
              const SizedBox(width: 12),
              Expanded(
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, mainAxisSize: MainAxisSize.min, children: [
                  Text(
                    'EMERGENCY · ${a.title}',
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w700, fontSize: 14),
                  ),
                  Text(
                    [
                      if ((a.location ?? '').isNotEmpty) a.location!,
                      if ((a.description ?? '').isNotEmpty) a.description!,
                      'since ${clockTime(a.triggeredAt)}',
                    ].join(' · '),
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(color: Colors.white, fontSize: 12.5),
                  ),
                ]),
              ),
              if (alerts.length > 1)
                Padding(
                  padding: const EdgeInsets.only(left: 8),
                  child: Text('+${alerts.length - 1}', style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w700)),
                ),
              const Icon(Icons.chevron_right_rounded, color: Colors.white),
            ]),
          ),
        ),
      ),
    );
  }
}
