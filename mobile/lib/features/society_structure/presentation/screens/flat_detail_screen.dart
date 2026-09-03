import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/router/app_router.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/society_structure/data/models/structure_models.dart';
import 'package:ar_society_app/features/society_structure/presentation/providers/structure_providers.dart';
import 'package:ar_society_app/features/resident_master/presentation/providers/resident_master_providers.dart';
import 'package:ar_society_app/features/resident_master/data/models/resident_master_models.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';

class FlatDetailScreen extends ConsumerWidget {
  final FlatModel flat;
  const FlatDetailScreen({super.key, required this.flat});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    // Read the live copy from flatsBySocietyProvider (already kept fresh by
    // every mutation) rather than the possibly-stale `flat` this screen was
    // pushed with — otherwise Save Changes on Edit Flat returns here via a
    // plain pop and this screen keeps showing pre-edit field values.
    final current = ref
            .watch(flatsBySocietyProvider)
            .valueOrNull
            ?.where((f) => f.id == flat.id)
            .firstOrNull ??
        flat;

    return Scaffold(
      backgroundColor: AppTheme.surface,
      appBar: AppBar(
        title: Text('Flat ${current.flatNumber}'),
        actions: [
          IconButton(
            icon: const Icon(Icons.edit_rounded),
            tooltip: 'Edit',
            onPressed: () => context.push(AppRoutes.flatForm, extra: {'flat': current}),
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
      body: ResponsiveBody(child: ListView(
        padding: const EdgeInsets.all(20),
        children: [
          _HeaderCard(flat: current),
          const SizedBox(height: 16),
          _DetailsCard(flat: current),
          const SizedBox(height: 16),
          _PeopleCard(flat: current),
        ],
      )),
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
                content: Text(friendlyErrorMessage(e)),
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

/// Concise "who lives here" summary — links into the Resident Master
/// screens rather than reproducing their detail here (Phase M1.4 §20:
/// Flat Detail must not become a dashboard).
class _PeopleCard extends ConsumerWidget {
  final FlatModel flat;
  const _PeopleCard({required this.flat});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final residentsAsync = ref.watch(residentsByFlatProvider(flat.id));
    final tenantsAsync = ref.watch(tenantsByFlatProvider(flat.id));
    final vehiclesAsync = ref.watch(vehiclesByFlatProvider(flat.id));

    final residents = residentsAsync.valueOrNull ?? const [];
    ResidentModel? primary;
    for (final r in residents) {
      if (r.isPrimary) { primary = r; break; }
    }
    final activeTenants = (tenantsAsync.valueOrNull ?? const [])
        .where((t) => t.moveOutDate == null).toList();
    final vehicleCount = vehiclesAsync.valueOrNull?.length;

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
          const Text('People',
              style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: AppTheme.textSecondary)),
          const SizedBox(height: 12),
          _PeopleRow(
            icon: Icons.star_rounded,
            label: 'Primary Resident',
            value: primary != null ? primary.fullName : (residents.isEmpty ? 'None on record' : '—'),
          ),
          _PeopleRow(
            icon: Icons.people_outline_rounded,
            label: 'Residents',
            value: '${residents.length}',
            onTap: () => context.push(AppRoutes.residentsList, extra: {'flat': flat}),
          ),
          _PeopleRow(
            icon: Icons.groups_2_outlined,
            label: 'Tenant',
            value: activeTenants.isNotEmpty ? activeTenants.first.fullName : 'Not rented',
            onTap: () => context.push(AppRoutes.tenantsList, extra: {'flat': flat}),
          ),
          _PeopleRow(
            icon: Icons.directions_car_outlined,
            label: 'Vehicles',
            value: vehicleCount != null ? '$vehicleCount' : '…',
          ),
        ],
      ),
    );
  }
}

class _PeopleRow extends StatelessWidget {
  final IconData icon;
  final String label;
  final String value;
  final VoidCallback? onTap;
  const _PeopleRow({required this.icon, required this.label, required this.value, this.onTap});

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(8),
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 8),
        child: Row(children: [
          Icon(icon, size: 16, color: AppTheme.textSecondary),
          const SizedBox(width: 10),
          Expanded(
            flex: 2,
            child: Text(label, style: const TextStyle(fontSize: 13, color: AppTheme.textSecondary)),
          ),
          const SizedBox(width: 8),
          Expanded(
            flex: 3,
            child: Text(
              value,
              textAlign: TextAlign.end,
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: AppTheme.textPrimary),
            ),
          ),
          if (onTap != null) ...[
            const SizedBox(width: 4),
            const Icon(Icons.chevron_right_rounded, size: 16, color: AppTheme.textSecondary),
          ],
        ]),
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
