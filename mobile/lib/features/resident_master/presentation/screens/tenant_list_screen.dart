import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:ar_society_app/core/router/app_router.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/features/resident_master/data/models/resident_master_models.dart';
import 'package:ar_society_app/features/resident_master/presentation/providers/resident_master_providers.dart';
import 'package:ar_society_app/features/resident_master/presentation/widgets/resident_master_widgets.dart';
import 'package:ar_society_app/features/society_structure/data/models/structure_models.dart';
import 'package:ar_society_app/features/society_structure/presentation/providers/structure_providers.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';

/// Tenant Master list — every tenant currently or previously on record,
/// with agreement status/expiry surfaced so "who's renting and until when"
/// is answerable at a glance.
class TenantListScreen extends ConsumerStatefulWidget {
  final FlatModel? filterFlat;
  const TenantListScreen({super.key, this.filterFlat});

  @override
  ConsumerState<TenantListScreen> createState() => _TenantListScreenState();
}

class _TenantListScreenState extends ConsumerState<TenantListScreen> {
  final _searchCtrl = TextEditingController();
  Timer? _debounce;
  bool? _activeFilter = true;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _load());
  }

  @override
  void dispose() {
    _debounce?.cancel();
    _searchCtrl.dispose();
    super.dispose();
  }

  void _load() {
    ref.read(tenantListProvider.notifier).load(
          isActive: _activeFilter,
          search: _searchCtrl.text.trim().isEmpty ? null : _searchCtrl.text.trim(),
          flatId: widget.filterFlat?.id,
        );
  }

  void _onSearchChanged(String _) {
    _debounce?.cancel();
    _debounce = Timer(const Duration(milliseconds: 400), _load);
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(tenantListProvider);
    final user = ref.watch(currentUserProvider);
    final flatsAsync = ref.watch(flatsBySocietyProvider);
    final flatsById = <String, FlatModel>{
      for (final f in flatsAsync.valueOrNull ?? <FlatModel>[]) f.id: f,
    };

    return Scaffold(
      backgroundColor: AppTheme.surface,
      appBar: AppBar(
        title: Text(widget.filterFlat != null ? 'Tenants — ${widget.filterFlat!.displayName}' : 'Tenants'),
        actions: [IconButton(icon: const Icon(Icons.refresh_rounded), onPressed: _load)],
      ),
      floatingActionButton: (user?.isAdminOrCommittee ?? false)
          ? FloatingActionButton.extended(
              onPressed: () => context.push(
                AppRoutes.tenantForm,
                extra: {if (widget.filterFlat != null) 'flat': widget.filterFlat},
              ),
              backgroundColor: AppTheme.primary,
              foregroundColor: Colors.white,
              icon: const Icon(Icons.person_add_alt_1_rounded),
              label: const Text('Add Tenant'),
            )
          : null,
      body: ResponsiveBody(child: Column(children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 12, 16, 0),
          child: Column(children: [
            TextField(
              controller: _searchCtrl,
              onChanged: _onSearchChanged,
              decoration: InputDecoration(
                hintText: 'Search tenant name, phone…',
                prefixIcon: const Icon(Icons.search_rounded, size: 20),
                suffixIcon: _searchCtrl.text.isNotEmpty
                    ? IconButton(icon: const Icon(Icons.clear, size: 18), onPressed: () {
                        _searchCtrl.clear();
                        _load();
                        setState(() {});
                      })
                    : null,
                contentPadding: const EdgeInsets.symmetric(vertical: 10),
                filled: true,
                fillColor: AppTheme.cardBg,
              ),
            ),
            const SizedBox(height: 10),
            Align(
              alignment: Alignment.centerLeft,
              child: GestureDetector(
                onTap: () {
                  setState(() => _activeFilter = _activeFilter == true ? false : true);
                  _load();
                },
                child: Container(
                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 7),
                  decoration: BoxDecoration(
                    color: AppTheme.cardBg,
                    borderRadius: BorderRadius.circular(20),
                    border: Border.all(color: AppTheme.border),
                  ),
                  child: Row(mainAxisSize: MainAxisSize.min, children: [
                    Icon(_activeFilter == true ? Icons.check_circle_rounded : Icons.block_rounded,
                        size: 14, color: _activeFilter == true ? AppTheme.success : AppTheme.textSecondary),
                    const SizedBox(width: 4),
                    Text(_activeFilter == true ? 'Active' : 'Inactive',
                        style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: AppTheme.textSecondary)),
                  ]),
                ),
              ),
            ),
          ]),
        ),
        const SizedBox(height: 8),
        Expanded(
          child: switch (state) {
            TenantListLoading() || TenantListInitial() =>
              const Center(child: CircularProgressIndicator(color: AppTheme.primary)),
            TenantListError(:final message) => Center(
                child: Column(mainAxisSize: MainAxisSize.min, children: [
                  Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 32),
                    child: Text(message, textAlign: TextAlign.center, style: const TextStyle(color: AppTheme.error)),
                  ),
                  const SizedBox(height: 12),
                  ElevatedButton(onPressed: _load, child: const Text('Retry')),
                ]),
              ),
            TenantListLoaded(:final tenants) => tenants.isEmpty
                ? const RmEmptyState(
                    icon: Icons.groups_2_outlined,
                    title: 'No tenants found',
                    subtitle: 'Try adjusting your search or filters.',
                  )
                : RefreshIndicator(
                    onRefresh: () async => _load(),
                    child: ListView.separated(
                      padding: const EdgeInsets.fromLTRB(16, 0, 16, 24),
                      itemCount: tenants.length,
                      separatorBuilder: (_, __) => const SizedBox(height: 10),
                      itemBuilder: (_, i) => _TenantCard(tenant: tenants[i], flat: flatsById[tenants[i].flatId]),
                    ),
                  ),
          },
        ),
      ])),
    );
  }
}

