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

/// What the gate should do with the vehicle, mirrors GateVehicleLookupOut.status.
enum GateStatus {
  allowed,
  noParking,
  unregistered;

  static GateStatus fromString(String? s, {required bool authorized}) {
    switch (s) {
      case 'allowed':      return GateStatus.allowed;
      case 'no_parking':   return GateStatus.noParking;
      case 'unregistered': return GateStatus.unregistered;
    }
    return authorized ? GateStatus.allowed : GateStatus.unregistered;
  }
}

class GateVehicleLookupEntity {
  final String vehicleNumber;
  final bool authorized;
  final GateStatus status;
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
    this.status = GateStatus.unregistered,
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

// ── Parking management: zones, slots, allocations ───────────────────────────

class ParkingZoneEntity {
  final String id;
  final String societyId;
  final String name;
  final String? code;
  final int totalSlots;

  const ParkingZoneEntity({
    required this.id,
    required this.societyId,
    required this.name,
    this.code,
    required this.totalSlots,
  });
}

enum ParkingSlotStatus {
  available,
  occupied,
  reserved,
  blocked,
  underMaintenance;

  static ParkingSlotStatus fromString(String s) {
    switch (s.toLowerCase()) {
      case 'occupied':           return ParkingSlotStatus.occupied;
      case 'reserved':           return ParkingSlotStatus.reserved;
      case 'blocked':            return ParkingSlotStatus.blocked;
      case 'under_maintenance':  return ParkingSlotStatus.underMaintenance;
      default:                   return ParkingSlotStatus.available;
    }
  }

  String get label {
    switch (this) {
      case ParkingSlotStatus.available:        return 'Available';
      case ParkingSlotStatus.occupied:         return 'Occupied';
      case ParkingSlotStatus.reserved:         return 'Reserved';
      case ParkingSlotStatus.blocked:          return 'Blocked';
      case ParkingSlotStatus.underMaintenance: return 'Maintenance';
    }
  }
}

class ParkingSlotEntity {
  final String id;
  final String societyId;
  final String zoneId;
  final String slotNumber;
  final String slotType;
  final ParkingSlotStatus status;
  final bool isCovered;
  final bool isEvCharging;

  const ParkingSlotEntity({
    required this.id,
    required this.societyId,
    required this.zoneId,
    required this.slotNumber,
    required this.slotType,
    required this.status,
    this.isCovered = false,
    this.isEvCharging = false,
  });
}

class ParkingAllocationEntity {
  final String id;
  final String societyId;
  final String slotId;
  final String? flatId;
  final String? vehicleId;
  final String allocationType;
  final String status;
  final DateTime startDate;
  final DateTime? endDate;
  final int? monthlyCharge;
  final String? slotNumber;
  final String? vehicleNumber;
  final String? flatNumber;
  final String? wingName;

  const ParkingAllocationEntity({
    required this.id,
    required this.societyId,
    required this.slotId,
    this.flatId,
    this.vehicleId,
    required this.allocationType,
    required this.status,
    required this.startDate,
    this.endDate,
    this.monthlyCharge,
    this.slotNumber,
    this.vehicleNumber,
    this.flatNumber,
    this.wingName,
  });

  bool get isActive => status == 'active';
  bool get isRented => monthlyCharge != null && monthlyCharge! > 0;
}


// ── Registered vehicles and their parking ───────────────────────────────────

/// A vehicle a resident or tenant has registered, and whether it has parking.
class VehicleParkingEntity {
  final String id;
  final String vehicleNumber;
  final String vehicleType;
  final String? make;
  final String? model;
  final String? color;
  final String? flatId;
  final String? flatNumber;
  final String? wingName;
  final String? ownerName;
  final String category; // resident | tenant
  final bool hasParking;
  final String? parkingSlot;
  final String? allocationId;
  final DateTime? endDate;
  final int? monthlyCharge;

  const VehicleParkingEntity({
    required this.id,
    required this.vehicleNumber,
    required this.vehicleType,
    this.make,
    this.model,
    this.color,
    this.flatId,
    this.flatNumber,
    this.wingName,
    this.ownerName,
    required this.category,
    required this.hasParking,
    this.parkingSlot,
    this.allocationId,
    this.endDate,
    this.monthlyCharge,
  });

  bool get isTenant => category == 'tenant';
  String get flatLabel =>
      [if (wingName != null) wingName, if (flatNumber != null) flatNumber].where((s) => s != null).join(' — ');
}
