import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';
import 'package:share_plus/share_plus.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/layout/app_sheet.dart';
import 'package:ar_society_app/core/layout/app_shell.dart' show isDesktopLayout;
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/features/maintenance_billing/data/defaulters_api.dart';
import 'package:ar_society_app/features/maintenance_billing/presentation/screens/maintenance_bill_detail_screen.dart';
import 'package:ar_society_app/features/maintenance_billing/presentation/widgets/billing_sheet_frame.dart';
import 'package:ar_society_app/shared/utils/csv_file.dart';
import 'package:ar_society_app/shared/utils/file_saver.dart';
import 'package:ar_society_app/shared/widgets/app_data_table.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';

final defaultersApiProvider = Provider<DefaultersApi>((_) => DefaultersApi());

typedef DefaultersKey = ({String societyId, int minMonths, bool includeAll});

final defaultersProvider = FutureProvider.autoDispose.family<DefaultersReport, DefaultersKey>(
  (ref, k) => ref.watch(defaultersApiProvider).report(k.societyId, minMonths: k.minMonths, includeAll: k.includeAll),
);

final _inr = NumberFormat.currency(locale: 'en_IN', symbol: '₹', decimalDigits: 2);
String _rs(double v) => _inr.format(v);
String _d(DateTime d) => DateFormat('d MMM yyyy').format(d);

Color bucketColor(String key) => switch (key) {
      'not_due' => AppTheme.textTertiary,
      'upto_3' => const Color(0xFFF2B400),
      'm3_6' => AppTheme.warning,
      'm6_12' => AppTheme.error,
      _ => const Color(0xFF9B1C1C),
    };

/// Column headings for the age buckets.
const _shortBucket = {'upto_3': '≤ 3 m', 'm3_6': '3–6 m', 'm6_12': '6–12 m', 'over_12': '> 1 yr'};

String overdueLabel(int days) {
  if (days <= 0) return 'Not yet due';
  if (days < 31) return '$days days overdue';
  final months = days ~/ 30;
  return '$months month${months == 1 ? '' : 's'} overdue';
}

/// Members' maintenance dues aged from the bills' due dates, and the list of
/// defaulters — flats with dues outstanding longer than the limit (3 months
/// by default) — with reminders, the printed list and a CSV.
class DefaultersScreen extends ConsumerStatefulWidget {
  const DefaultersScreen({super.key});

  @override
  ConsumerState<DefaultersScreen> createState() => _DefaultersScreenState();
}

class _DefaultersScreenState extends ConsumerState<DefaultersScreen> {
  int _minMonths = 3;
  bool _includeAll = false;
  String _q = '';
  final Set<String> _selected = {};
  bool _busy = false;

  DefaultersKey _key(String societyId) => (societyId: societyId, minMonths: _minMonths, includeAll: _includeAll);

