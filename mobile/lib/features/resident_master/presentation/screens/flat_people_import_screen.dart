import 'dart:convert';

import 'package:csv/csv.dart';
import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/resident_master/data/flat_people_import.dart';
import 'package:ar_society_app/shared/utils/csv_file.dart';
import 'package:ar_society_app/shared/widgets/app_form.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';

final peopleImportApiProvider = Provider<PeopleImportApi>((_) => PeopleImportApi());

enum _Status { ready, error, skipped, created }

class _Row {
  final int line;
  final List<String> canonical; // template order, for the preview and the error file
  final Map<String, dynamic>? payload; // what is sent (null: failed on this device, never sent)
  final _Status status;
  final String? message;
  const _Row(this.line, this.canonical, this.payload, this.status, [this.message]);

  _Row with_(_Status s, [String? m]) => _Row(line, canonical, payload, s, m);
}

/// Bring in each flat's vehicles or family members from a CSV. Columns are found by their headings, so the society's own
/// sheet works. Every row is checked by the server first (nothing is saved); then the good rows go in. Something already
/// on the flat is skipped, so a corrected file can be imported again.
class FlatPeopleImportScreen extends ConsumerStatefulWidget {
  final PeopleImportSpec spec;
  const FlatPeopleImportScreen({super.key, required this.spec});

  @override
  ConsumerState<FlatPeopleImportScreen> createState() => _FlatPeopleImportScreenState();
}

class _FlatPeopleImportScreenState extends ConsumerState<FlatPeopleImportScreen> {
  PeopleImportSpec get spec => widget.spec;
  List<_Row>? _rows;
  String? _fileError;
  bool _busy = false;
  bool _done = false;

  int _count(_Status s) => (_rows ?? []).where((r) => r.status == s).length;

  /// The key columns of a row: which flat, and which vehicle or person.
  String get _itemKey => spec.kind == 'vehicles' ? 'vehicle_number' : 'full_name';
  String get _itemLabel => spec.kind == 'vehicles' ? 'Vehicle number' : 'Name';

  Future<void> _template() async {
    final csv = const ListToCsvConverter().convert([spec.templateHeader, ...spec.templateExamples]);
    if (await saveCsvFile(csv, '${spec.fileName}_template.csv') && mounted) AppToast.success(context, 'Template downloaded');
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
      // The server checks every row (unknown flats, repeats, bad numbers and dates) and writes nothing.
      final sendable = rows.where((r) => r.payload != null).toList();
      final outcomes = sendable.isEmpty
          ? <PeopleImportOutcome>[]
          : await ref.read(peopleImportApiProvider).importRows(spec, [for (final r in sendable) r.payload!], dryRun: true);
      final byLine = {for (final o in outcomes) o.line: o};
      setState(() => _rows = [
            for (final r in rows)
              if (r.payload == null)
                r
              else
                switch (byLine[r.line]) {
                  final o? when o.status == 'error' => r.with_(_Status.error, o.message),
                  final o? when o.status == 'skipped' => r.with_(_Status.skipped, o.message),
                  final o? when o.message != null => r.with_(_Status.ready, o.message),
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
    final header = PeopleImportColumns.fromHeader(spec, table.first.map((c) => c.toString().trim()).toList());
    final columns = header ?? PeopleImportColumns.positional(spec);
    final out = <_Row>[];
    for (var i = header != null ? 1 : 0; i < table.length; i++) {
      final raw = table[i].map((c) => c.toString().trim()).toList();
      final fields = Map<String, dynamic>.from(columns.fields(raw));
      final canon = columns.canonical(raw);
      final line = i + 1;
      String? error;
      if (((fields['flat_number'] as String?) ?? '').isEmpty) error = 'Flat number is required';
      if (error == null && ((fields[_itemKey] as String?) ?? '').isEmpty) error = '$_itemLabel is required';
      if (error != null) {
        out.add(_Row(line, canon, null, _Status.error, error));
        continue;
      }
      out.add(_Row(line, canon, {'line': line, ...fields}, _Status.ready));
    }
    return out;
  }

  Future<void> _import() async {
    setState(() => _busy = true);
    final rows = _rows!;
    final sendable = rows.where((r) => r.status == _Status.ready).toList();
    try {
      final outcomes = await ref.read(peopleImportApiProvider).importRows(spec, [for (final r in sendable) r.payload!], dryRun: false);
      final byLine = {for (final o in outcomes) o.line: o};
      setState(() {
        _rows = [
          for (final r in rows)
            if (r.status != _Status.ready)
              r
            else
              switch (byLine[r.line]?.status) {
                'created' => r.with_(_Status.created, byLine[r.line]?.message),
                'skipped' => r.with_(_Status.skipped, byLine[r.line]?.message),
                _ => r.with_(_Status.error, byLine[r.line]?.message ?? 'Not imported'),
              },
        ];
        _done = true;
      });
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
      [...spec.templateHeader, 'Error'],
      for (final r in bad) [...r.canonical, r.message ?? 'Not imported'],
    ]);
    if (await saveCsvFile(csv, '${spec.fileName}_errors.csv') && mounted) AppToast.success(context, 'Error rows downloaded');
  }

  @override
  Widget build(BuildContext context) =>
      AppPage(title: spec.title, body: ResponsiveBody(child: _rows == null ? _intro() : _preview()));

  Widget _intro() => ListView(padding: const EdgeInsets.all(20), children: [
        Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: AppTheme.primary.withOpacity(0.06),
            borderRadius: BorderRadius.circular(AppTheme.radiusM),
            border: Border.all(color: AppTheme.primary.withOpacity(0.15)),
          ),
          child: Text(spec.intro, style: const TextStyle(fontSize: 13, height: 1.5)),
        ),
        const SizedBox(height: 24),
        SizedBox(
          height: 52,
          child: OutlinedButton.icon(
              key: const Key('people-import-template'),
              onPressed: _template,
              icon: const Icon(Icons.download_rounded),
              label: const Text('Download Template')),
        ),
        const SizedBox(height: 14),
        AppPrimaryButton(
            label: 'Choose CSV File', icon: Icons.upload_file_rounded, isLoading: _busy, onPressed: _busy ? null : _pick),
        if (_fileError != null) ...[const SizedBox(height: 16), AppErrorBanner(message: _fileError!)],
      ]);

