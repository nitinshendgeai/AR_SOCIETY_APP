import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/layout/app_shell.dart' show isDesktopLayout;
import 'package:ar_society_app/core/layout/app_sheet.dart';
import 'package:ar_society_app/core/router/app_router.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/accounts/data/accounts_api.dart' show formatInrShort;
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/features/stores/data/stores_api.dart';
import 'package:ar_society_app/features/stores/presentation/providers/stores_providers.dart';
import 'package:ar_society_app/features/stores/presentation/screens/store_sheets.dart';
import 'package:ar_society_app/shared/widgets/app_data_table.dart' show HeaderActionButton, StatusPill;
import 'package:ar_society_app/shared/widgets/app_widgets.dart';

String storeItemRoute(String id) => AppRoutes.storeItem.replaceFirst(':id', id);

/// The consumables the society keeps: cleaning supplies, tools, uniforms, bulbs. What is in stock, what is running
/// low, and who has what.
class StoresScreen extends ConsumerStatefulWidget {
  const StoresScreen({super.key});

  @override
  ConsumerState<StoresScreen> createState() => _StoresScreenState();
}

enum _View { all, low }

class _StoresScreenState extends ConsumerState<StoresScreen> with SingleTickerProviderStateMixin {
  late final _tabs = TabController(length: 2, vsync: this);
  final _search = TextEditingController();
  String _q = '';
  String? _category;
  _View _view = _View.all;

  @override
  void dispose() {
    _tabs.dispose();
    _search.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final societyId = ref.watch(currentUserProvider)?.societyId;
    if (societyId == null) return const Scaffold(body: Center(child: Text('No society context')));
    final desktop = isDesktopLayout(context);
    void add() => showAppSheet(context: context, builder: (_) => const ItemFormSheet());

    return Scaffold(
      backgroundColor: AppTheme.surface,
      appBar: AppBar(
        title: const Text('Stores'),
        actions: [if (desktop) HeaderActionButton(icon: Icons.add_rounded, label: 'Add item', onPressed: add)],
        bottom: TabBar(controller: _tabs, tabs: const [Tab(text: 'Items'), Tab(text: 'Issued')]),
      ),
      floatingActionButton: desktop ? null : FloatingActionButton.extended(onPressed: add, icon: const Icon(Icons.add_rounded), label: const Text('Add item')),
      body: TabBarView(controller: _tabs, children: [_items(societyId), _IssuedTab(societyId: societyId)]),
    );
  }

