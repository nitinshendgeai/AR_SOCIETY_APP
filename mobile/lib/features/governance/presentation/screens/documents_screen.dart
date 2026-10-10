import 'package:file_picker/file_picker.dart';
import 'package:ar_society_app/core/motion/loading.dart';
import 'package:flutter/material.dart';
import 'package:ar_society_app/core/l10n/app_locale.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';
import 'package:ar_society_app/core/layout/app_sheet.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/features/governance/data/governance_api.dart';
import 'package:ar_society_app/features/maintenance_billing/presentation/widgets/billing_sheet_frame.dart';
import 'package:ar_society_app/shared/utils/file_saver.dart';
import 'package:ar_society_app/shared/widgets/app_data_table.dart'
    show StatusPill;
import 'package:ar_society_app/shared/widgets/app_widgets.dart';
import 'package:ar_society_app/shared/widgets/app_form.dart';

const _mimeByExtension = {
  'pdf': 'application/pdf',
  'png': 'image/png',
  'jpg': 'image/jpeg',
  'jpeg': 'image/jpeg',
  'txt': 'text/plain',
  'doc': 'application/msword',
  'docx':
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  'xls': 'application/vnd.ms-excel',
  'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
};

IconData _iconFor(String mime) {
  if (mime == 'application/pdf') return Icons.picture_as_pdf_rounded;
  if (mime.startsWith('image/')) return Icons.image_rounded;
  if (mime.contains('sheet') || mime.contains('excel'))
    return Icons.table_chart_rounded;
  return Icons.description_rounded;
}

/// The society's papers in one place: bye-laws, minutes, audit reports, insurance, agreements.
class DocumentsScreen extends ConsumerWidget {
  const DocumentsScreen({super.key});

  Future<void> _add(BuildContext context) async {
    final pick = await FilePicker.platform.pickFiles(
        withData: true,
        type: FileType.custom,
        allowedExtensions: _mimeByExtension.keys.toList());
    final f = pick?.files.firstOrNull;
    if (f == null || f.bytes == null || !context.mounted) return;
    await showAppSheet(context: context, builder: (_) => _AddSheet(file: f));
  }

  Future<void> _open(BuildContext context, WidgetRef ref, SocietyDoc d) async {
    try {
      final bytes = await ref.read(governanceApiProvider).download(d.id);
      final saved =
          await saveFileBytes(bytes, d.fileName, mimeType: d.mimeType);
      if (context.mounted && saved)
        AppToast.success(context, 'Saved ${d.fileName}');
    } catch (e) {
      if (context.mounted) showErrorToast(context, e);
    }
  }

  Future<void> _delete(
      BuildContext context, WidgetRef ref, SocietyDoc d, String sid) async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text('Remove "${d.title}"?'),
        content: const Text('Members will no longer see it.'),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(ctx, false),
              child: const Text('Keep it')),
          FilledButton(
              style: FilledButton.styleFrom(backgroundColor: AppTheme.error),
              onPressed: () => Navigator.pop(ctx, true),
              child: const Text('Remove')),
        ],
      ),
    );
    if (ok != true) return;
    try {
      await ref.read(governanceApiProvider).deleteDocument(d.id);
      ref.invalidate(documentsProvider(sid));
    } catch (e) {
      if (context.mounted) showErrorToast(context, e);
    }
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final user = ref.watch(currentUserProvider);
    final sid = user?.societyId ?? '';
    final office = user?.isAdminOrCommittee == true;
    final async = ref.watch(documentsProvider(sid));
    return AppPage(
      title: 'Documents',
      floatingActionButton: office
          ? FloatingActionButton.extended(
              onPressed: () => _add(context),
              icon: const Icon(Icons.upload_file_rounded),
              label: Text(context.tr('Add document')))
          : null,
      body: async.when(
        loading: () => const SkeletonList(),
        error: (e, _) => Center(
            child: OutlinedButton(
                onPressed: () => ref.invalidate(documentsProvider(sid)),
                child: const Text('Could not load. Try again'))),
        data: (docs) {
          if (docs.isEmpty) {
            return AppEmptyState(
                icon: Icons.folder_open_rounded,
                title: context.tr('No documents yet'),
                subtitle: office
                    ? 'Add the bye-laws, minutes and audit reports.'
                    : 'Documents from the committee will appear here.');
          }
          final byCategory = <String, List<SocietyDoc>>{};
          for (final d in docs) {
            byCategory.putIfAbsent(d.category, () => []).add(d);
          }
          return RefreshIndicator(
            onRefresh: () async => ref.invalidate(documentsProvider(sid)),
            child: ListView(
                padding: const EdgeInsets.fromLTRB(16, 8, 16, 96),
                children: [
                  for (final c in kDocCategories)
                    if (byCategory[c.$1] != null) ...[
                      Padding(
                          padding: const EdgeInsets.fromLTRB(2, 14, 2, 8),
                          child: Text(c.$2,
                              style: const TextStyle(
                                  fontSize: 13,
                                  fontWeight: FontWeight.w600,
                                  color: AppTheme.textSecondary))),
                      for (final d in byCategory[c.$1]!)
                        Padding(
                          padding: const EdgeInsets.only(bottom: 8),
                          child: DecoratedBox(
                            decoration: BoxDecoration(
                                color: AppTheme.cardBg,
                                borderRadius:
                                    BorderRadius.circular(AppTheme.radiusL),
                                boxShadow: AppTheme.cardShadow),
                            child: Material(
                              type: MaterialType.transparency,
                              child: ListTile(
                                onTap: () => _open(context, ref, d),
                                leading: Icon(_iconFor(d.mimeType),
                                    color: AppTheme.primary),
                                title: Text(d.title,
                                    style: const TextStyle(
                                        fontWeight: FontWeight.w600)),
                                subtitle: Text(
                                    [
                                      sizeText(d.sizeBytes),
                                      if (d.createdAt != null)
                                        DateFormat('d MMM yyyy')
                                            .format(d.createdAt!),
                                      if ((d.description ?? '').isNotEmpty)
                                        d.description!,
                                    ].join(' · '),
                                    maxLines: 2,
                                    overflow: TextOverflow.ellipsis),
                                trailing: Row(
                                    mainAxisSize: MainAxisSize.min,
                                    children: [
                                      if (d.visibility == 'committee')
                                        const StatusPill(
                                            'Committee', AppTheme.warning),
                                      if (office)
                                        IconButton(
                                            tooltip: 'Remove',
                                            onPressed: () =>
                                                _delete(context, ref, d, sid),
                                            icon: const Icon(
                                                Icons.delete_outline_rounded,
                                                size: 20)),
                                    ]),
                              ),
                            ),
                          ),
                        ),
                    ],
                ]),
          );
        },
      ),
    );
  }
}

