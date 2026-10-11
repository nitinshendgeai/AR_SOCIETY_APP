import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/motion/loading.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/accounts/data/accounts_api.dart';
import 'package:ar_society_app/features/accounts/presentation/providers/accounts_providers.dart';
import 'package:ar_society_app/features/accounts/presentation/widgets/accounts_widgets.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/shared/widgets/app_form.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';

/// Payments and journals wait here until the admin or a committee member approves them; only then do they count in
/// the books. Whoever entered a voucher does not approve it themselves (unless nobody else could).
class ApprovalsScreen extends ConsumerStatefulWidget {
  const ApprovalsScreen({super.key});

  @override
  ConsumerState<ApprovalsScreen> createState() => _ApprovalsScreenState();
}

class _ApprovalsScreenState extends ConsumerState<ApprovalsScreen> {
  String? _busyId;

  Future<void> _approve(Voucher v) async {
    setState(() => _busyId = v.id);
    try {
      await ref.read(accountsApiProvider).approveVoucher(v.id);
      invalidateBooks(ref);
      if (mounted) AppToast.success(context, '${v.voucherNumber} approved');
    } catch (e) {
      if (mounted) showErrorToast(context, e);
    } finally {
      if (mounted) setState(() => _busyId = null);
    }
  }

  Future<void> _reject(Voucher v) async {
    final reason = TextEditingController();
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text('Reject ${v.voucherNumber}?'),
        content: Column(mainAxisSize: MainAxisSize.min, children: [
          const Text('It stays on record as rejected and never counts in the books. Say why, so the person who entered it can correct it.',
              style: TextStyle(fontSize: 13, color: AppTheme.textSecondary)),
          const SizedBox(height: 12),
          FormFieldBox(label: 'Reason', required: true, child: TextField(controller: reason, maxLines: 2)),
        ]),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancel')),
          FilledButton(
            style: FilledButton.styleFrom(backgroundColor: AppTheme.error),
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('Reject'),
          ),
        ],
      ),
    );
    if (ok != true) return;
    if (reason.text.trim().length < 3) {
      if (mounted) showErrorToast(context, Exception('Give a reason for rejecting'));
      return;
    }
    setState(() => _busyId = v.id);
    try {
      await ref.read(accountsApiProvider).rejectVoucher(v.id, reason.text.trim());
      invalidateBooks(ref);
      if (mounted) AppToast.success(context, '${v.voucherNumber} rejected');
    } catch (e) {
      if (mounted) showErrorToast(context, e);
    } finally {
      if (mounted) setState(() => _busyId = null);
    }
  }

  @override
  Widget build(BuildContext context) {
    final user = ref.watch(currentUserProvider);
    final societyId = user?.societyId ?? '';
    final mayApprove = user?.isAdminOrCommittee ?? false;
    final async = ref.watch(pendingApprovalsProvider(societyId));

    return AppPage(
      title: 'Approvals',
      subtitle: 'Payments and journals wait here until the admin or committee approves them',
      maxWidth: 960,
      body: RefreshIndicator(
        onRefresh: () async => ref.invalidate(pendingApprovalsProvider(societyId)),
        child: async.when(
          loading: () => const AppLoader(),
          error: (e, _) => ListView(padding: const EdgeInsets.all(24), children: [
            Text(friendlyErrorMessage(e), style: const TextStyle(color: AppTheme.error)),
          ]),
          data: (rows) => rows.isEmpty
              ? ListView(children: const [
                  SizedBox(height: 60),
                  AppEmptyState(
                      icon: Icons.fact_check_outlined,
                      title: 'Nothing is waiting for approval',
                      subtitle: 'A payment or journal you enter shows here until it is approved.'),
                ])
              : ListView(
                  padding: const EdgeInsets.fromLTRB(16, 12, 16, 96),
                  children: [
                    for (final v in rows) ...[
                      _ApprovalCard(
                        voucher: v,
                        mayApprove: mayApprove,
                        busy: _busyId == v.id,
                        onApprove: () => _approve(v),
                        onReject: () => _reject(v),
                        onOpen: () => showVoucherSheet(context, v.id),
                      ),
                      const SizedBox(height: 12),
                    ],
                  ],
                ),
        ),
      ),
    );
  }
}

class _ApprovalCard extends StatelessWidget {
  final Voucher voucher;
  final bool mayApprove;
  final bool busy;
  final VoidCallback onApprove;
  final VoidCallback onReject;
  final VoidCallback onOpen;
  const _ApprovalCard(
      {required this.voucher,
      required this.mayApprove,
      required this.busy,
      required this.onApprove,
      required this.onReject,
      required this.onOpen});

  @override
  Widget build(BuildContext context) {
    final v = voucher;
    final lines = [
      for (final e in v.entries)
        '${e.debit > 0 ? 'Dr' : 'Cr'} ${e.accountName ?? ''}${e.flatLabel == null ? '' : ' — ${e.flatLabel}'}  ${formatInr(e.debit > 0 ? e.debit : e.credit)}',
    ];
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(color: AppTheme.cardBg, borderRadius: BorderRadius.circular(AppTheme.radiusM)),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        InkWell(
          onTap: onOpen,
          child: Row(children: [
            VoucherTypeChip(v.voucherType),
            const SizedBox(width: 8),
            Expanded(child: Text(v.voucherNumber, style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w700))),
            Text(formatInr(v.amount), style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w700)),
          ]),
        ),
        const SizedBox(height: 6),
        Text(
            '${formatAccountsDate(v.voucherDate)} · Entered by ${v.createdByName ?? '—'}'
            '${(v.vendorName ?? '').isEmpty ? '' : ' · Paid to ${v.vendorName}'}',
            style: const TextStyle(fontSize: 12.5, color: AppTheme.textSecondary)),
        if ((v.narration ?? '').isNotEmpty) ...[
          const SizedBox(height: 6),
          Text(v.narration!, style: const TextStyle(fontSize: 13.5)),
        ],
        const SizedBox(height: 8),
        for (final l in lines) Text(l, style: const TextStyle(fontSize: 12.5, color: AppTheme.textSecondary)),
        if ((v.reference ?? '').isNotEmpty)
          Padding(
            padding: const EdgeInsets.only(top: 4),
            child: Text('Reference ${v.reference}', style: const TextStyle(fontSize: 12.5, color: AppTheme.textSecondary)),
          ),
        const SizedBox(height: 12),
        if (!mayApprove)
          const Text('Waiting for the admin or a committee member.',
              style: TextStyle(fontSize: 12.5, color: AppTheme.textSecondary))
        else if (!v.canApprove)
          const Text('You entered this one, so another admin or committee member has to approve it.',
              style: TextStyle(fontSize: 12.5, color: AppTheme.textSecondary))
        else
          Wrap(spacing: 10, runSpacing: 8, children: [
            FilledButton.icon(
              onPressed: busy ? null : onApprove,
              icon: const Icon(Icons.check_rounded, size: 18),
              label: const Text('Approve'),
              style: FilledButton.styleFrom(minimumSize: const Size(0, 44)),
            ),
            OutlinedButton.icon(
              onPressed: busy ? null : onReject,
              icon: const Icon(Icons.close_rounded, size: 18),
              label: const Text('Reject'),
              style: OutlinedButton.styleFrom(
                  foregroundColor: AppTheme.error, minimumSize: const Size(0, 44), side: const BorderSide(color: AppTheme.error)),
            ),
          ]),
      ]),
    );
  }
}
