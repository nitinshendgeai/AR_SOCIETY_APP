import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';

import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/auth/domain/entities/user_entity.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/features/resident_master/data/datasources/resident_master_remote_datasource.dart';
import 'package:ar_society_app/features/resident_master/data/models/resident_master_models.dart';
import 'package:ar_society_app/features/resident_master/data/repositories/resident_master_repository.dart';
import 'package:ar_society_app/features/resident_master/presentation/providers/resident_master_providers.dart';
import 'package:ar_society_app/features/resident_master/presentation/screens/resident_detail_screen.dart';
import 'package:ar_society_app/features/resident_master/presentation/screens/resident_form_screen.dart';
import 'package:ar_society_app/features/resident_master/presentation/screens/resident_list_screen.dart';
import 'package:ar_society_app/features/resident_master/presentation/screens/tenant_detail_screen.dart';
import 'package:ar_society_app/features/resident_master/presentation/screens/tenant_form_screen.dart';
import 'package:ar_society_app/features/resident_master/presentation/screens/tenant_list_screen.dart';
import 'package:ar_society_app/features/resident_master/presentation/widgets/occupancy_action_sheets.dart';
import 'package:ar_society_app/features/resident_master/presentation/widgets/resident_master_widgets.dart';
import 'package:ar_society_app/features/society_structure/data/models/structure_models.dart';
import 'package:ar_society_app/features/society_structure/presentation/providers/structure_providers.dart';
import 'package:ar_society_app/features/society_structure/presentation/screens/flat_form_screen.dart';

// ── Fixtures ─────────────────────────────────────────────────────────────

UserEntity _adminUser() => const UserEntity(
      id: 'admin-1',
      email: 'admin@test.com',
      fullName: 'Admin User',
      roles: ['Society Admin'],
      societyId: 'soc-1',
    );

WingModel _wing() => const WingModel(id: 'wing-1', name: 'Wing A', societyId: 'soc-1');

FlatModel _flat({String id = 'flat-1', String? occupancyStatus = 'vacant'}) => FlatModel(
      id: id,
      flatNumber: '101',
      wingId: 'wing-1',
      wingName: 'Wing A',
      occupancyStatus: occupancyStatus,
    );

ResidentModel _resident({
  String id = 'res-1',
  String fullName = 'John Owner',
  ResidentType type = ResidentType.owner,
  bool isPrimary = true,
  bool isActive = true,
  String? moveInDate,
  String? moveOutDate,
}) =>
    ResidentModel(
      id: id,
      flatId: 'flat-1',
      fullName: fullName,
      residentType: type,
      isPrimary: isPrimary,
      isActive: isActive,
      moveInDate: moveInDate,
      moveOutDate: moveOutDate,
    );

TenantModel _tenant({
  String id = 'ten-1',
  String fullName = 'Jane Tenant',
  String? agreementEndDate,
  bool isActive = true,
  String? moveOutDate,
}) =>
    TenantModel(
      id: id,
      flatId: 'flat-1',
      fullName: fullName,
      agreementStartDate: agreementEndDate != null ? '2026-01-01' : null,
      agreementEndDate: agreementEndDate,
      isActive: isActive,
      moveOutDate: moveOutDate,
    );

AgreementModel _agreement({
  String id = 'agr-1',
  String startDate = '2026-01-01',
  String endDate = '2026-12-31',
  AgreementStatus status = AgreementStatus.active,
  String? renewalOfId,
}) =>
    AgreementModel(
      id: id,
      societyId: 'soc-1',
      flatId: 'flat-1',
      tenantId: 'ten-1',
      startDate: startDate,
      endDate: endDate,
      status: status,
      monthlyRent: '15000',
      securityDeposit: '30000',
      renewalOfId: renewalOfId,
    );

/// Fake datasource — lets the real ResidentMasterRepository's success/error
/// mapping run against canned responses, instead of hitting Dio/network.
class _FakeDataSource extends ResidentMasterRemoteDataSource {
  _FakeDataSource() : super(dio: Dio());

  List<ResidentModel> residents = [];
  List<TenantModel> tenants = [];
  List<AgreementModel> agreements = [];
  Object? throwOnCreateResident;
  Object? throwOnCreateTenant;
  Object? throwOnListAgreements;

