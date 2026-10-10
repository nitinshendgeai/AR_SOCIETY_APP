import 'package:flutter/material.dart';
import 'package:ar_society_app/core/motion/loading.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/layout/app_sheet.dart';
import 'package:ar_society_app/core/router/app_router.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/accounts/data/accounts_api.dart' show formatInr;
import 'package:ar_society_app/features/assets/data/assets_api.dart';
import 'package:ar_society_app/features/assets/presentation/providers/assets_providers.dart';
import 'package:ar_society_app/features/assets/presentation/screens/asset_sheets.dart';
import 'package:ar_society_app/features/vendor/presentation/screens/vendors_work_screen.dart' show contractRoute, workOrderRoute;
import 'package:ar_society_app/shared/widgets/app_data_table.dart' show StatusPill;
import 'package:ar_society_app/shared/widgets/app_widgets.dart';
import 'package:ar_society_app/shared/widgets/app_form.dart';

/// One asset: what it is, when it is next due, and everything that has been done to it.
class AssetDetailScreen extends ConsumerWidget {
  final String assetId;
  const AssetDetailScreen({super.key, required this.assetId});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final async = ref.watch(assetHistoryProvider(assetId));
    return AppPage(
      title: async.valueOrNull?.asset.name ?? 'Asset',
      actions: [
          if (async.valueOrNull != null) ...[
            IconButton(
              tooltip: 'Edit',
              icon: const Icon(Icons.edit_outlined),
              onPressed: () => showAppSheet(
                  context: context, builder: (_) => AssetFormSheet(asset: async.value!.asset)),
            ),
            _StatusMenu(asset: async.value!.asset),
          ],
        ],
      body: RefreshIndicator(
        onRefresh: () async => invalidateAssets(ref),
        child: async.when(
          loading: () => const AppLoader(),
          error: (e, _) => ListView(padding: const EdgeInsets.all(20), children: [AppErrorBanner(message: friendlyErrorMessage(e))]),
          data: (h) => ResponsiveBody(maxWidth: 820, child: _Body(history: h)),
        ),
      ),
    );
  }
}

class _StatusMenu extends ConsumerWidget {
  final Asset asset;
  const _StatusMenu({required this.asset});

  Future<void> _set(BuildContext context, WidgetRef ref, String status, String confirmText) async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: Text(confirmText),
        content: Text(status == 'active'
            ? 'It will be counted among the assets in use again, and its service schedule resumes.'
            : 'It stays on record with its history but is left out of the counts and needs no service.'),
        actions: [
          TextButton(onPressed: () => Navigator.of(dialogContext).pop(false), child: const Text('Cancel')),
          FilledButton(onPressed: () => Navigator.of(dialogContext).pop(true), child: const Text('Yes')),
        ],
      ),
    );
    if (ok != true) return;
    try {
      await ref.read(assetsApiProvider).update(asset.id, {'status': status});
      invalidateAssets(ref);
      if (context.mounted) AppToast.success(context, 'Marked as ${assetStatusLabel(status).toLowerCase()}');
    } catch (e) {
      if (context.mounted) showErrorToast(context, e);
    }
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) => PopupMenuButton<String>(
        tooltip: 'More',
        onSelected: (v) => switch (v) {
          'active' => _set(context, ref, 'active', 'Put ${asset.name} back in use?'),
          'under_maintenance' => _set(context, ref, 'under_maintenance', 'Mark ${asset.name} as under repair?'),
          'retired' => _set(context, ref, 'retired', 'Retire ${asset.name}?'),
          'disposed' => _set(context, ref, 'disposed', 'Mark ${asset.name} as sold or scrapped?'),
          'lost' => _set(context, ref, 'lost', 'Mark ${asset.name} as lost?'),
          _ => null,
        },
        itemBuilder: (_) => [
          if (asset.status != 'active') const PopupMenuItem(value: 'active', child: Text('Put back in use')),
          if (asset.status == 'active') const PopupMenuItem(value: 'under_maintenance', child: Text('Mark as under repair')),
          if (!asset.isRetired) const PopupMenuItem(value: 'retired', child: Text('Retire')),
          if (!asset.isRetired) const PopupMenuItem(value: 'disposed', child: Text('Sold or scrapped')),
          if (!asset.isRetired) const PopupMenuItem(value: 'lost', child: Text('Lost')),
        ],
      );
}

