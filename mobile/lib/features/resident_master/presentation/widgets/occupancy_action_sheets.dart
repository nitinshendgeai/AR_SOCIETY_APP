import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/resident_master/data/models/resident_master_models.dart';
import 'package:ar_society_app/features/resident_master/presentation/providers/resident_master_providers.dart';
import 'package:ar_society_app/features/resident_master/presentation/widgets/resident_master_widgets.dart';
import 'package:ar_society_app/features/society_structure/presentation/providers/structure_providers.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';

// ── Canonical occupancy move-in / move-out actions ──────────────────────────
//
// These are the ONLY UI entry points that change Flat.occupancy_status —
// they always call the /occupancy/* endpoints via OccupancyService, never a
// direct Flat PATCH (see Phase M1.3 §5 / M1.4 §5: the Flat Edit form's
// occupancy_status control has been removed for exactly this reason).

Future<void> showResidentMoveInSheet(BuildContext context, WidgetRef ref, {required ResidentModel resident}) {
  return _showMoveSheet(
    context, ref,
    title: 'Move In — ${resident.fullName}',
    confirmLabel: 'Confirm Move In',
    confirmColor: AppTheme.success,
    onConfirm: (date) => ref.read(occupancyActionProvider.notifier)
        .residentMoveIn(resident.flatId, resident.id, date),
    onSettled: () {
      ref.invalidate(residentDetailProvider(resident.id));
      ref.invalidate(flatHistoryProvider(resident.flatId));
      ref.read(flatsBySocietyProvider.notifier).refresh();
    },
  );
}

Future<void> showResidentMoveOutSheet(BuildContext context, WidgetRef ref, {required ResidentModel resident}) {
  return _showMoveSheet(
    context, ref,
    title: 'Move Out — ${resident.fullName}',
    confirmLabel: 'Confirm Move Out',
    confirmColor: AppTheme.error,
    warning: 'This deactivates the resident record and unassigns their vehicles from this flat.',
    onConfirm: (date) => ref.read(occupancyActionProvider.notifier)
        .residentMoveOut(resident.flatId, resident.id, date),
    onSettled: () {
      ref.invalidate(residentDetailProvider(resident.id));
      ref.invalidate(residentsByFlatProvider(resident.flatId));
      ref.invalidate(flatHistoryProvider(resident.flatId));
      ref.invalidate(vehiclesByFlatProvider(resident.flatId));
      ref.read(flatsBySocietyProvider.notifier).refresh();
    },
  );
}

Future<void> showTenantMoveInSheet(BuildContext context, WidgetRef ref, {required TenantModel tenant}) {
  return _showMoveSheet(
    context, ref,
    title: 'Move In — ${tenant.fullName}',
    confirmLabel: 'Confirm Move In',
    confirmColor: AppTheme.success,
    warning: tenant.agreementStartDate != null
        ? 'This will also activate the agreement on file for this tenant.'
        : null,
    onConfirm: (date) => ref.read(occupancyActionProvider.notifier)
        .tenantMoveIn(tenant.flatId, tenant.id, date),
    onSettled: () {
      ref.invalidate(tenantDetailProvider(tenant.id));
      ref.invalidate(tenantAgreementsProvider(tenant.id));
      ref.invalidate(flatHistoryProvider(tenant.flatId));
      ref.read(flatsBySocietyProvider.notifier).refresh();
    },
  );
}

Future<void> showTenantMoveOutSheet(BuildContext context, WidgetRef ref, {required TenantModel tenant}) {
  return _showMoveSheet(
    context, ref,
    title: 'Move Out — ${tenant.fullName}',
    confirmLabel: 'Confirm Move Out',
    confirmColor: AppTheme.error,
    warning: 'This deactivates the tenant, terminates their active agreement, and unassigns their vehicles.',
    onConfirm: (date) => ref.read(occupancyActionProvider.notifier)
        .tenantMoveOut(tenant.flatId, tenant.id, date),
    onSettled: () {
      ref.invalidate(tenantDetailProvider(tenant.id));
      ref.invalidate(tenantAgreementsProvider(tenant.id));
      ref.invalidate(flatHistoryProvider(tenant.flatId));
      ref.invalidate(vehiclesByFlatProvider(tenant.flatId));
      ref.read(flatsBySocietyProvider.notifier).refresh();
    },
  );
}

