import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:ar_society_app/core/router/app_router.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/society_structure/data/models/structure_models.dart';
import 'package:ar_society_app/features/society_structure/presentation/providers/structure_providers.dart';

class WingListScreen extends ConsumerStatefulWidget {
  const WingListScreen({super.key});

  @override
  ConsumerState<WingListScreen> createState() => _WingListScreenState();
}

class _WingListScreenState extends ConsumerState<WingListScreen> {
  final _search = TextEditingController();
  bool _showInactive = false;

  @override
  void dispose() {
    _search.dispose();
    super.dispose();
  }

  List<WingModel> _filter(List<WingModel> wings) {
    final q = _search.text.toLowerCase();
    return wings.where((w) {
      if (!_showInactive && !w.isActive) return false;
      if (q.isEmpty) return true;
      return w.name.toLowerCase().contains(q) ||
          (w.code?.toLowerCase().contains(q) ?? false);
    }).toList();
  }

  @override
  Widget build(BuildContext context) {
    final async = ref.watch(wingsProvider);

    return Scaffold(
      backgroundColor: AppTheme.surface,
      appBar: AppBar(
        title: const Text('Wings'),
        actions: [
          IconButton(
            icon: const Icon(Icons.add_rounded),
            tooltip: 'Add Wing',
            onPressed: () => context.push(AppRoutes.wingForm),
          ),
        ],
      ),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 12, 16, 0),
            child: Row(children: [
              Expanded(
                child: TextField(
                  controller: _search,
                  onChanged: (_) => setState(() {}),
                  decoration: InputDecoration(
                    hintText: 'Search wings...',
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
              ),
              const SizedBox(width: 8),
              FilterChip(
                label: const Text('Show Inactive'),
                selected: _showInactive,
                onSelected: (v) => setState(() => _showInactive = v),
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
                          ref.read(wingsProvider.notifier).refresh(),
                      child: const Text('Retry'),
                    ),
                  ],
                ),
              ),
              data: (wings) {
                final filtered = _filter(wings);
                if (filtered.isEmpty) {
                  return Center(
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Icon(Icons.apartment_outlined,
                            size: 56,
                            color: AppTheme.textSecondary.withOpacity(0.4)),
                        const SizedBox(height: 12),
                        Text(
                          wings.isEmpty
                              ? 'No wings yet.\nTap + to add the first wing.'
                              : 'No wings match your search.',
                          textAlign: TextAlign.center,
                          style: const TextStyle(
                              color: AppTheme.textSecondary, fontSize: 14),
                        ),
                      ],
                    ),
                  );
                }
                return RefreshIndicator(
                  onRefresh: () =>
                      ref.read(wingsProvider.notifier).refresh(),
                  child: ListView.separated(
                    padding: const EdgeInsets.fromLTRB(16, 4, 16, 24),
                    itemCount: filtered.length,
                    separatorBuilder: (_, __) => const SizedBox(height: 10),
                    itemBuilder: (_, i) => _WingCard(wing: filtered[i]),
                  ),
                );
              },
            ),
          ),
        ],
      ),
    );
  }
}