  Future<void> _pdf(String societyId, {required bool share}) async {
    setState(() => _busy = true);
    final name = '${_includeAll ? 'Members-Dues' : 'Defaulters'}-${DateFormat('yyyy-MM-dd').format(DateTime.now())}.pdf';
    try {
      final bytes =
          await ref.read(defaultersApiProvider).pdf(societyId, minMonths: _minMonths, includeAll: _includeAll);
      if (share) {
        await Share.shareXFiles([XFile.fromData(bytes, name: name, mimeType: 'application/pdf')],
            fileNameOverrides: [name], subject: 'List of Defaulters');
      } else if (await saveFileBytes(bytes, name, mimeType: 'application/pdf') && mounted) {
        AppToast.success(context, '$name downloaded');
      }
    } catch (e) {
      if (mounted) showErrorToast(context, e);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _csv(DefaultersReport r) async {
    final rows = <List<String>>[
      ['Flat', 'Member', 'Phone', ...kDuesBuckets.values, 'Total outstanding', 'Oldest due date', 'Days overdue',
        'Unpaid bills', 'Last payment date', 'Last payment amount'],
      for (final f in r.flats)
        [
          f.flatLabel, f.memberName, f.phone ?? '',
          for (final k in kDuesBuckets.keys) (f.buckets[k] ?? 0).toStringAsFixed(2),
          f.total.toStringAsFixed(2), DateFormat('yyyy-MM-dd').format(f.oldestDueDate), '${f.daysOverdue}',
          '${f.unpaidBills}',
          f.lastPaymentDate == null ? '' : DateFormat('yyyy-MM-dd').format(f.lastPaymentDate!),
          f.lastPaymentAmount?.toStringAsFixed(2) ?? '',
        ],
    ];
    final csv = rows.map((row) => row.map((c) => c.contains(',') || c.contains('"') ? '"${c.replaceAll('"', '""')}"' : c).join(',')).join('\r\n');
    final name = '${_includeAll ? 'members-dues' : 'defaulters'}-${DateFormat('yyyy-MM-dd').format(DateTime.now())}.csv';
    if (await saveCsvFile(csv, name) && mounted) AppToast.success(context, '$name downloaded');
  }

  Future<void> _remind(String societyId, {List<String>? flatIds, required int count}) async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(flatIds == null ? 'Remind all defaulters?' : 'Send reminder to $count flat${count == 1 ? '' : 's'}?'),
        content: const Text(
          'Members with an app login get a notification with the amount outstanding and the oldest due date.',
          style: TextStyle(fontSize: 13, color: AppTheme.textSecondary),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancel')),
          FilledButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('Send')),
        ],
      ),
    );
    if (ok != true) return;
    setState(() => _busy = true);
    try {
      final r = await ref.read(defaultersApiProvider).remind(societyId, flatIds: flatIds, minMonths: _minMonths);
      ref.invalidate(defaultersProvider);
      _selected.clear();
      if (mounted) {
        final missing = r.flatsWithoutLogin.isEmpty ? '' : ' · ${r.flatsWithoutLogin.length} without an app login';
        AppToast.success(context, 'Reminder sent to ${r.flatsReminded} flat${r.flatsReminded == 1 ? '' : 's'}$missing');
      }
    } catch (e) {
      if (mounted) showErrorToast(context, e);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  void _openFlat(String societyId, FlatDues f) => showAppSheet(
        context: context,
        builder: (_) => _FlatSheet(
          flat: f,
          societyId: societyId,
          onRemind: () => _remind(societyId, flatIds: [f.flatId], count: 1),
        ),
      );

  @override
  Widget build(BuildContext context) {
    final societyId = ref.watch(currentUserProvider)?.societyId;
    if (societyId == null) return const Scaffold(body: Center(child: Text('No society context')));
    final key = _key(societyId);
    final async = ref.watch(defaultersProvider(key));
    final desktop = isDesktopLayout(context);
    final report = async.valueOrNull;

    return Scaffold(
      backgroundColor: AppTheme.surface,
      appBar: AppBar(title: Text(_includeAll ? "Members' Dues" : 'Defaulters'), actions: [
        IconButton(
          tooltip: 'Export CSV',
          onPressed: report == null || _busy ? null : () => _csv(report),
          icon: const Icon(Icons.table_view_rounded),
        ),
        IconButton(
          tooltip: 'Share PDF',
          onPressed: report == null || _busy ? null : () => _pdf(societyId, share: true),
          icon: const Icon(Icons.ios_share_rounded),
        ),
        if (desktop)
          HeaderActionButton(
            icon: Icons.download_rounded,
            label: 'Download PDF',
            onPressed: report == null || _busy ? null : () => _pdf(societyId, share: false),
          )
        else
          IconButton(
            tooltip: 'Download PDF',
            onPressed: report == null || _busy ? null : () => _pdf(societyId, share: false),
            icon: const Icon(Icons.download_rounded),
          ),
      ]),
      floatingActionButton: report == null || report.flats.isEmpty
          ? null
          : FloatingActionButton.extended(
              onPressed: _busy
                  ? null
                  : () => _selected.isEmpty
                      ? _remind(societyId, count: report.summary.defaulters)
                      : _remind(societyId, flatIds: _selected.toList(), count: _selected.length),
              icon: const Icon(Icons.notifications_active_rounded),
              label: Text(_selected.isEmpty ? 'Remind all defaulters' : 'Remind ${_selected.length} selected'),
            ),
      body: RefreshIndicator(
        onRefresh: () async => ref.invalidate(defaultersProvider(key)),
        child: async.when(
          loading: () => const Center(child: CircularProgressIndicator()),
          error: (e, _) => ListView(children: [
            Padding(
              padding: const EdgeInsets.all(24),
              child: Text(friendlyErrorMessage(e), style: const TextStyle(color: AppTheme.error)),
            ),
          ]),
          data: (r) {
            final q = _q.toLowerCase();
            final rows = r.flats
                .where((f) => q.isEmpty || f.flatLabel.toLowerCase().contains(q) || f.memberName.toLowerCase().contains(q))
                .toList();
            final s = r.summary;
            return ResponsiveBody(
              maxWidth: 1280,
              child: ListView(
                padding: const EdgeInsets.fromLTRB(16, 16, 16, 96),
                children: [
                  KpiGrid(cards: [
                    KpiCard(
                      icon: Icons.warning_amber_rounded,
                      label: 'Defaulters',
                      value: '${s.defaulters}',
                      note: 'Over ${s.minMonths} months · ${_rs(s.defaultersOutstanding)}',
                      color: AppTheme.error,
                      onTap: () => setState(() => _includeAll = false),
                    ),
                    KpiCard(
                      icon: Icons.hourglass_bottom_rounded,
                      label: 'In default',
                      value: _rs(s.inDefault),
                      note: 'Due over ${s.minMonths} months ago',
                      color: AppTheme.warning,
                    ),
                    KpiCard(
                      icon: Icons.account_balance_wallet_rounded,
                      label: 'Total dues',
                      value: _rs(s.totalOutstanding),
                      note: '${s.flatsWithDues} flats',
                      color: AppTheme.primary,
                      onTap: () => setState(() => _includeAll = true),
                    ),
                    KpiCard(
                      icon: Icons.event_available_rounded,
                      label: 'Not yet due',
                      value: _rs(s.buckets['not_due'] ?? 0),
                      color: AppTheme.success,
                    ),
                  ]),
                  const SizedBox(height: 14),
                  _AgeingStrip(summary: s),
                  const SizedBox(height: 14),
                  Wrap(spacing: 10, runSpacing: 10, crossAxisAlignment: WrapCrossAlignment.center, children: [
                    SegmentedButton<bool>(
                      showSelectedIcon: false,
                      segments: const [
                        ButtonSegment(value: false, label: Text('Defaulters')),
                        ButtonSegment(value: true, label: Text('All with dues')),
                      ],
                      selected: {_includeAll},
                      onSelectionChanged: (v) => setState(() {
                        _includeAll = v.first;
                        _selected.clear();
                      }),
                    ),
                    DropdownButtonHideUnderline(
                      child: Container(
                        padding: const EdgeInsets.symmetric(horizontal: 12),
                        decoration: BoxDecoration(
                          color: AppTheme.cardBg,
                          borderRadius: BorderRadius.circular(20),
                          border: Border.all(color: AppTheme.fieldBorder),
                        ),
                        child: DropdownButton<int>(
                          value: _minMonths,
                          isDense: true,
                          items: [
                            for (final m in const [1, 3, 6, 12])
                              DropdownMenuItem(value: m, child: Text('Overdue more than $m month${m == 1 ? '' : 's'}')),
                          ],
                          onChanged: (v) => setState(() {
                            _minMonths = v ?? 3;
                            _selected.clear();
                          }),
                        ),
                      ),
                    ),
                    TableSearchField(hint: 'Search flat or member', width: 260, onChanged: (v) => setState(() => _q = v)),
                  ]),
                  const SizedBox(height: 12),
                  if (rows.isEmpty)
                    AppEmptyState(
                      icon: Icons.verified_rounded,
                      title: _includeAll ? 'No dues outstanding' : 'No defaulters',
                      subtitle: _includeAll
                          ? 'Every issued bill is paid.'
                          : 'No flat has dues outstanding for more than $_minMonths month${_minMonths == 1 ? '' : 's'}.',
                    )
                  else if (desktop)
                    AppDataTable<FlatDues>(
                      rows: rows,
                      pageSize: 50,
                      onRowTap: (f) => _openFlat(societyId, f),
                      columns: [
                        AppDataColumn(
                          label: '',
                          width: 44,
                          cell: (f) => Checkbox(
                            value: _selected.contains(f.flatId),
                            onChanged: (v) => setState(() => v == true ? _selected.add(f.flatId) : _selected.remove(f.flatId)),
                          ),
                        ),
                        AppDataColumn(
                          label: 'Flat',
                          width: 104,
                          sortKey: (f) => f.flatLabel,
                          cell: (f) => TwoLineCell(f.flatLabel, '${f.unpaidBills} unpaid'),
                        ),
                        AppDataColumn(label: 'Member', flex: 2, sortKey: (f) => f.memberName,
                            cell: (f) => TwoLineCell(f.memberName, f.phone)),
                        for (final k in kDuesBuckets.keys.where((k) => k != 'not_due'))
                          AppDataColumn.text(_shortBucket[k]!, (f) => (f.buckets[k] ?? 0) == 0 ? '' : _rs(f.buckets[k]!),
                              numeric: true, width: 100, sortKey: (f) => f.buckets[k] ?? 0),
                        AppDataColumn(
                          label: 'Total due',
                          numeric: true,
                          width: 118,
                          sortKey: (f) => f.total,
                          cell: (f) => Text(_rs(f.total), textAlign: TextAlign.right,
                              style: const TextStyle(fontSize: 13.5, fontWeight: FontWeight.w700,
                                  fontFeatures: [FontFeature.tabularFigures()])),
                        ),
                        AppDataColumn(
                          label: 'Due since',
                          width: 126,
                          sortKey: (f) => f.oldestDueDate,
                          cell: (f) => TwoLineCell(_d(f.oldestDueDate), overdueLabel(f.daysOverdue)),
                        ),
                        AppDataColumn(
                          label: 'Last paid',
                          width: 118,
                          sortKey: (f) => f.lastPaymentDate,
                          cell: (f) => f.lastPaymentDate == null
                              ? const Text('—', style: TextStyle(color: AppTheme.textTertiary))
                              : TwoLineCell(_d(f.lastPaymentDate!), _rs(f.lastPaymentAmount ?? 0)),
                        ),
                        AppDataColumn(
                          label: 'Reminded',
                          width: 96,
                          sortKey: (f) => f.lastRemindedAt,
                          cell: (f) => Text(f.lastRemindedAt == null ? '—' : _d(f.lastRemindedAt!.toLocal()),
                              style: TextStyle(fontSize: 13,
                                  color: f.lastRemindedAt == null ? AppTheme.textTertiary : AppTheme.textPrimary)),
                        ),
                      ],
                    )
                  else
                    for (final f in rows)
                      _FlatCard(
                        flat: f,
                        selected: _selected.contains(f.flatId),
                        onSelect: (v) => setState(() => v ? _selected.add(f.flatId) : _selected.remove(f.flatId)),
                        onTap: () => _openFlat(societyId, f),
                      ),
                  if (s.interestRatePct != null && s.interestRatePct! > 0)
                    Padding(
                      padding: const EdgeInsets.only(top: 12),
                      child: Text(
                        'Dues are aged from each bill\'s due date; payments on account are set off against the oldest '
                        'bills first. Interest at ${s.interestRatePct!.toStringAsFixed(s.interestRatePct! % 1 == 0 ? 0 : 2)}% '
                        'p.a. on arrears is added to the next bill.',
                        style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary),
                      ),
                    ),
                ],
              ),
            );
          },
        ),
      ),
    );
  }
}

/// The dues of all flats split by age: one tile per bucket.
class _AgeingStrip extends StatelessWidget {
  final DuesSummary summary;
  const _AgeingStrip({required this.summary});