class _Body extends ConsumerWidget {
  final AssetHistory history;
  const _Body({required this.history});

  Asset get a => history.asset;

  Future<void> _logged(BuildContext context, LoggedService? done) async {
    if (done == null || !context.mounted) return;
    AppToast.success(context, 'Service saved');
    if (done.cost <= 0) return;
    // A service that cost money is an expense of the society: offer to book it.
    final book = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: Text('Record ${formatInr(done.cost)} as an expense?'),
        content: const Text('It goes into the books as a payment and counts towards the maintenance element you choose.'),
        actions: [
          TextButton(onPressed: () => Navigator.of(dialogContext).pop(false), child: const Text('Not now')),
          FilledButton(onPressed: () => Navigator.of(dialogContext).pop(true), child: const Text('Record expense')),
        ],
      ),
    );
    if (book == true && context.mounted) {
      context.push(AppRoutes.accountsExpenseNew, extra: {'amount': done.cost, 'note': done.note});
    }
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final open = history.services.where((s) => s.isOpen).toList()..sort((x, y) => x.scheduledDate.compareTo(y.scheduledDate));
    final done = history.services.where((s) => s.status == 'completed').toList();
    return ListView(padding: const EdgeInsets.fromLTRB(16, 16, 16, 40), children: [
      _Header(asset: a),
      const SizedBox(height: 14),
      if (!a.isRetired)
        Wrap(spacing: 10, runSpacing: 10, children: [
          FilledButton.icon(
            onPressed: () async =>
                _logged(context, await showAppSheet<LoggedService>(context: context, builder: (_) => LogServiceSheet(asset: a))),
            icon: const Icon(Icons.build_rounded, size: 18),
            label: const Text('Log a service'),
          ),
          OutlinedButton.icon(
            onPressed: () => showAppSheet(context: context, builder: (_) => ScheduleServiceSheet(asset: a)),
            icon: const Icon(Icons.event_rounded, size: 18),
            label: const Text('Plan a service'),
          ),
          OutlinedButton.icon(
            onPressed: () => showAppSheet(context: context, builder: (_) => AmcSheet(asset: a)),
            icon: const Icon(Icons.assignment_outlined, size: 18),
            label: const Text('Add service contract'),
          ),
        ]),
      const SizedBox(height: 16),
      _Section(title: 'Service schedule', children: [
        _Row('Serviced every', a.serviceIntervalMonths == null ? 'Not set' : '${a.serviceIntervalMonths} months'),
        _Row('Last serviced', a.lastServicedOn == null ? 'Not recorded' : formatDay(a.lastServicedOn!)),
        _Row('Next due', a.nextServiceDue == null ? 'Not scheduled' : formatDay(a.nextServiceDue!),
            valueColor: a.serviceStatus == 'overdue' ? AppTheme.error : null),
      ]),
      if (open.isNotEmpty)
        _Section(title: 'Planned services', children: [
          for (final s in open) _OpenService(asset: a, service: s, onLogged: (r) => _logged(context, r)),
        ]),
      _Section(title: 'About this asset', children: [
        _Row('Kind', assetCategoryLabel(a.category)),
        _Row('Where', a.location),
        _Row('Make / model', a.modelNumber),
        _Row('Serial no.', a.serialNumber),
        _Row('Bought on', a.purchaseDate == null ? null : formatDay(a.purchaseDate!)),
        _Row('Cost', a.purchaseCost == null ? null : formatInr(a.purchaseCost!)),
        _Row('Bought from', a.vendorName),
        _Row('Their phone', a.vendorContact),
        _Row('Invoice no.', a.invoiceNumber),
        _Row('Warranty until', a.warrantyExpiry == null ? null : formatDay(a.warrantyExpiry!),
            valueColor: a.warrantyStatus == 'expired' ? AppTheme.error : (a.warrantyStatus == 'expiring' ? AppTheme.warning : null)),
        _Row('Expected life', a.expectedLifeYears == null ? null : '${a.expectedLifeYears} years'),
        if ((a.description ?? '').isNotEmpty) _Row('Notes', a.description),
      ]),
      _Section(
        title: 'Service history',
        trailing: done.isEmpty ? null : 'Spent ${formatInr(history.totalServiceCost)}',
        children: [
          if (done.isEmpty)
            const Padding(
              padding: EdgeInsets.symmetric(vertical: 6),
              child: Text('Nothing logged yet. Use "Log a service" after each visit.', style: TextStyle(color: AppTheme.textSecondary)),
            ),
          for (final s in done)
            ListTile(
              contentPadding: EdgeInsets.zero,
              dense: true,
              title: Text('${maintenanceTypeLabel(s.type)} · ${formatDay(s.completedDate ?? s.scheduledDate)}'),
              subtitle: Text([
                if ((s.vendorName ?? '').isNotEmpty) s.vendorName!,
                if ((s.findings ?? '').isNotEmpty) s.findings!,
              ].join(' · ')),
              trailing: s.cost == null || s.cost == 0 ? null : Text(formatInr(s.cost!), style: const TextStyle(fontWeight: FontWeight.w600)),
            ),
        ],
      ),
      if (history.amc.isNotEmpty || history.contracts.isNotEmpty || history.workOrders.isNotEmpty)
        _Section(title: 'Contracts and work', children: [
          for (final c in history.amc)
            ListTile(
              contentPadding: EdgeInsets.zero,
              dense: true,
              leading: const Icon(Icons.assignment_outlined),
              title: Text('${c.vendorName}${c.contractNumber == null ? '' : ' · ${c.contractNumber}'}'),
              subtitle: Text('${formatDay(c.startDate)} to ${formatDay(c.endDate)}'
                  '${c.annualCost == null ? '' : ' · ${formatInr(c.annualCost!)} a year'}'
                  '${c.comprehensive ? ' · parts included' : ''}'),
              trailing: c.ended
                  ? const StatusPill('Ended', AppTheme.textSecondary)
                  : c.daysLeft <= 30
                      ? StatusPill('Ends in ${c.daysLeft < 0 ? 0 : c.daysLeft} days', AppTheme.warning)
                      : const StatusPill('In force', AppTheme.success),
            ),
          for (final c in history.contracts)
            ListTile(
              contentPadding: EdgeInsets.zero,
              dense: true,
              leading: const Icon(Icons.handshake_outlined),
              title: Text('${c.number} · ${c.name}'),
              subtitle: Text('${formatDay(c.startDate)} to ${formatDay(c.endDate)}${c.annualValue == null ? '' : ' · ${formatInr(c.annualValue!)} a year'}'),
              trailing: StatusPill(c.status, AppTheme.primary),
              onTap: () => context.push(contractRoute(c.id)),
            ),
          for (final w in history.workOrders)
            ListTile(
              contentPadding: EdgeInsets.zero,
              dense: true,
              leading: const Icon(Icons.handyman_outlined),
              title: Text('${w.number} · ${w.title}'),
              subtitle: w.estimatedCost == null ? null : Text('Estimated ${formatInr(w.estimatedCost!)}'),
              trailing: StatusPill(w.status, AppTheme.primary),
              onTap: () => context.push(workOrderRoute(w.id)),
            ),
        ]),
      if (history.log.isNotEmpty)
        _Section(title: 'Activity', children: [
          for (final l in history.log.take(12))
            ListTile(
              contentPadding: EdgeInsets.zero,
              dense: true,
              title: Text(_logLabel(l.action)),
              subtitle: (l.notes ?? '').isEmpty ? null : Text(l.notes!, maxLines: 2, overflow: TextOverflow.ellipsis),
              trailing: Text(formatDay(l.when.toLocal()), style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
            ),
        ]),
    ]);
  }
}

