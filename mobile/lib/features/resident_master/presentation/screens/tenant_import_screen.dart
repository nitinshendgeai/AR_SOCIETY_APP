import 'dart:convert';

import 'package:csv/csv.dart';
import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/resident_master/data/agreement_channel.dart';
import 'package:ar_society_app/features/resident_master/data/import_columns.dart' show parseImportDate;
import 'package:ar_society_app/features/resident_master/data/tenant_import_api.dart';
import 'package:ar_society_app/features/resident_master/data/tenant_import_columns.dart';
import 'package:ar_society_app/features/resident_master/presentation/providers/resident_master_providers.dart';
import 'package:ar_society_app/shared/utils/csv_file.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';
import 'package:ar_society_app/shared/widgets/app_form.dart';

final tenantImportApiProvider = Provider<TenantImportApi>((_) => TenantImportApi());

enum _Status { ready, error, skipped, created }

class _Row {
  final int line;
  final List<String> canonical; // template order, for the preview and the error file
  final Map<String, dynamic>? payload; // what is sent (null: failed on this device, never sent)
  final _Status status;
  final String? message;
  const _Row(this.line, this.canonical, this.payload, this.status, [this.message]);

  String get flat => [canonical[0], canonical[1]].where((s) => s.isNotEmpty).join(' ');
  String get name => canonical[2];
  _Row with_(_Status s, [String? m]) => _Row(line, canonical, payload, s, m);
}

/// Bring in the society's tenants from a CSV: one row per let-out flat, with the agreement, the rent and the channel
/// the agreement came through (direct, agent, online app). Columns are found by their headings, so the society's own
/// sheet works. Every row is checked by the server first (nothing is saved), then the good rows go in through the same
/// code as the Add Tenant form; a tenant already in the flat is skipped, so a corrected file can be imported again.
class TenantImportScreen extends ConsumerStatefulWidget {
  const TenantImportScreen({super.key});

  @override
  ConsumerState<TenantImportScreen> createState() => _TenantImportScreenState();
}

class _TenantImportScreenState extends ConsumerState<TenantImportScreen> {
  List<_Row>? _rows;
  String? _fileError;
  bool _busy = false;
  bool _done = false;

  int _count(_Status s) => (_rows ?? []).where((r) => r.status == s).length;
  bool get _hasGoodRows => _count(_Status.ready) > 0;

  static const _dateFields = ['agreement_start_date', 'agreement_end_date', 'move_in_date'];
  static const _dateLabels = {
    'agreement_start_date': 'Agreement Start',
    'agreement_end_date': 'Agreement End',
    'move_in_date': 'Move-in Date',
  };

  Future<void> _template() async {
    final csv = const ListToCsvConverter().convert([
      tenantImportTemplateHeader,
      ['A', '101', 'Meena Shah', '9876543210', 'meena@example.com', '01/04/2026', '28/02/2027', '25000', '75000',
        '01/04/2026', 'Agent', 'Ramesh Estates', 'Aadhaar', '', ''],
      ['A', '102', 'Karan Joshi', '9876500000', '', '01/06/2026', '30/04/2027', '30000', '90000', '', 'Direct', '', '', '',
        ''],
      ['B', '201', 'Priya Nair', '', '', '15/05/2026', '14/04/2027', '22000', '66000', '', 'Online App', 'NoBroker', '', '',
        ''],
    ]);
    if (await saveCsvFile(csv, 'tenants_import_template.csv') && mounted) {
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
      // The server checks every row (unknown flats, a tenant already there, bad dates and amounts) and writes nothing.
      final sendable = rows.where((r) => r.payload != null).toList();
      final outcomes = sendable.isEmpty
          ? <TenantImportOutcome>[]
          : await ref.read(tenantImportApiProvider).importRows([for (final r in sendable) r.payload!], dryRun: true);
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
    final header = TenantImportColumns.fromHeader(table.first.map((c) => c.toString().trim()).toList());
    final columns = header ?? TenantImportColumns.positional();
    final out = <_Row>[];
    for (var i = header != null ? 1 : 0; i < table.length; i++) {
      final raw = table[i].map((c) => c.toString().trim()).toList();
      final fields = Map<String, dynamic>.from(columns.fields(raw));
      final canon = columns.canonical(raw);
      final line = i + 1;

      String? error;
      for (final key in _dateFields) {
        final text = (fields[key] as String?) ?? '';
        if (text.isEmpty) {
          fields[key] = null;
          continue;
        }
        final d = parseImportDate(text);
        if (d == null) {
          error = '${_dateLabels[key]} "$text" is not a date (use dd/mm/yyyy)';
          break;
        }
        fields[key] = '${d.year.toString().padLeft(4, '0')}-${d.month.toString().padLeft(2, '0')}-'
            '${d.day.toString().padLeft(2, '0')}';
      }
      if (error == null && ((fields['flat_number'] as String?) ?? '').isEmpty) error = 'Flat number is required';
      if (error == null && ((fields['full_name'] as String?) ?? '').isEmpty) error = 'Tenant name is required';

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
      final outcomes =
          await ref.read(tenantImportApiProvider).importRows([for (final r in sendable) r.payload!], dryRun: false);
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
      ref.read(tenantListProvider.notifier).refresh();
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
      [...tenantImportTemplateHeader, 'Error'],
      for (final r in bad) [...r.canonical, r.message ?? 'Not imported'],
    ]);
    if (await saveCsvFile(csv, 'tenants_import_errors.csv') && mounted) {
      AppToast.success(context, 'Error rows downloaded');
    }
  }

