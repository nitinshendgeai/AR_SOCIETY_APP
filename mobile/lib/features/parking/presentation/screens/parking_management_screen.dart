import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/features/parking/domain/entities/parking_entities.dart';
import 'package:ar_society_app/features/parking/presentation/providers/parking_providers.dart';
import 'package:ar_society_app/features/resident_master/data/models/resident_master_models.dart';
import 'package:ar_society_app/features/resident_master/presentation/providers/resident_master_providers.dart';
import 'package:ar_society_app/features/society_structure/data/models/structure_models.dart';
import 'package:ar_society_app/features/society_structure/presentation/providers/structure_providers.dart';
import 'package:ar_society_app/features/staff/presentation/widgets/staff_widgets.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';

/// Admin/Committee screen for the parking setup that gate validation
/// depends on: define zones and slots, then allocate a slot to a specific
/// resident/tenant vehicle (permanent "alloted" parking, or "rented" when a
/// monthly charge is set). Only a vehicle with an active allocation here
/// (or a formal one is not required if Vehicle.parking_slot is set
/// directly — see ParkingService._resolve_parking_slot) passes the gate
/// check in gate_check_screen.dart.
class ParkingManagementScreen extends ConsumerStatefulWidget {
  const ParkingManagementScreen({super.key});

  @override
  ConsumerState<ParkingManagementScreen> createState() => _ParkingManagementScreenState();
}

class _ParkingManagementScreenState extends ConsumerState<ParkingManagementScreen>
    with SingleTickerProviderStateMixin {
  late TabController _tab;

  String get _societyId => ref.read(currentUserProvider)?.societyId ?? '';

  @override
  void initState() {
    super.initState();
    _tab = TabController(length: 2, vsync: this);
  }

  @override
  void dispose() {
    _tab.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final societyId = _societyId;

    ref.listen(parkingManagementProvider, (_, next) {
      if (next is ParkingActionSuccess) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(
          content: Text(next.message),
          backgroundColor: AppTheme.success,
          behavior: SnackBarBehavior.floating,
        ));
        ref.read(parkingManagementProvider.notifier).reset();
      } else if (next is ParkingActionError) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(
          content: Text(next.message),
          backgroundColor: AppTheme.error,
          behavior: SnackBarBehavior.floating,
        ));
        ref.read(parkingManagementProvider.notifier).reset();
      }
    });

    return Scaffold(
      backgroundColor: AppTheme.surface,
      appBar: AppBar(
        title: const Text('Parking Management'),
        bottom: TabBar(
          controller: _tab,
          tabs: const [Tab(text: 'Slots'), Tab(text: 'Allocations')],
        ),
      ),
      floatingActionButton: AnimatedBuilder(
        animation: _tab,
        builder: (_, __) => FloatingActionButton.extended(
          onPressed: societyId.isEmpty
              ? null
              : () => _tab.index == 0
                  ? _showAddSlotFlow(context, societyId)
                  : _showAllocateFlow(context, societyId),
          backgroundColor: AppTheme.primary,
          foregroundColor: Colors.white,
          icon: Icon(_tab.index == 0 ? Icons.add_road_rounded : Icons.assignment_add),
          label: Text(_tab.index == 0 ? 'Add Slot' : 'Allocate Parking'),
        ),
      ),
      body: societyId.isEmpty
          ? const Center(child: Text('Society not loaded. Please reload the app.'))
          : TabBarView(
              controller: _tab,
              children: [
                _SlotsTab(societyId: societyId),
                _AllocationsTab(societyId: societyId),
              ],
            ),
    );
  }

  Future<void> _showAddSlotFlow(BuildContext context, String societyId) async {
    final zonesAsync = ref.read(parkingZonesProvider(societyId));
    final zones = zonesAsync.valueOrNull ?? const <ParkingZoneEntity>[];
    if (zones.isEmpty) {
      final addZone = await showDialog<bool>(
        context: context,
        builder: (_) => AlertDialog(
          title: const Text('No zones yet'),
          content: const Text('Create a parking zone (e.g. "Basement", "Open Yard") before adding slots.'),
          actions: [
            TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Cancel')),
            ElevatedButton(onPressed: () => Navigator.pop(context, true), child: const Text('Add Zone')),
          ],
        ),
      );
      if (addZone == true && context.mounted) await _showAddZoneDialog(context, societyId);
      return;
    }
    if (context.mounted) await _showAddSlotDialog(context, societyId, zones);
  }

  Future<void> _showAddZoneDialog(BuildContext context, String societyId) async {
    final nameCtrl = TextEditingController();
    final codeCtrl = TextEditingController();
    final ok = await showDialog<bool>(
      context: context,
      builder: (_) => AlertDialog(
        title: const Text('Add Parking Zone'),
        content: Column(mainAxisSize: MainAxisSize.min, children: [
          TextField(controller: nameCtrl, decoration: const InputDecoration(labelText: 'Zone name (e.g. Basement)')),
          const SizedBox(height: 10),
          TextField(controller: codeCtrl, decoration: const InputDecoration(labelText: 'Short code (optional)')),
        ]),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Cancel')),
          ElevatedButton(onPressed: () => Navigator.pop(context, true), child: const Text('Create')),
        ],
      ),
    );
    if (ok == true && nameCtrl.text.trim().isNotEmpty) {
      ref.read(parkingManagementProvider.notifier).createZone(
            societyId: societyId, name: nameCtrl.text.trim(),
            code: codeCtrl.text.trim().isEmpty ? null : codeCtrl.text.trim(),
          );
    }
  }

  Future<void> _showAddSlotDialog(
      BuildContext context, String societyId, List<ParkingZoneEntity> zones) async {
    final slotCtrl = TextEditingController();
    String zoneId = zones.first.id;
    String slotType = 'resident';
    final ok = await showDialog<bool>(
      context: context,
      builder: (_) => StatefulBuilder(builder: (context, setState) {
        return AlertDialog(
          title: const Text('Add Parking Slot'),
          content: Column(mainAxisSize: MainAxisSize.min, children: [
            DropdownButtonFormField<String>(
              value: zoneId,
              decoration: const InputDecoration(labelText: 'Zone'),
              items: zones.map((z) => DropdownMenuItem(value: z.id, child: Text(z.name))).toList(),
              onChanged: (v) => setState(() => zoneId = v!),
            ),
            const SizedBox(height: 10),
            TextField(controller: slotCtrl, decoration: const InputDecoration(labelText: 'Slot number (e.g. B1-24)')),
            const SizedBox(height: 10),
            DropdownButtonFormField<String>(
              value: slotType,
              decoration: const InputDecoration(labelText: 'Reserved for'),
              items: const [
                DropdownMenuItem(value: 'resident', child: Text('Resident')),
                DropdownMenuItem(value: 'tenant', child: Text('Tenant')),
                DropdownMenuItem(value: 'visitor', child: Text('Visitor')),
                DropdownMenuItem(value: 'staff', child: Text('Staff')),
                DropdownMenuItem(value: 'reserved', child: Text('Reserved')),
              ],
              onChanged: (v) => setState(() => slotType = v!),
            ),
          ]),
          actions: [
            TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Cancel')),
            ElevatedButton(onPressed: () => Navigator.pop(context, true), child: const Text('Create')),
          ],
        );
      }),
    );
    if (ok == true && slotCtrl.text.trim().isNotEmpty) {
      ref.read(parkingManagementProvider.notifier).createSlot(
            societyId: societyId, zoneId: zoneId,
            slotNumber: slotCtrl.text.trim(), slotType: slotType,
          );
    }
  }

  Future<void> _showAllocateFlow(BuildContext context, String societyId) async {
    await showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (_) => _AllocateParkingSheet(societyId: societyId),
    );
  }
}

