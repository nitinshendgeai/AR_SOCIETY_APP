import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';

/// One column of an [AppDataTable].
class AppDataColumn<T> {
  final String label;
  final Widget Function(T row) cell;

  /// Makes the column sortable by clicking its header.
  final Comparable<Object?>? Function(T row)? sortKey;

  /// Right-aligns header and cells (amounts, counts).
  final bool numeric;

  /// Fixed width in px; otherwise the column shares the free width by [flex].
  final double? width;
  final int flex;

  const AppDataColumn({
    required this.label,
    required this.cell,
    this.sortKey,
    this.numeric = false,
    this.width,
    this.flex = 1,
  });

  /// Plain text cell, sortable by the same text unless [sortKey] is given.
  factory AppDataColumn.text(
    String label,
    String Function(T row) text, {
    int flex = 1,
    double? width,
    bool numeric = false,
    bool bold = false,
    Comparable<Object?>? Function(T row)? sortKey,
  }) =>
      AppDataColumn(
        label: label,
        flex: flex,
        width: width,
        numeric: numeric,
        sortKey: sortKey ?? (r) => text(r).toLowerCase(),
        cell: (r) => Text(
          text(r),
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
          textAlign: numeric ? TextAlign.right : TextAlign.left,
          style: TextStyle(
            fontSize: 13.5,
            fontWeight: bold ? FontWeight.w600 : FontWeight.w400,
            color: AppTheme.textPrimary,
            fontFeatures: numeric ? const [FontFeature.tabularFigures()] : null,
          ),
        ),
      );
}

/// Desktop data table in the web-ERP style (Fiori / Material data table):
/// a bordered surface with an optional toolbar row, a header with
/// click-to-sort columns, hoverable clickable rows, and a paging footer.
///
/// Screens show this on desktop widths and keep their card lists on
/// phones, where a multi-column grid doesn't fit.
class AppDataTable<T> extends StatefulWidget {
  final List<AppDataColumn<T>> columns;
  final List<T> rows;
  final void Function(T row)? onRowTap;

  /// Search box, filter chips, counts… shown above the header.
  final Widget? toolbar;

  /// Shown in place of the rows when [rows] is empty.
  final Widget? empty;

  /// Trailing per-row actions (icon buttons), in a fixed-width column.
  final List<Widget> Function(T row)? actions;
  final double actionsWidth;

  final int pageSize;

  /// Shows a spinner / an error with a Retry button in place of the rows,
  /// keeping the toolbar in place.
  final bool loading;
  final String? error;
  final VoidCallback? onRetry;

  const AppDataTable({
    super.key,
    required this.columns,
    required this.rows,
    this.onRowTap,
    this.toolbar,
    this.empty,
    this.actions,
    this.actionsWidth = 96,
    this.pageSize = 25,
    this.loading = false,
    this.error,
    this.onRetry,
  });

  @override
  State<AppDataTable<T>> createState() => _AppDataTableState<T>();
}

class _AppDataTableState<T> extends State<AppDataTable<T>> {
  int? _sortColumn;
  bool _ascending = true;
  int _page = 0;

  @override
  void didUpdateWidget(covariant AppDataTable<T> old) {
    super.didUpdateWidget(old);
    // A new filter/search result can be shorter than the current page.
    if (_page * widget.pageSize >= widget.rows.length) _page = 0;
  }

  List<T> get _sorted {
    final i = _sortColumn;
    final key = i == null ? null : widget.columns[i].sortKey;
    if (key == null) return widget.rows;
    final list = [...widget.rows];
    list.sort((a, b) {
      final c = _compare(key(a), key(b));
      return _ascending ? c : -c;
    });
    return list;
  }

  static int _compare(Comparable<Object?>? a, Comparable<Object?>? b) {
    if (a == null && b == null) return 0;
    if (a == null) return 1; // blanks last
    if (b == null) return -1;
    return a.compareTo(b);
  }

  void _toggleSort(int i) => setState(() {
        if (_sortColumn == i) {
          _ascending = !_ascending;
        } else {
          _sortColumn = i;
          _ascending = true;
        }
        _page = 0;
      });

  Widget _sized(AppDataColumn<T> c, Widget child) => c.width != null
      ? SizedBox(width: c.width, child: child)
      : Expanded(flex: c.flex, child: child);

