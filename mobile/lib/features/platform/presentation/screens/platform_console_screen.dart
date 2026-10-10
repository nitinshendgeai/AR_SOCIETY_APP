import 'package:flutter/material.dart';
import 'package:ar_society_app/core/motion/loading.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/router/app_router.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/platform/data/platform_api.dart';
import 'package:ar_society_app/features/platform/presentation/providers/platform_providers.dart';
import 'package:ar_society_app/shared/widgets/app_data_table.dart' show StatusPill;
import 'package:ar_society_app/shared/widgets/app_widgets.dart';
import 'package:ar_society_app/shared/widgets/app_form.dart';

String platformSocietyRoute(String id) => AppRoutes.platformSociety.replaceFirst(':id', id);

/// Every society on the platform: where each stands (trial, paid, suspended), how much it is used, and what has been
/// done to it. Open one to extend its trial, put it on a plan, suspend it or change its limits.
class PlatformConsoleScreen extends ConsumerStatefulWidget {
  const PlatformConsoleScreen({super.key});

  @override
  ConsumerState<PlatformConsoleScreen> createState() => _PlatformConsoleScreenState();
}

class _PlatformConsoleScreenState extends ConsumerState<PlatformConsoleScreen> with SingleTickerProviderStateMixin {
  late final _tabs = TabController(length: 2, vsync: this);
  final _search = TextEditingController();
  String _q = '';
  String? _status;

  @override
  void dispose() {
    _tabs.dispose();
    _search.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => AppPage(
    title: 'Platform Console',
    bottom: TabBar(controller: _tabs, tabs: const [Tab(text: 'Societies'), Tab(text: 'Activity')]),
    body: TabBarView(controller: _tabs, children: [_societies(), const _ActivityTab()]),
  );

  Widget _societies() {
    final stats = ref.watch(platformStatsProvider).valueOrNull ?? const PlatformStats();
    final list = ref.watch(platformSocietiesProvider((q: _q, status: _status)));
    return RefreshIndicator(
      onRefresh: () async => invalidatePlatform(ref),
      child: ResponsiveBody(
        maxWidth: 960,
        child: ListView(padding: const EdgeInsets.fromLTRB(16, 16, 16, 40), children: [
          KpiGrid(cards: [
            KpiCard(icon: Icons.apartment_rounded, label: 'Societies', value: '${stats.societies}', color: AppTheme.primary, note: '${stats.users} people, ${stats.flats} flats', onTap: () => setState(() => _status = null)),
            KpiCard(
              icon: Icons.hourglass_bottom_rounded,
              label: 'On trial',
              value: '${stats.trial}',
              color: stats.endedNotMarked > 0 ? AppTheme.warning : AppTheme.secondary,
              note: stats.endedNotMarked > 0 ? '${stats.endedNotMarked} past their end date' : (stats.expiringSoon > 0 ? '${stats.expiringSoon} ending within a week' : 'none ending soon'),
              onTap: () => setState(() => _status = 'TRIAL'),
            ),
            KpiCard(icon: Icons.verified_rounded, label: 'Paid', value: '${stats.active}', color: AppTheme.success, note: stats.expired > 0 ? '${stats.expired} expired' : null, onTap: () => setState(() => _status = 'ACTIVE')),
            KpiCard(icon: Icons.block_rounded, label: 'Suspended', value: '${stats.suspended}', color: stats.suspended > 0 ? AppTheme.error : AppTheme.textSecondary, onTap: () => setState(() => _status = 'SUSPENDED')),
          ]),
          const SizedBox(height: 16),
          TextField(
            controller: _search,
            onChanged: (v) => setState(() => _q = v.trim()),
            decoration: InputDecoration(
              hintText: 'Search by name, code, city or email',
              prefixIcon: const Icon(Icons.search_rounded),
              suffixIcon: _q.isEmpty ? null : IconButton(icon: const Icon(Icons.close_rounded, size: 18), onPressed: () => setState(() { _search.clear(); _q = ''; })),
            ),
          ),
          const SizedBox(height: 10),
          SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            child: Row(children: [
              for (final s in kStatuses)
                Padding(padding: const EdgeInsets.only(right: 8), child: ChoiceChip(label: Text(s.$2), selected: _status == s.$1, onSelected: (_) => setState(() => _status = s.$1))),
            ]),
          ),
          const SizedBox(height: 12),
          list.when(
            loading: () => const AppLoader(),
            error: (e, _) => AppErrorBanner(message: friendlyErrorMessage(e)),
            data: (rows) => rows.isEmpty
                ? const Padding(padding: EdgeInsets.only(top: 24), child: AppEmptyState(icon: Icons.apartment_rounded, title: 'No society matches'))
                : Column(children: [for (final s in rows) _SocietyCard(society: s)]),
          ),
        ]),
      ),
    );
  }
}

