import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/maintenance_billing/data/maintenance_billing_api.dart';
import 'package:ar_society_app/features/maintenance_billing/presentation/providers/maintenance_billing_providers.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';

/// Shows exactly what Generate Bills will create — every flat's lines as
/// calculated from the charge heads and rules — before anything is saved.
/// Pops `true` once bills are generated.
class CyclePreviewScreen extends ConsumerStatefulWidget {
  final String cycleId;
  final String cycleName;
  const CyclePreviewScreen({super.key, required this.cycleId, required this.cycleName});

  @override
  ConsumerState<CyclePreviewScreen> createState() => _CyclePreviewScreenState();
}

class _CyclePreviewScreenState extends ConsumerState<CyclePreviewScreen> {
  bool _generating = false;
  String _search = '';

  Future<void> _generate(int count) async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text('Generate $count bills?'),
        content: const Text('Bills are created as shown. Residents won\'t see them until you issue them.'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancel')),
          ElevatedButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('Generate')),
        ],
      ),
    );
    if (ok != true) return;
    setState(() => _generating = true);
    try {
      final n = await ref.read(maintenanceBillingApiProvider).generateBills(widget.cycleId);
      if (mounted) {
        AppToast.success(context, '$n bills generated — review, then issue them');
        Navigator.pop(context, true);
      }
    } catch (e) {
      if (mounted) showErrorToast(context, e);
    } finally {
      if (mounted) setState(() => _generating = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final previewAsync = ref.watch(cyclePreviewProvider(widget.cycleId));
    final preview = previewAsync.valueOrNull;

    return Scaffold(
      backgroundColor: AppTheme.surface,
      appBar: AppBar(title: Text('Preview · ${widget.cycleName}')),
      bottomNavigationBar: preview == null || preview.flatsCount == 0
          ? null
          : SafeArea(
              child: Padding(
                padding: const EdgeInsets.fromLTRB(16, 8, 16, 12),
                child: ElevatedButton.icon(
                  onPressed: _generating ? null : () => _generate(preview.flatsCount),
                  icon: _generating
                      ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2))
                      : const Icon(Icons.auto_awesome_rounded),
                  label: Text('Generate ${preview.flatsCount} Bills'),
                ),
              ),
            ),
      body: previewAsync.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (e, _) => Center(
          child: Padding(
            padding: const EdgeInsets.all(24),
            child: Text(friendlyErrorMessage(e), style: const TextStyle(color: AppTheme.error)),
          ),
        ),
        data: (p) {
          final q = _search.toLowerCase();
          final flats = q.isEmpty ? p.flats : p.flats.where((f) => f.flatLabel.toLowerCase().contains(q)).toList();
          final avg = p.flatsCount > 0 ? amountOf(p.total) / p.flatsCount : 0.0;
          return RefreshIndicator(
            onRefresh: () async => ref.invalidate(cyclePreviewProvider(widget.cycleId)),
            child: ListView(
              padding: const EdgeInsets.all(16),
              children: [
                KpiGrid(cards: [
                  KpiCard(
                    icon: Icons.receipt_long_rounded,
                    label: 'Total to bill',
                    value: formatRupees(p.total),
                    color: AppTheme.primary,
                    note: p.months == 1 ? '1 month' : '${p.months} months',
                  ),
                  KpiCard(
                    icon: Icons.home_work_rounded,
                    label: 'Flats',
                    value: '${p.flatsCount}',
                    color: AppTheme.success,
                    note: 'avg ${formatRupees('$avg')}',
                  ),
                ]),
                for (final w in p.warnings) ...[
                  const SizedBox(height: 10),
                  Container(
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color: AppTheme.warningSoft,
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                      const Icon(Icons.warning_amber_rounded, color: AppTheme.warning, size: 20),
                      const SizedBox(width: 10),
                      Expanded(child: Text(w, style: const TextStyle(fontSize: 13))),
                    ]),
                  ),
                ],
                const SizedBox(height: 16),
                if (p.flats.length > 6) ...[
                  TextField(
                    decoration: const InputDecoration(
                      prefixIcon: Icon(Icons.search_rounded),
                      hintText: 'Search flat',
                      isDense: true,
                    ),
                    onChanged: (v) => setState(() => _search = v.trim()),
                  ),
                  const SizedBox(height: 12),
                ],
                if (p.flats.isEmpty)
                  const Padding(
                    padding: EdgeInsets.only(top: 32),
                    child: AppEmptyState(
                      icon: Icons.calculate_outlined,
                      title: 'Nothing to bill',
                      subtitle: 'Check the warnings above, your charge heads, and flat areas.',
                    ),
                  ),
                for (final f in flats) _FlatPreviewCard(flat: f),
              ],
            ),
          );
        },
      ),
    );
  }
}

class _FlatPreviewCard extends StatelessWidget {
  final FlatPreview flat;
  const _FlatPreviewCard({required this.flat});

  @override
  Widget build(BuildContext context) {
    final meta = [
      if (flat.areaSqft != null) '${flat.areaSqft!.toStringAsFixed(0)} sq ft',
      if (flat.occupancy == 'tenant_occupied') 'Let out',
      if (amountOf(flat.previousDues) > 0) 'Arrears ${formatRupees(flat.previousDues)}',
    ];
    return Card(
      margin: const EdgeInsets.only(bottom: 10),
      clipBehavior: Clip.antiAlias,
      child: ExpansionTile(
        title: Text(flat.flatLabel, style: const TextStyle(fontWeight: FontWeight.w600)),
        subtitle: meta.isEmpty ? null : Text(meta.join(' · '), style: const TextStyle(fontSize: 12)),
        trailing: Text(formatRupees(flat.total), style: const TextStyle(fontWeight: FontWeight.w700)),
        childrenPadding: const EdgeInsets.fromLTRB(16, 0, 16, 12),
        children: [
          for (final l in flat.lines)
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 4),
              child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Expanded(
                  child: Text(
                    amountOf(l.taxAmount) > 0
                        ? '${l.description}\n+ ${formatRupees(l.taxAmount)} GST/tax'
                        : l.description,
                    style: const TextStyle(fontSize: 13),
                  ),
                ),
                Text(formatRupees(l.total), style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w500)),
              ]),
            ),
          const Divider(height: 16),
          Row(children: [
            const Expanded(child: Text('This bill', style: TextStyle(fontWeight: FontWeight.w700))),
            Text(formatRupees(flat.total), style: const TextStyle(fontWeight: FontWeight.w700)),
          ]),
        ],
      ),
    );
  }
}
