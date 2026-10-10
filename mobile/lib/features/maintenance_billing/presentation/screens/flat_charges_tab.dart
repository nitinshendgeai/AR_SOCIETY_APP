import 'package:flutter/material.dart';
import 'package:ar_society_app/core/motion/loading.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/layout/app_sheet.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/maintenance_billing/data/maintenance_billing_api.dart';
import 'package:ar_society_app/features/maintenance_billing/presentation/providers/maintenance_billing_providers.dart';
import 'package:ar_society_app/features/maintenance_billing/presentation/widgets/billing_sheet_frame.dart';
import 'package:ar_society_app/features/society_structure/data/models/structure_models.dart';
import 'package:ar_society_app/features/society_structure/presentation/providers/structure_providers.dart';
import 'package:ar_society_app/shared/widgets/app_data_table.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';

/// Opens the form to add a fine or an additional charge on one flat.
void showFlatChargeSheet(BuildContext context, String societyId) => showAppSheet(
      context: context,
      builder: (_) => _FlatChargeSheet(societyId: societyId),
    );

/// Fines and additional charges on individual flats. Each goes on the flat's
/// next maintenance bill (a recurring one on every bill until it ends), and
/// the flat's members are told when one is added. One that is still waiting
/// can be cancelled; one already on a bill goes when that bill is cancelled.
class FlatChargesTab extends ConsumerWidget {
  final String societyId;
  const FlatChargesTab({super.key, required this.societyId});

  Future<void> _cancel(BuildContext context, WidgetRef ref, FlatCharge c) async {
    final reason = TextEditingController();
    final formKey = GlobalKey<FormState>();
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text('Cancel ${c.isFine ? 'fine' : 'charge'}?'),
        content: Form(
          key: formKey,
          child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text('"${c.title}" (${formatRupees(c.amount)}) on ${c.flatLabel} won\'t be billed.'),
            const SizedBox(height: 12),
            TextFormField(
              controller: reason,
              maxLength: 1000,
              maxLines: 2,
              decoration: const InputDecoration(labelText: 'Reason *'),
              validator: (v) => (v ?? '').trim().isEmpty ? 'Enter the reason' : null,
            ),
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
      await ref.read(maintenanceBillingApiProvider).cancelFlatCharge(c.id, text);
      ref.invalidate(flatChargesProvider(societyId));
      if (context.mounted) AppToast.success(context, 'Cancelled');
    } catch (e) {
      if (context.mounted) showErrorToast(context, e);
    }
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final async = ref.watch(flatChargesProvider(societyId));
    return RefreshIndicator(
      onRefresh: () async => ref.invalidate(flatChargesProvider(societyId)),
      child: async.when(
        loading: () => const AppLoader(),
        error: (e, _) => ListView(children: [
          Padding(
            padding: const EdgeInsets.all(24),
            child: Text(friendlyErrorMessage(e), style: const TextStyle(color: AppTheme.error)),
          ),
        ]),
        data: (all) {
          final charges = all.where((c) => c.status != 'cancelled').toList();
          return ResponsiveBody(
            maxWidth: 800,
            child: ListView(
              padding: const EdgeInsets.fromLTRB(16, 16, 16, 96),
              children: [
                const Text(
                  'A fine or an extra charge on one flat goes on its next maintenance bill, with the reason. '
                  'Use it for things like parking violations, damage to common property or a member\'s own '
                  'additional charges.',
                  style: TextStyle(fontSize: 12, color: AppTheme.textSecondary),
                ),
                const SizedBox(height: 12),
                if (charges.isEmpty)
                  const Padding(
                    padding: EdgeInsets.symmetric(vertical: 40),
                    child: Center(child: Text('No fines or additional charges yet')),
                  ),
                for (final c in charges)
                  Card(
                    margin: const EdgeInsets.only(bottom: 8),
                    child: ListTile(
                      leading: Icon(c.isFine ? Icons.gavel_rounded : Icons.add_card_rounded,
                          color: c.isFine ? AppTheme.error : AppTheme.primary),
                      title: Text('${c.title} · ${formatRupees(c.amount)}',
                          style: const TextStyle(fontWeight: FontWeight.w600)),
                      subtitle: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                        Text('${c.flatLabel} · from ${formatBillDate(c.effectiveDate)}'
                            '${c.recurring ? (c.endDate != null ? ' to ${formatBillDate(c.endDate!)}' : ' · every month') : ''}'),
                        if (c.reason != null && c.reason!.isNotEmpty)
                          Text(c.reason!, maxLines: 2, overflow: TextOverflow.ellipsis),
                        const SizedBox(height: 4),
                        StatusPill(c.statusLabel, c.status == 'billed' ? AppTheme.success : AppTheme.warning),
                      ]),
                      isThreeLine: true,
                      trailing: c.canCancel
                          ? IconButton(
                              tooltip: 'Cancel',
                              icon: const Icon(Icons.close_rounded),
                              onPressed: () => _cancel(context, ref, c),
                            )
                          : null,
                    ),
                  ),
              ],
            ),
          );
        },
      ),
    );
  }
}

class _FlatChargeSheet extends ConsumerStatefulWidget {
  final String societyId;
  const _FlatChargeSheet({required this.societyId});

  @override
  ConsumerState<_FlatChargeSheet> createState() => _FlatChargeSheetState();
}

