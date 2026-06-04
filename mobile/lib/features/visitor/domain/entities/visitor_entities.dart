import 'package:flutter/material.dart';

// ── Visitor type ──────────────────────────────────────────────────────────────

enum VisitorType {
  guest,
  delivery,
  cab,
  maintenance,
  vendor;

  String get label {
    switch (this) {
      case VisitorType.guest:       return 'Guest';
      case VisitorType.delivery:    return 'Delivery';
      case VisitorType.cab:         return 'Cab';
      case VisitorType.maintenance: return 'Maintenance';
      case VisitorType.vendor:      return 'Vendor';
    }
  }

  static VisitorType fromString(String s) {
    switch (s.toLowerCase()) {
      case 'guest':       return VisitorType.guest;
      case 'delivery':    return VisitorType.delivery;
      case 'cab':         return VisitorType.cab;
      case 'maintenance': return VisitorType.maintenance;
      case 'vendor':      return VisitorType.vendor;
      default:            return VisitorType.guest;
    }
  }
}

// ── Visitor status ────────────────────────────────────────────────────────────

enum VisitorStatus {
  pending,
  approved,
  rejected,
  checkedIn,
  checkedOut;

  String get label {
    switch (this) {
      case VisitorStatus.pending:    return 'Pending';
      case VisitorStatus.approved:   return 'Approved';
      case VisitorStatus.rejected:   return 'Rejected';
      case VisitorStatus.checkedIn:  return 'Checked In';
      case VisitorStatus.checkedOut: return 'Checked Out';
    }
  }

  static VisitorStatus fromString(String s) {
    switch (s.toLowerCase()) {
      case 'pending':     return VisitorStatus.pending;
      case 'approved':    return VisitorStatus.approved;
      case 'rejected':    return VisitorStatus.rejected;
      case 'checked_in':  return VisitorStatus.checkedIn;
      case 'checked_out': return VisitorStatus.checkedOut;
      default:            return VisitorStatus.pending;
    }
  }

  Color get color {
    switch (this) {
      case VisitorStatus.pending:    return const Color(0xFFD97706); // warning
      case VisitorStatus.approved:   return const Color(0xFF0EA5E9); // secondary
      case VisitorStatus.rejected:   return const Color(0xFFDC2626); // error
      case VisitorStatus.checkedIn:  return const Color(0xFF16A34A); // success
      case VisitorStatus.checkedOut: return const Color(0xFF6B7280); // textSecondary
    }
  }
}

// ── Visitor log entity ────────────────────────────────────────────────────────

class VisitorLogEntity {
  final String id;
  final String visitorId;
  final String action;
  final String? notes;
  final String? gateId;
  final DateTime createdAt;

  const VisitorLogEntity({
    required this.id,
    required this.visitorId,
    required this.action,
    this.notes,
    this.gateId,
    required this.createdAt,
  });
}

// ── Visitor vehicle entity ────────────────────────────────────────────────────

class VisitorVehicleEntity {
  final String id;
  final String vehicleType;
  final String vehicleNumber;
  final String? vehicleModel;
  final String? vehicleColor;

  const VisitorVehicleEntity({
    required this.id,
    required this.vehicleType,
    required this.vehicleNumber,
    this.vehicleModel,
    this.vehicleColor,
  });
}

// ── Visitor entity ────────────────────────────────────────────────────────────

class VisitorEntity {
  final String id;
  final String name;
  final String mobile;
  final VisitorType visitorType;
  final String? purpose;
  final String societyId;
  final String? flatId;
  final String? residentId;
  final String? gateId;
  final VisitorStatus status;
  final DateTime? expectedArrival;
  final DateTime? checkedInAt;
  final DateTime? checkedOutAt;
  final DateTime? approvedAt;
  final String? rejectionReason;
  final String? qrToken;
  final VisitorVehicleEntity? vehicle;
  final List<VisitorLogEntity> logs;
  final DateTime createdAt;

  const VisitorEntity({
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

  bool get canCheckIn  => status == VisitorStatus.approved;
  bool get canCheckOut => status == VisitorStatus.checkedIn;
  bool get isPending   => status == VisitorStatus.pending;
}
