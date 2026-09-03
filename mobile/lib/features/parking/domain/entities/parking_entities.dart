// ── Gate vehicle lookup (pre-entry check, read-only) ────────────────────────

/// Which kind of record authorized this vehicle, mirrors the backend's
/// GateVehicleLookupOut.category.
enum GateVehicleCategory {
  resident,
  tenant,
  visitor,
  unregistered;

  static GateVehicleCategory fromString(String s) {
    switch (s.toLowerCase()) {
      case 'resident':     return GateVehicleCategory.resident;
      case 'tenant':       return GateVehicleCategory.tenant;
      case 'visitor':      return GateVehicleCategory.visitor;
      default:             return GateVehicleCategory.unregistered;
    }
  }

  String get label {
    switch (this) {
      case GateVehicleCategory.resident:     return 'Resident';
      case GateVehicleCategory.tenant:       return 'Tenant';
      case GateVehicleCategory.visitor:      return 'Visitor';
      case GateVehicleCategory.unregistered: return 'Unregistered';
    }
  }
}

class GateVehicleLookupEntity {
  final String vehicleNumber;
  final bool authorized;
  final GateVehicleCategory category;
  final String? vehicleType;
  final String? flatNumber;
  final String? wingName;
  final String? ownerName;
  final String? parkingSlot;
  final String? visitorPurpose;
  final DateTime? visitorCheckInTime;
  final String message;

  const GateVehicleLookupEntity({
    required this.vehicleNumber,
    required this.authorized,
    required this.category,
    this.vehicleType,
    this.flatNumber,
    this.wingName,
    this.ownerName,
    this.parkingSlot,
    this.visitorPurpose,
    this.visitorCheckInTime,
    required this.message,
  });
}

// ── Access log (entry/exit record, written after the guard decides) ────────

enum GateAccessType {
  entry,
  exit;

  String get value => this == GateAccessType.entry ? 'entry' : 'exit';
  String get label => this == GateAccessType.entry ? 'Entry' : 'Exit';
}

class ParkingAccessLogEntity {
  final String id;
  final String vehicleNumber;
  final GateAccessType accessType;
  final bool isAuthorized;
  final DateTime accessTime;

  const ParkingAccessLogEntity({
    required this.id,
    required this.vehicleNumber,
    required this.accessType,
    required this.isAuthorized,
    required this.accessTime,
  });
}
