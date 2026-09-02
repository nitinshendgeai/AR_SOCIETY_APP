import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/staff/domain/entities/staff_entities.dart';
import 'package:ar_society_app/features/staff/presentation/providers/staff_providers.dart';
import 'package:ar_society_app/features/staff/presentation/widgets/staff_widgets.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';

/// Manager/Admin/Committee review screen for staff attendance-correction
/// requests raised from the Attendance screen. Mirrors AttendanceApprovalScreen's
/// approve/reject pattern, but for corrections to already-recorded attendance
/// (wrong status/times) rather than pending check-in/check-out.
class AttendanceCorrectionScreen extends ConsumerStatefulWidget {
  final String societyId;
  const AttendanceCorrectionScreen({super.key, required this.societyId});

  @override
  ConsumerState<AttendanceCorrectionScreen> createState() =>
      _AttendanceCorrectionScreenState();
}

class _AttendanceCorrectionScreenState
    extends ConsumerState<AttendanceCorrectionScreen> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _load());
  }

  Future<void> _load() => ref.read(correctionProvider.notifier).loadForSociety(widget.societyId);

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(correctionProvider);

    ref.listen(correctionProvider, (_, next) {
      if (next is CorrectionActionSuccess) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(
          content: Text(next.message),
          backgroundColor: AppTheme.success,
          behavior: SnackBarBehavior.floating,
        ));
      } else if (next is CorrectionError) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(
          content: Text(next.message),
          backgroundColor: AppTheme.error,
          behavior: SnackBarBehavior.floating,
        ));
      }
    });

    final corrections = switch (state) {
      CorrectionLoaded(:final corrections) => corrections,
      CorrectionActionSuccess(:final corrections) => corrections,
      _ => <AttendanceCorrectionEntity>[],
    };
    final pending  = corrections.where((c) => c.status == CorrectionStatus.pending).toList();
    final resolved = corrections.where((c) => c.status != CorrectionStatus.pending).toList();

    return Scaffold(
      backgroundColor: AppTheme.surface,
      appBar: AppBar(
        title: const Text('Attendance Corrections'),
        actions: [
          IconButton(icon: const Icon(Icons.refresh_rounded), onPressed: _load),
        ],
      ),
      body: switch (state) {
        CorrectionLoading() || CorrectionInitial() =>
          const Center(child: CircularProgressIndicator(color: AppTheme.primary)),
        CorrectionError(:final message) => Center(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  AppErrorBanner(message: message),
                  const SizedBox(height: 12),
                  TextButton(onPressed: _load, child: const Text('Retry')),
                ],
              ),
            ),
          ),
        _ => corrections.isEmpty
            ? const EmptyState(
                icon: Icons.edit_note_rounded,
                title: 'No correction requests',
                subtitle: 'Requests from staff will show up here for review',
              )
            : RefreshIndicator(
                onRefresh: _load,
                child: ListView(
                  padding: const EdgeInsets.all(16),
                  children: [
                    if (pending.isNotEmpty) ...[
                      const SectionHeader(title: 'Pending'),
                      const SizedBox(height: 10),
                      ...pending.map((c) => Padding(
                            padding: const EdgeInsets.only(bottom: 10),
                            child: _CorrectionReviewCard(correction: c, societyId: widget.societyId),
                          )),
                      const SizedBox(height: 16),
                    ],
                    if (resolved.isNotEmpty) ...[
                      const SectionHeader(title: 'Resolved'),
                      const SizedBox(height: 10),
                      ...resolved.map((c) => Padding(
                            padding: const EdgeInsets.only(bottom: 10),
                            child: _CorrectionReviewCard(correction: c, societyId: widget.societyId),
                          )),
                    ],
                  ],
                ),
              ),
      },
    );
  }
}

class _CorrectionReviewCard extends ConsumerWidget {
  final AttendanceCorrectionEntity correction;
  final String societyId;
  const _CorrectionReviewCard({required this.correction, required this.societyId});

