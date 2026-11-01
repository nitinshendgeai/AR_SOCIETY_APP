import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/motion/loading.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/maintenance_billing/data/maintenance_billing_api.dart';
import 'package:ar_society_app/features/maintenance_billing/presentation/providers/maintenance_billing_providers.dart';
import 'package:ar_society_app/shared/widgets/app_form.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';

/// The tower-parking part of a billing cycle's bills, flat by flat: what each holder of a tower slot will be charged
/// for the zone's AMC, meter electricity, wallet and fire AMC (per slot held) plus the car-parking charge.
/// A dry run of the same calculation as the cycle preview - nothing is saved.
class TowerParkingPreviewScreen extends ConsumerWidget {
  final String cycleId;
  final String cycleName;
  const TowerParkingPreviewScreen({super.key, required this.cycleId, required this.cycleName});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final async = ref.watch(towerParkingPreviewProvider(cycleId));
    return AppPage(
      title: 'Tower parking · $cycleName',
      body: async.when(
        loading: () => const AppLoader(),
        error: (e, _) => Center(
          child: Padding(
            padding: const EdgeInsets.all(24),
            child: Text(friendlyErrorMessage(e), style: const TextStyle(color: AppTheme.error)),
          ),
        ),
        data: (p) {
          if (p.zones.isEmpty) {
            return const AppEmptyState(
              icon: Icons.local_parking_rounded,
              title: 'No tower parking charges',
              subtitle: 'Add a charge head with "Only for parking zone" set to the Tower zone '
                  '(Tower Parking AMC, Electricity, Wallet, Fire AMC), then come back.',
            );
          }
          return RefreshIndicator(
            onRefresh: () async => ref.invalidate(towerParkingPreviewProvider(cycleId)),
            child: ListView(
              padding: const EdgeInsets.all(16),
              children: [
                KpiGrid(cards: [
                  KpiCard(
                    icon: Icons.local_parking_rounded,
                    label: 'Tower parking total',
                    value: formatRupees(p.total),
                    color: AppTheme.primary,
                    note: p.months == 1 ? '1 month' : '${p.months} months',
                  ),
                  KpiCard(
                    icon: Icons.home_work_rounded,
                    label: 'Slot holders',
                    value: '${p.flats.length}',
                    color: AppTheme.success,
                    note: '${p.zones.fold<int>(0, (a, z) => a + z.slots)} slots',
                  ),
                ]),
                for (final z in p.zones) ...[
                  const SizedBox(height: 10),
                  Card(
                    margin: EdgeInsets.zero,
                    child: ListTile(
                      leading: const Icon(Icons.layers_rounded, color: AppTheme.primary),
                      title: Text('${z.zoneName}: ${formatRupees(z.total)}',
                          style: const TextStyle(fontWeight: FontWeight.w600)),
                      subtitle: Text(
                          '${z.holders} flat(s) · ${z.slots} slot(s)\n${z.heads.join(' · ')}',
                          style: const TextStyle(fontSize: 12.5)),
                      isThreeLine: true,
                    ),
                  ),
                ],
                for (final w in p.warnings) ...[
                  const SizedBox(height: 10),
                  Container(
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color: AppTheme.warningSoft,
                      borderRadius: BorderRadius.circular(AppTheme.radiusM),
                    ),
                    child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                      const Icon(Icons.warning_amber_rounded, color: AppTheme.warning, size: 20),
                      const SizedBox(width: 10),
                      Expanded(child: Text(w, style: const TextStyle(fontSize: 13))),
                    ]),
                  ),
                ],
                const SizedBox(height: 16),
                if (p.flats.isEmpty)
                  const AppEmptyState(
                    icon: Icons.local_parking_rounded,
                    title: 'No flat holds a tower slot',
                    subtitle: 'Allot tower slots to flats under Parking.',
                  ),
                for (final f in p.flats) _HolderCard(holder: f),
              ],
            ),
          );
        },
      ),
    );
  }
}

class _HolderCard extends StatelessWidget {
  final TowerHolderPreview holder;
  const _HolderCard({required this.holder});

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 10),
      clipBehavior: Clip.antiAlias,
      child: ExpansionTile(
        initiallyExpanded: true,
        title: Text(holder.flatLabel, style: const TextStyle(fontWeight: FontWeight.w600)),
        subtitle: Text('${holder.zoneName} · ${holder.slots} slot${holder.slots == 1 ? '' : 's'}',
            style: const TextStyle(fontSize: 12)),
        trailing: Text(formatRupees(holder.total), style: const TextStyle(fontWeight: FontWeight.w700)),
        childrenPadding: const EdgeInsets.fromLTRB(16, 0, 16, 12),
        children: [
          for (final l in holder.lines)
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 4),
              child: Row(children: [
                Expanded(child: Text(l.description, style: const TextStyle(fontSize: 13))),
                Text(formatRupees(l.total), style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w500)),
              ]),
            ),
          const Divider(height: 16),
          Row(children: [
            const Expanded(child: Text('Parking on this bill', style: TextStyle(fontWeight: FontWeight.w700))),
            Text(formatRupees(holder.total), style: const TextStyle(fontWeight: FontWeight.w700)),
          ]),
        ],
      ),
    );
  }
}
