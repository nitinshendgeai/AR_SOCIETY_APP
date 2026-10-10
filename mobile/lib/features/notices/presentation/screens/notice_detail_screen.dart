import 'package:flutter/material.dart';
import 'package:ar_society_app/core/motion/loading.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/layout/app_sheet.dart';
import 'package:ar_society_app/core/router/app_router.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/features/notices/data/notices_api.dart';
import 'package:ar_society_app/features/notices/presentation/providers/notices_providers.dart';
import 'package:ar_society_app/features/notices/presentation/screens/notice_sheets.dart';
import 'package:ar_society_app/features/notices/presentation/screens/notices_screen.dart' show noticeDay;
import 'package:ar_society_app/shared/widgets/app_data_table.dart' show StatusPill;
import 'package:ar_society_app/shared/widgets/app_widgets.dart';

/// One notice in full. The reader can confirm they have read it; the committee sees who has and has not, and
/// can publish a draft, change it, delete it, or archive a published notice.
class NoticeDetailScreen extends ConsumerStatefulWidget {
  final String noticeId;
  const NoticeDetailScreen({super.key, required this.noticeId});

  @override
  ConsumerState<NoticeDetailScreen> createState() => _NoticeDetailScreenState();
}

class _NoticeDetailScreenState extends ConsumerState<NoticeDetailScreen> {
  bool _busy = false;

  Future<void> _run(Future<void> Function() action, {String? done}) async {
    setState(() => _busy = true);
    try {
      await action();
      invalidateNotices(ref);
      if (mounted && done != null) AppToast.success(context, done);
    } catch (e) {
      if (mounted) showErrorToast(context, e);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<bool> _confirm(String title, String body, String yes) async =>
      (await showDialog<bool>(
        context: context,
        builder: (dialogContext) => AlertDialog(
          title: Text(title),
          content: Text(body),
          actions: [
            TextButton(onPressed: () => Navigator.of(dialogContext).pop(false), child: const Text('Cancel')),
            FilledButton(onPressed: () => Navigator.of(dialogContext).pop(true), child: Text(yes)),
          ],
        ),
      )) ==
      true;

  @override
  Widget build(BuildContext context) {
    final user = ref.watch(currentUserProvider);
    final writer = user?.isAdminOrCommittee ?? false;
    final async = ref.watch(noticeProvider(widget.noticeId));
    final api = ref.read(noticesApiProvider);

    return Scaffold(
      backgroundColor: AppTheme.surface,
      appBar: AppBar(
        title: const Text('Notice'),
        actions: [
          if (writer && async.valueOrNull?.isDraft == true)
            IconButton(
              tooltip: 'Edit',
              icon: const Icon(Icons.edit_outlined),
              onPressed: () => showAppSheet(context: context, builder: (_) => NoticeFormSheet(draft: async.value)),
            ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: () async => invalidateNotices(ref),
        child: async.when(
          loading: () => const AppLoader(),
          error: (e, _) => ListView(padding: const EdgeInsets.all(20), children: [AppErrorBanner(message: friendlyErrorMessage(e))]),
          data: (n) => ResponsiveBody(
            maxWidth: 760,
            child: ListView(padding: const EdgeInsets.fromLTRB(16, 16, 16, 40), children: [
              Row(children: [
                Icon(noticeCategoryIcon(n.category), size: 18, color: AppTheme.textSecondary),
                const SizedBox(width: 6),
                Text(noticeCategoryLabel(n.category), style: const TextStyle(color: AppTheme.textSecondary, fontSize: 13)),
                const SizedBox(width: 10),
                if (n.priority == 'urgent' || n.priority == 'high') StatusPill(noticePriorityLabel(n.priority), noticePriorityColor(n.priority)),
                if (writer && n.isDraft) const Padding(padding: EdgeInsets.only(left: 8), child: StatusPill('Draft', AppTheme.warning)),
                if (n.status == 'archived') const Padding(padding: EdgeInsets.only(left: 8), child: StatusPill('Archived', AppTheme.textSecondary)),
              ]),
              const SizedBox(height: 10),
              Text(n.title, style: const TextStyle(fontSize: 22, fontWeight: FontWeight.w800, height: 1.25)),
              const SizedBox(height: 6),
              Text(
                [
                  if (n.publishDate != null) 'Posted ${noticeDay(n.publishDate)}',
                  if ((n.createdByName ?? '').isNotEmpty) 'by ${n.createdByName}',
                  if (n.expiryDate != null) 'shown until ${noticeDay(n.expiryDate)}',
                ].join(' · '),
                style: const TextStyle(color: AppTheme.textSecondary, fontSize: 12.5),
              ),
              const SizedBox(height: 16),
              SelectableText(n.content, style: const TextStyle(fontSize: 15, height: 1.55)),
              const SizedBox(height: 22),

              // The reader's side
              if (n.isPublished && !writer && n.ackRequired)
                n.acknowledged == true
                    ? const Row(children: [
                        Icon(Icons.check_circle_rounded, color: AppTheme.success),
                        SizedBox(width: 8),
                        Text('You have confirmed you have read this', style: TextStyle(fontWeight: FontWeight.w600)),
                      ])
                    : FilledButton.icon(
                        onPressed: _busy ? null : () => _run(() => api.acknowledge(n.id), done: 'Thank you'),
                        icon: const Icon(Icons.done_all_rounded, size: 18),
                        label: const Text('I have read this'),
                      ),

              // The committee's side
              if (writer) ...[
                _AudienceCard(notice: n),
                const SizedBox(height: 12),
                Wrap(spacing: 10, runSpacing: 10, children: [
                  if (n.isDraft) ...[
                    FilledButton.icon(
                      onPressed: _busy
                          ? null
                          : () => _run(() async {
                                final p = await api.publish(n.id);
                                if (mounted) AppToast.success(context, 'Published to ${p.totalAudience} ${p.totalAudience == 1 ? 'person' : 'people'}');
                              }),
                      icon: const Icon(Icons.send_rounded, size: 18),
                      label: const Text('Publish'),
                    ),
                    OutlinedButton.icon(
                      onPressed: _busy
                          ? null
                          : () async {
                              if (!await _confirm('Delete this draft?', 'It has not been published, so nobody has seen it.', 'Delete')) return;
                              await _run(() => api.deleteDraft(n.id), done: 'Draft deleted');
                              if (mounted) context.canPop() ? context.pop() : context.go(AppRoutes.notices);
                            },
                      icon: const Icon(Icons.delete_outline_rounded, size: 18),
                      label: const Text('Delete draft'),
                    ),
                  ],
                  if (n.isPublished)
                    OutlinedButton.icon(
                      onPressed: _busy
                          ? null
                          : () async {
                              if (!await _confirm('Archive this notice?', 'It leaves everyone\'s notice board. A published notice can\'t be changed, so write a new one to correct it.', 'Archive')) return;
                              await _run(() => api.archive(n.id), done: 'Notice archived');
                            },
                      icon: const Icon(Icons.inventory_2_outlined, size: 18),
                      label: const Text('Archive'),
                    ),
                ]),
                if (n.isPublished) ...[
                  const SizedBox(height: 18),
                  _AckSection(notice: n),
                ],
              ],
            ]),
          ),
        ),
      ),
    );
  }
}

class _AudienceCard extends ConsumerWidget {
  final NoticeItem notice;
  const _AudienceCard({required this.notice});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final n = notice;
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(color: AppTheme.cardBg, borderRadius: BorderRadius.circular(AppTheme.radiusM), border: Border.all(color: AppTheme.border)),
      child: Row(children: [
        const Icon(Icons.groups_2_outlined, color: AppTheme.textSecondary),
        const SizedBox(width: 10),
        Expanded(
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text('For: ${audienceLabel(n.audience)}', style: const TextStyle(fontWeight: FontWeight.w600)),
            Text(
              n.isPublished
                  ? '${n.totalAudience} ${n.totalAudience == 1 ? 'person' : 'people'} can see it'
                  : 'Not published yet. Nobody else can see it.',
              style: const TextStyle(fontSize: 12.5, color: AppTheme.textSecondary),
            ),
          ]),
        ),
      ]),
    );
  }
}

