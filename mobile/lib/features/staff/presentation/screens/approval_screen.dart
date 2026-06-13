import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/staff/domain/entities/staff_entities.dart';
import 'package:ar_society_app/features/staff/presentation/providers/staff_providers.dart';
import 'package:ar_society_app/features/staff/presentation/widgets/staff_widgets.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';

/// Supervisor/Manager attendance approval screen.
/// Shows pending punch-in and punch-out records awaiting approval.
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
      body: switch (state) {
        ApprovalLoading() || ApprovalInitial() => const Center(child: CircularProgressIndicator(color: AppTheme.primary)),
        ApprovalError(:final message) => Center(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                AppErrorBanner(message: message),
                const SizedBox(height: 16),
                ElevatedButton.icon(
                  onPressed: () => ref.read(approvalProvider.notifier).load(widget.societyId, department: widget.department),
                  icon: const Icon(Icons.refresh_rounded),
                  label: const Text('Retry'),
                ),
              ],
            ),
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

class _ApprovalCard extends ConsumerWidget {
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
  Widget build(BuildContext context, WidgetRef ref) {
    final isLoading = ref.watch(approvalProvider) is ApprovalLoading;

    return AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
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
                  type == _ApprovalType.checkin ? Icons.login_rounded : Icons.logout_rounded,
                  color: AppTheme.primary, size: 18,
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                        record.staffName?.isNotEmpty == true
                            ? record.staffName!
                            : 'Staff #${record.staffId.substring(0, 8)}',
                        style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 13, color: AppTheme.textPrimary)),
                    Text(formatDate(record.attendanceDate),
                        style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
                  ],
                ),
              ),
              AttendanceStatusBadge(status: record.status),
            ],
          ),
          const SizedBox(height: 12),
          Row(
            children: [
              _TimeChip(label: 'In', time: formatTime(record.checkInTime), color: AppTheme.success),
              const SizedBox(width: 8),
              if (record.checkOutTime != null)
                _TimeChip(label: 'Out', time: formatTime(record.checkOutTime), color: AppTheme.error),
              const Spacer(),
              ElevatedButton(
                onPressed: isLoading ? null : () => _approve(context, ref),
                style: ElevatedButton.styleFrom(
                  backgroundColor: AppTheme.success,
                  padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                  elevation: 0,
                ),
                child: isLoading
                    ? const SizedBox(width: 14, height: 14,
                        child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                    : const Text('Approve', style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600)),
              ),
            ],
          ),
        ],
      ),
    );
  }

  void _approve(BuildContext context, WidgetRef ref) {
    _showApproveDialog(context, ref);
  }

  void _showApproveDialog(BuildContext context, WidgetRef ref) {
    final notesCtrl = TextEditingController();
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(type == _ApprovalType.checkin ? 'Approve Punch-In?' : 'Approve Punch-Out?'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              record.staffName?.isNotEmpty == true
                  ? record.staffName!
                  : 'Staff #${record.staffId.substring(0, 8)}',
              style: const TextStyle(fontWeight: FontWeight.w600),
            ),
            Text(formatDate(record.attendanceDate),
              style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
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
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('Cancel'),
          ),
          ElevatedButton(
            style: ElevatedButton.styleFrom(backgroundColor: AppTheme.success),
            onPressed: () {
              Navigator.pop(ctx);
              final notifier = ref.read(approvalProvider.notifier);
              final notes = notesCtrl.text.trim().isEmpty ? null : notesCtrl.text.trim();
              if (type == _ApprovalType.checkin) {
                notifier.approveCheckin(record.id, societyId, notes: notes, department: department);
              } else {
                notifier.approveCheckout(record.id, societyId, notes: notes, department: department);
              }
            },
            child: const Text('Approve'),
          ),
        ],
      ),
    );
  }
}

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
