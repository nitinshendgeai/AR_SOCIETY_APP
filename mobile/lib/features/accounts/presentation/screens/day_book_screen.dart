import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/layout/app_shell.dart' show isDesktopLayout;
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/accounts/data/accounts_api.dart';
import 'package:ar_society_app/features/accounts/presentation/providers/accounts_providers.dart';
import 'package:ar_society_app/features/accounts/presentation/screens/accounts_screen.dart' show chooseNewVoucher;
import 'package:ar_society_app/features/accounts/presentation/widgets/accounts_widgets.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/shared/widgets/app_data_table.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';

/// Every voucher, latest first, filtered by type and month: receipts,
/// payments, contras and journals the society entered, and the member
/// bills, receipts and vendor bills posted automatically.
class DayBookScreen extends ConsumerStatefulWidget {
  const DayBookScreen({super.key});

  @override
  ConsumerState<DayBookScreen> createState() => _DayBookScreenState();
}

class _DayBookScreenState extends ConsumerState<DayBookScreen> {
  String? _type;
  late DateTime _month = DateTime(DateTime.now().year, DateTime.now().month);
  bool _allDates = false;
  String _q = '';

  @override
  Widget build(BuildContext context) {
    final societyId = ref.watch(currentUserProvider)?.societyId;
    if (societyId == null) return const Scaffold(body: Center(child: Text('No society context')));
    final from = _allDates ? null : _month;
    final to = _allDates ? null : DateTime(_month.year, _month.month + 1, 0);
    final key = (societyId: societyId, type: _type, from: from, to: to);
    final async = ref.watch(vouchersProvider(key));
    final desktop = isDesktopLayout(context);
    final q = _q.toLowerCase();
    bool matches(Voucher v) =>
        q.isEmpty ||
        v.voucherNumber.toLowerCase().contains(q) ||
        (v.narration ?? '').toLowerCase().contains(q) ||
        (v.reference ?? '').toLowerCase().contains(q) ||
        (v.vendorName ?? '').toLowerCase().contains(q) ||
        v.entries.any((e) => e.title.toLowerCase().contains(q));

    return Scaffold(
      backgroundColor: AppTheme.surface,
      appBar: AppBar(title: const Text('Day Book'), actions: [
        PdfActions(
          load: () => ref.read(accountsApiProvider).dayBookPdf(societyId, type: _type, from: from, to: to),
          fileName: 'Day-Book-${_allDates ? 'all' : apiDate(_month).substring(0, 7)}.pdf',
          subject: 'Day Book — ${_allDates ? 'all dates' : _monthLabel(_month)}',
        ),
        if (desktop)
          HeaderActionButton(icon: Icons.add_rounded, label: 'New Voucher', onPressed: () => chooseNewVoucher(context)),
      ]),
      floatingActionButton: desktop
          ? null
          : FloatingActionButton.extended(
              onPressed: () => chooseNewVoucher(context),
              icon: const Icon(Icons.add_rounded),
              label: const Text('New Voucher'),
            ),
      body: RefreshIndicator(
        onRefresh: () async => ref.invalidate(vouchersProvider(key)),
        child: ResponsiveBody(
          maxWidth: 1200,
          child: ListView(
            padding: const EdgeInsets.fromLTRB(16, 12, 16, 96),
            children: [
              Row(children: [
                IconButton(
                  tooltip: 'Previous month',
                  onPressed: _allDates ? null : () => setState(() => _month = DateTime(_month.year, _month.month - 1)),
                  icon: const Icon(Icons.chevron_left_rounded),
                ),
                Text(_allDates ? 'All dates' : _monthLabel(_month),
                    style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w700)),
                IconButton(
                  tooltip: 'Next month',
                  onPressed: _allDates ? null : () => setState(() => _month = DateTime(_month.year, _month.month + 1)),
                  icon: const Icon(Icons.chevron_right_rounded),
                ),
                const Spacer(),
                FilterChip(
                  label: const Text('All dates'),
                  selected: _allDates,
                  onSelected: (v) => setState(() => _allDates = v),
                ),
              ]),
              const SizedBox(height: 6),
              SingleChildScrollView(
                scrollDirection: Axis.horizontal,
                child: Row(children: [
                  for (final t in [null, ...kVoucherTypes.keys])
                    Padding(
                      padding: const EdgeInsets.only(right: 8),
                      child: ChoiceChip(
                        label: Text(t == null ? 'All' : voucherTypeLabel(t)),
                        selected: _type == t,
                        onSelected: (_) => setState(() => _type = t),
                      ),
                    ),
                ]),
              ),
              const SizedBox(height: 10),
              TableSearchField(hint: 'Search number, narration, ledger, flat', onChanged: (v) => setState(() => _q = v)),
              const SizedBox(height: 12),
              ...async.when(
                loading: () => [const Padding(padding: EdgeInsets.all(40), child: Center(child: CircularProgressIndicator()))],
                error: (e, _) => [Text(friendlyErrorMessage(e), style: const TextStyle(color: AppTheme.error))],
                data: (all) {
                  final rows = all.where(matches).toList();
                  if (rows.isEmpty) {
                    return [
                      const AppEmptyState(
                        icon: Icons.receipt_long_outlined,
                        title: 'No vouchers',
                        subtitle: 'Nothing was posted for these filters.',
                      ),
                    ];
                  }
                  final live = rows.where((v) => !v.isCancelled);
                  final total = live.fold<double>(0, (s, v) => s + v.amount);
                  return [
                    Padding(
                      padding: const EdgeInsets.only(left: 2, bottom: 8),
                      child: Text('${live.length} vouchers · ${formatInr(total)}',
                          style: const TextStyle(fontSize: 12.5, color: AppTheme.textSecondary)),
                    ),
                    if (desktop)
                      AppDataTable<Voucher>(
                        rows: rows,
                        pageSize: 50,
                        onRowTap: (v) => showVoucherSheet(context, v.id),
                        columns: [
                          AppDataColumn.text('Date', (v) => formatAccountsDate(v.voucherDate),
                              width: 110, sortKey: (v) => v.voucherDate),
                          AppDataColumn(
                            label: 'Voucher',
                            width: 180,
                            sortKey: (v) => v.voucherNumber,
                            cell: (v) => Column(crossAxisAlignment: CrossAxisAlignment.start, mainAxisSize: MainAxisSize.min, children: [
                              Text(v.voucherNumber,
                                  style: TextStyle(
                                      fontSize: 13,
                                      fontWeight: FontWeight.w600,
                                      decoration: v.isCancelled ? TextDecoration.lineThrough : null)),
                              const SizedBox(height: 2),
                              VoucherTypeChip(v.voucherType),
                            ]),
                          ),
                          AppDataColumn(
                            label: 'Particulars',
                            flex: 4,
                            cell: (v) => TwoLineCell(_particulars(v), v.narration),
                          ),
                          AppDataColumn(
                            label: 'Amount',
                            numeric: true,
                            width: 150,
                            sortKey: (v) => v.amount,
                            cell: (v) => Column(crossAxisAlignment: CrossAxisAlignment.end, mainAxisSize: MainAxisSize.min, children: [
                              Text(formatInr(v.amount),
                                  style: TextStyle(
                                      fontSize: 13.5,
                                      fontWeight: FontWeight.w600,
                                      fontFeatures: const [FontFeature.tabularFigures()],
                                      decoration: v.isCancelled ? TextDecoration.lineThrough : null,
                                      color: v.isCancelled ? AppTheme.textTertiary : AppTheme.textPrimary)),
                              if (v.isCancelled) const StatusPill('Cancelled', AppTheme.error),
                            ]),
                          ),
                        ],
                      )
                    else
                      Container(
                        decoration: BoxDecoration(
                            color: AppTheme.cardBg, borderRadius: BorderRadius.circular(AppTheme.radiusM)),
                        child: Column(children: [
                          for (final (i, v) in rows.indexed) ...[
                            if (i > 0) const Divider(height: 1),
                            _VoucherTile(v: v, onTap: () => showVoucherSheet(context, v.id)),
                          ],
                        ]),
                      ),
                  ];
                },
              ),
            ],
          ),
        ),
      ),
    );
  }

  static const _months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  String _monthLabel(DateTime m) => '${_months[m.month - 1]} ${m.year}';
}