  @override
  Widget build(BuildContext context) => Container(
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(color: AppTheme.cardBg, borderRadius: BorderRadius.circular(AppTheme.radiusM)),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          const Text('Dues by age (from the due date)', style: TextStyle(fontSize: 13, fontWeight: FontWeight.w700)),
          const SizedBox(height: 10),
          Wrap(spacing: 22, runSpacing: 12, children: [
            for (final e in kDuesBuckets.entries)
              Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Row(mainAxisSize: MainAxisSize.min, children: [
                  Container(width: 8, height: 8,
                      decoration: BoxDecoration(color: bucketColor(e.key), shape: BoxShape.circle)),
                  const SizedBox(width: 6),
                  Text(e.value, style: const TextStyle(fontSize: 11.5, color: AppTheme.textSecondary,
                      fontWeight: FontWeight.w600)),
                ]),
                const SizedBox(height: 3),
                Text(_rs(summary.buckets[e.key] ?? 0),
                    style: const TextStyle(fontSize: 14.5, fontWeight: FontWeight.w700,
                        fontFeatures: [FontFeature.tabularFigures()])),
              ]),
          ]),
        ]),
      );
}

class _FlatCard extends StatelessWidget {
  final FlatDues flat;
  final bool selected;
  final ValueChanged<bool> onSelect;
  final VoidCallback onTap;
  const _FlatCard({required this.flat, required this.selected, required this.onSelect, required this.onTap});

