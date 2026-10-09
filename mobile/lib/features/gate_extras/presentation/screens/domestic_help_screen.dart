import 'package:flutter/material.dart';
import 'package:ar_society_app/core/l10n/app_locale.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/layout/app_sheet.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/features/gate_extras/data/gate_extras_api.dart';
import 'package:ar_society_app/features/maintenance_billing/presentation/widgets/billing_sheet_frame.dart';
import 'package:ar_society_app/features/society_structure/data/models/structure_models.dart';
import 'package:ar_society_app/features/society_structure/presentation/providers/structure_providers.dart';
import 'package:ar_society_app/shared/utils/file_saver.dart';
import 'package:ar_society_app/shared/widgets/app_data_table.dart'
    show StatusPill;
import 'package:ar_society_app/shared/widgets/app_widgets.dart';

(String, Color) _state(DomesticHelp h) => switch (h.effectiveStatus) {
      'active' => ('Pass active', AppTheme.success),
      'pending' => ('Awaiting pass', AppTheme.warning),
      'expired' => ('Pass expired', AppTheme.error),
      'suspended' => ('Suspended', AppTheme.error),
      _ => ('Ended', AppTheme.textSecondary),
    };

/// Domestic help (maids, cooks, drivers): residents register them, the office issues a pass, security records entry
/// and exit at the gate.
class DomesticHelpScreen extends ConsumerStatefulWidget {
  const DomesticHelpScreen({super.key});
  @override
  ConsumerState<DomesticHelpScreen> createState() => _DomesticHelpScreenState();
}

class _DomesticHelpScreenState extends ConsumerState<DomesticHelpScreen> {
  final _search = TextEditingController();
  String _q = '';

  @override
  void dispose() {
    _search.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final user = ref.watch(currentUserProvider);
    final sid = user?.societyId ?? '';
    final gate = user != null && user.isSecurity;
    final office = user?.isAdminOrCommittee == true;
    final async = ref.watch(domesticHelpProvider(sid));
    return Scaffold(
      backgroundColor: AppTheme.surface,
      appBar: AppBar(title: Text(context.tr('Domestic help'))),
      floatingActionButton: gate
          ? null
          : FloatingActionButton.extended(
              onPressed: () => showAppSheet(
                  context: context,
                  builder: (_) => _RegisterSheet(office: office)),
              icon: const Icon(Icons.person_add_alt_1_rounded),
              label: Text(context.tr('Add help'))),
      body: async.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (e, _) => Center(
            child: OutlinedButton(
                onPressed: () => ref.invalidate(domesticHelpProvider(sid)),
                child: const Text('Could not load. Try again'))),
        data: (all) {
          final q = _q.trim().toLowerCase();
          final items = q.isEmpty
              ? all
              : all
                  .where((h) =>
                      h.name.toLowerCase().contains(q) ||
                      h.mobile.contains(q) ||
                      (h.passNo ?? '').toLowerCase().contains(q))
                  .toList();
          // those who need attention first: awaiting a pass, then inside now
          items.sort((a, b) {
            int rank(DomesticHelp h) =>
                h.status == 'pending' ? 0 : (h.inside ? 1 : 2);
            final r = rank(a).compareTo(rank(b));
            return r != 0 ? r : a.name.compareTo(b.name);
          });
          return RefreshIndicator(
            onRefresh: () async => ref.invalidate(domesticHelpProvider(sid)),
            child: ListView(
              padding: const EdgeInsets.fromLTRB(16, 12, 16, 96),
              children: [
                if (gate || office || all.length > 6)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 12),
                    child: TextField(
                      controller: _search,
                      onChanged: (v) => setState(() => _q = v),
                      decoration: const InputDecoration(
                          prefixIcon: Icon(Icons.search_rounded),
                          hintText: 'Search name, mobile or pass number'),
                    ),
                  ),
                if (items.isEmpty)
                  Padding(
                      padding: const EdgeInsets.only(top: 40),
                      child: AppEmptyState(
                          icon: Icons.cleaning_services_outlined,
                          title:
                              all.isEmpty ? 'No domestic help yet' : 'No match',
                          subtitle: all.isEmpty
                              ? (gate
                                  ? 'Help registered by residents will appear here.'
                                  : 'Add your maid, cook or driver so security knows them.')
                              : 'Try another name, mobile or pass number.')),
                for (final h in items)
                  _HelpCard(help: h, sid: sid, gate: gate, office: office),
              ],
            ),
          );
        },
      ),
    );
  }
}

