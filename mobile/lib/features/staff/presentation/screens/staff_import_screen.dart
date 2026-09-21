import 'dart:convert';
import 'dart:io';

import 'package:csv/csv.dart';
import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:path_provider/path_provider.dart';
import 'package:share_plus/share_plus.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/features/staff/data/repositories/staff_repository.dart';
import 'package:ar_society_app/features/staff/domain/entities/staff_entities.dart';
import 'package:ar_society_app/features/staff/presentation/providers/staff_providers.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';

const _templateHeader = [
  'Full Name', 'Mobile', 'Email', 'Department', 'Designation', 'Joining Date',
];

// (value, label) — same set StaffAddScreen offers in its Department dropdown.
const _departments = [
  ('security',     'Security'),
  ('housekeeping', 'Housekeeping'),
  ('technical',    'Technical'),
  ('gym',          'Gym'),
  ('maintenance',  'Maintenance'),
  ('electrical',   'Electrical'),
  ('plumbing',     'Plumbing'),
  ('gardening',    'Gardening'),
  ('amenities',    'Amenities'),
  ('admin',        'Administration'),
];

enum _RowStatus { valid, error, pending, created, failed }

class _ImportRow {
  final int lineNumber;
  final List<String> raw;
  final _RowStatus status;
  final String? message;
  final Map<String, dynamic>? payload;

  const _ImportRow({
    required this.lineNumber,
    required this.raw,
    required this.status,
    this.message,
    this.payload,
  });

  _ImportRow copyWith(
          {_RowStatus? status, String? message, bool clearMessage = false}) =>
      _ImportRow(
        lineNumber: lineNumber,
        raw: raw,
        status: status ?? this.status,
        message: clearMessage ? message : (message ?? this.message),
        payload: payload,
      );
}

/// Bulk-imports Staff from a CSV file: pick a file, preview each row's
/// validity (resolved against the designations that already exist), then
/// create the valid rows one at a time through the same createStaff() call
/// the single Add Staff form uses — so every auto-provisioned login (see
/// backend's StaffService.create_staff()) and validation rule behaves
/// identically whether a staff member was added one at a time or via this
/// screen. Mirrors ResidentImportScreen's auto-create-missing-lookup logic:
/// a row naming a Designation that doesn't exist yet for its Department
/// still imports — the Designation is created automatically.
class StaffImportScreen extends ConsumerStatefulWidget {
  const StaffImportScreen({super.key});

  @override
  ConsumerState<StaffImportScreen> createState() => _StaffImportScreenState();
}

class _StaffImportScreenState extends ConsumerState<StaffImportScreen> {
  List<_ImportRow>? _rows;
  String? _fileError;
  bool _importing = false;
  bool _done = false;
  bool _pickingFile = false;

  String get _societyId => ref.read(currentUserProvider)?.societyId ?? '';

