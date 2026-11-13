import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:ar_society_app/core/l10n/app_locale.dart';
import 'package:ar_society_app/core/router/app_router.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/core/theme/design_tokens.dart';
import 'package:ar_society_app/features/auth/domain/entities/user_entity.dart';
import 'package:ar_society_app/features/dashboard/gate_summary.dart';
import 'package:ar_society_app/features/users/presentation/providers/user_providers.dart' show myFormCodesProvider;

/// The guard's gate at a glance: who is inside, who was let in today, and the four things a guard does all shift
/// (log a visitor, check one out, verify a code, take a parcel in) as large buttons. Uses the figures the server
/// already works out for the Security dashboard and the screens that already exist; it changes none of them.
///
/// A figure the server could not work out shows "--" and can be tapped to try again, never 0: a guard must not read
/// "0 inside" when the truth is "unknown".
class GatePanel extends ConsumerWidget {
  final UserEntity user;
  final String societyId;
  const GatePanel({super.key, required this.user, required this.societyId});

  /// The visitor log for the society, optionally on a tab or in code-verify mode.
  static String logRoute(String societyId, {String? query}) {
    final base = AppRoutes.visitorsSociety.replaceFirst(':societyId', societyId);
    return query == null ? base : '$base?$query';
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    if (!user.hasService('visitors')) return const SizedBox.shrink();
    final summary = ref.watch(gateSummaryProvider(societyId));
    final grants = ref.watch(myFormCodesProvider).valueOrNull;
    final parcels = user.hasService('gate_extras') && grants != null && grants.contains('parcels');

    int? pick(int? Function(GateSummary g) f) =>
        summary.whenOrNull(data: (g) => g.failed ? null : f(g));
    final loading = summary.isLoading;
    void retry() => ref.invalidate(gateSummaryProvider(societyId));

    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Row(children: [
        Expanded(
          child: _Stat(
            label: context.tr('Inside now'),
            value: pick((g) => g.inside),
            loading: loading,
            color: AppTheme.warning,
            onTap: () => context.push(logRoute(societyId, query: 'tab=inside')),
            onRetry: retry,
          ),
        ),
        const SizedBox(width: AppSpacing.s),
        Expanded(
          child: _Stat(
            label: context.tr('Let in today'),
            value: pick((g) => g.checkedInToday),
            loading: loading,
            color: AppTheme.success,
            onTap: () => context.push(logRoute(societyId)),
            onRetry: retry,
          ),
        ),
        const SizedBox(width: AppSpacing.s),
        Expanded(
          child: _Stat(
            label: context.tr('Visitors today'),
            value: pick((g) => g.visitorsToday),
            loading: loading,
            color: AppTheme.primary,
            onTap: () => context.push(logRoute(societyId)),
            onRetry: retry,
          ),
        ),
      ]),
      const SizedBox(height: AppSpacing.m),
      Row(children: [
        Expanded(
          child: _Action(
            icon: Icons.person_add_rounded,
            label: context.tr('Log visitor'),
            primary: true,
            onTap: () => context.push(AppRoutes.visitorsCreate, extra: societyId),
          ),
        ),
        const SizedBox(width: AppSpacing.s),
        Expanded(
          child: _Action(
            icon: Icons.logout_rounded,
            label: context.tr('Check Out'),
            onTap: () => context.push(logRoute(societyId, query: 'tab=inside')),
          ),
        ),
      ]),
      const SizedBox(height: AppSpacing.s),
      Row(children: [
        Expanded(
          child: _Action(
            icon: Icons.pin_outlined,
            label: context.tr('Verify code'),
            onTap: () => context.push(logRoute(societyId, query: 'verify=1')),
          ),
        ),
        if (parcels) ...[
          const SizedBox(width: AppSpacing.s),
          Expanded(
            child: _Action(
              icon: Icons.local_shipping_rounded,
              label: context.tr('Parcels in'),
              onTap: () => context.push(AppRoutes.parcels),
            ),
          ),
        ],
      ]),
    ]);
  }
}

class _Stat extends StatelessWidget {
  final String label;
  final int? value;
  final bool loading;
  final Color color;
  final VoidCallback onTap;
  final VoidCallback onRetry;
  const _Stat({
    required this.label,
    required this.value,
    required this.loading,
    required this.color,
    required this.onTap,
    required this.onRetry,
  });

  @override
  Widget build(BuildContext context) {
    final unavailable = !loading && value == null;
    final shown = loading ? '…' : (value?.toString() ?? '--');
    return Semantics(
      button: true,
      label: unavailable ? '$label unavailable. Tap to try again' : '$label: $shown',
      excludeSemantics: true,
      // The card is the outer box (colour and outline together) and the ink sits on a transparent Material inside it: a
      // shadow drawn above a coloured Material tints the whole card grey.
      child: Container(
        decoration: BoxDecoration(
          color: AppTheme.cardBg,
          borderRadius: BorderRadius.circular(AppTheme.radiusM),
          border: Border.all(color: AppTheme.border),
        ),
        child: Material(
          type: MaterialType.transparency,
          child: InkWell(
            borderRadius: BorderRadius.circular(AppTheme.radiusM),
            onTap: unavailable ? onRetry : onTap,
            child: Container(
              constraints: const BoxConstraints(minHeight: 84),
              padding: const EdgeInsets.all(AppSpacing.m),
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              FittedBox(
                fit: BoxFit.scaleDown,
                alignment: Alignment.centerLeft,
                child: Text(shown,
                    style: TextStyle(
                        fontSize: 28,
                        fontWeight: FontWeight.w700,
                        color: unavailable ? AppTheme.textSecondary : color,
                        fontFeatures: const [FontFeature.tabularFigures()])),
              ),
              const SizedBox(height: 2),
              Text(unavailable ? context.tr('Tap to retry') : label,
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(fontSize: 12.5, color: AppTheme.textSecondary)),
              ]),
            ),
          ),
        ),
      ),
    );
  }
}

class _Action extends StatelessWidget {
  final IconData icon;
  final String label;
  final VoidCallback onTap;

  /// The one thing a guard does most (logging who arrives): solid blue, where the others are quiet.
  final bool primary;
  const _Action({required this.icon, required this.label, required this.onTap, this.primary = false});

  @override
  Widget build(BuildContext context) => SizedBox(
        height: 64,
        child: (primary ? FilledButton.icon : FilledButton.tonalIcon)(
          onPressed: onTap,
          icon: Icon(icon, size: 24),
          // The size is set on the Text, which keeps the button's own (app) font; replacing the button's textStyle would
          // drop it, and the Marathi fallback font with it.
          label: Text(label,
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
              textAlign: TextAlign.center,
              style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w600)),
          style: FilledButton.styleFrom(
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(AppTheme.radiusM)),
          ),
        ),
      );
}
