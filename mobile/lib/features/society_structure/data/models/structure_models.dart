// ── Wing ──────────────────────────────────────────────────────────────────────

class WingModel {
  final String id;
  final String name;
  final String? code;
  final String? description;
  final int? totalFloors;
  final String societyId;
  final bool isActive;
  final int flatCount;
  final int floorCount;

  const WingModel({
    required this.id,
    required this.name,
    this.code,
    this.description,
    this.totalFloors,
    required this.societyId,
    this.isActive = true,
    this.flatCount = 0,
    this.floorCount = 0,
  });

  factory WingModel.fromJson(Map<String, dynamic> j) => WingModel(
        id: j['id'] as String,
        name: j['name'] as String,
        code: j['code'] as String?,
        description: j['description'] as String?,
        totalFloors: j['total_floors'] as int?,
        societyId: j['society_id'] as String,
        isActive: j['is_active'] as bool? ?? true,
        flatCount: j['flat_count'] as int? ?? 0,
        floorCount: j['floor_count'] as int? ?? 0,
      );

  String get displayName => code != null ? '$name ($code)' : name;
}

// ── Floor ─────────────────────────────────────────────────────────────────────

class FloorModel {
  final String id;
  final int floorNumber;
  final String? floorName;
  final String wingId;
  final String societyId;
  final bool isActive;
  final int flatCount;

  const FloorModel({
    required this.id,
    required this.floorNumber,
    this.floorName,
    required this.wingId,
    required this.societyId,
    this.isActive = true,
    this.flatCount = 0,
  });

  factory FloorModel.fromJson(Map<String, dynamic> j) => FloorModel(
        id: j['id'] as String,
        floorNumber: j['floor_number'] as int,
        floorName: j['floor_name'] as String?,
        wingId: j['wing_id'] as String,
        societyId: j['society_id'] as String,
        isActive: j['is_active'] as bool? ?? true,
        flatCount: j['flat_count'] as int? ?? 0,
      );

  String get displayName {
    if (floorName != null && floorName!.isNotEmpty) return floorName!;
    if (floorNumber == 0) return 'Ground Floor';
    final suffix = _ordinal(floorNumber);
    return '$suffix Floor';
  }

  static String _ordinal(int n) {
    if (n == 1) return '1st';
    if (n == 2) return '2nd';
    if (n == 3) return '3rd';
    return '${n}th';
  }
}

// ── Flat ──────────────────────────────────────────────────────────────────────

class FlatModel {
  final String id;
  final String flatNumber;
  final int? floor;
  final String? flatType;
  final double? areaSqft;
  final String? occupancyStatus;
  final String? remarks;
  final String wingId;
  final String? wingName;
  final bool isActive;

  const FlatModel({
    required this.id,
    required this.flatNumber,
    this.floor,
    this.flatType,
    this.areaSqft,
    this.occupancyStatus,
    this.remarks,
    required this.wingId,
    this.wingName,
    this.isActive = true,
  });

  factory FlatModel.fromJson(Map<String, dynamic> j) => FlatModel(
        id: j['id'] as String,
        flatNumber: j['flat_number'] as String,
        floor: j['floor'] as int?,
        flatType: j['flat_type'] as String?,
        areaSqft: (j['area_sqft'] as num?)?.toDouble(),
        occupancyStatus: j['occupancy_status'] as String?,
        remarks: j['remarks'] as String?,
        wingId: j['wing_id'] as String,
        wingName: j['wing_name'] as String?,
        isActive: j['is_active'] as bool? ?? true,
      );

  String get displayName =>
      wingName != null ? '$wingName-$flatNumber' : flatNumber;

  bool get isVacant => occupancyStatus == 'vacant' || occupancyStatus == null;
}
