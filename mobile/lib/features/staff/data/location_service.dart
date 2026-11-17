import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:geolocator/geolocator.dart';
import 'package:ar_society_app/features/staff/domain/entities/attendance_geo.dart';

/// The phone's location could not be read; [message] says what to do about it.
class LocationUnavailable implements Exception {
  final String message;
  const LocationUnavailable(this.message);
  @override
  String toString() => message;
}

/// Reads the phone's position. A seam so tests can stand in for the GPS.
abstract class LocationService {
  /// Waits (up to [timeout]) for a reading at least as accurate as [wantAccuracyM] metres and returns the best seen,
  /// even if it never got that good: the server decides what to do with a poor one. [onAccuracy] reports each reading's
  /// accuracy so the screen can show progress.
  Future<GeoReading> read({required double wantAccuracyM, Duration timeout, void Function(double accuracyM)? onAccuracy});
}

class DeviceLocationService implements LocationService {
  const DeviceLocationService();

  @override
  Future<GeoReading> read({
    required double wantAccuracyM,
    Duration timeout = const Duration(seconds: 20),
    void Function(double accuracyM)? onAccuracy,
  }) async {
    if (!await Geolocator.isLocationServiceEnabled()) {
      throw const LocationUnavailable("Turn on your phone's location (GPS), then try again.");
    }
    var permission = await Geolocator.checkPermission();
    if (permission == LocationPermission.denied) permission = await Geolocator.requestPermission();
    if (permission == LocationPermission.denied) {
      throw const LocationUnavailable('Allow location for this app to check in, then try again.');
    }
    if (permission == LocationPermission.deniedForever) {
      throw const LocationUnavailable(
          'Location is blocked for this app. Open Settings, Apps, this app, Permissions, Location, and choose '
          '"Allow only while using the app" with Precise location on.');
    }

    final done = Completer<void>();
    Position? best;
    final sub = Geolocator.getPositionStream(
      locationSettings: const LocationSettings(accuracy: LocationAccuracy.best, distanceFilter: 0),
    ).listen((p) {
      if (best == null || p.accuracy < best!.accuracy) best = p;
      onAccuracy?.call(best!.accuracy);
      if (best!.accuracy <= wantAccuracyM && !done.isCompleted) done.complete();
    }, onError: (Object e) {
      if (!done.isCompleted) done.complete();
    });
    final timer = Timer(timeout, () {
      if (!done.isCompleted) done.complete();
    });
    await done.future;
    timer.cancel();
    await sub.cancel();

    final p = best;
    if (p == null) throw const LocationUnavailable("Couldn't get your location. Go to open sky and try again.");
    return GeoReading(latitude: p.latitude, longitude: p.longitude, accuracyM: p.accuracy, mocked: p.isMocked);
  }
}

final locationServiceProvider = Provider<LocationService>((_) => const DeviceLocationService());
