import 'dart:convert';

import 'package:csv/csv.dart';
import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/resident_master/data/import_columns.dart' show parseImportDate;
import 'package:ar_society_app/features/society_structure/presentation/providers/structure_providers.dart';
import 'package:ar_society_app/shared/utils/csv_file.dart';
import 'package:ar_society_app/shared/widgets/app_form.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';

enum _Status { ready, error, updated, unchanged }

class _Row {
  final int line;
  final String wing, flat, date; // as typed, for the preview and the error file
  final Map<String, dynamic>? payload; // null: failed on this device, never sent
  final _Status status;
  final String? message;
  const _Row(this.line, this.wing, this.flat, this.date, this.payload, this.status, [this.message]);
  _Row with_(_Status s, [String? m]) => _Row(line, wing, flat, date, payload, s, m);
}

const _header = ['Wing', 'Flat Number', 'Possession Date'];

const _aliases = <String, List<String>>{
  'wing': ['wing', 'wing name', 'building', 'block', 'tower'],
  'flat': ['flat number', 'flat no', 'flat', 'flat num', 'unit', 'unit no', 'flat no.', 'flat/unit no'],
  'date': [
    'possession date', 'date of possession', 'possession', 'possession dt', 'handover date', 'date of handover',
  ],
};

String _norm(String s) => s.toLowerCase().replaceAll(RegExp(r'[_\-.]'), ' ').replaceAll(RegExp(r'\s+'), ' ').trim();

/// Set the possession date of many flats from a sheet (Excel → Save as CSV): columns Wing, Flat Number and
/// Possession Date. A flat with no date gets one; a flat that has one is changed to the date in the file. Every row
/// is checked by the server first (nothing is saved); flats are never added here.
class FlatPossessionImportScreen extends ConsumerStatefulWidget {
  const FlatPossessionImportScreen({super.key});

  @override
  ConsumerState<FlatPossessionImportScreen> createState() => _FlatPossessionImportScreenState();
}

class _FlatPossessionImportScreenState extends ConsumerState<FlatPossessionImportScreen> {
  List<_Row>? _rows;
  String? _fileError;
  bool _busy = false;
  bool _done = false;

  int _count(_Status s) => (_rows ?? []).where((r) => r.status == s).length;

  String _fmt(DateTime d) =>
      '${d.day.toString().padLeft(2, '0')}/${d.month.toString().padLeft(2, '0')}/${d.year}';

  String _iso(DateTime d) =>
      '${d.year.toString().padLeft(4, '0')}-${d.month.toString().padLeft(2, '0')}-${d.day.toString().padLeft(2, '0')}';