Future<void> _showMoveSheet(
  BuildContext context,
  WidgetRef ref, {
  required String title,
  required String confirmLabel,
  required Color confirmColor,
  required Future<void> Function(String date) onConfirm,
  required VoidCallback onSettled,
  String? warning,
}) {
  return showModalBottomSheet(
    context: context,
    isScrollControlled: true,
    backgroundColor: Colors.transparent,
    builder: (ctx) => _MoveSheetBody(
      title: title,
      confirmLabel: confirmLabel,
      confirmColor: confirmColor,
      warning: warning,
      onConfirm: onConfirm,
      onSettled: onSettled,
    ),
  );
}

class _MoveSheetBody extends ConsumerStatefulWidget {
  final String title;
  final String confirmLabel;
  final Color confirmColor;
  final String? warning;
  final Future<void> Function(String date) onConfirm;
  final VoidCallback onSettled;

  const _MoveSheetBody({
    required this.title,
    required this.confirmLabel,
    required this.confirmColor,
    this.warning,
    required this.onConfirm,
    required this.onSettled,
  });

  @override
  ConsumerState<_MoveSheetBody> createState() => _MoveSheetBodyState();
}

class _MoveSheetBodyState extends ConsumerState<_MoveSheetBody> {
  DateTime _date = DateTime.now();
  bool _submitting = false;
  String? _error;

  String get _dateStr =>
      '${_date.year}-${_date.month.toString().padLeft(2, '0')}-${_date.day.toString().padLeft(2, '0')}';

  Future<void> _pickDate() async {
    final picked = await showDatePicker(
      context: context,
      initialDate: _date,
      firstDate: DateTime(2000),
      lastDate: DateTime.now().add(const Duration(days: 365)),
    );
    if (picked != null) setState(() => _date = picked);
  }

  Future<void> _submit() async {
    setState(() { _submitting = true; _error = null; });
    await widget.onConfirm(_dateStr);
    if (!mounted) return;
    final state = ref.read(occupancyActionProvider);
    if (state is OccupancyActionSuccess) {
      widget.onSettled();
      ref.read(occupancyActionProvider.notifier).reset();
      Navigator.of(context).pop();
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(
        content: Text(state.message), backgroundColor: AppTheme.success,
        behavior: SnackBarBehavior.floating,
      ));
    } else if (state is OccupancyActionError) {
      setState(() { _submitting = false; _error = rmFriendlyError(state.message); });
    } else {
      setState(() => _submitting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: EdgeInsets.only(bottom: MediaQuery.of(context).viewInsets.bottom),
      child: Container(
        padding: const EdgeInsets.fromLTRB(20, 20, 20, 28),
        decoration: const BoxDecoration(
          color: AppTheme.cardBg,
          borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Center(
              child: Container(
                width: 40, height: 4, margin: const EdgeInsets.only(bottom: 16),
                decoration: BoxDecoration(color: AppTheme.border, borderRadius: BorderRadius.circular(2)),
              ),
            ),
            Text(widget.title, style: const TextStyle(fontSize: 17, fontWeight: FontWeight.w700, color: AppTheme.textPrimary)),
            const SizedBox(height: 16),
            if (widget.warning != null) ...[
              AppErrorBanner(message: widget.warning!),
              const SizedBox(height: 8),
            ],
            const Text('Effective Date', style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: AppTheme.textSecondary)),
            const SizedBox(height: 6),
            InkWell(
              onTap: _pickDate,
              borderRadius: BorderRadius.circular(12),
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 14),
                decoration: BoxDecoration(
                  color: AppTheme.surface, borderRadius: BorderRadius.circular(12),
                  border: Border.all(color: AppTheme.border),
                ),
                child: Row(children: [
                  const Icon(Icons.calendar_today_rounded, size: 18, color: AppTheme.primary),
                  const SizedBox(width: 10),
                  Text('${_date.day}/${_date.month}/${_date.year}', style: const TextStyle(fontSize: 14)),
                ]),
              ),
            ),
            if (_error != null) ...[
              const SizedBox(height: 12),
              AppErrorBanner(message: _error!),
            ],
            const SizedBox(height: 20),
            AppPrimaryButton(
              label: widget.confirmLabel,
              isLoading: _submitting,
              onPressed: _submit,
            ),
          ],
        ),
      ),
    );
  }
}
