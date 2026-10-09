import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/vendor/data/vendors_work_api.dart';
import 'package:ar_society_app/features/vendor/presentation/providers/vendor_providers.dart';
import 'package:ar_society_app/features/vendor/presentation/providers/vendors_work_providers.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart' show showErrorToast;

/// Pick who was paid from the Vendor Master, or add them on the spot. A vendor added here lands in the
/// master (Vendors & Work, vendor bills, work orders) at once, so there is one list of vendors, not a
/// typed name per expense.
class VendorPicker extends ConsumerWidget {
  final String societyId;
  final String? value;
  final ValueChanged<VendorRecord?> onChanged;
  final String label;

  /// A payee typed before the master was linked to expenses, shown when no vendor is chosen.
  final String? legacyName;
  const VendorPicker({
    super.key,
    required this.societyId,
    required this.value,
    required this.onChanged,
    this.label = 'Paid to (vendor)',
    this.legacyName,
  });

  Future<void> _add(BuildContext context, WidgetRef ref) async {
    final created = await showDialog<VendorRecord>(
      context: context,
      builder: (_) => QuickAddVendorDialog(societyId: societyId),
    );
    if (created != null) onChanged(created);
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final vendors = ref.watch(vendorRecordsProvider(societyId));
    return vendors.when(
      loading: () => const Padding(padding: EdgeInsets.symmetric(vertical: 18), child: LinearProgressIndicator()),
      error: (e, _) => Text(friendlyErrorMessage(e), style: const TextStyle(color: AppTheme.error)),
      data: (all) {
        // Vendors who can be paid; one already chosen stays listed even if since blacklisted.
        final list = all.where((v) => v.status != 'blacklisted' || v.id == value).toList()
          ..sort((a, b) => a.companyName.toLowerCase().compareTo(b.companyName.toLowerCase()));
        final known = list.any((v) => v.id == value);
        return Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Expanded(
            child: DropdownButtonFormField<String?>(
              key: ValueKey('vendor-$value-${list.length}'),
              initialValue: known ? value : null,
              isExpanded: true,
              decoration: InputDecoration(
                labelText: label,
                helperText: value == null && (legacyName ?? '').isNotEmpty
                    ? 'Was typed as "$legacyName" — pick the vendor to link it'
                    : (list.isEmpty ? 'No vendors yet — add one with +' : null),
                helperMaxLines: 2,
              ),
              items: [
                const DropdownMenuItem<String?>(value: null, child: Text('No vendor')),
                for (final v in list)
                  DropdownMenuItem<String?>(
                    value: v.id,
                    child: Text('${v.companyName} · ${vendorCategoryLabel(v.category)}', overflow: TextOverflow.ellipsis),
                  ),
              ],
              onChanged: (id) => onChanged(id == null ? null : list.firstWhere((v) => v.id == id)),
            ),
          ),
          const SizedBox(width: 4),
          Padding(
            padding: const EdgeInsets.only(top: 4),
            child: IconButton(
              onPressed: () => _add(context, ref),
              icon: const Icon(Icons.add_circle_outline_rounded),
              tooltip: 'Add a new vendor',
            ),
          ),
        ]);
      },
    );
  }
}

/// Name, phone and kind of work — enough to add a vendor in the middle of another form; the rest (GSTIN,
/// PAN, bank details) is filled in later under Vendors & Work.
class QuickAddVendorDialog extends ConsumerStatefulWidget {
  final String societyId;
  const QuickAddVendorDialog({super.key, required this.societyId});

  @override
  ConsumerState<QuickAddVendorDialog> createState() => _QuickAddVendorDialogState();
}

class _QuickAddVendorDialogState extends ConsumerState<QuickAddVendorDialog> {
  final _form = GlobalKey<FormState>();
  final _name = TextEditingController();
  final _mobile = TextEditingController();
  String _category = 'other';
  bool _saving = false;

  @override
  void dispose() {
    _name.dispose();
    _mobile.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    if (!_form.currentState!.validate()) return;
    setState(() => _saving = true);
    try {
      final vendor = await ref.read(vendorsWorkApiProvider).createVendor({
        'society_id': widget.societyId,
        'company_name': _name.text.trim(),
        'mobile': _mobile.text.trim(),
        'category': _category,
      });
      // Both vendor lists (the master and the bill form's) pick the new vendor up.
      ref.invalidate(vendorRecordsProvider(widget.societyId));
      ref.invalidate(vendorsProvider(widget.societyId));
      if (mounted) Navigator.pop(context, vendor);
    } catch (e) {
      if (mounted) {
        setState(() => _saving = false);
        showErrorToast(context, e);
      }
    }
  }

  @override
  Widget build(BuildContext context) => AlertDialog(
        title: const Text('Add a vendor'),
        content: Form(
          key: _form,
          child: Column(mainAxisSize: MainAxisSize.min, children: [
            TextFormField(
              controller: _name,
              autofocus: true,
              inputFormatters: [LengthLimitingTextInputFormatter(255)],
              decoration: const InputDecoration(labelText: 'Name of the vendor *'),
              validator: (v) => (v ?? '').trim().isEmpty ? 'Required' : null,
            ),
            const SizedBox(height: 8),
            TextFormField(
              controller: _mobile,
              keyboardType: TextInputType.phone,
              inputFormatters: [LengthLimitingTextInputFormatter(20)],
              decoration: const InputDecoration(labelText: 'Mobile *'),
              validator: (v) {
                final digits = (v ?? '').trim().replaceAll(RegExp(r'[\s\-()]'), '');
                if (digits.isEmpty) return 'Required';
                return RegExp(r'^\+?\d{7,15}$').hasMatch(digits) ? null : 'Enter a valid phone number';
              },
            ),
            const SizedBox(height: 8),
            DropdownButtonFormField<String>(
              initialValue: _category,
              decoration: const InputDecoration(labelText: 'Kind of work'),
              items: [for (final c in kVendorCategories) DropdownMenuItem(value: c.$1, child: Text(c.$2))],
              onChanged: (v) => setState(() => _category = v ?? 'other'),
            ),
            const SizedBox(height: 8),
            const Text('Add GSTIN, PAN and bank details later under Vendors & Work.',
                style: TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
          ]),
        ),
        actions: [
          TextButton(onPressed: _saving ? null : () => Navigator.pop(context), child: const Text('Cancel')),
          FilledButton(
            onPressed: _saving ? null : _save,
            child: _saving
                ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2))
                : const Text('Add vendor'),
          ),
        ],
      );
}
