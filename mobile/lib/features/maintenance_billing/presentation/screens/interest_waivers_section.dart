import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/layout/app_sheet.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/features/maintenance_billing/data/maintenance_billing_api.dart';
import 'package:ar_society_app/features/maintenance_billing/presentation/providers/maintenance_billing_providers.dart';
import 'package:ar_society_app/features/maintenance_billing/presentation/widgets/billing_sheet_frame.dart';
import 'package:ar_society_app/features/society_structure/data/models/structure_models.dart';
import 'package:ar_society_app/features/society_structure/presentation/providers/structure_providers.dart';
import 'package:ar_society_app/shared/widgets/app_form.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';

/// Interest concessions on the Fines & Charges tab: the committee waives the
/// interest on one flat's arrears, or charges a lower rate, for a stretch of
/// days, with a reason. It applies from the flat's next bill. Everyone who
/// manages billing sees the list; only the committee or admin can add or
/// cancel one.
class InterestWaiversSection extends ConsumerWidget {
  final String societyId;
  const InterestWaiversSection({super.key, required this.societyId});

  Future<void> _cancel(BuildContext context, WidgetRef ref, InterestWaiver w) async {
    final reason = TextEditingController();
    final formKey = GlobalKey<FormState>();
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Cancel this concession?'),
        content: Form(
          key: formKey,
          child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text('${w.title} on ${w.flatLabel} will stop applying from the next bill.'),
            const SizedBox(height: 12),
            FormFieldBox(label: 'Reason', required: true, child: TextFormField(
              controller: reason,
              maxLength: 1000,
              maxLines: 2,
              decoration: const InputDecoration(),
              validator: (v) => (v ?? '').trim().isEmpty ? 'Enter the reason' : null,
            )),
          ]),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Keep')),
          TextButton(
            onPressed: () {
              if (formKey.currentState!.validate()) Navigator.pop(ctx, true);
            },
            style: TextButton.styleFrom(foregroundColor: AppTheme.error),
            child: const Text('Cancel it'),
          ),
        ],
      ),
    );
    final text = reason.text.trim();
    reason.dispose();
    if (ok != true) return;
    try {
      await ref.read(maintenanceBillingApiProvider).cancelInterestWaiver(w.id, text);
      ref.invalidate(interestWaiversProvider(societyId));
      if (context.mounted) AppToast.success(context, 'Cancelled');
    } catch (e) {
      if (context.mounted) showErrorToast(context, e);
    }
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final canEdit = ref.watch(currentUserProvider)?.isAdminOrCommittee ?? false;
    final async = ref.watch(interestWaiversProvider(societyId));
    return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      const Divider(height: 32),
      Row(children: [
        const Expanded(
          child: Text('Interest concessions', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700)),
        ),
        if (canEdit)
          OutlinedButton.icon(
            onPressed: () => showAppSheet(context: context, builder: (_) => _WaiverSheet(societyId: societyId)),
            icon: const Icon(Icons.percent_rounded, size: 18),
            label: const Text('Waive interest'),
          ),
      ]),
      const SizedBox(height: 6),
      const Text(
        'Waive the interest on one flat\'s arrears, or charge a lower rate, for a stretch of days. '
        'It applies from that flat\'s next bill; bills already issued don\'t change.',
        style: TextStyle(fontSize: 12, color: AppTheme.textSecondary),
      ),
      const SizedBox(height: 12),
      async.when(
        loading: () => const Padding(padding: EdgeInsets.all(16), child: LinearProgressIndicator()),
        error: (e, _) => Text(friendlyErrorMessage(e), style: const TextStyle(color: AppTheme.error)),
        data: (list) => list.isEmpty
            ? const Padding(
                padding: EdgeInsets.symmetric(vertical: 12),
                child: Text('No interest concessions'),
              )
            : Column(children: [
                for (final w in list)
                  Card(
                    margin: const EdgeInsets.only(bottom: 8),
                    child: ListTile(
                      leading: Icon(w.mode == 'waive' ? Icons.money_off_rounded : Icons.percent_rounded,
                          color: AppTheme.primary),
                      title: Text('${w.title} · ${w.flatLabel}', style: const TextStyle(fontWeight: FontWeight.w600)),
                      subtitle: Text('From ${formatBillDate(w.from)}'
                          '${w.to != null ? ' to ${formatBillDate(w.to!)}' : ' · until cancelled'}\n${w.reason}',
                          maxLines: 3, overflow: TextOverflow.ellipsis),
                      isThreeLine: true,
                      trailing: canEdit
                          ? IconButton(
                              tooltip: 'Cancel',
                              icon: const Icon(Icons.close_rounded),
                              onPressed: () => _cancel(context, ref, w),
                            )
                          : null,
                    ),
                  ),
              ]),
      ),
    ]);
  }
}

class _WaiverSheet extends ConsumerStatefulWidget {
  final String societyId;
  const _WaiverSheet({required this.societyId});

  @override
  ConsumerState<_WaiverSheet> createState() => _WaiverSheetState();
}

