import 'package:flutter/material.dart';
import 'package:ar_society_app/shared/widgets/premium.dart';
import 'package:ar_society_app/core/motion/loading.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/core/theme/design_tokens.dart' show AppTone, kToneColors;
import 'package:ar_society_app/features/maintenance_billing/data/maintenance_billing_api.dart';
import 'package:ar_society_app/features/maintenance_billing/presentation/providers/maintenance_billing_providers.dart';
import 'package:ar_society_app/features/maintenance_billing/presentation/screens/billing_cycle_screen.dart'
    show BillTile, billStatusColor;
import 'package:ar_society_app/features/maintenance_billing/presentation/screens/maintenance_bill_detail_screen.dart';
import 'package:ar_society_app/features/maintenance_billing/presentation/widgets/pay_widgets.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';
import 'package:ar_society_app/shared/widgets/app_data_table.dart';
import 'package:ar_society_app/core/layout/app_shell.dart' show isDesktopLayout;
import 'package:ar_society_app/shared/widgets/app_form.dart';
import 'package:ar_society_app/features/resident_master/data/models/resident_master_models.dart';
import 'package:ar_society_app/features/resident_master/presentation/providers/resident_master_providers.dart' show myFlatsProvider;
import 'package:ar_society_app/features/society_structure/presentation/providers/structure_providers.dart' show flatByIdProvider;

/// When a bill is due, in the words a resident would use ("Overdue by 4 days", "Due today", "Due in 3 days").
/// Null for a bill that is settled or cancelled. [today] is passed in so the wording can be tested.
({String text, Color color})? billDueNote(MaintenanceBill b, DateTime today) {
  if (b.isPaid || b.isCancelled || amountOf(b.outstanding) <= 0) return null;
  final days = DateTime(b.dueDate.year, b.dueDate.month, b.dueDate.day)
      .difference(DateTime(today.year, today.month, today.day))
      .inDays;
  final part = amountOf(b.paidAmount) > 0 ? '  ·  ${formatRupees(b.paidAmount)} paid' : '';
  if (days < 0) {
    final n = -days;
    return (text: 'Overdue by $n day${n == 1 ? '' : 's'}$part', color: kToneColors[AppTone.danger]!.foreground);
  }
  if (days == 0) return (text: 'Due today$part', color: kToneColors[AppTone.warning]!.foreground);
  return (text: 'Due in $days day${days == 1 ? '' : 's'}$part', color: days <= 7 ? kToneColors[AppTone.warning]!.foreground : AppTheme.textSecondary);
}

/// Resident view: every issued bill for the flat(s) they live in.
class MyBillsScreen extends ConsumerWidget {
  const MyBillsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final flatFilter = ref.watch(myBillsFlatFilterProvider);
    final billsAsync = flatFilter == null ? ref.watch(myBillsProvider) : ref.watch(myBillsForFlatProvider(flatFilter));
    final myFlats = ref.watch(myFlatsProvider).valueOrNull ?? const [];
    return AppPage(
      title: 'My Bills',
      body: RefreshIndicator(
        onRefresh: () async {
          ref.invalidate(myBillsProvider);
          ref.invalidate(myBillsForFlatProvider);
        },
        child: billsAsync.when(
          loading: () => const SkeletonList(),
          error: (e, _) => AppErrorState(
              message: friendlyErrorMessage(e),
              onRetry: () {
                ref.invalidate(myBillsProvider);
                ref.invalidate(myBillsForFlatProvider);
              }),
          data: (summary) {
            final open = summary.bills.where((b) => amountOf(b.outstanding) > 0).toList();
            final settled = summary.bills.where((b) => amountOf(b.outstanding) <= 0).toList();
            final overdue = open.where((b) => b.displayStatus == 'overdue').toList();
            final upcoming = open.where((b) => b.displayStatus != 'overdue').toList();
            return ListView(
              padding: const EdgeInsets.all(16),
              children: [
                // A resident with several flats can look at all of them together or one at a time.
                if (myFlats.length > 1) ...[
                  _FlatFilter(flats: myFlats, selected: flatFilter),
                  const SizedBox(height: 14),
                ],
                _DueHero(summary: summary, open: open),
                const SizedBox(height: 16),
                const PaymentClaimsStrip(),
                const SizedBox(height: 20),
                if (isDesktopLayout(context) && summary.bills.isNotEmpty)
                  AppDataTable<MaintenanceBill>(
                    rows: [...open, ...settled],
                    onRowTap: (b) => _openBill(context, b),
                    columns: [
                      AppDataColumn.text('Bill no.', (b) => b.invoiceNumber, flex: 2, bold: true),
                      AppDataColumn.text('Period', (b) => b.cycleName ?? '—', flex: 3),
                      AppDataColumn.text('Flat', (b) => b.flatLabel, flex: 2),
                      AppDataColumn.text('Due', (b) => formatBillDate(b.dueDate),
                          flex: 2, sortKey: (b) => b.dueDate.millisecondsSinceEpoch),
                      AppDataColumn.text('Total', (b) => formatRupees(b.totalAmount),
                          flex: 2, numeric: true, sortKey: (b) => amountOf(b.totalAmount)),
                      AppDataColumn.text('Outstanding', (b) => formatRupees(b.outstanding),
                          flex: 2, numeric: true, bold: true, sortKey: (b) => amountOf(b.outstanding)),
                      AppDataColumn(
                        label: 'Status',
                        flex: 2,
                        sortKey: (b) => billStatusLabel(b.displayStatus),
                        cell: (b) => StatusPill(billStatusLabel(b.displayStatus), billStatusColor(b.displayStatus)),
                      ),
                    ],
                  )
                else ...[
                  if (summary.bills.isEmpty)
                    const Padding(
                      padding: EdgeInsets.only(top: 40),
                      child: AppEmptyState(
                        icon: Icons.receipt_long_rounded,
                        title: 'No bills yet',
                        subtitle: 'Your maintenance bills will appear here once the society issues them.',
                      ),
                    ),
                  if (overdue.isNotEmpty) ...[
                    const _Heading('Overdue'),
                    for (final b in overdue) _tile(context, b),
                    const SizedBox(height: 12),
                  ],
                  if (upcoming.isNotEmpty) ...[
                    const _Heading('To Pay'),
                    for (final b in upcoming) _tile(context, b),
                    const SizedBox(height: 12),
                  ],
                  if (settled.isNotEmpty) ...[
                    const _Heading('History'),
                    for (final b in settled) _tile(context, b),
                  ],
                ],
              ],
            );
          },
        ),
      ),
    );
  }

  void _openBill(BuildContext context, MaintenanceBill bill) => Navigator.push(
      context,
      MaterialPageRoute(
        builder: (_) => MaintenanceBillDetailScreen(billId: bill.id),
      ));

  Widget _tile(BuildContext context, MaintenanceBill bill) {
    final note = billDueNote(bill, DateTime.now());
    return BillTile(bill: bill, onTap: () => _openBill(context, bill), note: note?.text, noteColor: note?.color);
  }
}