  @override
  Widget build(BuildContext context) {
    return AppPage(
      title: 'Import Tenants',
      body: ResponsiveBody(child: _rows == null ? _intro() : _preview()),
    );
  }

  Widget _intro() => ListView(padding: const EdgeInsets.all(20), children: [
        Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: AppTheme.primary.withOpacity(0.06),
            borderRadius: BorderRadius.circular(AppTheme.radiusM),
            border: Border.all(color: AppTheme.primary.withOpacity(0.15)),
          ),
          child: const Text(
            '1. Download the template and fill it in (Excel, Google Sheets…), or use your own sheet: columns are found by '
            'their headings (Wing, Flat No, Tenant Name, Rent, Deposit, Agreement Start…), in any order.\n'
            '2. One row per let-out flat. Wing and Flat No must match a flat already in the society; only Flat No and '
            'Tenant Name are required. Dates are read day first (01/04/2026). If there is no Move-in Date, the agreement '
            'start is used, and the flat is marked as let out from then.\n'
            '3. Channel says how the agreement came: Direct, Agent, Online App or Other. Put the agent\'s or the app\'s '
            'name in Agent / App Name.\n'
            '4. A flat that already has the same tenant is skipped, so you can import a corrected file again. Each row is '
            'checked first and nothing is saved until you press Import.',
            style: TextStyle(fontSize: 13, height: 1.5),
          ),
        ),
        const SizedBox(height: 24),
        SizedBox(
          height: 52,
          child: OutlinedButton.icon(
              onPressed: _template, icon: const Icon(Icons.download_rounded), label: const Text('Download Template')),
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
    return Column(children: [
      Padding(
        padding: const EdgeInsets.fromLTRB(20, 16, 20, 8),
        child: Row(children: [
          Expanded(
            child: Text(
              _done
                  ? '$created added${skipped > 0 ? ', $skipped already there' : ''}${errors > 0 ? ', $errors not imported' : ''}'
                  : '$ready ready${skipped > 0 ? ', $skipped already there' : ''}${errors > 0 ? ', $errors need fixing' : ''}',
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
                  label: _busy ? 'Importing…' : 'Import $ready Tenant${ready == 1 ? '' : 's'}',
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
      _Status.skipped => (AppTheme.primary, Icons.skip_next_rounded),
      _Status.created => (AppTheme.success, Icons.check_circle_rounded),
    };
    final channel = agreementChannelLabel(_channelValue(row.canonical[10]));
    final meta = [
      if (row.canonical[7].isNotEmpty) 'Rent ${row.canonical[7]}',
      if (row.canonical[5].isNotEmpty) 'from ${row.canonical[5]}',
      if (channel.isNotEmpty) channel,
      if (row.canonical[11].isNotEmpty) row.canonical[11],
    ].join(' · ');
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
          color: AppTheme.cardBg, borderRadius: BorderRadius.circular(AppTheme.radiusS), border: Border.all(color: AppTheme.border)),
      child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Icon(icon, color: color, size: 18),
        const SizedBox(width: 10),
        Expanded(
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(
                'Row ${row.line}: ${row.flat.isEmpty ? '(no flat)' : 'Flat ${row.flat}'}'
                '${row.name.isEmpty ? '' : ' — ${row.name}'}',
                style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600)),
            if (meta.isNotEmpty) Text(meta, style: const TextStyle(fontSize: 11, color: AppTheme.textSecondary)),
            if (row.message != null) Text(row.message!, style: TextStyle(fontSize: 11, color: color)),
          ]),
        ),
      ]),
    );
  }

  /// The label for what the file says, when it is one of the known channels (the server reads the rest).
  static String? _channelValue(String text) {
    final t = text.trim().toLowerCase().replaceAll(RegExp(r'[^a-z ]'), ' ');
    if (t.isEmpty) return null;
    if (t.contains('direct')) return 'direct';
    if (t.contains('agent') || t.contains('broker')) return 'agent';
    if (t.contains('online') || t.contains('app') || t.contains('portal')) return 'online_app';
    return 'other';
  }
}
