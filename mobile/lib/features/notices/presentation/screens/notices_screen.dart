import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/layout/app_shell.dart' show isDesktopLayout;
import 'package:ar_society_app/core/layout/app_sheet.dart';
import 'package:ar_society_app/core/router/app_router.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/features/notices/data/notices_api.dart';
import 'package:ar_society_app/features/notices/presentation/providers/notices_providers.dart';
import 'package:ar_society_app/features/notices/presentation/screens/notice_sheets.dart';
import 'package:ar_society_app/features/notices/presentation/widgets/emergency_banner.dart';
import 'package:ar_society_app/shared/widgets/app_data_table.dart' show HeaderActionButton, StatusPill;
import 'package:ar_society_app/shared/widgets/app_widgets.dart';

String noticeRoute(String id) => AppRoutes.noticeDetail.replaceFirst(':id', id);

const _months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
String noticeDay(DateTime? d) {
  if (d == null) return '';
  final l = d.toLocal();
  return '${l.day} ${_months[l.month - 1]} ${l.year}';
}

/// The society's notice board. Everyone sees the notices meant for them, urgent first; the committee also
/// manages them here (drafts, published, archived) and can raise an emergency alert.
class NoticesScreen extends ConsumerStatefulWidget {
  const NoticesScreen({super.key});

  @override
  ConsumerState<NoticesScreen> createState() => _NoticesScreenState();
}

class _NoticesScreenState extends ConsumerState<NoticesScreen> with SingleTickerProviderStateMixin {
  TabController? _tabs;

  @override
  void dispose() {
    _tabs?.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final user = ref.watch(currentUserProvider);
    final societyId = user?.societyId;
    if (user == null || societyId == null) return const Scaffold(body: Center(child: Text('No society context')));
    final writer = user.isAdminOrCommittee;
    final raiser = writer || user.isManager || user.isSecurity;
    final desktop = isDesktopLayout(context);
    if (writer && _tabs == null) _tabs = TabController(length: 2, vsync: this);

    void newNotice() => showAppSheet(context: context, builder: (_) => const NoticeFormSheet());
    void alert() => showAppSheet(context: context, builder: (_) => const AlertSheet());

    final board = _Board(societyId: societyId, raiser: raiser);
    return Scaffold(
      backgroundColor: AppTheme.surface,
      appBar: AppBar(
        title: const Text('Notices'),
        actions: [
          if (raiser)
            TextButton.icon(
              onPressed: alert,
              icon: const Icon(Icons.warning_amber_rounded, size: 18, color: AppTheme.error),
              label: const Text('Emergency alert', style: TextStyle(color: AppTheme.error)),
            ),
          if (writer && desktop) HeaderActionButton(icon: Icons.add_rounded, label: 'New notice', onPressed: newNotice),
        ],
        bottom: writer ? TabBar(controller: _tabs, tabs: const [Tab(text: 'Notice board'), Tab(text: 'Manage')]) : null,
      ),
      floatingActionButton: writer && !desktop
          ? FloatingActionButton.extended(onPressed: newNotice, icon: const Icon(Icons.add_rounded), label: const Text('New notice'))
          : null,
      body: writer ? TabBarView(controller: _tabs, children: [board, _Manage(societyId: societyId)]) : board,
    );
  }
}

// ── Board ────────────────────────────────────────────────────────────────────

