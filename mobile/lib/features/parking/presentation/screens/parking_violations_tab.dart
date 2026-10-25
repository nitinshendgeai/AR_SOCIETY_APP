import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/layout/app_sheet.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/parking/data/parking_violations_api.dart';
import 'package:ar_society_app/features/society_structure/data/models/structure_models.dart';
import 'package:ar_society_app/features/society_structure/presentation/providers/structure_providers.dart';
import 'package:ar_society_app/shared/widgets/app_data_table.dart' show StatusPill;
import 'package:ar_society_app/shared/widgets/app_form.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';

Color _fineColor(FineStatus s) => switch (s) {
      FineStatus.active => AppTheme.warning,
      FineStatus.billed => AppTheme.primary,
      FineStatus.cancelled => AppTheme.textSecondary,
      FineStatus.none => AppTheme.textSecondary,
    };

/// Record a violation (optionally with a fine) from the Violations tab.
Future<void> showReportViolation(BuildContext context, WidgetRef ref, String societyId) async {
  final ok = await showAppSheet<bool>(context: context, builder: (_) => ReportViolationSheet(societyId: societyId));
  if (ok == true) ref.invalidate(parkingViolationsProvider);
}

/// Parking violations and where each fine stands: a fine is charged to the flat and goes on its next maintenance
/// bill as a fine (Fines & Penalties); it can be waived until it has been billed.
class ViolationsTab extends ConsumerWidget {
  final String societyId;
  const ViolationsTab({super.key, required this.societyId});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final async = ref.watch(parkingViolationsProvider(societyId));
    return async.when(
      loading: () => const Center(child: CircularProgressIndicator()),
      error: (e, _) => Center(child: Padding(padding: const EdgeInsets.all(24), child: Text('Could not load violations: $e'))),
      data: (rows) => rows.isEmpty
          ? const Center(child: Text('No violations recorded'))
          : RefreshIndicator(
              onRefresh: () async => ref.invalidate(parkingViolationsProvider(societyId)),
              child: ListView(
                padding: const EdgeInsets.all(16),
                children: [for (final v in rows) ViolationCard(violation: v, societyId: societyId)],
              ),
            ),
    );
  }
}

class ViolationCard extends ConsumerStatefulWidget {
  final ViolationItem violation;
  final String societyId;
  const ViolationCard({super.key, required this.violation, required this.societyId});

  @override
  ConsumerState<ViolationCard> createState() => _ViolationCardState();
}

class _ViolationCardState extends ConsumerState<ViolationCard> {
  bool _busy = false;

  Future<void> _run(Future<void> Function() action, String done) async {
    setState(() => _busy = true);
    try {
      await action();
      ref.invalidate(parkingViolationsProvider);
      if (mounted) AppToast.success(context, done);
    } catch (e) {
      if (mounted) showErrorToast(context, e);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _charge() async {
    final v = widget.violation;
    final r = await showAppSheet<ChargeFineEntry>(context: context, builder: (_) => ChargeFineSheet(violation: v));
    if (r == null) return;
    await _run(() => ref.read(parkingViolationsApiProvider).chargeFine(v.id, flatId: r.flatId, amount: r.amount),
        'Fine added to the flat\'s next bill');
  }

  Future<void> _waive() async {
    final v = widget.violation;
    final reason = await showAppSheet<String>(
        context: context,
        builder: (_) => const _WaiveSheet());
    if (reason == null) return;
    await _run(() => ref.read(parkingViolationsApiProvider).waiveFine(v.id, reason), 'Fine waived');
  }

  @override
  Widget build(BuildContext context) {
    final v = widget.violation;
    return Card(
      margin: const EdgeInsets.only(bottom: 10),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            Expanded(child: Text(v.vehicleNumber, style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 16))),
            if (v.hasFine || v.fine != FineStatus.none) StatusPill(v.fine.label, _fineColor(v.fine)),
          ]),
          const SizedBox(height: 2),
          Text(violationTypeLabel(v.type), style: const TextStyle(fontWeight: FontWeight.w600)),
          if ((v.description ?? '').isNotEmpty) Text(v.description!, style: const TextStyle(fontSize: 13)),
          if (v.hasFine)
            Padding(
              padding: const EdgeInsets.only(top: 2),
              child: Text('Fine ₹${v.fineAmount}', style: const TextStyle(fontSize: 12.5, color: AppTheme.textSecondary)),
            ),
          if (v.canCharge || v.canWaive) ...[
            const SizedBox(height: 10),
            Wrap(spacing: 8, runSpacing: 8, children: [
              if (v.canCharge)
                FilledButton.icon(
                  onPressed: _busy ? null : _charge,
                  icon: const Icon(Icons.request_quote_outlined, size: 18),
                  label: Text(v.fine == FineStatus.cancelled ? 'Charge fine again' : 'Charge fine to flat'),
                ),
              if (v.canWaive)
                OutlinedButton.icon(
                  onPressed: _busy ? null : _waive,
                  icon: const Icon(Icons.money_off_rounded, size: 18),
                  label: const Text('Waive fine'),
                ),
            ]),
          ],
        ]),
      ),
    );
  }
}