/// "Dr Bank Account / Cr Members' Dues — A 101"
String _particulars(Voucher v) {
  final dr = v.debits.map((e) => e.title).toSet().join(', ');
  final cr = v.credits.map((e) => e.title).toSet().join(', ');
  return 'Dr $dr  ·  Cr $cr';
}

class _VoucherTile extends StatelessWidget {
  final Voucher v;
  final VoidCallback onTap;
  const _VoucherTile({required this.v, required this.onTap});

  @override
  Widget build(BuildContext context) => InkWell(
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.fromLTRB(14, 10, 14, 10),
          child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Expanded(
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Row(children: [
                  VoucherTypeChip(v.voucherType),
                  const SizedBox(width: 8),
                  Flexible(
                    child: Text(v.voucherNumber,
                        overflow: TextOverflow.ellipsis,
                        style: TextStyle(
                            fontSize: 13,
                            fontWeight: FontWeight.w600,
                            decoration: v.isCancelled ? TextDecoration.lineThrough : null)),
                  ),
                ]),
                const SizedBox(height: 4),
                Text(_particulars(v),
                    maxLines: 2, overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 12.5)),
                if ((v.narration ?? '').isNotEmpty)
                  Text(v.narration!,
                      maxLines: 1, overflow: TextOverflow.ellipsis,
                      style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
              ]),
            ),
            const SizedBox(width: 10),
            Column(crossAxisAlignment: CrossAxisAlignment.end, children: [
              Text(formatInr(v.amount),
                  style: TextStyle(
                      fontSize: 13.5,
                      fontWeight: FontWeight.w700,
                      fontFeatures: const [FontFeature.tabularFigures()],
                      decoration: v.isCancelled ? TextDecoration.lineThrough : null,
                      color: v.isCancelled ? AppTheme.textTertiary : AppTheme.textPrimary)),
              const SizedBox(height: 2),
              Text(v.isCancelled ? 'Cancelled' : formatAccountsDate(v.voucherDate),
                  style: TextStyle(fontSize: 11.5, color: v.isCancelled ? AppTheme.error : AppTheme.textSecondary)),
            ]),
          ]),
        ),
      );
}