String _logLabel(String action) => switch (action) {
      'REGISTERED' => 'Added to the register',
      'ASSIGNED' => 'Handed over',
      'MAINTENANCE_COMPLETED' => 'Service done',
      'STATUS_CHANGED' => 'Status changed',
      _ => action,
    };

class _Header extends StatelessWidget {
  final Asset asset;
  const _Header({required this.asset});

  @override
  Widget build(BuildContext context) {
    final a = asset;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Container(
            width: 52,
            height: 52,
            decoration: BoxDecoration(color: AppTheme.primary.withOpacity(0.1), borderRadius: BorderRadius.circular(12)),
            child: Icon(assetCategoryIcon(a.category), color: AppTheme.primary, size: 28),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text(a.name, style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w700)),
              const SizedBox(height: 2),
              Text([a.assetCode, assetCategoryLabel(a.category), if ((a.location ?? '').isNotEmpty) a.location!].join(' · '),
                  style: const TextStyle(color: AppTheme.textSecondary, fontSize: 13)),
              const SizedBox(height: 10),
              Wrap(spacing: 8, runSpacing: 6, children: [
                StatusPill(assetStatusLabel(a.status), a.status == 'active' ? AppTheme.success : (a.status == 'under_maintenance' ? AppTheme.warning : AppTheme.textSecondary)),
                if (a.serviceStatus != 'none') StatusPill(serviceLabel(a.serviceStatus, a.daysToService), serviceColor(a.serviceStatus)),
                if (a.warrantyStatus != 'none') StatusPill(warrantyLabel(a.warrantyStatus), warrantyColor(a.warrantyStatus)),
              ]),
            ]),
          ),
        ]),
      ),
    );
  }
}

