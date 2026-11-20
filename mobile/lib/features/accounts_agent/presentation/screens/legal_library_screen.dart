import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/features/accounts_agent/presentation/screens/society_rule_form_screen.dart' show calcValueLabels;
import 'package:ar_society_app/core/router/app_router.dart';
import 'package:go_router/go_router.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/motion/loading.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/core/theme/design_tokens.dart';
import 'package:ar_society_app/features/accounts_agent/data/legal_api.dart';
import 'package:ar_society_app/features/accounts_agent/presentation/providers/legal_providers.dart';
import 'package:ar_society_app/features/accounts_agent/presentation/widgets/agent_widgets.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/shared/widgets/app_form.dart';
import 'package:ar_society_app/shared/widgets/app_status.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';

/// The society's legal sources: its own documents (bye-laws, minutes, policies) with their verification state, the
/// versioned rule registry, and the legal review queue. Uploading never makes a document operative.
class LegalLibraryScreen extends ConsumerWidget {
  const LegalLibraryScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final mayDecide = ref.watch(currentUserProvider)?.isAdminOrCommittee ?? false;
    return DefaultTabController(
      length: 3,
      child: AppPage(
        title: 'Legal document library',
        subtitle: 'Registered bye-laws, resolutions, legal rules and their verification',
        maxWidth: 1040,
        bottom: const TabBar(tabs: [Tab(text: 'Documents'), Tab(text: 'Legal rules'), Tab(text: 'Legal reviews')]),
        floatingActionButton: mayDecide
            ? FloatingActionButton.extended(
                onPressed: () => _upload(context, ref), icon: const Icon(Icons.upload_file_rounded), label: const Text('Upload'))
            : null,
        body: TabBarView(children: [
          _Documents(mayDecide: mayDecide),
          _Rules(mayDecide: mayDecide),
          _Reviews(mayDecide: mayDecide),
        ]),
      ),
    );
  }

  Future<void> _upload(BuildContext context, WidgetRef ref) async {
    final pick = await FilePicker.platform.pickFiles(withData: true, type: FileType.custom, allowedExtensions: ['pdf', 'docx', 'doc', 'txt']);
    final f = pick?.files.firstOrNull;
    if (f == null || f.bytes == null || !context.mounted) return;
    var type = 'REGISTERED_BYELAWS';
    final title = TextEditingController(text: f.name);
    final ref0 = TextEditingController();
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setS) => AlertDialog(
          title: const Text('Upload a legal document'),
          content: SingleChildScrollView(
            child: Column(mainAxisSize: MainAxisSize.min, children: [
              DropdownButtonFormField<String>(
                initialValue: type,
                isExpanded: true,
                decoration: const InputDecoration(labelText: 'Document type'),
                items: [for (final e in documentTypes.entries) DropdownMenuItem(value: e.key, child: Text(e.value))],
                onChanged: (v) => setS(() => type = v ?? type),
              ),
              TextField(controller: title, decoration: const InputDecoration(labelText: 'Title')),
              TextField(controller: ref0, decoration: const InputDecoration(labelText: 'Registration / reference number (optional)')),
              const SizedBox(height: 10),
              const Text('The file is kept unchanged with its fingerprint. It is NOT used for compliance until an authorised person verifies it.',
                  style: TextStyle(fontSize: 12.5, color: AppTheme.textSecondary)),
            ]),
          ),
          actions: [
            TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancel')),
            FilledButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('Upload')),
          ],
        ),
      ),
    );
    if (ok != true || !context.mounted) return;
    try {
      final d = await ref.read(legalApiProvider).upload(
          bytes: f.bytes!, fileName: f.name, type: type, title: title.text.trim().isEmpty ? f.name : title.text.trim(),
          requestedStatus: statusForType[type], referenceNumber: ref0.text.trim());
      invalidateLegal(ref);
      if (context.mounted) {
        AppToast.success(context, d.issues.isEmpty ? 'Uploaded — awaiting verification' : 'Uploaded with ${d.issues.length} point(s) to check');
      }
    } catch (e) {
      if (context.mounted) showErrorToast(context, e);
    }
  }
}