  bool get _hasValidRows => (_rows ?? []).any((r) => r.status == _RowStatus.valid);

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppTheme.surface,
      appBar: AppBar(title: const Text('Import Staff')),
      body: ResponsiveBody(
        child: _rows == null ? _buildIntro(context) : _buildPreview(context),
      ),
    );
  }

  // ── Step 1: intro + template download + file pick ──────────────────────

  Widget _buildIntro(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.all(20),
      children: [
        Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: AppTheme.primary.withOpacity(0.06),
            borderRadius: BorderRadius.circular(12),
            border: Border.all(color: AppTheme.primary.withOpacity(0.15)),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(children: [
                Icon(Icons.info_outline_rounded, color: AppTheme.primary, size: 18),
                const SizedBox(width: 8),
                const Expanded(
                  child: Text('How this works',
                      style: TextStyle(fontWeight: FontWeight.w700, fontSize: 14)),
                ),
              ]),
              const SizedBox(height: 8),
              const Text(
                '1. Download the template and fill it in (in Excel, Google Sheets, etc.)\n'
                '2. Designation and Joining Date are optional. If a Designation doesn\'t '
                'exist yet, it will be created automatically during import\n'
                '3. Choose the filled file, review the preview, then import',
                style: TextStyle(fontSize: 13, color: AppTheme.textPrimary, height: 1.5),
              ),
            ],
          ),
        ),
        const SizedBox(height: 24),
        SizedBox(
          height: 52,
          child: OutlinedButton.icon(
            onPressed: _downloadTemplate,
            icon: const Icon(Icons.download_rounded),
            label: const Text('Download Template'),
          ),
        ),
        const SizedBox(height: 14),
        AppPrimaryButton(
          label: 'Choose CSV File',
          icon: Icons.upload_file_rounded,
          isLoading: _pickingFile,
          onPressed: _pickFile,
        ),
        if (_fileError != null) ...[
          const SizedBox(height: 16),
          AppErrorBanner(message: _fileError!),
        ],
      ],
    );
  }

  Future<void> _downloadTemplate() async {
    try {
      final rows = [
        _templateHeader,
        ['Ramesh Kumar', '9876543210', 'ramesh@example.com', 'Security', 'Security Guard', '2024-01-15'],
      ];
      final csvString = const ListToCsvConverter().convert(rows);
      final dir = await getTemporaryDirectory();
      final file = File('${dir.path}/staff_import_template.csv');
      await file.writeAsBytes(utf8.encode(csvString));
      await Share.shareXFiles([XFile(file.path)],
          subject: 'Staff Import Template');
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(
          content: Text('Could not create template: $e'),
          backgroundColor: AppTheme.error,
        ));
      }
    }
  }

  /// Exports every row that didn't make it in — whether it failed validation
  /// up front (_RowStatus.error) or was sent but rejected by the backend
  /// (_RowStatus.failed) — as a CSV in the same column layout as the
  /// template, plus a trailing Error column explaining what to fix. The
  /// user corrects just those rows and re-imports that smaller file.
  Future<void> _exportErrorRows() async {
    final badRows = (_rows ?? [])
        .where((r) => r.status == _RowStatus.error || r.status == _RowStatus.failed)
        .toList();
    if (badRows.isEmpty) return;

    List<String> paddedRaw(List<String> raw) {
      final padded = List<String>.from(raw);
      while (padded.length < _templateHeader.length) {
        padded.add('');
      }
      return padded.sublist(0, _templateHeader.length);
    }

    try {
      final csvRows = [
        [..._templateHeader, 'Error'],
        for (final r in badRows) [...paddedRaw(r.raw), r.message ?? 'Import failed'],
      ];
      final csvString = const ListToCsvConverter().convert(csvRows);
      final dir = await getTemporaryDirectory();
      final file = File('${dir.path}/staff_import_errors.csv');
      await file.writeAsBytes(utf8.encode(csvString));
      await Share.shareXFiles([XFile(file.path)],
          subject: 'Staff Import Errors');
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(
          content: Text('Could not export error rows: $e'),
          backgroundColor: AppTheme.error,
        ));
      }
    }
  }

  Future<void> _pickFile() async {
    setState(() => _fileError = null);
    final result = await FilePicker.platform.pickFiles(
      type: FileType.custom,
      allowedExtensions: ['csv'],
    );
    final picked = result?.files.single;
    if (picked == null) return;

    setState(() => _pickingFile = true);
    try {
      final bytes = picked.path != null
          ? await File(picked.path!).readAsBytes()
          : picked.bytes!;
      final content = _decodeCsvBytes(bytes);

      // Await the designation reference data rather than reading whatever
      // snapshot happens to be cached — a plain ref.read() here could race
      // an in-flight (or not-yet-started) fetch and see an empty list,
      // failing every row with a false "designation doesn't exist" note.
      final designations =
          await ref.read(designationsProvider(_societyId).future);

      final rows = _parseAndValidate(content, designations);
      if (rows.isEmpty) {
        setState(() => _fileError = 'No data rows found in that file.');
        return;
      }
      setState(() => _rows = rows);
    } catch (e) {
      setState(() => _fileError = 'Could not read that file: $e');
    } finally {
      if (mounted) setState(() => _pickingFile = false);
    }
  }

  /// Decodes CSV bytes as UTF-8 when possible, falling back to Latin-1
  /// when the file was saved with a non-UTF-8 encoding — Excel's default
  /// "CSV (Comma delimited)" export on Windows uses the system codepage
  /// rather than UTF-8, which otherwise throws on any non-ASCII byte
  /// (accented names, curly quotes, etc.). A leading UTF-8 byte-order mark,
  /// which Excel's "CSV UTF-8" export adds, is stripped either way so it
  /// doesn't get parsed as part of the header's first cell.
  String _decodeCsvBytes(List<int> bytes) {
    var b = bytes;
    if (b.length >= 3 && b[0] == 0xEF && b[1] == 0xBB && b[2] == 0xBF) {
      b = b.sublist(3);
    }
    try {
      return utf8.decode(b);
    } on FormatException {
      return latin1.decode(b);
    }
  }

  // ── Parsing + validation ─────────────────────────────────────────────────

  List<_ImportRow> _parseAndValidate(
    String csvString,
    List<DesignationEntity> designations,
  ) {
    final table = const CsvToListConverter(shouldParseNumbers: false)
        .convert(csvString)
        .where((r) => r.any((c) => c.toString().trim().isNotEmpty))
        .toList();
    if (table.isEmpty) return [];

    // Skip a header row if the first cell looks like the template's own
    // header rather than actual data (so re-importing a downloaded-then-
    // filled template doesn't try to create a staff member named "Full Name").
    final startIndex =
        table.first.isNotEmpty && table.first[0].toString().trim().toLowerCase() == 'full name'
            ? 1
            : 0;

    final result = <_ImportRow>[];
    for (var i = startIndex; i < table.length; i++) {
      final raw = table[i].map((c) => c.toString().trim()).toList();
      final lineNumber = i + 1;

      String cell(int idx) => idx < raw.length ? raw[idx] : '';

      final fullName        = cell(0);
      final mobile          = cell(1);
      final email           = cell(2);
      final deptText        = cell(3);
      final designationText = cell(4);
      final joiningText     = cell(5);

      String? error;

      if (fullName.isEmpty) error = 'Full Name is required';
      if (error == null && mobile.isEmpty) error = 'Mobile is required';
      if (error == null && mobile.isNotEmpty && mobile.length < 10) {
        error = 'Enter a valid mobile number';
      }
      if (error == null && deptText.isEmpty) error = 'Department is required';

      String? department;
      if (error == null) {
        final match = _departments.cast<(String, String)?>().firstWhere(
              (d) => d!.$1.toLowerCase() == deptText.toLowerCase() ||
                     d.$2.toLowerCase() == deptText.toLowerCase(),
              orElse: () => null,
            );
        if (match == null) {
          error = 'Department must be one of: '
              '${_departments.map((d) => d.$2).join(", ")}';
        } else {
          department = match.$1;
        }
      }

      String? joiningDate;
      if (error == null && joiningText.isNotEmpty) {
        if (RegExp(r'^\d{4}-\d{2}-\d{2}$').hasMatch(joiningText) &&
            DateTime.tryParse(joiningText) != null) {
          joiningDate = joiningText;
        } else {
          error = 'Joining Date must be in YYYY-MM-DD format';
        }
      }

      if (error != null) {
        result.add(_ImportRow(
            lineNumber: lineNumber, raw: raw, status: _RowStatus.error, message: error));
        continue;
      }

      // Designation need not already exist — a row referencing a Designation
      // that isn't set up for this Department yet is still importable;
      // _runImport() creates it (checking first, so a name shared by an
      // earlier row in the same file is reused, not duplicated) before
      // creating the Staff member under it.
      DesignationEntity? designation;
      if (designationText.isNotEmpty) {
        designation = designations.cast<DesignationEntity?>().firstWhere(
            (d) =>
                d!.department == department &&
                d.name.trim().toLowerCase() == designationText.toLowerCase(),
            orElse: () => null);
      }

      String? note;
      if (designationText.isNotEmpty && designation == null) {
        note = 'Will create new Designation "$designationText" under '
            '${_departments.firstWhere((d) => d.$1 == department).$2}';
      }

      result.add(_ImportRow(
        lineNumber: lineNumber,
        raw: raw,
        status: _RowStatus.valid,
        message: note,
        payload: {
          'full_name': fullName,
          'mobile': mobile,
          if (email.isNotEmpty) 'email': email,
          'department': department,
          'designation_id': designation?.id,
          'designation_name': designationText.isEmpty ? null : designationText,
          if (joiningDate != null) 'joining_date': joiningDate,
        },
      ));
    }
    return result;
  }

  // ── Step 2: preview + import ─────────────────────────────────────────────

  Widget _buildPreview(BuildContext context) {
    final rows = _rows!;
    final validCount = rows.where((r) => r.status == _RowStatus.valid).length;
    final errorCount = rows.where((r) => r.status == _RowStatus.error).length;
    final createdCount = rows.where((r) => r.status == _RowStatus.created).length;
    final failedCount = rows.where((r) => r.status == _RowStatus.failed).length;

    return Column(children: [
      Padding(
        padding: const EdgeInsets.fromLTRB(20, 16, 20, 8),
        child: Row(children: [
          Expanded(
            child: Text(
              _done
                  ? '$createdCount imported${failedCount > 0 ? ', $failedCount failed' : ''}'
                  : '$validCount ready to import'
                      '${errorCount > 0 ? ', $errorCount need fixing' : ''}',
              style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600),
            ),
          ),
          if (!_importing && !_done)
            TextButton(
              onPressed: () => setState(() { _rows = null; _fileError = null; }),
              child: const Text('Choose different file'),
            ),
        ]),
      ),
      Expanded(
        child: ListView.separated(
          padding: const EdgeInsets.symmetric(horizontal: 20),
          itemCount: rows.length,
          separatorBuilder: (_, __) => const SizedBox(height: 8),
          itemBuilder: (_, i) => _RowTile(row: rows[i]),
        ),
      ),
      Padding(
        padding: const EdgeInsets.fromLTRB(20, 12, 20, 20),
        child: Column(children: [
          // Rows that failed validation (never sent) or failed on the
          // backend (e.g. a duplicate employee code) are never silently
          // dropped — the user can pull them back out as a CSV, fix just
          // those, and re-import that smaller file rather than redoing the
          // whole batch.
          if (errorCount > 0 || failedCount > 0) ...[
            SizedBox(
              width: double.infinity,
              child: OutlinedButton.icon(
                onPressed: _exportErrorRows,
                icon: const Icon(Icons.download_rounded),
                label: Text(
                    'Export ${errorCount + failedCount} Error Row${errorCount + failedCount == 1 ? '' : 's'} to Fix'),
              ),
            ),
            const SizedBox(height: 12),
          ],
          _done
              ? AppPrimaryButton(label: 'Done', onPressed: () => Navigator.pop(context, true))
              : AppPrimaryButton(
                  label: _importing
                      ? 'Importing…'
                      : 'Import $validCount Staff Member${validCount == 1 ? '' : 's'}',
                  icon: Icons.file_download_done_rounded,
                  isLoading: _importing,
                  onPressed: (_importing || !_hasValidRows) ? null : _runImport,
                ),
        ]),
      ),
    ]);
  }

  Future<void> _runImport() async {
    setState(() => _importing = true);
    final repo = ref.read(staffRepositoryProvider);
    final rows = _rows!;

    // Seeded from what's already loaded, then grown in-memory as rows create
    // new Designations — so two rows naming the same not-yet-existing
    // Designation (within the same Department) share the one record created
    // for the first of them rather than each creating (and colliding on)
    // their own.
    final designationsByKey = <String, DesignationEntity>{
      for (final d
          in ref.read(designationsProvider(_societyId)).valueOrNull ??
              const <DesignationEntity>[])
        '${d.department}|${d.name.trim().toLowerCase()}': d,
    };

    for (var i = 0; i < rows.length; i++) {
      if (rows[i].status != _RowStatus.valid) continue;
      setState(() => rows[i] =
          rows[i].copyWith(status: _RowStatus.pending, clearMessage: true));

      final payload = Map<String, dynamic>.from(rows[i].payload!);
      final department = payload['department'] as String;
      final designationName = payload.remove('designation_name') as String?;
      var designationId = payload.remove('designation_id') as String?;

      if (designationId == null && designationName != null) {
        final key = '$department|${designationName.trim().toLowerCase()}';
        final cached = designationsByKey[key];
        if (cached != null) {
          designationId = cached.id;
        } else {
          final result = await repo.createDesignation(
            societyId: _societyId,
            name: designationName,
            department: department,
          );
          switch (result) {
            case StaffSuccess(:final data):
              designationsByKey[key] = data;
              designationId = data.id;
            case StaffFailure(:final message):
              setState(() => rows[i] = rows[i].copyWith(
                    status: _RowStatus.failed,
                    clearMessage: true,
                    message: 'Could not create Designation: $message',
                  ));
              continue;
          }
        }
      }

      payload['society_id'] = _societyId;
      if (designationId != null) payload['designation_id'] = designationId;

      final result = await repo.createStaff(payload);
      switch (result) {
        case StaffSuccess(:final data):
          setState(() => rows[i] = rows[i].copyWith(
                status: _RowStatus.created,
                clearMessage: true,
                message: data.tempPassword != null
                    ? 'Login created (password: ${data.tempPassword})'
                    : null,
              ));
        case StaffFailure(:final message):
          setState(() => rows[i] = rows[i]
              .copyWith(status: _RowStatus.failed, clearMessage: true, message: message));
      }
    }

    ref.invalidate(staffListProvider);
    ref.invalidate(designationsProvider(_societyId));
    setState(() { _importing = false; _done = true; });
  }
}

