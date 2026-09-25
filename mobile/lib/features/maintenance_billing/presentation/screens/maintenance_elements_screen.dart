import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/features/maintenance_billing/data/maintenance_billing_api.dart';
import 'package:ar_society_app/features/maintenance_billing/presentation/providers/maintenance_billing_providers.dart';
import 'package:ar_society_app/features/maintenance_billing/presentation/widgets/billing_sheet_frame.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';
import 'package:ar_society_app/core/layout/app_sheet.dart';
import 'package:ar_society_app/shared/widgets/app_data_table.dart';
import 'package:ar_society_app/core/layout/app_shell.dart' show isDesktopLayout;

/// Admin/Committee master of maintenance elements — the kinds of charge
/// the society levies and how each is calculated by default. Starts with
/// the standard bye-law set; every element can be edited or switched off,
/// and custom ones added. Charge heads are created from these.
class MaintenanceElementsScreen extends ConsumerWidget {
  const MaintenanceElementsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final societyId = ref.watch(currentUserProvider)?.societyId;
    if (societyId == null) {
      return const Scaffold(body: Center(child: Text('No society context')));
    }
    final key = (societyId: societyId, includeInactive: true);
    final elementsAsync = ref.watch(maintenanceElementsProvider(key));

    void openSheet([MaintenanceElement? existing]) => showAppSheet(
          context: context,
          builder: (_) => _ElementSheet(societyId: societyId, existing: existing),
        );

    final desktop = isDesktopLayout(context);
    return Scaffold(
      backgroundColor: AppTheme.surface,
      appBar: AppBar(title: const Text('Maintenance Elements'), actions: [
        if (desktop) HeaderActionButton(icon: Icons.add_rounded, label: 'Add Element', onPressed: openSheet),
      ]),
      floatingActionButton: desktop
          ? null
          : FloatingActionButton.extended(
              onPressed: openSheet,
              icon: const Icon(Icons.add_rounded),
              label: const Text('Add Element'),
            ),
      body: RefreshIndicator(
        onRefresh: () async => ref.invalidate(maintenanceElementsProvider(key)),
        child: elementsAsync.when(
          loading: () => const Center(child: CircularProgressIndicator()),
          error: (e, _) => ListView(children: [
            Padding(
              padding: const EdgeInsets.all(24),
              child: Text(friendlyErrorMessage(e), style: const TextStyle(color: AppTheme.error)),
            ),
          ]),
          data: (elements) {
            final active = elements.where((e) => e.isActive).toList();
            final inactive = elements.where((e) => !e.isActive).toList();
            return ListView(
              padding: const EdgeInsets.fromLTRB(16, 16, 16, 96),
              children: [
                const Text(
                  'The kinds of charge your society can bill, and how each is worked out by default. '
                  'Charge heads are created from these — edit a default here and new charge heads '
                  'pick it up; existing ones keep their own settings.',
                  style: TextStyle(fontSize: 12, color: AppTheme.textSecondary),
                ),
                const SizedBox(height: 12),
                if (desktop)
                  AppDataTable<MaintenanceElement>(
                    rows: elements,
                    pageSize: 50,
                    onRowTap: openSheet,
                    columns: [
                      AppDataColumn(
                        label: 'Element',
                        flex: 3,
                        sortKey: (e) => e.name.toLowerCase(),
                        cell: (e) => Row(children: [
                          Flexible(
                            child: Text(e.name,
                                overflow: TextOverflow.ellipsis,
                                style: const TextStyle(fontSize: 13.5, fontWeight: FontWeight.w600)),
                          ),
                          if (!e.isSystem) const _Tag('Custom', AppTheme.primary),
                        ]),
                      ),
                      AppDataColumn.text('Default calculation', (e) => e.rateLabel, flex: 4),
                      AppDataColumn.text('Bye-law', (e) => e.byeLawRef ?? '—', flex: 2),
                      AppDataColumn(
                        label: 'Type',
                        sortKey: (e) => e.isServiceCharge ? 0 : 1,
                        cell: (e) => e.isServiceCharge
                            ? const StatusPill('Service', AppTheme.success)
                            : const Text('—', style: TextStyle(color: AppTheme.textSecondary)),
                      ),
                      AppDataColumn(
                        label: 'Status',
                        width: 120,
                        sortKey: (e) => e.isActive ? 0 : 1,
                        cell: (e) => e.isActive
                            ? const StatusPill('Active', AppTheme.success)
                            : const StatusPill('Switched off', AppTheme.textSecondary),
                      ),
                    ],
                  )
                else ...[
                  for (final e in active) _ElementTile(element: e, onTap: () => openSheet(e)),
                  if (inactive.isNotEmpty) ...[
                    const Padding(
                      padding: EdgeInsets.fromLTRB(4, 16, 0, 8),
                      child: Text('Switched off',
                          style: TextStyle(fontSize: 13, fontWeight: FontWeight.w700, color: AppTheme.textSecondary)),
                    ),
                    for (final e in inactive) _ElementTile(element: e, onTap: () => openSheet(e)),
                  ],
                ],
              ],
            );
          },
        ),
      ),
    );
  }
}

