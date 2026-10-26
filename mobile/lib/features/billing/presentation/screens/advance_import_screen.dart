import 'dart:convert';

import 'package:csv/csv.dart';
import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/features/billing/presentation/providers/billing_providers.dart';
import 'package:ar_society_app/features/resident_master/data/import_columns.dart' show parseImportDate;
import 'package:ar_society_app/features/society_structure/presentation/providers/structure_providers.dart';
import 'package:ar_society_app/shared/utils/csv_file.dart';
import 'package:ar_society_app/shared/widgets/app_form.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';

enum _Status { ready, error, recorded }

class _Row {
  final int line;
  final List<String> cells; // header order, for the preview and the error file
  final Map<String, dynamic>? payload; // null: failed on this device, never sent
  final _Status status;
  final String? message;
  const _Row(this.line, this.cells, this.payload, this.status, [this.message]);

  String get wing => cells[0];
  String get flat => cells[1];
  String get amount => cells[2];
  _Row with_(_Status s, [String? m]) => _Row(line, cells, payload, s, m);
}

const _header = ['Wing', 'Flat Number', 'Amount', 'Payment Date', 'Payment Mode', 'Cheque / UTR No', 'Bank Name', 'Notes'];
const _keys = ['wing', 'flat', 'amount', 'date', 'mode', 'ref', 'bank', 'notes'];

const _aliases = <String, List<String>>{
  'wing': ['wing', 'wing name', 'building', 'block', 'tower'],
  'flat': ['flat number', 'flat no', 'flat', 'flat num', 'unit', 'unit no', 'flat no.', 'flat/unit no'],
  'amount': ['amount', 'advance amount', 'advance', 'amount paid', 'amount (₹)', 'amount received', 'paid'],
  'date': ['payment date', 'date', 'date of payment', 'received on', 'date received', 'paid on', 'receipt date'],
  'mode': ['payment mode', 'mode', 'mode of payment', 'paid by', 'payment type'],
  'ref': [
    'cheque / utr no', 'cheque no', 'utr', 'utr no', 'reference', 'ref no', 'transaction ref', 'cheque / utr',
    'transaction id', 'cheque number', 'ref',
  ],
  'bank': ['bank name', 'bank', 'drawn on'],
  'notes': ['notes', 'note', 'remarks', 'remark', 'narration'],
};

String _norm(String s) => s.toLowerCase().replaceAll(RegExp(r'[_\-.]'), ' ').replaceAll(RegExp(r'\s+'), ' ').trim();

/// Bring in the maintenance members paid in advance, from a sheet (Excel → Save as CSV): one payment per row with
/// the flat, amount, date and mode. Each is recorded like Record Payment on account — a receipt is issued and the
/// money is kept as the flat's advance in the "Advance Maintenance from Members" ledger — and is set off against the
/// flat's bills as they are raised. Every row is checked by the server first (nothing is saved).
class AdvanceImportScreen extends ConsumerStatefulWidget {
  const AdvanceImportScreen({super.key});

  @override
  ConsumerState<AdvanceImportScreen> createState() => _AdvanceImportScreenState();
}

class _AdvanceImportScreenState extends ConsumerState<AdvanceImportScreen> {
  List<_Row>? _rows;
  String? _fileError;
  bool _busy = false;
  bool _done = false;

  int _count(_Status s) => (_rows ?? []).where((r) => r.status == s).length;

  String _iso(DateTime d) =>
      '${d.year.toString().padLeft(4, '0')}-${d.month.toString().padLeft(2, '0')}-${d.day.toString().padLeft(2, '0')}';

