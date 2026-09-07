import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/features/complaint/domain/entities/complaint_entities.dart';
import 'package:ar_society_app/features/complaint/presentation/providers/complaint_providers.dart';
import 'package:ar_society_app/features/staff/domain/entities/staff_entities.dart';
import 'package:ar_society_app/features/staff/presentation/providers/staff_providers.dart';
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
      // Staff list backs the Assign picker — only fetch it for roles that
      // can actually reach GET /staff/society/{id} (supervisor_above), so a
      // resident opening this screen never fires a 403 in the background.
      final user = ref.read(currentUserProvider);
      final societyId = user?.societyId;
      if (societyId != null && (user!.isAdminOrCommittee || user.isManager)) {
        ref.read(staffListProvider.notifier).load(societyId);
      }
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
                          Expanded(
                            child: Text(
                              _numberWithFlat(complaint),
                              style: const TextStyle(
                                fontSize: 13,
                                fontWeight: FontWeight.w700,
                                color: AppTheme.primary,
                              ),
                              overflow: TextOverflow.ellipsis,
                            ),
                          ),
                          const SizedBox(width: 8),
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

                // Workflow actions — assign / status transitions / reopen,
                // gated by role and the complaint's current status.
                _ActionsBar(complaint: complaint),
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
                          value: complaint.assignedToName ?? complaint.assignedTo!,
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

// ── Workflow actions ─────────────────────────────────────────────────────────
//
// Mirrors the backend's VALID_TRANSITIONS FSM (app/modules/complaint/models/
// complaint.py): Assign is its own flow (POST /assign, picks a staff
// member) offered on OPEN/REOPENED; every other transition goes through
// ComplaintEntity.nextStatuses via the generic status dialog; Reopen is a
// third, separate flow only offered on RESOLVED.

class _ActionsBar extends ConsumerWidget {
  final ComplaintEntity complaint;
  const _ActionsBar({required this.complaint});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final user = ref.watch(currentUserProvider);
    if (user == null) return const SizedBox.shrink();

    final canManageStatus = user.isAdminOrCommittee || user.isStaff || user.isSecurity;
    final canAssign = (user.isAdminOrCommittee || user.isManager) && complaint.status.canAssign;
    final isReassign = complaint.status == ComplaintStatus.assigned;
    final canReopen = complaint.status.canReopen;

    final buttons = <Widget>[
      if (canAssign)
        _ActionChip(
          label: isReassign ? 'Reassign' : 'Assign',
          icon: Icons.assignment_ind_rounded,
          color: AppTheme.secondary,
          onTap: () => _openAssignSheet(context, ref, complaint),
        ),
      if (canManageStatus)
        for (final target in complaint.status.nextStatuses)
          _ActionChip(
            label: _statusActionLabel(target),
            icon: _statusActionIcon(target),
            color: target == ComplaintStatus.rejected ? AppTheme.error : AppTheme.primary,
            onTap: () => _openStatusDialog(context, ref, complaint, target),
          ),
      if (canReopen)
        _ActionChip(
          label: 'Reopen',
          icon: Icons.replay_rounded,
          color: AppTheme.warning,
          onTap: () => _openReopenDialog(context, ref, complaint),
        ),
    ];

    if (buttons.isEmpty) return const SizedBox.shrink();

    return AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const SectionHeader(title: 'Actions'),
          const SizedBox(height: 10),
          Wrap(spacing: 8, runSpacing: 8, children: buttons),
        ],
      ),
    );
  }
}

String _numberWithFlat(ComplaintEntity c) {
  final flat = [
    if (c.wingName != null) c.wingName,
    if (c.flatNumber != null) c.flatNumber,
  ].join(' — ');
  return flat.isEmpty ? '#${c.complaintNumber}' : '#${c.complaintNumber} · $flat';
}

String _statusActionLabel(ComplaintStatus target) {
  switch (target) {
    case ComplaintStatus.inProgress: return 'Start Progress';
    case ComplaintStatus.resolved:   return 'Mark Resolved';
    case ComplaintStatus.rejected:   return 'Reject';
    case ComplaintStatus.closed:     return 'Close';
    default:                         return target.label;
  }
}

IconData _statusActionIcon(ComplaintStatus target) {
  switch (target) {
    case ComplaintStatus.inProgress: return Icons.play_circle_outline_rounded;
    case ComplaintStatus.resolved:   return Icons.check_circle_outline_rounded;
    case ComplaintStatus.rejected:   return Icons.cancel_outlined;
    case ComplaintStatus.closed:     return Icons.lock_outline_rounded;
    default:                         return Icons.arrow_forward_rounded;
  }
}