// ── Slots tab ────────────────────────────────────────────────────────────────

class _SlotsTab extends ConsumerWidget {
  final String societyId;
  const _SlotsTab({required this.societyId});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final zonesAsync = ref.watch(parkingZonesProvider(societyId));
    final slotsAsync = ref.watch(parkingSlotsProvider(societyId));

    return RefreshIndicator(
      onRefresh: () async {
        ref.invalidate(parkingZonesProvider(societyId));
        ref.invalidate(parkingSlotsProvider(societyId));
      },
      child: zonesAsync.when(
        loading: () => const Center(child: CircularProgressIndicator(color: AppTheme.primary)),
        error: (e, _) => ListView(children: [
          const SizedBox(height: 60),
          AppErrorBanner(message: 'Could not load zones: $e'),
        ]),
        data: (zones) {
          if (zones.isEmpty) {
            return ListView(children: const [
              SizedBox(height: 60),
              EmptyState(
                icon: Icons.local_parking_rounded,
                title: 'No parking zones yet',
                subtitle: 'Tap "Add Slot" to create your first zone and slot',
              ),
            ]);
          }
          final slots = slotsAsync.valueOrNull ?? const <ParkingSlotEntity>[];
          return ListView.separated(
            padding: const EdgeInsets.fromLTRB(16, 16, 16, 90),
            itemCount: zones.length,
            separatorBuilder: (_, __) => const SizedBox(height: 12),
            itemBuilder: (_, i) {
              final zone = zones[i];
              final zoneSlots = slots.where((s) => s.zoneId == zone.id).toList();
              return _ZoneCard(zone: zone, slots: zoneSlots);
            },
          );
        },
      ),
    );
  }
}