class _Board extends ConsumerWidget {
  final String societyId;
  final bool raiser;
  const _Board({required this.societyId, required this.raiser});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final board = ref.watch(noticeBoardProvider(societyId));
    final alerts = ref.watch(activeAlertsProvider).valueOrNull ?? const <EmergencyAlertItem>[];
    return RefreshIndicator(
      onRefresh: () async => invalidateNotices(ref),
      child: ResponsiveBody(
        maxWidth: 820,
        child: ListView(padding: const EdgeInsets.fromLTRB(16, 16, 16, 96), children: [
          for (final a in alerts) _AlertCard(alert: a, canEnd: raiser),
          board.when(
            loading: () => const Padding(padding: EdgeInsets.all(40), child: Center(child: CircularProgressIndicator())),
            error: (e, _) => AppErrorBanner(message: friendlyErrorMessage(e)),
            data: (rows) {
              if (rows.isEmpty) {
                return const Padding(
                  padding: EdgeInsets.only(top: 24),
                  child: AppEmptyState(
                    icon: Icons.campaign_outlined,
                    title: 'No notices for you right now',
                    subtitle: 'When the committee posts a notice meant for you, it appears here.',
                  ),
                );
              }
              final waiting = rows.where((n) => n.needsAck).length;
              return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                if (waiting > 0)
                  Container(
                    margin: const EdgeInsets.only(bottom: 12),
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(color: AppTheme.warningSoft, borderRadius: BorderRadius.circular(AppTheme.radiusM)),
                    child: Row(children: [
                      const Icon(Icons.mark_email_unread_outlined, color: AppTheme.warning),
                      const SizedBox(width: 10),
                      Expanded(child: Text(waiting == 1 ? '1 notice is waiting for you to confirm you have read it' : '$waiting notices are waiting for you to confirm you have read them',
                          style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 13.5))),
                    ]),
                  ),
                for (final n in rows) NoticeCard(notice: n, onTap: () => context.push(noticeRoute(n.id))),
              ]);
            },
          ),
        ]),
      ),
    );
  }
}

class _AlertCard extends ConsumerWidget {
  final EmergencyAlertItem alert;
  final bool canEnd;
  const _AlertCard({required this.alert, required this.canEnd});

  Future<void> _end(BuildContext context, WidgetRef ref) async {
    final notes = TextEditingController();
    final ok = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: Text('End “${alert.title}”?'),
        content: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
          const Text('The red bar goes away for everyone.'),
          const SizedBox(height: 12),
          TextField(controller: notes, decoration: const InputDecoration(labelText: 'What happened (optional)')),
        ]),
        actions: [
          TextButton(onPressed: () => Navigator.of(dialogContext).pop(false), child: const Text('Keep it')),
          FilledButton(onPressed: () => Navigator.of(dialogContext).pop(true), child: const Text('End alert')),
        ],
      ),
    );
    final text = notes.text.trim();
    notes.dispose();
    if (ok != true) return;
    try {
      await ref.read(noticesApiProvider).resolveAlert(alert.id, notes: text);
      invalidateNotices(ref);
    } catch (e) {
      if (context.mounted) showErrorToast(context, e);
    }
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) => Card(
        color: AppTheme.error.withOpacity(0.08),
        margin: const EdgeInsets.only(bottom: 12),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(AppTheme.radiusM), side: const BorderSide(color: AppTheme.error)),
        child: Padding(
          padding: const EdgeInsets.all(14),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Row(children: [
              Icon(alertTypeIcon(alert.type), color: AppTheme.error),
              const SizedBox(width: 10),
              Expanded(child: Text(alert.title, style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 15.5, color: AppTheme.error))),
            ]),
            const SizedBox(height: 6),
            Text(
              [
                alertTypeLabel(alert.type),
                if ((alert.location ?? '').isNotEmpty) alert.location!,
                'raised ${clockTime(alert.triggeredAt)}${alert.triggeredBy == null ? '' : ' by ${alert.triggeredBy}'}',
              ].join(' · '),
              style: const TextStyle(fontSize: 12.5, color: AppTheme.textSecondary),
            ),
            if ((alert.description ?? '').isNotEmpty) ...[
              const SizedBox(height: 8),
              Text(alert.description!, style: const TextStyle(fontSize: 14, height: 1.4)),
            ],
            if (canEnd) ...[
              const SizedBox(height: 10),
              OutlinedButton(onPressed: () => _end(context, ref), child: const Text('End this alert')),
            ],
          ]),
        ),
      );
}

/// One notice in a list: how important, what it is about, a few lines, and whether it needs the reader.
class NoticeCard extends StatelessWidget {
  final NoticeItem notice;
  final VoidCallback onTap;
  final bool manage;
  const NoticeCard({super.key, required this.notice, required this.onTap, this.manage = false});

