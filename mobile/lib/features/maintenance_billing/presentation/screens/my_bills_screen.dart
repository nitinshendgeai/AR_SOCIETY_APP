import 'package:flutter/material.dart';
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

/// Resident view: every issued bill for the flat(s) they live in.
class MyBillsScreen extends ConsumerWidget {
  const MyBillsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final billsAsync = ref.watch(myBillsProvider);
    return Scaffold(
      backgroundColor: AppTheme.surface,
      appBar: AppBar(title: const Text('My Bills')),
      body: RefreshIndicator(
        onRefresh: () async => ref.invalidate(myBillsProvider),
        child: billsAsync.when(
          loading: () => const Center(child: CircularProgressIndicator()),
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
