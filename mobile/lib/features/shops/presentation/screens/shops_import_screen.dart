import 'dart:convert';

import 'package:csv/csv.dart';
import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/features/resident_master/data/import_columns.dart' show parseImportDate;
import 'package:ar_society_app/features/shops/data/shop_import_columns.dart';
import 'package:ar_society_app/features/shops/data/shops_api.dart';
import 'package:ar_society_app/features/shops/presentation/providers/shops_providers.dart';
import 'package:ar_society_app/shared/utils/csv_file.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';

enum _Status { ready, error, created, updated }

class _Row {
  final int line;
  final List<String> canonical; // template order, for the preview and the error file
  final Map<String, dynamic>? payload; // what is sent (null: failed on this device, never sent)
  final _Status status;
  final String? message;
  const _Row(this.line, this.canonical, this.payload, this.status, [this.message]);

  String get shopNumber => canonical[0];
  String get owner => canonical[1];
  _Row with_(_Status s, [String? m]) => _Row(line, canonical, payload, s, m);
}

/// Bring in the society's shops from a CSV: shop, owner, possession date, electricity meter and the rest. Columns
/// are found by their headings, so the society's own sheet works. Every row is checked by the server first (nothing
/// is saved), then the good rows go in; a shop whose number exists is filled in, not duplicated.
class ShopsImportScreen extends ConsumerStatefulWidget {
  const ShopsImportScreen({super.key});

  @override
  ConsumerState<ShopsImportScreen> createState() => _ShopsImportScreenState();
}

class _ShopsImportScreenState extends ConsumerState<ShopsImportScreen> {
  List<_Row>? _rows;
  String? _fileError;
  bool _busy = false;
  bool _done = false;

  int _count(_Status s) => (_rows ?? []).where((r) => r.status == s).length;
  bool get _hasGoodRows => _count(_Status.ready) > 0;

  Future<void> _template() async {
    final csv = const ListToCsvConverter().convert([
      shopImportTemplateHeader,
      ['S-1', 'Ramesh Mehta', '9876543210', 'ramesh@example.com', '0', 'Ground floor, Block C', '250', 'Mehta Stationers',
        'owner run', '', '', '01/04/2019', 'MTR-001234', '170012345678', ''],
    ]);
    if (await saveCsvFile(csv, 'shops_import_template.csv') && mounted) {
      AppToast.success(context, 'Template downloaded');
    }
  }

  String _decode(List<int> bytes) {
    var b = bytes;
    if (b.length >= 3 && b[0] == 0xEF && b[1] == 0xBB && b[2] == 0xBF) b = b.sublist(3);
    try {
      return utf8.decode(b);
    } on FormatException {
      return latin1.decode(b);
    }
  }

