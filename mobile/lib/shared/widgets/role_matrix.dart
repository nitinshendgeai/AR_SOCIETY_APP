import 'package:flutter/material.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';

/// A column of a [RoleMatrix]: one permission tier or screen.
class MatrixColumn {
  final String key;
  final String label;
  final String? tooltip;

  /// Columns with the same group sit together under a group header.
  final String? group;

  const MatrixColumn({required this.key, required this.label, this.tooltip, this.group});
}

/// A row of a [RoleMatrix]: one role and the column keys it's granted.
class MatrixRow {
  final String roleId;
  final String roleName;
  final Set<String> granted;
  const MatrixRow({required this.roleId, required this.roleName, required this.granted});
}

/// Roles × grants editor laid out as a spreadsheet: the Role column and the
/// header rows stay frozen while the grid scrolls in both directions, and
/// both scrollbars are always visible so wide matrices are obviously
/// scrollable. Each cell is a checkbox that saves immediately via [onToggle].
class RoleMatrix extends StatefulWidget {
  final List<MatrixColumn> columns;
  final List<MatrixRow> rows;
  final Future<void> Function(String roleId, String key, bool value) onToggle;

  /// One-line explanation shown in the toolbar.
  final String description;

  /// What a column is called in the summary ("tiers", "screens").
  final String columnNoun;

  const RoleMatrix({
    super.key,
    required this.columns,
    required this.rows,
    required this.onToggle,
    required this.description,
    this.columnNoun = 'columns',
  });

  @override
  State<RoleMatrix> createState() => _RoleMatrixState();
}

class _RoleMatrixState extends State<RoleMatrix> {
  static const _minCellWidth = 124.0;
  static const _rowHeight = 44.0;
  static const _groupHeight = 30.0;
  static const _headerHeight = 56.0;

  final _hHeader = ScrollController();
  final _hBody = ScrollController();
  final _vRoles = ScrollController();
  final _vBody = ScrollController();
  bool _syncing = false;

  /// Column width for the current layout: at least [_minCellWidth], wider
  /// when a short matrix would otherwise leave the grid half empty.
  double _cellWidth = _minCellWidth;

  /// Phones get a narrower frozen column, tighter margins and a
  /// search-only toolbar so the grid itself keeps most of the screen.
  bool _compact = false;
  double get _roleWidth => _compact ? 150 : 220;
  double get _margin => _compact ? 8 : 24;

  String _query = '';
  String? _hoverRole;
  final _saving = <String>{};

  @override
  void initState() {
    super.initState();
    _link(_hBody, _hHeader);
    _link(_vBody, _vRoles);
    _link(_vRoles, _vBody);
  }

  /// Mirror [from]'s offset onto [to] (frozen header / frozen role column).
  void _link(ScrollController from, ScrollController to) {
    from.addListener(() {
      if (_syncing || !to.hasClients) return;
      _syncing = true;
      to.jumpTo(from.offset.clamp(0.0, to.position.maxScrollExtent));
      _syncing = false;
    });
  }

  @override
  void dispose() {
    for (final c in [_hHeader, _hBody, _vRoles, _vBody]) {
      c.dispose();
    }
    super.dispose();
  }

