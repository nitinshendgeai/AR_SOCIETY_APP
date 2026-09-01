import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/router/app_router.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/society_structure/data/models/structure_models.dart';
import 'package:ar_society_app/features/society_structure/domain/flat_numbering.dart';
import 'package:ar_society_app/features/society_structure/presentation/providers/structure_providers.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';

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
              extra: {'wing': wing, 'floor': null},
            ),
          ),
        ],
      ),
      body: ResponsiveBody(child: async.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (e, _) => Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(friendlyErrorMessage(e),
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
      )),
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
                    value: 'add_flats', child: Text('Add Flats')),
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
    if (action == 'add_flats') {
      await _addFlats(context, ref);
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
                content: Text(friendlyErrorMessage(e)),
                backgroundColor: AppTheme.error));
          }
        }
      }
    }
  }

  /// Bulk-adds flats to an EXISTING floor — for floors that were already
  /// created without using the "Units on this Floor" field on Add Floor
  /// (which only bulk-generates at creation time, not afterwards).
  /// Auto-numbered the same way (nextFlatNumbers), skipping any unit index
  /// that would collide with a flat already on this floor.
  Future<void> _addFlats(BuildContext context, WidgetRef ref) async {
    final countCtrl = TextEditingController();
    final count = await showDialog<int>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text('Add Flats to ${floor.displayName}'),
        content: TextField(
          controller: countCtrl,
          keyboardType: TextInputType.number,
          autofocus: true,
          decoration: const InputDecoration(
            labelText: 'Number of flats to add',
            hintText: 'e.g. 5',
          ),
        ),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(ctx),
              child: const Text('Cancel')),
          ElevatedButton(
            onPressed: () {
              final n = int.tryParse(countCtrl.text.trim());
              if (n != null && n > 0 && n <= 100) Navigator.pop(ctx, n);
            },
            child: const Text('Add'),
          ),
        ],
      ),
    );
    if (count == null || !context.mounted) return;

    final allFlats = await ref.read(flatsBySocietyProvider.future);
    final existingNumbers = allFlats
        .where((f) => f.wingId == wing.id && f.floor == floor.floorNumber)
        .map((f) => f.flatNumber)
        .toSet();
    final numbers = nextFlatNumbers(floor.floorNumber, count, existingNumbers);

    if (!context.mounted) return;
    var progressLabel = 'Creating flat 1 of ${numbers.length}…';
    StateSetter? setProgress;
    showDialog(
      context: context,
      barrierDismissible: false,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setState) {
          setProgress = setState;
          return AlertDialog(
            content: Row(children: [
              const SizedBox(
                width: 20,
                height: 20,
                child: CircularProgressIndicator(strokeWidth: 2),
              ),
              const SizedBox(width: 16),
              Expanded(child: Text(progressLabel)),
            ]),
          );
        },
      ),
    );

    var created = 0;
    String? error;
    for (var i = 0; i < numbers.length; i++) {
      progressLabel = 'Creating flat ${i + 1} of ${numbers.length}…';
      setProgress?.call(() {});
      try {
        await ref.read(flatsBySocietyProvider.notifier).create(
              flatNumber: numbers[i],
              wingId: wing.id,
              floor: floor.floorNumber,
            );
        created++;
      } catch (e) {
        error = friendlyErrorMessage(e);
        break;
      }
    }

    ref.read(floorsByWingProvider(wing.id).notifier).refresh();
    if (context.mounted) Navigator.pop(context); // close progress dialog

    if (context.mounted) {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(
        content: Text(error == null
            ? '$created flat${created == 1 ? '' : 's'} added to ${floor.displayName}'
            : 'Added $created of ${numbers.length} flats before an error: $error'),
        backgroundColor: error == null ? AppTheme.success : AppTheme.error,
      ));
    }
  }
}
