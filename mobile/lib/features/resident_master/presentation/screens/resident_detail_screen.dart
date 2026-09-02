import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:ar_society_app/core/router/app_router.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/features/resident_master/data/models/resident_master_models.dart';
import 'package:ar_society_app/features/resident_master/presentation/providers/resident_master_providers.dart';
import 'package:ar_society_app/features/resident_master/presentation/widgets/resident_master_widgets.dart';
import 'package:ar_society_app/features/resident_master/presentation/widgets/occupancy_action_sheets.dart';
import 'package:ar_society_app/features/resident_master/presentation/widgets/vehicle_form_sheet.dart';
import 'package:ar_society_app/features/society_structure/data/models/structure_models.dart';
import 'package:ar_society_app/features/society_structure/presentation/providers/structure_providers.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';

/// Canonical Resident Detail screen — answers "who is this person, where do
/// they live, who else lives there, is it rented, and what vehicles do they
/// have" from a single place.
class ResidentDetailScreen extends ConsumerWidget {
  final ResidentModel resident;
  const ResidentDetailScreen({super.key, required this.resident});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final detailAsync = ref.watch(residentDetailProvider(resident.id));
    final user = ref.watch(currentUserProvider);
    final canEdit = user?.isAdminOrCommittee ?? false;

    return detailAsync.when(
      loading: () => const Scaffold(body: Center(child: CircularProgressIndicator())),
      error: (e, _) => Scaffold(
        appBar: AppBar(title: const Text('Resident')),
        body: Center(child: Text(rmFriendlyError(e), style: const TextStyle(color: AppTheme.error))),
      ),
      data: (r) => _ResidentDetailBody(resident: r, canEdit: canEdit),
    );
  }
}

class _ResidentDetailBody extends ConsumerWidget {
  final ResidentModel resident;
  final bool canEdit;
  const _ResidentDetailBody({required this.resident, required this.canEdit});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final flatsAsync = ref.watch(flatsBySocietyProvider);
    final flat = (flatsAsync.valueOrNull ?? <FlatModel>[])
        .where((f) => f.id == resident.flatId)
        .cast<FlatModel?>()
        .firstWhere((f) => true, orElse: () => null);

    final familyAsync = ref.watch(residentsByFlatProvider(resident.flatId));
    final tenantsAsync = ref.watch(tenantsByFlatProvider(resident.flatId));
    final vehiclesAsync = ref.watch(vehiclesByFlatProvider(resident.flatId));
    final historyAsync = ref.watch(flatHistoryProvider(resident.flatId));

    final canMoveIn = resident.isActive && resident.moveInDate == null;
    final canMoveOut = resident.isActive && resident.moveInDate != null && resident.moveOutDate == null;