  Color _statusColor() {
    switch (correction.status) {
      case CorrectionStatus.pending:  return AppTheme.warning;
      case CorrectionStatus.approved: return AppTheme.success;
      case CorrectionStatus.rejected: return AppTheme.error;
    }
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final isLoading = ref.watch(correctionProvider) is CorrectionLoading;

    return AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  correction.staffName ?? 'Staff #${correction.staffId.substring(0, correction.staffId.length.clamp(0, 8))}',
                  style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 13, color: AppTheme.textPrimary),
                ),
              ),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                decoration: BoxDecoration(
                  color: _statusColor().withOpacity(0.12),
                  borderRadius: BorderRadius.circular(20),
                  border: Border.all(color: _statusColor().withOpacity(0.3)),
                ),
                child: Text(correction.status.label,
                    style: TextStyle(color: _statusColor(), fontSize: 12, fontWeight: FontWeight.w600)),
              ),
            ],
          ),
          const SizedBox(height: 4),
          Text(formatDate(correction.correctionDate),
              style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
          const SizedBox(height: 10),
          if (correction.originalStatus != correction.requestedStatus &&
              correction.requestedStatus != null)
            InfoRow(
              icon: Icons.compare_arrows_rounded,
              label: 'Status',
              value: '${correction.originalStatus ?? '--'} → ${correction.requestedStatus}',
            ),
          if (correction.requestedCheckIn != null)
            InfoRow(
              icon: Icons.login_rounded,
              label: 'Check-in',
              value: '${correction.originalCheckIn ?? '--'} → ${correction.requestedCheckIn}',
            ),
          if (correction.requestedCheckOut != null)
            InfoRow(
              icon: Icons.logout_rounded,
              label: 'Check-out',
              value: '${correction.originalCheckOut ?? '--'} → ${correction.requestedCheckOut}',
            ),
          const SizedBox(height: 6),
          Text(correction.reason,
              style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary, fontStyle: FontStyle.italic)),
          if (correction.status == CorrectionStatus.rejected && correction.rejectionReason != null) ...[
            const SizedBox(height: 6),
            Text('Rejected: ${correction.rejectionReason}',
                style: const TextStyle(fontSize: 12, color: AppTheme.error)),
          ],
          if (correction.isPending) ...[
            const SizedBox(height: 12),
            Row(
              mainAxisAlignment: MainAxisAlignment.end,
              children: [
                OutlinedButton(
                  onPressed: isLoading ? null : () => _showRejectDialog(context, ref),
                  style: OutlinedButton.styleFrom(
                    foregroundColor: AppTheme.error,
                    side: BorderSide(color: AppTheme.error.withOpacity(0.5)),
                  ),
                  child: const Text('Reject'),
                ),
                const SizedBox(width: 8),
                ElevatedButton(
                  onPressed: isLoading
                      ? null
                      : () => ref.read(correctionProvider.notifier).approve(correction.id, societyId),
                  style: ElevatedButton.styleFrom(backgroundColor: AppTheme.success),
                  child: isLoading
                      ? const SizedBox(
                          width: 14, height: 14,
                          child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                      : const Text('Approve'),
                ),
              ],
            ),
          ],
        ],
      ),
    );
  }

  void _showRejectDialog(BuildContext context, WidgetRef ref) {
    final reasonCtrl = TextEditingController();
    final formKey = GlobalKey<FormState>();
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Reject Correction?'),
        content: Form(
          key: formKey,
          child: TextFormField(
            controller: reasonCtrl,
            maxLines: 3,
            autofocus: true,
            decoration: const InputDecoration(labelText: 'Reason *'),
            validator: (v) => (v == null || v.trim().isEmpty) ? 'Required' : null,
          ),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Cancel')),
          ElevatedButton(
            style: ElevatedButton.styleFrom(backgroundColor: AppTheme.error),
            onPressed: () {
              if (!(formKey.currentState?.validate() ?? true)) return;
              Navigator.pop(ctx);
              ref.read(correctionProvider.notifier)
                  .reject(correction.id, societyId, reasonCtrl.text.trim());
            },
            child: const Text('Reject', style: TextStyle(color: Colors.white)),
          ),
        ],
      ),
    );
  }
}