class _ElementTile extends StatelessWidget {
  final MaintenanceElement element;
  final VoidCallback onTap;
  const _ElementTile({required this.element, required this.onTap});

  @override
  Widget build(BuildContext context) {
    final e = element;
    return Opacity(
      opacity: e.isActive ? 1 : 0.55,
      child: Card(
        margin: const EdgeInsets.only(bottom: 10),
        child: ListTile(
          onTap: onTap,
          title: Row(children: [
            Expanded(child: Text(e.name, style: const TextStyle(fontWeight: FontWeight.w600))),
            if (!e.isSystem) const _Tag('Custom', AppTheme.primary),
            if (e.isServiceCharge) const _Tag('Service', AppTheme.success),
          ]),
          subtitle: Text(
            [e.rateLabel, if (e.byeLawRef != null) e.byeLawRef!].join('\n'),
            style: const TextStyle(fontSize: 12),
          ),
          isThreeLine: e.byeLawRef != null,
          trailing: const Icon(Icons.chevron_right_rounded),
        ),
      ),
    );
  }
}

class _Tag extends StatelessWidget {
  final String label;
  final Color color;
  const _Tag(this.label, this.color);

  @override
  Widget build(BuildContext context) => Container(
        margin: const EdgeInsets.only(left: 6),
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
        decoration: BoxDecoration(color: color.withOpacity(0.12), borderRadius: BorderRadius.circular(10)),
        child: Text(label, style: TextStyle(fontSize: 10, fontWeight: FontWeight.w600, color: color)),
      );
}

class _ElementSheet extends ConsumerStatefulWidget {
  final String societyId;
  final MaintenanceElement? existing;
  const _ElementSheet({required this.societyId, this.existing});

  @override
  ConsumerState<_ElementSheet> createState() => _ElementSheetState();
}

class _ElementSheetState extends ConsumerState<_ElementSheet> {
  final _formKey = GlobalKey<FormState>();
  late final _nameCtrl = TextEditingController(text: widget.existing?.name ?? '');
  late final _amountCtrl = TextEditingController(text: widget.existing?.defaultAmount ?? '');
  late final _refCtrl = TextEditingController(text: widget.existing?.byeLawRef ?? '');
  late final _descCtrl = TextEditingController(text: widget.existing?.description ?? '');
  late String _category = widget.existing?.category ?? 'other';
  late String _basis = widget.existing?.defaultBasis ?? 'fixed';
  late bool _service = widget.existing?.isServiceCharge ?? false;
  late bool _gst = widget.existing?.gstApplicable ?? true;
  late bool _active = widget.existing?.isActive ?? true;
  bool _saving = false;

  bool get _editing => widget.existing != null;

  @override
  void dispose() {
    for (final c in [_nameCtrl, _amountCtrl, _refCtrl, _descCtrl]) {
      c.dispose();
    }
    super.dispose();
  }

  String? _optional(String v) => v.trim().isEmpty ? null : v.trim();

