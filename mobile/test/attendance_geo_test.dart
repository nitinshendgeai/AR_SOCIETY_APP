import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/auth/domain/entities/user_entity.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/features/staff/data/attendance_geo_api.dart';
import 'package:ar_society_app/features/staff/data/datasources/staff_remote_datasource.dart';
import 'package:ar_society_app/features/staff/data/location_service.dart';
import 'package:ar_society_app/features/staff/data/models/staff_models.dart';
import 'package:ar_society_app/features/staff/data/repositories/staff_repository.dart';
import 'package:ar_society_app/features/staff/domain/entities/attendance_geo.dart';
import 'package:ar_society_app/features/staff/presentation/providers/staff_providers.dart';
import 'package:ar_society_app/features/staff/presentation/screens/attendance_location_screen.dart';
import 'package:ar_society_app/features/staff/presentation/screens/attendance_screen.dart';

AttendanceModel _record({Map<String, dynamic>? geoIn}) => AttendanceModel.fromJson({
      'id': 'a1', 'staff_id': 's1', 'society_id': 'soc', 'attendance_date': '2026-11-17', 'status': 'present',
      'check_in_time': '2026-11-17T04:00:00Z', 'is_manual_entry': false, 'is_approved': false,
      if (geoIn != null) 'geo_in': geoIn,
    });

/// A server that remembers what check-in sent, and answers with a verdict.
class FakeStaffSource extends StaffRemoteDataSource {
  FakeStaffSource() : super(dio: Dio());
  final punches = <Map<String, dynamic>?>[];
  Map<String, dynamic>? verdict;

  @override
  Future<AttendanceModel> checkIn(String staffId, {String? notes, Map<String, dynamic>? location}) async {
    punches.add(location);
    return _record(geoIn: verdict);
  }

  @override
  Future<List<AttendanceModel>> getAttendanceHistory(String staffId, {int skip = 0, int limit = 30}) async => [];
}

class FakeGeoApi extends AttendanceGeoApi {
  FakeGeoApi(this.statusNow, {this.served}) : super(dio: Dio());
  final GeoStatus statusNow;
  final GeoConfig? served;
  @override
  Future<GeoStatus> status() async => statusNow;
  @override
  Future<GeoConfig> config(String societyId) async => served!;
}

class FakeLocation implements LocationService {
  FakeLocation({this.reading, this.error});
  final GeoReading? reading;
  final LocationUnavailable? error;
  double? askedFor;
  @override
  Future<GeoReading> read({required double wantAccuracyM, Duration timeout = const Duration(seconds: 20), void Function(double)? onAccuracy}) async {
    askedFor = wantAccuracyM;
    onAccuracy?.call(12);
    if (error != null) throw error!;
    return reading!;
  }
}

const _user = UserEntity(id: 'u', email: 'u@t.com', fullName: 'Guard', roles: ['Security Staff'], societyId: 'soc');

Future<FakeStaffSource> _pump(WidgetTester t, GeoStatus status, FakeLocation loc, {Map<String, dynamic>? verdict}) async {
  t.view.physicalSize = const Size(420, 2000);
  t.view.devicePixelRatio = 1.0;
  addTearDown(t.view.resetPhysicalSize);
  addTearDown(t.view.resetDevicePixelRatio);
  final source = FakeStaffSource()..verdict = verdict;
  await t.pumpWidget(ProviderScope(
    overrides: [
      currentUserProvider.overrideWithValue(_user),
      staffRepositoryProvider.overrideWithValue(StaffRepository(ds: source)),
      attendanceGeoApiProvider.overrideWithValue(FakeGeoApi(status)),
      locationServiceProvider.overrideWithValue(loc),
    ],
    child: MaterialApp(theme: AppTheme.lightTheme, home: const AttendanceScreen(staffId: 's1')),
  ));
  await t.pumpAndSettle();
  return source;
}

