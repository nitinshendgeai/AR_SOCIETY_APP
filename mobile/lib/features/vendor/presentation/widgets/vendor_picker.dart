import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/layout/app_sheet.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/vendor/data/vendors_work_api.dart';
import 'package:ar_society_app/features/vendor/presentation/providers/vendors_work_providers.dart';
import 'package:ar_society_app/features/vendor/presentation/widgets/vendor_master_sheet.dart';

/// Pick who was paid from the Vendor Master, or add them on the spot in the Vendor Master form. A vendor added here lands in the
/// master (Vendors & Work, vendor bills, work orders) at once, so there is one list of vendors, not a
/// typed name per expense.
class VendorPicker extends ConsumerWidget {
  final String societyId;
  final String? value;
  final ValueChanged<VendorRecord?> onChanged;
  final String label;

  /// The vendor must be chosen (a bill), so there is no "No vendor" entry.
  final bool required;

  /// A payee typed before the master was linked to expenses, shown when no vendor is chosen.
  final String? legacyName;
  const VendorPicker({
    super.key,
    required this.societyId,
    required this.value,
    required this.onChanged,
    this.label = 'Paid to (vendor)',
    this.required = false,
    this.legacyName,
  });

  /// The Vendor Master form itself — GSTIN, PAN and bank details included — not a cut-down copy of it.
  Future<void> _add(BuildContext context, WidgetRef ref) async {
    final created = await showAppSheet<VendorRecord>(
      context: context,
      builder: (_) => VendorSheet(societyId: societyId),
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
                labelText: label.isEmpty ? null : label,
                helperText: value == null && (legacyName ?? '').isNotEmpty
                    ? 'Was typed as "$legacyName" — pick the vendor to link it'
                    : (list.isEmpty ? 'No vendors yet — add one with +' : null),
                helperMaxLines: 2,
              ),
              validator: required ? (v) => v == null ? 'Choose the vendor' : null : null,
              items: [
                if (!required) const DropdownMenuItem<String?>(value: null, child: Text('No vendor')),
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
