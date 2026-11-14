import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:ar_society_app/core/l10n/app_locale.dart';
import 'package:ar_society_app/core/motion/loading.dart';
import 'package:ar_society_app/core/router/app_router.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/core/theme/design_tokens.dart';
import 'package:ar_society_app/features/maintenance_billing/data/maintenance_billing_api.dart'
    show MyBillsSummary, amountOf, formatRupees;
import 'package:ar_society_app/features/maintenance_billing/presentation/providers/maintenance_billing_providers.dart'
    show myBillsProvider;
import 'package:ar_society_app/shared/widgets/app_status.dart';
import 'package:ar_society_app/shared/widgets/premium.dart';

/// What a resident owes, first thing on their home screen: the total, how many bills it is spread over, whether any is
/// overdue, and a button to the bills. Read-only: it shows the figures the bills API already returns and changes none.
class ResidentDuesCard extends ConsumerWidget {
  const ResidentDuesCard({super.key});

  /// The tone and wording of the status chip for [s]. Overdue wins over merely due; nothing owed is "all paid".
  static (AppTone, IconData, String) statusFor(MyBillsSummary s) {
    if (s.overdueCount > 0) {
      return (AppTone.danger, Icons.error_outline_rounded, '${s.overdueCount} overdue');
    }
    if (amountOf(s.totalOutstanding) > 0) {
      return (AppTone.warning, Icons.schedule_rounded, 'Payment due');
    }
    return (AppTone.success, Icons.check_circle_outline_rounded, 'All paid');
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final bills = ref.watch(myBillsProvider);
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(AppSpacing.l),
      decoration: BoxDecoration(
        color: AppTheme.cardBg,
        borderRadius: BorderRadius.circular(AppTheme.radiusXl),
        boxShadow: AppTheme.cardShadow,
      ),
      child: bills.when(
        loading: () => const _Loading(),
        error: (_, __) => _Failed(onRetry: () => ref.invalidate(myBillsProvider)),
        data: (s) => _Loaded(summary: s),
      ),
    );
  }
}

class _Loaded extends StatelessWidget {
  final MyBillsSummary summary;
  const _Loaded({required this.summary});

  @override
  Widget build(BuildContext context) {
    final (tone, icon, englishStatus) = ResidentDuesCard.statusFor(summary);
    final statusLabel = summary.overdueCount > 0
        ? context.trf('{n} overdue', {'n': summary.overdueCount})
        : context.tr(englishStatus);
    final owes = amountOf(summary.totalOutstanding) > 0;
    final count = summary.openCount;
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Row(children: [
        AccentBadge(icon: Icons.account_balance_wallet_rounded, accent: kAccents[owes ? 3 : 5], size: 36),
        const SizedBox(width: 10),
        Expanded(
          child: Text(context.tr('Outstanding maintenance'),
              style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: AppTheme.textSecondary)),
        ),
        AppStatusChip(label: statusLabel, tone: tone, icon: icon),
      ]),
      const SizedBox(height: AppSpacing.s),
      Semantics(
        label: owes ? 'Total outstanding ${formatRupees(summary.totalOutstanding)}' : 'Nothing outstanding',
        excludeSemantics: true,
        child: Text(
          formatRupees(summary.totalOutstanding),
          style: const TextStyle(
            fontSize: 34,
            fontWeight: FontWeight.w800,
            letterSpacing: -0.6,
            color: AppTheme.textPrimary,
            fontFeatures: [FontFeature.tabularFigures()],
          ),
        ),
      ),
      const SizedBox(height: 2),
      Text(
        owes
            ? context.trf(count == 1 ? 'Across {n} open bill' : 'Across {n} open bills', {'n': count})
            : context.tr('You have no open bills'),
        style: const TextStyle(fontSize: 13, color: AppTheme.textSecondary),
      ),
      const SizedBox(height: AppSpacing.m),
      SizedBox(
        width: double.infinity,
        height: AppSpacing.minTouch,
        child: FilledButton(
          onPressed: () => context.push(AppRoutes.myBills),
          child: Text(context.tr(owes ? 'View and pay' : 'View bills and receipts')),
        ),
      ),
    ]);
  }
}

class _Loading extends StatelessWidget {
  const _Loading();

  @override
  Widget build(BuildContext context) => Semantics(
        label: 'Loading what is outstanding',
        liveRegion: true,
        child: const Shimmer(
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            SkeletonBox(width: 150, height: 13),
            SizedBox(height: AppSpacing.m),
            SkeletonBox(width: 180, height: 30, radius: 8),
            SizedBox(height: AppSpacing.s),
            SkeletonBox(width: 120, height: 13),
            SizedBox(height: AppSpacing.m),
            SkeletonBox(height: AppSpacing.minTouch, radius: 24),
          ]),
        ),
      );
}

class _Failed extends StatelessWidget {
  final VoidCallback onRetry;
  const _Failed({required this.onRetry});

  @override
  Widget build(BuildContext context) => Semantics(
        liveRegion: true,
        child: Row(children: [
          const Icon(Icons.cloud_off_rounded, color: AppTheme.textSecondary),
          const SizedBox(width: AppSpacing.m),
          Expanded(
            child: Text(context.tr('Could not check what is outstanding'),
                style: const TextStyle(fontSize: 14, color: AppTheme.textPrimary)),
          ),
          TextButton(
            onPressed: onRetry,
            style: TextButton.styleFrom(minimumSize: const Size(AppSpacing.minTouch, AppSpacing.minTouch)),
            child: Text(context.tr('Retry')),
          ),
        ]),
      );
}
