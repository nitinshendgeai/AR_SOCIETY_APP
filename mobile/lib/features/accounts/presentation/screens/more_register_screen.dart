import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/layout/app_shell.dart' show isDesktopLayout;
import 'package:ar_society_app/core/motion/loading.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/accounts/data/more_registers_api.dart';
import 'package:ar_society_app/features/accounts/presentation/widgets/accounts_widgets.dart';
import 'package:ar_society_app/features/accounts/presentation/widgets/register_widgets.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/shared/utils/file_saver.dart' show saveFileBytes;
import 'package:ar_society_app/shared/widgets/app_form.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';

/// Any register in the shared shape (rental, receipts, staff attendance): filters, totals, the rows as a table on a
/// computer and cards on a phone, a printout and a spreadsheet of the same view.
class MoreRegisterScreen extends ConsumerStatefulWidget {
  /// `rental`, `receipts` or `attendance`.
  final String kind;
  const MoreRegisterScreen({super.key, required this.kind});

  @override
  ConsumerState<MoreRegisterScreen> createState() => _MoreRegisterScreenState();
}

class _MoreRegisterScreenState extends ConsumerState<MoreRegisterScreen> {
  RegisterPeriod _period = RegisterPeriod.thisYear;
  late DateTime _month = DateTime(DateTime.now().year, DateTime.now().month);
  String? _status;
  String _search = '';

  MoreRegisterKey _key(String societyId, MoreRegister? reg) {
    final (from, to) = _period.range;
    final usesMonth = reg?.usesMonth ?? widget.kind == 'attendance';
    final usesPeriod = reg?.usesPeriod ?? widget.kind == 'receipts' || widget.kind == 'petty_cash';
    return (
      kind: widget.kind,
      societyId: societyId,
      from: usesPeriod ? from : null,
      to: usesPeriod ? to : null,
      month: usesMonth ? DateFormat('yyyy-MM').format(_month) : null,
      status: _status,
      search: _search,
    );
  }

  Future<void> _csv(MoreRegisterKey key, MoreRegister reg) async {
    try {
      final bytes = await ref.read(moreRegistersApiProvider).file(key, 'csv');
      final name = '${reg.title.replaceAll(' ', '-')}.csv';
      if (await saveFileBytes(bytes, name, mimeType: 'text/csv') && mounted) AppToast.success(context, '$name downloaded');
    } catch (e) {
      if (mounted) showErrorToast(context, e);
    }
  }