class _ZoneCard extends StatelessWidget {
  final ParkingZoneEntity zone;
  final List<ParkingSlotEntity> slots;
  const _ZoneCard({required this.zone, required this.slots});

  @override
  Widget build(BuildContext context) {
    return AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(children: [
            Expanded(
              child: Text(zone.name,
                  style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w700, color: AppTheme.textPrimary)),
            ),
            Text('${slots.length} slot${slots.length == 1 ? '' : 's'}',
                style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
          ]),
          if (slots.isNotEmpty) ...[
            const SizedBox(height: 10),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: slots.map((s) => _SlotChip(slot: s)).toList(),
            ),
          ],
        ],
      ),
    );
  }
}

class _SlotChip extends StatelessWidget {
  final ParkingSlotEntity slot;
  const _SlotChip({required this.slot});

  Color get _color {
    switch (slot.status) {
      case ParkingSlotStatus.available: return AppTheme.success;
      case ParkingSlotStatus.occupied:  return AppTheme.secondary;
      case ParkingSlotStatus.reserved:  return AppTheme.warning;
      default:                          return AppTheme.error;
    }
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: _color.withOpacity(0.1),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: _color.withOpacity(0.3)),
      ),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, mainAxisSize: MainAxisSize.min, children: [
        Text(slot.slotNumber,
            style: TextStyle(fontSize: 12, fontWeight: FontWeight.w700, color: _color)),
        Text(slot.status.label, style: TextStyle(fontSize: 10, color: _color)),
      ]),
    );
  }
}

// ── Allocations tab ────────────────────────────────────────────────────────

class _AllocationsTab extends ConsumerWidget {
  final String societyId;
  const _AllocationsTab({required this.societyId});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final allocationsAsync = ref.watch(parkingAllocationsProvider(societyId));

    return RefreshIndicator(
      onRefresh: () async => ref.invalidate(parkingAllocationsProvider(societyId)),
      child: allocationsAsync.when(
        loading: () => const Center(child: CircularProgressIndicator(color: AppTheme.primary)),
        error: (e, _) => ListView(children: [
          const SizedBox(height: 60),
          AppErrorBanner(message: 'Could not load allocations: $e'),
        ]),
        data: (allocations) {
          final active = allocations.where((a) => a.isActive).toList();
          if (active.isEmpty) {
            return ListView(children: const [
              SizedBox(height: 60),
              EmptyState(
                icon: Icons.assignment_late_outlined,
                title: 'No parking allocated yet',
                subtitle: 'Tap "Allocate Parking" to give a vehicle an allotted or rented slot',
              ),
            ]);
          }
          return ListView.separated(
            padding: const EdgeInsets.fromLTRB(16, 16, 16, 90),
            itemCount: active.length,
            separatorBuilder: (_, __) => const SizedBox(height: 10),
            itemBuilder: (_, i) => _AllocationTile(allocation: active[i], societyId: societyId),
          );
        },
      ),
    );
  }
}

class _AllocationTile extends ConsumerWidget {
  final ParkingAllocationEntity allocation;
  final String societyId;
  const _AllocationTile({required this.allocation, required this.societyId});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final flat = [
      if (allocation.wingName != null) allocation.wingName,
      if (allocation.flatNumber != null) allocation.flatNumber,
    ].where((s) => s != null).join(' — ');

    return AppCard(
      child: Row(children: [
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(children: [
                Text(allocation.slotNumber ?? '—',
                    style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w700, color: AppTheme.primary)),
                const SizedBox(width: 8),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                  decoration: BoxDecoration(
                    color: (allocation.isRented ? AppTheme.warning : AppTheme.success).withOpacity(0.12),
                    borderRadius: BorderRadius.circular(6),
                  ),
                  child: Text(allocation.isRented ? 'Rented' : 'Alloted',
                      style: TextStyle(
                          fontSize: 10, fontWeight: FontWeight.w600,
                          color: allocation.isRented ? AppTheme.warning : AppTheme.success)),
                ),
              ]),
              const SizedBox(height: 4),
              Text(allocation.vehicleNumber ?? 'No vehicle linked',
                  style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: AppTheme.textPrimary)),
              if (flat.isNotEmpty)
                Text(flat, style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
            ],
          ),
        ),
        TextButton(
          onPressed: () => ref
              .read(parkingManagementProvider.notifier)
              .releaseAllocation(allocation.id, societyId),
          child: const Text('Release'),
        ),
      ]),
    );
  }
}

// ── Allocate Parking flow (bottom sheet) ─────────────────────────────────────

class _AllocateParkingSheet extends ConsumerStatefulWidget {
  final String societyId;
  const _AllocateParkingSheet({required this.societyId});

  @override
  ConsumerState<_AllocateParkingSheet> createState() => _AllocateParkingSheetState();
}

