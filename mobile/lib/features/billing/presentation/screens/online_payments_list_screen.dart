import 'dart:convert';
import 'dart:io';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:path_provider/path_provider.dart';
import 'package:share_plus/share_plus.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/features/billing/data/repositories/billing_repository.dart';
import 'package:ar_society_app/features/billing/domain/entities/billing_entities.dart';
import 'package:ar_society_app/features/billing/presentation/providers/billing_providers.dart';
import 'package:ar_society_app/features/billing/presentation/screens/online_payment_detail_screen.dart';
import 'package:ar_society_app/features/billing/presentation/screens/online_payment_submit_screen.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';
import 'package:ar_society_app/shared/widgets/app_data_table.dart';
import 'package:ar_society_app/core/layout/app_shell.dart' show isDesktopLayout;

/// FMC Manager/Admin/Committee: list of resident payment screenshots
/// captured for bank reconciliation.
class OnlinePaymentsListScreen extends ConsumerStatefulWidget {
  const OnlinePaymentsListScreen({super.key});

  @override
  ConsumerState<OnlinePaymentsListScreen> createState() => _OnlinePaymentsListScreenState();
}

class _OnlinePaymentsListScreenState extends ConsumerState<OnlinePaymentsListScreen> {
  String? _statusFilter;
  bool _exporting = false;

  Future<void> _exportCsv(String societyId) async {
    setState(() => _exporting = true);
    try {
      final result = await ref.read(billingRepositoryProvider).exportCsv(societyId, status: _statusFilter);
      switch (result) {
        case BillingSuccess(:final data):
          final dir = await getTemporaryDirectory();
          final file = File('${dir.path}/online_payments.csv');
          await file.writeAsBytes(utf8.encode(data));
          await Share.shareXFiles([XFile(file.path)], subject: 'Online Payments — Bank Reconciliation');
        case BillingFailure(:final message):
          throw Exception(message);
      }
    } catch (e) {
      if (mounted) showErrorToast(context, e);
    } finally {
      if (mounted) setState(() => _exporting = false);
    }
  }

  Future<void> _recordPayment() => Navigator.push(context, MaterialPageRoute(
        builder: (_) => const OnlinePaymentSubmitScreen(),
      ));

  void _openPayment(OnlinePaymentEntity p) => Navigator.push(context, MaterialPageRoute(
        builder: (_) => OnlinePaymentDetailScreen(paymentId: p.id),
      ));

  Widget _statusChips() => Wrap(spacing: 8, children: [
        _FilterChip(label: 'All', selected: _statusFilter == null, onTap: () => setState(() => _statusFilter = null)),
        for (final s in const ['pending', 'reconciled', 'rejected'])
          _FilterChip(
            label: reconciliationStatusLabel(s),
            selected: _statusFilter == s,
            onTap: () => setState(() => _statusFilter = s),
          ),
      ]);