class _Documents extends ConsumerWidget {
  final bool mayDecide;
  const _Documents({required this.mayDecide});

  Future<void> _verify(BuildContext context, WidgetRef ref, LegalDocument d) async {
    final note = TextEditingController();
    final override = TextEditingController();
    DateTime? approved;
    var verification = 'VERIFIED_SECONDARY_SOURCE';
    final status = statusForType[d.type];
    if (status == null) {
      showErrorToast(context, Exception('This kind of document is kept for reference; it is not made operative.'));
      return;
    }
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setS) => AlertDialog(
          title: Text('Verify as ${titleCase(status).toLowerCase()}'),
          content: SingleChildScrollView(
            child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text('Confirm you compared "${d.title}" with the registered / signed original.', style: const TextStyle(fontSize: 13)),
              DropdownButtonFormField<String>(
                initialValue: verification,
                decoration: const InputDecoration(labelText: 'Verified against'),
                items: const [
                  DropdownMenuItem(value: 'VERIFIED_SECONDARY_SOURCE', child: Text('Certified copy / signed original')),
                  DropdownMenuItem(value: 'LEGAL_REVIEW_REQUIRED', child: Text('Needs legal review')),
                ],
                onChanged: (v) => setS(() => verification = v ?? verification),
              ),
              if (status == 'REGISTERED' || status == 'APPROVED_AMENDMENT')
                TextButton.icon(
                  icon: const Icon(Icons.event_outlined),
                  label: Text(approved == null ? 'Registrar approval date (required)' : day(approved!)),
                  onPressed: () async {
                    final p = await showDatePicker(context: ctx, firstDate: DateTime(1960), lastDate: DateTime.now());
                    if (p != null) setS(() => approved = p);
                  },
                ),
              TextField(controller: note, maxLines: 2, decoration: const InputDecoration(labelText: 'How it was verified (required)')),
              if (d.issues.any((i) => i.toLowerCase().contains('draft')))
                TextField(controller: override, maxLines: 2,
                    decoration: const InputDecoration(labelText: 'Draft markers found — registration details confirming it is final')),
            ]),
          ),
          actions: [
            TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancel')),
            FilledButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('Verify')),
          ],
        ),
      ),
    );
    if (ok != true || !context.mounted) return;
    try {
      await ref.read(legalApiProvider).verifyDocument(d.id,
          status: verification == 'LEGAL_REVIEW_REQUIRED' ? 'UNVERIFIED' : status,
          verification: verification, note: note.text.trim(), approvalDate: approved, overrideDraftWarning: override.text.trim());
      invalidateLegal(ref);
      if (context.mounted) AppToast.success(context, 'Document updated');
    } catch (e) {
      if (context.mounted) showErrorToast(context, e);
    }
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final async = ref.watch(legalDocumentsProvider);
    return async.when(
      loading: () => const AppLoader(),
      error: (e, _) => AppErrorState(message: friendlyErrorMessage(e), onRetry: () => ref.invalidate(legalDocumentsProvider)),
      data: (docs) => docs.isEmpty
          ? const AppEmptyState(
              icon: Icons.menu_book_outlined,
              title: 'No documents yet',
              subtitle: 'Upload the society\'s registered bye-laws and approved amendments first. Model bye-laws are not your bye-laws.')
          : ListView(padding: const EdgeInsets.fromLTRB(16, 12, 16, 96), children: [
              for (final d in docs)
                Padding(
                  padding: const EdgeInsets.only(bottom: 10),
                  child: AgentCard(
                    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                      Wrap(spacing: 8, runSpacing: 6, children: [
                        AppStatusChip(label: titleCase(d.status), tone: d.operative ? AppTone.success : AppTone.warning),
                        AppStatusChip(label: verificationLabel(d.verification), tone: AppTone.neutral),
                        if (!d.societySpecific) const AppStatusChip(label: 'Jurisdiction-wide law', tone: AppTone.info),
                        AppStatusChip(label: 'Text: ${titleCase(d.quality)}', tone: d.quality == 'GOOD' ? AppTone.neutral : AppTone.warning),
                      ]),
                      const SizedBox(height: 8),
                      Text(d.title, style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w700)),
                      KeyValue('Type', documentTypes[d.type] ?? titleCase(d.type)),
                      KeyValue('Language', d.language == 'mr' ? 'Marathi' : d.language == 'en' ? 'English' : titleCase(d.language)),
                      KeyValue('Pages', d.pages?.toString()),
                      KeyValue('Fingerprint', d.sha256.length > 16 ? '${d.sha256.substring(0, 16)}…' : d.sha256),
                      for (final i in d.issues)
                        Padding(padding: const EdgeInsets.only(top: 4), child: Text('• $i', style: const TextStyle(fontSize: 12.5, color: AppTheme.warning))),
                      if (mayDecide && d.societySpecific && !d.operative && d.status != 'SUPERSEDED')
                        Align(
                          alignment: Alignment.centerRight,
                          child: TextButton.icon(onPressed: () => _verify(context, ref, d), icon: const Icon(Icons.verified_outlined), label: const Text('Verify')),
                        ),
                    ]),
                  ),
                ),
            ]),
    );
  }
}