  Future<void> _pick() async {
    setState(() => _fileError = null);
    final result = await FilePicker.platform.pickFiles(type: FileType.custom, allowedExtensions: ['csv'], withData: true);
    final picked = result?.files.single;
    if (picked == null) return;
    setState(() => _busy = true);
    try {
      final bytes = picked.bytes;
      if (bytes == null) throw 'the file could not be read';
      final rows = _parse(_decode(bytes));
      if (rows.isEmpty) {
        setState(() => _fileError = 'No data rows found in that file.');
        return;
      }
      // The server checks every row (numbers already used, meters on two shops, bad values) and writes nothing.
      final sendable = rows.where((r) => r.payload != null).toList();
      final outcomes = sendable.isEmpty
          ? <ImportOutcome>[]
          : await ref.read(shopsApiProvider).importRows([for (final r in sendable) r.payload!], dryRun: true);
      final byLine = {for (final o in outcomes) o.line: o};
      setState(() => _rows = [
            for (final r in rows)
              if (r.payload == null)
                r
              else
                switch (byLine[r.line]) {
                  final o? when o.status == 'error' => r.with_(_Status.error, o.message),
                  final o? when o.status == 'updated' => r.with_(_Status.ready, 'Shop exists — will fill in what the file gives'),
                  _ => r,
                },
          ]);
    } catch (e) {
      setState(() => _fileError = 'Could not read that file: ${friendlyErrorMessage(e)}');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  List<_Row> _parse(String csv) {
    final table = readCsvRows(csv).where((r) => r.any((c) => c.toString().trim().isNotEmpty)).toList();
    if (table.isEmpty) return [];
    final header = ShopImportColumns.fromHeader(table.first.map((c) => c.toString().trim()).toList());
    final columns = header ?? ShopImportColumns.positional();
    final out = <_Row>[];
    for (var i = header != null ? 1 : 0; i < table.length; i++) {
      final raw = table[i].map((c) => c.toString().trim()).toList();
      final fields = columns.fields(raw);
      final canon = columns.canonical(raw);
      final line = i + 1;

      String? error;
      var possession = fields['possession_date'] ?? '';
      if (possession.isNotEmpty) {
        final d = parseImportDate(possession);
        if (d == null) {
          error = 'Possession Date "$possession" is not a date (use dd/mm/yyyy)';
        } else {
          possession = apiDate(d);
        }
      }
      if (error == null && (fields['shop_number'] ?? '').isEmpty) error = 'Shop number is required';

      if (error != null) {
        out.add(_Row(line, canon, null, _Status.error, error));
        continue;
      }
      out.add(_Row(line, canon, {'line': line, ...fields, 'possession_date': possession.isEmpty ? null : possession}, _Status.ready));
    }
    return out;
  }

  Future<void> _import() async {
    setState(() => _busy = true);
    final rows = _rows!;
    final sendable = rows.where((r) => r.status == _Status.ready).toList();
    try {
      final outcomes = await ref.read(shopsApiProvider).importRows([for (final r in sendable) r.payload!], dryRun: false);
      final byLine = {for (final o in outcomes) o.line: o};
      setState(() {
        _rows = [
          for (final r in rows)
            if (r.status != _Status.ready)
              r
            else
              switch (byLine[r.line]?.status) {
                'created' => r.with_(_Status.created),
                'updated' => r.with_(_Status.updated),
                _ => r.with_(_Status.error, byLine[r.line]?.message ?? 'Not imported'),
              },
        ];
        _done = true;
      });
      ref.invalidate(shopsProvider);
    } catch (e) {
      if (mounted) showErrorToast(context, e);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _exportErrors() async {
    final bad = (_rows ?? []).where((r) => r.status == _Status.error).toList();
    if (bad.isEmpty) return;
    final csv = const ListToCsvConverter().convert([
      [...shopImportTemplateHeader, 'Error'],
      for (final r in bad) [...r.canonical, r.message ?? 'Not imported'],
    ]);
    if (await saveCsvFile(csv, 'shops_import_errors.csv') && mounted) AppToast.success(context, 'Error rows downloaded');
  }

  @override
  Widget build(BuildContext context) {
    ref.watch(currentUserProvider);
    return Scaffold(
      backgroundColor: AppTheme.surface,
      appBar: AppBar(title: const Text('Import Shops')),
      body: ResponsiveBody(child: _rows == null ? _intro() : _preview()),
    );
  }

  Widget _intro() => ListView(padding: const EdgeInsets.all(20), children: [
        Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: AppTheme.primary.withOpacity(0.06),
            borderRadius: BorderRadius.circular(12),
            border: Border.all(color: AppTheme.primary.withOpacity(0.15)),
          ),
          child: const Text(
            '1. Download the template and fill it in (Excel, Google Sheets…), or use your own sheet: columns are found by '
            'their headings (Shop No, Owner, Possession Date, Meter No…), in any order.\n'
            '2. Only Shop Number and Owner Name are needed for a new shop. Dates are read day first (01/04/2019). '
            'Occupancy can be owner run, rented or vacant. Floor can be 0 or Ground.\n'
            '3. A shop number that already exists is filled in with what the file gives, not duplicated. '
            'Each row is checked first and nothing is saved until you press Import.',
            style: TextStyle(fontSize: 13, height: 1.5),
          ),
        ),
        const SizedBox(height: 24),
        SizedBox(
          height: 52,
          child: OutlinedButton.icon(onPressed: _template, icon: const Icon(Icons.download_rounded), label: const Text('Download Template')),
        ),
        const SizedBox(height: 14),
        AppPrimaryButton(label: 'Choose CSV File', icon: Icons.upload_file_rounded, isLoading: _busy, onPressed: _busy ? null : _pick),
        if (_fileError != null) ...[const SizedBox(height: 16), AppErrorBanner(message: _fileError!)],
      ]);

  Widget _preview() {
    final rows = _rows!;
    final ready = _count(_Status.ready);
    final errors = _count(_Status.error);
    final created = _count(_Status.created);
    final updated = _count(_Status.updated);
    return Column(children: [
      Padding(
        padding: const EdgeInsets.fromLTRB(20, 16, 20, 8),
        child: Row(children: [
          Expanded(
            child: Text(
              _done
                  ? '$created added, $updated updated${errors > 0 ? ', $errors not imported' : ''}'
                  : '$ready ready${errors > 0 ? ', $errors need fixing' : ''}',
              style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600),
            ),
          ),
          if (!_busy && !_done)
            TextButton(onPressed: () => setState(() { _rows = null; _fileError = null; }), child: const Text('Choose different file')),
        ]),
      ),
      Expanded(
        child: ListView.separated(
          padding: const EdgeInsets.symmetric(horizontal: 20),
          itemCount: rows.length,
          separatorBuilder: (_, __) => const SizedBox(height: 8),
          itemBuilder: (_, i) => _Tile(row: rows[i]),
        ),
      ),
      Padding(
        padding: const EdgeInsets.fromLTRB(20, 12, 20, 20),
        child: Column(children: [
          if (errors > 0) ...[
            SizedBox(
              width: double.infinity,
              child: OutlinedButton.icon(
                onPressed: _exportErrors,
                icon: const Icon(Icons.download_rounded),
                label: Text('Export $errors Error Row${errors == 1 ? '' : 's'} to Fix'),
              ),
            ),
            const SizedBox(height: 12),
          ],
          _done
              ? AppPrimaryButton(label: 'Done', onPressed: () => Navigator.pop(context, true))
              : AppPrimaryButton(
                  label: _busy ? 'Importing…' : 'Import $ready Shop${ready == 1 ? '' : 's'}',
                  icon: Icons.file_download_done_rounded,
                  isLoading: _busy,
                  onPressed: (_busy || !_hasGoodRows) ? null : _import,
                ),
        ]),
      ),
    ]);
  }
}

class _Tile extends StatelessWidget {
  final _Row row;
  const _Tile({required this.row});