  @override
  Widget build(BuildContext context) {
    final rows = _sorted;
    final total = rows.length;
    final pages = (total / widget.pageSize).ceil().clamp(1, 1 << 30);
    final start = _page * widget.pageSize;
    final visible = rows.skip(start).take(widget.pageSize).toList();

    return Container(
      decoration: BoxDecoration(
        color: AppTheme.cardBg,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppTheme.border),
      ),
      clipBehavior: Clip.antiAlias,
      child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        if (widget.toolbar != null) ...[
          Padding(padding: const EdgeInsets.fromLTRB(16, 12, 16, 12), child: widget.toolbar),
          const Divider(height: 1),
        ],
        _header(),
        const Divider(height: 1),
        if (widget.loading)
          const Padding(
            padding: EdgeInsets.symmetric(vertical: 48),
            child: Center(child: CircularProgressIndicator(color: AppTheme.primary)),
          )
        else if (widget.error != null)
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 40, horizontal: 16),
            child: Column(children: [
              Text(widget.error!, textAlign: TextAlign.center, style: const TextStyle(color: AppTheme.error)),
              if (widget.onRetry != null) ...[
                const SizedBox(height: 12),
                OutlinedButton(onPressed: widget.onRetry, child: const Text('Retry')),
              ],
            ]),
          )
        else if (total == 0)
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 40, horizontal: 16),
            child: widget.empty ??
                const Center(
                  child: Text('No records', style: TextStyle(color: AppTheme.textSecondary)),
                ),
          )
        else
          for (var i = 0; i < visible.length; i++) ...[
            if (i > 0) const Divider(height: 1),
            _row(visible[i]),
          ],
        if (total > 0 && !widget.loading && widget.error == null) ...[
          const Divider(height: 1),
          _footer(start, visible.length, total, pages),
        ],
      ]),
    );
  }

  Widget _header() => Container(
        color: AppTheme.surface.withOpacity(0.6),
        padding: const EdgeInsets.symmetric(horizontal: 16),
        height: 44,
        child: Row(children: [
          for (var i = 0; i < widget.columns.length; i++)
            _sized(widget.columns[i], _headerCell(i)),
          if (widget.actions != null) SizedBox(width: widget.actionsWidth),
        ]),
      );

  Widget _headerCell(int i) {
    final c = widget.columns[i];
    final active = _sortColumn == i;
    final label = Text(
      c.label,
      maxLines: 1,
      overflow: TextOverflow.ellipsis,
      style: TextStyle(
        fontSize: 12.5,
        fontWeight: FontWeight.w600,
        color: active ? AppTheme.textPrimary : AppTheme.textSecondary,
      ),
    );
    final content = Row(
      mainAxisAlignment: c.numeric ? MainAxisAlignment.end : MainAxisAlignment.start,
      children: [
        Flexible(child: label),
        if (c.sortKey != null)
          Padding(
            padding: const EdgeInsets.only(left: 4),
            child: Icon(
              active
                  ? (_ascending ? Icons.arrow_upward_rounded : Icons.arrow_downward_rounded)
                  : Icons.unfold_more_rounded,
              size: 14,
              color: active ? AppTheme.primary : AppTheme.textTertiary,
            ),
          ),
      ],
    );
    return Padding(
      padding: const EdgeInsets.only(right: 16),
      child: c.sortKey == null
          ? content
          : InkWell(
              borderRadius: BorderRadius.circular(6),
              onTap: () => _toggleSort(i),
              child: Padding(padding: const EdgeInsets.symmetric(vertical: 6), child: content),
            ),
    );
  }

  Widget _row(T r) => Material(
        color: Colors.transparent,
        child: InkWell(
          onTap: widget.onRowTap == null ? null : () => widget.onRowTap!(r),
          hoverColor: AppTheme.primarySoft.withOpacity(0.5),
          child: ConstrainedBox(
            constraints: const BoxConstraints(minHeight: 52),
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
              child: Row(children: [
                for (final c in widget.columns)
                  _sized(
                    c,
                    Padding(
                      padding: const EdgeInsets.only(right: 16),
                      child: Align(
                        alignment: c.numeric ? Alignment.centerRight : Alignment.centerLeft,
                        child: c.cell(r),
                      ),
                    ),
                  ),
                if (widget.actions != null)
                  SizedBox(
                    width: widget.actionsWidth,
                    child: Row(mainAxisAlignment: MainAxisAlignment.end, children: widget.actions!(r)),
                  ),
              ]),
            ),
          ),
        ),
      );

  Widget _footer(int start, int shown, int total, int pages) => Padding(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
        child: Row(children: [
          Text(
            '${start + 1}–${start + shown} of $total',
            style: const TextStyle(fontSize: 12.5, color: AppTheme.textSecondary),
          ),
          const Spacer(),
          if (pages > 1) ...[
            Text('Page ${_page + 1} of $pages',
                style: const TextStyle(fontSize: 12.5, color: AppTheme.textSecondary)),
            const SizedBox(width: 8),
            IconButton(
              tooltip: 'Previous page',
              iconSize: 20,
              icon: const Icon(Icons.chevron_left_rounded),
              onPressed: _page == 0 ? null : () => setState(() => _page--),
            ),
            IconButton(
              tooltip: 'Next page',
              iconSize: 20,
              icon: const Icon(Icons.chevron_right_rounded),
              onPressed: _page >= pages - 1 ? null : () => setState(() => _page++),
            ),
          ],
        ]),
      );
}