typedef ChargeFineEntry = ({String? flatId, int? amount});

/// Charge a violation's fine to a flat. The flat defaults to the one the vehicle is registered to; pick one when the
/// vehicle is not registered. An amount is asked for only when the violation was recorded without a fine.
class ChargeFineSheet extends ConsumerStatefulWidget {
  final ViolationItem violation;
  const ChargeFineSheet({super.key, required this.violation});

  @override
  ConsumerState<ChargeFineSheet> createState() => _ChargeFineSheetState();
}

class _ChargeFineSheetState extends ConsumerState<ChargeFineSheet> {
  final _form = GlobalKey<FormState>();
  final _amount = TextEditingController();
  FlatModel? _flat;

  @override
  void dispose() {
    _amount.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final v = widget.violation;
    final flats = ref.watch(flatsBySocietyProvider);
    return AppSheetFrame(
      title: 'Charge the fine to a flat',
      subtitle: '${v.vehicleNumber} · ${violationTypeLabel(v.type)}',
      child: Form(
        key: _form,
        child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          flats.when(
            loading: () => const LinearProgressIndicator(),
            error: (e, _) => Text('Could not load flats: $e'),
            data: (all) => FormFieldBox(
              label: 'Flat',
              child: DropdownButtonFormField<FlatModel?>(
                initialValue: _flat,
                isExpanded: true,
                decoration: const InputDecoration(helperText: 'Leave as is to use the flat the vehicle is registered to'),
                items: [
                  const DropdownMenuItem<FlatModel?>(value: null, child: Text('The vehicle\'s registered flat')),
                  for (final f in all) DropdownMenuItem<FlatModel?>(value: f, child: Text('${f.wingName ?? ''} — ${f.flatNumber}')),
                ],
                onChanged: (f) => setState(() => _flat = f),
              ),
            ),
          ),
          if (!v.hasFine)
            FormFieldBox(
              label: 'Fine amount',
              required: true,
              child: TextFormField(
                controller: _amount,
                keyboardType: TextInputType.number,
                inputFormatters: [FilteringTextInputFormatter.digitsOnly, LengthLimitingTextInputFormatter(7)],
                decoration: const InputDecoration(prefixText: '₹ '),
                validator: (t) => (int.tryParse(t ?? '') ?? 0) <= 0 ? 'Enter the fine' : null,
              ),
            )
          else
            Padding(
              padding: const EdgeInsets.only(bottom: 12),
              child: Text('Fine ₹${v.fineAmount} goes on the flat\'s next maintenance bill.',
                  style: const TextStyle(fontWeight: FontWeight.w600)),
            ),
          FilledButton(
            onPressed: () {
              if (!_form.currentState!.validate()) return;
              Navigator.of(context).pop<ChargeFineEntry>((flatId: _flat?.id, amount: v.hasFine ? null : int.parse(_amount.text)));
            },
            child: const Text('Charge fine'),
          ),
        ]),
      ),
    );
  }
}

class _WaiveSheet extends StatefulWidget {
  const _WaiveSheet();

  @override
  State<_WaiveSheet> createState() => _WaiveSheetState();
}