  @override
  Future<List<ResidentModel>> listResidents({
    String? flatId, String? residentType, bool? isActive, String? search, int skip = 0, int limit = 50,
  }) async => residents;

  @override
  Future<ResidentModel> createResident(Map<String, dynamic> data) async {
    if (throwOnCreateResident != null) throw throwOnCreateResident!;
    final r = _resident(id: 'new-res', fullName: data['full_name'] as String);
    residents = [...residents, r];
    return r;
  }

  @override
  Future<ResidentModel> updateResident(String id, Map<String, dynamic> data) async =>
      _resident(id: id, fullName: data['full_name'] as String? ?? 'Updated');

  @override
  Future<List<TenantModel>> listTenants({
    String? flatId, bool? isActive, String? search, int skip = 0, int limit = 50,
  }) async => tenants;

  @override
  Future<TenantModel> createTenant(Map<String, dynamic> data) async {
    if (throwOnCreateTenant != null) throw throwOnCreateTenant!;
    final t = _tenant(id: 'new-ten', fullName: data['full_name'] as String);
    tenants = [...tenants, t];
    return t;
  }

  @override
  Future<void> residentMoveIn({required String flatId, required String residentId, required String moveInDate}) async {}

  @override
  Future<ResidentModel> getResident(String id) async =>
      residents.firstWhere((r) => r.id == id, orElse: () => _resident(id: id));

  @override
  Future<TenantModel> getTenant(String id) async =>
      tenants.firstWhere((t) => t.id == id, orElse: () => _tenant(id: id));

  @override
  Future<List<AgreementModel>> listTenantAgreements(String tenantId) async {
    if (throwOnListAgreements != null) throw throwOnListAgreements!;
    return agreements;
  }

  @override
  Future<List<OccupancyLogModel>> getFlatHistory(String flatId) async => [];

  @override
  Future<List<VehicleModel>> vehiclesByFlat(String flatId) async => [];
}

Widget _wrap(Widget child, {UserEntity? user, List<Override> overrides = const []}) {
  return ProviderScope(
    overrides: [
      currentUserProvider.overrideWithValue(user ?? _adminUser()),
      flatsBySocietyProvider.overrideWith(() => _FakeFlatsNotifier([_flat()])),
      wingsProvider.overrideWith(() => _FakeWingsNotifier([_wing()])),
      ...overrides,
    ],
    child: MaterialApp(theme: AppTheme.lightTheme, home: child),
  );
}

class _FakeFlatsNotifier extends FlatsBySocietyNotifier {
  final List<FlatModel> data;
  _FakeFlatsNotifier(this.data);
  @override
  Future<List<FlatModel>> build() async => data;
}

class _FakeWingsNotifier extends WingsNotifier {
  final List<WingModel> data;
  _FakeWingsNotifier(this.data);
  @override
  Future<List<WingModel>> build() async => data;
}

