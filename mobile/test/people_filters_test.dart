import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/auth/domain/entities/user_entity.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/features/resident_master/data/datasources/resident_master_remote_datasource.dart';
import 'package:ar_society_app/features/resident_master/data/models/resident_master_models.dart';
import 'package:ar_society_app/features/resident_master/data/repositories/resident_master_repository.dart';
import 'package:ar_society_app/features/resident_master/presentation/providers/resident_master_providers.dart';
import 'package:ar_society_app/features/resident_master/presentation/screens/resident_list_screen.dart';
import 'package:ar_society_app/features/resident_master/presentation/screens/tenant_list_screen.dart';
import 'package:ar_society_app/features/society_structure/data/models/structure_models.dart';
import 'package:ar_society_app/features/society_structure/presentation/providers/structure_providers.dart';

/// What the lists asked the server for, so a tapped filter can be checked without a network.
class _Recorder extends ResidentMasterRemoteDataSource {
  _Recorder() : super(dio: Dio());
  final residentCalls = <Map<String, Object?>>[];
  final tenantCalls = <Map<String, Object?>>[];

  @override
  Future<List<ResidentModel>> listResidents({
    String? flatId, String? wingId, String? residentType, bool? isActive, bool? movedIn, String? search,
    int skip = 0, int limit = 50,
  }) async {
    residentCalls.add({'flat': flatId, 'wing': wingId, 'movedIn': movedIn, 'type': residentType, 'active': isActive});
    return [];
  }

  @override
  Future<List<TenantModel>> listTenants({
    String? flatId, String? wingId, bool? isActive, bool? movedIn, String? agreement, String? police,
    bool? kycVerified, String? search, int skip = 0, int limit = 50,
  }) async {
    tenantCalls.add({
      'flat': flatId, 'wing': wingId, 'movedIn': movedIn, 'agreement': agreement, 'police': police, 'kyc': kycVerified,
    });
    return [];
  }
}

class _Flats extends FlatsBySocietyNotifier {
  final List<FlatModel> data;
  _Flats(this.data);
  @override
  Future<List<FlatModel>> build() async => data;
}

FlatModel _flat(String id, String number, String wingId, String wingName) =>
    FlatModel(id: id, flatNumber: number, wingId: wingId, wingName: wingName, occupancyStatus: 'vacant');

Widget _app(_Recorder ds, Widget home) => ProviderScope(
      overrides: [
        currentUserProvider.overrideWithValue(
            const UserEntity(id: 'u', email: 'u@t.com', fullName: 'U', roles: ['Society Admin'], societyId: 's1')),
        flatsBySocietyProvider.overrideWith(() => _Flats([
              _flat('f1', '101', 'wa', 'Wing A'),
              _flat('f2', '102', 'wa', 'Wing A'),
              _flat('f3', '201', 'wb', 'Wing B'),
            ])),
        residentMasterRepositoryProvider.overrideWithValue(ResidentMasterRepository(ds: ds)),
      ],
      child: MaterialApp(theme: AppTheme.lightTheme, home: home),
    );

void main() {
  testWidgets('the Residents list asks the server for a moved-in or not-yet-moved-in filter', (tester) async {
    final ds = _Recorder();
    await tester.pumpWidget(_app(ds, const ResidentListScreen()));
    await tester.pumpAndSettle();
    expect(ds.residentCalls.last['movedIn'], isNull);

    await tester.tap(find.byKey(const ValueKey('filter-moved-in-true')));
    await tester.pumpAndSettle();
    expect(ds.residentCalls.last['movedIn'], true);

    await tester.tap(find.byKey(const ValueKey('filter-moved-in-false')));
    await tester.pumpAndSettle();
    expect(ds.residentCalls.last['movedIn'], false);

    await tester.tap(find.byKey(const ValueKey('filter-moved-in-all')));
    await tester.pumpAndSettle();
    expect(ds.residentCalls.last['movedIn'], isNull);
  });

  testWidgets('choosing a wing narrows the Residents list to it and opens that wing\'s flats', (tester) async {
    final ds = _Recorder();
    await tester.pumpWidget(_app(ds, const ResidentListScreen()));
    await tester.pumpAndSettle();

    await tester.tap(find.byKey(const ValueKey('filter-wing')));
    await tester.pumpAndSettle();
    expect(find.text('Wing A').last, findsOneWidget);
    await tester.tap(find.text('Wing A').last);
    await tester.pumpAndSettle();
    expect(ds.residentCalls.last['wing'], 'wa');
    expect(ds.residentCalls.last['flat'], isNull);

    await tester.tap(find.byKey(const ValueKey('filter-flat-wa')));
    await tester.pumpAndSettle();
    expect(find.text('102'), findsOneWidget);
    expect(find.text('201'), findsNothing);                              // another wing's flat is not offered
    await tester.tap(find.text('102').last);
    await tester.pumpAndSettle();
    expect(ds.residentCalls.last['flat'], 'f2');
    expect(ds.residentCalls.last['wing'], 'wa');
  });

  testWidgets('the Tenants list filters by move-in, agreement, police verification and KYC', (tester) async {
    await tester.binding.setSurfaceSize(const Size(900, 1400));   // the filter rows need room; the default window is tiny
    addTearDown(() => tester.binding.setSurfaceSize(null));
    final ds = _Recorder();
    await tester.pumpWidget(_app(ds, const TenantListScreen()));
    await tester.pumpAndSettle();
    expect(ds.tenantCalls.last['agreement'], isNull);
    expect(find.byKey(const ValueKey('filter-agreement-expiring')), findsNothing);   // folded away until asked for

    await tester.tap(find.byKey(const ValueKey('tenant-more-filters')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const ValueKey('filter-agreement-expiring')));
    await tester.pumpAndSettle();
    expect(ds.tenantCalls.last['agreement'], 'expiring');

    await tester.tap(find.byKey(const ValueKey('filter-police-pending')));
    await tester.pumpAndSettle();
    expect(ds.tenantCalls.last['police'], 'pending');
    expect(ds.tenantCalls.last['agreement'], 'expiring');                // filters combine

    await tester.tap(find.byKey(const ValueKey('filter-kyc-false')));
    await tester.pumpAndSettle();
    expect(ds.tenantCalls.last['kyc'], false);

    await tester.tap(find.byKey(const ValueKey('filter-moved-in-true')));
    await tester.pumpAndSettle();
    expect(ds.tenantCalls.last['movedIn'], true);

    await tester.tap(find.byKey(const ValueKey('filter-agreement-all')));
    await tester.pumpAndSettle();
    expect(ds.tenantCalls.last['agreement'], isNull);
    expect(ds.tenantCalls.last['police'], 'pending');                     // the others stay
  });
}