class _Rules extends ConsumerWidget {
  final bool mayDecide;
  const _Rules({required this.mayDecide});

  Future<void> _verify(BuildContext context, WidgetRef ref, LegalRule r) async {
    final note = TextEditingController();
    final page = TextEditingController(text: r.raw['page_number'] as String? ?? '');
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text('Verify ${r.code}'),
        content: SingleChildScrollView(
          child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
            const Text('Confirm the figure and wording match the verified society document. The document itself must already '
                'be verified (registered / approved).', style: TextStyle(fontSize: 13)),
            TextField(controller: page, decoration: const InputDecoration(labelText: 'Page checked (required)')),
            TextField(controller: note, maxLines: 2, decoration: const InputDecoration(labelText: 'How it was checked (required)')),
          ]),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancel')),
          FilledButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('Verify')),
        ],
      ),
    );
    if (ok != true || !context.mounted) return;
    if (note.text.trim().length < 3 || page.text.trim().isEmpty) {
      showErrorToast(context, Exception('Record the page and how it was checked'));
      return;
    }
    try {
      await ref.read(legalApiProvider).verifyRule(r.id,
          verification: 'VERIFIED_SECONDARY_SOURCE', note: note.text.trim(), pageNumber: page.text.trim(), legalStatus: 'BINDING');
      invalidateLegal(ref);
      if (context.mounted) AppToast.success(context, 'Rule verified — it now governs the agent\'s checks');
    } catch (e) {
      if (context.mounted) showErrorToast(context, e);
    }
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final async = ref.watch(legalRulesProvider);
    return async.when(
      loading: () => const AppLoader(),
      error: (e, _) => AppErrorState(message: friendlyErrorMessage(e), onRetry: () => ref.invalidate(legalRulesProvider)),
      data: (rules) => ListView(padding: const EdgeInsets.fromLTRB(16, 12, 16, 96), children: [
        const Text('Rules are versioned. A rule that is not verified against the original Gazette or your registered bye-laws can only '
            'raise potential issues for review, never a confirmed violation.', style: TextStyle(fontSize: 13, color: AppTheme.textSecondary)),
        if (mayDecide) ...[
          const SizedBox(height: 10),
          Align(
            alignment: Alignment.centerLeft,
            child: OutlinedButton.icon(
              onPressed: () => context.push(AppRoutes.accountsAgentSocietyRuleNew),
              icon: const Icon(Icons.add_rounded),
              label: const Text('Add society rule'),
            ),
          ),
        ],
        const SizedBox(height: 10),
        for (final r in rules)
          Padding(
            padding: const EdgeInsets.only(bottom: 10),
            child: AgentCard(
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Wrap(spacing: 8, runSpacing: 6, children: [
                  AppStatusChip(label: verificationLabel(r.verification), tone: r.isVerified ? AppTone.success : AppTone.warning),
                  AppStatusChip(label: titleCase(r.legalStatus), tone: AppTone.neutral),
                  if (r.societySpecific) const AppStatusChip(label: 'Society rule', tone: AppTone.info),
                ]),
                const SizedBox(height: 6),
                Text(r.title, style: const TextStyle(fontWeight: FontWeight.w700)),
                KeyValue('Rule', '${r.code} v${r.version}'),
                KeyValue('Level', r.levelName),
                KeyValue('Reference', r.reference),
                if (r.calcValue != null) KeyValue('Figure', '${calcValueLabels[r.calcType] ?? titleCase(r.calcType ?? '')}: ${r.calcValue}'),
                KeyValue('In force', [if (r.effectiveFrom != null) 'from ${r.effectiveFrom}', if (r.effectiveUntil != null) 'until ${r.effectiveUntil}'].join(' ')),
                if (r.note != null) Text(r.note!, style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
                if (mayDecide && r.societySpecific && !r.isVerified && r.isLatest)
                  Align(
                    alignment: Alignment.centerRight,
                    child: TextButton.icon(onPressed: () => _verify(context, ref, r), icon: const Icon(Icons.verified_outlined), label: const Text('Verify')),
                  ),
              ]),
            ),
          ),
      ]),
    );
  }
}