class _AckSection extends ConsumerWidget {
  final NoticeItem notice;
  const _AckSection({required this.notice});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    if (!notice.ackRequired) return const SizedBox.shrink();
    final report = ref.watch(ackReportProvider(notice.id));
    return report.when(
      loading: () => const LinearProgressIndicator(),
      error: (e, _) => AppErrorBanner(message: friendlyErrorMessage(e)),
      data: (r) => Container(
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(color: AppTheme.cardBg, borderRadius: BorderRadius.circular(AppTheme.radiusM), border: Border.all(color: AppTheme.border)),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            const Expanded(child: Text('Who has read it', style: TextStyle(fontWeight: FontWeight.w700))),
            Text('${r.acknowledged} of ${r.total} (${r.ratePct.toStringAsFixed(r.ratePct % 1 == 0 ? 0 : 1)}%)',
                style: const TextStyle(fontWeight: FontWeight.w600)),
          ]),
          const SizedBox(height: 8),
          ClipRRect(
            borderRadius: BorderRadius.circular(4),
            child: LinearProgressIndicator(value: r.total == 0 ? 0 : r.acknowledged / r.total, minHeight: 8, color: AppTheme.success, backgroundColor: AppTheme.border),
          ),
          if (r.pendingPeople.isNotEmpty)
            ExpansionTile(
              tilePadding: EdgeInsets.zero,
              title: Text('Not yet read (${r.pending})', style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600)),
              children: [for (final p in r.pendingPeople) _person(p, false)],
            ),
          if (r.acknowledgers.isNotEmpty)
            ExpansionTile(
              tilePadding: EdgeInsets.zero,
              title: Text('Read it (${r.acknowledged})', style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600)),
              children: [for (final p in r.acknowledgers) _person(p, true)],
            ),
        ]),
      ),
    );
  }

  Widget _person(AckPerson p, bool done) => ListTile(
        dense: true,
        contentPadding: EdgeInsets.zero,
        leading: Icon(done ? Icons.check_circle_rounded : Icons.radio_button_unchecked_rounded, size: 18, color: done ? AppTheme.success : AppTheme.textTertiary),
        title: Text(p.name.isEmpty ? 'Unnamed' : p.name),
        subtitle: p.flat.isEmpty ? null : Text(p.flat),
        trailing: p.at == null ? null : Text(noticeDay(p.at), style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
      );
}