class _WaiveSheetState extends State<_WaiveSheet> {
  final _form = GlobalKey<FormState>();
  final _reason = TextEditingController();

  @override
  void dispose() {
    _reason.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => AppSheetFrame(
        title: 'Waive this fine',
        subtitle: 'It comes off the flat\'s next bill. Not possible once it has been billed.',
        child: Form(
          key: _form,
          child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
            FormFieldBox(
              label: 'Why',
              required: true,
              child: TextFormField(
                controller: _reason,
                minLines: 2,
                maxLines: 4,
                textCapitalization: TextCapitalization.sentences,
                decoration: const InputDecoration(alignLabelWithHint: true),
                validator: (t) => (t ?? '').trim().length < 3 ? 'Say why (at least 3 letters)' : null,
              ),
            ),
            const SizedBox(height: 14),
            FilledButton(
              onPressed: () {
                if (_form.currentState!.validate()) Navigator.of(context).pop(_reason.text.trim());
              },
              child: const Text('Waive fine'),
            ),
          ]),
        ),
      );
}

/// Record a violation. A fine entered here is charged straight away when the vehicle is registered to a flat.
class ReportViolationSheet extends ConsumerStatefulWidget {
  final String societyId;
  const ReportViolationSheet({super.key, required this.societyId});

  @override
  ConsumerState<ReportViolationSheet> createState() => _ReportViolationSheetState();
}

class _ReportViolationSheetState extends ConsumerState<ReportViolationSheet> {
  final _form = GlobalKey<FormState>();
  final _vehicle = TextEditingController();
  final _notes = TextEditingController();
  final _fine = TextEditingController();
  String _type = kViolationTypes.first.$1;
  bool _busy = false;

  @override
  void dispose() {
    _vehicle.dispose();
    _notes.dispose();
    _fine.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    if (!_form.currentState!.validate()) return;
    setState(() => _busy = true);
    try {
      final saved = await ref.read(parkingViolationsApiProvider).report(
            societyId: widget.societyId,
            vehicleNumber: _vehicle.text.trim(),
            type: _type,
            description: _notes.text.trim(),
            fineAmount: int.tryParse(_fine.text.trim()),
          );
      if (!mounted) return;
      AppToast.success(
          context,
          saved.fine == FineStatus.active
              ? 'Recorded; the fine is on the flat\'s next bill'
              : 'Violation recorded');
      Navigator.of(context).pop(true);
    } catch (e) {
      if (mounted) {
        setState(() => _busy = false);
        showErrorToast(context, e);
      }
    }
  }

  @override
  Widget build(BuildContext context) => AppSheetFrame(
        title: 'Report a violation',
        child: Form(
          key: _form,
          child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
            FormFieldBox(
              label: 'Vehicle number',
              required: true,
              child: TextFormField(
                controller: _vehicle,
                textCapitalization: TextCapitalization.characters,
                inputFormatters: [LengthLimitingTextInputFormatter(20)],
                validator: (t) => (t ?? '').trim().isEmpty ? 'Enter the vehicle number' : null,
              ),
            ),
            FormFieldBox(
              label: 'What happened',
              child: DropdownButtonFormField<String>(
                initialValue: _type,
                isExpanded: true,
                items: [for (final t in kViolationTypes) DropdownMenuItem(value: t.$1, child: Text(t.$2))],
                onChanged: (v) => setState(() => _type = v!),
              ),
            ),
            FormFieldBox(
              label: 'Notes (optional)',
              child: TextFormField(controller: _notes, minLines: 2, maxLines: 3, decoration: const InputDecoration(alignLabelWithHint: true)),
            ),
            FormFieldBox(
              label: 'Fine (optional)',
              child: TextFormField(
                controller: _fine,
                keyboardType: TextInputType.number,
                inputFormatters: [FilteringTextInputFormatter.digitsOnly, LengthLimitingTextInputFormatter(7)],
                decoration: const InputDecoration(prefixText: '₹ ', helperText: 'Charged to the vehicle\'s flat on its next bill'),
              ),
            ),
            const SizedBox(height: 8),
            FilledButton(onPressed: _busy ? null : _save, child: const Text('Record violation')),
          ]),
        ),
      );
}
