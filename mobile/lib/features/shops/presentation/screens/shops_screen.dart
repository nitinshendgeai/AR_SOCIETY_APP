import 'package:flutter/material.dart';
import 'package:ar_society_app/core/motion/loading.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/layout/app_shell.dart' show isDesktopLayout;
import 'package:ar_society_app/core/layout/app_sheet.dart';
import 'package:ar_society_app/core/router/app_router.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/features/maintenance_billing/data/maintenance_billing_api.dart' show formatBillDate;
import 'package:ar_society_app/features/shops/data/shops_api.dart';
import 'package:ar_society_app/features/shops/presentation/providers/shops_providers.dart';
import 'package:ar_society_app/features/shops/presentation/widgets/shop_sheet.dart';
import 'package:ar_society_app/shared/widgets/app_data_table.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';
import 'package:ar_society_app/shared/widgets/app_form.dart';

/// The society's shops: who owns each, who runs it, when the owner took possession and which electricity meter it
/// has. A master of its own, apart from the flats.
class ShopsScreen extends ConsumerStatefulWidget {
  const ShopsScreen({super.key});

  @override
  ConsumerState<ShopsScreen> createState() => _ShopsScreenState();
}

class _ShopsScreenState extends ConsumerState<ShopsScreen> {
  String _q = '';
  String? _occupancy;
  bool _noMeter = false;

  List<Shop> _filtered(List<Shop> all) {
    final q = _q.trim().toLowerCase();
    return all.where((s) {
      if (_occupancy != null && s.occupancy != _occupancy) return false;
      if (_noMeter && s.hasMeter) return false;
      if (q.isEmpty) return true;
      return [s.shopNumber, s.ownerName, s.businessName, s.ownerPhone, s.tenantName, s.electricMeterNo, s.location]
          .any((v) => (v ?? '').toLowerCase().contains(q));
    }).toList();
  }

  Future<void> _open([Shop? shop]) =>
      showAppSheet(context: context, builder: (_) => ShopSheet(existing: shop));

  @override
  Widget build(BuildContext context) {
    final societyId = ref.watch(currentUserProvider)?.societyId;
    if (societyId == null) return const Scaffold(body: Center(child: Text('No society context')));
    final desktop = isDesktopLayout(context);
    final async = ref.watch(shopsProvider(societyId));

    return AppPage(
      title: 'Shops',
      actions: [
          AppBarTextAction(
              icon: Icons.upload_file_rounded, label: 'Import', onPressed: () => context.push(AppRoutes.shopsImport)),
          if (desktop) HeaderActionButton(icon: Icons.add_rounded, label: 'Add shop', onPressed: _open),
        ],
      floatingActionButton: desktop
          ? null
          : FloatingActionButton.extended(
              onPressed: _open, icon: const Icon(Icons.add_rounded), label: const Text('Add shop')),
      body: RefreshIndicator(
        onRefresh: () async => ref.invalidate(shopsProvider(societyId)),
        child: async.when(
          loading: () => const SkeletonList(),
          error: (e, _) => ListView(children: [
            Padding(padding: const EdgeInsets.all(24), child: Text(friendlyErrorMessage(e), style: const TextStyle(color: AppTheme.error))),
          ]),
          data: (all) => _content(all, desktop),
        ),
      ),
    );
  }

