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
