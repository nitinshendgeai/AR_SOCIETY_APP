import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/maintenance_billing/data/maintenance_billing_api.dart';
import 'package:ar_society_app/features/maintenance_billing/presentation/providers/maintenance_billing_providers.dart';
import 'package:ar_society_app/features/maintenance_billing/presentation/screens/maintenance_bill_detail_screen.dart';
import 'package:ar_society_app/features/maintenance_billing/presentation/screens/cycle_preview_screen.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';

enum _BillFilter { all, unpaid, overdue, paid, notIssued }

class BillingCycleScreen extends ConsumerStatefulWidget {
  final String cycleId;
  final String societyId;
  const BillingCycleScreen({super.key, required this.cycleId, required this.societyId});

  @override
  ConsumerState<BillingCycleScreen> createState() => _BillingCycleScreenState();
}

class _BillingCycleScreenState extends ConsumerState<BillingCycleScreen> {
  _BillFilter _filter = _BillFilter.all;
  String _search = '';
  bool _busy = false;

  void _refresh() => invalidateCycle(ref, widget.societyId, widget.cycleId);

  Future<bool> _confirm(String title, String body, String action) async =>
      await showDialog<bool>(
        context: context,
        builder: (ctx) => AlertDialog(
          title: Text(title),
          content: Text(body),
          actions: [
            TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancel')),
            ElevatedButton(onPressed: () => Navigator.pop(ctx, true), child: Text(action)),
          ],
        ),
      ) ==
      true;

  Future<void> _generate() async {
    final List<ChargeHead> charges;
    try {
      charges = await ref.read(maintenanceBillingApiProvider).listChargeHeads(widget.societyId);
    } catch (e) {
      if (mounted) showErrorToast(context, e);
      return;
    }
    if (!mounted) return;
    if (charges.isEmpty) {
      AppToast.warning(context, 'Add charge heads first — Maintenance Billing → Charge Heads');
      return;
    }
    final cycle = ref.read(billingCycleProvider(widget.cycleId)).valueOrNull;
    final generated = await Navigator.push<bool>(context, MaterialPageRoute(
      builder: (_) => CyclePreviewScreen(cycleId: widget.cycleId, cycleName: cycle?.name ?? 'Cycle'),
    ));
    if (generated == true) _refresh();
  }

  Future<void> _issueAll(int count) async {
    final ok = await _confirm(
      'Issue $count bills?',
      'Residents will be notified and can see their bill in the app.',
      'Issue All',
    );
    if (!ok) return;
    await _run(() async {
      final n = await ref.read(maintenanceBillingApiProvider).issueAll(widget.cycleId);
      if (mounted) AppToast.success(context, '$n bills issued to residents');
    });
  }

