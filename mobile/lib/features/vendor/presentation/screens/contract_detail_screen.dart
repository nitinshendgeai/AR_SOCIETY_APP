import 'package:flutter/material.dart';
import 'package:ar_society_app/core/motion/loading.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/layout/app_sheet.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/features/maintenance_billing/data/maintenance_billing_api.dart' show formatBillDate, formatRupees;
import 'package:ar_society_app/features/vendor/data/vendors_work_api.dart';
import 'package:ar_society_app/features/vendor/presentation/providers/vendors_work_providers.dart';
import 'package:ar_society_app/features/vendor/presentation/widgets/procurement_widgets.dart';
import 'package:ar_society_app/shared/widgets/app_data_table.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';

/// An annual maintenance contract: quotations, the sanction, then it starts.
class ContractDetailScreen extends ConsumerStatefulWidget {
  final String contractId;
  const ContractDetailScreen({super.key, required this.contractId});

  @override
  ConsumerState<ContractDetailScreen> createState() => _ContractDetailScreenState();
}

class _ContractDetailScreenState extends ConsumerState<ContractDetailScreen> {
  bool _busy = false;

  VendorsWorkApi get _api => ref.read(vendorsWorkApiProvider);

  void _refresh() {
    ref.invalidate(contractProvider(widget.contractId));
    final sid = ref.read(currentUserProvider)?.societyId;
    if (sid != null) ref.invalidate(contractsProvider(sid));
  }

  Future<void> _run(Future<void> Function() call, String done) async {
    setState(() => _busy = true);
    try {
      await call();
      _refresh();
      if (mounted) AppToast.success(context, done);
    } catch (e) {
      if (mounted) showErrorToast(context, e);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _addQuotation(AmcContract c, String societyId) async {
    final vendors = await ref.read(vendorRecordsProvider(societyId).future);
    if (!mounted) return;
    showAppSheet(
      context: context,
      builder: (_) => QuotationSheet(
        vendors: vendors,
        alreadyQuoted: {for (final q in c.quotations) q.vendorId},
        onSave: (q) async {
          await _api.addContractQuotation(c.id, q);
          _refresh();
        },
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final user = ref.watch(currentUserProvider);
    final societyId = user?.societyId ?? '';
    final committee = user?.isAdminOrCommittee ?? false;
    final async = ref.watch(contractProvider(widget.contractId));
    return Scaffold(
      backgroundColor: AppTheme.surface,
      appBar: AppBar(title: Text(async.valueOrNull?.contractNumber ?? 'Contract')),
      body: async.when(
        loading: () => const AppLoader(),
        error: (e, _) => Center(child: Text(friendlyErrorMessage(e), style: const TextStyle(color: AppTheme.error))),
        data: (c) {
          final open = c.isDraft && !c.sanction.isSanctioned;
          return RefreshIndicator(
            onRefresh: () async => _refresh(),
            child: ResponsiveBody(
              maxWidth: 860,
              child: ListView(padding: const EdgeInsets.all(16), children: [
                Card(
                  margin: EdgeInsets.zero,
                  child: Padding(
                    padding: const EdgeInsets.all(16),
                    child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
                      Row(children: [
                        Expanded(
                            child: Text(c.contractName,
                                style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w700))),
                        StatusPill(c.statusLabel, c.status == 'active' ? AppTheme.success : AppTheme.warning),
                      ]),
                      const SizedBox(height: 6),
                      Text([
                        vendorCategoryLabel(c.category),
                        kServiceFrequencies.firstWhere((f) => f.$1 == c.serviceFrequency, orElse: () => (c.serviceFrequency, c.serviceFrequency)).$2,
                        '${formatBillDate(c.startDate)} – ${formatBillDate(c.endDate)}',
                      ].join(' · '), style: const TextStyle(color: AppTheme.textSecondary)),
                      const SizedBox(height: 8),
                      InfoLine('Vendor', c.vendorName ?? '—'),
                      if (c.annualValue != null) InfoLine('Annual value', formatRupees(c.annualValue!)),
                      if (c.scopeOfWork != null) InfoLine('Scope', c.scopeOfWork!),
                      const SizedBox(height: 8),
                      Wrap(spacing: 8, runSpacing: 8, children: [
                        if (open)
                          OutlinedButton.icon(
                              onPressed: _busy ? null : () => _addQuotation(c, societyId),
                              icon: const Icon(Icons.add_rounded, size: 18),
                              label: const Text('Add quotation')),
                        if (open && committee && c.quotations.isNotEmpty)
                          FilledButton.icon(
                              onPressed: _busy
                                  ? null
                                  : () => showAppSheet(
                                        context: context,
                                        builder: (_) => SanctionSheet(
                                          what: c.contractNumber,
                                          quotations: c.quotations,
                                          requirements: c.requirements,
                                          onSave: (s) async {
                                            await _api.sanctionContract(c.id, s);
                                            _refresh();
                                          },
                                        ),
                                      ),
                              icon: const Icon(Icons.gavel_rounded, size: 18),
                              label: const Text('Sanction')),
                        if (c.isDraft && c.sanction.isSanctioned && committee)
                          FilledButton.icon(
                              onPressed: _busy ? null : () => _run(() => _api.activateContract(c.id), 'Contract started'),
                              icon: const Icon(Icons.play_arrow_rounded, size: 18),
                              label: const Text('Start contract')),
                      ]),
                    ]),
                  ),
                ),
                if (open) ...[
                  const SizedBox(height: 12),
                  RequirementsBanner(c.requirements),
                ],
                const SizedBox(height: 12),
                Card(
                  margin: EdgeInsets.zero,
                  child: Padding(
                    padding: const EdgeInsets.all(16),
                    child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
                      const Text('Quotations', style: TextStyle(fontSize: 15, fontWeight: FontWeight.w700)),
                      QuotationsList(
                        quotations: c.quotations,
                        onRemove: open
                            ? (q) => _run(() => _api.removeContractQuotation(c.id, q.id), 'Quotation removed')
                            : null,
                      ),
                    ]),
                  ),
                ),
                if (c.sanction.isSanctioned) ...[
                  const SizedBox(height: 12),
                  Card(
                    margin: EdgeInsets.zero,
                    child: Padding(
                      padding: const EdgeInsets.all(16),
                      child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
                        const Text('Sanction', style: TextStyle(fontSize: 15, fontWeight: FontWeight.w700)),
                        const SizedBox(height: 8),
                        SanctionSummary(c.sanction),
                      ]),
                    ),
                  ),
                ],
              ]),
            ),
          );
        },
      ),
    );
  }
}