  @override
  Widget build(BuildContext context) {
    final societyId = ref.watch(currentUserProvider)?.societyId ?? '';
    final key = _key(societyId, null);
    final async = ref.watch(moreRegisterProvider(key));
    final reg = async.valueOrNull;
    final fullKey = _key(societyId, reg);
    return AppPage(
      title: reg?.title ?? 'Register',
      subtitle: reg?.subtitle,
      actions: [
        IconButton(
          key: const ValueKey('register-csv'),
          tooltip: 'Download as a spreadsheet',
          icon: const Icon(Icons.table_view_rounded),
          onPressed: reg == null ? null : () => _csv(fullKey, reg),
        ),
        PdfActions(
          load: reg == null ? null : () => ref.read(moreRegistersApiProvider).file(fullKey, 'pdf'),
          fileName: '${(reg?.title ?? 'Register').replaceAll(' ', '-')}.pdf',
          subject: reg?.title,
        ),
      ],
      body: RefreshIndicator(
        onRefresh: () async => ref.invalidate(moreRegisterProvider(key)),
        child: ListView(
          padding: const EdgeInsets.fromLTRB(16, 12, 16, 96),
          children: [
            if (reg?.usesPeriod ?? false) ...[
              RegisterPeriodBar(value: _period, onChanged: (p) => setState(() => _period = p)),
              const SizedBox(height: 10),
            ],
            if (reg?.usesMonth ?? false) ...[_monthBar(), const SizedBox(height: 10)],
            if (reg != null && reg.statuses.length > 1) ...[
              Wrap(spacing: 8, runSpacing: 8, children: [
                for (final (value, label) in reg.statuses)
                  ChoiceChip(
                    key: ValueKey('register-status-${value ?? 'all'}'),
                    label: Text(label),
                    selected: _status == value,
                    onSelected: (_) => setState(() => _status = value),
                  ),
              ]),
              const SizedBox(height: 12),
            ],
            TextField(
              key: const ValueKey('register-search'),
              onChanged: (v) => setState(() => _search = v.trim()),
              decoration: const InputDecoration(prefixIcon: Icon(Icons.search_rounded), hintText: 'Search'),
            ),
            const SizedBox(height: 14),
            ...async.when(
              loading: () => [const AppLoader()],
              error: (e, _) => [AppErrorState(compact: true, message: friendlyErrorMessage(e), onRetry: () => ref.invalidate(moreRegisterProvider(key)))],
              data: (r) => [
                RegisterTotals(figures: r.totals),
                const SizedBox(height: 14),
                if (r.rows.isEmpty)
                  const AppEmptyState(
                      icon: Icons.inbox_rounded, title: 'Nothing to show', subtitle: 'Try another filter or period.')
                else if (isDesktopLayout(context))
                  _table(r)
                else
                  _cards(r),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _monthBar() => Row(children: [
        IconButton(
          key: const ValueKey('register-month-prev'),
          icon: const Icon(Icons.chevron_left_rounded),
          onPressed: () => setState(() => _month = DateTime(_month.year, _month.month - 1)),
        ),
        Text(DateFormat('MMMM yyyy').format(_month),
            key: const ValueKey('register-month'), style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w700)),
        IconButton(
          key: const ValueKey('register-month-next'),
          icon: const Icon(Icons.chevron_right_rounded),
          onPressed: () => setState(() => _month = DateTime(_month.year, _month.month + 1)),
        ),
      ]);

  /// A computer: every column, scrolling sideways when there are many (a month of attendance has 30 and more).
  Widget _table(MoreRegister r) => Container(
        decoration: BoxDecoration(color: AppTheme.cardBg, borderRadius: BorderRadius.circular(AppTheme.radiusM)),
        child: SingleChildScrollView(
          scrollDirection: Axis.horizontal,
          child: DataTable(
            columnSpacing: 14,
            horizontalMargin: 12,
            headingRowHeight: 36,
            dataRowMinHeight: 32,
            dataRowMaxHeight: 44,
            columns: [for (final c in r.columns) DataColumn(label: Text(c.label, style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w700)), numeric: c.right)],
            rows: [
              for (final row in r.rows)
                DataRow(cells: [for (final c in r.columns) DataCell(Text(row[c.key] ?? '', style: const TextStyle(fontSize: 12.5)))]),
            ],
          ),
        ),
      );

  /// A phone: one card per row, headed by the first column a phone shows, then "label: value" for the others.
  Widget _cards(MoreRegister r) {
    final shown = [for (final c in r.columns) if (c.phone) c];
    final head = shown.isEmpty ? r.columns.first : shown.first;
    return Container(
      decoration: BoxDecoration(color: AppTheme.cardBg, borderRadius: BorderRadius.circular(AppTheme.radiusM)),
      child: Column(children: [
        for (final (i, row) in r.rows.indexed) ...[
          if (i > 0) const Divider(height: 1),
          Padding(
            padding: const EdgeInsets.fromLTRB(14, 10, 14, 10),
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text(row[head.key] ?? '', style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w700)),
              const SizedBox(height: 4),
              for (final c in shown.where((c) => c.key != head.key))
                if ((row[c.key] ?? '').isNotEmpty)
                  Padding(
                    padding: const EdgeInsets.only(top: 2),
                    child: Text('${c.label}: ${row[c.key]}', style: const TextStyle(fontSize: 12.5, color: AppTheme.textSecondary)),
                  ),
            ]),
          ),
        ],
      ]),
    );
  }
}