class _ActionChip extends StatelessWidget {
  final String label;
  final IconData icon;
  final Color color;
  final VoidCallback onTap;
  const _ActionChip({
    required this.label, required this.icon, required this.color, required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return OutlinedButton.icon(
      onPressed: onTap,
      icon: Icon(icon, size: 16, color: color),
      label: Text(label),
      style: OutlinedButton.styleFrom(
        foregroundColor: color,
        side: BorderSide(color: color.withOpacity(0.4)),
      ),
    );
  }
}

/// Generic status-change dialog: a single notes field, required for
/// RESOLVED (resolution_notes) and REJECTED (rejection_reason), optional
/// otherwise, sent to the field POST /status actually expects for that
/// target status.
Future<void> _openStatusDialog(
  BuildContext context, WidgetRef ref, ComplaintEntity complaint, ComplaintStatus target,
) async {
  final requiresNotes = target == ComplaintStatus.resolved || target == ComplaintStatus.rejected;
  final label = target == ComplaintStatus.resolved
      ? 'Resolution notes'
      : target == ComplaintStatus.rejected
          ? 'Rejection reason'
          : 'Notes (optional)';
  final ctrl = TextEditingController();
  final formKey = GlobalKey<FormState>();

  final confirmed = await showDialog<bool>(
    context: context,
    builder: (ctx) => AlertDialog(
      title: Text('${_statusActionLabel(target)} Complaint?'),
      content: Form(
        key: formKey,
        child: TextFormField(
          controller: ctrl,
          maxLines: 3,
          autofocus: requiresNotes,
          decoration: InputDecoration(labelText: requiresNotes ? '$label *' : label),
          validator: requiresNotes
              ? (v) => (v == null || v.trim().isEmpty) ? 'Required' : null
              : null,
        ),
      ),
      actions: [
        TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancel')),
        ElevatedButton(
          style: target == ComplaintStatus.rejected
              ? ElevatedButton.styleFrom(backgroundColor: AppTheme.error)
              : null,
          onPressed: () {
            if (formKey.currentState?.validate() ?? true) Navigator.pop(ctx, true);
          },
          child: Text(_statusActionLabel(target)),
        ),
      ],
    ),
  );
  if (confirmed != true) return;

  final text = ctrl.text.trim().isEmpty ? null : ctrl.text.trim();
  await ref.read(complaintDetailProvider.notifier).updateStatus(
        complaint.id,
        target.value,
        notes: !requiresNotes ? text : null,
        resolutionNotes: target == ComplaintStatus.resolved ? text : null,
        rejectionReason: target == ComplaintStatus.rejected ? text : null,
      );
}

Future<void> _openReopenDialog(
  BuildContext context, WidgetRef ref, ComplaintEntity complaint,
) async {
  final ctrl = TextEditingController();
  final formKey = GlobalKey<FormState>();

  final confirmed = await showDialog<bool>(
    context: context,
    builder: (ctx) => AlertDialog(
      title: const Text('Reopen Complaint?'),
      content: Form(
        key: formKey,
        child: TextFormField(
          controller: ctrl,
          maxLines: 3,
          autofocus: true,
          decoration: const InputDecoration(labelText: 'Reason *'),
          validator: (v) => (v == null || v.trim().isEmpty) ? 'Required' : null,
        ),
      ),
      actions: [
        TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancel')),
        ElevatedButton(
          onPressed: () {
            if (formKey.currentState?.validate() ?? true) Navigator.pop(ctx, true);
          },
          child: const Text('Reopen'),
        ),
      ],
    ),
  );
  if (confirmed != true) return;

  await ref.read(complaintDetailProvider.notifier).reopen(complaint.id, ctrl.text.trim());
}

Future<void> _openAssignSheet(
  BuildContext context, WidgetRef ref, ComplaintEntity complaint,
) {
  return showModalBottomSheet(
    context: context,
    isScrollControlled: true,
    backgroundColor: Colors.transparent,
    constraints: const BoxConstraints(maxWidth: 480),
    builder: (_) => _AssignSheetBody(complaint: complaint),
  );
}

class _AssignSheetBody extends ConsumerStatefulWidget {
  final ComplaintEntity complaint;
  const _AssignSheetBody({required this.complaint});

