import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/motion/loading.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/accounts/data/element_monthly_api.dart';
import 'package:ar_society_app/features/accounts/presentation/screens/element_months_screen.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/shared/widgets/app_form.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';

enum ElementView { spent, billed, difference }

final _inr = NumberFormat.decimalPattern('en_IN');
String _amt(double v) => v == 0 ? '–' : (v < 0 ? '−${_inr.format(v.abs().round())}' : _inr.format(v.round()));

/// The figures a row shows for the chosen view: month by month, and the row's total.
(List<double>, double) elementViewValues(ElementMonthRow r, ElementView v) => switch (v) {
      ElementView.spent => (r.spent, r.spentTotal),
      ElementView.billed => (r.billed, r.billedTotal),
      ElementView.difference => (r.monthlyDifference, r.difference),
    };

/// Element-wise expenses, month by month: every expense entry in the books, under the maintenance element its ledger
/// counts towards, for each month of a financial year — with what the bills charged for it beside it.
class ElementMonthlyScreen extends ConsumerStatefulWidget {
  const ElementMonthlyScreen({super.key});
  @override
  ConsumerState<ElementMonthlyScreen> createState() => _ElementMonthlyScreenState();
}

class _ElementMonthlyScreenState extends ConsumerState<ElementMonthlyScreen> {
  static DateTime get _today {
    final n = DateTime.now();
    return DateTime(n.year, n.month, n.day);
  }

  static int _fyOf(DateTime d) => d.month >= 4 ? d.year : d.year - 1;
  late int _fy = _fyOf(_today);
  ElementView _view = ElementView.spent;

  DateTime get _from => DateTime(_fy, 4, 1);
  DateTime get _to {
    final end = DateTime(_fy + 1, 3, 31);
    return end.isAfter(_today) ? _today : end;
  }

  @override
  Widget build(BuildContext context) {
    final sid = ref.watch(currentUserProvider)?.societyId;
    if (sid == null) return const Scaffold(body: Center(child: Text('No society context')));
    final key = (societyId: sid, from: _from, to: _to);
    final async = ref.watch(elementMonthlyProvider(key));
    return AppPage(
      title: 'Element-wise expenses',
      subtitle: 'Monthly, from every expense entry in the books',
      body: RefreshIndicator(
        onRefresh: () async => ref.invalidate(elementMonthlyProvider(key)),
        child: ListView(padding: const EdgeInsets.fromLTRB(16, 12, 16, 60), children: [
          Wrap(spacing: 12, runSpacing: 8, crossAxisAlignment: WrapCrossAlignment.center, children: [
            Row(mainAxisSize: MainAxisSize.min, children: [
              IconButton(
                  tooltip: 'Previous year',
                  icon: const Icon(Icons.chevron_left_rounded),
                  onPressed: () => setState(() => _fy--)),
              Text('FY $_fy-${(_fy + 1) % 100}', style: const TextStyle(fontWeight: FontWeight.w700)),
              IconButton(
                  tooltip: 'Next year',
                  icon: const Icon(Icons.chevron_right_rounded),
                  onPressed: _fy < _fyOf(_today) ? () => setState(() => _fy++) : null),
            ]),
            SegmentedButton<ElementView>(
              segments: const [
                ButtonSegment(value: ElementView.spent, label: Text('Spent')),
                ButtonSegment(value: ElementView.billed, label: Text('Billed')),
                ButtonSegment(value: ElementView.difference, label: Text('Billed − spent')),
              ],
              selected: {_view},
              showSelectedIcon: false,
              onSelectionChanged: (s) => setState(() => _view = s.first),
            ),
          ]),
          const SizedBox(height: 12),
          async.when(
            loading: () => const Padding(padding: EdgeInsets.only(top: 80), child: AppLoader()),
            error: (e, _) => AppErrorState(
                compact: true, message: friendlyErrorMessage(e), onRetry: () => ref.invalidate(elementMonthlyProvider(key))),
            data: (r) => _body(context, r),
          ),
        ]),
      ),
    );
  }