  @override
  Widget build(BuildContext context) {
    final f = flat;
    final color = bucketColor(f.worstBucket);
    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      decoration: BoxDecoration(
        color: AppTheme.cardBg,
        borderRadius: BorderRadius.circular(AppTheme.radiusM),
        border: Border(left: BorderSide(color: color, width: 4)),
      ),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(AppTheme.radiusM),
        child: Padding(
          padding: const EdgeInsets.fromLTRB(4, 10, 14, 10),
          child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Checkbox(value: selected, onChanged: (v) => onSelect(v ?? false)),
            Expanded(
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Row(children: [
                  Expanded(
                    child: Text(f.flatLabel, style: const TextStyle(fontSize: 14.5, fontWeight: FontWeight.w700)),
                  ),
                  Text(_rs(f.total),
                      style: const TextStyle(fontSize: 14.5, fontWeight: FontWeight.w700,
                          fontFeatures: [FontFeature.tabularFigures()])),
                ]),
                const SizedBox(height: 2),
                Text(f.memberName, style: const TextStyle(fontSize: 12.5, color: AppTheme.textSecondary)),
                const SizedBox(height: 6),
                Row(children: [
                  StatusPill(overdueLabel(f.daysOverdue), color),
                  const SizedBox(width: 8),
                  Flexible(
                    child: Text('${f.unpaidBills} unpaid · since ${_d(f.oldestDueDate)}',
                        overflow: TextOverflow.ellipsis,
                        style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
                  ),
                ]),
                if (f.lastRemindedAt != null)
                  Padding(
                    padding: const EdgeInsets.only(top: 4),
                    child: Text('Reminded ${_d(f.lastRemindedAt!.toLocal())}',
                        style: const TextStyle(fontSize: 11.5, color: AppTheme.textTertiary)),
                  ),
              ]),
            ),
          ]),
        ),
      ),
    );
  }
}

