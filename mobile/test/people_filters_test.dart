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
import 'package:ar_society_app/shared/widgets/app_widgets.dart' show AppFilterPill;

/// What the lists asked the server for, so a tapped filter can be checked without a network.
class _Recorder extends ResidentMasterRemoteDataSource {
  _Recorder() : super(dio: Dio());
  final residentCalls = <Map<String, Object?>>[];
  final tenantCalls = <Map<String, Object?>>[];
  final residentCountCalls = <Map<String, Object?>>[];
  final tenantCountCalls = <Map<String, Object?>>[];
  int residentTotal = 7;
  int tenantTotal = 3;

  @override
  Future<int> countResidents({
    String? flatId, String? wingId, String? residentType, bool? isActive, bool? movedIn, String? search,
  }) async {
    residentCountCalls.add({
      'flat': flatId, 'wing': wingId, 'type': residentType, 'movedIn': movedIn, 'active': isActive, 'search': search,
    });
    return residentTotal;
  }

  @override
  Future<int> countTenants({
    String? flatId, String? wingId, bool? isActive, bool? movedIn, String? agreement, String? police,
    bool? kycVerified, String? search,
  }) async {
    tenantCountCalls.add({
      'flat': flatId, 'wing': wingId, 'movedIn': movedIn, 'agreement': agreement, 'police': police,
      'kyc': kycVerified, 'active': isActive, 'search': search,
    });
    return tenantTotal;
  }

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

/// A server whose lists answer but whose counts fail.
class _FailingCounts extends _Recorder {
  @override
  Future<int> countResidents({
    String? flatId, String? wingId, String? residentType, bool? isActive, bool? movedIn, String? search,
  }) async => throw Exception('no count');

  @override
  Future<int> countTenants({
    String? flatId, String? wingId, bool? isActive, bool? movedIn, String? agreement, String? police,
    bool? kycVerified, String? search,
  }) async => throw Exception('no count');
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

Finder _chip(String key, String value) =>
    find.descendant(of: find.byKey(ValueKey(key)), matching: find.text(value));

void main() {
  pagingTests();
  testWidgets('the Residents list shows how many residents and tenants there are', (tester) async {
    final ds = _Recorder();
    await tester.pumpWidget(_app(ds, const ResidentListScreen()));
    await tester.pumpAndSettle();
    expect(_chip('people-count-residents', '7'), findsOneWidget);
    expect(_chip('people-count-tenants', '3'), findsOneWidget);
  });

  testWidgets('the counts follow the filters: a wing narrows both, a type only the residents', (tester) async {
    final ds = _Recorder();
    await tester.pumpWidget(_app(ds, const ResidentListScreen()));
    await tester.pumpAndSettle();

    await tester.tap(find.byKey(const ValueKey('filter-wing')));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Wing A').last);
    await tester.pumpAndSettle();
    expect(ds.residentCountCalls.last['wing'], 'wa');
    expect(ds.tenantCountCalls.last['wing'], 'wa');                       // the pair reads as one picture of the wing

    ds.residentTotal = 2;
    await tester.tap(find.widgetWithText(AppFilterPill, 'Owner'));
    await tester.pumpAndSettle();
    expect(ds.residentCountCalls.last['type'], 'owner');
    expect(ds.residentCountCalls.last['wing'], 'wa');                     // filters combine
    expect(ds.tenantCountCalls.last['wing'], 'wa');
    expect(_chip('people-count-residents', '2'), findsOneWidget);          // the number follows
    expect(_chip('people-count-tenants', '3'), findsOneWidget);
  });

  testWidgets('the Tenants list counts under its own filters, and the residents under the shared ones', (tester) async {
    await tester.binding.setSurfaceSize(const Size(900, 1400));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    final ds = _Recorder();
    await tester.pumpWidget(_app(ds, const TenantListScreen()));
    await tester.pumpAndSettle();
    expect(_chip('people-count-tenants', '3'), findsOneWidget);
    expect(_chip('people-count-residents', '7'), findsOneWidget);

    final residentAsks = ds.residentCountCalls.length;
    ds.tenantTotal = 1;
    await tester.tap(find.byKey(const ValueKey('tenant-more-filters')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const ValueKey('filter-police-pending')));
    await tester.pumpAndSettle();
    expect(ds.tenantCountCalls.last['police'], 'pending');
    expect(_chip('people-count-tenants', '1'), findsOneWidget);
    expect(ds.residentCountCalls.length, residentAsks);                   // a police filter does not touch residents
  });

  testWidgets('a count that cannot be fetched shows a dash, not a wrong number', (tester) async {
    final ds = _FailingCounts();
    await tester.pumpWidget(_app(ds, const ResidentListScreen()));
    await tester.pumpAndSettle();
    expect(_chip('people-count-residents', '—'), findsOneWidget);
    expect(_chip('people-count-tenants', '—'), findsOneWidget);
  });

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


/// A server holding [total] people, handing them out the way the real one does: `skip` then at most `limit`.
class _Paged extends ResidentMasterRemoteDataSource {
  _Paged(this.total) : super(dio: Dio());
  final int total;
  final skips = <int>[];

  @override
  Future<List<ResidentModel>> listResidents({
    String? flatId, String? wingId, String? residentType, bool? isActive, bool? movedIn, String? search,
    int skip = 0, int limit = 50,
  }) async {
    skips.add(skip);
    final end = (skip + limit) > total ? total : skip + limit;
    return [
      for (var i = skip; i < end; i++)
        ResidentModel(id: 'r$i', flatId: 'f1', fullName: 'Person $i', residentType: ResidentType.owner, isPrimary: true, isActive: true),
    ];
  }
}

void pagingTests() {
  test('the Residents list loads 50 at a time until every resident has been fetched', () async {
    final ds = _Paged(120);
    final n = ResidentListNotifier(ResidentMasterRepository(ds: ds));
    await n.load();
    var s = n.state as ResidentListLoaded;
    expect(s.residents.length, 50);
    expect(s.hasMore, isTrue);

    await n.loadMore();
    s = n.state as ResidentListLoaded;
    expect(s.residents.length, 100);
    expect(s.hasMore, isTrue);

    await n.loadMore();
    s = n.state as ResidentListLoaded;
    expect(s.residents.length, 120);
    expect(s.hasMore, isFalse);                                  // a short page means that was the last
    expect(ds.skips, [0, 50, 100]);
    expect({for (final r in s.residents) r.id}.length, 120);     // nobody twice, nobody missing

    await n.loadMore();                                          // nothing more to ask for
    expect(ds.skips.length, 3);
  });

  test('a list of exactly one page has nothing more to load', () async {
    final n = ResidentListNotifier(ResidentMasterRepository(ds: _Paged(30)));
    await n.load();
    final s = n.state as ResidentListLoaded;
    expect(s.residents.length, 30);
    expect(s.hasMore, isFalse);
  });
}