  Future<void> _run(Future<void> Function() action) async {
    setState(() => _busy = true);
    try {
      await action();
      _refresh();
    } catch (e) {
      if (mounted) showErrorToast(context, e);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  bool _matches(MaintenanceBill b) {
    final passes = switch (_filter) {
      _BillFilter.all => true,
      _BillFilter.unpaid => !b.isPaid && !b.isCancelled && !b.isGenerated,
      _BillFilter.overdue => b.isOverdue,
      _BillFilter.paid => b.isPaid,
      _BillFilter.notIssued => b.isGenerated,
    };
    if (!passes) return false;
    if (_search.isEmpty) return true;
    final q = _search.toLowerCase();
    return b.flatLabel.toLowerCase().contains(q) ||
        (b.residentName?.toLowerCase().contains(q) ?? false) ||
        b.invoiceNumber.toLowerCase().contains(q);
  }

  @override
  Widget build(BuildContext context) {
    final cycleAsync = ref.watch(billingCycleProvider(widget.cycleId));
    final billsAsync = ref.watch(cycleBillsProvider(widget.cycleId));
    final cycle = cycleAsync.valueOrNull;

    return Scaffold(
      backgroundColor: AppTheme.surface,
      appBar: AppBar(
        title: Text(cycle?.name ?? 'Billing Cycle'),
        actions: [IconButton(icon: const Icon(Icons.refresh_rounded), onPressed: _refresh)],
      ),
      bottomNavigationBar: cycle == null ? null : _actionBar(cycle),
      body: cycleAsync.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (e, _) => Center(
            child: Text(friendlyErrorMessage(e), style: const TextStyle(color: AppTheme.error))),
        data: (cycle) => RefreshIndicator(
          onRefresh: () async => _refresh(),
          child: CustomScrollView(slivers: [
            SliverPadding(
              padding: const EdgeInsets.fromLTRB(16, 16, 16, 0),
              sliver: SliverToBoxAdapter(child: _Header(cycle: cycle)),
            ),
            if (!cycle.isFinalized)
              const SliverFillRemaining(
                hasScrollBody: false,
                child: AppEmptyState(
                  icon: Icons.post_add_rounded,
                  title: 'No bills yet',
                  subtitle: 'Calculate bills to preview each flat\'s amount from your charge heads and rules, then generate.',
                ),
              )
            else ...[
              SliverToBoxAdapter(child: _filters()),
              ...billsAsync.when<List<Widget>>(
                loading: () => [
                  const SliverFillRemaining(child: Center(child: CircularProgressIndicator())),
                ],
                error: (e, _) => [
                  SliverFillRemaining(
                    child: Center(child: Text(friendlyErrorMessage(e),
                        style: const TextStyle(color: AppTheme.error))),
                  ),
                ],
                data: (bills) {
                  final shown = bills.where(_matches).toList();
                  if (shown.isEmpty) {
                    return [
                      const SliverFillRemaining(
                        hasScrollBody: false,
                        child: AppEmptyState(icon: Icons.search_off_rounded, title: 'No bills match'),
                      ),
                    ];
                  }
                  return [
                    SliverPadding(
                      padding: const EdgeInsets.fromLTRB(16, 4, 16, 24),
                      sliver: SliverList.builder(
                        itemCount: shown.length,
                        itemBuilder: (_, i) => BillTile(
                          bill: shown[i],
                          showFlat: true,
                          onTap: () async {
                            await Navigator.push(context, MaterialPageRoute(
                              builder: (_) => MaintenanceBillDetailScreen(
                                billId: shown[i].id, societyId: widget.societyId, canManage: true),
                            ));
                            _refresh();
                          },
                        ),
                      ),
                    ),
                  ];
                },
              ),
            ],
          ]),
        ),
      ),
    );
  }

  Widget? _actionBar(BillingCycle cycle) {
    if (!cycle.isFinalized) {
      return _bar('Calculate & Preview Bills', Icons.calculate_rounded, _generate);
    }
    if (cycle.awaitingIssue) {
      return _bar('Issue ${cycle.generatedCount} Bills to Residents', Icons.send_rounded,
          () => _issueAll(cycle.generatedCount));
    }
    return null;
  }

  Widget _bar(String label, IconData icon, VoidCallback onPressed) => SafeArea(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(16, 8, 16, 12),
          child: ElevatedButton.icon(
            onPressed: _busy ? null : onPressed,
            icon: _busy
                ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2))
                : Icon(icon),
            label: Text(label),
          ),
        ),
      );

  Widget _filters() => Column(children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 16, 16, 4),
          child: TextField(
            decoration: const InputDecoration(
              prefixIcon: Icon(Icons.search_rounded),
              hintText: 'Search flat, resident or bill no.',
              isDense: true,
            ),
            onChanged: (v) => setState(() => _search = v.trim()),
          ),
        ),
        SizedBox(
          height: 48,
          child: ListView(
            scrollDirection: Axis.horizontal,
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
            children: [
              for (final (f, label) in const [
                (_BillFilter.all, 'All'),
                (_BillFilter.unpaid, 'Unpaid'),
                (_BillFilter.overdue, 'Overdue'),
                (_BillFilter.paid, 'Paid'),
                (_BillFilter.notIssued, 'Not Issued'),
              ])
                Padding(
                  padding: const EdgeInsets.only(right: 8),
                  child: ChoiceChip(
                    label: Text(label, style: const TextStyle(fontSize: 12)),
                    selected: _filter == f,
                    onSelected: (_) => setState(() => _filter = f),
                  ),
                ),
            ],
          ),
        ),
      ]);
}