class _RowTile extends StatelessWidget {
  final _ImportRow row;
  const _RowTile({required this.row});

  @override
  Widget build(BuildContext context) {
    final (color, icon) = switch (row.status) {
      _RowStatus.valid => (AppTheme.textSecondary, Icons.radio_button_unchecked_rounded),
      _RowStatus.error => (AppTheme.error, Icons.error_outline_rounded),
      _RowStatus.pending => (AppTheme.warning, Icons.hourglass_top_rounded),
      _RowStatus.created => (AppTheme.success, Icons.check_circle_rounded),
      _RowStatus.failed => (AppTheme.error, Icons.cancel_rounded),
    };
    final name = row.raw.isNotEmpty && row.raw[0].isNotEmpty ? row.raw[0] : '(no name)';
    final subtitle = [
      if (row.raw.length > 1) row.raw[1],
      if (row.raw.length > 3) row.raw[3],
    ].where((s) => s.isNotEmpty).join(' — ');

    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: AppTheme.cardBg,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: AppTheme.border),
      ),
      child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Icon(icon, color: color, size: 18),
        const SizedBox(width: 10),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('Row ${row.lineNumber}: $name',
                  style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600)),
              if (subtitle.isNotEmpty)
                Text(subtitle,
                    style: const TextStyle(fontSize: 11, color: AppTheme.textSecondary)),
              if (row.message != null) ...[
                const SizedBox(height: 2),
                Text(row.message!, style: TextStyle(fontSize: 11, color: color)),
              ],
            ],
          ),
        ),
      ]),
    );
  }
}
