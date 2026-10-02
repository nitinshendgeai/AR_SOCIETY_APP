import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/layout/app_shell.dart' show isDesktopLayout;
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/accounts/data/accounts_api.dart';
import 'package:ar_society_app/features/accounts/presentation/providers/accounts_providers.dart';
import 'package:ar_society_app/features/accounts/presentation/widgets/accounts_widgets.dart';
import 'package:ar_society_app/shared/widgets/app_data_table.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';

enum _Period { thisYear, lastYear, all, custom }

/// A ledger account for a period: opening balance, every posting with the
/// ledgers on the other side and the running balance, and the closing
/// balance. For Cash in Hand or a bank ledger this is the cash book / bank
/// book; with [flatId] it is one member's account on Members' Dues, with
/// [vendorId] one vendor's account on Sundry Creditors.
class LedgerStatementScreen extends ConsumerStatefulWidget {
  final String accountId;
  final String? flatId;
  final String? vendorId;
  final String? title;

  /// Opens on this period (e.g. a financial year, from a statement).
  final DateTime? from;
  final DateTime? to;
  const LedgerStatementScreen(
      {super.key, required this.accountId, this.flatId, this.vendorId, this.title, this.from, this.to});

  @override
  ConsumerState<LedgerStatementScreen> createState() => _LedgerStatementScreenState();
}

class _LedgerStatementScreenState extends ConsumerState<LedgerStatementScreen> {
  late _Period _period = widget.from != null && widget.to != null ? _Period.custom : _Period.thisYear;
  late DateTimeRange? _custom =
      widget.from != null && widget.to != null ? DateTimeRange(start: widget.from!, end: widget.to!) : null;

  (DateTime?, DateTime?) get _range {
    final today = DateTime.now();
    final fy = financialYearStart(today);
    return switch (_period) {
      _Period.thisYear => (fy, null),
      _Period.lastYear => (DateTime(fy.year - 1, 4, 1), DateTime(fy.year, 3, 31)),
      _Period.all => (null, null),
      _Period.custom => (_custom?.start, _custom?.end),
    };
  }

