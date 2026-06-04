import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/complaint/domain/entities/complaint_entities.dart';
import 'package:ar_society_app/features/complaint/presentation/providers/complaint_providers.dart';
import 'package:ar_society_app/features/staff/presentation/widgets/staff_widgets.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';

// ── Status badge ──────────────────────────────────────────────────────────────

class _StatusBadge extends StatelessWidget {
  final ComplaintStatus status;
  const _StatusBadge(this.status);

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: status.color.withOpacity(0.12),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: status.color.withOpacity(0.3)),
      ),
      child: Text(
        status.label,
        style: TextStyle(
          color: status.color,
          fontSize: 12,
          fontWeight: FontWeight.w600,
        ),
      ),
    );
  }
}

// ── Priority badge ────────────────────────────────────────────────────────────

class _PriorityBadge extends StatelessWidget {
  final ComplaintPriority priority;
  const _PriorityBadge(this.priority);

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: priority.color.withOpacity(0.10),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: priority.color.withOpacity(0.3)),
      ),
      child: Text(
        priority.label,
        style: TextStyle(
          color: priority.color,
          fontSize: 12,
          fontWeight: FontWeight.w600,
        ),
      ),
    );
  }
}

// ── Comment tile ──────────────────────────────────────────────────────────────

class _CommentTile extends StatelessWidget {
  final ComplaintCommentEntity comment;
  const _CommentTile({required this.comment});

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: comment.isInternal
            ? AppTheme.warning.withOpacity(0.05)
            : AppTheme.surface,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(
          color: comment.isInternal
              ? AppTheme.warning.withOpacity(0.2)
              : AppTheme.border,
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.account_circle_outlined,
                  size: 16, color: AppTheme.textSecondary),
              const SizedBox(width: 4),
              Text(
                comment.authorId,
                style: const TextStyle(
                  fontSize: 12,
                  fontWeight: FontWeight.w600,
                  color: AppTheme.textSecondary,
                ),
              ),
              const Spacer(),
              if (comment.isInternal)
                Container(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                  decoration: BoxDecoration(
                    color: AppTheme.warning.withOpacity(0.1),
                    borderRadius: BorderRadius.circular(4),
                  ),
                  child: const Text(
                    'Internal',
                    style: TextStyle(
                      fontSize: 10,
                      color: AppTheme.warning,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ),
              const SizedBox(width: 4),
              Text(
                _formatDate(comment.createdAt),
                style: const TextStyle(
                  fontSize: 11,
                  color: AppTheme.textSecondary,
                ),
              ),
            ],
          ),
          const SizedBox(height: 6),
          Text(
            comment.body,
            style: const TextStyle(
              fontSize: 13,
              color: AppTheme.textPrimary,
              height: 1.4,
            ),
          ),
        ],
      ),
    );
  }

  String _formatDate(DateTime dt) {
    const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                    'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    return '${dt.day} ${months[dt.month - 1]}, ${dt.hour.toString().padLeft(2, '0')}:${dt.minute.toString().padLeft(2, '0')}';
  }
}

// ── Complaint detail screen ───────────────────────────────────────────────────

class ComplaintDetailScreen extends ConsumerStatefulWidget {
  final String complaintId;

  const ComplaintDetailScreen({super.key, required this.complaintId});

  @override
  ConsumerState<ComplaintDetailScreen> createState() =>
      _ComplaintDetailScreenState();
}

