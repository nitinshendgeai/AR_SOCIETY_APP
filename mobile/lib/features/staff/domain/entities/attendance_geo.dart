import 'dart:math' as math;

/// What the phone reports at a check-in or check-out.
class GeoReading {
  final double latitude, longitude;
  final double? accuracyM;

  /// Android says this location is faked (a "mock location" app).
  final bool mocked;
  const GeoReading({required this.latitude, required this.longitude, this.accuracyM, this.mocked = false});

  Map<String, dynamic> toJson() => {
        'latitude': latitude,
        'longitude': longitude,
        if (accuracyM != null) 'accuracy_m': accuracyM,
        'mocked': mocked,
      };
}

/// The server's verdict on a reading: inside, outside, no_location, low_accuracy or mocked.
class AttendanceGeoResult {
  final String status;
  final double? distanceM, accuracyM;
  final String? spotName;
  final bool mocked;
  const AttendanceGeoResult({required this.status, this.distanceM, this.accuracyM, this.spotName, this.mocked = false});

  factory AttendanceGeoResult.fromJson(Map<String, dynamic> j) => AttendanceGeoResult(
        status: j['status'] as String,
        distanceM: (j['distance_m'] as num?)?.toDouble(),
        accuracyM: (j['accuracy_m'] as num?)?.toDouble(),
        spotName: j['spot_name'] as String?,
        mocked: j['mocked'] as bool? ?? false,
      );

  bool get isInside => status == 'inside';

  /// A short line for the manager and the staff member.
  String get label => switch (status) {
        'inside' => 'At ${spotName ?? 'the spot'}${distanceM == null ? '' : ' · ${distanceM!.round()} m'}',
        'outside' => '${distanceM?.round() ?? '?'} m from ${spotName ?? 'the spot'}',
        'mocked' => 'Fake location detected',
        'low_accuracy' => 'Location not accurate enough${accuracyM == null ? '' : ' (±${accuracyM!.round()} m)'}',
        _ => 'No location',
      };
}

/// Great-circle distance in metres, the same formula the server uses.
double distanceMetres(double lat1, double lng1, double lat2, double lng2) {
  const r = 6371008.8;
  double rad(double d) => d * math.pi / 180;
  final p1 = rad(lat1), p2 = rad(lat2);
  final a = math.pow(math.sin((p2 - p1) / 2), 2) + math.cos(p1) * math.cos(p2) * math.pow(math.sin(rad(lng2 - lng1) / 2), 2);
  return 2 * r * math.asin(math.sqrt(a));
}