  Future<void> _pickCustom() async {
    final today = DateTime.now();
    final picked = await showDateRangePicker(
      context: context,
      firstDate: DateTime(2000),
      lastDate: DateTime(today.year + 1, 12, 31),
      initialDateRange: _custom ?? DateTimeRange(start: financialYearStart(today), end: today),
    );
    if (picked != null) {
      setState(() {
        _custom = picked;
        _period = _Period.custom;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final (from, to) = _range;
    final key = (accountId: widget.accountId, from: from, to: to, flatId: widget.flatId, vendorId: widget.vendorId);
    final async = ref.watch(ledgerStatementProvider(key));
    final desktop = isDesktopLayout(context);
    final account = async.valueOrNull?.account;
    final title = widget.title ?? account?.name ?? 'Ledger';

    return Scaffold(
      backgroundColor: AppTheme.surface,
      appBar: AppBar(title: Text(title, overflow: TextOverflow.ellipsis)),
      body: RefreshIndicator(
        onRefresh: () async => ref.invalidate(ledgerStatementProvider(key)),
        child: ResponsiveBody(
          maxWidth: 1200,
          child: ListView(
            padding: const EdgeInsets.fromLTRB(16, 12, 16, 96),
            children: [
              Wrap(spacing: 8, runSpacing: 8, children: [
                for (final (p, label) in [
                  (_Period.thisYear, 'This year'),
                  (_Period.lastYear, 'Last year'),
                  (_Period.all, 'All'),
                ])
                  ChoiceChip(
                    label: Text(label),
                    selected: _period == p,
                    onSelected: (_) => setState(() => _period = p),
                  ),
                ChoiceChip(
                  avatar: const Icon(Icons.date_range_rounded, size: 16),
                  label: Text(_period == _Period.custom && _custom != null
                      ? '${formatAccountsDate(_custom!.start)} – ${formatAccountsDate(_custom!.end)}'
                      : 'Dates…'),
                  selected: _period == _Period.custom,
                  onSelected: (_) => _pickCustom(),
                ),
              ]),
              const SizedBox(height: 14),
              ...async.when(
                loading: () => [const Padding(padding: EdgeInsets.all(40), child: Center(child: CircularProgressIndicator()))],
                error: (e, _) => [Text(friendlyErrorMessage(e), style: const TextStyle(color: AppTheme.error))],
                data: (st) => [
                  _Header(st: st, from: from, to: to, subtitle: widget.title == null ? null : st.account.name),
                  const SizedBox(height: 14),
                  if (st.lines.isEmpty)
                    const AppEmptyState(
                      icon: Icons.menu_book_outlined,
                      title: 'No entries in this period',
                      subtitle: 'Postings to this ledger will appear here.',
                    )
                  else if (desktop)
                    AppDataTable<StatementLine>(
                      rows: st.lines,
                      pageSize: 100,
                      onRowTap: (l) => showVoucherSheet(context, l.voucherId),
                      columns: [
                        AppDataColumn.text('Date', (l) => formatAccountsDate(l.date),
                            width: 110, sortKey: (l) => l.date),
                        AppDataColumn(
                          label: 'Voucher',
                          width: 170,
                          sortKey: (l) => l.voucherNumber,
                          cell: (l) => Column(crossAxisAlignment: CrossAxisAlignment.start, mainAxisSize: MainAxisSize.min, children: [
                            Text(l.voucherNumber, style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600)),
                            Text(voucherTypeLabel(l.voucherType),
                                style: TextStyle(fontSize: 11.5, color: voucherTypeColor(l.voucherType))),
                          ]),
                        ),
                        AppDataColumn(
                          label: 'Particulars',
                          flex: 4,
                          cell: (l) => TwoLineCell(l.particulars, l.narration),
                        ),
                        AppDataColumn.text('Debit', (l) => l.debit == 0 ? '' : formatInr(l.debit),
                            numeric: true, width: 130, sortKey: (l) => l.debit),
                        AppDataColumn.text('Credit', (l) => l.credit == 0 ? '' : formatInr(l.credit),
                            numeric: true, width: 130, sortKey: (l) => l.credit),
                        AppDataColumn(
                          label: 'Balance',
                          numeric: true,
                          width: 150,
                          cell: (l) => Align(alignment: Alignment.centerRight, child: DrCrText(l.balance)),
                        ),
                      ],
                    )
                  else
                    Container(
                      decoration:
                          BoxDecoration(color: AppTheme.cardBg, borderRadius: BorderRadius.circular(AppTheme.radiusM)),
                      child: Column(children: [
                        for (final (i, l) in st.lines.indexed) ...[
                          if (i > 0) const Divider(height: 1),
                          _LineTile(line: l, onTap: () => showVoucherSheet(context, l.voucherId)),
                        ],
                      ]),
                    ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _Header extends StatelessWidget {
  final LedgerStatement st;
  final DateTime? from;
  final DateTime? to;
  final String? subtitle;
  const _Header({required this.st, required this.from, required this.to, this.subtitle});

  @override
  Widget build(BuildContext context) {
    final a = st.account;
    final period = from == null && to == null
        ? 'All dates'
        : '${from == null ? 'Start' : formatAccountsDate(from!)} – ${to == null ? 'Today' : formatAccountsDate(to!)}';
    Widget figure(String label, Widget value) => Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(label, style: const TextStyle(fontSize: 11.5, color: AppTheme.textSecondary, fontWeight: FontWeight.w600)),
          const SizedBox(height: 3),
          value,
        ]);
    TextStyle amt = const TextStyle(fontSize: 15, fontWeight: FontWeight.w700, fontFeatures: [FontFeature.tabularFigures()]);
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(color: AppTheme.cardBg, borderRadius: BorderRadius.circular(AppTheme.radiusM)),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text([if (subtitle != null) subtitle!, a.groupName ?? ''].where((s) => s.isNotEmpty).join(' · '),
            style: const TextStyle(fontSize: 12.5, color: AppTheme.textSecondary)),
        if (a.isBank && (a.bankAccountNumber ?? '').isNotEmpty)
          Text('A/c ${a.bankAccountNumber}${a.bankIfsc == null ? '' : ' · ${a.bankIfsc}'}',
              style: const TextStyle(fontSize: 12.5, color: AppTheme.textSecondary)),
        Text(period, style: const TextStyle(fontSize: 12.5, color: AppTheme.textSecondary)),
        const SizedBox(height: 14),
        Wrap(spacing: 28, runSpacing: 12, children: [
          figure('Opening', DrCrText(st.opening, fontSize: 15, weight: FontWeight.w700)),
          figure('Debits', Text(formatInr(st.totalDebit), style: amt)),
          figure('Credits', Text(formatInr(st.totalCredit), style: amt)),
          figure('Closing', DrCrText(st.closing, fontSize: 15, weight: FontWeight.w700)),
        ]),
      ]),
    );
  }
}

class _LineTile extends StatelessWidget {
  final StatementLine line;
  final VoidCallback onTap;
  const _LineTile({required this.line, required this.onTap});

  @override
  Widget build(BuildContext context) {
    final dr = line.debit > 0;
    return InkWell(
      onTap: onTap,
      child: Padding(
        padding: const EdgeInsets.fromLTRB(14, 10, 14, 10),
        child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Expanded(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text(line.particulars,
                  maxLines: 2, overflow: TextOverflow.ellipsis,
                  style: const TextStyle(fontSize: 13.5, fontWeight: FontWeight.w600)),
              const SizedBox(height: 2),
              Text('${formatAccountsDate(line.date)} · ${line.voucherNumber}',
                  style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
              if ((line.narration ?? '').isNotEmpty)
                Text(line.narration!,
                    maxLines: 2, overflow: TextOverflow.ellipsis,
                    style: const TextStyle(fontSize: 12, color: AppTheme.textTertiary)),
            ]),
          ),
          const SizedBox(width: 10),
          Column(crossAxisAlignment: CrossAxisAlignment.end, children: [
            Text('${formatInr(dr ? line.debit : line.credit)} ${dr ? 'Dr' : 'Cr'}',
                style: TextStyle(
                    fontSize: 13.5,
                    fontWeight: FontWeight.w700,
                    color: dr ? AppTheme.textPrimary : AppTheme.primaryDark,
                    fontFeatures: const [FontFeature.tabularFigures()])),
            const SizedBox(height: 2),
            Text('Bal ${line.balance.label}',
                style: const TextStyle(fontSize: 11.5, color: AppTheme.textSecondary)),
          ]),
        ]),
      ),
    );
  }
}
