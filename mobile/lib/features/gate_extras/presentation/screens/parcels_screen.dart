import 'package:flutter/material.dart';
import 'package:ar_society_app/core/l10n/app_locale.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';
import 'package:ar_society_app/core/layout/app_sheet.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/features/gate_extras/data/gate_extras_api.dart';
import 'package:ar_society_app/features/maintenance_billing/presentation/widgets/billing_sheet_frame.dart';
import 'package:ar_society_app/features/society_structure/data/models/structure_models.dart';
import 'package:ar_society_app/features/society_structure/presentation/providers/structure_providers.dart';
import 'package:ar_society_app/shared/widgets/app_data_table.dart'
    show StatusPill;
import 'package:ar_society_app/shared/widgets/app_widgets.dart';

/// Whether the person works the gate (security) or the office; they log, hand over and return parcels.
bool _atGate(WidgetRef ref) {
  final u = ref.read(currentUserProvider);
  return u != null && (u.isSecurity || u.isAdminOrCommittee || u.isManager);
}

/// Parcels and deliveries left at the gate: security logs them, the flat is told, the parcel is handed over.
class ParcelsScreen extends ConsumerWidget {
  const ParcelsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final user = ref.watch(currentUserProvider);
    final sid = user?.societyId ?? '';
    final gate = user != null &&
        (user.isSecurity || user.isAdminOrCommittee || user.isManager);
    final async = ref.watch(parcelsProvider(sid));
    return Scaffold(
      backgroundColor: AppTheme.surface,
      appBar: AppBar(title: Text(context.tr('Parcels'))),
      floatingActionButton: gate
          ? FloatingActionButton.extended(
              onPressed: () => showAppSheet(
                  context: context, builder: (_) => const _LogSheet()),
              icon: const Icon(Icons.inventory_2_rounded),
              label: Text(context.tr('Log parcel')))
          : null,
      body: async.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (e, _) => Center(
            child: OutlinedButton(
                onPressed: () => ref.invalidate(parcelsProvider(sid)),
                child: const Text('Could not load. Try again'))),
        data: (items) {
          if (items.isEmpty) {
            return AppEmptyState(
                icon: Icons.inventory_2_outlined,
                title: context.tr('No parcels'),
                subtitle: gate
                    ? 'Log a parcel when a courier leaves one at the gate.'
                    : 'Parcels left for your flat at the gate will show here.');
          }
          final waiting = items.where((p) => p.atGate).toList();
          final earlier = items.where((p) => !p.atGate).toList();
          Widget section(String title, List<Parcel> list) =>
              Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Padding(
                    padding: const EdgeInsets.fromLTRB(2, 14, 2, 8),
                    child: Text(title,
                        style: const TextStyle(
                            fontSize: 13,
                            fontWeight: FontWeight.w600,
                            color: AppTheme.textSecondary))),
                for (final p in list) _ParcelCard(parcel: p, sid: sid),
              ]);
          return RefreshIndicator(
            onRefresh: () async => ref.invalidate(parcelsProvider(sid)),
            child: ListView(
                padding: const EdgeInsets.fromLTRB(16, 4, 16, 96),
                children: [
                  if (waiting.isNotEmpty) section('At the gate', waiting),
                  if (earlier.isNotEmpty) section('Earlier', earlier),
                ]),
          );
        },
      ),
    );
  }
}

class _ParcelCard extends ConsumerWidget {
  final Parcel parcel;
  final String sid;
  const _ParcelCard({required this.parcel, required this.sid});

  Future<void> _collect(BuildContext context, WidgetRef ref) async {
    final gate = _atGate(ref);
    final name = TextEditingController();
    final ok = await showDialog<bool>(
        context: context,
        builder: (ctx) => AlertDialog(
              title: const Text('Hand over this parcel?'),
              content: gate
                  ? TextField(
                      controller: name,
                      decoration:
                          const InputDecoration(labelText: 'Who collected it?'))
                  : const Text('Mark it as collected by you.'),
              actions: [
                TextButton(
                    onPressed: () => Navigator.pop(ctx, false),
                    child: const Text('Cancel')),
                FilledButton(
                    onPressed: () => Navigator.pop(ctx, true),
                    child: Text(context.tr('Collected'))),
              ],
            ));
    if (ok != true) return;
    try {
      await ref
          .read(gateExtrasApiProvider)
          .collectParcel(parcel.id, collectedBy: name.text.trim());
      ref.invalidate(parcelsProvider(sid));
    } catch (e) {
      if (context.mounted) showErrorToast(context, e);
    }
  }