class _TenantCard extends StatelessWidget {
  final TenantModel tenant;
  final FlatModel? flat;
  const _TenantCard({required this.tenant, this.flat});

  @override
  Widget build(BuildContext context) {
    final daysLeft = rmDaysUntil(tenant.agreementEndDate);
    final expiringSoon = daysLeft != null && daysLeft >= 0 && daysLeft <= 30;
    final expired = daysLeft != null && daysLeft < 0;

    return Container(
      decoration: BoxDecoration(
        color: AppTheme.cardBg,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: AppTheme.border),
      ),
      child: InkWell(
        borderRadius: BorderRadius.circular(14),
        onTap: () => context.push(AppRoutes.tenantDetail, extra: tenant),
        child: Padding(
          padding: const EdgeInsets.all(14),
          child: Row(children: [
            Container(
              width: 44,
              height: 44,
              decoration: BoxDecoration(color: AppTheme.secondary.withOpacity(0.1), borderRadius: BorderRadius.circular(12)),
              child: const Icon(Icons.groups_2_rounded, color: AppTheme.secondary, size: 22),
            ),
            const SizedBox(width: 14),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(children: [
                    Expanded(
                      child: Text(tenant.fullName,
                          overflow: TextOverflow.ellipsis,
                          style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w600, color: AppTheme.textPrimary)),
                    ),
                    ActiveBadge(isActive: tenant.isActive && !tenant.hasMovedOut),
                  ]),
                  const SizedBox(height: 4),
                  Row(children: [
                    const Icon(Icons.door_front_door_outlined, size: 13, color: AppTheme.textSecondary),
                    const SizedBox(width: 4),
                    Text(flat?.displayName ?? '—', style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
                    if (tenant.phone != null) ...[
                      const SizedBox(width: 10),
                      const Icon(Icons.phone_rounded, size: 13, color: AppTheme.textSecondary),
                      const SizedBox(width: 4),
                      Text(tenant.phone!, style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
                    ],
                  ]),
                  if (tenant.agreementEndDate != null) ...[
                    const SizedBox(height: 4),
                    Row(children: [
                      Icon(Icons.event_rounded, size: 13,
                          color: expired ? AppTheme.error : expiringSoon ? AppTheme.warning : AppTheme.textSecondary),
                      const SizedBox(width: 4),
                      Text(
                        expired
                            ? 'Agreement expired ${rmFormatDate(tenant.agreementEndDate)}'
                            : 'Agreement until ${rmFormatDate(tenant.agreementEndDate)}',
                        style: TextStyle(
                          fontSize: 12,
                          fontWeight: expiringSoon || expired ? FontWeight.w700 : FontWeight.w400,
                          color: expired ? AppTheme.error : expiringSoon ? AppTheme.warning : AppTheme.textSecondary,
                        ),
                      ),
                    ]),
                  ],
                ],
              ),
            ),
          ]),
        ),
      ),
    );
  }
}
