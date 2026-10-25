import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/layout/app_sheet.dart';
import 'package:ar_society_app/core/motion/loading.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/features/vendor/data/vendor_master_api.dart';
import 'package:ar_society_app/features/vendor/presentation/providers/vendors_work_providers.dart';
import 'package:ar_society_app/shared/widgets/app_form.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';

/// Every vendor's TDS setup in one list. The rate deducted when a vendor is paid comes from its type (individual, firm,
/// company…), its PAN and its section, so a vendor with no type, a type that disagrees with its PAN, or no section is
/// deducted wrongly or not at all. Vendors that need attention are listed first with what is wrong; the fix that can be
/// worked out (the type from the PAN or name, the section from the category) is applied to one vendor, or to all of
/// them at once. Anything else is set by hand on the vendor.
class VendorTdsReviewScreen extends ConsumerStatefulWidget {
  const VendorTdsReviewScreen({super.key});

  @override
  ConsumerState<VendorTdsReviewScreen> createState() => _VendorTdsReviewScreenState();
}

class _VendorTdsReviewScreenState extends ConsumerState<VendorTdsReviewScreen> {
  bool _busy = false;
  bool _problemsOnly = true;

  Future<void> _apply(String societyId,
      {List<({String vendorId, String? constitution, String? section})> items = const [],
      bool useSuggestions = false}) async {
    setState(() => _busy = true);
    try {
      final r = await ref
          .read(vendorMasterApiProvider)
          .applyTdsFixes(societyId, items: items, useSuggestions: useSuggestions);
      ref.invalidate(tdsReviewProvider);
      ref.invalidate(vendorRecordsProvider);
      if (!mounted) return;
      if (r.failed.isEmpty) {
        AppToast.success(context, '${r.fixed} vendor${r.fixed == 1 ? '' : 's'} updated');
      } else {
        AppToast.warning(context, '${r.fixed} updated. ${r.failed.join('; ')}');
      }
    } catch (e) {
      if (mounted) showErrorToast(context, e);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _applyAll(String societyId, int count) async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('Apply suggested fixes'),
        content: Text('$count vendor${count == 1 ? '' : 's'} will get the type and TDS section shown for '
            '${count == 1 ? 'it' : 'them'}. Check the list first: these are worked out from the PAN, the name and the '
            'category, and your chartered accountant should confirm them.'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(dialogContext, false), child: const Text('Cancel')),
          FilledButton(onPressed: () => Navigator.pop(dialogContext, true), child: const Text('Apply to all')),
        ],
      ),
    );
    if (ok == true) await _apply(societyId, useSuggestions: true);
  }

  Future<void> _edit(String societyId, TdsReviewRow v) async {
    final r = await showAppSheet<({String? constitution, String? section})>(
        context: context, builder: (_) => _EditTdsSheet(vendor: v));
    if (r == null) return;
    await _apply(societyId, items: [(vendorId: v.id, constitution: r.constitution, section: r.section)]);
  }

  @override
  Widget build(BuildContext context) {
    final societyId = ref.watch(currentUserProvider)?.societyId;
    if (societyId == null) return const Scaffold(body: Center(child: Text('No society context')));
    final committee = ref.watch(currentUserProvider)?.isAdminOrCommittee ?? false;
    final async = ref.watch(tdsReviewProvider(societyId));
    return AppPage(
      title: 'TDS Review',
      body: async.when(
        loading: () => const AppLoader(),
        error: (e, _) => ListView(children: [
          Padding(padding: const EdgeInsets.all(24), child: Text(friendlyErrorMessage(e), style: const TextStyle(color: AppTheme.error)))
        ]),
        data: (review) {
          final rows = _problemsOnly ? review.vendors.where((v) => v.hasIssues).toList() : review.vendors;
          return RefreshIndicator(
            onRefresh: () async => ref.invalidate(tdsReviewProvider(societyId)),
            child: ResponsiveBody(
              maxWidth: 860,
              child: ListView(padding: const EdgeInsets.fromLTRB(16, 16, 16, 96), children: [
                const Text(
                    'The TDS deducted when a vendor is paid depends on its type (individual, firm, company…), its PAN and its '
                    'section. Fix the vendors below so every payment is deducted at the right rate.',
                    style: TextStyle(fontSize: 12.5, color: AppTheme.textSecondary, height: 1.35)),
                const SizedBox(height: 12),
                Wrap(spacing: 8, runSpacing: 4, crossAxisAlignment: WrapCrossAlignment.center, children: [
                  _Pill(review.withIssues == 0 ? 'All ${review.total} vendors are set up' : '${review.withIssues} of ${review.total} need attention',
                      review.withIssues == 0 ? AppTheme.success : AppTheme.warning),
                  if (review.fixable > 0) _Pill('${review.fixable} can be fixed automatically', AppTheme.primary),
                  FilterChip(
                    label: const Text('Problems only', style: TextStyle(fontSize: 12)),
                    selected: _problemsOnly,
                    onSelected: (v) => setState(() => _problemsOnly = v),
                  ),
                ]),
                if (committee && review.fixable > 0) ...[
                  const SizedBox(height: 12),
                  FilledButton.icon(
                    key: const Key('tds-apply-all'),
                    onPressed: _busy ? null : () => _applyAll(societyId, review.fixable),
                    icon: const Icon(Icons.auto_fix_high_rounded, size: 18),
                    label: Text('Apply suggested fixes to ${review.fixable} vendor${review.fixable == 1 ? '' : 's'}'),
                  ),
                ],
                const SizedBox(height: 12),
                if (rows.isEmpty)
                  const Padding(padding: EdgeInsets.all(24), child: Center(child: Text('Nothing to fix')))
                else
                  for (final v in rows)
                    _VendorTile(
                      vendor: v,
                      committee: committee,
                      busy: _busy,
                      onFix: () => _apply(societyId, items: [
                        (vendorId: v.id, constitution: v.suggestedConstitution, section: v.suggestedSection)
                      ]),
                      onEdit: () => _edit(societyId, v),
                    ),
              ]),
            ),
          );
        },
      ),
    );
  }
}

