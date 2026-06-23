import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/staff/domain/entities/staff_entities.dart';
import 'package:ar_society_app/features/staff/presentation/providers/staff_providers.dart';
import 'package:ar_society_app/features/staff/presentation/widgets/staff_widgets.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';

/// Supervisor/Manager attendance approval screen.
/// Shows pending punch-in and punch-out records awaiting approval or rejection.
class AttendanceApprovalScreen extends ConsumerStatefulWidget {
  final String societyId;
  final String? department;
  const AttendanceApprovalScreen({super.key, required this.societyId, this.department});

  @override
  ConsumerState<AttendanceApprovalScreen> createState() => _AttendanceApprovalScreenState();
}

class _AttendanceApprovalScreenState extends ConsumerState<AttendanceApprovalScreen>
    with SingleTickerProviderStateMixin {
  late TabController _tab;

  @override
  void initState() {
    super.initState();
    _tab = TabController(length: 2, vsync: this);
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (widget.societyId.isEmpty) return;
      ref.read(approvalProvider.notifier).load(widget.societyId, department: widget.department);
    });
  }

  @override
  void dispose() {
    _tab.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(approvalProvider);

    ref.listen(approvalProvider, (_, next) {
      if (next is ApprovalSuccess) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(
          content: Text(next.message),
          backgroundColor: AppTheme.success,
          behavior: SnackBarBehavior.floating,
        ));
      } else if (next is ApprovalError) {
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
        title: const Text('Attendance Approvals'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh_rounded),
            onPressed: () => ref.read(approvalProvider.notifier)
                .load(widget.societyId, department: widget.department),
          ),
        ],
        bottom: TabBar(
          controller: _tab,
          tabs: const [
            Tab(text: 'Punch In'),
            Tab(text: 'Punch Out'),
          ],
        ),
      ),
      body: widget.societyId.isEmpty
          ? _ErrorView(
              message: 'Society context is missing. Please go back and reopen this screen.',
              onRetry: () => Navigator.pop(context),
            )
          : switch (state) {
        ApprovalLoading() || ApprovalInitial() =>
          const Center(child: CircularProgressIndicator(color: AppTheme.primary)),
        ApprovalError(:final message) => _ErrorView(
            message: message,
            onRetry: () => ref.read(approvalProvider.notifier)
                .load(widget.societyId, department: widget.department),
          ),
        ApprovalLoaded(:final pendingCheckin, :final pendingCheckout) => TabBarView(
          controller: _tab,
          children: [
            _ApprovalList(
              records: pendingCheckin,
              type: _ApprovalType.checkin,
              societyId: widget.societyId,
              department: widget.department,
            ),
            _ApprovalList(
              records: pendingCheckout,
              type: _ApprovalType.checkout,
              societyId: widget.societyId,
              department: widget.department,
            ),
          ],
        ),
        _ => const Center(child: CircularProgressIndicator(color: AppTheme.primary)),
      },
    );
  }
}

// ── Error view with diagnostic message ───────────────────────────────────────

class _ErrorView extends StatelessWidget {
  final String message;
  final VoidCallback onRetry;
  const _ErrorView({required this.message, required this.onRetry});

  @override
  Widget build(BuildContext context) {
    final isPermission = message.contains('Permission') || message.contains('403');
    final isSession    = message.contains('Session') || message.contains('401');
    final isServer     = message.contains('Server') || message.contains('500');
    final isNotFound   = message.contains('not found') || message.contains('404');

    final icon = isPermission ? Icons.lock_outline_rounded
               : isSession    ? Icons.login_rounded
               : isServer     ? Icons.cloud_off_rounded
               : isNotFound   ? Icons.search_off_rounded
               : Icons.error_outline_rounded;

    final color = isPermission || isSession ? AppTheme.warning : AppTheme.error;

    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, color: color, size: 48),
            const SizedBox(height: 16),
            Text(
              message,
              textAlign: TextAlign.center,
              style: TextStyle(
                color: color,
                fontSize: 14,
                fontWeight: FontWeight.w500,
              ),
            ),
            const SizedBox(height: 8),
            if (isPermission)
              const Text(
                'Contact your administrator if you believe this is an error.',
                textAlign: TextAlign.center,
                style: TextStyle(fontSize: 12, color: AppTheme.textSecondary),
              ),
            const SizedBox(height: 24),
            ElevatedButton.icon(
              onPressed: onRetry,
              icon: const Icon(Icons.refresh_rounded),
              label: const Text('Retry'),
            ),
          ],
        ),
      ),
    );
  }
}

// ── Approval list ─────────────────────────────────────────────────────────────

enum _ApprovalType { checkin, checkout }

class _ApprovalList extends ConsumerWidget {
  final List<AttendanceEntity> records;
  final _ApprovalType type;
  final String societyId;
  final String? department;