class _Reviews extends ConsumerWidget {
  final bool mayDecide;
  const _Reviews({required this.mayDecide});

  Future<void> _decide(BuildContext context, WidgetRef ref, LegalReview r) async {
    final note = TextEditingController();
    final status = await showDialog<String>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(r.title),
        content: TextField(controller: note, maxLines: 3, decoration: const InputDecoration(labelText: 'Decision and reasons (required)')),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Cancel')),
          TextButton(onPressed: () => Navigator.pop(ctx, 'DISMISSED'), child: const Text('Dismiss')),
          FilledButton(onPressed: () => Navigator.pop(ctx, 'RESOLVED'), child: const Text('Resolve')),
        ],
      ),
    );
    if (status == null || !context.mounted) return;
    try {
      await ref.read(legalApiProvider).decideReview(r.id, status, note.text.trim());
      invalidateLegal(ref);
    } catch (e) {
      if (context.mounted) showErrorToast(context, e);
    }
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final async = ref.watch(legalReviewsProvider);
    return async.when(
      loading: () => const AppLoader(),
      error: (e, _) => AppErrorState(message: friendlyErrorMessage(e), onRetry: () => ref.invalidate(legalReviewsProvider)),
      data: (rows) => ListView(padding: const EdgeInsets.fromLTRB(16, 12, 16, 96), children: [
        for (final r in rows)
          Padding(
            padding: const EdgeInsets.only(bottom: 10),
            child: AgentCard(
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Wrap(spacing: 8, runSpacing: 6, children: [
                  AppStatusChip(label: titleCase(r.status), tone: r.isOpen ? AppTone.warning : AppTone.neutral),
                  AppStatusChip(label: titleCase(r.type), tone: AppTone.neutral),
                  if (r.blocking && r.isOpen) const AppStatusChip(label: 'Blocks confirmed findings', tone: AppTone.danger),
                ]),
                const SizedBox(height: 6),
                Text(r.title, style: const TextStyle(fontWeight: FontWeight.w700)),
                const SizedBox(height: 4),
                Text(r.description, style: const TextStyle(fontSize: 13, height: 1.35)),
                if (mayDecide && r.isOpen && r.societySpecific)
                  Align(alignment: Alignment.centerRight, child: TextButton(onPressed: () => _decide(context, ref, r), child: const Text('Decide'))),
                if (r.isOpen && !r.societySpecific)
                  const Padding(
                    padding: EdgeInsets.only(top: 6),
                    child: Text('Jurisdiction-wide: decided by the platform\'s legal reviewer.', style: TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
                  ),
              ]),
            ),
          ),
      ]),
    );
  }
}