  Future<void> _return(BuildContext context, WidgetRef ref) async {
    final note = TextEditingController();
    final ok = await showDialog<bool>(
        context: context,
        builder: (ctx) => AlertDialog(
              title: const Text('Return to the courier?'),
              content: TextField(
                  controller: note,
                  decoration: const InputDecoration(labelText: 'Reason')),
              actions: [
                TextButton(
                    onPressed: () => Navigator.pop(ctx, false),
                    child: const Text('Cancel')),
                FilledButton(
                    onPressed: () => Navigator.pop(ctx, true),
                    child: Text(context.tr('Return'))),
              ],
            ));
    if (ok != true) return;
    try {
      await ref
          .read(gateExtrasApiProvider)
          .returnParcel(parcel.id, note: note.text.trim());
      ref.invalidate(parcelsProvider(sid));
    } catch (e) {
      if (context.mounted) showErrorToast(context, e);
    }
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final p = parcel;
    final gate = _atGate(ref);
    final fmt = DateFormat('d MMM, h:mm a');
    final title = [
      if ((p.courier ?? '').isNotEmpty) p.courier!,
      if ((p.description ?? '').isNotEmpty) p.description!,
    ].join(' · ');
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: DecoratedBox(
        decoration: BoxDecoration(
            color: AppTheme.cardBg,
            borderRadius: BorderRadius.circular(AppTheme.radiusL),
            boxShadow: AppTheme.cardShadow),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child:
              Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Row(children: [
              Expanded(
                  child: Text(title.isEmpty ? 'Parcel' : title,
                      style: const TextStyle(
                          fontSize: 15,
                          fontWeight: FontWeight.w700,
                          color: AppTheme.textPrimary))),
              const SizedBox(width: 8),
              switch (p.status) {
                'collected' =>
                  StatusPill(context.tr('Collected'), AppTheme.success),
                'returned' =>
                  StatusPill(context.tr('Returned'), AppTheme.textSecondary),
                _ => StatusPill(context.tr('At the gate'), AppTheme.warning),
              },
            ]),
            const SizedBox(height: 6),
            Text(
                [
                  if (p.flat != null) 'Flat ${p.flat}',
                  if ((p.recipientName ?? '').isNotEmpty)
                    'for ${p.recipientName}',
                  if (p.receivedAt != null) fmt.format(p.receivedAt!),
                ].join(' · '),
                style: const TextStyle(
                    fontSize: 13, color: AppTheme.textSecondary)),
            if (p.status == 'collected')
              Padding(
                padding: const EdgeInsets.only(top: 4),
                child: Text(
                    [
                      'Collected',
                      if ((p.collectedByName ?? '').isNotEmpty)
                        'by ${p.collectedByName}',
                      if (p.collectedAt != null) fmt.format(p.collectedAt!),
                    ].join(' '),
                    style: const TextStyle(
                        fontSize: 12.5, color: AppTheme.textSecondary)),
              ),
            if ((p.note ?? '').isNotEmpty)
              Padding(
                padding: const EdgeInsets.only(top: 4),
                child: Text(p.note!,
                    style: const TextStyle(
                        fontSize: 12.5, color: AppTheme.textSecondary)),
              ),
            if (p.atGate) ...[
              const SizedBox(height: 12),
              Row(children: [
                Expanded(
                    child: ElevatedButton(
                        onPressed: () => _collect(context, ref),
                        child: Text(context
                            .tr(gate ? 'Hand over' : 'I collected it')))),
                if (gate) ...[
                  const SizedBox(width: 8),
                  Expanded(
                      child: OutlinedButton(
                          onPressed: () => _return(context, ref),
                          child: Text(context.tr('Return')))),
                ],
              ]),
            ],
          ]),
        ),
      ),
    );
  }
}

class _LogSheet extends ConsumerStatefulWidget {
  const _LogSheet();
  @override
  ConsumerState<_LogSheet> createState() => _LogSheetState();
}

class _LogSheetState extends ConsumerState<_LogSheet> {
  final _form = GlobalKey<FormState>();
  FlatModel? _flat;
  final _courier = TextEditingController();
  final _desc = TextEditingController();
  final _recipient = TextEditingController();
  bool _saving = false;

  @override
  void dispose() {
    _courier.dispose();
    _desc.dispose();
    _recipient.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    if (!_form.currentState!.validate()) return;
    setState(() => _saving = true);
    try {
      final sid = ref.read(currentUserProvider)?.societyId ?? '';
      await ref.read(gateExtrasApiProvider).logParcel(sid,
          flatId: _flat!.id,
          courier: _courier.text.trim(),
          description: _desc.text.trim(),
          recipientName: _recipient.text.trim());
      ref.invalidate(parcelsProvider(sid));
      if (mounted) {
        AppToast.success(context, 'Parcel logged. The flat has been told.');
        Navigator.pop(context);
      }
    } catch (e) {
      if (mounted) {
        setState(() => _saving = false);
        showErrorToast(context, e);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final flats = ref.watch(flatsBySocietyProvider);
    return BillingSheetFrame(
      title: 'Log a parcel',
      child: Form(
        key: _form,
        child:
            Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          flats.when(
            loading: () => const LinearProgressIndicator(),
            error: (e, _) => Text(friendlyErrorMessage(e),
                style: const TextStyle(color: AppTheme.error)),
            data: (list) => DropdownButtonFormField<FlatModel>(
              initialValue: _flat,
              isExpanded: true,
              decoration: const InputDecoration(labelText: 'Flat *'),
              items: [
                for (final f in list.where((f) => f.isActive))
                  DropdownMenuItem(
                      value: f,
                      child: Text('${f.wingName ?? ''} / ${f.flatNumber}')),
              ],
              onChanged: (f) => setState(() => _flat = f),
              validator: (v) => v == null ? 'Choose the flat' : null,
            ),
          ),
          const SizedBox(height: 12),
          TextFormField(
              controller: _courier,
              decoration: const InputDecoration(
                  labelText: 'From (courier / shop)', hintText: 'e.g. Amazon')),
          const SizedBox(height: 12),
          TextFormField(
              controller: _recipient,
              decoration:
                  const InputDecoration(labelText: 'For (name on parcel)')),
          const SizedBox(height: 12),
          TextFormField(
              controller: _desc,
              decoration: const InputDecoration(
                  labelText: 'What it looks like (optional)')),
          const SizedBox(height: 16),
          AppPrimaryButton(
              label: context.tr('Log parcel'),
              isLoading: _saving,
              onPressed: _save),
        ]),
      ),
    );
  }
}