  Widget _items(String societyId) {
    final summary = ref.watch(storesSummaryProvider(societyId)).valueOrNull ?? const StoresSummary();
    final list = ref.watch(storeItemsProvider(societyId));
    return RefreshIndicator(
      onRefresh: () async => invalidateStores(ref),
      child: ResponsiveBody(
        maxWidth: 960,
        child: ListView(padding: const EdgeInsets.fromLTRB(16, 16, 16, 96), children: [
          KpiGrid(cards: [
            KpiCard(icon: Icons.inventory_2_outlined, label: 'Items', value: '${summary.items}', color: AppTheme.primary, note: 'in the stores', onTap: () => setState(() => _view = _View.all)),
            KpiCard(
              icon: Icons.trending_down_rounded,
              label: 'Running low',
              value: '${summary.low}',
              color: summary.low > 0 ? AppTheme.warning : AppTheme.success,
              note: summary.outOfStock > 0 ? '${summary.outOfStock} out of stock' : 'all above the minimum',
              onTap: () => setState(() => _view = _View.low),
            ),
            KpiCard(
              icon: Icons.outbox_rounded,
              label: 'With people',
              value: '${summary.withPeople}',
              color: summary.overdue > 0 ? AppTheme.error : AppTheme.secondary,
              note: summary.overdue > 0 ? '${summary.overdue} overdue' : 'issued, not yet back',
              onTap: () => _tabs.animateTo(1),
            ),
            KpiCard(icon: Icons.currency_rupee_rounded, label: 'Stock value', value: formatInrShort(summary.value), color: AppTheme.secondary, note: 'at the costs you entered'),
          ]),
          const SizedBox(height: 16),
          TextField(
            controller: _search,
            onChanged: (v) => setState(() => _q = v.trim().toLowerCase()),
            decoration: InputDecoration(
              hintText: 'Search by name or code',
              prefixIcon: const Icon(Icons.search_rounded),
              suffixIcon: _q.isEmpty ? null : IconButton(icon: const Icon(Icons.close_rounded, size: 18), onPressed: () => setState(() { _search.clear(); _q = ''; })),
            ),
          ),
          const SizedBox(height: 10),
          SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            child: Row(children: [
              ChoiceChip(label: const Text('All'), selected: _view == _View.all && _category == null, onSelected: (_) => setState(() { _view = _View.all; _category = null; })),
              const SizedBox(width: 8),
              ChoiceChip(label: const Text('Running low'), selected: _view == _View.low, onSelected: (_) => setState(() => _view = _View.low)),
              const SizedBox(width: 8),
              PopupMenuButton<String?>(
                tooltip: 'Kind',
                onSelected: (c) => setState(() => _category = c),
                itemBuilder: (_) => [
                  const PopupMenuItem<String?>(value: null, child: Text('All kinds')),
                  for (final c in kItemCategories) PopupMenuItem<String?>(value: c.$1, child: Row(children: [Icon(c.$3, size: 18), const SizedBox(width: 10), Text(c.$2)])),
                ],
                child: Chip(avatar: Icon(_category == null ? Icons.filter_list_rounded : itemCategoryIcon(_category!), size: 18), label: Text(_category == null ? 'Kind' : itemCategoryLabel(_category!))),
              ),
            ]),
          ),
          const SizedBox(height: 12),
          list.when(
            loading: () => const Padding(padding: EdgeInsets.all(40), child: Center(child: CircularProgressIndicator(color: AppTheme.primary))),
            error: (e, _) => AppErrorBanner(message: friendlyErrorMessage(e)),
            data: (all) {
              var rows = all.where((i) => _view == _View.all || i.low).toList();
              if (_category != null) rows = rows.where((i) => i.category == _category).toList();
              if (_q.isNotEmpty) rows = rows.where((i) => '${i.name} ${i.code}'.toLowerCase().contains(_q)).toList();
              if (rows.isEmpty) {
                return Padding(
                  padding: const EdgeInsets.only(top: 24),
                  child: AppEmptyState(
                    icon: Icons.inventory_2_outlined,
                    title: all.isEmpty ? 'Nothing in the stores yet' : 'Nothing matches',
                    subtitle: all.isEmpty ? 'Add the things you keep: floor cleaner, bulbs, gloves, uniforms. Then record what comes in and who takes what.' : 'Try another search or filter.',
                  ),
                );
              }
              return Column(children: [for (final i in rows) _ItemTile(item: i)]);
            },
          ),
        ]),
      ),
    );
  }
}

class _ItemTile extends StatelessWidget {
  final StoreItem item;
  const _ItemTile({required this.item});

  @override
  Widget build(BuildContext context) {
    final i = item;
    final color = i.out ? AppTheme.error : (i.low ? AppTheme.warning : AppTheme.success);
    return Card(
      margin: const EdgeInsets.only(bottom: 10),
      child: InkWell(
        borderRadius: BorderRadius.circular(AppTheme.radiusM),
        onTap: () => context.push(storeItemRoute(i.id)),
        child: Padding(
          padding: const EdgeInsets.all(14),
          child: Row(children: [
            CircleAvatar(backgroundColor: AppTheme.primary.withOpacity(0.1), child: Icon(itemCategoryIcon(i.category), color: AppTheme.primary)),
            const SizedBox(width: 12),
            Expanded(
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text(i.name, style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 15.5)),
                Text([i.code, itemCategoryLabel(i.category), if ((i.location ?? '').isNotEmpty) i.location!].join(' · '), style: const TextStyle(color: AppTheme.textSecondary, fontSize: 12.5)),
              ]),
            ),
            Column(crossAxisAlignment: CrossAxisAlignment.end, children: [
              Text(i.stockText, style: TextStyle(fontWeight: FontWeight.w800, fontSize: 15, color: color)),
              if (i.out) const StatusPill('Out of stock', AppTheme.error) else if (i.low) const StatusPill('Running low', AppTheme.warning),
            ]),
          ]),
        ),
      ),
    );
  }
}