  const _ApprovalList({
    required this.records,
    required this.type,
    required this.societyId,
    this.department,
  });

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    if (records.isEmpty) {
      return EmptyState(
        icon: type == _ApprovalType.checkin
            ? Icons.login_rounded
            : Icons.logout_rounded,
        title: 'No pending ${type == _ApprovalType.checkin ? 'punch-in' : 'punch-out'} approvals',
        subtitle: 'All records are up to date.',
      );
    }

    return RefreshIndicator(
      onRefresh: () => ref.read(approvalProvider.notifier).load(societyId, department: department),
      child: ListView.builder(
        padding: const EdgeInsets.all(16),
        itemCount: records.length,
        itemBuilder: (_, i) => Padding(
          padding: const EdgeInsets.only(bottom: 12),
          child: _ApprovalCard(
            record: records[i],
            type: type,
            societyId: societyId,
            department: department,
          ),
        ),
      ),
    );
  }
}

// ── Approval card with Approve, Reject, View Details ─────────────────────────

class _ApprovalCard extends ConsumerStatefulWidget {
  final AttendanceEntity record;
  final _ApprovalType type;
  final String societyId;
  final String? department;

  const _ApprovalCard({
    required this.record,
    required this.type,
    required this.societyId,
    this.department,
  });

  @override
  ConsumerState<_ApprovalCard> createState() => _ApprovalCardState();
}

class _ApprovalCardState extends ConsumerState<_ApprovalCard> {
  bool _expanded = false;

  @override
  Widget build(BuildContext context) {
    final isLoading = ref.watch(approvalProvider) is ApprovalLoading;
    final r = widget.record;
    final staffLabel = r.staffName?.isNotEmpty == true
        ? r.staffName!
        : 'Staff #${r.staffId.substring(0, r.staffId.length.clamp(0, 8))}';

    return AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // ── Header row ─────────────────────────────────────────────────────
          Row(
            children: [
              Container(
                width: 36,
                height: 36,
                decoration: BoxDecoration(
                  color: AppTheme.primary.withOpacity(0.1),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Icon(
                  widget.type == _ApprovalType.checkin
                      ? Icons.login_rounded
                      : Icons.logout_rounded,
                  color: AppTheme.primary, size: 18,
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(staffLabel,
                        style: const TextStyle(
                            fontWeight: FontWeight.w600,
                            fontSize: 13,
                            color: AppTheme.textPrimary)),
                    Text(formatDate(r.attendanceDate),
                        style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
                  ],
                ),
              ),
              AttendanceStatusBadge(status: r.status),
            ],
          ),

          const SizedBox(height: 10),

          // ── Time chips row ─────────────────────────────────────────────────
          Row(
            children: [
              _TimeChip(label: 'In',  time: formatTime(r.checkInTime),  color: AppTheme.success),
              if (r.checkOutTime != null) ...[
                const SizedBox(width: 8),
                _TimeChip(label: 'Out', time: formatTime(r.checkOutTime), color: AppTheme.error),
              ],
              if (r.workingHours != null) ...[
                const SizedBox(width: 8),
                _TimeChip(label: 'Hrs', time: '${r.workingHours!.toStringAsFixed(1)}h', color: AppTheme.primary),
              ],
            ],
          ),

          const SizedBox(height: 12),

          // ── Action buttons row ─────────────────────────────────────────────
          Row(
            children: [
              // View Details toggle
              GestureDetector(
                onTap: () => setState(() => _expanded = !_expanded),
                child: Row(
                  children: [
                    Icon(
                      _expanded ? Icons.expand_less_rounded : Icons.expand_more_rounded,
                      size: 18,
                      color: AppTheme.textSecondary,
                    ),
                    const SizedBox(width: 4),
                    Text(
                      _expanded ? 'Hide' : 'Details',
                      style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary),
                    ),
                  ],
                ),
              ),
              const Spacer(),
              // Reject button
              OutlinedButton(
                onPressed: isLoading ? null : () => _showRejectDialog(context),
                style: OutlinedButton.styleFrom(
                  foregroundColor: AppTheme.error,
                  side: BorderSide(color: AppTheme.error.withOpacity(0.5)),
                  padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                  minimumSize: Size.zero,
                  tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                ),
                child: const Text('Reject', style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600)),
              ),
              const SizedBox(width: 8),
              // Approve button
              ElevatedButton(
                onPressed: isLoading ? null : () => _showApproveDialog(context),
                style: ElevatedButton.styleFrom(
                  backgroundColor: AppTheme.success,
                  padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                  elevation: 0,
                  minimumSize: Size.zero,
                  tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                ),
                child: isLoading
                    ? const SizedBox(
                        width: 14, height: 14,
                        child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                    : const Text('Approve', style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600)),
              ),
            ],
          ),

