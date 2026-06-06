import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:ar_society_app/core/router/app_router.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/society_structure/data/models/structure_models.dart';
import 'package:ar_society_app/features/society_structure/presentation/providers/structure_providers.dart';

class FloorListScreen extends ConsumerWidget {
  final WingModel wing;
  const FloorListScreen({super.key, required this.wing});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final async = ref.watch(floorsByWingProvider(wing.id));

    return Scaffold(
      backgroundColor: AppTheme.surface,
      appBar: AppBar(
        title: Text('${wing.name} — Floors'),
        actions: [
          IconButton(
            icon: const Icon(Icons.add_rounded),
            tooltip: 'Add Floor',
            onPressed: () => context.push(
              AppRoutes.floorForm.replaceFirst(':wingId', wing.id),
              extra: wing,
            ),
          ),
        ],
      ),
      body: async.when(
        loading: () => const Center(child: CircularProgressIndicator()),
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
                    ref.read(floorsByWingProvider(wing.id).notifier).refresh(),
                child: const Text('Retry'),
              ),
            ],
          ),
        ),
        data: (floors) {
          if (floors.isEmpty) {
            return Center(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(Icons.layers_outlined,
                      size: 56,
                      color: AppTheme.textSecondary.withOpacity(0.4)),
                  const SizedBox(height: 12),
                  Text('No floors yet.\nTap + to add the first floor.',
                      textAlign: TextAlign.center,
                      style: const TextStyle(
                          color: AppTheme.textSecondary, fontSize: 14)),
                ],
              ),
            );
          }
          return RefreshIndicator(
            onRefresh: () =>
                ref.read(floorsByWingProvider(wing.id).notifier).refresh(),
            child: ListView.separated(
              padding: const EdgeInsets.fromLTRB(16, 12, 16, 24),
              itemCount: floors.length,
              separatorBuilder: (_, __) => const SizedBox(height: 10),
              itemBuilder: (_, i) =>
                  _FloorCard(floor: floors[i], wing: wing),
            ),
          );
        },
      ),
    );
  }
}

class _FloorCard extends ConsumerWidget {
  final FloorModel floor;
  final WingModel wing;
  const _FloorCard({required this.floor, required this.wing});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return Container(
      decoration: BoxDecoration(
        color: AppTheme.cardBg,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: AppTheme.border),
      ),
      child: InkWell(
        borderRadius: BorderRadius.circular(14),
        onTap: () => context.push(
          AppRoutes.flatsByWing.replaceFirst(':wingId', wing.id),
          extra: {'wing': wing, 'floor': floor},
        ),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Row(children: [
            Container(
              width: 44,
              height: 44,
              decoration: BoxDecoration(
                color: AppTheme.secondary.withOpacity(0.12),
                borderRadius: BorderRadius.circular(12),
              ),
              child: Center(
                child: Text(
                  '${floor.floorNumber}',
                  style: const TextStyle(
                    fontSize: 16,
                    fontWeight: FontWeight.w700,
                    color: AppTheme.secondary,
                  ),
                ),
              ),
            ),
            const SizedBox(width: 14),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(floor.displayName,
                      style: const TextStyle(
                          fontSize: 15,
                          fontWeight: FontWeight.w600,
                          color: AppTheme.textPrimary)),
                  const SizedBox(height: 4),
                  Row(children: [
                    const Icon(Icons.door_front_door_rounded,
                        size: 13, color: AppTheme.textSecondary),
                    const SizedBox(width: 4),
                    Text('${floor.flatCount} flats',
                        style: const TextStyle(
                            fontSize: 12, color: AppTheme.textSecondary)),
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
      context.push(
        AppRoutes.floorForm.replaceFirst(':wingId', wing.id),
        extra: {'wing': wing, 'floor': floor},
      );
      return;
    }
    if (action == 'delete') {
      final ok = await showDialog<bool>(
        context: context,
        builder: (ctx) => AlertDialog(
          title: const Text('Delete Floor?'),
          content: Text(
              'Delete "${floor.displayName}"? All flats on this floor will also be removed.'),
          actions: [
            TextButton(
                onPressed: () => Navigator.pop(ctx, false),
                child: const Text('Cancel')),
            ElevatedButton(
              style: ElevatedButton.styleFrom(backgroundColor: AppTheme.error),
              onPressed: () => Navigator.pop(ctx, true),
              child: const Text('Delete'),
            ),
          ],
        ),
      );
      if (ok == true) {
        try {
          await ref
              .read(floorsByWingProvider(wing.id).notifier)
              .delete(floor.id);
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