class _AddSheet extends ConsumerStatefulWidget {
  final PlatformFile file;
  const _AddSheet({required this.file});
  @override
  ConsumerState<_AddSheet> createState() => _AddSheetState();
}

class _AddSheetState extends ConsumerState<_AddSheet> {
  final _form = GlobalKey<FormState>();
  late final _title = TextEditingController(
      text: widget.file.name.replaceAll(RegExp(r'\.[^.]+$'), ''));
  final _description = TextEditingController();
  String _category = 'other';
  String _visibility = 'everyone';
  bool _saving = false;

  @override
  void dispose() {
    _title.dispose();
    _description.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    if (!_form.currentState!.validate()) return;
    setState(() => _saving = true);
    try {
      final ext = (widget.file.extension ?? '').toLowerCase();
      final sid = ref.read(currentUserProvider)?.societyId ?? '';
      await ref.read(governanceApiProvider).addDocument(sid,
          title: _title.text.trim(),
          category: _category,
          visibility: _visibility,
          description: _description.text.trim(),
          bytes: widget.file.bytes!,
          fileName: widget.file.name,
          mimeType: _mimeByExtension[ext] ?? 'application/octet-stream');
      ref.invalidate(documentsProvider(sid));
      if (mounted) {
        AppToast.success(context, 'Document added');
        Navigator.pop(context);
      }
    } catch (e) {
      if (mounted) {
        setState(() => _saving = false);
        showErrorToast(context, e);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return BillingSheetFrame(
      title: 'Add a document',
      child: Form(
        key: _form,
        child:
            Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          Row(children: [
            const Icon(Icons.attach_file_rounded,
                size: 18, color: AppTheme.textSecondary),
            const SizedBox(width: 6),
            Expanded(
                child: Text(
                    '${widget.file.name} · ${sizeText(widget.file.size)}',
                    style: const TextStyle(
                        fontSize: 13, color: AppTheme.textSecondary))),
          ]),
          const SizedBox(height: 14),
          FormFieldBox(label: 'Title', required: true, child: TextFormField(
              controller: _title,
              decoration: const InputDecoration(),
              validator: (v) =>
                  (v ?? '').trim().isEmpty ? 'Enter a title' : null)),
          const SizedBox(height: 12),
          FormFieldBox(label: 'Kind of document', child: DropdownButtonFormField<String>(
            initialValue: _category,
            decoration: const InputDecoration(),
            items: [
              for (final c in kDocCategories)
                DropdownMenuItem(value: c.$1, child: Text(c.$2))
            ],
            onChanged: (v) => setState(() => _category = v ?? _category),
          )),
          const SizedBox(height: 12),
          FormFieldBox(label: 'Who can see it', child: DropdownButtonFormField<String>(
            initialValue: _visibility,
            decoration: const InputDecoration(),
            items: const [
              DropdownMenuItem(value: 'everyone', child: Text('Every member')),
              DropdownMenuItem(
                  value: 'committee', child: Text('Committee only')),
            ],
            onChanged: (v) => setState(() => _visibility = v ?? _visibility),
          )),
          const SizedBox(height: 12),
          FormFieldBox(label: 'Note (optional)', child: TextFormField(
              controller: _description,
              minLines: 1,
              maxLines: 3,
              decoration: const InputDecoration())),
          const SizedBox(height: 16),
          AppPrimaryButton(label: 'Add', isLoading: _saving, onPressed: _save),
        ]),
      ),
    );
  }
}
