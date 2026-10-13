import 'package:flutter/material.dart';
import 'package:ar_society_app/core/motion/loading.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/maintenance_billing/data/maintenance_billing_api.dart';
import 'package:ar_society_app/features/maintenance_billing/presentation/providers/maintenance_billing_providers.dart';
import 'package:ar_society_app/features/maintenance_billing/presentation/screens/billing_cycle_screen.dart'
    show BillTile, billStatusColor;
import 'package:ar_society_app/features/maintenance_billing/presentation/screens/maintenance_bill_detail_screen.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';
import 'package:ar_society_app/shared/widgets/app_data_table.dart';
import 'package:ar_society_app/core/layout/app_shell.dart' show isDesktopLayout;
import 'package:ar_society_app/shared/widgets/app_form.dart';
import 'package:ar_society_app/features/resident_master/data/models/resident_master_models.dart';
import 'package:ar_society_app/features/resident_master/presentation/providers/resident_master_providers.dart' show myFlatsProvider;
import 'package:ar_society_app/features/society_structure/presentation/providers/structure_providers.dart' show flatByIdProvider;

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
          error: (e, _) => ListView(children: [
            Padding(
              padding: const EdgeInsets.all(24),
              child: Text(friendlyErrorMessage(e), style: const TextStyle(color: AppTheme.error)),
            ),
          ]),
          data: (summary) {
            final open = summary.bills.where((b) => amountOf(b.outstanding) > 0).toList();
            final settled = summary.bills.where((b) => amountOf(b.outstanding) <= 0).toList();
            return ListView(
              padding: const EdgeInsets.all(16),
              children: [
                // A resident with several flats can look at all of them together or one at a time.
                if (myFlats.length > 1) ...[
                  _FlatFilter(flats: myFlats, selected: flatFilter),
                  const SizedBox(height: 14),
                ],
                KpiGrid(cards: [
                  KpiCard(
                    icon: Icons.account_balance_wallet_rounded,
                    label: 'Total Due',
                    value: formatRupees(summary.totalOutstanding),
                    color: summary.overdueCount > 0 ? AppTheme.error : AppTheme.warning,
                    note: summary.overdueCount > 0 ? '${summary.overdueCount} overdue' : null,
                  ),
                  KpiCard(
                    icon: Icons.receipt_long_rounded,
                    label: 'Unpaid Bills',
                    value: '${summary.openCount}',
                    color: AppTheme.primary,
                  ),
                ]),
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
                  if (open.isNotEmpty) ...[
                    const _Heading('To Pay'),
                    for (final b in open) _tile(context, b),
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

  Widget _tile(BuildContext context, MaintenanceBill bill) => BillTile(
        bill: bill,
        onTap: () => _openBill(context, bill),
      );
}

class _Heading extends StatelessWidget {
  final String text;
  const _Heading(this.text);

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.only(bottom: 8),
        child: Text(text,
            style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w700, color: AppTheme.textSecondary)),
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