class _FlatChargeSheetState extends ConsumerState<_FlatChargeSheet> {
  final _formKey = GlobalKey<FormState>();
  final _title = TextEditingController();
  final _amount = TextEditingController();
  final _reason = TextEditingController();
  FlatModel? _flat;
  String _kind = 'fine';
  bool _gst = false;
  bool _recurring = false;
  DateTime _from = DateTime.now();
  DateTime? _to;
  bool _saving = false;

  @override
  void dispose() {
    _title.dispose();
    _amount.dispose();
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
      await ref.read(maintenanceBillingApiProvider).createFlatCharge(
            societyId: widget.societyId,
            flatId: _flat!.id,
            kind: _kind,
            title: _title.text.trim(),
            reason: _reason.text.trim(),
            amount: (double.parse(_amount.text.trim())).toStringAsFixed(2),
            gstApplicable: _kind == 'extra' && _gst,
            effectiveDate: _from,
            recurring: _recurring,
            endDate: _to,
          );
      ref.invalidate(flatChargesProvider(widget.societyId));
      if (mounted) {
        AppToast.success(context, _kind == 'fine' ? 'Fine added' : 'Charge added');
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
      title: 'Add Fine / Extra Charge',
      child: Form(
        key: _formKey,
        child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          SegmentedButton<String>(
            segments: const [
              ButtonSegment(value: 'fine', label: Text('Fine'), icon: Icon(Icons.gavel_rounded)),
              ButtonSegment(value: 'extra', label: Text('Extra charge'), icon: Icon(Icons.add_card_rounded)),
            ],
            selected: {_kind},
            onSelectionChanged: (s) => setState(() => _kind = s.first),
          ),
          const SizedBox(height: 14),
          flats.when(
            loading: () => const LinearProgressIndicator(),
            error: (e, _) => Text(friendlyErrorMessage(e), style: const TextStyle(color: AppTheme.error)),
            data: (list) => DropdownButtonFormField<FlatModel>(
              initialValue: _flat,
              isExpanded: true,
              decoration: const InputDecoration(labelText: 'Flat *'),
              items: [
                for (final f in list.where((f) => f.isActive))
                  DropdownMenuItem(value: f, child: Text('${f.wingName ?? ''} / ${f.flatNumber}')),
              ],
              onChanged: (f) => setState(() => _flat = f),
              validator: (v) => v == null ? 'Choose the flat' : null,
            ),
          ),
          const SizedBox(height: 14),
          TextFormField(
            controller: _title,
            maxLength: 150,
            decoration: InputDecoration(
              labelText: 'What is it for? *',
              hintText: _kind == 'fine' ? 'e.g. Parked in visitor bay' : 'e.g. Club house fee',
              counterText: '',
            ),
            validator: (v) => (v ?? '').trim().isEmpty ? 'Required' : null,
          ),
          const SizedBox(height: 14),
          TextFormField(
            controller: _amount,
            keyboardType: const TextInputType.numberWithOptions(decimal: true),
            inputFormatters: [FilteringTextInputFormatter.allow(RegExp(r'^\d{0,8}(\.\d{0,2})?'))],
            decoration: const InputDecoration(labelText: 'Amount (₹) *'),
            validator: (v) {
              final n = double.tryParse((v ?? '').trim());
              return n == null || n <= 0 ? 'Enter an amount above 0' : null;
            },
          ),
          const SizedBox(height: 14),
          TextFormField(
            controller: _reason,
            maxLength: 1000,
            maxLines: 3,
            decoration: const InputDecoration(labelText: 'Reason / details', helperText: 'Shown to the member'),
          ),
          const SizedBox(height: 6),
          InkWell(
            onTap: () => _pick(_from, (d) {
              _from = d;
              if (_to != null && _to!.isBefore(d)) _to = null;
            }),
            child: InputDecorator(
              decoration: const InputDecoration(
                labelText: 'Applies from',
                suffixIcon: Icon(Icons.calendar_today_rounded, size: 18),
              ),
              child: Text(formatBillDate(_from)),
            ),
          ),
          if (_kind == 'extra')
            SwitchListTile(
              contentPadding: EdgeInsets.zero,
              title: const Text('GST applicable'),
              value: _gst,
              onChanged: (v) => setState(() => _gst = v),
            ),
          SwitchListTile(
            contentPadding: EdgeInsets.zero,
            title: const Text('Repeats every bill'),
            subtitle: const Text('For a charge that recurs, until you set an end date or cancel it'),
            value: _recurring,
            onChanged: (v) => setState(() {
              _recurring = v;
              if (!v) _to = null;
            }),
          ),
          if (_recurring)
            InkWell(
              onTap: () => _pick(_to ?? _from, (d) => _to = d.isBefore(_from) ? _from : d),
              child: InputDecorator(
                decoration: InputDecoration(
                  labelText: 'Ends on (optional)',
                  suffixIcon: _to == null
                      ? const Icon(Icons.calendar_today_rounded, size: 18)
                      : IconButton(icon: const Icon(Icons.close_rounded, size: 18), onPressed: () => setState(() => _to = null)),
                ),
                child: Text(_to == null ? 'No end date' : formatBillDate(_to!)),
              ),
            ),
          const SizedBox(height: 20),
          ElevatedButton(
            onPressed: _saving ? null : _save,
            child: _saving
                ? const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2))
                : Text(_kind == 'fine' ? 'Add Fine' : 'Add Charge'),
          ),
        ]),
      ),
    );
  }
}
