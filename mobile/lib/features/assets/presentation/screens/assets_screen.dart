import 'package:flutter/material.dart';
import 'package:ar_society_app/core/motion/loading.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/layout/app_shell.dart' show isDesktopLayout;
import 'package:ar_society_app/core/layout/app_sheet.dart';
import 'package:ar_society_app/core/router/app_router.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/accounts/data/accounts_api.dart' show formatInrShort;
import 'package:ar_society_app/features/assets/data/assets_api.dart';
import 'package:ar_society_app/features/assets/presentation/providers/assets_providers.dart';
import 'package:ar_society_app/features/assets/presentation/screens/asset_sheets.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/shared/widgets/app_data_table.dart' show HeaderActionButton, StatusPill;
import 'package:ar_society_app/shared/widgets/app_widgets.dart';
import 'package:ar_society_app/shared/widgets/app_form.dart';

String assetRoute(String id) => AppRoutes.assetDetail.replaceFirst(':id', id);

enum _View { all, needsService, underMaintenance, retired }

/// What the society owns: air conditioners, water pumps, the lift, the generator… Each with where it is,
/// its warranty, when it is next due for service, and (on its own page) everything done to it.
class AssetsScreen extends ConsumerStatefulWidget {
  const AssetsScreen({super.key});

  @override
  ConsumerState<AssetsScreen> createState() => _AssetsScreenState();
}

class _AssetsScreenState extends ConsumerState<AssetsScreen> {
  _View _view = _View.all;
  String? _category;
  final _search = TextEditingController();
  String _q = '';

  @override
  void dispose() {
    _search.dispose();
    super.dispose();
  }

  Future<void> _add(String societyId) async {
    final saved = await showAppSheet<Asset>(context: context, builder: (_) => const AssetFormSheet());
    if (saved != null && mounted) context.push(assetRoute(saved.id));
  }

  AssetListKey _key(String societyId) => (
        societyId: societyId,
        category: _category,
        status: _view == _View.underMaintenance ? 'under_maintenance' : null,
        due: _view == _View.needsService,
      );

  @override
  Widget build(BuildContext context) {
    final societyId = ref.watch(currentUserProvider)?.societyId;
    if (societyId == null) return const Scaffold(body: Center(child: Text('No society context')));
    final desktop = isDesktopLayout(context);
    final summary = ref.watch(assetSummaryProvider(societyId)).valueOrNull ?? const AssetSummary();
    final list = ref.watch(assetListProvider(_key(societyId)));

    return AppPage(
      title: 'Assets',
      actions: [if (desktop) HeaderActionButton(icon: Icons.add_rounded, label: 'Add asset', onPressed: () => _add(societyId))],
      floatingActionButton: desktop
          ? null
          : FloatingActionButton.extended(
              onPressed: () => _add(societyId), icon: const Icon(Icons.add_rounded), label: const Text('Add asset')),
      body: RefreshIndicator(
        onRefresh: () async => invalidateAssets(ref),
        child: ResponsiveBody(
          maxWidth: 960,
          child: ListView(padding: const EdgeInsets.fromLTRB(16, 16, 16, 96), children: [
            KpiGrid(cards: [
              KpiCard(
                icon: Icons.inventory_2_outlined,
                label: 'Assets',
                value: '${summary.total - summary.retired}',
                color: AppTheme.primary,
                note: summary.retired > 0 ? '${summary.retired} retired' : 'in use',
                onTap: () => setState(() => _view = _View.all),
              ),
              KpiCard(
                icon: Icons.build_circle_outlined,
                label: 'Service due',
                value: '${summary.needsService}',
                color: summary.serviceOverdue > 0 ? AppTheme.error : (summary.needsService > 0 ? AppTheme.warning : AppTheme.success),
                note: summary.serviceOverdue > 0 ? '${summary.serviceOverdue} overdue' : 'in the next 30 days',
                onTap: () => setState(() => _view = _View.needsService),
              ),
              KpiCard(
                icon: Icons.verified_user_outlined,
                label: 'Warranty ending',
                value: '${summary.warrantyExpiring}',
                color: summary.warrantyExpiring > 0 ? AppTheme.warning : AppTheme.success,
                note: summary.warrantyExpired > 0 ? '${summary.warrantyExpired} already ended' : 'in the next 30 days',
              ),
              KpiCard(
                icon: Icons.currency_rupee_rounded,
                label: 'Value at cost',
                value: formatInrShort(summary.totalPurchaseCost),
                color: AppTheme.secondary,
                note: summary.amcExpiring > 0 ? '${summary.amcExpiring} service contract${summary.amcExpiring == 1 ? '' : 's'} ending' : null,
              ),
            ]),
            const SizedBox(height: 16),
            TextField(
              controller: _search,
              onChanged: (v) => setState(() => _q = v.trim().toLowerCase()),
              decoration: InputDecoration(
                hintText: 'Search by name, code, place or serial no.',
                prefixIcon: const Icon(Icons.search_rounded),
                suffixIcon: _q.isEmpty
                    ? null
                    : IconButton(
                        icon: const Icon(Icons.close_rounded, size: 18),
                        onPressed: () => setState(() {
                          _search.clear();
                          _q = '';
                        })),
              ),
            ),
            const SizedBox(height: 10),
            SingleChildScrollView(
              scrollDirection: Axis.horizontal,
              child: Row(children: [
                for (final v in const [
                  (_View.all, 'All'),
                  (_View.needsService, 'Needs service'),
                  (_View.underMaintenance, 'Under repair'),
                  (_View.retired, 'Retired'),
                ])
                  Padding(
                    padding: const EdgeInsets.only(right: 8),
                    child: ChoiceChip(label: Text(v.$2), selected: _view == v.$1, onSelected: (_) => setState(() => _view = v.$1)),
                  ),
                const SizedBox(width: 4),
                _CategoryMenu(value: _category, onChanged: (c) => setState(() => _category = c)),
              ]),
            ),
            const SizedBox(height: 12),
            list.when(
              loading: () => const SkeletonList(),
              error: (e, _) => AppErrorBanner(message: friendlyErrorMessage(e)),
              data: (all) {
                var rows = all;
                if (_view == _View.retired) rows = all.where((a) => a.isRetired).toList();
                if (_view != _View.retired) rows = rows.where((a) => !a.isRetired).toList();
                if (_q.isNotEmpty) {
                  rows = rows
                      .where((a) => [a.name, a.assetCode, a.location, a.serialNumber, a.modelNumber]
                          .any((s) => (s ?? '').toLowerCase().contains(_q)))
                      .toList();
                }
                if (rows.isEmpty) return _empty(societyId, all.isEmpty && _q.isEmpty && _category == null && _view == _View.all);
                return Column(children: [for (final a in rows) _AssetTile(asset: a)]);
              },
            ),
          ]),
        ),
      ),
    );
  }