    return Scaffold(
      backgroundColor: AppTheme.surface,
      appBar: AppBar(
        title: Text(resident.fullName),
        actions: [
          if (canEdit)
            IconButton(
              icon: const Icon(Icons.edit_rounded),
              tooltip: 'Edit',
              onPressed: () => context.push(AppRoutes.residentForm, extra: {'resident': resident}),
            ),
        ],
      ),
      body: ResponsiveBody(child: ListView(
        padding: const EdgeInsets.all(20),
        children: [
          _HeaderCard(resident: resident),
          const SizedBox(height: 16),

          RmSection(title: 'Profile', children: [
            RmRow(label: 'Date of Birth', value: rmFormatDate(resident.dateOfBirth)),
            RmRow(label: 'Phone', value: resident.phone ?? '—'),
            RmRow(label: 'Email', value: resident.email ?? '—'),
            RmRow(label: 'ID Proof', value: resident.idProofType != null
                ? '${resident.idProofType} · ${resident.idProofNumber ?? "—"}' : '—'),
            RmRow(label: 'KYC', value: resident.kycVerified ? 'Verified' : 'Not verified'),
            RmRow(label: 'Emergency Contact', value: resident.emergencyContactName != null
                ? '${resident.emergencyContactName} (${resident.emergencyContactPhone ?? "—"})' : '—'),
            RmRow(label: 'Communication', value: resident.commPreference.label),
          ]),
          const SizedBox(height: 16),

          RmSection(
            title: 'Flat',
            trailing: flat != null
                ? TextButton(
                    onPressed: () => context.push(AppRoutes.flatDetail, extra: flat),
                    child: const Text('View Flat', style: TextStyle(fontSize: 12)),
                  )
                : null,
            children: [
              RmRow(label: 'Wing', value: flat?.wingName ?? '—'),
              RmRow(label: 'Flat', value: flat?.displayName ?? '—'),
              if (flat?.floor != null) RmRow(label: 'Floor', value: flat!.floor.toString()),
              RmRow(label: 'Relationship', value: resident.residentType.label),
              RmRow(label: 'Move-in Date', value: rmFormatDate(resident.moveInDate)),
              if (resident.moveOutDate != null)
                RmRow(label: 'Move-out Date', value: rmFormatDate(resident.moveOutDate)),
            ],
          ),
          const SizedBox(height: 16),

          RmSection(
            title: 'Family (${familyAsync.valueOrNull?.where((r) => r.id != resident.id).length ?? 0})',
            children: [
              familyAsync.when(
                loading: () => const LinearProgressIndicator(),
                error: (_, __) => const Text('Unable to load family members', style: TextStyle(color: AppTheme.error, fontSize: 12)),
                data: (all) {
                  final others = all.where((r) => r.id != resident.id).toList();
                  if (others.isEmpty) {
                    return const Text('No other residents on this flat.',
                        style: TextStyle(fontSize: 13, color: AppTheme.textSecondary));
                  }
                  return Column(
                    children: others.map((r) => _PersonTile(
                          name: r.fullName,
                          subtitle: r.residentType.label,
                          trailing: r.isPrimary ? const PrimaryChip() : null,
                          onTap: () => context.push(AppRoutes.residentDetail, extra: r),
                        )).toList(),
                  );
                },
              ),
            ],
          ),
          const SizedBox(height: 16),

          RmSection(
            title: 'Tenancy',
            children: [
              tenantsAsync.when(
                loading: () => const LinearProgressIndicator(),
                error: (_, __) => const Text('Unable to load tenancy info', style: TextStyle(color: AppTheme.error, fontSize: 12)),
                data: (tenants) {
                  final active = tenants.where((t) => t.moveOutDate == null).toList();
                  if (active.isEmpty) {
                    return const Text('This flat is not currently rented.',
                        style: TextStyle(fontSize: 13, color: AppTheme.textSecondary));
                  }
                  return Column(
                    children: active.map((t) => _PersonTile(
                          name: t.fullName,
                          subtitle: t.agreementEndDate != null
                              ? 'Agreement until ${rmFormatDate(t.agreementEndDate)}'
                              : 'Tenant',
                          trailing: null,
                          onTap: () => context.push(AppRoutes.tenantDetail, extra: t),
                        )).toList(),
                  );
                },
              ),
            ],
          ),
          const SizedBox(height: 16),

          RmSection(
            title: 'Vehicles',
            trailing: canEdit
                ? IconButton(
                    icon: const Icon(Icons.add_circle_outline_rounded, size: 20, color: AppTheme.primary),
                    tooltip: 'Add Vehicle',
                    onPressed: () => showVehicleFormSheet(context, ref,
                        flatId: resident.flatId, residentId: resident.id),
                  )
                : null,
            children: [
              vehiclesAsync.when(
                loading: () => const LinearProgressIndicator(),
                error: (e, _) => Text(rmFriendlyError(e), style: const TextStyle(color: AppTheme.error, fontSize: 12)),
                data: (vehicles) {
                  final own = vehicles.where((v) => v.residentId == resident.id).toList();
                  if (own.isEmpty) {
                    return const Text('No vehicles registered.',
                        style: TextStyle(fontSize: 13, color: AppTheme.textSecondary));
                  }
                  return Column(
                    children: own.map((v) => _VehicleTile(
                          vehicle: v,
                          canEdit: canEdit,
                          onEdit: () => showVehicleFormSheet(context, ref,
                              flatId: resident.flatId, residentId: resident.id, vehicle: v),
                          onDeactivate: () => confirmDeactivateVehicle(
                              context, ref, resident.flatId, v),
                        )).toList(),
                  );
                },
              ),
            ],
          ),
          const SizedBox(height: 16),

          RmSection(title: 'Occupancy History', children: [
            historyAsync.when(
              loading: () => const LinearProgressIndicator(),
              error: (_, __) => const Text('Unable to load history', style: TextStyle(color: AppTheme.error, fontSize: 12)),
              data: (logs) {
                final relevant = logs.where((l) => l.residentId == resident.id).toList();
                if (relevant.isEmpty) {
                  return const Text('No occupancy events recorded yet.',
                      style: TextStyle(fontSize: 13, color: AppTheme.textSecondary));
                }
                return Column(
                  children: relevant.map((l) => Padding(
                        padding: const EdgeInsets.symmetric(vertical: 6),
                        child: Row(children: [
                          const Icon(Icons.circle, size: 6, color: AppTheme.primary),
                          const SizedBox(width: 8),
                          Expanded(child: Text(l.eventType.label, style: const TextStyle(fontSize: 13, color: AppTheme.textPrimary))),
                          Text(rmFormatDate(l.eventDate), style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
                        ]),
                      )).toList(),
                );
              },
            ),
          ]),

          if (canEdit && (canMoveIn || canMoveOut)) ...[
            const SizedBox(height: 24),
            if (canMoveIn)
              OutlinedButton.icon(
                onPressed: () => showResidentMoveInSheet(context, ref, resident: resident),
                icon: const Icon(Icons.login_rounded, size: 18),
                label: const Text('Move In'),
                style: OutlinedButton.styleFrom(
                  foregroundColor: AppTheme.success,
                  side: const BorderSide(color: AppTheme.success),
                  minimumSize: const Size(double.infinity, 44),
                ),
              ),
            if (canMoveOut)
              OutlinedButton.icon(
                onPressed: () => showResidentMoveOutSheet(context, ref, resident: resident),
                icon: const Icon(Icons.logout_rounded, size: 18),
                label: const Text('Move Out'),
                style: OutlinedButton.styleFrom(
                  foregroundColor: AppTheme.error,
                  side: const BorderSide(color: AppTheme.error),
                  minimumSize: const Size(double.infinity, 44),
                ),
              ),
          ],
          const SizedBox(height: 24),
        ],
      )),
    );
  }
}

