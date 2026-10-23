import 'dart:typed_data';

import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/assets/data/assets_api.dart';
import 'package:ar_society_app/features/assets/presentation/providers/assets_providers.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/shared/utils/file_saver.dart';
import 'package:ar_society_app/shared/widgets/app_form.dart' show AppPage;
import 'package:ar_society_app/shared/widgets/app_widgets.dart';

/// A file the person chose: its name and bytes.
typedef PickedFile = ({String name, Uint8List bytes});

Future<PickedFile?> _pickWithFilePicker() async {
  final result = await FilePicker.platform
      .pickFiles(type: FileType.custom, allowedExtensions: ['xlsx', 'csv'], withData: true);
  final file = result?.files.single;
  final bytes = file?.bytes;
  if (file == null || bytes == null) return null;
  return (name: file.name, bytes: bytes);
}

/// Bring in the society's asset register from an Excel (.xlsx) or CSV file. Every column of the file is read:
/// the ones that match an asset field (by their headings: Asset Name, Purchase Date, Cost…) are imported, the rest
/// are listed as not imported, and any column can be pointed at a different field. The server checks every row
/// first and saves nothing; only when the person presses Import are the good rows added. An asset whose code or
/// serial number is already registered is skipped, so the same file can be imported again safely.
class AssetsImportScreen extends ConsumerStatefulWidget {
  /// How a file is chosen; tests supply their own.
  final Future<PickedFile?> Function() pickFile;
  const AssetsImportScreen({super.key, this.pickFile = _pickWithFilePicker});

  @override
  ConsumerState<AssetsImportScreen> createState() => _AssetsImportScreenState();
}

class _AssetsImportScreenState extends ConsumerState<AssetsImportScreen> {
  PickedFile? _file;
  AssetImportResult? _result;
  Map<String, String?> _mapping = {};
  String? _error;
  bool _busy = false;
  bool _done = false;
  bool _problemsOnly = false;

  String? get _societyId => ref.read(currentUserProvider)?.societyId;

  Future<void> _template() async {
    try {
      final bytes = await ref.read(assetsApiProvider).importTemplate();
      if (await saveFileBytes(bytes, 'assets_import_template.csv', mimeType: 'text/csv') && mounted) {
        AppToast.success(context, 'Template downloaded');
      }
    } catch (e) {
      if (mounted) showErrorToast(context, e);
    }
  }

  Future<void> _choose() async {
    setState(() => _error = null);
    final picked = await widget.pickFile();
    if (picked == null) return;
    _file = picked;
    _mapping = {};
    await _preview();
  }