  Widget _empty(String societyId, bool none) => Padding(
        padding: const EdgeInsets.only(top: 24),
        child: AppEmptyState(
          icon: Icons.inventory_2_outlined,
          title: none ? 'No assets recorded yet' : 'Nothing matches',
          subtitle: none
              ? 'Add what the society owns: the lift, water pumps, generator, air conditioners, CCTV. '
                  'Give each its service interval and the app will tell you when a service is due.'
              : 'Try another search or filter.',
          actionLabel: none ? 'Add the first asset' : null,
          onAction: none ? () => _add(societyId) : null,
        ),
      );
}

class _CategoryMenu extends StatelessWidget {
  final String? value;
  final ValueChanged<String?> onChanged;
  const _CategoryMenu({required this.value, required this.onChanged});

  @override
  Widget build(BuildContext context) => PopupMenuButton<String?>(
        tooltip: 'Kind of asset',
        onSelected: onChanged,
        itemBuilder: (_) => [
          const PopupMenuItem<String?>(value: null, child: Text('All kinds')),
          for (final c in kAssetCategories)
            PopupMenuItem<String?>(value: c.$1, child: Row(children: [Icon(c.$3, size: 18), const SizedBox(width: 10), Text(c.$2)])),
        ],
        child: Chip(
          avatar: Icon(value == null ? Icons.filter_list_rounded : assetCategoryIcon(value!), size: 18),
          label: Text(value == null ? 'Kind' : assetCategoryLabel(value!)),
          deleteIcon: value == null ? null : const Icon(Icons.close_rounded, size: 16),
          onDeleted: value == null ? null : () => onChanged(null),
        ),
      );
}

class _AssetTile extends StatelessWidget {
  final Asset asset;
  const _AssetTile({required this.asset});

  @override
  Widget build(BuildContext context) {
    final a = asset;
    final svc = a.serviceStatus;
    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      child: InkWell(
        borderRadius: BorderRadius.circular(AppTheme.radiusM),
        onTap: () => context.push(assetRoute(a.id)),
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: Row(children: [
            Container(
              width: 42,
              height: 42,
              decoration: BoxDecoration(color: AppTheme.primary.withOpacity(0.1), borderRadius: BorderRadius.circular(10)),
              child: Icon(assetCategoryIcon(a.category), color: AppTheme.primary, size: 22),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text(a.name, maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 14.5)),
                const SizedBox(height: 2),
                Text(
                  [a.assetCode, assetCategoryLabel(a.category), if ((a.location ?? '').isNotEmpty) a.location!].join(' · '),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary),
                ),
                if (a.warrantyStatus == 'expiring' || a.warrantyStatus == 'expired')
                  Padding(
                    padding: const EdgeInsets.only(top: 2),
                    child: Text(warrantyLabel(a.warrantyStatus),
                        style: TextStyle(fontSize: 11.5, color: warrantyColor(a.warrantyStatus), fontWeight: FontWeight.w600)),
                  ),
              ]),
            ),
            const SizedBox(width: 8),
            if (a.isRetired)
              StatusPill(assetStatusLabel(a.status), AppTheme.textSecondary)
            else if (a.status == 'under_maintenance')
              const StatusPill('Under repair', AppTheme.warning)
            else if (svc != 'none')
              StatusPill(serviceLabel(svc, a.daysToService), serviceColor(svc)),
          ]),
        ),
      ),
    );
  }
}