class _AllocateParkingSheetState extends ConsumerState<_AllocateParkingSheet> {
  FlatModel? _flat;
  VehicleModel? _vehicle;
  ParkingSlotEntity? _slot;
  final _chargeCtrl = TextEditingController();

  @override
  void dispose() {
    _chargeCtrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final flatsAsync = ref.watch(flatsBySocietyProvider);
    final availableSlotsAsync = ref.watch(parkingAvailableSlotsProvider(widget.societyId));
    final actionState = ref.watch(parkingManagementProvider);

    return Padding(
      padding: EdgeInsets.only(bottom: MediaQuery.of(context).viewInsets.bottom),
      child: Container(
        padding: const EdgeInsets.all(20),
        decoration: const BoxDecoration(
          color: AppTheme.surface,
          borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
        ),
        child: SingleChildScrollView(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisSize: MainAxisSize.min,
            children: [
              const Text('Allocate Parking',
                  style: TextStyle(fontSize: 17, fontWeight: FontWeight.w700)),
              const SizedBox(height: 16),
              flatsAsync.when(
                loading: () => const LinearProgressIndicator(),
                error: (e, _) => Text('Could not load flats: $e'),
                data: (flats) => DropdownButtonFormField<FlatModel>(
                  value: _flat,
                  decoration: const InputDecoration(labelText: 'Flat'),
                  items: flats
                      .map((f) => DropdownMenuItem(
                          value: f, child: Text('${f.wingName ?? ''} — ${f.flatNumber}')))
                      .toList(),
                  onChanged: (v) => setState(() { _flat = v; _vehicle = null; }),
                ),
              ),
              const SizedBox(height: 12),
              if (_flat != null)
                Consumer(builder: (context, ref, __) {
                  final vehiclesAsync = ref.watch(vehiclesByFlatProvider(_flat!.id));
                  return vehiclesAsync.when(
                    loading: () => const LinearProgressIndicator(),
                    error: (e, _) => Text('Could not load vehicles: $e'),
                    data: (vehicles) {
                      if (vehicles.isEmpty) {
                        return const Text('No vehicles registered on this flat yet.',
                            style: TextStyle(fontSize: 13, color: AppTheme.textSecondary));
                      }
                      return DropdownButtonFormField<VehicleModel>(
                        value: _vehicle,
                        decoration: const InputDecoration(labelText: 'Vehicle'),
                        items: vehicles
                            .map((v) => DropdownMenuItem(value: v, child: Text(v.vehicleNumber)))
                            .toList(),
                        onChanged: (v) => setState(() => _vehicle = v),
                      );
                    },
                  );
                }),
              const SizedBox(height: 12),
              availableSlotsAsync.when(
                loading: () => const LinearProgressIndicator(),
                error: (e, _) => Text('Could not load slots: $e'),
                data: (slots) {
                  if (slots.isEmpty) {
                    return const Text('No available slots — add one in the Slots tab first.',
                        style: TextStyle(fontSize: 13, color: AppTheme.textSecondary));
                  }
                  return DropdownButtonFormField<ParkingSlotEntity>(
                    value: _slot,
                    decoration: const InputDecoration(labelText: 'Available Slot'),
                    items: slots
                        .map((s) => DropdownMenuItem(value: s, child: Text(s.slotNumber)))
                        .toList(),
                    onChanged: (v) => setState(() => _slot = v),
                  );
                },
              ),
              const SizedBox(height: 12),
              TextField(
                controller: _chargeCtrl,
                keyboardType: TextInputType.number,
                decoration: const InputDecoration(
                  labelText: 'Monthly charge (optional)',
                  helperText: 'Leave blank for free/alloted parking; set an amount for rented parking',
                  helperMaxLines: 2,
                ),
              ),
              const SizedBox(height: 20),
              AppPrimaryButton(
                label: 'Allocate',
                isLoading: actionState is ParkingActionLoading,
                onPressed: (_flat == null || _vehicle == null || _slot == null)
                    ? null
                    : () {
                        final now = DateTime.now();
                        final startDate =
                            '${now.year}-${now.month.toString().padLeft(2, '0')}-${now.day.toString().padLeft(2, '0')}';
                        final allocationType = _vehicle!.tenantId != null ? 'tenant' : 'resident';
                        final charge = int.tryParse(_chargeCtrl.text.trim());
                        ref.read(parkingManagementProvider.notifier).createAllocation(
                              societyId: widget.societyId,
                              slotId: _slot!.id,
                              flatId: _flat!.id,
                              vehicleId: _vehicle!.id,
                              allocationType: allocationType,
                              startDate: startDate,
                              monthlyCharge: charge,
                            );
                        Navigator.pop(context);
                      },
              ),
            ],
          ),
        ),
      ),
    );
  }
}