class _Section extends StatelessWidget {
  final String title;
  final String? trailing;
  final List<Widget> children;
  const _Section({required this.title, required this.children, this.trailing});

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.only(bottom: 14),
        child: Card(
          child: Padding(
            padding: const EdgeInsets.fromLTRB(16, 14, 16, 10),
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Row(children: [
                Expanded(child: Text(title, style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 14))),
                if (trailing != null) Text(trailing!, style: const TextStyle(fontSize: 12.5, color: AppTheme.textSecondary)),
              ]),
              const SizedBox(height: 6),
              ...children,
            ]),
          ),
        ),
      );
}

class _Row extends StatelessWidget {
  final String label;
  final String? value;
  final Color? valueColor;
  const _Row(this.label, this.value, {this.valueColor});

  @override
  Widget build(BuildContext context) {
    if (value == null || value!.isEmpty) return const SizedBox.shrink();
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
        SizedBox(width: 120, child: Text(label, style: const TextStyle(fontSize: 13, color: AppTheme.textSecondary))),
        Expanded(child: Text(value!, style: TextStyle(fontSize: 13.5, fontWeight: FontWeight.w500, color: valueColor))),
      ]),
    );
  }
}

class _OpenService extends ConsumerWidget {
  final Asset asset;
  final AssetService service;
  final Future<void> Function(LoggedService?) onLogged;
  const _OpenService({required this.asset, required this.service, required this.onLogged});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final late = service.scheduledDate.isBefore(DateTime(DateTime.now().year, DateTime.now().month, DateTime.now().day));
    return ListTile(
      contentPadding: EdgeInsets.zero,
      dense: true,
      title: Text('${maintenanceTypeLabel(service.type)} · ${formatDay(service.scheduledDate)}'),
      subtitle: Text([
        if ((service.vendorName ?? '').isNotEmpty) service.vendorName!,
        if ((service.description ?? '').isNotEmpty) service.description!,
        if (late) 'Past its date',
      ].join(' · ')),
      trailing: Row(mainAxisSize: MainAxisSize.min, children: [
        TextButton(
          onPressed: () async => onLogged(await showAppSheet<LoggedService>(
              context: context, builder: (_) => LogServiceSheet(asset: asset, service: service))),
          child: const Text('Done'),
        ),
        IconButton(
          tooltip: 'Cancel this visit',
          icon: const Icon(Icons.close_rounded, size: 18),
          onPressed: () async {
            try {
              await ref.read(assetsApiProvider).cancelService(service.id);
              invalidateAssets(ref);
            } catch (e) {
              if (context.mounted) showErrorToast(context, e);
            }
          },
        ),
      ]),
    );
  }
}
