import 'package:ar_society_app/features/parking/domain/entities/parking_entities.dart';

// ── Gate vehicle lookup model — matches GateVehicleLookupOut ───────────────

class GateVehicleLookupModel {
  final String vehicleNumber;
  final bool authorized;
  final String category;
  final String? vehicleType;
  final String? flatNumber;
  final String? wingName;
  final String? ownerName;
  final String? parkingSlot;
  final String? visitorPurpose;
  final String? visitorCheckInTime;
  final String message;

  const GateVehicleLookupModel({
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

  factory GateVehicleLookupModel.fromJson(Map<String, dynamic> j) =>
      GateVehicleLookupModel(
        vehicleNumber: j['vehicle_number'] as String,
        authorized: j['authorized'] as bool,
        category: j['category'] as String,
        vehicleType: j['vehicle_type'] as String?,
        flatNumber: j['flat_number'] as String?,
        wingName: j['wing_name'] as String?,
        ownerName: j['owner_name'] as String?,
        parkingSlot: j['parking_slot'] as String?,
        visitorPurpose: j['visitor_purpose'] as String?,
        visitorCheckInTime: j['visitor_check_in_time'] as String?,
        message: j['message'] as String,
      );

  GateVehicleLookupEntity toEntity() => GateVehicleLookupEntity(
        vehicleNumber: vehicleNumber,
        authorized: authorized,
        category: GateVehicleCategory.fromString(category),
        vehicleType: vehicleType,
        flatNumber: flatNumber,
        wingName: wingName,
        ownerName: ownerName,
        parkingSlot: parkingSlot,
        visitorPurpose: visitorPurpose,
        visitorCheckInTime: visitorCheckInTime != null
            ? DateTime.tryParse(visitorCheckInTime!)
            : null,
        message: message,
      );
}

// ── Access log model — matches AccessLogOut ─────────────────────────────────

class ParkingAccessLogModel {
  final String id;
  final String vehicleNumber;
  final String accessType;
  final bool isAuthorized;
  final String accessTime;

  const ParkingAccessLogModel({
    required this.id,
    required this.vehicleNumber,
    required this.accessType,
    required this.isAuthorized,
    required this.accessTime,
  });

  factory ParkingAccessLogModel.fromJson(Map<String, dynamic> j) =>
      ParkingAccessLogModel(
        id: j['id'] as String,
        vehicleNumber: j['vehicle_number'] as String,
        accessType: j['access_type'] as String,
        isAuthorized: j['is_authorized'] as bool,
        accessTime: j['access_time'] as String,
      );

  ParkingAccessLogEntity toEntity() => ParkingAccessLogEntity(
        id: id,
        vehicleNumber: vehicleNumber,
        accessType: accessType == 'exit' ? GateAccessType.exit : GateAccessType.entry,
        isAuthorized: isAuthorized,
        accessTime: DateTime.parse(accessTime),
      );
}

// ── Zone model — matches ZoneOut ────────────────────────────────────────────

class ParkingZoneModel {
  final String id;
  final String societyId;
  final String name;
  final String? code;
  final int totalSlots;

  const ParkingZoneModel({
    required this.id,
    required this.societyId,
    required this.name,
    this.code,
    required this.totalSlots,
  });

  factory ParkingZoneModel.fromJson(Map<String, dynamic> j) => ParkingZoneModel(
        id: j['id'] as String,
        societyId: j['society_id'] as String,
        name: j['name'] as String,
        code: j['code'] as String?,
        totalSlots: j['total_slots'] as int? ?? 0,
      );

  ParkingZoneEntity toEntity() => ParkingZoneEntity(
        id: id, societyId: societyId, name: name, code: code, totalSlots: totalSlots,
      );
}

// ── Slot model — matches SlotOut ────────────────────────────────────────────

class ParkingSlotModel {
  final String id;
  final String societyId;
  final String zoneId;
  final String slotNumber;
  final String slotType;
  final String status;
  final bool isCovered;
  final bool isEvCharging;

  const ParkingSlotModel({
    required this.id,
    required this.societyId,
    required this.zoneId,
    required this.slotNumber,
    required this.slotType,
    required this.status,
    this.isCovered = false,
    this.isEvCharging = false,
  });

  factory ParkingSlotModel.fromJson(Map<String, dynamic> j) => ParkingSlotModel(
        id: j['id'] as String,
        societyId: j['society_id'] as String,
        zoneId: j['zone_id'] as String,
        slotNumber: j['slot_number'] as String,
        slotType: j['slot_type'] as String,
        status: j['status'] as String,
        isCovered: j['is_covered'] as bool? ?? false,
        isEvCharging: j['is_ev_charging'] as bool? ?? false,
      );

  ParkingSlotEntity toEntity() => ParkingSlotEntity(
        id: id, societyId: societyId, zoneId: zoneId, slotNumber: slotNumber,
        slotType: slotType, status: ParkingSlotStatus.fromString(status),
        isCovered: isCovered, isEvCharging: isEvCharging,
      );
}

// ── Allocation model — matches AllocationOut ────────────────────────────────

class ParkingAllocationModel {
  final String id;
  final String societyId;
  final String slotId;
  final String? flatId;
  final String? vehicleId;
  final String allocationType;
  final String status;
  final String startDate;
  final String? endDate;
  final int? monthlyCharge;
  final String? slotNumber;
  final String? vehicleNumber;
  final String? flatNumber;
  final String? wingName;

  const ParkingAllocationModel({
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

  factory ParkingAllocationModel.fromJson(Map<String, dynamic> j) => ParkingAllocationModel(
        id: j['id'] as String,
        societyId: j['society_id'] as String,
        slotId: j['slot_id'] as String,
        flatId: j['flat_id'] as String?,
        vehicleId: j['vehicle_id'] as String?,
        allocationType: j['allocation_type'] as String,
        status: j['status'] as String,
        startDate: j['start_date'] as String,
        endDate: j['end_date'] as String?,
        monthlyCharge: j['monthly_charge'] as int?,
        slotNumber: j['slot_number'] as String?,
        vehicleNumber: j['vehicle_number'] as String?,
        flatNumber: j['flat_number'] as String?,
        wingName: j['wing_name'] as String?,
      );

  ParkingAllocationEntity toEntity() => ParkingAllocationEntity(
        id: id,
        societyId: societyId,
        slotId: slotId,
        flatId: flatId,
        vehicleId: vehicleId,
        allocationType: allocationType,
        status: status,
        startDate: DateTime.parse(startDate),
        endDate: endDate != null ? DateTime.tryParse(endDate!) : null,
        monthlyCharge: monthlyCharge,
        slotNumber: slotNumber,
        vehicleNumber: vehicleNumber,
        flatNumber: flatNumber,
        wingName: wingName,
      );
}