void main() {
  // ── Enum / model unit tests ───────────────────────────────────────────

  group('ResidentType', () {
    test('fromString round-trips all backend values', () {
      expect(ResidentTypeX.fromString('owner'), ResidentType.owner);
      expect(ResidentTypeX.fromString('co_owner'), ResidentType.coOwner);
      expect(ResidentTypeX.fromString('family'), ResidentType.family);
      expect(ResidentTypeX.fromString('dependent'), ResidentType.dependent);
    });

    test('canBePrimary is true only for owner/co_owner (mirrors backend rule)', () {
      expect(ResidentType.owner.canBePrimary, isTrue);
      expect(ResidentType.coOwner.canBePrimary, isTrue);
      expect(ResidentType.family.canBePrimary, isFalse);
      expect(ResidentType.dependent.canBePrimary, isFalse);
    });

    test('value maps back to the exact backend enum string', () {
      for (final t in ResidentType.values) {
        expect(ResidentTypeX.fromString(t.value), t);
      }
    });
  });

  group('AgreementStatus / PoliceVerificationStatus / VehicleType', () {
    test('AgreementStatus.fromString handles all values', () {
      expect(AgreementStatusX.fromString('active'), AgreementStatus.active);
      expect(AgreementStatusX.fromString('renewed'), AgreementStatus.renewed);
      expect(AgreementStatusX.fromString('terminated'), AgreementStatus.terminated);
      expect(AgreementStatusX.fromString('garbage'), AgreementStatus.active);
    });

    test('VehicleType round-trips', () {
      for (final t in VehicleType.values) {
        expect(VehicleTypeX.fromString(t.value), t);
      }
    });
  });

  group('rmDaysUntil / rmFormatDate', () {
    test('rmDaysUntil returns null for null input', () {
      expect(rmDaysUntil(null), isNull);
    });

    test('rmDaysUntil returns negative for a past date', () {
      final past = DateTime.now().subtract(const Duration(days: 5));
      final iso = '${past.year}-${past.month.toString().padLeft(2, '0')}-${past.day.toString().padLeft(2, '0')}';
      expect(rmDaysUntil(iso), lessThan(0));
    });

    test('rmFormatDate falls back to raw string on parse failure', () {
      expect(rmFormatDate('not-a-date'), 'not-a-date');
    });
  });

  // ── Resident list screen ──────────────────────────────────────────────

  group('ResidentListScreen', () {
    testWidgets('shows loading indicator before data resolves', (tester) async {
      final repo = ResidentMasterRepository(ds: _FakeDataSource());
      await tester.pumpWidget(_wrap(
        const ResidentListScreen(),
        overrides: [residentMasterRepositoryProvider.overrideWithValue(repo)],
      ));
      expect(find.byType(CircularProgressIndicator), findsWidgets);
    });

    testWidgets('renders resident cards once loaded, with type + primary badge', (tester) async {
      final repo = ResidentMasterRepository(
        ds: _FakeDataSource()..residents = [_resident(fullName: 'Asha Owner', isPrimary: true)],
      );
      await tester.pumpWidget(_wrap(
        const ResidentListScreen(),
        overrides: [residentMasterRepositoryProvider.overrideWithValue(repo)],
      ));
      await tester.pumpAndSettle();

      expect(find.text('Asha Owner'), findsOneWidget);
      expect(find.text('PRIMARY'), findsOneWidget);
    });

    testWidgets('shows empty state when no residents match', (tester) async {
      final repo = ResidentMasterRepository(ds: _FakeDataSource());
      await tester.pumpWidget(_wrap(
        const ResidentListScreen(),
        overrides: [residentMasterRepositoryProvider.overrideWithValue(repo)],
      ));
      await tester.pumpAndSettle();

      expect(find.text('No residents found'), findsOneWidget);
    });

    testWidgets('shows error state with retry when the repository fails', (tester) async {
      final failingRepo = ResidentMasterRepository(ds: _ThrowingResidentListDataSource());
      await tester.pumpWidget(_wrap(
        const ResidentListScreen(),
        overrides: [residentMasterRepositoryProvider.overrideWithValue(failingRepo)],
      ));
      await tester.pumpAndSettle();

      expect(find.text('Retry'), findsOneWidget);
    });
  });

  // ── Resident form validation ───────────────────────────────────────────

  group('ResidentFormScreen', () {
    testWidgets('blocks submit when name is empty', (tester) async {
      // The form is long — grow the test surface so the submit button at
      // the bottom is actually built (Sliver-based ListView virtualizes
      // children outside the viewport+cacheExtent).
      tester.view.physicalSize = const Size(800, 3000);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);

      final repo = ResidentMasterRepository(ds: _FakeDataSource());
      await tester.pumpWidget(_wrap(
        ResidentFormScreen(defaultFlat: _flat()),
        overrides: [residentMasterRepositoryProvider.overrideWithValue(repo)],
      ));
      await tester.pumpAndSettle();

      await tester.tap(find.widgetWithText(ElevatedButton, 'Add Resident'));
      await tester.pump();

      expect(find.text('Name is required'), findsOneWidget);
    });

    testWidgets('mobile field strips non-digit characters and rejects a bad length', (tester) async {
      tester.view.physicalSize = const Size(800, 3000);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);

      final repo = ResidentMasterRepository(ds: _FakeDataSource());
      await tester.pumpWidget(_wrap(
        ResidentFormScreen(defaultFlat: _flat()),
        overrides: [residentMasterRepositoryProvider.overrideWithValue(repo)],
      ));
      await tester.pumpAndSettle();

      await tester.enterText(find.byType(TextFormField).at(0), 'Valid Name');
      // "abc123abcd" mixes letters into a 10-character string — the old
      // validator only checked string length (< 10), so this passed
      // straight through to the API. The digitsOnly input formatter now
      // strips the letters as they're typed, leaving just "123".
      await tester.enterText(find.byType(TextFormField).at(1), 'abc123abcd');
      await tester.pump();

      expect(find.text('123'), findsOneWidget);

      await tester.tap(find.widgetWithText(ElevatedButton, 'Add Resident'));
      await tester.pump();

      expect(find.text('Enter a valid 10-digit mobile number'), findsOneWidget);
    });

    testWidgets('successful create shows success snackbar and pops', (tester) async {
      tester.view.physicalSize = const Size(800, 3000);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);

      final fakeDs = _FakeDataSource();
      final repo = ResidentMasterRepository(ds: fakeDs);

      // ResidentFormScreen pops via go_router's context.pop() extension, so
      // this needs a real GoRouter ancestor (a plain Navigator won't do).
      final router = GoRouter(
        initialLocation: '/',
        routes: [
          GoRoute(path: '/', builder: (_, __) => Builder(builder: (context) => ElevatedButton(
                onPressed: () => GoRouter.of(context).push('/form'),
                child: const Text('open'),
              ))),
          GoRoute(path: '/form', builder: (_, __) => ResidentFormScreen(defaultFlat: _flat())),
        ],
      );

      await tester.pumpWidget(ProviderScope(
        overrides: [
          currentUserProvider.overrideWithValue(_adminUser()),
          flatsBySocietyProvider.overrideWith(() => _FakeFlatsNotifier([_flat()])),
          wingsProvider.overrideWith(() => _FakeWingsNotifier([_wing()])),
          residentMasterRepositoryProvider.overrideWithValue(repo),
        ],
        child: MaterialApp.router(theme: AppTheme.lightTheme, routerConfig: router),
      ));
      await tester.tap(find.text('open'));
      await tester.pumpAndSettle();

      await tester.enterText(find.byType(TextFormField).first, 'New Resident');
      await tester.tap(find.widgetWithText(ElevatedButton, 'Add Resident'));
      // Deliberately NOT pumpAndSettle(): a SnackBar's auto-dismiss timer
      // schedules further frames, so pumpAndSettle would pump straight
      // through its entire 4s lifecycle and find it already gone. A few
      // bounded pumps catch it mid-flight instead.
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));
      await tester.pump(const Duration(milliseconds: 100));

      expect(find.text('Resident added successfully'), findsOneWidget);
      // The form screen was popped back to the trigger button.
      expect(find.text('open'), findsOneWidget);
    });

    testWidgets(
        'list screen shows the newly created resident without a manual refresh '
        '(regression: ref.invalidate() on a StateNotifierProvider resets state '
        'to Initial but never re-fetches, since the list only calls load() from '
        'initState — found live in M1.8)', (tester) async {
      tester.view.physicalSize = const Size(800, 3000);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);

      final fakeDs = _FakeDataSource();
      final repo = ResidentMasterRepository(ds: fakeDs);

      // Real push-based navigation, mirroring the app: ResidentListScreen
      // stays mounted underneath while ResidentFormScreen is pushed on top,
      // so its initState does not re-run when the form pops back.
      final router = GoRouter(
        initialLocation: '/',
        routes: [
          GoRoute(path: '/', builder: (_, __) => const ResidentListScreen()),
          GoRoute(path: '/form', builder: (_, __) => ResidentFormScreen(defaultFlat: _flat())),
        ],
      );

      await tester.pumpWidget(ProviderScope(
        overrides: [
          currentUserProvider.overrideWithValue(_adminUser()),
          flatsBySocietyProvider.overrideWith(() => _FakeFlatsNotifier([_flat()])),
          wingsProvider.overrideWith(() => _FakeWingsNotifier([_wing()])),
          residentMasterRepositoryProvider.overrideWithValue(repo),
        ],
        child: MaterialApp.router(theme: AppTheme.lightTheme, routerConfig: router),
      ));
      await tester.pumpAndSettle();
      expect(find.text('No residents found'), findsOneWidget);

      router.push('/form');
      await tester.pumpAndSettle();
      await tester.enterText(find.byType(TextFormField).first, 'Fresh Resident');
      await tester.tap(find.widgetWithText(ElevatedButton, 'Add Resident'));
      await tester.pumpAndSettle();

      expect(find.text('Fresh Resident'), findsOneWidget);
      expect(find.text('No residents found'), findsNothing);
      expect(find.byType(CircularProgressIndicator), findsNothing);
    });
  });

  // ── Tenant list + form ─────────────────────────────────────────────────

  group('TenantListScreen', () {
    testWidgets('renders tenant card with agreement expiry text', (tester) async {
      final futureDate = DateTime.now().add(const Duration(days: 20));
      final iso = '${futureDate.year}-${futureDate.month.toString().padLeft(2, '0')}-${futureDate.day.toString().padLeft(2, '0')}';
      final repo = ResidentMasterRepository(
        ds: _FakeDataSource()..tenants = [_tenant(fullName: 'Ravi Tenant', agreementEndDate: iso)],
      );
      await tester.pumpWidget(_wrap(
        const TenantListScreen(),
        overrides: [residentMasterRepositoryProvider.overrideWithValue(repo)],
      ));
      await tester.pumpAndSettle();

      expect(find.text('Ravi Tenant'), findsOneWidget);
      expect(find.textContaining('Agreement until'), findsOneWidget);
    });

    testWidgets('shows empty state when no tenants match', (tester) async {
      final repo = ResidentMasterRepository(ds: _FakeDataSource());
      await tester.pumpWidget(_wrap(
        const TenantListScreen(),
        overrides: [residentMasterRepositoryProvider.overrideWithValue(repo)],
      ));
      await tester.pumpAndSettle();

      expect(find.text('No tenants found'), findsOneWidget);
    });
  });

  group('TenantFormScreen', () {
    testWidgets('blocks submit when name is empty', (tester) async {
      tester.view.physicalSize = const Size(800, 3000);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);

      final repo = ResidentMasterRepository(ds: _FakeDataSource());
      await tester.pumpWidget(_wrap(
        TenantFormScreen(defaultFlat: _flat()),
        overrides: [residentMasterRepositoryProvider.overrideWithValue(repo)],
      ));
      await tester.pumpAndSettle();

      await tester.tap(find.widgetWithText(ElevatedButton, 'Add Tenant'));
      await tester.pump();

      expect(find.text('Name is required'), findsOneWidget);
    });

    testWidgets('mobile field strips non-digit characters and rejects a bad length', (tester) async {
      tester.view.physicalSize = const Size(800, 3000);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);

      final repo = ResidentMasterRepository(ds: _FakeDataSource());
      await tester.pumpWidget(_wrap(
        TenantFormScreen(defaultFlat: _flat()),
        overrides: [residentMasterRepositoryProvider.overrideWithValue(repo)],
      ));
      await tester.pumpAndSettle();

      await tester.enterText(find.byType(TextFormField).at(0), 'Valid Name');
      // Same length-only validator bug as ResidentFormScreen (see that
      // test above) — "abc123abcd" is 10 characters, which the old
      // `.length < 10` check let straight through to the API.
      await tester.enterText(find.byType(TextFormField).at(1), 'abc123abcd');
      await tester.pump();

      expect(find.text('123'), findsOneWidget);

      await tester.tap(find.widgetWithText(ElevatedButton, 'Add Tenant'));
      await tester.pump();

      expect(find.text('Enter a valid 10-digit mobile number'), findsOneWidget);
    });
  });

  // ── Agreement history (Phase M1.4-R) ─────────────────────────────────────

  group('Agreement History (Tenant Detail)', () {
    testWidgets('shows "No agreement history available." when empty', (tester) async {
      tester.view.physicalSize = const Size(800, 3000);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      final repo = ResidentMasterRepository(
        ds: _FakeDataSource()..tenants = [_tenant(id: 'ten-1')],
      );
      await tester.pumpWidget(_wrap(
        TenantDetailScreen(tenant: _tenant(id: 'ten-1')),
        overrides: [residentMasterRepositoryProvider.overrideWithValue(repo)],
      ));
      await tester.pumpAndSettle();

      expect(find.text('No agreement history available.'), findsOneWidget);
    });

    testWidgets('renders CURRENT/PREVIOUS labels newest-first, as returned by the backend', (tester) async {
      tester.view.physicalSize = const Size(800, 3000);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      final repo = ResidentMasterRepository(
        ds: _FakeDataSource()
          ..tenants = [_tenant(id: 'ten-1')]
          ..agreements = [
            _agreement(id: 'agr-2', startDate: '2027-01-01', endDate: '2027-12-31', status: AgreementStatus.active),
            _agreement(id: 'agr-1', startDate: '2026-01-01', endDate: '2026-12-31', status: AgreementStatus.renewed),
          ],
      );
      await tester.pumpWidget(_wrap(
        TenantDetailScreen(tenant: _tenant(id: 'ten-1')),
        overrides: [residentMasterRepositoryProvider.overrideWithValue(repo)],
      ));
      await tester.pumpAndSettle();

      expect(find.text('CURRENT'), findsOneWidget);
      expect(find.text('PREVIOUS'), findsOneWidget);
    });

    testWidgets('shows a friendly message, not a raw exception, on error', (tester) async {
      tester.view.physicalSize = const Size(800, 3000);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      final repo = ResidentMasterRepository(
        ds: _FakeDataSource()
          ..tenants = [_tenant(id: 'ten-1')]
          ..throwOnListAgreements = Exception('Access requires one of roles: Society Admin, ...'),
      );
      await tester.pumpWidget(_wrap(
        TenantDetailScreen(tenant: _tenant(id: 'ten-1')),
        overrides: [residentMasterRepositoryProvider.overrideWithValue(repo)],
      ));
      await tester.pumpAndSettle();

      expect(find.text('You do not have permission to view this.'), findsOneWidget);
      expect(find.textContaining('Access requires one of roles'), findsNothing);
    });
  });

  // ── Agreement status badge before move-in (M1.9-R1) ─────────────────────
  //
  // A tenant created with agreement dates but no move-in yet has those
  // dates cached on the Tenant row only — activeAgreementId stays null
  // until move-in creates a real AgreementTracker. Found live: the badge
  // fell through to the terminated/expired branch and showed "TERMINATED"
  // for an agreement that was never active in the first place.
  group('Tenant Detail agreement status badge', () {
    testWidgets('shows a neutral pending message, not TERMINATED, before move-in', (tester) async {
      tester.view.physicalSize = const Size(800, 3000);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      final futureEnd = DateTime.now().add(const Duration(days: 300));
      final iso = '${futureEnd.year}-${futureEnd.month.toString().padLeft(2, '0')}-${futureEnd.day.toString().padLeft(2, '0')}';
      final repo = ResidentMasterRepository(
        ds: _FakeDataSource()..tenants = [_tenant(id: 'ten-1', agreementEndDate: iso)],
      );
      await tester.pumpWidget(_wrap(
        TenantDetailScreen(tenant: _tenant(id: 'ten-1', agreementEndDate: iso)),
        overrides: [residentMasterRepositoryProvider.overrideWithValue(repo)],
      ));
      await tester.pumpAndSettle();

      expect(find.text('Not yet active — becomes effective when the tenant moves in.'), findsOneWidget);
      expect(find.text('TERMINATED'), findsNothing);
    });
  });

  // ── Occupancy move-in sheet ─────────────────────────────────────────────

  group('Occupancy move-in', () {
    testWidgets('resident move-in sheet opens and submits successfully', (tester) async {
      final repo = ResidentMasterRepository(ds: _FakeDataSource());
      final resident = _resident();

      await tester.pumpWidget(ProviderScope(
        overrides: [
          currentUserProvider.overrideWithValue(_adminUser()),
          flatsBySocietyProvider.overrideWith(() => _FakeFlatsNotifier([_flat()])),
          residentMasterRepositoryProvider.overrideWithValue(repo),
        ],
        child: MaterialApp(
          theme: AppTheme.lightTheme,
          home: Scaffold(
            body: Consumer(builder: (context, ref, _) => ElevatedButton(
                  onPressed: () => showResidentMoveInSheet(context, ref, resident: resident),
                  child: const Text('open sheet'),
                )),
          ),
        ),
      ));

      await tester.tap(find.text('open sheet'));
      await tester.pumpAndSettle();

      expect(find.text('Move In — John Owner'), findsOneWidget);
      expect(find.text('Confirm Move In'), findsOneWidget);

      await tester.tap(find.text('Confirm Move In'));
      await tester.pumpAndSettle();

      expect(find.text('Resident moved in successfully'), findsOneWidget);
    });
  });

  // ── Flat occupancy_status protection (Phase M1.4 §5) ────────────────────

  group('FlatFormScreen occupancy_status protection', () {
    testWidgets('edit mode displays occupancy status but exposes no editable control', (tester) async {
      await tester.pumpWidget(_wrap(FlatFormScreen(flat: _flat(occupancyStatus: 'owner_occupied'))));
      await tester.pumpAndSettle();

      // Read-only summary is shown...
      expect(find.textContaining('Occupancy status: Owner Occupied'), findsOneWidget);
      // ...but there is no "Occupancy Status" dropdown field to edit it.
      expect(find.widgetWithText(DropdownButtonFormField<String>, 'Occupancy Status'), findsNothing);
      expect(find.byWidgetPredicate((w) =>
          w is InputDecorator && w.decoration.labelText == 'Occupancy Status'), findsNothing);
    });

    testWidgets('create mode still exposes the occupancy status dropdown (new flat, no history to bypass)',
        (tester) async {
      await tester.pumpWidget(_wrap(const FlatFormScreen()));
      await tester.pumpAndSettle();

      expect(find.text('Occupancy Status'), findsOneWidget);
    });
  });

  // ── Navigation ───────────────────────────────────────────────────────────

  group('Resident Master navigation', () {
    testWidgets('resident list -> detail -> back pops correctly', (tester) async {
      final repo = ResidentMasterRepository(
        ds: _FakeDataSource()..residents = [_resident(fullName: 'Nav Test Resident')],
      );

      final router = GoRouter(
        initialLocation: '/residents',
        routes: [
          GoRoute(path: '/residents', builder: (_, __) => const ResidentListScreen()),
          GoRoute(
            path: '/residents/detail',
            builder: (_, state) => ResidentDetailScreen(resident: state.extra as ResidentModel),
          ),
        ],
      );

      await tester.pumpWidget(ProviderScope(
        overrides: [
          currentUserProvider.overrideWithValue(_adminUser()),
          flatsBySocietyProvider.overrideWith(() => _FakeFlatsNotifier([_flat()])),
          // Every Resident Master provider used by the detail screen
          // (residentDetailProvider, residentsByFlatProvider,
          // tenantsByFlatProvider, vehiclesByFlatProvider, flatHistoryProvider)
          // ultimately calls through this one repository, so overriding it
          // alone is sufficient to keep the whole detail screen offline.
          residentMasterRepositoryProvider.overrideWithValue(repo),
        ],
        child: MaterialApp.router(theme: AppTheme.lightTheme, routerConfig: router),
      ));
      await tester.pumpAndSettle();

      expect(find.text('Nav Test Resident'), findsOneWidget);

      await tester.tap(find.text('Nav Test Resident'));
      await tester.pumpAndSettle();

      // Now on the detail screen: AppBar title is the resident's name, and
      // the Profile section (unique to the detail screen) is present.
      expect(find.text('Profile'), findsOneWidget);
      expect(find.text('No residents found'), findsNothing);

      await tester.pageBack();
      await tester.pumpAndSettle();

      expect(find.text('Nav Test Resident'), findsOneWidget);
    });
  });
}

class _ThrowingResidentListDataSource extends ResidentMasterRemoteDataSource {
  _ThrowingResidentListDataSource() : super(dio: Dio());

  @override
  Future<List<ResidentModel>> listResidents({
    String? flatId, String? residentType, bool? isActive, String? search, int skip = 0, int limit = 50,
  }) async {
    throw DioException(
      requestOptions: RequestOptions(path: '/residents/'),
      response: Response(
        requestOptions: RequestOptions(path: '/residents/'),
        statusCode: 500,
      ),
      type: DioExceptionType.badResponse,
    );
  }
}
