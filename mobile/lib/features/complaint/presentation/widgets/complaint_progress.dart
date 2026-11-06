import 'package:flutter/material.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/complaint/domain/entities/complaint_entities.dart';

/// "today", "yesterday", "3 days ago": how long ago [then] was, in whole calendar days.
String complaintAgo(DateTime then, DateTime now) {
  final days = DateTime(now.year, now.month, now.day)
      .difference(DateTime(then.year, then.month, then.day))
      .inDays;
  if (days <= 0) return 'today';
  if (days == 1) return 'yesterday';
  return '$days days ago';
}

/// Where the complaint is on the four steps a resident cares about: 0 Raised, 1 Assigned, 2 In progress, 3 Resolved.
/// A rejected complaint has no place on the track, so it returns null.
int? complaintStep(ComplaintStatus s) => switch (s) {
      ComplaintStatus.open || ComplaintStatus.reopened => 0,
      ComplaintStatus.assigned => 1,
      ComplaintStatus.inProgress => 2,
      ComplaintStatus.resolved || ComplaintStatus.closed => 3,
      ComplaintStatus.rejected => null,
    };

/// One plain sentence about where the complaint stands.
String complaintStatusSentence(ComplaintEntity c) {
  final who = c.assignedToName;
  return switch (c.status) {
    ComplaintStatus.open => 'Waiting for the office to assign this to someone.',
    ComplaintStatus.reopened => 'Reopened. Waiting for the office to assign this again.',
    ComplaintStatus.assigned => who == null ? 'Assigned. Work has not started yet.' : 'Assigned to $who. Work has not started yet.',
    ComplaintStatus.inProgress => who == null ? 'Someone is working on this.' : '$who is working on this.',
    ComplaintStatus.resolved => 'Marked resolved. If the problem is still there, reopen it.',
    ComplaintStatus.closed => 'Closed.',
    ComplaintStatus.rejected => 'This complaint was not taken up.',
  };
}

/// The one-line status under a complaint in the resident's list.
String complaintListNote(ComplaintListEntity c, DateTime now) {
  final raised = 'raised ${complaintAgo(c.createdAt, now)}';
  final who = c.assignedToName;
  return switch (c.status) {
    ComplaintStatus.open => 'Waiting to be assigned  ·  $raised',
    ComplaintStatus.reopened => 'Reopened, waiting to be assigned  ·  $raised',
    ComplaintStatus.assigned => who == null ? 'Assigned  ·  $raised' : 'Assigned to $who  ·  $raised',
    ComplaintStatus.inProgress => who == null ? 'In progress  ·  $raised' : '$who is on it  ·  $raised',
    ComplaintStatus.resolved => c.resolvedAt == null ? 'Resolved' : 'Resolved ${complaintAgo(c.resolvedAt!, now)}',
    ComplaintStatus.closed => c.closedAt == null ? 'Closed' : 'Closed ${complaintAgo(c.closedAt!, now)}',
    ComplaintStatus.rejected => 'Not taken up',
  };
}

/// A complaint that still needs attention (as against one that is finished, one way or another).
bool complaintIsActive(ComplaintStatus s) => switch (s) {
      ComplaintStatus.open || ComplaintStatus.assigned || ComplaintStatus.inProgress || ComplaintStatus.reopened => true,
      _ => false,
    };

/// Raised → Assigned → In progress → Resolved, with the current step marked and a sentence below.
class ComplaintProgressCard extends StatelessWidget {
  final ComplaintEntity complaint;
  const ComplaintProgressCard({super.key, required this.complaint});

  static const _steps = ['Raised', 'Assigned', 'In progress', 'Resolved'];

  @override
  Widget build(BuildContext context) {
    final step = complaintStep(complaint.status);
    final rejected = step == null;
    final color = rejected ? AppTheme.error : complaint.status.color;
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: color.withOpacity(0.07),
        borderRadius: BorderRadius.circular(AppTheme.radiusM),
        border: Border.all(color: color.withOpacity(0.3)),
      ),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        if (!rejected)
          Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
            for (var i = 0; i < _steps.length; i++) ...[
              if (i > 0)
                Expanded(
                  child: Padding(
                    padding: const EdgeInsets.only(top: 10),
                    child: Container(height: 2, color: i <= step ? color : AppTheme.border),
                  ),
                ),
              _Dot(label: _steps[i], reached: i <= step, current: i == step, color: color),
            ],
          ]),
        if (!rejected) const SizedBox(height: 10),
        Text(
          complaintStatusSentence(complaint),
          style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: color, height: 1.4),
        ),
        if (rejected && complaint.rejectionReason != null && complaint.rejectionReason!.isNotEmpty) ...[
          const SizedBox(height: 4),
          Text('Reason: ${complaint.rejectionReason}',
              style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
        ],
        if (complaint.reopenCount > 0) ...[
          const SizedBox(height: 4),
          Text('Reopened ${complaint.reopenCount} time${complaint.reopenCount == 1 ? '' : 's'}',
              style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
        ],
      ]),
    );
  }
}

class _Dot extends StatelessWidget {
  final String label;
  final bool reached;
  final bool current;
  final Color color;
  const _Dot({required this.label, required this.reached, required this.current, required this.color});

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: 64,
      child: Column(children: [
        Container(
          width: 22,
          height: 22,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            color: reached ? color : Colors.transparent,
            border: Border.all(color: reached ? color : AppTheme.border, width: 2),
          ),
          child: reached ? const Icon(Icons.check_rounded, size: 14, color: Colors.white) : null,
        ),
        const SizedBox(height: 4),
        Text(label,
            textAlign: TextAlign.center,
            style: TextStyle(
              fontSize: 11,
              fontWeight: current ? FontWeight.w700 : FontWeight.w500,
              color: reached ? AppTheme.textPrimary : AppTheme.textSecondary,
            )),
      ]),
    );
  }
}