class _ComplaintDetailScreenState
    extends ConsumerState<ComplaintDetailScreen> {
  final _commentCtrl = TextEditingController();
  bool _isSendingComment = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      ref.read(complaintDetailProvider.notifier).load(widget.complaintId);
    });
  }

  @override
  void dispose() {
    _commentCtrl.dispose();
    super.dispose();
  }

  Future<void> _sendComment() async {
    final body = _commentCtrl.text.trim();
    if (body.isEmpty) return;
    setState(() => _isSendingComment = true);
    await ref
        .read(complaintDetailProvider.notifier)
        .addComment(widget.complaintId, body);
    setState(() => _isSendingComment = false);
    _commentCtrl.clear();
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(complaintDetailProvider);

    ref.listen(complaintDetailProvider, (_, next) {
      if (next is ComplaintDetailActionSuccess) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(
          content: Text(next.message),
          backgroundColor: AppTheme.success,
          behavior: SnackBarBehavior.floating,
        ));
        ref.read(complaintDetailProvider.notifier).clearActionStatus();
      } else if (next is ComplaintDetailError) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(
          content: Text(next.message),
          backgroundColor: AppTheme.error,
          behavior: SnackBarBehavior.floating,
        ));
      }
    });

    return Scaffold(
      backgroundColor: AppTheme.surface,
      appBar: AppBar(
        title: const Text('Complaint Detail'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh_rounded),
            onPressed: () => ref
                .read(complaintDetailProvider.notifier)
                .load(widget.complaintId),
          ),
        ],
      ),
      body: _buildBody(state),
    );
  }

  Widget _buildBody(ComplaintDetailState state) {
    if (state is ComplaintDetailLoading) {
      return const Center(
        child: CircularProgressIndicator(color: AppTheme.primary),
      );
    }
    if (state is ComplaintDetailError) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              AppErrorBanner(message: state.message),
              const SizedBox(height: 12),
              TextButton(
                onPressed: () => ref
                    .read(complaintDetailProvider.notifier)
                    .load(widget.complaintId),
                child: const Text('Retry'),
              ),
            ],
          ),
        ),
      );
    }

    ComplaintEntity? complaint;
    if (state is ComplaintDetailLoaded) complaint = state.complaint;
    if (state is ComplaintDetailActionSuccess) complaint = state.complaint;
    if (complaint == null) return const SizedBox.shrink();

    return Column(
      children: [
        Expanded(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // Header card
                AppCard(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Text(
                            '#${complaint.complaintNumber}',
                            style: const TextStyle(
                              fontSize: 13,
                              fontWeight: FontWeight.w700,
                              color: AppTheme.primary,
                            ),
                          ),
                          const Spacer(),
                          _StatusBadge(complaint.status),
                        ],
                      ),
                      const SizedBox(height: 8),
                      Text(
                        complaint.title,
                        style: const TextStyle(
                          fontSize: 17,
                          fontWeight: FontWeight.w700,
                          color: AppTheme.textPrimary,
                        ),
                      ),
                      const SizedBox(height: 10),
                      Wrap(
                        spacing: 8,
                        runSpacing: 6,
                        children: [
                          _PriorityBadge(complaint.priority),
                          Container(
                            padding: const EdgeInsets.symmetric(
                                horizontal: 8, vertical: 4),
                            decoration: BoxDecoration(
                              color: AppTheme.border,
                              borderRadius: BorderRadius.circular(8),
                            ),
                            child: Text(
                              complaint.category.label,
                              style: const TextStyle(
                                fontSize: 12,
                                color: AppTheme.textSecondary,
                                fontWeight: FontWeight.w500,
                              ),
                            ),
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 12),

                // Description card
                AppCard(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const SectionHeader(title: 'Description'),
                      const SizedBox(height: 10),
                      Text(
                        complaint.description,
                        style: const TextStyle(
                          fontSize: 13,
                          color: AppTheme.textPrimary,
                          height: 1.5,
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 12),

                // Details card
                AppCard(
                  child: Column(
                    children: [
                      InfoRow(
                        icon: Icons.person_outline_rounded,
                        label: 'Raised by',
                        value: complaint.raisedBy,
                      ),
                      if (complaint.assignedTo != null)
                        InfoRow(
                          icon: Icons.assignment_ind_outlined,
                          label: 'Assigned to',
                          value: complaint.assignedTo!,
                        ),
                      InfoRow(
                        icon: Icons.calendar_today_rounded,
                        label: 'Created',
                        value: _formatDate(complaint.createdAt),
                      ),
                      if (complaint.resolvedAt != null)
                        InfoRow(
                          icon: Icons.check_circle_outline_rounded,
                          label: 'Resolved',
                          value: _formatDate(complaint.resolvedAt!),
                          valueColor: AppTheme.success,
                        ),
                      if (complaint.resolutionNotes != null) ...[
                        const Divider(height: 16),
                        Text(
                          'Resolution: ${complaint.resolutionNotes}',
                          style: const TextStyle(
                            fontSize: 13,
                            color: AppTheme.textSecondary,
                            fontStyle: FontStyle.italic,
                          ),
                        ),
                      ],
                      if (complaint.rejectionReason != null) ...[
                        const Divider(height: 16),
                        Text(
                          'Rejection reason: ${complaint.rejectionReason}',
                          style: const TextStyle(
                            fontSize: 13,
                            color: AppTheme.error,
                            fontStyle: FontStyle.italic,
                          ),
                        ),
                      ],
                    ],
                  ),
                ),
                const SizedBox(height: 12),

                // Comments section
                SectionHeader(
                  title: 'Comments (${complaint.comments.length})',
                ),
                const SizedBox(height: 10),
                if (complaint.comments.isEmpty)
                  const Center(
                    child: Padding(
                      padding: EdgeInsets.symmetric(vertical: 16),
                      child: Text(
                        'No comments yet',
                        style: TextStyle(
                          color: AppTheme.textSecondary,
                          fontSize: 13,
                        ),
                      ),
                    ),
                  )
                else
                  ...complaint.comments
                      .map((c) => _CommentTile(comment: c))
                      .toList(),

                const SizedBox(height: 80), // Space for bottom input
              ],
            ),
          ),
        ),

        // Add comment input
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
          decoration: const BoxDecoration(
            color: AppTheme.cardBg,
            border: Border(top: BorderSide(color: AppTheme.border)),
          ),
          child: SafeArea(
            top: false,
            child: Row(
              children: [
                Expanded(
                  child: TextField(
                    controller: _commentCtrl,
                    decoration: const InputDecoration(
                      hintText: 'Add a comment...',
                      contentPadding:
                          EdgeInsets.symmetric(horizontal: 12, vertical: 10),
                    ),
                    maxLines: null,
                    textInputAction: TextInputAction.newline,
                  ),
                ),
                const SizedBox(width: 10),
                _isSendingComment
                    ? const SizedBox(
                        width: 36,
                        height: 36,
                        child: CircularProgressIndicator(
                          strokeWidth: 2.5,
                          color: AppTheme.primary,
                        ),
                      )
                    : IconButton(
                        onPressed: _sendComment,
                        icon: const Icon(Icons.send_rounded),
                        color: AppTheme.primary,
                        style: IconButton.styleFrom(
                          backgroundColor: AppTheme.primary.withOpacity(0.1),
                        ),
                      ),
              ],
            ),
          ),
        ),
      ],
    );
  }

  String _formatDate(DateTime dt) {
    const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                    'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    return '${dt.day} ${months[dt.month - 1]} ${dt.year}';
  }
}