class _HelpCard extends ConsumerWidget {
  final DomesticHelp help;
  final String sid;
  final bool gate, office;
  const _HelpCard(
      {required this.help,
      required this.sid,
      required this.gate,
      required this.office});

  Future<void> _scan(BuildContext context, WidgetRef ref) async {
    try {
      final r = await ref.read(gateExtrasApiProvider).scan(help.id);
      ref.invalidate(domesticHelpProvider(sid));
      if (context.mounted) {
        AppToast.success(
            context,
            r.direction == 'in'
                ? '${r.name} checked in'
                : '${r.name} checked out');
      }
    } catch (e) {
      if (context.mounted) showErrorToast(context, e);
    }
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final h = help;
    final (label, color) = _state(h);
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: DecoratedBox(
        decoration: BoxDecoration(
            color: AppTheme.cardBg,
            borderRadius: BorderRadius.circular(AppTheme.radiusL),
            boxShadow: AppTheme.cardShadow),
        child: Material(
          type: MaterialType.transparency,
          child: InkWell(
            borderRadius: BorderRadius.circular(AppTheme.radiusL),
            onTap: () => showAppSheet(
                context: context,
                builder: (_) => _DetailSheet(
                    help: h, sid: sid, office: office, gate: gate)),
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(children: [
                      Expanded(
                          child: Text('${h.name} · ${helpKindLabel(h.kind)}',
                              style: const TextStyle(
                                  fontSize: 15,
                                  fontWeight: FontWeight.w700,
                                  color: AppTheme.textPrimary))),
                      const SizedBox(width: 8),
                      StatusPill(context.tr(label), color),
                    ]),
                    const SizedBox(height: 6),
                    Text(
                        [
                          if (h.passNo != null) h.passNo!,
                          h.flats.map((f) => f.label).join(', '),
                        ].where((s) => s.isNotEmpty).join(' · '),
                        style: const TextStyle(
                            fontSize: 13, color: AppTheme.textSecondary)),
                    if (h.inside)
                      const Padding(
                        padding: EdgeInsets.only(top: 6),
                        child: Row(children: [
                          Icon(Icons.circle, size: 9, color: AppTheme.success),
                          SizedBox(width: 6),
                          Text('Inside now',
                              style: TextStyle(
                                  fontSize: 12.5,
                                  fontWeight: FontWeight.w600,
                                  color: AppTheme.success)),
                        ]),
                      ),
                    if (gate) ...[
                      const SizedBox(height: 12),
                      SizedBox(
                        width: double.infinity,
                        child: ElevatedButton(
                            onPressed: () => _scan(context, ref),
                            child: Text(context
                                .tr(h.inside ? 'Check out' : 'Check in'))),
                      ),
                    ],
                  ]),
            ),
          ),
        ),
      ),
    );
  }
}

class _DetailSheet extends ConsumerStatefulWidget {
  final DomesticHelp help;
  final String sid;
  final bool office, gate;
  const _DetailSheet(
      {required this.help,
      required this.sid,
      required this.office,
      required this.gate});
  @override
  ConsumerState<_DetailSheet> createState() => _DetailSheetState();
}

class _DetailSheetState extends ConsumerState<_DetailSheet> {
  late Future<List<HelpEntry>> _entries =
      ref.read(gateExtrasApiProvider).entries(widget.help.id);
  bool _busy = false;

  Future<void> _do(
      Future<void> Function(GateExtrasApi api) action, String done) async {
    setState(() => _busy = true);
    try {
      await action(ref.read(gateExtrasApiProvider));
      ref.invalidate(domesticHelpProvider(widget.sid));
      if (mounted) {
        AppToast.success(context, done);
        Navigator.pop(context);
      }
    } catch (e) {
      if (mounted) {
        setState(() => _busy = false);
        showErrorToast(context, e);
      }
    }
  }