  /// Every flat of the society with the date it has now (blank when none): fill in the blanks and change the rest.
  Future<void> _template() async {
    setState(() => _busy = true);
    try {
      final flats = await ref.read(flatsBySocietyProvider.future);
      final csv = const ListToCsvConverter().convert([
        _header,
        if (flats.isEmpty)
          ['Wing A', '101', '01/04/2019']
        else
          for (final f in flats) [f.wingName ?? '', f.flatNumber, f.possessionDate == null ? '' : _fmt(f.possessionDate!)],
      ]);
      if (await saveCsvFile(csv, 'flat_possession_dates.csv') && mounted) {
        AppToast.success(context, 'Template downloaded');
      }
    } catch (e) {
      if (mounted) showErrorToast(context, e);
    } finally {
      if (mounted) setState(() => _busy = false);
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
      final sendable = rows.where((r) => r.payload != null).toList();
      final outcomes = sendable.isEmpty ? <Map<String, dynamic>>[] : await _send(sendable, dryRun: true);
      setState(() => _rows = _merge(rows, outcomes, final_: false));
    } catch (e) {
      setState(() => _fileError = 'Could not read that file: ${friendlyErrorMessage(e)}');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<List<Map<String, dynamic>>> _send(List<_Row> rows, {required bool dryRun}) async {
    final r = await ApiClient.instance
        .post('/flats/possession-import', data: {'rows': [for (final x in rows) x.payload!], 'dry_run': dryRun});
    return [for (final o in r.data as List) o as Map<String, dynamic>];
  }

  List<_Row> _merge(List<_Row> rows, List<Map<String, dynamic>> outcomes, {required bool final_}) {
    final byLine = {for (final o in outcomes) o['line']: o};
    return [
      for (final r in rows)
        if (r.status == _Status.error && r.payload == null || (final_ && r.status != _Status.ready))
          r
        else
          switch (byLine[r.line]) {
            final o? when o['status'] == 'error' => r.with_(_Status.error, o['message'] as String?),
            final o? when o['status'] == 'unchanged' => r.with_(_Status.unchanged, 'Already has this date'),
            final o? when o['status'] == 'updated' => r.with_(
                final_ ? _Status.updated : _Status.ready,
                [
                  if (o['previous'] == null)
                    'Date will be added'
                  else if (o['previous'] != r.payload?['possession_date'])
                    'Replaces ${_fmt(DateTime.parse(o['previous'] as String))}',
                  // Residents marked as moved in on this date, or why no one was
                  if (o['message'] != null) o['message'] as String,
                ].join(' · ')),
            _ => r.with_(_Status.error, 'Not imported'),
          },
    ];
  }

  List<_Row> _parse(String csv) {
    final table = readCsvRows(csv).where((r) => r.any((c) => c.toString().trim().isNotEmpty)).toList();
    if (table.isEmpty) return [];
    final head = table.first.map((c) => _norm(c.toString())).toList();
    int? col(String key) {
      final i = head.indexWhere((h) => _aliases[key]!.map(_norm).contains(h));
      return i < 0 ? null : i;
    }

    final wingC = col('wing'), flatC = col('flat'), dateC = col('date');
    final hasHeader = flatC != null && dateC != null;
    final w = hasHeader ? wingC : 0, f = hasHeader ? flatC : 1, d = hasHeader ? dateC : 2;
    String at(List<String> raw, int? i) => i == null || i >= raw.length ? '' : raw[i];

    final out = <_Row>[];
    for (var i = hasHeader ? 1 : 0; i < table.length; i++) {
      final raw = table[i].map((c) => c.toString().trim()).toList();
      final wing = at(raw, w), flat = at(raw, f), date = at(raw, d);
      final line = i + 1;
      String? error;
      String? iso;
      if (flat.isEmpty) {
        error = 'Flat number is required';
      } else if (date.isEmpty) {
        error = 'Possession Date is empty';
      } else {
        final parsed = parseImportDate(date);
        if (parsed == null) {
          error = 'Possession Date "$date" is not a date (use dd/mm/yyyy)';
        } else {
          iso = _iso(parsed);
        }
      }
      out.add(error != null
          ? _Row(line, wing, flat, date, null, _Status.error, error)
          : _Row(line, wing, flat, date, {'line': line, 'wing': wing, 'flat_number': flat, 'possession_date': iso}, _Status.ready));
    }
    return out;
  }

  Future<void> _import() async {
    setState(() => _busy = true);
    final rows = _rows!;
    try {
      final outcomes = await _send(rows.where((r) => r.status == _Status.ready).toList(), dryRun: false);
      setState(() {
        _rows = _merge(rows, outcomes, final_: true);
        _done = true;
      });
      ref.invalidate(flatsBySocietyProvider);
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
      [..._header, 'Error'],
      for (final r in bad) [r.wing, r.flat, r.date, r.message ?? 'Not imported'],
    ]);
    if (await saveCsvFile(csv, 'flat_possession_errors.csv') && mounted) AppToast.success(context, 'Error rows downloaded');
  }

  @override
  Widget build(BuildContext context) => AppPage(
        title: 'Import Possession Dates',
        body: ResponsiveBody(child: _rows == null ? _intro() : _preview()),
      );

  Widget _intro() => ListView(padding: const EdgeInsets.all(20), children: [
        Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: AppTheme.primary.withOpacity(0.06),
            borderRadius: BorderRadius.circular(AppTheme.radiusM),
            border: Border.all(color: AppTheme.primary.withOpacity(0.15)),
          ),
          child: const Text(
            '1. Download the sheet: it lists every flat with the possession date it has now (blank if none).\n'
            '2. Fill in or change the Possession Date in Excel (dd/mm/yyyy), then File → Save As → CSV.\n'
            '3. Choose the CSV here. A flat with no date gets one; a flat that has one is changed to the date in '
            'the file. Flats are found by Wing + Flat Number (Wing can be left out if the number is used only once). '
            'Each row is checked first and nothing is saved until you press Import.',
            style: TextStyle(fontSize: 13, height: 1.5),
          ),
        ),
        const SizedBox(height: 24),
        SizedBox(
          height: 52,
          child: OutlinedButton.icon(
              onPressed: _busy ? null : _template, icon: const Icon(Icons.download_rounded), label: const Text('Download Flats Sheet')),
        ),
        const SizedBox(height: 14),
        AppPrimaryButton(label: 'Choose CSV File', icon: Icons.upload_file_rounded, isLoading: _busy, onPressed: _busy ? null : _pick),
        if (_fileError != null) ...[const SizedBox(height: 16), AppErrorBanner(message: _fileError!)],
      ]);

  Widget _preview() {
    final rows = _rows!;
    final ready = _count(_Status.ready);
    final errors = _count(_Status.error);
    final updated = _count(_Status.updated);
    final same = _count(_Status.unchanged);
    return Column(children: [
      Padding(
        padding: const EdgeInsets.fromLTRB(20, 16, 20, 8),
        child: Row(children: [
          Expanded(
            child: Text(
              _done
                  ? '$updated updated${same > 0 ? ', $same unchanged' : ''}${errors > 0 ? ', $errors not imported' : ''}'
                  : '$ready to update${same > 0 ? ', $same unchanged' : ''}${errors > 0 ? ', $errors need fixing' : ''}',
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
                  label: _busy ? 'Importing…' : 'Update $ready Flat${ready == 1 ? '' : 's'}',
                  icon: Icons.file_download_done_rounded,
                  isLoading: _busy,
                  onPressed: (_busy || ready == 0) ? null : _import,
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
      _Status.updated => (AppTheme.success, Icons.check_circle_rounded),
      _Status.unchanged => (AppTheme.textSecondary, Icons.drag_handle_rounded),
    };
    final name = [row.wing, row.flat].where((s) => s.isNotEmpty).join(' - ');
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(color: AppTheme.cardBg, borderRadius: BorderRadius.circular(AppTheme.radiusS), border: Border.all(color: AppTheme.border)),
      child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Icon(icon, color: color, size: 18),
        const SizedBox(width: 10),
        Expanded(
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text('Row ${row.line}: ${name.isEmpty ? '(no flat)' : 'Flat $name'}'
                '${row.date.isEmpty ? '' : ' — ${row.date}'}',
                style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600)),
            if (row.message != null) Text(row.message!, style: TextStyle(fontSize: 11, color: color)),
          ]),
        ),
      ]),
    );
  }
}