  @override
  ConsumerState<_AssignSheetBody> createState() => _AssignSheetBodyState();
}

class _AssignSheetBodyState extends ConsumerState<_AssignSheetBody> {
  String? _selectedUserId;
  DateTime? _dueDate;
  final _notesCtrl = TextEditingController();
  bool _submitting = false;

  @override
  void dispose() {
    _notesCtrl.dispose();
    super.dispose();
  }

  Future<void> _pickDueDate() async {
    final now = DateTime.now();
    final picked = await showDatePicker(
      context: context,
      initialDate: now,
      firstDate: now,
      lastDate: now.add(const Duration(days: 365)),
    );
    if (picked != null) setState(() => _dueDate = picked);
  }

  Future<void> _submit() async {
    if (_selectedUserId == null) return;
    setState(() => _submitting = true);
    await ref.read(complaintDetailProvider.notifier).assign(
          widget.complaint.id,
          assignedTo: _selectedUserId!,
          dueDate: _dueDate,
          notes: _notesCtrl.text.trim().isEmpty ? null : _notesCtrl.text.trim(),
        );
    if (mounted) Navigator.pop(context);
  }

  @override
  Widget build(BuildContext context) {
    final staffState = ref.watch(staffListProvider);
    final assignable = staffState is StaffListLoaded
        ? staffState.staff.where((s) => s.userId != null).toList()
        : <StaffEntity>[];
    final isReassign = widget.complaint.status == ComplaintStatus.assigned;

    return Padding(
      padding: EdgeInsets.only(bottom: MediaQuery.of(context).viewInsets.bottom),
      child: Container(
        padding: const EdgeInsets.fromLTRB(20, 20, 20, 28),
        decoration: const BoxDecoration(
          color: AppTheme.cardBg,
          borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
        ),
        child: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Center(
                child: Container(
                  width: 40, height: 4, margin: const EdgeInsets.only(bottom: 16),
                  decoration: BoxDecoration(
                      color: AppTheme.border, borderRadius: BorderRadius.circular(2)),
                ),
              ),
              Text(isReassign ? 'Reassign Complaint' : 'Assign Complaint',
                  style: const TextStyle(fontSize: 17, fontWeight: FontWeight.w700)),
              if (isReassign && widget.complaint.assignedToName != null) ...[
                const SizedBox(height: 4),
                Text(
                  'Currently with ${widget.complaint.assignedToName}',
                  style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary),
                ),
              ],
              const SizedBox(height: 16),
              if (staffState is StaffListLoading)
                const Padding(
                  padding: EdgeInsets.symmetric(vertical: 12),
                  child: Center(child: CircularProgressIndicator(strokeWidth: 2)),
                )
              else if (assignable.isEmpty)
                const Padding(
                  padding: EdgeInsets.symmetric(vertical: 8),
                  child: Text(
                    'No staff with a login account are available to assign yet.',
                    style: TextStyle(fontSize: 13, color: AppTheme.textSecondary),
                  ),
                )
              else
                DropdownButtonFormField<String>(
                  value: _selectedUserId,
                  decoration: const InputDecoration(labelText: 'Assign to *'),
                  hint: const Text('Select staff member'),
                  items: assignable
                      .map((s) => DropdownMenuItem(
                            value: s.userId,
                            child: Text(s.designationName != null
                                ? '${s.fullName} — ${s.designationName}'
                                : s.fullName),
                          ))
                      .toList(),
                  onChanged: (v) => setState(() => _selectedUserId = v),
                ),
              const SizedBox(height: 14),
              InkWell(
                onTap: _pickDueDate,
                child: InputDecorator(
                  decoration: const InputDecoration(labelText: 'Due date (optional)'),
                  child: Text(
                    _dueDate == null
                        ? 'Not set'
                        : '${_dueDate!.day}/${_dueDate!.month}/${_dueDate!.year}',
                  ),
                ),
              ),
              const SizedBox(height: 14),
              TextField(
                controller: _notesCtrl,
                maxLines: 2,
                decoration: const InputDecoration(labelText: 'Notes (optional)'),
              ),
              const SizedBox(height: 20),
              AppPrimaryButton(
                label: isReassign ? 'Reassign' : 'Assign',
                isLoading: _submitting,
                onPressed:
                    (_selectedUserId == null || _submitting) ? null : _submit,
              ),
            ],
          ),
        ),
      ),
    );
  }
}
