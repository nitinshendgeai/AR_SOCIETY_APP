import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:ar_society_app/core/motion/loading.dart';
import 'package:ar_society_app/core/router/app_router.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/resident_master/data/models/resident_master_models.dart';
import 'package:ar_society_app/features/resident_master/presentation/providers/resident_master_providers.dart';
import 'package:ar_society_app/features/resident_master/presentation/widgets/resident_master_widgets.dart';
import 'package:ar_society_app/features/resident_master/presentation/widgets/vehicle_form_sheet.dart';
import 'package:ar_society_app/features/society_structure/presentation/providers/structure_providers.dart' show flatByIdProvider;
import 'package:ar_society_app/shared/widgets/app_widgets.dart';

/// A resident's own place in the society: their flat, who else lives in it, and the vehicles registered to it.
/// Residents can register a vehicle for their flat; changing or removing one is for the society office, which the
/// screen says rather than offering buttons that would be refused.
class MyHomeScreen extends ConsumerWidget {
  const MyHomeScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final residentAsync = ref.watch(myResidentProvider);
    return AppPage(
      title: 'My Home',
      body: residentAsync.when(
        loading: () => const AppLoader(),
        error: (e, _) => Center(
          child: Padding(
            padding: const EdgeInsets.all(24),
            child: Text(rmFriendlyError(e), textAlign: TextAlign.center, style: const TextStyle(color: AppTheme.error)),
          ),
        ),
        data: (me) {
          if (me == null) {
            return const Center(
              child: Padding(
                padding: EdgeInsets.all(24),
                child: Text('Your login is not linked to a flat yet. Ask the society office to link it.',
                    textAlign: TextAlign.center),
              ),
            );
          }
          return _Body(me: me);
        },
      ),
    );
  }
}

class _Body extends ConsumerWidget {
  final ResidentModel me;
  const _Body({required this.me});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final flat = ref.watch(flatByIdProvider(me.flatId)).valueOrNull;
    final household = ref.watch(residentsByFlatProvider(me.flatId));
    final vehicles = ref.watch(vehiclesByFlatProvider(me.flatId));
    final requests = ref.watch(myEditRequestsProvider).valueOrNull ?? const <ResidentEditRequestModel>[];
    final pending = requests.where((r) => r.status == ResidentEditRequestStatus.pending).firstOrNull;

