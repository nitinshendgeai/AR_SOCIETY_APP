import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/layout/app_sheet.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/resident_master/data/models/resident_master_models.dart';
import 'package:ar_society_app/features/resident_master/presentation/providers/resident_master_providers.dart';
import 'package:ar_society_app/features/resident_master/presentation/widgets/resident_master_widgets.dart';
import 'package:ar_society_app/features/society_structure/presentation/providers/structure_providers.dart';
import 'package:ar_society_app/shared/widgets/app_form.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';

/// The owners a flat can be transferred to: its other active owners / co-owners who have not moved out.
List<ResidentModel> transferCandidates(List<ResidentModel> residents, ResidentModel from) => [
      for (final r in residents)
        if (r.id != from.id && r.isActive && r.moveOutDate == null &&
            (r.residentType == ResidentType.owner || r.residentType == ResidentType.coOwner))
          r
    ];

/// Record that [from] has transferred the flat to another owner already added on the flat. Calls
/// /occupancy/ownership-transfer: [from] moves out on the date, the new owner becomes primary, and the flat's history
/// gets an ownership-transfer entry. No accounts are changed; the Accounts Agent reviews dues, advances and the
/// transfer premium at the next scan.
Future<void> showOwnershipTransferSheet(BuildContext context, WidgetRef ref, {required ResidentModel from}) {
  return showAppSheet(
    context: context,
    constraints: const BoxConstraints(maxWidth: 520),
    builder: (_) => _TransferBody(from: from),
  );
}

class _TransferBody extends ConsumerStatefulWidget {
  final ResidentModel from;
  const _TransferBody({required this.from});
  @override
  ConsumerState<_TransferBody> createState() => _TransferBodyState();
}

class _TransferBodyState extends ConsumerState<_TransferBody> {
  DateTime _date = DateTime.now();
  String? _newOwner;
  final _cert = TextEditingController(), _deed = TextEditingController(), _notes = TextEditingController();
  bool _submitting = false;
  String? _error;

  @override
  void dispose() {
    _cert.dispose();
    _deed.dispose();
    _notes.dispose();
    super.dispose();
  }

  String get _dateStr => '${_date.year}-${_date.month.toString().padLeft(2, '0')}-${_date.day.toString().padLeft(2, '0')}';

  Future<void> _submit() async {
    if (_newOwner == null) {
      setState(() => _error = 'Choose the new owner');
      return;
    }
    setState(() { _submitting = true; _error = null; });
    await ref.read(occupancyActionProvider.notifier).ownershipTransfer(
        flatId: widget.from.flatId, fromResidentId: widget.from.id, newOwnerId: _newOwner!, transferDate: _dateStr,
        shareCertificateNo: _cert.text.trim(), deedReference: _deed.text.trim(), notes: _notes.text.trim());
    if (!mounted) return;
    final state = ref.read(occupancyActionProvider);
    if (state is OccupancyActionSuccess) {
      ref.invalidate(residentDetailProvider(widget.from.id));
      ref.invalidate(residentsByFlatProvider(widget.from.flatId));
      ref.invalidate(flatHistoryProvider(widget.from.flatId));
      ref.invalidate(vehiclesByFlatProvider(widget.from.flatId));
      ref.read(flatsBySocietyProvider.notifier).refresh();
      ref.read(occupancyActionProvider.notifier).reset();
      Navigator.of(context).pop();
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(
          content: Text(state.message), backgroundColor: AppTheme.success, behavior: SnackBarBehavior.floating));
    } else if (state is OccupancyActionError) {
      setState(() { _submitting = false; _error = rmFriendlyError(state.message); });
    } else {
      setState(() => _submitting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final residents = ref.watch(residentsByFlatProvider(widget.from.flatId));
    return AppSheetFrame(
      title: 'Transfer ownership — ${widget.from.fullName}',
      child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        const AppErrorBanner(
            message: 'The current owner moves out on the transfer date and their vehicles are unassigned. Add the new '
                'owner as a resident of this flat (type Owner) first.'),
        const SizedBox(height: 12),
        residents.when(
          loading: () => const LinearProgressIndicator(),
          error: (e, _) => AppErrorBanner(message: rmFriendlyError('$e')),
          data: (rows) {
            final options = transferCandidates(rows, widget.from);
            if (options.isEmpty) {
              return const AppErrorBanner(message: 'No other owner is recorded on this flat yet. Add the new owner first.');
            }
            return DropdownButtonFormField<String>(
              initialValue: _newOwner,
              isExpanded: true,
              decoration: const InputDecoration(labelText: 'New owner'),
              items: [for (final r in options) DropdownMenuItem(value: r.id, child: Text(r.fullName))],
              onChanged: (v) => setState(() => _newOwner = v),
            );
          },
        ),
        const SizedBox(height: 12),
        FormFieldBox(
          label: 'Transfer date',
          child: FormDateField(
            value: _date,
            hint: 'Select date',
            format: (d) => '${d.day}/${d.month}/${d.year}',
            onTap: () async {
              final p = await showDatePicker(context: context, initialDate: _date, firstDate: DateTime(2000), lastDate: DateTime.now());
              if (p != null) setState(() => _date = p);
            },
          ),
        ),
        TextField(controller: _cert, decoration: const InputDecoration(labelText: 'Share certificate no. (optional)')),
        TextField(controller: _deed, decoration: const InputDecoration(labelText: 'Deed / registration no. (optional)')),
        TextField(controller: _notes, maxLines: 2, decoration: const InputDecoration(labelText: 'Notes (optional)')),
        if (_error != null) ...[const SizedBox(height: 12), AppErrorBanner(message: _error!)],
        const SizedBox(height: 16),
        FilledButton(
          onPressed: _submitting ? null : _submit,
          child: _submitting
              ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2))
              : const Text('Record ownership transfer'),
        ),
      ]),
    );
  }
}