  @override
  Widget build(BuildContext context) {
    final (color, icon) = switch (row.status) {
      _Status.ready => (AppTheme.textSecondary, Icons.radio_button_unchecked_rounded),
      _Status.error => (AppTheme.error, Icons.error_outline_rounded),
      _Status.created => (AppTheme.success, Icons.check_circle_rounded),
      _Status.updated => (AppTheme.primary, Icons.published_with_changes_rounded),
    };
    final meta = [row.canonical[7], row.canonical[11], row.canonical[12]].where((s) => s.isNotEmpty).join(' · ');
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(color: AppTheme.cardBg, borderRadius: BorderRadius.circular(10), border: Border.all(color: AppTheme.border)),
      child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Icon(icon, color: color, size: 18),
        const SizedBox(width: 10),
        Expanded(
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text('Row ${row.line}: ${row.shopNumber.isEmpty ? '(no shop number)' : 'Shop ${row.shopNumber}'}'
                '${row.owner.isEmpty ? '' : ' — ${row.owner}'}',
                style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600)),
            if (meta.isNotEmpty) Text(meta, style: const TextStyle(fontSize: 11, color: AppTheme.textSecondary)),
            if (row.message != null) Text(row.message!, style: TextStyle(fontSize: 11, color: color)),
          ]),
        ),
      ]),
    );
  }
}