// ── Issued ───────────────────────────────────────────────────────────────────

class _IssuedTab extends ConsumerStatefulWidget {
  final String societyId;
  const _IssuedTab({required this.societyId});

  @override
  ConsumerState<_IssuedTab> createState() => _IssuedTabState();
}

class _IssuedTabState extends ConsumerState<_IssuedTab> {
  String? _status = 'open';

  @override
  Widget build(BuildContext context) {
    final async = ref.watch(storeIssuesProvider((societyId: widget.societyId, status: _status, itemId: null)));
    return RefreshIndicator(
      onRefresh: () async => invalidateStores(ref),
      child: ResponsiveBody(
        maxWidth: 820,
        child: ListView(padding: const EdgeInsets.fromLTRB(16, 12, 16, 96), children: [
          Wrap(spacing: 8, children: [
            for (final s in const [('open', 'Still out'), ('overdue', 'Overdue'), (null, 'All')])
              ChoiceChip(label: Text(s.$2), selected: _status == s.$1, onSelected: (_) => setState(() => _status = s.$1)),
          ]),
          const SizedBox(height: 10),
          async.when(
            loading: () => const Padding(padding: EdgeInsets.all(40), child: Center(child: CircularProgressIndicator())),
            error: (e, _) => AppErrorBanner(message: friendlyErrorMessage(e)),
            data: (rows) => rows.isEmpty
                ? const Padding(
                    padding: EdgeInsets.only(top: 24),
                    child: AppEmptyState(icon: Icons.outbox_rounded, title: 'Nothing here', subtitle: 'Items you issue to staff show here until they are taken back or used up.'),
                  )
                : Column(children: [for (final i in rows) IssueCard(issue: i)]),
          ),
        ]),
      ),
    );
  }
}

/// One issue: what, to whom, how much is still out, and a Take back button while it is.
class IssueCard extends ConsumerWidget {
  final IssueItem issue;
  const IssueCard({super.key, required this.issue});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final i = issue;
    return Card(
      margin: const EdgeInsets.only(bottom: 10),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            Expanded(child: Text(i.itemName, style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 15.5))),
            StatusPill(i.statusLabel, i.statusColor),
          ]),
          const SizedBox(height: 2),
          Text('${qty(i.issued)} ${unitLabel(i.unit)} to ${i.toName ?? 'someone'}${i.at == null ? '' : ' on ${dayText(i.at)}'}', style: const TextStyle(fontWeight: FontWeight.w600)),
          if (i.isOut) Text('${qty(i.outstanding)} still out${i.expectedReturn == null ? '' : ' · due back ${dayText(i.expectedReturn)}'}', style: TextStyle(color: i.overdue ? AppTheme.error : AppTheme.textSecondary, fontSize: 12.5)),
          if ((i.purpose ?? '').isNotEmpty) Text(i.purpose!, style: const TextStyle(fontSize: 13)),
          if (i.byName != null) Text('Issued by ${i.byName}', style: const TextStyle(color: AppTheme.textSecondary, fontSize: 12)),
          if (i.isOut)
            Align(
              alignment: Alignment.centerLeft,
              child: TextButton.icon(
                onPressed: () => showAppSheet(context: context, builder: (_) => ReturnSheet(issue: i)),
                icon: const Icon(Icons.undo_rounded, size: 18),
                label: const Text('Take back'),
              ),
            ),
        ]),
      ),
    );
  }
}
