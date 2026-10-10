import 'package:flutter/material.dart';
import 'package:ar_society_app/core/motion/loading.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/layout/app_sheet.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/features/stores/data/stores_api.dart';
import 'package:ar_society_app/features/stores/presentation/providers/stores_providers.dart';
import 'package:ar_society_app/features/stores/presentation/screens/store_sheets.dart';
import 'package:ar_society_app/features/stores/presentation/screens/stores_screen.dart' show IssueCard;
import 'package:ar_society_app/shared/widgets/app_data_table.dart' show StatusPill;
import 'package:ar_society_app/shared/widgets/app_widgets.dart';
import 'package:ar_society_app/shared/widgets/app_form.dart';

/// One item: how much is in stock, buttons to bring stock in, issue it, or correct the count, who has some of it
/// now, and every movement of stock.
class StoreItemScreen extends ConsumerWidget {
  final String itemId;
  const StoreItemScreen({super.key, required this.itemId});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final async = ref.watch(storeItemProvider(itemId));
    final societyId = ref.watch(currentUserProvider)?.societyId ?? '';
    return AppPage(
      title: async.valueOrNull?.name ?? 'Item',
      actions: [
          if (async.valueOrNull != null)
            IconButton(tooltip: 'Edit', icon: const Icon(Icons.edit_outlined), onPressed: () => showAppSheet(context: context, builder: (_) => ItemFormSheet(item: async.value))),
        ],
      body: RefreshIndicator(
        onRefresh: () async => invalidateStores(ref),
        child: async.when(
          loading: () => const AppLoader(),
          error: (e, _) => ListView(padding: const EdgeInsets.all(20), children: [AppErrorBanner(message: friendlyErrorMessage(e))]),
          data: (i) {
            final color = i.out ? AppTheme.error : (i.low ? AppTheme.warning : AppTheme.success);
            final out = ref.watch(storeIssuesProvider((societyId: societyId, status: 'open', itemId: i.id))).valueOrNull ?? const <IssueItem>[];
            final history = ref.watch(stockHistoryProvider(i.id));
            return ResponsiveBody(
              maxWidth: 760,
              child: ListView(padding: const EdgeInsets.fromLTRB(16, 16, 16, 40), children: [
                Container(
                  padding: const EdgeInsets.all(16),
                  decoration: BoxDecoration(color: AppTheme.cardBg, borderRadius: BorderRadius.circular(AppTheme.radiusM), border: Border.all(color: AppTheme.border)),
                  child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    Row(children: [
                      Icon(itemCategoryIcon(i.category), color: AppTheme.textSecondary, size: 18),
                      const SizedBox(width: 6),
                      Text('${i.code} · ${itemCategoryLabel(i.category)}', style: const TextStyle(color: AppTheme.textSecondary)),
                      const Spacer(),
                      if (i.out) const StatusPill('Out of stock', AppTheme.error) else if (i.low) const StatusPill('Running low', AppTheme.warning),
                    ]),
                    const SizedBox(height: 8),
                    Text(i.stockText, style: TextStyle(fontSize: 30, fontWeight: FontWeight.w800, color: color)),
                    Text('in stock · minimum ${qty(i.minimum)} ${unitLabel(i.unit)}', style: const TextStyle(color: AppTheme.textSecondary)),
                    if ((i.location ?? '').isNotEmpty || i.unitCost != null || (i.vendor ?? '').isNotEmpty) ...[
                      const SizedBox(height: 8),
                      Text([if ((i.location ?? '').isNotEmpty) 'Kept at ${i.location}', if (i.unitCost != null) '₹${qty(i.unitCost!)} each', if ((i.vendor ?? '').isNotEmpty) 'From ${i.vendor}'].join(' · '),
                          style: const TextStyle(color: AppTheme.textSecondary, fontSize: 13)),
                    ],
                  ]),
                ),
                const SizedBox(height: 14),
                Wrap(spacing: 10, runSpacing: 10, children: [
                  FilledButton.icon(onPressed: () => showAppSheet(context: context, builder: (_) => StockInSheet(item: i)), icon: const Icon(Icons.add_box_rounded, size: 18), label: const Text('Stock in')),
                  OutlinedButton.icon(
                    onPressed: i.out ? null : () => showAppSheet(context: context, builder: (_) => IssueSheet(item: i)),
                    icon: const Icon(Icons.outbox_rounded, size: 18),
                    label: const Text('Issue'),
                  ),
                  OutlinedButton.icon(onPressed: () => showAppSheet(context: context, builder: (_) => CountSheet(item: i)), icon: const Icon(Icons.fact_check_outlined, size: 18), label: const Text('Correct the count')),
                ]),
                if (out.isNotEmpty) ...[
                  const SizedBox(height: 22),
                  const Text('With people now', style: TextStyle(fontWeight: FontWeight.w800, fontSize: 15)),
                  const SizedBox(height: 8),
                  for (final o in out) IssueCard(issue: o),
                ],
                const SizedBox(height: 22),
                const Text('Every movement', style: TextStyle(fontWeight: FontWeight.w800, fontSize: 15)),
                const SizedBox(height: 4),
                history.when(
                  loading: () => const Padding(padding: EdgeInsets.all(16), child: LinearProgressIndicator()),
                  error: (e, _) => AppErrorBanner(message: friendlyErrorMessage(e)),
                  data: (moves) => moves.isEmpty
                      ? const Padding(padding: EdgeInsets.symmetric(vertical: 12), child: Text('Nothing yet. Record the first stock in.', style: TextStyle(color: AppTheme.textSecondary)))
                      : Column(children: [
                          for (final m in moves)
                            ListTile(
                              dense: true,
                              contentPadding: EdgeInsets.zero,
                              leading: Icon(txnIcon(m.type), size: 20, color: txnAdds(m.type) ? AppTheme.success : AppTheme.textSecondary),
                              title: Text('${txnLabel(m.type)}: ${m.type == 'adjustment' ? 'now ${qty(m.after)}' : '${txnAdds(m.type) ? '+' : '−'}${qty(m.quantity)}'}'),
                              subtitle: Text([
                                if (m.at != null) dayText(m.at),
                                if (m.by != null) m.by!,
                                if ((m.notes ?? '').isNotEmpty) m.notes!,
                                if ((m.ref ?? '').isNotEmpty && m.type == 'stock_in') 'Bill ${m.ref}',
                              ].join(' · ')),
                              trailing: Text('${qty(m.before)} → ${qty(m.after)}', style: const TextStyle(color: AppTheme.textSecondary, fontSize: 12)),
                            ),
                        ]),
                ),
              ]),
            );
          },
        ),
      ),
    );
  }
}