/// The first thing a resident sees: how much is due, how many bills, and when the next one falls due.
class _DueHero extends StatelessWidget {
  final MyBillsSummary summary;
  final List<MaintenanceBill> open;
  const _DueHero({required this.summary, required this.open});

  @override
  Widget build(BuildContext context) {
    final clear = summary.openCount == 0;
    final color = clear ? AppTheme.success : (summary.overdueCount > 0 ? AppTheme.error : AppTheme.primary);
    // The words use the readable tone of the same meaning; the bright colour stays for the icon and the tinted fill.
    final textColor = kToneColors[clear ? AppTone.success : (summary.overdueCount > 0 ? AppTone.danger : AppTone.info)]!.foreground;
    final soonest = ([...open]..sort((a, b) => a.dueDate.compareTo(b.dueDate))).firstOrNull;
    final next = soonest == null ? null : billDueNote(soonest, DateTime.now());
    return Semantics(
      container: true,
      label: clear
          ? 'All bills paid'
          : 'Total due ${formatRupees(summary.totalOutstanding)} on ${summary.openCount} bills',
      child: Container(
        width: double.infinity,
        padding: const EdgeInsets.all(18),
        decoration: BoxDecoration(
          color: solidTint(color),
          borderRadius: BorderRadius.circular(AppTheme.radiusL),
          boxShadow: AppTheme.cardShadow,
        ),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            Icon(clear ? Icons.check_circle_rounded : Icons.account_balance_wallet_rounded, color: color, size: 20),
            const SizedBox(width: 8),
            Text(clear ? 'You are all paid up' : 'Total due',
                style: TextStyle(fontSize: 13, fontWeight: FontWeight.w700, color: textColor)),
          ]),
          if (!clear) ...[
            const SizedBox(height: 6),
            Text(formatRupees(summary.totalOutstanding),
                style: const TextStyle(fontSize: 30, fontWeight: FontWeight.w800, color: AppTheme.textPrimary)),
            const SizedBox(height: 4),
            Text(
              '${summary.openCount} unpaid bill${summary.openCount == 1 ? '' : 's'}'
              '${summary.overdueCount > 0 ? '  ·  ${summary.overdueCount} overdue' : ''}',
              style: const TextStyle(fontSize: 13, color: AppTheme.textSecondary),
            ),
            if (next != null) ...[
              const SizedBox(height: 4),
              Text('Next: ${next.text}', style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: next.color)),
            ],
            const SizedBox(height: 10),
            const Text(
              'Pay the society, then tell the office. Your bill is marked paid and the receipt appears on it once they have checked the payment.',
              style: TextStyle(fontSize: 12, color: AppTheme.textSecondary, height: 1.4),
            ),
            const SizedBox(height: 10),
            Row(children: [
              Expanded(
                child: ElevatedButton.icon(
                  key: const Key('how-to-pay'),
                  onPressed: () => showHowToPaySheet(context, bill: open.length == 1 ? open.first : null),
                  icon: const Icon(Icons.payments_rounded, size: 18),
                  label: const Text('Pay now'),
                ),
              ),
            ]),
          ],
        ]),
      ),
    );
  }
}

class _Heading extends StatelessWidget {
  final String text;
  const _Heading(this.text);

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.only(bottom: 8),
        child: SectionHeading(text),
      );
}

/// "All flats" / one chip per flat the resident lives in.
class _FlatFilter extends ConsumerWidget {
  final List<ResidentModel> flats;
  final String? selected;
  const _FlatFilter({required this.flats, required this.selected});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    void pick(String? id) => ref.read(myBillsFlatFilterProvider.notifier).state = id;
    return Wrap(spacing: 8, runSpacing: 8, children: [
      ChoiceChip(label: const Text('All my flats'), selected: selected == null, onSelected: (_) => pick(null)),
      for (final f in flats)
        Consumer(builder: (context, ref, _) {
          final flat = ref.watch(flatByIdProvider(f.flatId)).valueOrNull;
          return ChoiceChip(
            label: Text(flat?.displayName ?? 'Flat'),
            selected: selected == f.flatId,
            onSelected: (_) => pick(f.flatId),
          );
        }),
    ]);
  }
}