class _SocietyCard extends StatelessWidget {
  final PlatformSociety society;
  const _SocietyCard({required this.society});

  @override
  Widget build(BuildContext context) {
    final s = society;
    return Card(
      margin: const EdgeInsets.only(bottom: 10),
      child: InkWell(
        borderRadius: BorderRadius.circular(AppTheme.radiusM),
        onTap: () => context.push(platformSocietyRoute(s.id)),
        child: Padding(
          padding: const EdgeInsets.all(14),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Row(children: [
              Expanded(child: Text(s.name, style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 16))),
              if (s.trialEnded && s.status == 'TRIAL') const Padding(padding: EdgeInsets.only(right: 6), child: StatusPill('Trial ended', AppTheme.warning)),
              StatusPill(statusLabel(s.status), statusColor(s.status)),
            ]),
            const SizedBox(height: 2),
            Text([if ((s.code ?? '').isNotEmpty) s.code!, if ((s.city ?? '').isNotEmpty) s.city!, s.standing].join(' · '), style: const TextStyle(color: AppTheme.textSecondary, fontSize: 12.5)),
            const SizedBox(height: 8),
            Wrap(spacing: 16, runSpacing: 4, children: [
              _chip(Icons.people_outline_rounded, '${s.users} of ${s.allowedUsers} people'),
              _chip(Icons.apartment_rounded, '${s.flats} of ${s.allowedFlats} flats'),
              _chip(Icons.login_rounded, 'Last sign-in ${ago(s.lastLogin)}'),
              if (s.setupPct < 100) _chip(Icons.checklist_rounded, 'Setup ${s.setupPct}%'),
            ]),
          ]),
        ),
      ),
    );
  }

  Widget _chip(IconData i, String t) => Row(mainAxisSize: MainAxisSize.min, children: [Icon(i, size: 15, color: AppTheme.textSecondary), const SizedBox(width: 4), Text(t, style: const TextStyle(fontSize: 12.5, color: AppTheme.textSecondary))]);
}

class _ActivityTab extends ConsumerWidget {
  const _ActivityTab();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final async = ref.watch(platformActivityProvider);
    return RefreshIndicator(
      onRefresh: () async => invalidatePlatform(ref),
      child: ResponsiveBody(
        maxWidth: 820,
        child: ListView(padding: const EdgeInsets.fromLTRB(16, 16, 16, 40), children: [
          async.when(
            loading: () => const AppLoader(),
            error: (e, _) => AppErrorBanner(message: friendlyErrorMessage(e)),
            data: (rows) => rows.isEmpty
                ? const Padding(padding: EdgeInsets.only(top: 24), child: AppEmptyState(icon: Icons.history_rounded, title: 'Nothing yet', subtitle: 'Suspensions, activations, extended trials and changed limits are listed here.'))
                : Column(children: [for (final e in rows) EventTile(event: e, showSociety: true)]),
          ),
        ]),
      ),
    );
  }
}

/// One thing a platform admin did.
class EventTile extends StatelessWidget {
  final PlatformEvent event;
  final bool showSociety;
  const EventTile({super.key, required this.event, this.showSociety = false});

  @override
  Widget build(BuildContext context) {
    final e = event;
    final detail = eventDetail(e.event, e.details);
    return ListTile(
      dense: true,
      contentPadding: EdgeInsets.zero,
      leading: Icon(e.event == 'society_suspended' ? Icons.block_rounded : (e.event == 'society_activated' ? Icons.verified_rounded : Icons.history_rounded), size: 20, color: e.event == 'society_suspended' ? AppTheme.error : AppTheme.textSecondary),
      title: Text(showSociety && e.societyName != null ? '${eventLabel(e.event)}: ${e.societyName}' : eventLabel(e.event), style: const TextStyle(fontWeight: FontWeight.w600)),
      subtitle: Text([if (detail.isNotEmpty) detail, '${e.by ?? 'Someone'}, ${dayTimeText(e.at)}'].join('\n')),
      isThreeLine: detail.isNotEmpty,
    );
  }
}
