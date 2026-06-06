import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:ar_society_app/core/router/app_router.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/society_structure/data/models/structure_models.dart';
import 'package:ar_society_app/features/society_structure/presentation/providers/structure_providers.dart';

class FlatDetailScreen extends ConsumerWidget {
  final FlatModel flat;
  const FlatDetailScreen({super.key, required this.flat});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return Scaffold(
      backgroundColor: AppTheme.surface,
      appBar: AppBar(
        title: Text('Flat ${flat.flatNumber}'),
        actions: [
          IconButton(
            icon: const Icon(Icons.edit_rounded),
            tooltip: 'Edit',
            onPressed: () => context.push(AppRoutes.flatForm, extra: {'flat': flat}),
          ),
          PopupMenuButton<String>(
            onSelected: (v) => _onMenu(context, ref, v),
            itemBuilder: (_) => [
              const PopupMenuItem(
                value: 'delete',
                child: Text('Delete', style: TextStyle(color: AppTheme.error)),
              ),
            ],
          ),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.all(20),
        children: [
          _HeaderCard(flat: flat),
          const SizedBox(height: 16),
          _DetailsCard(flat: flat),
        ],
      ),
    );
  }

  Future<void> _onMenu(
      BuildContext context, WidgetRef ref, String action) async {
    if (action == 'delete') {
      final ok = await showDialog<bool>(
        context: context,
        builder: (ctx) => AlertDialog(
          title: const Text('Delete Flat?'),
          content: Text('Permanently delete flat "${flat.displayName}"?'),
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
      if (ok == true && context.mounted) {
        try {
          await ref.read(flatsBySocietyProvider.notifier).delete(flat.id);
          context.pop();
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

class _HeaderCard extends StatelessWidget {
  final FlatModel flat;
  const _HeaderCard({required this.flat});

  @override
  Widget build(BuildContext context) {
    Color occColor;
    String occLabel;
    IconData occIcon;
    switch (flat.occupancyStatus) {
      case 'owner_occupied':
        occColor = AppTheme.success;
        occLabel = 'Owner Occupied';
        occIcon  = Icons.home_rounded;
        break;
      case 'tenant_occupied':
        occColor = AppTheme.warning;
        occLabel = 'Tenant Occupied';
        occIcon  = Icons.person_rounded;
        break;
      default:
        occColor = AppTheme.textSecondary;
        occLabel = 'Vacant';
        occIcon  = Icons.door_front_door_outlined;
        break;
    }

    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: [occColor.withOpacity(0.15), occColor.withOpacity(0.05)],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: occColor.withOpacity(0.2)),
      ),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Container(
            width: 52,
            height: 52,
            decoration: BoxDecoration(
              color: occColor.withOpacity(0.2),
              borderRadius: BorderRadius.circular(14),
            ),
            child: Icon(occIcon, color: occColor, size: 28),
          ),
          const SizedBox(width: 16),
          Expanded(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text(flat.displayName,
                  style: const TextStyle(
                      fontSize: 20,
                      fontWeight: FontWeight.w700,
                      color: AppTheme.textPrimary)),
              const SizedBox(height: 4),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 3),
                decoration: BoxDecoration(
                  color: occColor.withOpacity(0.15),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Text(occLabel,
                    style: TextStyle(
                        fontSize: 12,
                        fontWeight: FontWeight.w600,
                        color: occColor)),
              ),
            ]),
          ),
        ]),
      ]),
    );
  }
}

class _DetailsCard extends StatelessWidget {
  final FlatModel flat;
  const _DetailsCard({required this.flat});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppTheme.cardBg,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: AppTheme.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('Details',
              style: TextStyle(
                  fontSize: 13,
                  fontWeight: FontWeight.w600,
                  color: AppTheme.textSecondary)),
          const SizedBox(height: 12),
          _Row(label: 'Flat Number', value: flat.flatNumber),
          if (flat.wingName != null)
            _Row(label: 'Wing', value: flat.wingName!),
          if (flat.floor != null)
            _Row(label: 'Floor', value: flat.floor.toString()),
          if (flat.flatType != null)
            _Row(label: 'Type', value: flat.flatType!),
          if (flat.areaSqft != null)
            _Row(
                label: 'Area',
                value: '${flat.areaSqft!.toStringAsFixed(0)} sq ft'),
          _Row(label: 'Status', value: flat.isActive ? 'Active' : 'Inactive'),
          if (flat.remarks != null && flat.remarks!.isNotEmpty)
            _Row(label: 'Remarks', value: flat.remarks!),
        ],
      ),
    );
  }
}

class _Row extends StatelessWidget {
  final String label;
  final String value;
  const _Row({required this.label, required this.value});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Row(children: [
        Expanded(
          flex: 2,
          child: Text(label,
              style: const TextStyle(
                  fontSize: 13, color: AppTheme.textSecondary)),
        ),
        Expanded(
          flex: 3,
          child: Text(value,
              style: const TextStyle(
                  fontSize: 13,
                  fontWeight: FontWeight.w500,
                  color: AppTheme.textPrimary)),
        ),
      ]),
    );
  }
}