  Widget _preview() {
    final rows = _rows!;
    final ready = _count(_Status.ready);
    final errors = _count(_Status.error);
    final skipped = _count(_Status.skipped);
    final created = _count(_Status.created);
    final plural = spec.kind == 'vehicles' ? 'vehicles' : 'family members';
    return Column(children: [
      Padding(
        padding: const EdgeInsets.fromLTRB(20, 16, 20, 8),
        child: Row(children: [
          Expanded(
            child: Text(
              _done
                  ? '$created added${skipped > 0 ? ', $skipped already there' : ''}${errors > 0 ? ', $errors not imported' : ''}'
                  : '$ready ready${skipped > 0 ? ', $skipped already there' : ''}${errors > 0 ? ', $errors need fixing' : ''}',
              key: const Key('people-import-summary'),
              style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600),
            ),
          ),
          if (!_busy && !_done)
            TextButton(
                onPressed: () => setState(() {
                      _rows = null;
                      _fileError = null;
                    }),
                child: const Text('Choose different file')),
        ]),
      ),
      Expanded(
        child: ListView.separated(
          padding: const EdgeInsets.symmetric(horizontal: 20),
          itemCount: rows.length,
          separatorBuilder: (_, __) => const SizedBox(height: 8),
          itemBuilder: (_, i) => _Tile(row: rows[i], spec: spec),
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
                  key: const Key('people-import-go'),
                  label: _busy ? 'Importing…' : 'Import $ready ${ready == 1 ? spec.noun : plural}',
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
  final PeopleImportSpec spec;
  const _Tile({required this.row, required this.spec});

  @override
  Widget build(BuildContext context) {
    final (color, icon) = switch (row.status) {
      _Status.ready => (AppTheme.textSecondary, Icons.radio_button_unchecked_rounded),
      _Status.error => (AppTheme.error, Icons.error_outline_rounded),
      _Status.skipped => (AppTheme.primary, Icons.skip_next_rounded),
      _Status.created => (AppTheme.success, Icons.check_circle_rounded),
    };
    String at(String key) => row.canonical[spec.keys.indexOf(key)];
    final flat = [at('wing'), at('flat_number')].where((s) => s.isNotEmpty).join(' ');
    final item = spec.kind == 'vehicles' ? at('vehicle_number') : at('full_name');
    final meta = (spec.kind == 'vehicles'
            ? [at('vehicle_type'), at('make'), at('model'), at('color'), at('parking_slot'), if (at('owner_name').isNotEmpty) 'owner ${at('owner_name')}']
            : [at('relationship'), at('phone'), at('date_of_birth')])
        .where((s) => s.isNotEmpty)
        .join(' · ');
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
          color: AppTheme.cardBg, borderRadius: BorderRadius.circular(AppTheme.radiusS), boxShadow: AppTheme.cardShadow),
      child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Icon(icon, color: color, size: 18),
        const SizedBox(width: 10),
        Expanded(
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text('Row ${row.line}: ${flat.isEmpty ? '(no flat)' : 'Flat $flat'}${item.isEmpty ? '' : ' — $item'}',
                style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600)),
            if (meta.isNotEmpty) Text(meta, style: const TextStyle(fontSize: 11, color: AppTheme.textSecondary)),
            if (row.message != null) Text(row.message!, style: TextStyle(fontSize: 11, color: color)),
          ]),
        ),
      ]),
    );
  }
}