          // ── Expanded detail section ────────────────────────────────────────
          if (_expanded) ...[
            const SizedBox(height: 12),
            const Divider(height: 1),
            const SizedBox(height: 12),
            _DetailRow('Staff ID', r.staffId.substring(0, r.staffId.length.clamp(0, 16))),
            _DetailRow('Date', r.attendanceDate),
            _DetailRow('Status', r.status.label),
            if (r.notes?.isNotEmpty == true) _DetailRow('Notes', r.notes!),
            if (r.overtimeHours != null && r.overtimeHours! > 0)
              _DetailRow('Overtime', '${r.overtimeHours!.toStringAsFixed(1)}h'),
          ],
        ],
      ),
    );
  }

  void _showApproveDialog(BuildContext context) {
    final notesCtrl = TextEditingController();
    final isCheckin = widget.type == _ApprovalType.checkin;
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(isCheckin ? 'Approve Punch-In?' : 'Approve Punch-Out?'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              widget.record.staffName?.isNotEmpty == true
                  ? widget.record.staffName!
                  : 'Staff #${widget.record.staffId.substring(0, widget.record.staffId.length.clamp(0, 8))}',
              style: const TextStyle(fontWeight: FontWeight.w600),
            ),
            Text(
              formatDate(widget.record.attendanceDate),
              style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: notesCtrl,
              decoration: const InputDecoration(
                hintText: 'Optional approval notes',
                border: OutlineInputBorder(),
                isDense: true,
              ),
              maxLines: 2,
              textCapitalization: TextCapitalization.sentences,
            ),
          ],
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Cancel')),
          ElevatedButton(
            style: ElevatedButton.styleFrom(backgroundColor: AppTheme.success),
            onPressed: () {
              Navigator.pop(ctx);
              final notifier = ref.read(approvalProvider.notifier);
              final notes = notesCtrl.text.trim().isEmpty ? null : notesCtrl.text.trim();
              if (isCheckin) {
                notifier.approveCheckin(widget.record.id, widget.societyId,
                    notes: notes, department: widget.department);
              } else {
                notifier.approveCheckout(widget.record.id, widget.societyId,
                    notes: notes, department: widget.department);
              }
            },
            child: const Text('Approve'),
          ),
        ],
      ),
    );
  }

  void _showRejectDialog(BuildContext context) {
    final reasonCtrl = TextEditingController();
    final isCheckin  = widget.type == _ApprovalType.checkin;
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(isCheckin ? 'Reject Punch-In?' : 'Reject Punch-Out?'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              widget.record.staffName?.isNotEmpty == true
                  ? widget.record.staffName!
                  : 'Staff #${widget.record.staffId.substring(0, widget.record.staffId.length.clamp(0, 8))}',
              style: const TextStyle(fontWeight: FontWeight.w600),
            ),
            Text(
              formatDate(widget.record.attendanceDate),
              style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary),
            ),
            const SizedBox(height: 8),
            Container(
              padding: const EdgeInsets.all(10),
              decoration: BoxDecoration(
                color: AppTheme.warning.withOpacity(0.08),
                borderRadius: BorderRadius.circular(8),
                border: Border.all(color: AppTheme.warning.withOpacity(0.3)),
              ),
              child: Text(
                isCheckin
                    ? 'Rejecting will remove this check-in. The staff member must check in again.'
                    : 'Rejecting will remove this check-out. The staff member must check out again.',
                style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary),
              ),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: reasonCtrl,
              decoration: const InputDecoration(
                hintText: 'Reason for rejection (optional)',
                border: OutlineInputBorder(),
                isDense: true,
              ),
              maxLines: 2,
              textCapitalization: TextCapitalization.sentences,
            ),
          ],
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Cancel')),
          ElevatedButton(
            style: ElevatedButton.styleFrom(backgroundColor: AppTheme.error),
            onPressed: () {
              Navigator.pop(ctx);
              final notifier = ref.read(approvalProvider.notifier);
              final reason = reasonCtrl.text.trim().isEmpty ? null : reasonCtrl.text.trim();
              if (isCheckin) {
                notifier.rejectCheckin(widget.record.id, widget.societyId,
                    reason: reason, department: widget.department);
              } else {
                notifier.rejectCheckout(widget.record.id, widget.societyId,
                    reason: reason, department: widget.department);
              }
            },
            child: const Text('Reject', style: TextStyle(color: Colors.white)),
          ),
        ],
      ),
    );
  }
}

// ── Detail row ────────────────────────────────────────────────────────────────

class _DetailRow extends StatelessWidget {
  final String label;
  final String value;
  const _DetailRow(this.label, this.value);

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 6),
      child: Row(
        children: [
          SizedBox(
            width: 70,
            child: Text(label,
                style: const TextStyle(fontSize: 11, color: AppTheme.textSecondary)),
          ),
          Expanded(
            child: Text(value,
                style: const TextStyle(fontSize: 12, color: AppTheme.textPrimary,
                    fontWeight: FontWeight.w500)),
          ),
        ],
      ),
    );
  }
}

// ── Time chip ─────────────────────────────────────────────────────────────────

class _TimeChip extends StatelessWidget {
  final String label;
  final String time;
  final Color color;
  const _TimeChip({required this.label, required this.time, required this.color});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: color.withOpacity(0.1),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: color.withOpacity(0.25)),
      ),
      child: Text('$label: $time',
          style: TextStyle(fontSize: 11, fontWeight: FontWeight.w600, color: color)),
    );
  }
}