  Widget _content(List<Shop> all, bool desktop) {
    final shown = _filtered(all);
    final rented = all.where((s) => s.rented).length;
    final vacant = all.where((s) => s.vacant).length;
    final noMeter = all.where((s) => !s.hasMeter).length;

    final kpis = KpiGrid(cards: [
      KpiCard(icon: Icons.storefront_rounded, label: 'Shops', value: '${all.length}', color: AppTheme.primary),
      KpiCard(icon: Icons.key_rounded, label: 'Rented out', value: '$rented', color: AppTheme.success,
          onTap: () => setState(() => _occupancy = _occupancy == 'rented' ? null : 'rented')),
      KpiCard(icon: Icons.door_front_door_outlined, label: 'Vacant', value: '$vacant', color: AppTheme.warning,
          onTap: () => setState(() => _occupancy = _occupancy == 'vacant' ? null : 'vacant')),
      KpiCard(icon: Icons.electric_meter_outlined, label: 'No meter recorded', value: '$noMeter',
          color: noMeter == 0 ? AppTheme.success : AppTheme.error, onTap: () => setState(() => _noMeter = !_noMeter)),
    ]);

    final filters = Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      TextField(
        onChanged: (v) => setState(() => _q = v),
        decoration: const InputDecoration(
            prefixIcon: Icon(Icons.search_rounded), hintText: 'Search shop, owner, business, meter…', isDense: true),
      ),
      const SizedBox(height: 10),
      SingleChildScrollView(
        scrollDirection: Axis.horizontal,
        child: Row(children: [
          _chip('All', _occupancy == null && !_noMeter, () => setState(() { _occupancy = null; _noMeter = false; })),
          for (final o in kShopOccupancy)
            _chip(o.$2, _occupancy == o.$1, () => setState(() => _occupancy = _occupancy == o.$1 ? null : o.$1)),
          _chip('No meter', _noMeter, () => setState(() => _noMeter = !_noMeter)),
        ]),
      ),
    ]);

    final body = shown.isEmpty
        ? AppEmptyState(
            icon: Icons.storefront_outlined,
            title: all.isEmpty ? 'No shops yet' : 'No shop matches',
            subtitle: all.isEmpty
                ? 'Add a shop, or import your list with Import (a CSV with shop, owner, possession date and meter).'
                : 'Try another search or filter.')
        : desktop
            ? _table(shown)
            : Column(children: [for (final s in shown) _card(s)]);

    return ListView(padding: EdgeInsets.fromLTRB(desktop ? 24 : 16, 8, desktop ? 24 : 16, 96), children: [
      kpis,
      const SizedBox(height: 16),
      filters,
      const SizedBox(height: 12),
      body,
    ]);
  }

  Widget _chip(String label, bool selected, VoidCallback onTap) => Padding(
        padding: const EdgeInsets.only(right: 8),
        child: FilterChip(label: Text(label), selected: selected, onSelected: (_) => onTap(), showCheckmark: true),
      );

  Widget _table(List<Shop> shops) => AppDataTable<Shop>(
        rows: shops,
        onRowTap: _open,
        columns: [
          AppDataColumn(label: 'Shop', width: 90, sortKey: (s) => s.shopNumber, cell: (s) => Text(s.shopNumber, style: const TextStyle(fontWeight: FontWeight.w600))),
          AppDataColumn(label: 'Owner', flex: 2, sortKey: (s) => s.ownerName, cell: (s) => Text(s.ownerName, overflow: TextOverflow.ellipsis)),
          AppDataColumn(label: 'Business', flex: 2, cell: (s) => Text(s.businessName ?? '—', overflow: TextOverflow.ellipsis)),
          AppDataColumn(label: 'Occupancy', width: 160, cell: (s) => _occupancyPill(s)),
          AppDataColumn(label: 'Possession', width: 120, sortKey: (s) => s.possessionDate?.millisecondsSinceEpoch ?? 0,
              cell: (s) => Text(s.possessionDate == null ? '—' : formatBillDate(s.possessionDate!))),
          AppDataColumn(label: 'Meter', width: 130, cell: (s) => Text(s.electricMeterNo ?? '—', overflow: TextOverflow.ellipsis)),
        ],
      );

  Widget _occupancyPill(Shop s) => StatusPill(
      occupancyLabel(s.occupancy), s.rented ? AppTheme.success : (s.vacant ? AppTheme.warning : AppTheme.primary));

  Widget _card(Shop s) => Card(
        margin: const EdgeInsets.only(bottom: 8),
        child: InkWell(
          borderRadius: BorderRadius.circular(12),
          onTap: () => _open(s),
          child: Padding(
            padding: const EdgeInsets.all(14),
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Row(children: [
                Expanded(
                  child: Text(
                    [s.shopNumber, if ((s.businessName ?? '').isNotEmpty) s.businessName!].join(' · '),
                    style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w700),
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
                _occupancyPill(s),
              ]),
              const SizedBox(height: 4),
              Text([s.ownerName, if ((s.ownerPhone ?? '').isNotEmpty) s.ownerPhone!].join(' · '),
                  style: const TextStyle(fontSize: 13, color: AppTheme.textSecondary)),
              const SizedBox(height: 6),
              Wrap(spacing: 14, runSpacing: 4, children: [
                _fact(Icons.event_available_rounded,
                    s.possessionDate == null ? 'Possession not recorded' : 'Possession ${formatBillDate(s.possessionDate!)}',
                    muted: s.possessionDate == null),
                _fact(Icons.electric_meter_outlined, s.hasMeter ? 'Meter ${s.electricMeterNo}' : 'No meter recorded',
                    muted: !s.hasMeter),
              ]),
            ]),
          ),
        ),
      );

  Widget _fact(IconData icon, String text, {bool muted = false}) => Row(mainAxisSize: MainAxisSize.min, children: [
        Icon(icon, size: 14, color: muted ? AppTheme.textTertiary : AppTheme.textSecondary),
        const SizedBox(width: 4),
        Text(text, style: TextStyle(fontSize: 12, color: muted ? AppTheme.textTertiary : AppTheme.textSecondary)),
      ]);
}