  Future<void> _download() async {
    final h = widget.help;
    try {
      final bytes = await ref.read(gateExtrasApiProvider).pass(h.id);
      final name = '${h.passNo ?? 'pass'}.pdf';
      final saved =
          await saveFileBytes(bytes, name, mimeType: 'application/pdf');
      if (mounted && saved) AppToast.success(context, 'Saved $name');
    } catch (e) {
      if (mounted) showErrorToast(context, e);
    }
  }

  Widget _line(String label, String? value) => (value ?? '').isEmpty
      ? const SizedBox.shrink()
      : Padding(
          padding: const EdgeInsets.only(bottom: 8),
          child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
            SizedBox(
                width: 96,
                child: Text(label,
                    style: const TextStyle(
                        fontSize: 13, color: AppTheme.textSecondary))),
            Expanded(
                child: Text(value!,
                    style: const TextStyle(
                        fontSize: 14, color: AppTheme.textPrimary))),
          ]),
        );

  @override
  Widget build(BuildContext context) {
    final h = widget.help;
    final (label, color) = _state(h);
    final fmt = DateFormat('d MMM, h:mm a');
    final day = DateFormat('d MMM yyyy');
    return BillingSheetFrame(
      title: h.name,
      child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        Align(
            alignment: Alignment.centerLeft,
            child: StatusPill(context.tr(label), color)),
        const SizedBox(height: 12),
        _line('Work', helpKindLabel(h.kind)),
        _line('Mobile', h.mobile),
        _line('ID proof', h.idProof),
        _line('Pass no.', h.passNo),
        _line('Valid till',
            h.validUntil == null ? null : day.format(h.validUntil!)),
        _line('Police check', h.policeVerified ? 'Verified' : 'Not recorded'),
        _line('Works in', h.flats.map((f) => f.label).join(', ')),
        _line('Note', h.note),
        const SizedBox(height: 4),
        const Text('Last 30 days',
            style: TextStyle(
                fontSize: 13,
                fontWeight: FontWeight.w600,
                color: AppTheme.textSecondary)),
        const SizedBox(height: 6),
        FutureBuilder<List<HelpEntry>>(
          future: _entries,
          builder: (context, snap) {
            if (!snap.hasData) {
              return const Padding(
                  padding: EdgeInsets.all(8), child: LinearProgressIndicator());
            }
            final list = snap.data!.take(8).toList();
            if (list.isEmpty) {
              return const Text('No visits recorded yet.',
                  style:
                      TextStyle(fontSize: 13, color: AppTheme.textSecondary));
            }
            return Column(children: [
              for (final e in list)
                Padding(
                  padding: const EdgeInsets.only(bottom: 4),
                  child: Row(children: [
                    Expanded(
                        child: Text(e.inAt == null ? '-' : fmt.format(e.inAt!),
                            style: const TextStyle(fontSize: 13))),
                    Text(
                        e.outAt == null
                            ? 'inside'
                            : 'left ${DateFormat('h:mm a').format(e.outAt!)}',
                        style: const TextStyle(
                            fontSize: 13, color: AppTheme.textSecondary)),
                  ]),
                ),
            ]);
          },
        ),
        const SizedBox(height: 12),
        if (h.passNo != null && h.status == 'active')
          AppPrimaryButton(
              label: context.tr('Download pass'), onPressed: _download),
        if (widget.office) ...[
          if (h.status == 'pending')
            Padding(
              padding: const EdgeInsets.only(top: 8),
              child: AppPrimaryButton(
                  label: context.tr('Issue pass'),
                  isLoading: _busy,
                  onPressed: () => _do(
                      (api) => api.approve(h.id, policeVerified: false),
                      'Pass issued')),
            ),
          if (h.effectiveStatus == 'expired')
            Padding(
              padding: const EdgeInsets.only(top: 8),
              child: OutlinedButton(
                  onPressed: _busy
                      ? null
                      : () => _do((api) => api.renew(h.id), 'Pass renewed'),
                  child: const Text('Renew for a year')),
            ),
          if (h.status == 'active')
            Padding(
              padding: const EdgeInsets.only(top: 8),
              child: OutlinedButton(
                  onPressed: _busy
                      ? null
                      : () => _do((api) => api.setStatus(h.id, 'suspended'),
                          'Pass suspended'),
                  style:
                      OutlinedButton.styleFrom(foregroundColor: AppTheme.error),
                  child: Text(context.tr('Suspend pass'))),
            ),
          if (h.status == 'suspended' || h.status == 'ended')
            Padding(
              padding: const EdgeInsets.only(top: 8),
              child: OutlinedButton(
                  onPressed: _busy
                      ? null
                      : () =>
                          _do((api) => api.approve(h.id), 'Pass active again'),
                  child: const Text('Activate again')),
            ),
        ] else if (!widget.gate && h.flats.isNotEmpty)
          Padding(
            padding: const EdgeInsets.only(top: 8),
            child: OutlinedButton(
                onPressed: _busy
                    ? null
                    : () => _do(
                        (api) => api.removeFlat(h.id, h.flats.first.flatId),
                        'Removed from your flat'),
                child: const Text('Stop coming to my flat')),
          ),
      ]),
    );
  }
}

