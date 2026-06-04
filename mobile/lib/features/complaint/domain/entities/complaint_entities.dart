import 'package:flutter/material.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';

// ── Complaint Status ──────────────────────────────────────────────────────────

enum ComplaintStatus {
  open,
  assigned,
  inProgress,
  resolved,
  reopened,
  closed,
  rejected;

  String get label {
    switch (this) {
      case ComplaintStatus.open:       return 'Open';
      case ComplaintStatus.assigned:   return 'Assigned';
      case ComplaintStatus.inProgress: return 'In Progress';
      case ComplaintStatus.resolved:   return 'Resolved';
      case ComplaintStatus.reopened:   return 'Reopened';
      case ComplaintStatus.closed:     return 'Closed';
      case ComplaintStatus.rejected:   return 'Rejected';
    }
  }

  Color get color {
    switch (this) {
      case ComplaintStatus.open:       return AppTheme.primary;
      case ComplaintStatus.assigned:   return AppTheme.secondary;
      case ComplaintStatus.inProgress: return AppTheme.warning;
      case ComplaintStatus.resolved:   return AppTheme.success;
      case ComplaintStatus.reopened:   return AppTheme.warning;
      case ComplaintStatus.closed:     return AppTheme.textSecondary;
      case ComplaintStatus.rejected:   return AppTheme.error;
    }
  }

  static ComplaintStatus fromString(String s) {
    switch (s.toLowerCase()) {
      case 'assigned':    return ComplaintStatus.assigned;
      case 'in_progress': return ComplaintStatus.inProgress;
      case 'resolved':    return ComplaintStatus.resolved;
      case 'reopened':    return ComplaintStatus.reopened;
      case 'closed':      return ComplaintStatus.closed;
      case 'rejected':    return ComplaintStatus.rejected;
      default:            return ComplaintStatus.open;
    }
  }
}

// ── Complaint Priority ────────────────────────────────────────────────────────

enum ComplaintPriority {
  low,
  medium,
  high,
  critical;

  String get label {
    switch (this) {
      case ComplaintPriority.low:      return 'Low';
      case ComplaintPriority.medium:   return 'Medium';
      case ComplaintPriority.high:     return 'High';
      case ComplaintPriority.critical: return 'Critical';
    }
  }

  Color get color {
    switch (this) {
      case ComplaintPriority.low:      return AppTheme.textSecondary;
      case ComplaintPriority.medium:   return AppTheme.warning;
      case ComplaintPriority.high:     return AppTheme.error;
      case ComplaintPriority.critical: return const Color(0xFF7C0000);
    }
  }

  static ComplaintPriority fromString(String s) {
    switch (s.toLowerCase()) {
      case 'low':      return ComplaintPriority.low;
      case 'high':     return ComplaintPriority.high;
      case 'critical': return ComplaintPriority.critical;
      default:         return ComplaintPriority.medium;
    }
  }
}

// ── Complaint Category ────────────────────────────────────────────────────────

enum ComplaintCategory {
  plumbing,
  electrical,
  security,
  housekeeping,
  parking,
  lift,
  water,
  amenities,
  other;

  String get label {
    switch (this) {
      case ComplaintCategory.plumbing:     return 'Plumbing';
      case ComplaintCategory.electrical:   return 'Electrical';
      case ComplaintCategory.security:     return 'Security';
      case ComplaintCategory.housekeeping: return 'Housekeeping';
      case ComplaintCategory.parking:      return 'Parking';
      case ComplaintCategory.lift:         return 'Lift / Elevator';
      case ComplaintCategory.water:        return 'Water Supply';
      case ComplaintCategory.amenities:    return 'Amenities';
      case ComplaintCategory.other:        return 'Other';
    }
  }

  static ComplaintCategory fromString(String s) {
    switch (s.toLowerCase()) {
      case 'plumbing':     return ComplaintCategory.plumbing;
      case 'electrical':   return ComplaintCategory.electrical;
      case 'security':     return ComplaintCategory.security;
      case 'housekeeping': return ComplaintCategory.housekeeping;
      case 'parking':      return ComplaintCategory.parking;
      case 'lift':         return ComplaintCategory.lift;
      case 'water':        return ComplaintCategory.water;
      case 'amenities':    return ComplaintCategory.amenities;
      default:             return ComplaintCategory.other;
    }
  }
}

// ── Complaint Comment Entity ──────────────────────────────────────────────────

class ComplaintCommentEntity {
  final String id;
  final String complaintId;
  final String authorId;
  final String body;
  final bool isInternal;
  final DateTime createdAt;

  const ComplaintCommentEntity({
    required this.id,
    required this.complaintId,
    required this.authorId,
    required this.body,
    required this.isInternal,
    required this.createdAt,
  });
}

// ── Complaint List Entity (lightweight) ───────────────────────────────────────

class ComplaintListEntity {
  final String id;
  final String complaintNumber;
  final String title;
  final ComplaintCategory category;
  final ComplaintPriority priority;
  final ComplaintStatus status;
  final String societyId;
  final String raisedBy;
  final String? assignedTo;
  final DateTime? resolvedAt;
  final DateTime? closedAt;
  final DateTime createdAt;

  const ComplaintListEntity({
    required this.id,
    required this.complaintNumber,
    required this.title,
    required this.category,
    required this.priority,
    required this.status,
    required this.societyId,
    required this.raisedBy,
    this.assignedTo,
    this.resolvedAt,
    this.closedAt,
    required this.createdAt,
  });
}

// ── Complaint Entity (full detail) ────────────────────────────────────────────

class ComplaintEntity {
  final String id;
  final String complaintNumber;
  final String title;
  final String description;
  final ComplaintCategory category;
  final ComplaintPriority priority;
  final ComplaintStatus status;
  final String societyId;
  final String? flatId;
  final String raisedBy;
  final String? assignedTo;
  final DateTime? resolvedAt;
  final DateTime? closedAt;
  final DateTime? dueDate;
  final String? resolutionNotes;
  final String? rejectionReason;
  final int reopenCount;
  final List<ComplaintCommentEntity> comments;
  final DateTime createdAt;

  const ComplaintEntity({
    required this.id,
    required this.complaintNumber,
    required this.title,
    required this.description,
    required this.category,
    required this.priority,
    required this.status,
    required this.societyId,
    this.flatId,
    required this.raisedBy,
    this.assignedTo,
    this.resolvedAt,
    this.closedAt,
    this.dueDate,
    this.resolutionNotes,
    this.rejectionReason,
    this.reopenCount = 0,
    this.comments = const [],
    required this.createdAt,
  });

  bool get isActive => status != ComplaintStatus.closed && status != ComplaintStatus.rejected;
}
