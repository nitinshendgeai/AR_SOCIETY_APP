import 'package:ar_society_app/features/complaint/domain/entities/complaint_entities.dart';

// ── Complaint comment model ───────────────────────────────────────────────────

class ComplaintCommentModel {
  final String id;
  final String complaintId;
  final String authorId;
  final String body;
  final bool isInternal;
  final String createdAt;

  const ComplaintCommentModel({
    required this.id,
    required this.complaintId,
    required this.authorId,
    required this.body,
    required this.isInternal,
    required this.createdAt,
  });

  factory ComplaintCommentModel.fromJson(Map<String, dynamic> j) =>
      ComplaintCommentModel(
        id: j['id'] as String,
        complaintId: j['complaint_id'] as String,
        authorId: j['author_id'] as String,
        body: j['body'] as String,
        isInternal: j['is_internal'] as bool? ?? false,
        createdAt: j['created_at'] as String,
      );

  ComplaintCommentEntity toEntity() => ComplaintCommentEntity(
        id: id,
        complaintId: complaintId,
        authorId: authorId,
        body: body,
        isInternal: isInternal,
        createdAt: DateTime.parse(createdAt),
      );
}

// ── Complaint model (full detail — matches ComplaintOut) ──────────────────────

class ComplaintModel {
  final String id;
  final String complaintNumber;
  final String title;
  final String description;
  final String category;
  final String priority;
  final String status;
  final String societyId;
  final String? flatId;
  final String raisedBy;
  final String? assignedTo;
  final String? resolvedAt;
  final String? closedAt;
  final String? dueDate;
  final String? resolutionNotes;
  final String? rejectionReason;
  final int reopenCount;
  final List<ComplaintCommentModel> comments;
  final String createdAt;

  const ComplaintModel({
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
    required this.comments,
    required this.createdAt,
  });

  factory ComplaintModel.fromJson(Map<String, dynamic> j) => ComplaintModel(
        id: j['id'] as String,
        complaintNumber: j['complaint_number'] as String,
        title: j['title'] as String,
        description: j['description'] as String,
        category: j['category'] as String,
        priority: j['priority'] as String,
        status: j['status'] as String,
        societyId: j['society_id'] as String,
        flatId: j['flat_id'] as String?,
        raisedBy: j['raised_by'] as String,
        assignedTo: j['assigned_to'] as String?,
        resolvedAt: j['resolved_at'] as String?,
        closedAt: j['closed_at'] as String?,
        dueDate: j['due_date'] as String?,
        resolutionNotes: j['resolution_notes'] as String?,
        rejectionReason: j['rejection_reason'] as String?,
        reopenCount: j['reopen_count'] as int? ?? 0,
        comments: (j['comments'] as List<dynamic>? ?? [])
            .map((e) =>
                ComplaintCommentModel.fromJson(e as Map<String, dynamic>))
            .toList(),
        createdAt: j['created_at'] as String,
      );

  ComplaintEntity toEntity() => ComplaintEntity(
        id: id,
        complaintNumber: complaintNumber,
        title: title,
        description: description,
        category: ComplaintCategory.fromString(category),
        priority: ComplaintPriority.fromString(priority),
        status: ComplaintStatus.fromString(status),
        societyId: societyId,
        flatId: flatId,
        raisedBy: raisedBy,
        assignedTo: assignedTo,
        resolvedAt: resolvedAt != null ? DateTime.tryParse(resolvedAt!) : null,
        closedAt: closedAt != null ? DateTime.tryParse(closedAt!) : null,
        dueDate: dueDate != null ? DateTime.tryParse(dueDate!) : null,
        resolutionNotes: resolutionNotes,
        rejectionReason: rejectionReason,
        reopenCount: reopenCount,
        comments: comments.map((c) => c.toEntity()).toList(),
        createdAt: DateTime.parse(createdAt),
      );
}

// ── Complaint list model (lightweight — matches ComplaintListOut) ──────────────

class ComplaintListModel {
  final String id;
  final String complaintNumber;
  final String title;
  final String category;
  final String priority;
  final String status;
  final String societyId;
  final String raisedBy;
  final String? assignedTo;
  final String? resolvedAt;
  final String? closedAt;
  final String createdAt;

  const ComplaintListModel({
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

  factory ComplaintListModel.fromJson(Map<String, dynamic> j) =>
      ComplaintListModel(
        id: j['id'] as String,
        complaintNumber: j['complaint_number'] as String,
        title: j['title'] as String,
        category: j['category'] as String,
        priority: j['priority'] as String,
        status: j['status'] as String,
        societyId: j['society_id'] as String,
        raisedBy: j['raised_by'] as String,
        assignedTo: j['assigned_to'] as String?,
        resolvedAt: j['resolved_at'] as String?,
        closedAt: j['closed_at'] as String?,
        createdAt: j['created_at'] as String,
      );

  ComplaintListEntity toEntity() => ComplaintListEntity(
        id: id,
        complaintNumber: complaintNumber,
        title: title,
        category: ComplaintCategory.fromString(category),
        priority: ComplaintPriority.fromString(priority),
        status: ComplaintStatus.fromString(status),
        societyId: societyId,
        raisedBy: raisedBy,
        assignedTo: assignedTo,
        resolvedAt: resolvedAt != null ? DateTime.tryParse(resolvedAt!) : null,
        closedAt: closedAt != null ? DateTime.tryParse(closedAt!) : null,
        createdAt: DateTime.parse(createdAt),
      );
}