  @override
  Widget build(BuildContext context) {
    final n = notice;
    final color = noticePriorityColor(n.priority);
    return Card(
      margin: const EdgeInsets.only(bottom: 10),
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: onTap,
        child: IntrinsicHeight(
          child: Row(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
            Container(width: n.priority == 'normal' || n.priority == 'low' ? 0 : 5, color: color),
            Expanded(
              child: Padding(
                padding: const EdgeInsets.all(14),
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Row(children: [
                    Icon(noticeCategoryIcon(n.category), size: 16, color: AppTheme.textSecondary),
                    const SizedBox(width: 6),
                    Text(noticeCategoryLabel(n.category), style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
                    const SizedBox(width: 8),
                    if (n.priority == 'urgent' || n.priority == 'high') StatusPill(noticePriorityLabel(n.priority), color),
                    const Spacer(),
                    Text(noticeDay(n.publishDate ?? n.createdAt), style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
                  ]),
                  const SizedBox(height: 6),
                  Text(n.title, style: const TextStyle(fontSize: 15.5, fontWeight: FontWeight.w700)),
                  const SizedBox(height: 4),
                  Text(n.content, maxLines: 3, overflow: TextOverflow.ellipsis,
                      style: const TextStyle(fontSize: 13.5, color: AppTheme.textSecondary, height: 1.35)),
                  const SizedBox(height: 8),
                  Wrap(spacing: 8, runSpacing: 4, crossAxisAlignment: WrapCrossAlignment.center, children: [
                    if (manage) StatusPill(n.isDraft ? 'Draft' : (n.isPublished ? (n.isExpired ? 'Expired' : 'Published') : 'Archived'),
                        n.isDraft ? AppTheme.warning : (n.isPublished && !n.isExpired ? AppTheme.success : AppTheme.textSecondary)),
                    if (manage) Text(audienceLabel(n.audience), style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
                    if (manage && n.isPublished)
                      Text(n.ackRequired ? '${n.ackCount} of ${n.totalAudience} confirmed' : '${n.totalAudience} reached',
                          style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
                    if (!manage && n.needsAck) const StatusPill('Please confirm you have read this', AppTheme.warning),
                    if (!manage && n.ackRequired && n.acknowledged == true) const StatusPill('You have read this', AppTheme.success),
                  ]),
                ]),
              ),
            ),
          ]),
        ),
      ),
    );
  }
}

// ── Manage (committee) ───────────────────────────────────────────────────────

class _Manage extends ConsumerStatefulWidget {
  final String societyId;
  const _Manage({required this.societyId});

  @override
  ConsumerState<_Manage> createState() => _ManageState();
}

class _ManageState extends ConsumerState<_Manage> {
  String? _status;

  @override
  Widget build(BuildContext context) {
    final rows = ref.watch(noticeManageProvider((societyId: widget.societyId, status: _status)));
    return RefreshIndicator(
      onRefresh: () async => invalidateNotices(ref),
      child: ResponsiveBody(
        maxWidth: 820,
        child: ListView(padding: const EdgeInsets.fromLTRB(16, 16, 16, 96), children: [
          Wrap(spacing: 8, children: [
            for (final f in const [(null, 'All'), ('draft', 'Drafts'), ('published', 'Published'), ('archived', 'Archived')])
              ChoiceChip(label: Text(f.$2), selected: _status == f.$1, onSelected: (_) => setState(() => _status = f.$1)),
          ]),
          const SizedBox(height: 12),
          rows.when(
            loading: () => const Padding(padding: EdgeInsets.all(40), child: Center(child: CircularProgressIndicator())),
            error: (e, _) => AppErrorBanner(message: friendlyErrorMessage(e)),
            data: (list) => list.isEmpty
                ? const Padding(
                    padding: EdgeInsets.only(top: 24),
                    child: AppEmptyState(
                      icon: Icons.edit_note_rounded,
                      title: 'No notices here yet',
                      subtitle: 'Press “New notice” to write one. It stays a draft until you publish it.',
                    ),
                  )
                : Column(children: [for (final n in list) NoticeCard(notice: n, manage: true, onTap: () => context.push(noticeRoute(n.id)))]),
          ),
        ]),
      ),
    );
  }
}