class _Header extends StatelessWidget {
  final BillingCycle cycle;
  const _Header({required this.cycle});

  @override
  Widget build(BuildContext context) {
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Text(
        '${formatBillDate(cycle.cycleStart)} – ${formatBillDate(cycle.cycleEnd)} · Due ${formatBillDate(cycle.dueDate)}',
        style: const TextStyle(color: AppTheme.textSecondary, fontSize: 13),
      ),
      if (cycle.isFinalized) ...[
        const SizedBox(height: 12),
        KpiGrid(cards: [
          KpiCard(icon: Icons.receipt_long_rounded, label: 'Billed',
              value: formatRupees(cycle.totalBilled), color: AppTheme.primary,
              note: '${cycle.billsCount} flats'),
          KpiCard(icon: Icons.account_balance_wallet_rounded, label: 'Collected',
              value: formatRupees(cycle.totalCollected), color: AppTheme.success,
              note: '${cycle.paidCount} fully paid'),
          KpiCard(icon: Icons.pending_actions_rounded, label: 'Outstanding',
              value: formatRupees(cycle.totalOutstanding), color: AppTheme.warning),
          KpiCard(icon: Icons.warning_amber_rounded, label: 'Overdue',
              value: '${cycle.overdueCount}', color: AppTheme.error, note: 'flats past due'),
        ]),
      ],
    ]);
  }
}

/// One bill row — shared by the society's cycle view (showFlat) and the
/// resident's My Bills list (shows the cycle name instead).
class BillTile extends StatelessWidget {
  final MaintenanceBill bill;
  final bool showFlat;
  final VoidCallback onTap;
  const BillTile({super.key, required this.bill, required this.onTap, this.showFlat = false});

  @override
  Widget build(BuildContext context) {
    final status = bill.displayStatus;
    final color = billStatusColor(status);
    final title = showFlat ? bill.flatLabel : (bill.cycleName ?? bill.invoiceNumber);
    final subtitle = showFlat
        ? [if (bill.residentName != null) bill.residentName!, bill.invoiceNumber].join(' · ')
        : '${bill.invoiceNumber} · Due ${formatBillDate(bill.dueDate)}';
    final showBalance = !bill.isPaid && !bill.isCancelled && amountOf(bill.outstanding) > 0;

    return Card(
      margin: const EdgeInsets.only(bottom: 10),
      child: ListTile(
        onTap: onTap,
        title: Text(title, style: const TextStyle(fontWeight: FontWeight.w600)),
        subtitle: Text(subtitle, maxLines: 1, overflow: TextOverflow.ellipsis),
        trailing: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          crossAxisAlignment: CrossAxisAlignment.end,
          children: [
            Text(
              formatRupees(showBalance ? bill.outstanding : bill.totalAmount),
              style: const TextStyle(fontWeight: FontWeight.w700),
            ),
            const SizedBox(height: 4),
            Text(billStatusLabel(status),
                style: TextStyle(fontSize: 11, fontWeight: FontWeight.w600, color: color)),
          ],
        ),
      ),
    );
  }
}

Color billStatusColor(String status) => switch (status) {
      'paid' => AppTheme.success,
      'overdue' => AppTheme.error,
      'partially_paid' => AppTheme.warning,
      'issued' => AppTheme.primary,
      _ => AppTheme.textSecondary,
    };