  /// Checks the file (nothing is saved). [mapping] is sent only after the person has changed a column.
  Future<void> _preview({bool sendMapping = false}) async {
    final societyId = _societyId, file = _file;
    if (societyId == null || file == null) return;
    setState(() => _busy = true);
    try {
      final result = await ref.read(assetsApiProvider).importFile(
            societyId, file.bytes, file.name,
            dryRun: true, mapping: sendMapping ? _mapping : null);
      setState(() {
        _result = result;
        _mapping = {for (final c in result.columns) c.heading: c.field};
      });
    } catch (e) {
      setState(() {
        _error = friendlyErrorMessage(e);
        if (!sendMapping) _result = null;
      });
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  void _pointColumn(String heading, String? field) {
    final next = {..._mapping};
    if (field != null) {
      // a field comes from one column: whichever column had it is let go
      for (final e in next.entries.toList()) {
        if (e.value == field) next[e.key] = null;
      }
    }
    next[heading] = field;
    setState(() => _mapping = next);
    _preview(sendMapping: true);
  }

  Future<void> _import() async {
    final societyId = _societyId, file = _file;
    if (societyId == null || file == null) return;
    setState(() => _busy = true);
    try {
      final result = await ref.read(assetsApiProvider).importFile(
            societyId, file.bytes, file.name, dryRun: false, mapping: _mapping);
      setState(() {
        _result = result;
        _done = true;
      });
      invalidateAssets(ref);
    } catch (e) {
      if (mounted) showErrorToast(context, e);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  void _reset() => setState(() {
        _file = null;
        _result = null;
        _mapping = {};
        _error = null;
        _done = false;
        _problemsOnly = false;
      });

  @override
  Widget build(BuildContext context) {
    ref.watch(currentUserProvider);
    final r = _result;
    return AppPage(
      title: 'Import Assets',
      body: ResponsiveBody(child: r == null ? _intro() : _review(r)),
      bottomNavigationBar: r == null ? null : _actionBar(r),
    );
  }

  Widget _actionBar(AssetImportResult r) => SafeArea(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(20, 8, 20, 12),
          child: _done
              ? AppPrimaryButton(label: 'Done', onPressed: () => Navigator.pop(context, true))
              : AppPrimaryButton(
                  key: const Key('assets-import-go'),
                  label: _busy ? 'Working…' : 'Import ${r.ready} Asset${r.ready == 1 ? '' : 's'}',
                  icon: Icons.file_download_done_rounded,
                  isLoading: _busy,
                  onPressed: (_busy || r.ready == 0 || r.message != null) ? null : _import,
                ),
        ),
      );

  Widget _intro() => ListView(padding: const EdgeInsets.all(20), children: [
        Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: AppTheme.primary.withOpacity(0.06),
            borderRadius: BorderRadius.circular(12),
            border: Border.all(color: AppTheme.primary.withOpacity(0.15)),
          ),
          child: const Text(
            '1. Use your own Excel or CSV register, or download the template and fill it in. Columns are found by their '
            'headings (Asset Name, Category, Location, Purchase Date, Cost, Serial No…), in any order, and a title '
            'above the headings is fine.\n'
            '2. Every column is read. The ones that match an asset field are imported; the rest are shown as not imported, '
            'and you can point any column at a different field.\n'
            '3. Only the name is needed. A blank Asset Code is numbered automatically. Dates are read day first '
            '(12/03/2021). An asset whose code or serial number is already registered is skipped, so importing the same '
            'file twice is safe.\n'
            '4. Every row is checked first and nothing is saved until you press Import.',
            style: TextStyle(fontSize: 13, height: 1.5),
          ),
        ),
        const SizedBox(height: 24),
        SizedBox(
          height: 52,
          child: OutlinedButton.icon(
            key: const Key('assets-import-template'),
            onPressed: _template,
            icon: const Icon(Icons.download_rounded),
            label: const Text('Download Template'),
          ),
        ),
        const SizedBox(height: 14),
        AppPrimaryButton(
          key: const Key('assets-import-choose'),
          label: 'Choose Excel or CSV File',
          icon: Icons.upload_file_rounded,
          isLoading: _busy,
          onPressed: _busy ? null : _choose,
        ),
        if (_error != null) ...[const SizedBox(height: 16), AppErrorBanner(message: _error!)],
      ]);

  Widget _review(AssetImportResult r) {
    final shown = _problemsOnly ? r.rows.where((x) => x.status != 'ready' && x.status != 'created').toList() : r.rows;
    final capped = shown.length > 300 ? shown.sublist(0, 300) : shown;
    final imported = r.columns.where((c) => c.field != null).length;
    return ListView(padding: const EdgeInsets.only(bottom: 16), children: [
      Padding(
        padding: const EdgeInsets.fromLTRB(20, 16, 20, 4),
        child: Row(children: [
          Expanded(
            child: Text(
              '${r.fileName}${r.sheet == 'CSV' ? '' : ' · ${r.sheet}'} · ${r.totalRows} row${r.totalRows == 1 ? '' : 's'}',
              style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600),
              overflow: TextOverflow.ellipsis,
            ),
          ),
          if (!_busy && !_done) TextButton(onPressed: _reset, child: const Text('Choose different file')),
        ]),
      ),
      if (_error != null) Padding(padding: const EdgeInsets.fromLTRB(20, 4, 20, 4), child: AppErrorBanner(message: _error!)),
      if (r.message != null) Padding(padding: const EdgeInsets.fromLTRB(20, 4, 20, 4), child: AppErrorBanner(message: r.message!)),
      if (!_done)
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 20),
          child: Card(
            margin: EdgeInsets.zero,
            child: ExpansionTile(
              key: const Key('assets-import-columns'),
              initiallyExpanded: r.message != null,
              title: Text('Columns: $imported of ${r.columns.length} will be imported',
                  style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600)),
              subtitle: const Text('Change what a column is read as, or choose Not imported.',
                  style: TextStyle(fontSize: 11, color: AppTheme.textSecondary)),
              children: [
                for (final c in r.columns)
                  _ColumnRow(
                    column: c,
                    fields: r.fields,
                    value: _mapping[c.heading],
                    enabled: !_busy,
                    onChanged: (f) => _pointColumn(c.heading, f),
                  ),
              ],
            ),
          ),
        ),
      Padding(
        padding: const EdgeInsets.fromLTRB(20, 12, 20, 4),
        child: Row(children: [
          Expanded(
            child: Wrap(spacing: 8, runSpacing: 4, children: [
              if (_done) _Chip('${r.created} added', AppTheme.success) else _Chip('${r.ready} ready', AppTheme.success),
              if (r.duplicates > 0) _Chip('${r.duplicates} already registered', AppTheme.warning),
              if (r.errors > 0) _Chip('${r.errors} need fixing', AppTheme.error),
            ]),
          ),
          if (r.duplicates + r.errors > 0 && !_done)
            FilterChip(
              label: const Text('Problems only', style: TextStyle(fontSize: 12)),
              selected: _problemsOnly,
              onSelected: (v) => setState(() => _problemsOnly = v),
            ),
        ]),
      ),
      for (final row in capped)
        Padding(padding: const EdgeInsets.fromLTRB(20, 4, 20, 4), child: _RowTile(row: row)),
      if (shown.length > capped.length)
        Padding(
          padding: const EdgeInsets.all(12),
          child: Text('… and ${shown.length - capped.length} more rows',
              textAlign: TextAlign.center, style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
        ),
    ]);
  }
}