  /// Every flat of the society with the amount and date left blank, to fill in.
  Future<void> _template() async {
    setState(() => _busy = true);
    try {
      final flats = await ref.read(flatsBySocietyProvider.future);
      final csv = const ListToCsvConverter().convert([
        _header,
        if (flats.isEmpty)
          ['Wing A', '101', '12000', '01/04/2026', 'NEFT', 'UTR123456', 'HDFC Bank', '']
        else
          for (final f in flats) [f.wingName ?? '', f.flatNumber, '', '', '', '', '', ''],
      ]);
      if (await saveCsvFile(csv, 'advance_maintenance_template.csv') && mounted) {
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
        setState(() => _fileError = 'No rows with an amount found in that file.');
        return;
      }
      final sendable = rows.where((r) => r.payload != null).toList();
      final outcomes = sendable.isEmpty ? <Map<String, dynamic>>[] : await _send(sendable, dryRun: true);
      setState(() => _rows = _merge(rows, outcomes, recorded: false));
    } catch (e) {
      setState(() => _fileError = 'Could not read that file: ${friendlyErrorMessage(e)}');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<List<Map<String, dynamic>>> _send(List<_Row> rows, {required bool dryRun}) async {
    final r = await ApiClient.instance
        .post('/billing/advance-import', data: {'rows': [for (final x in rows) x.payload!], 'dry_run': dryRun});
    return [for (final o in r.data as List) o as Map<String, dynamic>];
  }

  List<_Row> _merge(List<_Row> rows, List<Map<String, dynamic>> outcomes, {required bool recorded}) {
    final byLine = {for (final o in outcomes) o['line']: o};
    return [
      for (final r in rows)
        if (r.payload == null || (recorded && r.status != _Status.ready))
          r
        else
          switch (byLine[r.line]) {
            final o? when o['status'] == 'error' => r.with_(_Status.error, o['message'] as String?),
            final o? when o['status'] == 'recorded' => r.with_(_Status.recorded, 'Receipt ${o['receipt_number']}'),
            final o? when o['status'] == 'ready' => r.with_(_Status.ready),
            _ => r.with_(_Status.error, 'Not imported'),
          },
    ];
  }

  List<_Row> _parse(String csv) {
    final table = readCsvRows(csv).where((r) => r.any((c) => c.toString().trim().isNotEmpty)).toList();
    if (table.isEmpty) return [];
    final head = table.first.map((c) => _norm(c.toString())).toList();
    final index = <String, int>{};
    for (final k in _keys) {
      final i = head.indexWhere((h) => _aliases[k]!.map(_norm).contains(h));
      if (i >= 0) index[k] = i;
    }
    final hasHeader = index.containsKey('flat') && index.containsKey('amount');
    if (!hasHeader) {
      for (var i = 0; i < _keys.length; i++) {
        index[_keys[i]] = i;
      }
    }
    String at(List<String> raw, String k) {
      final i = index[k];
      return i == null || i >= raw.length ? '' : raw[i];
    }

    final out = <_Row>[];
    for (var i = hasHeader ? 1 : 0; i < table.length; i++) {
      final raw = table[i].map((c) => c.toString().trim()).toList();
      final cells = [for (final k in _keys) at(raw, k)];
      // The template lists every flat; the ones with no amount are not receiving an advance.
      if (cells[2].isEmpty && cells[3].isEmpty && cells[4].isEmpty) continue;
      final line = i + 1;
      String? error;
      String? iso;
      if (cells[1].isEmpty) {
        error = 'Flat number is required';
      } else if (cells[2].isEmpty) {
        error = 'Amount is empty';
      } else if (cells[3].isEmpty) {
        error = 'Payment Date is empty';
      } else {
        final d = parseImportDate(cells[3]);
        if (d == null) {
          error = 'Payment Date "${cells[3]}" is not a date (use dd/mm/yyyy)';
        } else {
          iso = _iso(d);
        }
      }
      out.add(error != null
          ? _Row(line, cells, null, _Status.error, error)
          : _Row(line, cells, {
              'line': line,
              'wing': cells[0],
              'flat_number': cells[1],
              'amount': cells[2],
              'payment_date': iso,
              'payment_mode': cells[4],
              'transaction_ref': cells[5],
              'bank_name': cells[6],
              'notes': cells[7],
            }, _Status.ready));
    }
    return out;
  }

  Future<void> _import() async {
    setState(() => _busy = true);
    final rows = _rows!;
    try {
      final outcomes = await _send(rows.where((r) => r.status == _Status.ready).toList(), dryRun: false);
      setState(() {
        _rows = _merge(rows, outcomes, recorded: true);
        _done = true;
      });
      final societyId = ref.read(currentUserProvider)?.societyId;
      if (societyId != null) ref.invalidate(onlinePaymentsProvider(societyId));
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
      for (final r in bad) [...r.cells, r.message ?? 'Not imported'],
    ]);
    if (await saveCsvFile(csv, 'advance_maintenance_errors.csv') && mounted) AppToast.success(context, 'Error rows downloaded');
  }

  @override
  Widget build(BuildContext context) => AppPage(
        title: 'Import Advance Maintenance',
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
            '1. Download the sheet: it lists every flat. Fill in Amount, Payment Date (dd/mm/yyyy) and Payment Mode '
            '(cash, cheque, UPI, NEFT, RTGS or bank transfer) for the flats that paid in advance, with the cheque / '
            'UTR number if any. Flats with nothing filled in are skipped. Save the file as CSV.\n'
            '2. Choose the CSV here. Each payment gets a receipt and is kept as that flat\'s advance in the '
            '"Advance Maintenance from Members" ledger (a liability).\n'
            '3. When bills are raised, each flat\'s advance is set off against its bills, oldest first, and what is '
            'left stays as its balance. Importing the same file twice is refused row by row. Each row is checked '
            'first and nothing is saved until you press Import.',
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
    final recorded = _count(_Status.recorded);
    return Column(children: [
      Padding(
        padding: const EdgeInsets.fromLTRB(20, 16, 20, 8),
        child: Row(children: [
          Expanded(
            child: Text(
              _done
                  ? '$recorded recorded${errors > 0 ? ', $errors not imported' : ''}'
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
                  label: _busy ? 'Importing…' : 'Record $ready Advance${ready == 1 ? '' : 's'}',
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
      _Status.recorded => (AppTheme.success, Icons.check_circle_rounded),
    };
    final name = [row.wing, row.flat].where((s) => s.isNotEmpty).join(' - ');
    final meta = [row.cells[3], row.cells[4], row.cells[5]].where((s) => s.isNotEmpty).join(' · ');
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(color: AppTheme.cardBg, borderRadius: BorderRadius.circular(AppTheme.radiusS), border: Border.all(color: AppTheme.border)),
      child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Icon(icon, color: color, size: 18),
        const SizedBox(width: 10),
        Expanded(
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text('Row ${row.line}: ${name.isEmpty ? '(no flat)' : 'Flat $name'}${row.amount.isEmpty ? '' : ' — ₹${row.amount}'}',
                style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600)),
            if (meta.isNotEmpty) Text(meta, style: const TextStyle(fontSize: 11, color: AppTheme.textSecondary)),
            if (row.message != null) Text(row.message!, style: TextStyle(fontSize: 11, color: color)),
          ]),
        ),
      ]),
    );
  }
}
