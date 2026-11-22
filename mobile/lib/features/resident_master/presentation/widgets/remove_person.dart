import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:ar_society_app/features/resident_master/data/repositories/resident_master_repository.dart';
import 'package:ar_society_app/features/resident_master/presentation/providers/resident_master_providers.dart';
import 'package:ar_society_app/features/society_structure/presentation/providers/structure_providers.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';
import 'package:ar_society_app/shared/widgets/confirm_remove.dart';

/// Remove a resident or tenant entered by mistake, after asking. The server refuses (with the reason) once the person
/// has bills, a move-out or other history; then Move out is the right action. Goes back to the list on success.
Future<void> removePerson(
  BuildContext context,
  WidgetRef ref, {
  required bool tenant,
  required String id,
  required String name,
  required String flatId,
}) async {
  final kind = tenant ? 'tenant' : 'resident';
  final ok = await confirmRemove(context,
      title: 'Remove $name?',
      message: 'Use this for a $kind entered by mistake: they are taken off the lists, along with their vehicles'
          '${tenant ? ' and agreement' : ''}, and their app login is switched off if it was never used. '
          'Someone who lived here should be moved out instead, which keeps the history.');
  if (!ok) return;
  final repo = ref.read(residentMasterRepositoryProvider);
  final result = tenant ? await repo.deleteTenant(id) : await repo.deleteResident(id);
  if (!context.mounted) return;
  switch (result) {
    case RmSuccess():
      if (tenant) {
        ref.read(tenantListProvider.notifier).refresh();
        ref.invalidate(tenantsByFlatProvider(flatId));
      } else {
        ref.read(residentListProvider.notifier).refresh();
        ref.invalidate(residentsByFlatProvider(flatId));
      }
      ref.invalidate(vehiclesByFlatProvider(flatId));
      ref.invalidate(flatHistoryProvider(flatId));
      ref.read(flatsBySocietyProvider.notifier).refresh();
      AppToast.success(context, '$name removed');
      context.pop();
    case RmFailure(:final message):
      AppToast.error(context, message);
  }
}