class _Chip extends StatelessWidget {
  final String text;
  final Color color;
  const _Chip(this.text, this.color);

  @override
  Widget build(BuildContext context) => Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
        decoration: BoxDecoration(color: color.withOpacity(0.12), borderRadius: BorderRadius.circular(12)),
        child: Text(text, style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: color)),
      );
}

class _ColumnRow extends StatelessWidget {
  final AssetImportColumn column;
  final List<(String, String)> fields;
  final String? value;
  final bool enabled;
  final ValueChanged<String?> onChanged;
  const _ColumnRow({
    required this.column,
    required this.fields,
    required this.value,
    required this.enabled,
    required this.onChanged,
  });

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.fromLTRB(16, 4, 16, 8),
        child: Row(children: [
          Expanded(
            flex: 5,
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text(column.heading, style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600), overflow: TextOverflow.ellipsis),
              if (column.sample != null)
                Text(column.sample!,
                    style: const TextStyle(fontSize: 11, color: AppTheme.textSecondary), overflow: TextOverflow.ellipsis),
            ]),
          ),
          const SizedBox(width: 8),
          Expanded(
            flex: 5,
            child: DropdownButtonFormField<String?>(
              key: ValueKey('col-${column.index}'),
              value: value,
              isExpanded: true,
              decoration: const InputDecoration(isDense: true),
              items: [
                const DropdownMenuItem<String?>(value: null, child: Text('Not imported', style: TextStyle(fontSize: 13))),
                for (final f in fields) DropdownMenuItem<String?>(value: f.$1, child: Text(f.$2, style: const TextStyle(fontSize: 13))),
              ],
              onChanged: enabled ? onChanged : null,
            ),
          ),
        ]),
      );
}

class _RowTile extends StatelessWidget {
  final AssetImportRow row;
  const _RowTile({required this.row});

  @override
  Widget build(BuildContext context) {
    final (color, icon) = switch (row.status) {
      'created' => (AppTheme.success, Icons.check_circle_rounded),
      'duplicate' => (AppTheme.warning, Icons.content_copy_rounded),
      'error' => (AppTheme.error, Icons.error_outline_rounded),
      _ => (AppTheme.textSecondary, Icons.radio_button_unchecked_rounded),
    };
    final meta = [row.assetCode, if (row.category != null) assetCategoryLabel(row.category!)]
        .where((s) => s != null && s.isNotEmpty)
        .join(' · ');
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(color: AppTheme.cardBg, borderRadius: BorderRadius.circular(10), border: Border.all(color: AppTheme.border)),
      child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Icon(icon, color: color, size: 18),
        const SizedBox(width: 10),
        Expanded(
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text('Row ${row.line}: ${(row.name ?? '').isEmpty ? '(no name)' : row.name}',
                style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600)),
            if (meta.isNotEmpty) Text(meta, style: const TextStyle(fontSize: 11, color: AppTheme.textSecondary)),
            if (row.message != null) Text(row.message!, style: TextStyle(fontSize: 11, color: color)),
          ]),
        ),
      ]),
    );
  }
}