  /// Desktop: summary tiles above a sortable payments register.
  Widget _table(String societyId, AsyncValue<List<OnlinePaymentEntity>> paymentsAsync) {
    final payments = paymentsAsync.valueOrNull ?? const <OnlinePaymentEntity>[];
    final rows = _statusFilter == null ? payments : payments.where((p) => p.status == _statusFilter).toList();
    return RefreshIndicator(
      onRefresh: () => ref.read(onlinePaymentsProvider(societyId).notifier).refresh(),
      child: ListView(padding: const EdgeInsets.fromLTRB(24, 8, 24, 32), children: [
        if (paymentsAsync.hasValue) ...[
          KpiGrid(cards: [
            KpiCard(
              icon: Icons.hourglass_top_rounded,
              label: 'Pending Review',
              value: '${payments.where((p) => p.isPending).length}',
              color: AppTheme.warning,
            ),
            KpiCard(
              icon: Icons.verified_rounded,
              label: 'Reconciled',
              value: '${payments.where((p) => p.isReconciled).length}',
              color: AppTheme.success,
            ),
          ]),
          const SizedBox(height: 16),
        ],
        AppDataTable<OnlinePaymentEntity>(
          toolbar: _statusChips(),
          rows: rows,
          loading: paymentsAsync.isLoading && !paymentsAsync.hasValue,
          error: paymentsAsync.hasError ? friendlyErrorMessage(paymentsAsync.error!) : null,
          onRetry: () => ref.read(onlinePaymentsProvider(societyId).notifier).refresh(),
          onRowTap: _openPayment,
          empty: const AppEmptyState(
            icon: Icons.receipt_long_rounded,
            title: 'No payments recorded yet',
            subtitle: 'Use "Record Payment" to add one.',
          ),
          columns: [
            AppDataColumn.text('Receipt', (p) => p.receiptNumber, flex: 2, bold: true),
            AppDataColumn.text('Date', (p) => tableDate(p.paymentDate),
                flex: 2, sortKey: (p) => p.paymentDate.millisecondsSinceEpoch),
            AppDataColumn.text('Flat', (p) => '${p.wingName ?? ''} ${p.flatNumber ?? ''}'.trim().ifEmpty('—')),
            AppDataColumn.text('For',
                (p) => p.isOnBill ? 'Bill ${p.billInvoiceNumber ?? ''}' : onlinePaymentPurposeLabel(p.purpose),
                flex: 2),
            AppDataColumn.text('Mode', (p) => paymentModeLabel(p.paymentMode)),
            AppDataColumn.text('Reference', (p) => p.transactionRef ?? '—', flex: 2),
            AppDataColumn.text('Amount', (p) => tableMoney(p.amount),
                numeric: true, bold: true, sortKey: (p) => double.tryParse(p.amount) ?? 0),
            AppDataColumn(
              label: 'Status',
              sortKey: (p) => p.status,
              cell: (p) => StatusPill(
                reconciliationStatusLabel(p.status),
                switch (p.status) {
                  'reconciled' => AppTheme.success,
                  'rejected' => AppTheme.error,
                  _ => AppTheme.warning,
                },
              ),
            ),
          ],
        ),
      ]),
    );
  }