class _RegisterSheet extends ConsumerStatefulWidget {
  final bool office;
  const _RegisterSheet({required this.office});
  @override
  ConsumerState<_RegisterSheet> createState() => _RegisterSheetState();
}

class _RegisterSheetState extends ConsumerState<_RegisterSheet> {
  final _form = GlobalKey<FormState>();
  final _name = TextEditingController();
  final _mobile = TextEditingController();
  final _proof = TextEditingController();
  String _kind = 'maid';
  FlatModel? _flat;
  bool _saving = false;

  @override
  void dispose() {
    _name.dispose();
    _mobile.dispose();
    _proof.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    if (!_form.currentState!.validate()) return;
    setState(() => _saving = true);
    try {
      final sid = ref.read(currentUserProvider)?.societyId ?? '';
      await ref.read(gateExtrasApiProvider).register(sid,
          name: _name.text.trim(),
          mobile: _mobile.text.trim(),
          kind: _kind,
          idProof: _proof.text.trim(),
          flatIds: _flat == null ? null : [_flat!.id]);
      ref.invalidate(domesticHelpProvider(sid));
      if (mounted) {
        AppToast.success(
            context,
            widget.office
                ? 'Added, pass issued'
                : 'Added. The society office will issue the pass.');
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
    final flats = widget.office ? ref.watch(flatsBySocietyProvider) : null;
    return BillingSheetFrame(
      title: 'Add domestic help',
      child: Form(
        key: _form,
        child:
            Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          TextFormField(
              controller: _name,
              textCapitalization: TextCapitalization.words,
              decoration: const InputDecoration(labelText: 'Name *'),
              validator: (v) =>
                  (v ?? '').trim().length < 2 ? 'Enter the name' : null),
          const SizedBox(height: 12),
          TextFormField(
              controller: _mobile,
              keyboardType: TextInputType.phone,
              decoration: const InputDecoration(labelText: 'Mobile *'),
              validator: (v) => (v ?? '').trim().length < 7
                  ? 'Enter the mobile number'
                  : null),
          const SizedBox(height: 12),
          DropdownButtonFormField<String>(
            initialValue: _kind,
            decoration: const InputDecoration(labelText: 'Work'),
            items: [
              for (final k in kHelpKinds)
                DropdownMenuItem(value: k.$1, child: Text(k.$2))
            ],
            onChanged: (v) => setState(() => _kind = v ?? _kind),
          ),
          const SizedBox(height: 12),
          TextFormField(
              controller: _proof,
              decoration: const InputDecoration(
                  labelText: 'ID proof (optional)',
                  hintText: 'e.g. Aadhaar ending 4821')),
          if (flats != null) ...[
            const SizedBox(height: 12),
            flats.when(
              loading: () => const LinearProgressIndicator(),
              error: (e, _) => Text(friendlyErrorMessage(e),
                  style: const TextStyle(color: AppTheme.error)),
              data: (list) => DropdownButtonFormField<FlatModel>(
                initialValue: _flat,
                isExpanded: true,
                decoration: const InputDecoration(labelText: 'Works in flat *'),
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
          ],
          const SizedBox(height: 16),
          AppPrimaryButton(label: 'Add', isLoading: _saving, onPressed: _save),
        ]),
      ),
    );
  }
}
