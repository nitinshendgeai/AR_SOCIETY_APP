import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:share_plus/share_plus.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/motion/loading.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/resident_master/data/resident_report_api.dart';
import 'package:ar_society_app/shared/utils/file_saver.dart';
import 'package:ar_society_app/shared/widgets/app_form.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';

final residentReportApiProvider = Provider<ResidentReportApi>((_) => ResidentReportApi());

final residentReportColumnsProvider = FutureProvider.autoDispose<List<ReportColumn>>(
    (ref) => ref.watch(residentReportApiProvider).columns());

/// What the person ticked last time, kept while the app is open.
final residentReportChoiceProvider = StateProvider<Set<String>?>((_) => null);

const _xlsxMime = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet';

/// Choose the columns of the Residents report, then print it, share it or download it as a PDF or an Excel file.
/// [load] fetches the report for the filters the list is showing: it is given the format ('pdf' / 'xlsx') and the
/// chosen column keys.
class ResidentReportSheet extends ConsumerStatefulWidget {
  final Future<Uint8List> Function(String format, List<String> columns) load;
  const ResidentReportSheet({super.key, required this.load});

  @override
  ConsumerState<ResidentReportSheet> createState() => _ResidentReportSheetState();
}

class _ResidentReportSheetState extends ConsumerState<ResidentReportSheet> {
  Set<String>? _chosen;
  String? _busy;

  Future<void> _run(String tag, String format, List<ReportColumn> all, {required bool share}) async {
    final keys = [for (final c in all) if (_chosen!.contains(c.key)) c.key];
    if (keys.isEmpty) return;
    ref.read(residentReportChoiceProvider.notifier).state = {..._chosen!};
    setState(() => _busy = tag);
    try {
      final bytes = await widget.load(format, keys);
      final stamp = DateTime.now().toIso8601String().substring(0, 10);
      final name = 'Residents-Report-$stamp.$format';
      final mime = format == 'pdf' ? 'application/pdf' : _xlsxMime;
      if (format == 'pdf' && !share && await openFileBytes(() async => bytes, mimeType: mime)) {
        if (mounted) Navigator.of(context).pop();
        return;
      }
      if (share || format == 'pdf') {
        await Share.shareXFiles([XFile.fromData(bytes, name: name, mimeType: mime)],
            fileNameOverrides: [name], subject: 'Residents report');
      } else if (await saveFileBytes(bytes, name, mimeType: mime) && mounted) {
        AppToast.success(context, '$name downloaded');
      }
      if (mounted) Navigator.of(context).pop();
    } catch (e) {
      if (mounted) {
        setState(() => _busy = null);
        showErrorToast(context, e);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final async = ref.watch(residentReportColumnsProvider);
    return AppSheetFrame(
      title: 'Print or download residents',
      subtitle: 'For the filters on the list. Choose the columns you need.',
      child: async.when(
        loading: () => const Padding(padding: EdgeInsets.all(24), child: AppLoader()),
        error: (e, _) => AppErrorState(
            compact: true, message: friendlyErrorMessage(e), onRetry: () => ref.invalidate(residentReportColumnsProvider)),
        data: (all) {
          // First time only: what was ticked last time, else the usual columns. Clearing the list later must stick.
          if (_chosen == null) {
            final last = {...?ref.read(residentReportChoiceProvider)}..retainAll({for (final c in all) c.key});
            _chosen = last.isEmpty ? {for (final c in all) if (c.isDefault) c.key} : last;
          }
          final none = _chosen!.isEmpty;
          Widget action(String tag, IconData icon, String label, String format, {required bool share}) => OutlinedButton.icon(
                key: Key('report-$tag'),
                onPressed: _busy != null || none ? null : () => _run(tag, format, all, share: share),
                icon: _busy == tag
                    ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2))
                    : Icon(icon, size: 18),
                label: Text(label),
              );
          return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
            Wrap(children: [
              TextButton(
                  key: const Key('report-defaults'),
                  onPressed: () => setState(() => _chosen = {for (final c in all) if (c.isDefault) c.key}),
                  child: const Text('Usual columns')),
              TextButton(
                  key: const Key('report-all'),
                  onPressed: () => setState(() => _chosen = {for (final c in all) c.key}),
                  child: const Text('All')),
              TextButton(
                  key: const Key('report-none'), onPressed: () => setState(() => _chosen = {}), child: const Text('None')),
            ]),
            for (final c in all)
              CheckboxListTile(
                key: Key('report-col-${c.key}'),
                dense: true,
                contentPadding: EdgeInsets.zero,
                controlAffinity: ListTileControlAffinity.leading,
                value: _chosen!.contains(c.key),
                onChanged: (v) => setState(() => v == true ? _chosen!.add(c.key) : _chosen!.remove(c.key)),
                title: Text(c.label),
                subtitle: c.sensitive
                    ? Text('Personal details', style: TextStyle(fontSize: 11.5, color: AppTheme.warning))
                    : null,
              ),
            const SizedBox(height: 4),
            Text('An identity number is printed with only its last four characters.',
                style: TextStyle(fontSize: 11.5, color: AppTheme.textSecondary)),
            const SizedBox(height: 12),
            Wrap(spacing: 8, runSpacing: 8, children: [
              action('pdf-open', Icons.print_rounded, 'Print / open PDF', 'pdf', share: false),
              action('pdf-share', Icons.ios_share_rounded, 'Share PDF', 'pdf', share: true),
              action('xlsx-download', Icons.table_chart_outlined, 'Download Excel', 'xlsx', share: false),
              action('xlsx-share', Icons.ios_share_rounded, 'Share Excel', 'xlsx', share: true),
            ]),
            if (none)
              Padding(
                padding: EdgeInsets.only(top: 8),
                child: Text('Tick at least one column.', style: TextStyle(fontSize: 12, color: AppTheme.error)),
              ),
          ]);
        },
      ),
    );
  }
}
