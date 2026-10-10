import 'dart:convert';

import 'package:csv/csv.dart';
import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/resident_master/data/import_columns.dart';
import 'package:ar_society_app/features/resident_master/data/models/resident_master_models.dart';
import 'package:ar_society_app/features/resident_master/data/repositories/resident_master_repository.dart';
import 'package:ar_society_app/features/resident_master/presentation/providers/resident_master_providers.dart';
import 'package:ar_society_app/features/resident_master/presentation/widgets/resident_master_widgets.dart';
import 'package:ar_society_app/features/society_settings/presentation/providers/society_settings_providers.dart';
import 'package:ar_society_app/features/society_structure/data/models/structure_models.dart';
import 'package:ar_society_app/features/society_structure/presentation/providers/structure_providers.dart';
import 'package:ar_society_app/shared/utils/csv_file.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';

const _templateHeader = importTemplateHeader;

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
  bool _pickingFile = false;

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
                '2. Floor, Flat Type (1 BHK, 2 BHK…), Area (sq ft), Possession or Purchase Date, Electric Meter No and Consumer No are optional. If a Wing, Floor, or Flat Number doesn\'t exist yet, it will be created automatically during import\n'
                '3. Your own sheet works too: columns are found by their headings (Wing, Flat No, Name, Flat Type, Area, Possession Date or Purchase Date, Meter No…), in any order. Dates are read day first (01/04/2019). An area in square metres ("60 sq m") is converted to square feet\n'
                '4. Type, area, date and meter details are saved on the flat (and used in billing). Choose the filled file, review the preview, then import',
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

  /// Saves a CSV the user keeps — a browser download on the web, the system
  /// "Save as" dialog on the phone (no temp files, which the web can't write).
  Future<void> _saveCsv(String csv, String fileName, String what) async {
    if (await saveCsvFile(csv, fileName) && mounted) {
      AppToast.success(context, '$what downloaded as $fileName');
    }
  }

  Future<void> _downloadTemplate() async {
    try {
      final rows = [
        _templateHeader,
        ['A Wing', '101', 'Ramesh Kumar', 'owner', 'yes', '9876543210', 'ramesh@example.com', '1', '01/04/2019', 'MTR-001234', '170012345678', '2 BHK', '650'],
      ];
      final csvString = const ListToCsvConverter().convert(rows);
      await _saveCsv(csvString, 'resident_import_template.csv', 'Template');
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(
          content: Text('Could not create template: $e'),
          backgroundColor: AppTheme.error,
        ));
      }
    }
  }

  /// Exports every row that didn't make it in — whether it failed
  /// validation up front (_RowStatus.error) or was sent but rejected by the
  /// backend (_RowStatus.failed) — as a CSV in the same column layout as
  /// the template, plus a trailing Error column explaining what to fix.
  /// The user corrects just those rows and re-imports that smaller file.
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
      await _saveCsv(csvString, 'resident_import_errors.csv', 'Error rows');
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
      // Read the contents on every platform: on the web a picked file has
      // no path (file_picker throws if `path` is even read).
      withData: true,
    );
    final picked = result?.files.single;
    if (picked == null) return;

    setState(() => _pickingFile = true);
    try {
      final bytes = picked.bytes;
      if (bytes == null) throw 'the file could not be read';
      final content = _decodeCsvBytes(bytes);

      // Await the wing/flat reference data rather than reading whatever
      // snapshot happens to be cached — a plain ref.read() here could race
      // an in-flight (or not-yet-started) fetch and see an empty list,
      // failing every row with a false "wing doesn't exist" error.
      final wings = await ref.read(wingsProvider.future);
      final flats = await ref.read(flatsBySocietyProvider.future);

      final rows = _parseAndValidate(content, wings, flats);
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
    List<WingModel> wings,
    List<FlatModel> flats,
  ) {
    final table = readCsvRows(csvString)
        .where((r) => r.any((c) => c.toString().trim().isNotEmpty))
        .toList();
    if (table.isEmpty) return [];

    // A header row says which column is which (any order, the names people use); without one the template's
    // own order is used. Either way the header isn't a resident.
    final headerColumns = ImportColumns.fromHeader(table.first.map((c) => c.toString().trim()).toList());
    final columns = headerColumns ?? ImportColumns.positional();
    final startIndex = headerColumns != null ? 1 : 0;

    final result = <_ImportRow>[];
    for (var i = startIndex; i < table.length; i++) {
      final fileRow = table[i].map((c) => c.toString().trim()).toList();
      final raw = columns.canonical(fileRow);           // in template order, for the preview and the error file
      final lineNumber = i + 1;

      String cell(String key) => columns.cell(fileRow, key);

      final wingText = cell('wing');
      final flatText = cell('flat');
      final fullName = cell('name');
      final typeText = cell('type');
      final primaryText = cell('primary');
      final phone = cell('phone');
      final email = cell('email');
      final floorText = cell('floor');
      final dateCell = columns.dateOf(fileRow);
      final possessionText = dateCell.text;
      final bhkText = cell('bhk');
      final areaText = cell('area');
      final meterText = cell('meter');
      final consumerText = cell('consumer');

      String? error;

      if (fullName.isEmpty) error = 'Full Name is required';
      if (error == null && wingText.isEmpty) error = 'Wing is required';
      if (error == null && flatText.isEmpty) error = 'Flat Number is required';

      int? floorNumber;
      if (error == null && floorText.isNotEmpty) {
        floorNumber = int.tryParse(floorText);
        if (floorNumber == null) error = 'Floor must be a whole number';
      }

      DateTime? possession;
      if (error == null && possessionText.isNotEmpty) {
        possession = parseImportDate(possessionText);
        if (possession == null) {
          error = '${dateCell.heading} "$possessionText" is not a date (use dd/mm/yyyy)';
        } else if (possession.isAfter(DateTime.now().add(const Duration(days: 366))) ||
            possession.isBefore(DateTime(1950))) {
          error = '${dateCell.heading} must be between 1950 and a year from today';
        }
      }

      final flatType = parseFlatType(bhkText);
      if (error == null) error = flatType.error;
      final area = parseAreaSqft(areaText);
      if (error == null) error = area.error;

      // Wing/Floor/Flat need not already exist — a row referencing a Wing,
      // Floor, or Flat that isn't in the society yet is still importable;
      // _runImport() creates whichever is missing (checking first, so a
      // name/number shared by an earlier row in the same file is reused,
      // not duplicated) before creating the Resident under it.
      WingModel? wing;
      if (error == null) {
        wing = wings.cast<WingModel?>().firstWhere(
            (w) => w!.name.trim().toLowerCase() == wingText.toLowerCase(),
            orElse: () => null);
      }

      FlatModel? flat;
      if (error == null && wing != null) {
        flat = flats.cast<FlatModel?>().firstWhere(
            (f) =>
                f!.wingId == wing!.id &&
                f.flatNumber.trim().toLowerCase() == flatText.toLowerCase(),
            orElse: () => null);
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

      String? note;
      if (wing == null) {
        note = 'Will create new Wing "$wingText"'
            '${floorNumber != null ? ', Floor $floorNumber,' : ''}'
            ' and Flat "$flatText"';
      } else if (flat == null) {
        note = 'Will create new Flat "$flatText" in Wing "$wingText"'
            '${floorNumber != null ? ' (Floor $floorNumber)' : ''}';
      } else if (floorNumber != null) {
        note = 'Will ensure Floor $floorNumber exists in Wing "$wingText"';
      }
      final flatNotes = [
        if (possession != null) 'possession ${possession.day}/${possession.month}/${possession.year}',
        if (flatType.value != null) 'type ${flatType.value}',
        if (area.sqft != null) 'area ${area.sqft!.toStringAsFixed(area.sqft! == area.sqft!.roundToDouble() ? 0 : 2)} sq ft',
        if (meterText.isNotEmpty) 'meter $meterText',
        if (consumerText.isNotEmpty) 'consumer no. $consumerText',
      ];
      if (flatNotes.isNotEmpty) {
        note = [if (note != null) note, 'Will set ${flatNotes.join(', ')} on the flat'].join(' · ');
      }
      if (flatType.note != null) note = [if (note != null) note, flatType.note!].join(' · ');

      result.add(_ImportRow(
        lineNumber: lineNumber,
        raw: raw,
        status: _RowStatus.valid,
        message: note,
        payload: {
          'wing_id': wing?.id,
          'wing_name': wingText,
          'floor_number': floorNumber,
          'flat_id': flat?.id,
          'flat_number': flatText,
          'full_name': fullName,
          'resident_type': residentType.value,
          'is_primary': isPrimary,
          if (phone.isNotEmpty) 'phone': phone,
          if (email.isNotEmpty) 'email': email,
          // Kept on the flat, not the resident (taken out before the resident is created)
          if (possession != null) 'possession_date': _iso(possession),
          if (flatType.value != null) 'flat_type': flatType.value,
          if (area.sqft != null) 'area_sqft': area.sqft,
          if (meterText.isNotEmpty) 'electric_meter_no': meterText,
          if (consumerText.isNotEmpty) 'electric_consumer_no': consumerText,
        },
      ));
    }
    return result;
  }

  static String _iso(DateTime d) =>
      '${d.year.toString().padLeft(4, '0')}-${d.month.toString().padLeft(2, '0')}-${d.day.toString().padLeft(2, '0')}';

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
          // backend (e.g. a duplicate) are never silently dropped — the
          // user can pull them back out as a CSV, fix just those, and
          // re-import that smaller file rather than redoing the whole batch.
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
                      : 'Import $validCount Resident${validCount == 1 ? '' : 's'}',
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
    final repo = ref.read(residentMasterRepositoryProvider);
    final rows = _rows!;

    // Seeded from what's already loaded, then grown in-memory as rows create
    // new Wings/Floors/Flats — so two rows naming the same not-yet-existing
    // Wing, Floor, or Flat share the one record created for the first of
    // them rather than each creating (and colliding on) their own.
    final wingsByName = <String, WingModel>{
      for (final w in ref.read(wingsProvider).valueOrNull ?? const <WingModel>[])
        w.name.trim().toLowerCase(): w,
    };
    final flatsByKey = <String, FlatModel>{
      for (final f in ref.read(flatsBySocietyProvider).valueOrNull ?? const <FlatModel>[])
        '${f.wingId}|${f.flatNumber.trim().toLowerCase()}': f,
    };
    final floorsByWing = <String, Map<int, FloorModel>>{};
    final appliedByFlat = <String, Map<String, dynamic>>{};
    String? societyId;

    Future<Map<int, FloorModel>> floorsFor(String wingId) async {
      final cached = floorsByWing[wingId];
      if (cached != null) return cached;
      final floors = await ref.read(floorsByWingProvider(wingId).future);
      return floorsByWing[wingId] = {for (final f in floors) f.floorNumber: f};
    }

    for (var i = 0; i < rows.length; i++) {
      if (rows[i].status != _RowStatus.valid) continue;
      setState(() => rows[i] =
          rows[i].copyWith(status: _RowStatus.pending, clearMessage: true));

      final payload = Map<String, dynamic>.from(rows[i].payload!);
      final wingName = payload.remove('wing_name') as String;
      final floorNumber = payload.remove('floor_number') as int?;
      final flatNumber = payload.remove('flat_number') as String;
      var wingId = payload.remove('wing_id') as String?;
      var flatId = payload.remove('flat_id') as String?;
      final flatFields = <String, dynamic>{
        for (final k in const ['possession_date', 'electric_meter_no', 'electric_consumer_no', 'flat_type', 'area_sqft'])
          if (payload.containsKey(k)) k: payload.remove(k),
      };

      try {
        if (wingId == null) {
          final key = wingName.trim().toLowerCase();
          final wing = wingsByName[key] ??
              await ref.read(wingsProvider.notifier).create(name: wingName);
          wingsByName[key] = wing;
          wingId = wing.id;
        }

        if (floorNumber != null) {
          final floors = await floorsFor(wingId);
          if (!floors.containsKey(floorNumber)) {
            societyId ??= (await ref.read(currentSocietyProvider.future)).id;
            floors[floorNumber] = await ref
                .read(floorsByWingProvider(wingId).notifier)
                .create(floorNumber: floorNumber, societyId: societyId);
          }
        }

        if (flatId == null) {
          final flatKey = '$wingId|${flatNumber.trim().toLowerCase()}';
          final flat = flatsByKey[flatKey] ??
              await ref.read(flatsBySocietyProvider.notifier).create(
                    flatNumber: flatNumber,
                    wingId: wingId,
                    floor: floorNumber,
                  );
          flatsByKey[flatKey] = flat;
          flatId = flat.id;
        }

        // The flat's own details from the file: only what the file gives, and only once per flat per value
        // (a family of four rows for one flat patches it once).
        if (flatFields.isNotEmpty) {
          final applied = appliedByFlat.putIfAbsent(flatId, () => <String, dynamic>{});
          final changed = {
            for (final e in flatFields.entries)
              if (applied[e.key] != e.value) e.key: e.value,
          };
          if (changed.isNotEmpty) {
            await ref.read(flatsBySocietyProvider.notifier).updateFlat(flatId, changed);
            applied.addAll(changed);
          }
        }
      } catch (e) {
        setState(() => rows[i] = rows[i].copyWith(
              status: _RowStatus.failed,
              clearMessage: true,
              message: 'Could not create or update the Wing/Floor/Flat: ${friendlyErrorMessage(e)}',
            ));
        continue;
      }

      payload['flat_id'] = flatId;
      final result = await repo.createResident(payload);
      switch (result) {
        case RmSuccess(:final data):
          setState(() => rows[i] = rows[i].copyWith(
                status: _RowStatus.created,
                clearMessage: true,
                message: data.warnings.isNotEmpty ? data.warnings.first : null,
              ));
        case RmFailure(:final message):
          setState(() => rows[i] = rows[i]
              .copyWith(status: _RowStatus.failed, clearMessage: true, message: message));
      }
    }

    ref.invalidate(residentListProvider);
    ref.invalidate(wingsProvider);
    ref.invalidate(flatsBySocietyProvider);
    for (final wingId in floorsByWing.keys) {
      ref.invalidate(floorsByWingProvider(wingId));
    }
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