void main() {
  test('distance in metres agrees with the server', () {
    expect(distanceMetres(19.076, 72.8777, 19.076 + 100 * 0.000009, 72.8777), closeTo(100, 1));
  });

  testWidgets('with no location check, check-in sends no location and asks the phone for nothing', (t) async {
    final loc = FakeLocation(reading: const GeoReading(latitude: 1, longitude: 1));
    final source = await _pump(t, const GeoStatus(enabled: false, mode: 'off', maxAccuracyM: 20), loc);
    await t.tap(find.text('Check In').last);
    await t.pumpAndSettle();
    expect(source.punches, [null]);
    expect(loc.askedFor, isNull);
  });

  testWidgets('with the check on, the phone is read and the location goes with the check-in', (t) async {
    final loc = FakeLocation(reading: const GeoReading(latitude: 19.076, longitude: 72.8777, accuracyM: 6));
    final source = await _pump(t, const GeoStatus(enabled: true, mode: 'flag', maxAccuracyM: 20), loc,
        verdict: {'status': 'inside', 'distance_m': 4.0, 'spot_name': 'Main gate'});
    await t.tap(find.text('Check In').last);
    await t.pumpAndSettle();
    expect(loc.askedFor, 20);                                                 // waits for the society's accuracy limit
    expect(source.punches.single, {'latitude': 19.076, 'longitude': 72.8777, 'accuracy_m': 6.0, 'mocked': false});
    expect(find.textContaining('At Main gate · 4 m'), findsOneWidget);       // the staff member is told where they were
  });

  testWidgets('outside the spot: still checked in under flag, and told the manager will see it', (t) async {
    final loc = FakeLocation(reading: const GeoReading(latitude: 1, longitude: 1, accuracyM: 5));
    await _pump(t, const GeoStatus(enabled: true, mode: 'flag', maxAccuracyM: 20), loc,
        verdict: {'status': 'outside', 'distance_m': 35.0, 'spot_name': 'Main gate'});
    await t.tap(find.text('Check In').last);
    await t.pumpAndSettle();
    expect(find.textContaining('35 m from main gate'), findsOneWidget);
    expect(find.textContaining('Your manager will see this'), findsOneWidget);
  });

  testWidgets('location off: flag goes ahead without it, block stops with the reason', (t) async {
    final off = FakeLocation(error: const LocationUnavailable("Turn on your phone's location (GPS), then try again."));
    final flagged = await _pump(t, const GeoStatus(enabled: true, mode: 'flag', maxAccuracyM: 20), off);
    await t.tap(find.text('Check In').last);
    await t.pumpAndSettle();
    expect(flagged.punches, [null]);                                          // still checks in; the server marks "no location"
    expect(find.textContaining('Going ahead without it'), findsOneWidget);

    await t.pumpWidget(const SizedBox());
    final blocked = await _pump(t, const GeoStatus(enabled: true, mode: 'block', maxAccuracyM: 20), off);
    await t.tap(find.text('Check In').last);
    await t.pumpAndSettle();
    expect(blocked.punches, isEmpty);                                         // refused before the server is asked
    expect(find.textContaining("Turn on your phone's location"), findsOneWidget);
  });

  testWidgets('the setup screen lists the spots; a manager can read it but not change it', (t) async {
    t.view.physicalSize = const Size(420, 2000);
    t.view.devicePixelRatio = 1.0;
    addTearDown(t.view.resetPhysicalSize);
    addTearDown(t.view.resetDevicePixelRatio);
    final cfg = GeoConfig(mode: 'flag', maxAccuracyM: 20, spots: const [
      GeoSpot(id: 'p1', name: 'Main gate', latitude: 19.076, longitude: 72.8777, radiusM: 10),
    ]);
    Future<void> open(String role) async {
      await t.pumpWidget(ProviderScope(
        overrides: [
          currentUserProvider.overrideWithValue(UserEntity(id: 'u', email: 'u@t.com', fullName: 'U', roles: [role], societyId: 'soc')),
          attendanceGeoApiProvider.overrideWithValue(FakeGeoApi(const GeoStatus(enabled: true, mode: 'flag', maxAccuracyM: 20), served: cfg)),
          locationServiceProvider.overrideWithValue(FakeLocation(reading: const GeoReading(latitude: 19.076 + 0.000045, longitude: 72.8777, accuracyM: 4))),
        ],
        child: MaterialApp(theme: AppTheme.lightTheme, home: const AttendanceLocationScreen()),
      ));
      await t.pumpAndSettle();
    }

    await open('Society Admin');
    expect(find.byKey(const Key('geo-spot-Main gate')), findsOneWidget);
    expect(find.byKey(const Key('geo-add')), findsOneWidget);
    await t.tap(find.byKey(const Key('geo-check-here')));                     // 5 m north of the gate
    await t.pumpAndSettle();
    expect(find.textContaining('5 m from Main gate (allowed 10 m): inside'), findsOneWidget);

    await t.pumpWidget(const SizedBox());
    await open('Manager');
    expect(find.byKey(const Key('geo-spot-Main gate')), findsOneWidget);
    expect(find.byKey(const Key('geo-add')), findsNothing);
    expect(find.byIcon(Icons.edit_outlined), findsNothing);
  });
}