  Future<void> _toggle(MatrixRow row, MatrixColumn col, bool value) async {
    final id = '${row.roleId}/${col.key}';
    setState(() => _saving.add(id));
    try {
      await widget.onToggle(row.roleId, col.key, value);
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(
          content: Text(friendlyErrorMessage(e)),
          backgroundColor: AppTheme.error,
        ));
      }
    } finally {
      if (mounted) setState(() => _saving.remove(id));
    }
  }

  List<(String?, int)> get _groups {
    final groups = <(String?, int)>[];
    for (final c in widget.columns) {
      if (groups.isNotEmpty && groups.last.$1 == c.group) {
        groups[groups.length - 1] = (c.group, groups.last.$2 + 1);
      } else {
        groups.add((c.group, 1));
      }
    }
    return groups;
  }

  bool get _hasGroups => widget.columns.any((c) => c.group != null);

  @override
  Widget build(BuildContext context) {
    final q = _query.trim().toLowerCase();
    final rows = q.isEmpty ? widget.rows : widget.rows.where((r) => r.roleName.toLowerCase().contains(q)).toList();
    final headerHeight = _headerHeight + (_hasGroups ? _groupHeight : 0);

    return LayoutBuilder(builder: (context, constraints) {
      _compact = constraints.maxWidth < 600;
      // Both horizontal margins, plus 1 for the frozen column's divider.
      final available = constraints.maxWidth - 2 * _margin - _roleWidth - 1;
      final columns = widget.columns.isEmpty ? 1 : widget.columns.length;
      _cellWidth = (available / columns).floorToDouble().clamp(_minCellWidth, 220.0);
      final gridWidth = widget.columns.length * _cellWidth;
      return _card(rows, headerHeight, gridWidth, overflows: gridWidth > available);
    });
  }

  Widget _card(List<MatrixRow> rows, double headerHeight, double gridWidth, {required bool overflows}) {
    return Container(
      margin: EdgeInsets.fromLTRB(_margin, 8, _margin, _margin),
      decoration: BoxDecoration(
        color: AppTheme.cardBg,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppTheme.border),
      ),
      clipBehavior: Clip.antiAlias,
      child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        _toolbar(rows.length),
        const Divider(height: 1),
        // ── Frozen header ─────────────────────────────────────────────────
        SizedBox(
          height: headerHeight,
          child: Row(children: [
            _corner(headerHeight),
            const VerticalDivider(width: 1),
            Expanded(
              child: SingleChildScrollView(
                controller: _hHeader,
                scrollDirection: Axis.horizontal,
                physics: const NeverScrollableScrollPhysics(),
                child: SizedBox(
                  width: gridWidth,
                  child: Column(children: [
                    if (_hasGroups) _groupRow(),
                    Expanded(child: _headerRow()),
                  ]),
                ),
              ),
            ),
          ]),
        ),
        const Divider(height: 1),
        // ── Body: frozen role column + scrollable grid ────────────────────
        Expanded(
          child: Row(children: [
            SizedBox(
              width: _roleWidth,
              child: ScrollConfiguration(
                behavior: ScrollConfiguration.of(context).copyWith(scrollbars: false),
                child: ListView.builder(
                  controller: _vRoles,
                  itemCount: rows.length,
                  itemExtent: _rowHeight,
                  itemBuilder: (_, i) => _roleCell(rows[i], i),
                ),
              ),
            ),
            const VerticalDivider(width: 1),
            Expanded(
              child: Scrollbar(
                controller: _vBody,
                thumbVisibility: true,
                trackVisibility: true,
                notificationPredicate: (n) => n.depth == 1 && n.metrics.axis == Axis.vertical,
                child: Scrollbar(
                  controller: _hBody,
                  // Only when there is something to scroll to; a full-width
                  // thumb on a grid that fits just reads as clutter.
                  thumbVisibility: overflows,
                  trackVisibility: overflows,
                  child: ScrollConfiguration(
                    behavior: ScrollConfiguration.of(context).copyWith(scrollbars: false),
                    child: SingleChildScrollView(
                      controller: _hBody,
                      scrollDirection: Axis.horizontal,
                      child: SizedBox(
                        width: gridWidth,
                        child: ListView.builder(
                          controller: _vBody,
                          padding: const EdgeInsets.only(bottom: 12),
                          itemCount: rows.length,
                          itemExtent: _rowHeight,
                          itemBuilder: (_, i) => _gridRow(rows[i], i),
                        ),
                      ),
                    ),
                  ),
                ),
              ),
            ),
          ]),
        ),
      ]),
    );
  }

  Widget _search() => TextField(
        onChanged: (v) => setState(() => _query = v),
        decoration: const InputDecoration(
          hintText: 'Find a role…',
          prefixIcon: Icon(Icons.search_rounded, size: 20),
          isDense: true,
          contentPadding: EdgeInsets.symmetric(vertical: 10),
        ),
      );

  Widget _toolbar(int shown) => Padding(
        padding: const EdgeInsets.fromLTRB(16, 12, 16, 12),
        child: Row(children: [
          // Fixed width on desktop; takes the whole row on a phone.
          if (_compact) Expanded(child: _search()) else SizedBox(width: 260, child: _search()),
          if (!_compact) ...[
            const SizedBox(width: 16),
            Expanded(
              child: Text(widget.description,
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(fontSize: 12.5, color: AppTheme.textSecondary)),
            ),
            const SizedBox(width: 16),
            Text('$shown roles × ${widget.columns.length} ${widget.columnNoun}',
                style: const TextStyle(fontSize: 12.5, fontWeight: FontWeight.w600, color: AppTheme.textSecondary)),
          ],
        ]),
      );

  Widget _corner(double height) => Container(
        width: _roleWidth,
        height: height,
        color: AppTheme.surface.withOpacity(0.6),
        padding: const EdgeInsets.symmetric(horizontal: 16),
        alignment: Alignment.bottomLeft,
        child: const Padding(
          padding: EdgeInsets.only(bottom: 18),
          child: Text('Role', style: TextStyle(fontSize: 12.5, fontWeight: FontWeight.w700)),
        ),
      );

  Widget _groupRow() => SizedBox(
        height: _groupHeight,
        child: Row(children: [
          for (final (group, count) in _groups)
            Container(
              width: count * _cellWidth,
              alignment: Alignment.center,
              decoration: const BoxDecoration(
                color: AppTheme.primarySoft,
                border: Border(
                  right: BorderSide(color: AppTheme.cardBg, width: 2),
                  bottom: BorderSide(color: AppTheme.border),
                ),
              ),
              child: Text((group ?? 'Other').toUpperCase(),
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(
                      fontSize: 11, fontWeight: FontWeight.w700, letterSpacing: 0.6, color: AppTheme.primary)),
            ),
        ]),
      );

  Widget _headerRow() => Container(
        color: AppTheme.surface.withOpacity(0.6),
        child: Row(children: [
          for (final c in widget.columns)
            Tooltip(
              message: c.tooltip ?? c.label,
              waitDuration: const Duration(milliseconds: 400),
              child: Container(
                width: _cellWidth,
                padding: const EdgeInsets.symmetric(horizontal: 8),
                alignment: Alignment.center,
                child: Text(c.label,
                    textAlign: TextAlign.center,
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(fontSize: 12.5, fontWeight: FontWeight.w600, height: 1.25)),
              ),
            ),
        ]),
      );

  Color _rowColor(MatrixRow r, int i) => _hoverRole == r.roleId
      ? AppTheme.primarySoft.withOpacity(0.6)
      : i.isOdd
          ? AppTheme.surface.withOpacity(0.45)
          : AppTheme.cardBg;

  Widget _hoverable(MatrixRow r, Widget child) => MouseRegion(
        onEnter: (_) => setState(() => _hoverRole = r.roleId),
        onExit: (_) => setState(() => _hoverRole = _hoverRole == r.roleId ? null : _hoverRole),
        child: child,
      );

  Widget _roleCell(MatrixRow r, int i) => _hoverable(
        r,
        Container(
          color: _rowColor(r, i),
          padding: const EdgeInsets.symmetric(horizontal: 16),
          alignment: Alignment.centerLeft,
          child: Row(children: [
            Expanded(
              child: Tooltip(
                  message: r.roleName,
                  waitDuration: const Duration(milliseconds: 500),
                  child: Text(r.roleName,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(fontSize: 13.5, fontWeight: FontWeight.w600))),
            ),
            Text('${r.granted.intersection({for (final c in widget.columns) c.key}).length}',
                style: const TextStyle(fontSize: 12, color: AppTheme.textTertiary)),
          ]),
        ),
      );

  Widget _gridRow(MatrixRow r, int i) => _hoverable(
        r,
        Container(
          color: _rowColor(r, i),
          child: Row(children: [
            for (final c in widget.columns)
              SizedBox(
                width: _cellWidth,
                child: Center(
                  child: _saving.contains('${r.roleId}/${c.key}')
                      ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2))
                      : Tooltip(
                          message: '${r.roleName} · ${c.label}',
                          waitDuration: const Duration(milliseconds: 600),
                          child: Checkbox(
                            value: r.granted.contains(c.key),
                            onChanged: (v) => _toggle(r, c, v ?? false),
                          ),
                        ),
                ),
              ),
          ]),
        ),
      );
}
