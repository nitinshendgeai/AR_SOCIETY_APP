import 'package:ar_society_app/features/visitor/domain/entities/visitor_entities.dart';

// ── Visitor log model ─────────────────────────────────────────────────────────

class VisitorLogModel {
  final String id;
  final String visitorId;
  final String action;
  final String? notes;
  final String? gateId;
  final String createdAt;

  const VisitorLogModel({
    required this.id,
    required this.visitorId,
    required this.action,
    this.notes,
    this.gateId,
    required this.createdAt,
  });

  factory VisitorLogModel.fromJson(Map<String, dynamic> j) => VisitorLogModel(
        id: j['id'] as String,
        visitorId: j['visitor_id'] as String,
        action: j['action'] as String,
        notes: j['notes'] as String?,
        gateId: j['gate_id'] as String?,
        createdAt: j['created_at'] as String,
      );

  VisitorLogEntity toEntity() => VisitorLogEntity(
        id: id,
        visitorId: visitorId,
        action: action,
        notes: notes,
        gateId: gateId,
        createdAt: DateTime.parse(createdAt),
      );
}

// ── Visitor vehicle model ─────────────────────────────────────────────────────

class VisitorVehicleModel {
  final String id;
  final String vehicleType;
  final String vehicleNumber;
  final String? vehicleModel;
  final String? vehicleColor;

  const VisitorVehicleModel({
    required this.id,
    required this.vehicleType,
    required this.vehicleNumber,
    this.vehicleModel,
    this.vehicleColor,
  });

  factory VisitorVehicleModel.fromJson(Map<String, dynamic> j) =>
      VisitorVehicleModel(
        id: j['id'] as String,
        vehicleType: j['vehicle_type'] as String,
        vehicleNumber: j['vehicle_number'] as String,
        vehicleModel: j['vehicle_model'] as String?,
        vehicleColor: j['vehicle_color'] as String?,
      );

  VisitorVehicleEntity toEntity() => VisitorVehicleEntity(
        id: id,
        vehicleType: vehicleType,
        vehicleNumber: vehicleNumber,
        vehicleModel: vehicleModel,
        vehicleColor: vehicleColor,
      );
}

// ── Visitor model ─────────────────────────────────────────────────────────────

class VisitorModel {
  final String id;
  final String name;
  final String mobile;
  final String visitorType;
  final String? purpose;
  final String societyId;
  final String? flatId;
  final String? residentId;
  final String? gateId;
  final String status;
  final String? expectedArrival;
  final String? checkedInAt;
  final String? checkedOutAt;
  final String? approvedAt;
  final String? rejectionReason;
  final String? qrToken;
  final VisitorVehicleModel? vehicle;
  final List<VisitorLogModel> logs;
  final String createdAt;

  const VisitorModel({
    required this.id,
    required this.name,
    required this.mobile,
    required this.visitorType,
    this.purpose,
    required this.societyId,
    this.flatId,
    this.residentId,
    this.gateId,
    required this.status,
    this.expectedArrival,
    this.checkedInAt,
    this.checkedOutAt,
    this.approvedAt,
    this.rejectionReason,
    this.qrToken,
    this.vehicle,
    required this.logs,
    required this.createdAt,
  });

  factory VisitorModel.fromJson(Map<String, dynamic> j) => VisitorModel(
        id: j['id'] as String,
        name: j['name'] as String,
        mobile: j['mobile'] as String,
        visitorType: j['visitor_type'] as String,
        purpose: j['purpose'] as String?,
        societyId: j['society_id'] as String,
        flatId: j['flat_id'] as String?,
        residentId: j['resident_id'] as String?,
        gateId: j['gate_id'] as String?,
        status: j['status'] as String,
        expectedArrival: j['expected_arrival'] as String?,
        checkedInAt: j['checked_in_at'] as String?,
        checkedOutAt: j['checked_out_at'] as String?,
        approvedAt: j['approved_at'] as String?,
        rejectionReason: j['rejection_reason'] as String?,
        qrToken: j['qr_token'] as String?,
        vehicle: j['vehicle'] != null
            ? VisitorVehicleModel.fromJson(j['vehicle'] as Map<String, dynamic>)
            : null,
        logs: (j['logs'] as List<dynamic>? ?? [])
            .map((e) => VisitorLogModel.fromJson(e as Map<String, dynamic>))
            .toList(),
        createdAt: j['created_at'] as String,
      );

  VisitorEntity toEntity() => VisitorEntity(
        id: id,
        name: name,
        mobile: mobile,
        visitorType: VisitorType.fromString(visitorType),
        purpose: purpose,
        societyId: societyId,
        flatId: flatId,
        residentId: residentId,
        gateId: gateId,
        status: VisitorStatus.fromString(status),
        expectedArrival:
            expectedArrival != null ? DateTime.tryParse(expectedArrival!) : null,
        checkedInAt: checkedInAt != null ? DateTime.tryParse(checkedInAt!) : null,
        checkedOutAt:
            checkedOutAt != null ? DateTime.tryParse(checkedOutAt!) : null,
        approvedAt: approvedAt != null ? DateTime.tryParse(approvedAt!) : null,
        rejectionReason: rejectionReason,
        qrToken: qrToken,
        vehicle: vehicle?.toEntity(),
        logs: logs.map((l) => l.toEntity()).toList(),
        createdAt: DateTime.parse(createdAt),
      );
}
