import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/users/data/models/user_admin_models.dart';
import 'package:ar_society_app/features/users/presentation/providers/user_providers.dart';
import 'package:ar_society_app/features/staff/presentation/widgets/staff_widgets.dart' show EmptyState;
import 'package:ar_society_app/shared/widgets/app_widgets.dart';

/// Members who tapped "Forgot password?" on the login screen. The admin
/// resets the password here and gives the member the temporary one (they
/// must change it at their next sign-in), or dismisses the request.
class PasswordResetRequestsScreen extends ConsumerWidget {
  const PasswordResetRequestsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return DefaultTabController(
      length: 2,
      child: Scaffold(
        backgroundColor: AppTheme.surface,
        appBar: AppBar(
          title: const Text('Password Reset Requests'),
          bottom: const TabBar(tabs: [Tab(text: 'Pending'), Tab(text: 'Handled')]),
          actions: [
            IconButton(
              icon: const Icon(Icons.refresh_rounded),
              tooltip: 'Refresh',
              onPressed: () => ref.invalidate(passwordResetRequestsProvider),
            ),
          ],
        ),
        body: const TabBarView(children: [
          _RequestList(pending: true),
          _RequestList(pending: false),
        ]),
      ),
    );
  }
}

class _RequestList extends ConsumerWidget {
  final bool pending;
  const _RequestList({required this.pending});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final requests = ref.watch(passwordResetRequestsProvider(pending ? 'pending' : 'all'));
    return requests.when(
      loading: () => const Center(child: CircularProgressIndicator()),
      error: (e, _) => Center(
        child: Text(friendlyErrorMessage(e), style: const TextStyle(color: AppTheme.error)),
      ),
      data: (all) {
        final list = pending ? all : all.where((r) => !r.isPending).toList();
        if (list.isEmpty) {
          return EmptyState(
            icon: pending ? Icons.lock_reset_rounded : Icons.history_rounded,
            title: pending ? 'No pending requests' : 'Nothing handled yet',
            subtitle: pending
                ? 'Members who tap "Forgot password?" on the login screen appear here'
                : null,
          );
        }
        return RefreshIndicator(
          onRefresh: () async => ref.invalidate(passwordResetRequestsProvider),
          child: ListView.separated(
            padding: const EdgeInsets.all(16),
            itemCount: list.length,
            separatorBuilder: (_, __) => const SizedBox(height: 12),
            itemBuilder: (_, i) => _RequestCard(request: list[i]),
          ),
        );
      },
    );
  }
}

class _RequestCard extends ConsumerStatefulWidget {
  final PasswordResetRequestModel request;
  const _RequestCard({required this.request});

  @override
  ConsumerState<_RequestCard> createState() => _RequestCardState();
}

class _RequestCardState extends ConsumerState<_RequestCard> {
  bool _busy = false;
  static final _when = DateFormat('d MMM, h:mm a');

  PasswordResetRequestModel get r => widget.request;

  Future<void> _reset() async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Reset password?'),
        content: Text('A temporary password is created for ${r.fullName}. '
            'Give it to them only after confirming it is really them (in person or by a call '
            'to their registered mobile). They must set a new password when they sign in.'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancel')),
          ElevatedButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('Reset')),
        ],
      ),
    );
    if (ok != true) return;
    setState(() => _busy = true);
    try {
      final result = await ref.read(userAdminRepoProvider).resolveResetRequest(r.id);
      ref.invalidate(passwordResetRequestsProvider);
      if (mounted) await _showTemporaryPassword(result.temporaryPassword);
    } catch (e) {
      if (mounted) showErrorToast(context, e);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _dismiss() async {
    setState(() => _busy = true);
    try {
      await ref.read(userAdminRepoProvider).dismissResetRequest(r.id);
      ref.invalidate(passwordResetRequestsProvider);
      if (mounted) AppToast.success(context, 'Request dismissed');
    } catch (e) {
      if (mounted) showErrorToast(context, e);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _showTemporaryPassword(String password) {
    final signInWith = r.contact?.split(' · ').first ?? r.identifier;
    final message = 'Your DUX OS password has been reset. Sign in with $signInWith and the '
        'temporary password $password — you will be asked to set a new password.';
    void copy(String text, String what) {
      Clipboard.setData(ClipboardData(text: text));
      AppToast.success(context, '$what copied');
    }

    return showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Temporary password'),
        content: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text('Give this to ${r.fullName}. It works once — they must set a new password when they sign in.',
              style: const TextStyle(fontSize: 13, color: AppTheme.textSecondary)),
          const SizedBox(height: 12),
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: AppTheme.surface,
              borderRadius: BorderRadius.circular(8),
              border: Border.all(color: AppTheme.border),
            ),
            child: SelectableText(password,
                style: const TextStyle(fontFamily: 'monospace', fontWeight: FontWeight.w700, fontSize: 18)),
          ),
        ]),
        actions: [
          TextButton.icon(
            onPressed: () => copy(message, 'Message'),
            icon: const Icon(Icons.message_rounded, size: 18),
            label: const Text('Copy message'),
          ),
          TextButton.icon(
            onPressed: () => copy(password, 'Password'),
            icon: const Icon(Icons.copy_rounded, size: 18),
            label: const Text('Copy password'),
          ),
          ElevatedButton(onPressed: () => Navigator.pop(ctx), child: const Text('Done')),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final details = [
      if (r.contact != null) r.contact!,
      ...r.flats,
      ...r.roles,
    ].join('  ·  ');
    final Color statusColor = switch (r.status) {
      'completed' => AppTheme.success,
      'dismissed' => AppTheme.textSecondary,
      _ => AppTheme.warning,
    };
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: AppTheme.cardBg,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: AppTheme.border),
      ),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          CircleAvatar(
            radius: 18,
            backgroundColor: statusColor.withValues(alpha: 0.12),
            child: Icon(Icons.lock_reset_rounded, size: 20, color: statusColor),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text(r.fullName, style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w700)),
              if (details.isNotEmpty)
                Text(details, style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
            ]),
          ),
          if (!r.isPending)
            Text(r.status == 'completed' ? 'Reset' : 'Dismissed',
                style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: statusColor)),
        ]),
        const SizedBox(height: 8),
        Text(
          r.isPending
              ? 'Asked ${_when.format(r.lastAskedAt.toLocal())}'
                  '${r.lastAskedAt.difference(r.requestedAt).inMinutes > 1 ? ' (first asked ${_when.format(r.requestedAt.toLocal())})' : ''}'
              : '${r.status == 'completed' ? 'Reset' : 'Dismissed'} by ${r.resolvedBy ?? '—'}'
                  '${r.resolvedAt != null ? ' · ${_when.format(r.resolvedAt!.toLocal())}' : ''}',
          style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary),
        ),
        if (r.isPending) ...[
          const SizedBox(height: 12),
          Row(children: [
            Expanded(
              child: OutlinedButton(
                onPressed: _busy ? null : _dismiss,
                child: const Text('Dismiss'),
              ),
            ),
            const SizedBox(width: 10),
            Expanded(
              child: ElevatedButton.icon(
                onPressed: _busy ? null : _reset,
                icon: const Icon(Icons.lock_reset_rounded, size: 18),
                label: const Text('Reset password'),
              ),
            ),
          ]),
        ],
      ]),
    );
  }
}