  Widget _body(BuildContext context, ElementMonthly r) {
    if (r.rows.isEmpty) {
      return const Padding(
        padding: EdgeInsets.only(top: 60),
        child: AppEmptyState(
          icon: Icons.table_chart_outlined,
          title: 'No expenses in this year',
          subtitle: 'Expense entries appear here under the element their ledger counts towards.',
        ),
      );
    }
    final head = TextStyle(fontWeight: FontWeight.w700, fontSize: 12.5, color: AppTheme.textSecondary);
    DataRow line(ElementMonthRow row, {bool total = false}) {
      final (vals, sum) = elementViewValues(row, _view);
      final style = TextStyle(fontWeight: total ? FontWeight.w800 : FontWeight.w500,
          fontFeatures: const [FontFeature.tabularFigures()]);
      Color? tone(double v) => _view == ElementView.difference && v != 0 ? (v < 0 ? AppTheme.error : AppTheme.success) : null;
      return DataRow(
        color: total ? WidgetStatePropertyAll(AppTheme.primary.withValues(alpha: 0.06)) : null,
        onSelectChanged: total
            ? null
            : (_) => Navigator.push(context,
                MaterialPageRoute<void>(builder: (_) => ElementMonthsScreen(elementId: row.elementId, name: row.element))),
        cells: [
          DataCell(ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 200),
            child: Row(mainAxisSize: MainAxisSize.min, children: [
              Flexible(child: Text(row.element, style: style, overflow: TextOverflow.ellipsis)),
              if (!total && !row.hasLedger)
                Tooltip(
                  message: 'No expense ledger is linked to this element yet',
                  child: Padding(padding: const EdgeInsets.only(left: 4),
                      child: Icon(Icons.link_off_rounded, size: 15, color: AppTheme.warning)),
                ),
            ]),
          )),
          for (final v in vals) DataCell(Text(_amt(v), style: style.copyWith(color: tone(v)))),
          DataCell(Text(_amt(sum), style: style.copyWith(fontWeight: FontWeight.w800, color: tone(sum)))),
        ],
      );
    }

    return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      Wrap(spacing: 10, runSpacing: 10, children: [
        _Tile('Spent', r.totals.spentTotal, AppTheme.error),
        _Tile('Billed to members', r.totals.billedTotal, AppTheme.primary),
        _Tile('Billed − spent', r.totals.difference, r.totals.difference < 0 ? AppTheme.error : AppTheme.success),
      ]),
      const SizedBox(height: 12),
      Card(
        margin: EdgeInsets.zero,
        clipBehavior: Clip.antiAlias,
        child: SingleChildScrollView(
          scrollDirection: Axis.horizontal,
          child: DataTable(
            key: const Key('element-monthly-table'),
            showCheckboxColumn: false,
            headingRowHeight: 40,
            dataRowMinHeight: 40,
            dataRowMaxHeight: 48,
            columnSpacing: 22,
            columns: [
              DataColumn(label: Text('Element', style: head)),
              for (final m in r.months) DataColumn(numeric: true, label: Text(m, style: head)),
              DataColumn(numeric: true, label: Text('Total', style: head)),
            ],
            rows: [for (final row in r.rows) line(row), line(r.totals, total: true)],
          ),
        ),
      ),
      const SizedBox(height: 10),
      Text(r.note, style: TextStyle(color: AppTheme.textSecondary, fontSize: 12.5, height: 1.4)),
      const SizedBox(height: 4),
      Text('Tap an element for its ledgers and entries.', style: TextStyle(color: AppTheme.textTertiary, fontSize: 12)),
    ]);
  }
}

class _Tile extends StatelessWidget {
  final String label;
  final double value;
  final Color color;
  const _Tile(this.label, this.value, this.color);
  @override
  Widget build(BuildContext context) => Container(
        constraints: const BoxConstraints(minWidth: 150),
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
        decoration: BoxDecoration(
          color: color.withValues(alpha: 0.08),
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: color.withValues(alpha: 0.25)),
        ),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(label, style: TextStyle(color: AppTheme.textSecondary, fontSize: 12)),
          const SizedBox(height: 2),
          Text('₹${_amt(value)}', style: TextStyle(color: color, fontWeight: FontWeight.w800, fontSize: 17)),
        ]),
      );
}