/// A flat's unpaid bills, with reminder and links to the bills.
class _FlatSheet extends StatelessWidget {
  final FlatDues flat;
  final String societyId;
  final VoidCallback onRemind;
  const _FlatSheet({required this.flat, required this.societyId, required this.onRemind});

  @override
  Widget build(BuildContext context) {
    final f = flat;
    return BillingSheetFrame(
      title: '${f.flatLabel} · ${f.memberName}',
      child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        Wrap(spacing: 24, runSpacing: 10, children: [
          _fig('Total due', _rs(f.total)),
          _fig('Due since', _d(f.oldestDueDate)),
          _fig('Last payment',
              f.lastPaymentDate == null ? '—' : '${_rs(f.lastPaymentAmount ?? 0)} on ${_d(f.lastPaymentDate!)}'),
          if (f.phone != null) _fig('Phone', f.phone!),
        ]),
        if (f.onAccount > 0)
          Padding(
            padding: const EdgeInsets.only(top: 8),
            child: Text('${_rs(f.onAccount)} paid on account is set off against the oldest bills.',
                style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
          ),
        const SizedBox(height: 14),
        const Text('Unpaid bills', style: TextStyle(fontSize: 13.5, fontWeight: FontWeight.w700)),
        const SizedBox(height: 6),
        Container(
          decoration: BoxDecoration(
              border: Border.all(color: AppTheme.border), borderRadius: BorderRadius.circular(AppTheme.radiusS)),
          child: Column(children: [
            for (final (i, b) in f.bills.indexed) ...[
              if (i > 0) const Divider(height: 1),
              ListTile(
                dense: true,
                title: Text('${b.invoiceNumber} · ${b.period}',
                    style: const TextStyle(fontSize: 13.5, fontWeight: FontWeight.w600)),
                subtitle: Text('Due ${_d(b.dueDate)} · ${overdueLabel(b.daysOverdue)}',
                    style: TextStyle(fontSize: 12, color: bucketColor(b.bucket))),
                trailing: Text(_rs(b.outstanding),
                    style: const TextStyle(fontSize: 13.5, fontWeight: FontWeight.w700,
                        fontFeatures: [FontFeature.tabularFigures()])),
                onTap: () => Navigator.of(context).push(MaterialPageRoute(
                  builder: (_) => MaintenanceBillDetailScreen(billId: b.billId, societyId: societyId, canManage: true),
                )),
              ),
            ],
          ]),
        ),
        const SizedBox(height: 16),
        AppPrimaryButton(
          label: 'Send reminder',
          icon: Icons.notifications_active_rounded,
          onPressed: () {
            // Close this panel with its own context — the screen's navigator
            // is a different one, and popping it would close the screen.
            Navigator.pop(context);
            onRemind();
          },
        ),
      ]),
    );
  }

  Widget _fig(String label, String value) => Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text(label, style: const TextStyle(fontSize: 11.5, color: AppTheme.textSecondary, fontWeight: FontWeight.w600)),
        const SizedBox(height: 2),
        Text(value, style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w700)),
      ]);
}