  @override
  Widget build(BuildContext context) {
    final societyId = ref.watch(currentUserProvider)?.societyId;
    if (societyId == null) {
      return const Scaffold(body: Center(child: Text('No society context')));
    }
    final paymentsAsync = ref.watch(onlinePaymentsProvider(societyId));
    final desktop = isDesktopLayout(context);

    return Scaffold(
      backgroundColor: AppTheme.surface,
      appBar: AppBar(
        title: const Text('Payments'),
        actions: [
          IconButton(
            icon: _exporting
                ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2))
                : const Icon(Icons.ios_share_rounded),
            tooltip: 'Export CSV for bank reconciliation',
            onPressed: _exporting ? null : () => _exportCsv(societyId),
          ),
          IconButton(
            icon: const Icon(Icons.refresh_rounded),
            tooltip: 'Refresh',
            onPressed: () => ref.read(onlinePaymentsProvider(societyId).notifier).refresh(),
          ),
          if (desktop)
            HeaderActionButton(icon: Icons.add_rounded, label: 'Record Payment', onPressed: _recordPayment),
        ],
      ),
      floatingActionButton: desktop
          ? null
          : FloatingActionButton.extended(
              onPressed: _recordPayment,
              icon: const Icon(Icons.add_rounded),
              label: const Text('Record Payment'),
            ),
      body: desktop ? _table(societyId, paymentsAsync) : Column(
        children: [
          paymentsAsync.when(
            loading: () => const SizedBox.shrink(),
            error: (_, __) => const SizedBox.shrink(),
            data: (payments) {
              final pending = payments.where((p) => p.isPending).length;
              final reconciled = payments.where((p) => p.isReconciled).length;
              return Padding(
                padding: const EdgeInsets.fromLTRB(16, 12, 16, 0),
                child: KpiGrid(cards: [
                  KpiCard(
                    icon: Icons.hourglass_top_rounded,
                    label: 'Pending Review',
                    value: '$pending',
                    color: AppTheme.warning,
                  ),
                  KpiCard(
                    icon: Icons.verified_rounded,
                    label: 'Reconciled',
                    value: '$reconciled',
                    color: AppTheme.success,
                  ),
                ]),
              );
            },
          ),
          SizedBox(
            height: 48,
            child: ListView(
              scrollDirection: Axis.horizontal,
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
              children: [
                _FilterChip(label: 'All', selected: _statusFilter == null,
                    onTap: () => setState(() => _statusFilter = null)),
                for (final s in const ['pending', 'reconciled', 'rejected'])
                  Padding(
                    padding: const EdgeInsets.only(left: 8),
                    child: _FilterChip(
                      label: reconciliationStatusLabel(s), selected: _statusFilter == s,
                      onTap: () => setState(() => _statusFilter = s),
                    ),
                  ),
              ],
            ),
          ),
          Expanded(
            child: paymentsAsync.when(
              loading: () => const Center(child: CircularProgressIndicator()),
              error: (e, _) => Center(
                  child: Text(friendlyErrorMessage(e), style: const TextStyle(color: AppTheme.error))),
              data: (payments) {
                final filtered = _statusFilter == null
                    ? payments
                    : payments.where((p) => p.status == _statusFilter).toList();
                if (filtered.isEmpty) {
                  return const AppEmptyState(
                    icon: Icons.receipt_long_rounded,
                    title: 'No payments recorded yet',
                    subtitle: 'Tap "Record Payment" to add one.',
                  );
                }
                return RefreshIndicator(
                  onRefresh: () => ref.read(onlinePaymentsProvider(societyId).notifier).refresh(),
                  child: ListView.builder(
                    padding: const EdgeInsets.fromLTRB(16, 8, 16, 88),
                    itemCount: filtered.length,
                    itemBuilder: (_, i) => _PaymentCard(
                      payment: filtered[i],
                      onTap: () => Navigator.push(context, MaterialPageRoute(
                        builder: (_) => OnlinePaymentDetailScreen(paymentId: filtered[i].id),
                      )),
                    ),
                  ),
                );
              },
            ),
          ),
        ],
      ),
    );
  }
}

class _FilterChip extends StatelessWidget {
  final String label;
  final bool selected;
  final VoidCallback onTap;
  const _FilterChip({required this.label, required this.selected, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return ChoiceChip(
      label: Text(label, style: const TextStyle(fontSize: 12)),
      selected: selected,
      onSelected: (_) => onTap(),
      selectedColor: AppTheme.primary.withOpacity(0.15),
      labelStyle: TextStyle(color: selected ? AppTheme.primary : AppTheme.textSecondary),
    );
  }
}

class _PaymentCard extends StatelessWidget {
  final OnlinePaymentEntity payment;
  final VoidCallback onTap;
  const _PaymentCard({required this.payment, required this.onTap});

  Color get _statusColor => switch (payment.status) {
        'reconciled' => AppTheme.success,
        'rejected' => AppTheme.error,
        _ => AppTheme.warning,
      };

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      child: ListTile(
        onTap: onTap,
        title: Text('₹${payment.amount} — ${payment.wingName ?? ''} ${payment.flatNumber ?? ''}'.trim(),
            style: const TextStyle(fontWeight: FontWeight.w600)),
        subtitle: Text(
            '${payment.receiptNumber} · '
            '${payment.isOnBill ? "Bill ${payment.billInvoiceNumber ?? ""}" : onlinePaymentPurposeLabel(payment.purpose)} · '
            '${paymentModeLabel(payment.paymentMode)} · '
            '${payment.paymentDate.day}/${payment.paymentDate.month}/${payment.paymentDate.year}'),
        trailing: Chip(
          label: Text(reconciliationStatusLabel(payment.status),
              style: TextStyle(fontSize: 11, color: _statusColor)),
          backgroundColor: _statusColor.withOpacity(0.12),
          side: BorderSide.none,
        ),
      ),
    );
  }
}

extension on String {
  String ifEmpty(String fallback) => isEmpty ? fallback : this;
}