/// Small colored status label for table cells.
class StatusPill extends StatelessWidget {
  final String label;
  final Color color;
  const StatusPill(this.label, this.color, {super.key});

  @override
  Widget build(BuildContext context) => Container(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
        decoration: BoxDecoration(color: color.withOpacity(0.12), borderRadius: BorderRadius.circular(6)),
        child: Text(
          label,
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
          style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: color),
        ),
      );
}

/// Two-line cell: a primary value with a muted secondary line under it.
class TwoLineCell extends StatelessWidget {
  final String title;
  final String? subtitle;
  const TwoLineCell(this.title, [this.subtitle]);

  @override
  Widget build(BuildContext context) => Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(fontSize: 13.5, fontWeight: FontWeight.w600, color: AppTheme.textPrimary)),
          if (subtitle != null && subtitle!.isNotEmpty)
            Text(subtitle!,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
        ],
      );
}

/// A page's primary action as a header button — the desktop counterpart
/// of a phone screen's floating action button. Put it in `AppBar.actions`.
class HeaderActionButton extends StatelessWidget {
  final IconData icon;
  final String label;
  final VoidCallback? onPressed;
  const HeaderActionButton({super.key, required this.icon, required this.label, this.onPressed});

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.only(left: 8, right: 24),
        child: FilledButton.icon(onPressed: onPressed, icon: Icon(icon, size: 18), label: Text(label)),
      );
}

/// Width-limited search field for a table toolbar.
class TableSearchField extends StatelessWidget {
  final TextEditingController? controller;
  final String hint;
  final ValueChanged<String> onChanged;
  final double width;
  const TableSearchField({
    super.key,
    this.controller,
    required this.hint,
    required this.onChanged,
    this.width = 320,
  });

  @override
  Widget build(BuildContext context) => SizedBox(
        width: width,
        child: TextField(
          controller: controller,
          onChanged: onChanged,
          decoration: InputDecoration(
            hintText: hint,
            prefixIcon: const Icon(Icons.search_rounded, size: 20),
            contentPadding: const EdgeInsets.symmetric(vertical: 10),
            isDense: true,
          ),
        ),
      );
}

/// Date/time for table cells: "25 Sep 2026, 14:05" (local time), or "—".
String tableDateTime(DateTime? d) => d == null ? '—' : DateFormat('d MMM yyyy, HH:mm').format(d.toLocal());

/// Date for table cells: "25 Sep 2026", or "—".
String tableDate(DateTime? d) => d == null ? '—' : DateFormat('d MMM yyyy').format(d.toLocal());

final _inr = NumberFormat.currency(locale: 'en_IN', symbol: '₹', decimalDigits: 2);

/// Amount for table cells with Indian digit grouping: "₹1,40,892.00".
/// Accepts the API's decimal strings or numbers; null/blank gives "—".
String tableMoney(Object? v) {
  if (v == null || (v is String && v.trim().isEmpty)) return '—';
  final n = v is num ? v : double.tryParse(v.toString());
  return n == null ? v.toString() : _inr.format(n);
}