class _WaiverSheetState extends ConsumerState<_WaiverSheet> {
  final _formKey = GlobalKey<FormState>();
  final _rate = TextEditingController();
  final _reason = TextEditingController();
  FlatModel? _flat;
  String _mode = 'waive';
  DateTime _from = DateTime.now();
  DateTime? _to;
  bool _saving = false;

  @override
  void dispose() {
    _rate.dispose();
    _reason.dispose();
    super.dispose();
  }

  Future<void> _pick(DateTime initial, ValueChanged<DateTime> done) async {
    final d = await showDatePicker(
      context: context,
      initialDate: initial,
      firstDate: DateTime(2000),
      lastDate: DateTime(2100),
    );
    if (d != null) setState(() => done(d));
  }

  Future<void> _save() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() => _saving = true);
    try {
      await ref.read(maintenanceBillingApiProvider).createInterestWaiver(
            societyId: widget.societyId,
            flatId: _flat!.id,
            mode: _mode,
            ratePct: _mode == 'rate' ? _rate.text.trim() : null,
            from: _from,
            to: _to,
            reason: _reason.text.trim(),
          );
      ref.invalidate(interestWaiversProvider(widget.societyId));
      if (mounted) {
        AppToast.success(context, 'Interest concession added');
        Navigator.pop(context);
      }
    } catch (e) {
      if (mounted) showErrorToast(context, e);
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final flats = ref.watch(flatsBySocietyProvider);
    return BillingSheetFrame(
      title: 'Waive Interest',
      child: Form(
        key: _formKey,
        child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          flats.when(
            loading: () => const LinearProgressIndicator(),
            error: (e, _) => Text(friendlyErrorMessage(e), style: const TextStyle(color: AppTheme.error)),
            data: (list) => FormFieldBox(label: 'Flat', required: true, child: DropdownButtonFormField<FlatModel>(
              initialValue: _flat,
              isExpanded: true,
              decoration: const InputDecoration(),
              items: [
                for (final f in list.where((f) => f.isActive))
                  DropdownMenuItem(value: f, child: Text('${f.wingName ?? ''} / ${f.flatNumber}')),
              ],
              onChanged: (f) => setState(() => _flat = f),
              validator: (v) => v == null ? 'Choose the flat' : null,
            )),
          ),
          const SizedBox(height: 14),
          SegmentedButton<String>(
            segments: const [
              ButtonSegment(value: 'waive', label: Text('No interest'), icon: Icon(Icons.money_off_rounded)),
              ButtonSegment(value: 'rate', label: Text('Lower rate'), icon: Icon(Icons.percent_rounded)),
            ],
            selected: {_mode},
            onSelectionChanged: (s) => setState(() => _mode = s.first),
          ),
          if (_mode == 'rate') ...[
            const SizedBox(height: 14),
            FormFieldBox(label: 'Charge instead (% a year)', required: true, child: TextFormField(
              controller: _rate,
              keyboardType: const TextInputType.numberWithOptions(decimal: true),
              inputFormatters: [FilteringTextInputFormatter.allow(RegExp(r'^\d{0,2}(\.\d{0,2})?'))],
              decoration: const InputDecoration(helperText: 'Up to 21%, the legal ceiling'),
              validator: (v) {
                final n = double.tryParse((v ?? '').trim());
                return n == null || n < 0 || n > 21 ? 'Enter 0 to 21' : null;
              },
            )),
          ],
          const SizedBox(height: 14),
          InkWell(
            onTap: () => _pick(_from, (d) {
              _from = d;
              if (_to != null && _to!.isBefore(d)) _to = null;
            }),
            child: FormFieldBox(label: 'For the days from', child: InputDecorator(
              decoration: const InputDecoration(suffixIcon: Icon(Icons.calendar_today_rounded, size: 18)),
              child: Text(formatBillDate(_from)),
            )),
          ),
          const SizedBox(height: 14),
          InkWell(
            onTap: () => _pick(_to ?? _from, (d) => _to = d.isBefore(_from) ? _from : d),
            child: FormFieldBox(label: 'Until (optional)', child: InputDecorator(
              decoration: InputDecoration(
                suffixIcon: _to == null
                    ? const Icon(Icons.calendar_today_rounded, size: 18)
                    : IconButton(
                        icon: const Icon(Icons.close_rounded, size: 18), onPressed: () => setState(() => _to = null)),
              ),
              child: Text(_to == null ? 'Until cancelled' : formatBillDate(_to!)),
            )),
          ),
          const SizedBox(height: 14),
          FormFieldBox(label: 'Reason', required: true, child: TextFormField(
            controller: _reason,
            maxLength: 1000,
            maxLines: 3,
            decoration: const InputDecoration(helperText: 'Kept on record with your name'),
            validator: (v) => (v ?? '').trim().isEmpty ? 'Enter the reason' : null,
          )),
          const SizedBox(height: 20),
          ElevatedButton(
            onPressed: _saving ? null : _save,
            child: _saving
                ? const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2))
                : const Text('Save'),
          ),
        ]),
      ),
    );
  }
}