    return RefreshIndicator(
      onRefresh: () async {
        ref.invalidate(residentsByFlatProvider(me.flatId));
        ref.invalidate(myEditRequestsProvider);
        await ref.read(vehiclesByFlatProvider(me.flatId).notifier).refresh();
      },
      child: ListView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.all(16),
        children: [
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              gradient: const LinearGradient(colors: [AppTheme.primary, AppTheme.primaryDark]),
              borderRadius: BorderRadius.circular(AppTheme.radiusL),
            ),
            child: Row(children: [
              const Icon(Icons.home_rounded, color: Colors.white, size: 32),
              const SizedBox(width: 14),
              Expanded(
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Text(flat?.displayName ?? 'My flat',
                      style: const TextStyle(color: Colors.white, fontSize: 20, fontWeight: FontWeight.w800)),
                  const SizedBox(height: 2),
                  Text('${me.fullName}  ·  ${me.residentType.label}',
                      style: TextStyle(color: Colors.white.withOpacity(0.9), fontSize: 13)),
                  if (me.moveInDate != null)
                    Text('Living here since ${rmFormatDate(me.moveInDate)}',
                        style: TextStyle(color: Colors.white.withOpacity(0.8), fontSize: 12)),
                ]),
              ),
            ]),
          ),
          const SizedBox(height: 12),
          if (pending != null)
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: AppTheme.warningSoft,
                borderRadius: BorderRadius.circular(AppTheme.radiusM),
                border: Border.all(color: AppTheme.warning.withOpacity(0.3)),
              ),
              child: const Row(children: [
                Icon(Icons.pending_actions_rounded, color: AppTheme.warning, size: 18),
                SizedBox(width: 8),
                Expanded(
                  child: Text('Your profile change is waiting for the office to approve',
                      style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600)),
                ),
              ]),
            ),
          if (pending != null) const SizedBox(height: 12),
          RmSection(
            title: 'My details',
            trailing: TextButton.icon(
              onPressed: () => context.push(AppRoutes.editMyProfile),
              icon: const Icon(Icons.edit_note_rounded, size: 18),
              label: const Text('Edit'),
            ),
            children: [
              _DetailRow(Icons.phone_outlined, 'Mobile', me.phone),
              _DetailRow(Icons.mail_outline_rounded, 'Email', me.email),
              _DetailRow(Icons.emergency_outlined, 'Emergency contact',
                  [me.emergencyContactName, me.emergencyContactPhone].whereType<String>().where((s) => s.isNotEmpty).join('  ·  ')),
            ],
          ),
          const SizedBox(height: 12),
          RmSection(
            title: 'Household',
            children: [
              household.when(
                loading: () => const LinearProgressIndicator(),
                error: (_, __) => const Text('Could not load the household',
                    style: TextStyle(color: AppTheme.error, fontSize: 12)),
                data: (all) {
                  final others = all.where((r) => r.id != me.id).toList();
                  if (others.isEmpty) {
                    return const Text('No one else is registered on this flat.',
                        style: TextStyle(fontSize: 13, color: AppTheme.textSecondary));
                  }
                  return Column(children: [
                    for (final r in others)
                      Padding(
                        padding: const EdgeInsets.symmetric(vertical: 6),
                        child: Row(children: [
                          const Icon(Icons.person_outline_rounded, size: 18, color: AppTheme.textSecondary),
                          const SizedBox(width: 10),
                          Expanded(
                            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                              Text(r.fullName, style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600)),
                              Text(r.residentType.label,
                                  style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
                            ]),
                          ),
                          if (r.isPrimary) const PrimaryChip(),
                        ]),
                      ),
                  ]);
                },
              ),
              const SizedBox(height: 6),
              const Text('To add or remove someone, ask the society office.',
                  style: TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
            ],
          ),
          const SizedBox(height: 12),
          RmSection(
            title: 'Vehicles',
            trailing: TextButton.icon(
              onPressed: () => showVehicleFormSheet(context, ref, flatId: me.flatId, residentId: me.id),
              icon: const Icon(Icons.add_circle_outline_rounded, size: 18),
              label: const Text('Add vehicle'),
            ),
            children: [
              vehicles.when(
                loading: () => const LinearProgressIndicator(),
                error: (e, _) => Text(rmFriendlyError(e), style: const TextStyle(color: AppTheme.error, fontSize: 12)),
                data: (list) {
                  if (list.isEmpty) {
                    return const Text('No vehicles registered. Add yours so the gate knows it.',
                        style: TextStyle(fontSize: 13, color: AppTheme.textSecondary));
                  }
                  return Column(children: [
                    for (final v in list)
                      Padding(
                        padding: const EdgeInsets.symmetric(vertical: 6),
                        child: Row(children: [
                          Icon(_twoWheeler(v.vehicleType) ? Icons.two_wheeler_rounded : Icons.directions_car_rounded,
                              size: 18, color: AppTheme.textSecondary),
                          const SizedBox(width: 10),
                          Expanded(
                            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                              Text(v.vehicleNumber,
                                  style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w700)),
                              Text(
                                [v.vehicleType.label, if (v.parkingSlot != null) 'Slot ${v.parkingSlot}'].join('  ·  '),
                                style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary),
                              ),
                            ]),
                          ),
                        ]),
                      ),
                  ]);
                },
              ),
              const SizedBox(height: 6),
              const Text('To change or remove a vehicle, ask the society office.',
                  style: TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
            ],
          ),
          const SizedBox(height: 24),
        ],
      ),
    );
  }
}

bool _twoWheeler(VehicleType t) => t == VehicleType.motorcycle || t == VehicleType.scooter || t == VehicleType.bicycle;

class _DetailRow extends StatelessWidget {
  final IconData icon;
  final String label;
  final String? value;
  const _DetailRow(this.icon, this.label, this.value);

  @override
  Widget build(BuildContext context) {
    final has = value != null && value!.isNotEmpty;
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 5),
      child: Row(children: [
        Icon(icon, size: 18, color: AppTheme.textSecondary),
        const SizedBox(width: 10),
        SizedBox(width: 120, child: Text(label, style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary))),
        Expanded(
          child: Text(has ? value! : 'Not set',
              style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: has ? AppTheme.textPrimary : AppTheme.textSecondary)),
        ),
      ]),
    );
  }
}