class _HeaderCard extends StatelessWidget {
  final ResidentModel resident;
  const _HeaderCard({required this.resident});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: [AppTheme.primary.withOpacity(0.12), AppTheme.primary.withOpacity(0.03)],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppTheme.primary.withOpacity(0.15)),
      ),
      child: Row(children: [
        Container(
          width: 56,
          height: 56,
          decoration: BoxDecoration(color: AppTheme.primary.withOpacity(0.15), shape: BoxShape.circle),
          child: const Icon(Icons.person_rounded, color: AppTheme.primary, size: 28),
        ),
        const SizedBox(width: 16),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(resident.fullName,
                  style: const TextStyle(fontSize: 19, fontWeight: FontWeight.w700, color: AppTheme.textPrimary)),
              const SizedBox(height: 6),
              Wrap(spacing: 6, runSpacing: 6, children: [
                ResidentTypeBadge(type: resident.residentType),
                if (resident.isPrimary) const PrimaryChip(),
                ActiveBadge(isActive: resident.isActive),
              ]),
            ],
          ),
        ),
      ]),
    );
  }
}

class _PersonTile extends StatelessWidget {
  final String name;
  final String subtitle;
  final Widget? trailing;
  final VoidCallback onTap;
  const _PersonTile({required this.name, required this.subtitle, this.trailing, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(10),
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 8),
        child: Row(children: [
          const Icon(Icons.person_outline_rounded, size: 18, color: AppTheme.textSecondary),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(name, style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: AppTheme.textPrimary)),
                Text(subtitle, style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
              ],
            ),
          ),
          if (trailing != null) trailing!,
          const Icon(Icons.chevron_right_rounded, size: 18, color: AppTheme.textSecondary),
        ]),
      ),
    );
  }
}

class _VehicleTile extends StatelessWidget {
  final VehicleModel vehicle;
  final bool canEdit;
  final VoidCallback onEdit;
  final VoidCallback onDeactivate;
  const _VehicleTile({
    required this.vehicle,
    required this.canEdit,
    required this.onEdit,
    required this.onDeactivate,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Row(children: [
        const Icon(Icons.directions_car_rounded, size: 18, color: AppTheme.textSecondary),
        const SizedBox(width: 10),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(vehicle.vehicleNumber, style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w700, color: AppTheme.textPrimary)),
              Text('${vehicle.vehicleType.label}${vehicle.parkingSlot != null ? " · Slot ${vehicle.parkingSlot}" : ""}',
                  style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
            ],
          ),
        ),
        if (canEdit) ...[
          IconButton(
            icon: const Icon(Icons.edit_outlined, size: 18),
            tooltip: 'Edit vehicle',
            onPressed: onEdit,
          ),
          IconButton(
            icon: const Icon(Icons.remove_circle_outline_rounded, size: 18, color: AppTheme.error),
            tooltip: 'Deregister vehicle',
            onPressed: onDeactivate,
          ),
        ],
      ]),
    );
  }
}
