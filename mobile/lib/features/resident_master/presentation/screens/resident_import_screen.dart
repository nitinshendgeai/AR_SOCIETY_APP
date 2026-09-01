import 'dart:convert';
import 'dart:io';

import 'package:csv/csv.dart';
import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:path_provider/path_provider.dart';
import 'package:share_plus/share_plus.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/resident_master/data/models/resident_master_models.dart';
import 'package:ar_society_app/features/resident_master/data/repositories/resident_master_repository.dart';
import 'package:ar_society_app/features/resident_master/presentation/providers/resident_master_providers.dart';
import 'package:ar_society_app/features/resident_master/presentation/widgets/resident_master_widgets.dart';
import 'package:ar_society_app/features/society_structure/data/models/structure_models.dart';
import 'package:ar_society_app/features/society_structure/presentation/providers/structure_providers.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';

const _templateHeader = [
  'Wing', 'Flat Number', 'Full Name', 'Resident Type', 'Is Primary', 'Phone', 'Email',
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

  _ImportRow copyWith({_RowStatus? status, String? message}) => _ImportRow(
        lineNumber: lineNumber,
        raw: raw,
        status: status ?? this.status,
        message: message ?? this.message,
        payload: payload,
      );
}

/// Bulk-imports Residents from a CSV file: pick a file, preview each row's
/// validity (resolved against the wings/flats that already exist), then
/// create the valid rows one at a time through the same createResident()
/// call the single Add Resident form uses — so every auto-provisioned login
/// (see backend's ResidentService.create()/user_provisioning.py), duplicate
/// warning, and validation rule behaves identically whether a resident was
/// added one at a time or via this screen.
class ResidentImportScreen extends ConsumerStatefulWidget {
  const ResidentImportScreen({super.key});

  @override
  ConsumerState<ResidentImportScreen> createState() => _ResidentImportScreenState();
}

class _ResidentImportScreenState extends ConsumerState<ResidentImportScreen> {
  List<_ImportRow>? _rows;
  String? _fileError;
  bool _importing = false;
  bool _done = false;

