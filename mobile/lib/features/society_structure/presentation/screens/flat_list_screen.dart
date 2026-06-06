import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:ar_society_app/core/router/app_router.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/society_structure/data/models/structure_models.dart';
import 'package:ar_society_app/features/society_structure/presentation/providers/structure_providers.dart';

class FlatListScreen extends ConsumerStatefulWidget {
  final WingModel? filterWing;
  final FloorModel? filterFloor;
  const FlatListScreen({super.key, this.filterWing, this.filterFloor});

  @override
  ConsumerState<FlatListScreen> createState() => _FlatListScreenState();
}

class _FlatListScreenState extends ConsumerState<FlatListScreen> {
  final _search = TextEditingController();
  String? _occupancyFilter;

  static const _occupancyOptions = [
    'all', 'vacant', 'owner_occupied', 'tenant_occupied'
  ];

  @override
  void dispose() {
    _search.dispose();
    super.dispose();
  }

  List<FlatModel> _filter(List<FlatModel> flats) {
    final q = _search.text.toLowerCase();
    return flats.where((f) {
      if (widget.filterWing != null && f.wingId != widget.filterWing!.id) {
        return false;
      }
      if (widget.filterFloor != null && f.floor != widget.filterFloor!.floorNumber) {
        return false;
      }
      if (_occupancyFilter != null && _occupancyFilter != 'all') {
        if (f.occupancyStatus != _occupancyFilter) return false;
      }
      if (q.isEmpty) return true;
      return f.flatNumber.toLowerCase().contains(q) ||
          (f.wingName?.toLowerCase().contains(q) ?? false) ||
          (f.flatType?.toLowerCase().contains(q) ?? false);
    }).toList()
      ..sort((a, b) => a.flatNumber.compareTo(b.flatNumber));
  }

  @override
  Widget build(BuildContext context) {
    final async = ref.watch(flatsBySocietyProvider);
    final title = widget.filterFloor != null
        ? 'Floor ${widget.filterFloor!.displayName} Flats'
        : widget.filterWing != null
            ? '${widget.filterWing!.name} Flats'
            : 'All Flats';

    return Scaffold(
      backgroundColor: AppTheme.surface,
      appBar: AppBar(
        title: Text(title),
        actions: [
          IconButton(
            icon: const Icon(Icons.add_rounded),
            tooltip: 'Add Flat',
            onPressed: () => context.push(
              AppRoutes.flatForm,
              extra: {
                if (widget.filterWing != null) 'wing': widget.filterWing,
                if (widget.filterFloor != null) 'floor': widget.filterFloor,
              },
            ),
          ),
        ],
      ),
      body: Column(children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 12, 16, 0),
          child: Column(children: [
            TextField(
              controller: _search,
              onChanged: (_) => setState(() {}),
              decoration: InputDecoration(
                hintText: 'Search flat number, wing...',
                prefixIcon: const Icon(Icons.search_rounded, size: 20),
                suffixIcon: _search.text.isNotEmpty
                    ? IconButton(
                        icon: const Icon(Icons.clear, size: 18),
                        onPressed: () {
                          _search.clear();
                          setState(() {});
                        })
                    : null,
              ),
            ),
            const SizedBox(height: 8),
            SingleChildScrollView(
              scrollDirection: Axis.horizontal,
              child: Row(children: _occupancyOptions.map((o) {
                final isAll = o == 'all';
                final selected = _occupancyFilter == o ||
                    (isAll && _occupancyFilter == null);
                return Padding(
                  padding: const EdgeInsets.only(right: 8),
                  child: FilterChip(
                    label: Text(_occupancyLabel(o)),
                    selected: selected,
                    onSelected: (_) =>
                        setState(() => _occupancyFilter = isAll ? null : o),
                  ),
                );
              }).toList()),
            ),
          ]),
        ),
        const SizedBox(height: 8),
        Expanded(
          child: async.when(
            loading: () =>
                const Center(child: CircularProgressIndicator()),
            error: (e, _) => Center(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text('Error: $e',
                      textAlign: TextAlign.center,
                      style: const TextStyle(color: AppTheme.error)),
                  const SizedBox(height: 12),
                  ElevatedButton(
                    onPressed: () =>
                        ref.read(flatsBySocietyProvider.notifier).refresh(),
                    child: const Text('Retry'),
                  ),
                ],
              ),
            ),
            data: (flats) {
              final filtered = _filter(flats);
              if (filtered.isEmpty) {
                return Center(
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Icon(Icons.door_front_door_outlined,
                          size: 56,
                          color:
                              AppTheme.textSecondary.withOpacity(0.4)),
                      const SizedBox(height: 12),
                      Text(
                        flats.isEmpty
                            ? 'No flats yet.\nTap + to add the first flat.'
                            : 'No flats match your filters.',
                        textAlign: TextAlign.center,
                        style: const TextStyle(
                            color: AppTheme.textSecondary,
                            fontSize: 14),
                      ),
                    ],
                  ),
                );
              }
              return RefreshIndicator(
                onRefresh: () =>
                    ref.read(flatsBySocietyProvider.notifier).refresh(),
                child: ListView.separated(
                  padding: const EdgeInsets.fromLTRB(16, 4, 16, 24),
                  itemCount: filtered.length,
                  separatorBuilder: (_, __) =>
                      const SizedBox(height: 10),
                  itemBuilder: (_, i) => _FlatCard(flat: filtered[i]),
                ),
              );
            },
          ),
        ),
      ]),
    );
  }

  String _occupancyLabel(String s) {
    switch (s) {
      case 'all': return 'All';
      case 'vacant': return 'Vacant';
      case 'owner_occupied': return 'Owner';
      case 'tenant_occupied': return 'Tenant';
      default: return s;
    }
  }
}

