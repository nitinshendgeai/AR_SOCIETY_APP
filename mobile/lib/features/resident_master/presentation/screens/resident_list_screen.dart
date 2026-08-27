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

/// Resident Master list — the canonical, searchable roster of every
/// resident (owner / co-owner / family / dependent) across the society.
class ResidentListScreen extends ConsumerStatefulWidget {
  final FlatModel? filterFlat;
  const ResidentListScreen({super.key, this.filterFlat});

  @override
  ConsumerState<ResidentListScreen> createState() => _ResidentListScreenState();
}

class _ResidentListScreenState extends ConsumerState<ResidentListScreen> {
  final _searchCtrl = TextEditingController();
  Timer? _debounce;
  String? _typeFilter;
  bool? _activeFilter = true;

  static const _typeOptions = [
    (null, 'All'),
    ('owner', 'Owner'),
    ('co_owner', 'Co-Owner'),
    ('family', 'Family'),
    ('dependent', 'Dependent'),
  ];

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
    ref.read(residentListProvider.notifier).load(
          residentType: _typeFilter,
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
    final state = ref.watch(residentListProvider);
    final user = ref.watch(currentUserProvider);
    final flatsAsync = ref.watch(flatsBySocietyProvider);
    final flatsById = <String, FlatModel>{
      for (final f in flatsAsync.valueOrNull ?? <FlatModel>[]) f.id: f,
    };

    return Scaffold(
      backgroundColor: AppTheme.surface,
      appBar: AppBar(
        title: Text(widget.filterFlat != null ? 'Residents — ${widget.filterFlat!.displayName}' : 'Residents'),
        actions: [
          IconButton(icon: const Icon(Icons.refresh_rounded), onPressed: _load),
        ],
      ),
      floatingActionButton: (user?.isAdminOrCommittee ?? false)
          ? FloatingActionButton.extended(
              onPressed: () => context.push(
                AppRoutes.residentForm,
                extra: {if (widget.filterFlat != null) 'flat': widget.filterFlat},
              ),
              backgroundColor: AppTheme.primary,
              foregroundColor: Colors.white,
              icon: const Icon(Icons.person_add_rounded),
              label: const Text('Add Resident'),
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
                hintText: 'Search name, phone, email…',
                prefixIcon: const Icon(Icons.search_rounded, size: 20),
                suffixIcon: _searchCtrl.text.isNotEmpty
                    ? IconButton(
                        icon: const Icon(Icons.clear, size: 18),
                        onPressed: () {
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
            Row(children: [
              Expanded(
                child: SizedBox(
                  height: 34,
                  child: ListView.separated(
                    scrollDirection: Axis.horizontal,
                    itemCount: _typeOptions.length,
                    separatorBuilder: (_, __) => const SizedBox(width: 8),
                    itemBuilder: (_, i) {
                      final (value, label) = _typeOptions[i];
                      final selected = value == _typeFilter;
                      return GestureDetector(
                        onTap: () {
                          setState(() => _typeFilter = value);
                          _load();
                        },
                        child: AnimatedContainer(
                          duration: const Duration(milliseconds: 200),
                          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
                          decoration: BoxDecoration(
                            color: selected ? AppTheme.primary : AppTheme.cardBg,
                            borderRadius: BorderRadius.circular(20),
                            border: Border.all(color: selected ? AppTheme.primary : AppTheme.border),
                          ),
                          child: Text(label,
                              style: TextStyle(
                                  fontSize: 12,
                                  fontWeight: FontWeight.w600,
                                  color: selected ? Colors.white : AppTheme.textSecondary)),
                        ),
                      );
                    },
                  ),
                ),
              ),
              const SizedBox(width: 8),
              GestureDetector(
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
                        size: 14,
                        color: _activeFilter == true ? AppTheme.success : AppTheme.textSecondary),
                    const SizedBox(width: 4),
                    Text(_activeFilter == true ? 'Active' : 'Inactive',
                        style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: AppTheme.textSecondary)),
                  ]),
                ),
              ),
            ]),
          ]),
        ),
        const SizedBox(height: 8),
        Expanded(
          child: switch (state) {
            ResidentListLoading() || ResidentListInitial() =>
              const Center(child: CircularProgressIndicator(color: AppTheme.primary)),
            ResidentListError(:final message) => Center(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 32),
                      child: Text(message, textAlign: TextAlign.center, style: const TextStyle(color: AppTheme.error)),
                    ),
                    const SizedBox(height: 12),
                    ElevatedButton(onPressed: _load, child: const Text('Retry')),
                  ],
                ),
              ),
            ResidentListLoaded(:final residents) => residents.isEmpty
                ? const RmEmptyState(
                    icon: Icons.people_outline_rounded,
                    title: 'No residents found',
                    subtitle: 'Try adjusting your search or filters.',
                  )
                : RefreshIndicator(
                    onRefresh: () async => _load(),
                    child: ListView.separated(
                      padding: const EdgeInsets.fromLTRB(16, 0, 16, 24),
                      itemCount: residents.length,
                      separatorBuilder: (_, __) => const SizedBox(height: 10),
                      itemBuilder: (_, i) => _ResidentCard(resident: residents[i], flat: flatsById[residents[i].flatId]),
                    ),
                  ),
          },
        ),
      ])),
    );
  }
}

class _ResidentCard extends StatelessWidget {
  final ResidentModel resident;
  final FlatModel? flat;
  const _ResidentCard({required this.resident, this.flat});

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: AppTheme.cardBg,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: AppTheme.border),
      ),
      child: InkWell(
        borderRadius: BorderRadius.circular(14),
        onTap: () => context.push(AppRoutes.residentDetail, extra: resident),
        child: Padding(
          padding: const EdgeInsets.all(14),
          child: Row(children: [
            Container(
              width: 44,
              height: 44,
              decoration: BoxDecoration(
                color: AppTheme.primary.withOpacity(0.1),
                borderRadius: BorderRadius.circular(12),
              ),
              child: const Icon(Icons.person_rounded, color: AppTheme.primary, size: 22),
            ),
            const SizedBox(width: 14),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(children: [
                    Expanded(
                      child: Text(resident.fullName,
                          overflow: TextOverflow.ellipsis,
                          style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w600, color: AppTheme.textPrimary)),
                    ),
                    if (resident.isPrimary) ...[const PrimaryChip(), const SizedBox(width: 6)],
                    ResidentTypeBadge(type: resident.residentType),
                  ]),
                  const SizedBox(height: 4),
                  Row(children: [
                    const Icon(Icons.door_front_door_outlined, size: 13, color: AppTheme.textSecondary),
                    const SizedBox(width: 4),
                    Text(flat?.displayName ?? '—',
                        style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
                    if (resident.phone != null) ...[
                      const SizedBox(width: 10),
                      const Icon(Icons.phone_rounded, size: 13, color: AppTheme.textSecondary),
                      const SizedBox(width: 4),
                      Text(resident.phone!, style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
                    ],
                  ]),
                  if (!resident.isActive) ...[
                    const SizedBox(height: 4),
                    const ActiveBadge(isActive: false),
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