class _Pill extends StatelessWidget {
  final String text;
  final Color color;
  const _Pill(this.text, this.color);

  @override
  Widget build(BuildContext context) => Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
        decoration: BoxDecoration(color: color.withValues(alpha: 0.12), borderRadius: BorderRadius.circular(AppTheme.radiusM)),
        child: Text(text, style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: color)),
      );
}

class _VendorTile extends StatelessWidget {
  final TdsReviewRow vendor;
  final bool committee;
  final bool busy;
  final VoidCallback onFix;
  final VoidCallback onEdit;
  const _VendorTile({required this.vendor, required this.committee, required this.busy, required this.onFix, required this.onEdit});

  @override
  Widget build(BuildContext context) {
    final v = vendor;
    return Card(
      margin: const EdgeInsets.only(bottom: 10),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(v.name, style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 15)),
          Text(
              [v.vendorCode, if ((v.pan ?? '').isNotEmpty) 'PAN ${v.pan}' else 'No PAN'].join(' · '),
              style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
          const SizedBox(height: 4),
          Text('Type: ${v.constitutionLabel ?? 'Not set'}', style: const TextStyle(fontSize: 13)),
          Text('Section: ${v.sectionLabel ?? v.section ?? 'None (no TDS deducted)'}', style: const TextStyle(fontSize: 13)),
          for (final i in v.issues)
            Padding(
              padding: const EdgeInsets.only(top: 4),
              child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Icon(i.code == 'no_pan' ? Icons.info_outline_rounded : Icons.warning_amber_rounded,
                    size: 15, color: i.code == 'no_pan' ? AppTheme.textSecondary : AppTheme.warning),
                const SizedBox(width: 6),
                Expanded(child: Text(i.message, style: const TextStyle(fontSize: 12, height: 1.3))),
              ]),
            ),
          if (v.canFix)
            Padding(
              padding: const EdgeInsets.only(top: 6),
              child: Text(
                  'Suggested: ${[
                    if (v.suggestedConstitutionLabel != null) v.suggestedConstitutionLabel!,
                    if (v.suggestedSectionLabel != null) v.suggestedSectionLabel!,
                  ].join(' · ')}',
                  style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: AppTheme.primary)),
            ),
          if (committee) ...[
            const SizedBox(height: 10),
            Wrap(spacing: 8, runSpacing: 8, children: [
              if (v.canFix)
                FilledButton.icon(
                  onPressed: busy ? null : onFix,
                  icon: const Icon(Icons.check_rounded, size: 18),
                  label: const Text('Apply suggestion'),
                ),
              OutlinedButton.icon(
                onPressed: busy ? null : onEdit,
                icon: const Icon(Icons.edit_outlined, size: 18),
                label: const Text('Set type and section'),
              ),
            ]),
          ],
        ]),
      ),
    );
  }
}

/// Choose a vendor's type and TDS section by hand. Pops (type, section).
class _EditTdsSheet extends ConsumerStatefulWidget {
  final TdsReviewRow vendor;
  const _EditTdsSheet({required this.vendor});

  @override
  ConsumerState<_EditTdsSheet> createState() => _EditTdsSheetState();
}

class _EditTdsSheetState extends ConsumerState<_EditTdsSheet> {
  late String? _constitution = widget.vendor.constitution ?? widget.vendor.suggestedConstitution;
  late String? _section = widget.vendor.section ?? widget.vendor.suggestedSection;

  @override
  Widget build(BuildContext context) {
    final options = ref.watch(tdsOptionsProvider);
    return AppSheetFrame(
      title: widget.vendor.name,
      subtitle: widget.vendor.pan == null || widget.vendor.pan!.isEmpty ? 'No PAN' : 'PAN ${widget.vendor.pan}',
      child: options.when(
        loading: () => const LinearProgressIndicator(),
        error: (e, _) => Text(friendlyErrorMessage(e)),
        data: (o) => Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          FormFieldBox(
            label: 'Type of vendor',
            child: DropdownButtonFormField<String?>(
              initialValue: _constitution,
              isExpanded: true,
              items: [
                for (final c in o.constitutions) DropdownMenuItem<String?>(value: c.$1, child: Text(c.$2)),
              ],
              onChanged: (v) => setState(() => _constitution = v),
            ),
          ),
          FormFieldBox(
            label: 'Usually paid under',
            child: DropdownButtonFormField<String?>(
              initialValue: _section,
              isExpanded: true,
              items: [
                for (final s in o.sections) DropdownMenuItem<String?>(value: s.$1, child: Text(s.$2, overflow: TextOverflow.ellipsis)),
              ],
              onChanged: (v) => setState(() => _section = v),
            ),
          ),
          const SizedBox(height: 8),
          FilledButton(
            onPressed: _constitution == null
                ? null
                : () => Navigator.of(context).pop<({String? constitution, String? section})>(
                    (constitution: _constitution, section: _section)),
            child: const Text('Save'),
          ),
        ]),
      ),
    );
  }
}