class _WingCard extends ConsumerWidget {
  final WingModel wing;
  const _WingCard({required this.wing});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return Container(
      decoration: BoxDecoration(
        color: AppTheme.cardBg,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(
          color: wing.isActive ? AppTheme.border : AppTheme.error.withOpacity(0.3),
        ),
      ),
      child: InkWell(
        borderRadius: BorderRadius.circular(14),
        onTap: () => context.push(
          AppRoutes.floorsByWing.replaceFirst(':wingId', wing.id),
          extra: wing,
        ),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Row(
            children: [
              Container(
                width: 46,
                height: 46,
                decoration: BoxDecoration(
                  color: (wing.isActive ? AppTheme.primary : AppTheme.textSecondary)
                      .withOpacity(0.12),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Center(
                  child: Text(
                    wing.code ?? wing.name.substring(0, 1).toUpperCase(),
                    style: TextStyle(
                      fontSize: 16,
                      fontWeight: FontWeight.w700,
                      color: wing.isActive
                          ? AppTheme.primary
                          : AppTheme.textSecondary,
                    ),
                  ),
                ),
              ),
              const SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(children: [
                      Expanded(
                        child: Text(wing.name,
                            style: const TextStyle(
                                fontSize: 15,
                                fontWeight: FontWeight.w600,
                                color: AppTheme.textPrimary)),
                      ),
                      if (!wing.isActive)
                        Container(
                          padding: const EdgeInsets.symmetric(
                              horizontal: 8, vertical: 2),
                          decoration: BoxDecoration(
                            color: AppTheme.error.withOpacity(0.12),
                            borderRadius: BorderRadius.circular(6),
                          ),
                          child: const Text('Inactive',
                              style: TextStyle(
                                  fontSize: 10,
                                  color: AppTheme.error,
                                  fontWeight: FontWeight.w600)),
                        ),
                    ]),
                    const SizedBox(height: 4),
                    Row(children: [
                      _StatChip(
                          icon: Icons.layers_rounded,
                          label: '${wing.floorCount} floors'),
                      const SizedBox(width: 8),
                      _StatChip(
                          icon: Icons.door_front_door_rounded,
                          label: '${wing.flatCount} flats'),
                    ]),
                    if (wing.description != null) ...[
                      const SizedBox(height: 4),
                      Text(wing.description!,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: const TextStyle(
                              fontSize: 12, color: AppTheme.textSecondary)),
                    ],
                  ],
                ),
              ),
              PopupMenuButton<String>(
                icon: const Icon(Icons.more_vert_rounded,
                    color: AppTheme.textSecondary),
                onSelected: (v) => _onMenu(context, ref, v),
                itemBuilder: (_) => [
                  PopupMenuItem(
                    value: 'edit',
                    child: const Text('Edit'),
                  ),
                  PopupMenuItem(
                    value: wing.isActive ? 'deactivate' : 'activate',
                    child: Text(wing.isActive ? 'Deactivate' : 'Activate'),
                  ),
                  const PopupMenuItem(
                    value: 'delete',
                    child: Text('Delete',
                        style: TextStyle(color: AppTheme.error)),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }

  Future<void> _onMenu(
      BuildContext context, WidgetRef ref, String action) async {
    if (action == 'edit') {
      context.push(AppRoutes.wingForm, extra: wing);
      return;
    }
    if (action == 'activate' || action == 'deactivate') {
      final activate = action == 'activate';
      try {
        await ref.read(structureRepoProvider).toggleWing(wing.id, activate: activate);
        ref.read(wingsProvider.notifier).refresh();
      } catch (e) {
        if (context.mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
              SnackBar(content: Text('Error: $e'), backgroundColor: AppTheme.error));
        }
      }
      return;
    }
    if (action == 'delete') {
      final ok = await showDialog<bool>(
        context: context,
        builder: (ctx) => AlertDialog(
          title: const Text('Delete Wing?'),
          content: Text('Delete "${wing.name}"? This cannot be undone.'),
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
          await ref.read(wingsProvider.notifier).delete(wing.id);
        } catch (e) {
          if (context.mounted) {
            ScaffoldMessenger.of(context).showSnackBar(
                SnackBar(
                    content: Text('Error: $e'),
                    backgroundColor: AppTheme.error));
          }
        }
      }
    }
  }
}

class _StatChip extends StatelessWidget {
  final IconData icon;
  final String label;
  const _StatChip({required this.icon, required this.label});

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(icon, size: 13, color: AppTheme.textSecondary),
        const SizedBox(width: 3),
        Text(label,
            style: const TextStyle(
                fontSize: 12, color: AppTheme.textSecondary)),
      ],
    );
  }
}