class _FlatCard extends ConsumerWidget {
  final FlatModel flat;
  const _FlatCard({required this.flat});

  Color _occupancyColor(String? status) {
    switch (status) {
      case 'owner_occupied': return AppTheme.success;
      case 'tenant_occupied': return AppTheme.warning;
      case 'vacant': return AppTheme.textSecondary;
      default: return AppTheme.textSecondary;
    }
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final occColor = _occupancyColor(flat.occupancyStatus);
    return Container(
      decoration: BoxDecoration(
        color: AppTheme.cardBg,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: AppTheme.border),
      ),
      child: InkWell(
        borderRadius: BorderRadius.circular(14),
        onTap: () => context.push(AppRoutes.flatDetail, extra: flat),
        child: Padding(
          padding: const EdgeInsets.all(14),
          child: Row(children: [
            Container(
              width: 44,
              height: 44,
              decoration: BoxDecoration(
                color: occColor.withOpacity(0.12),
                borderRadius: BorderRadius.circular(12),
              ),
              child: Center(
                child: Icon(Icons.door_front_door_rounded,
                    color: occColor, size: 22),
              ),
            ),
            const SizedBox(width: 14),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(children: [
                    Expanded(
                      child: Text(flat.displayName,
                          style: const TextStyle(
                              fontSize: 15,
                              fontWeight: FontWeight.w600,
                              color: AppTheme.textPrimary)),
                    ),
                    _OccupancyBadge(status: flat.occupancyStatus),
                  ]),
                  const SizedBox(height: 4),
                  Row(children: [
                    if (flat.flatType != null) ...[
                      Text(flat.flatType!,
                          style: const TextStyle(
                              fontSize: 12,
                              color: AppTheme.textSecondary)),
                      const SizedBox(width: 10),
                    ],
                    if (flat.areaSqft != null)
                      Text('${flat.areaSqft!.toStringAsFixed(0)} sqft',
                          style: const TextStyle(
                              fontSize: 12,
                              color: AppTheme.textSecondary)),
                    if (flat.floor != null) ...[
                      const SizedBox(width: 10),
                      Text('Floor ${flat.floor}',
                          style: const TextStyle(
                              fontSize: 12,
                              color: AppTheme.textSecondary)),
                    ],
                  ]),
                ],
              ),
            ),
            PopupMenuButton<String>(
              icon: const Icon(Icons.more_vert_rounded,
                  color: AppTheme.textSecondary),
              onSelected: (v) => _onMenu(context, ref, v),
              itemBuilder: (_) => [
                const PopupMenuItem(value: 'edit', child: Text('Edit')),
                const PopupMenuItem(
                  value: 'delete',
                  child: Text('Delete',
                      style: TextStyle(color: AppTheme.error)),
                ),
              ],
            ),
          ]),
        ),
      ),
    );
  }

  Future<void> _onMenu(
      BuildContext context, WidgetRef ref, String action) async {
    if (action == 'edit') {
      context.push(AppRoutes.flatForm, extra: {'flat': flat});
      return;
    }
    if (action == 'delete') {
      final ok = await showDialog<bool>(
        context: context,
        builder: (ctx) => AlertDialog(
          title: const Text('Delete Flat?'),
          content: Text('Delete flat "${flat.displayName}"?'),
          actions: [
            TextButton(
                onPressed: () => Navigator.pop(ctx, false),
                child: const Text('Cancel')),
            ElevatedButton(
              style: ElevatedButton.styleFrom(
                  backgroundColor: AppTheme.error),
              onPressed: () => Navigator.pop(ctx, true),
              child: const Text('Delete'),
            ),
          ],
        ),
      );
      if (ok == true) {
        try {
          await ref.read(flatsBySocietyProvider.notifier).delete(flat.id);
        } catch (e) {
          if (context.mounted) {
            ScaffoldMessenger.of(context).showSnackBar(SnackBar(
                content: Text('Error: $e'),
                backgroundColor: AppTheme.error));
          }
        }
      }
    }
  }
}

class _OccupancyBadge extends StatelessWidget {
  final String? status;
  const _OccupancyBadge({required this.status});

  @override
  Widget build(BuildContext context) {
    Color color;
    String label;
    switch (status) {
      case 'owner_occupied':
        color = AppTheme.success; label = 'Owner'; break;
      case 'tenant_occupied':
        color = AppTheme.warning; label = 'Tenant'; break;
      default:
        color = AppTheme.textSecondary; label = 'Vacant'; break;
    }
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
      decoration: BoxDecoration(
        color: color.withOpacity(0.12),
        borderRadius: BorderRadius.circular(6),
      ),
      child: Text(label,
          style: TextStyle(
              fontSize: 10,
              color: color,
              fontWeight: FontWeight.w600)),
    );
  }
}