  bool get _hasValidRows => (_rows ?? []).any((r) => r.status == _RowStatus.valid);

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppTheme.surface,
      appBar: AppBar(title: const Text('Import Residents')),
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
                '2. Wing and Flat Number must exactly match wings/flats already added to this society\n'
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
        ['A Wing', '101', 'Ramesh Kumar', 'owner', 'yes', '9876543210', 'ramesh@example.com'],
      ];
      final csvString = const ListToCsvConverter().convert(rows);
      final dir = await getTemporaryDirectory();
      final file = File('${dir.path}/resident_import_template.csv');
      await file.writeAsBytes(utf8.encode(csvString));
      await Share.shareXFiles([XFile(file.path)],
          subject: 'Resident Import Template');
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(
          content: Text('Could not create template: $e'),
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

    try {
      final content = picked.path != null
          ? await File(picked.path!).readAsString()
          : utf8.decode(picked.bytes!);
      final rows = _parseAndValidate(content);
      if (rows.isEmpty) {
        setState(() => _fileError = 'No data rows found in that file.');
        return;
      }
      setState(() => _rows = rows);
    } catch (e) {
      setState(() => _fileError = 'Could not read that file: $e');
    }
  }

  // ── Parsing + validation ─────────────────────────────────────────────────

  List<_ImportRow> _parseAndValidate(String csvString) {
    final table = const CsvToListConverter(shouldParseNumbers: false)
        .convert(csvString)
        .where((r) => r.any((c) => c.toString().trim().isNotEmpty))
        .toList();
    if (table.isEmpty) return [];

    // Skip a header row if the first cell looks like the template's own
    // header rather than actual data (so re-importing a downloaded-then-
    // filled template doesn't try to create a resident named "Wing").
    final startIndex =
        table.first.isNotEmpty && table.first[0].toString().trim().toLowerCase() == 'wing'
            ? 1
            : 0;

    final wings = ref.read(wingsProvider).valueOrNull ?? const <WingModel>[];
    final flats = ref.read(flatsBySocietyProvider).valueOrNull ?? const <FlatModel>[];

    final result = <_ImportRow>[];
    for (var i = startIndex; i < table.length; i++) {
      final raw = table[i].map((c) => c.toString().trim()).toList();
      final lineNumber = i + 1;

      String cell(int idx) => idx < raw.length ? raw[idx] : '';

      final wingText = cell(0);
      final flatText = cell(1);
      final fullName = cell(2);
      final typeText = cell(3);
      final primaryText = cell(4);
      final phone = cell(5);
      final email = cell(6);

      String? error;

      if (fullName.isEmpty) error = 'Full Name is required';

      WingModel? wing;
      if (error == null) {
        if (wingText.isEmpty) {
          error = 'Wing is required';
        } else {
          wing = wings.cast<WingModel?>().firstWhere(
              (w) => w!.name.trim().toLowerCase() == wingText.toLowerCase(),
              orElse: () => null);
          if (wing == null) error = 'No wing named "$wingText" exists yet';
        }
      }

      FlatModel? flat;
      if (error == null && wing != null) {
        if (flatText.isEmpty) {
          error = 'Flat Number is required';
        } else {
          flat = flats.cast<FlatModel?>().firstWhere(
              (f) =>
                  f!.wingId == wing!.id &&
                  f.flatNumber.trim().toLowerCase() == flatText.toLowerCase(),
              orElse: () => null);
          if (flat == null) {
            error = 'No flat "$flatText" in wing "$wingText"';
          }
        }
      }

      ResidentType residentType = ResidentType.owner;
      if (error == null && typeText.isNotEmpty) {
        final normalized = typeText.toLowerCase().replaceAll('-', '_').replaceAll(' ', '_');
        final match = ResidentType.values
            .cast<ResidentType?>()
            .firstWhere((t) => t!.value == normalized, orElse: () => null);
        if (match == null) {
          error = 'Resident Type must be owner, co_owner, family, or dependent';
        } else {
          residentType = match;
        }
      }

      final isPrimary =
          ['yes', 'y', 'true', '1'].contains(primaryText.toLowerCase());
      if (error == null && isPrimary && !residentType.canBePrimary) {
        error = 'Only Owner or Co-Owner can be marked primary';
      }

      if (error == null && phone.isNotEmpty) {
        error = rmPhoneValidator(phone);
      }

      if (error != null) {
        result.add(_ImportRow(
            lineNumber: lineNumber, raw: raw, status: _RowStatus.error, message: error));
        continue;
      }

      result.add(_ImportRow(
        lineNumber: lineNumber,
        raw: raw,
        status: _RowStatus.valid,
        payload: {
          'flat_id': flat!.id,
          'full_name': fullName,
          'resident_type': residentType.value,
          'is_primary': isPrimary,
          if (phone.isNotEmpty) 'phone': phone,
          if (email.isNotEmpty) 'email': email,
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
        padding: const EdgeInsets.all(20),
        child: _done
            ? AppPrimaryButton(label: 'Done', onPressed: () => Navigator.pop(context, true))
            : AppPrimaryButton(
                label: _importing
                    ? 'Importing…'
                    : 'Import $validCount Resident${validCount == 1 ? '' : 's'}',
                icon: Icons.file_download_done_rounded,
                isLoading: _importing,
                onPressed: (_importing || !_hasValidRows) ? null : _runImport,
              ),
      ),
    ]);
  }

  Future<void> _runImport() async {
    setState(() => _importing = true);
    final repo = ref.read(residentMasterRepositoryProvider);
    final rows = _rows!;

    for (var i = 0; i < rows.length; i++) {
      if (rows[i].status != _RowStatus.valid) continue;
      setState(() => rows[i] = rows[i].copyWith(status: _RowStatus.pending));
      final result = await repo.createResident(rows[i].payload!);
      switch (result) {
        case RmSuccess(:final data):
          setState(() => rows[i] = rows[i].copyWith(
                status: _RowStatus.created,
                message: data.warnings.isNotEmpty ? data.warnings.first : null,
              ));
        case RmFailure(:final message):
          setState(() => rows[i] = rows[i].copyWith(status: _RowStatus.failed, message: message));
      }
    }

    ref.invalidate(residentListProvider);
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
    final name = row.raw.length > 2 && row.raw[2].isNotEmpty ? row.raw[2] : '(no name)';
    final location = [
      if (row.raw.isNotEmpty) row.raw[0],
      if (row.raw.length > 1) row.raw[1],
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
              if (location.isNotEmpty)
                Text(location,
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