  Future<void> _save() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() => _saving = true);
    final fields = <String, dynamic>{
      'name': _nameCtrl.text.trim(),
      'category': _category,
      'default_basis': _basis,
      'default_amount': _optional(_amountCtrl.text),
      'is_service_charge': _service,
      'gst_applicable': _gst,
      'bye_law_ref': _optional(_refCtrl.text),
      'description': _optional(_descCtrl.text),
      if (_editing) 'is_active': _active,
    };
    try {
      final api = ref.read(maintenanceBillingApiProvider);
      if (_editing) {
        await api.updateElement(widget.existing!.id, fields);
      } else {
        await api.createElement(widget.societyId, fields);
      }
      ref.invalidate(maintenanceElementsProvider((societyId: widget.societyId, includeInactive: true)));
      ref.invalidate(maintenanceElementsProvider((societyId: widget.societyId, includeInactive: false)));
      if (mounted) {
        AppToast.success(context, _editing ? 'Element updated' : 'Element added');
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
    return BillingSheetFrame(
      title: _editing ? 'Edit Element' : 'Add Element',
      child: Form(
        key: _formKey,
        child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          TextFormField(
            controller: _nameCtrl,
            decoration: const InputDecoration(labelText: 'Name *', hintText: 'e.g. Festival Fund'),
            validator: (v) => (v == null || v.trim().isEmpty) ? 'Required' : null,
          ),
          const SizedBox(height: 14),
          DropdownButtonFormField<String>(
            initialValue: _category,
            decoration: const InputDecoration(labelText: 'Category (for reports)'),
            items: [for (final t in kChargeTypes) DropdownMenuItem(value: t.$1, child: Text(t.$2))],
            onChanged: (v) => setState(() => _category = v ?? _category),
          ),
          const SizedBox(height: 14),
          DropdownButtonFormField<String>(
            initialValue: _basis,
            isExpanded: true,
            decoration: const InputDecoration(labelText: 'Default calculation'),
            items: [for (final b in kChargeBases) DropdownMenuItem(value: b.$1, child: Text(b.$2))],
            onChanged: (v) => setState(() => _basis = v ?? _basis),
          ),
          const SizedBox(height: 6),
          Text(chargeBasisHint(_basis), style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
          const SizedBox(height: 14),
          TextFormField(
            controller: _amountCtrl,
            keyboardType: const TextInputType.numberWithOptions(decimal: true),
            decoration: InputDecoration(
              labelText: 'Default ${chargeAmountFieldLabel(_basis).toLowerCase()}',
              helperText: 'Optional — leave blank if each society decides it',
            ),
            validator: (v) {
              if (v == null || v.trim().isEmpty) return null;
              final n = double.tryParse(v.trim());
              return (n == null || n < 0) ? 'Enter a valid amount' : null;
            },
          ),
          const SizedBox(height: 4),
          SwitchListTile(
            contentPadding: EdgeInsets.zero,
            title: const Text('Service charge'),
            subtitle: const Text('Counts towards non-occupancy charges'),
            value: _service,
            onChanged: (v) => setState(() => _service = v),
          ),
          SwitchListTile(
            contentPadding: EdgeInsets.zero,
            title: const Text('GST applicable'),
            value: _gst,
            onChanged: (v) => setState(() => _gst = v),
          ),
          TextFormField(
            controller: _refCtrl,
            decoration: const InputDecoration(labelText: 'Bye-law reference', hintText: 'e.g. Bye-law 67(a)(iii)'),
          ),
          const SizedBox(height: 14),
          TextFormField(
            controller: _descCtrl,
            maxLines: 3,
            decoration: const InputDecoration(labelText: 'Description'),
          ),
          if (_editing) ...[
            const SizedBox(height: 4),
            SwitchListTile(
              contentPadding: EdgeInsets.zero,
              title: const Text('Active'),
              subtitle: const Text('Switched-off elements can\'t be used for new charge heads'),
              value: _active,
              onChanged: (v) => setState(() => _active = v),
            ),
          ],
          const SizedBox(height: 20),
          ElevatedButton(
            onPressed: _saving ? null : _save,
            child: _saving
                ? const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2))
                : Text(_editing ? 'Save Changes' : 'Add Element'),
          ),
        ]),
      ),
    );
  }
}
