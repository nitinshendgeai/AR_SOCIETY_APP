import 'dart:io';
import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/auth/domain/entities/user_entity.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/features/resident_master/data/datasources/resident_master_remote_datasource.dart';
import 'package:ar_society_app/features/resident_master/data/models/resident_master_models.dart';
import 'package:ar_society_app/features/resident_master/data/repositories/resident_master_repository.dart';
import 'package:ar_society_app/features/resident_master/data/tenant_report_api.dart';
import 'package:ar_society_app/features/resident_master/presentation/providers/resident_master_providers.dart';
import 'package:ar_society_app/features/resident_master/presentation/screens/tenant_list_screen.dart';
import 'package:ar_society_app/features/society_structure/data/models/structure_models.dart';
import 'package:ar_society_app/features/society_structure/presentation/providers/structure_providers.dart';

class _Ds extends ResidentMasterRemoteDataSource {
  _Ds() : super(dio: Dio());
  @override
  Future<int> countTenants({
    String? flatId, String? wingId, bool? isActive, bool? movedIn, String? agreement, String? police,
    bool? kycVerified, String? search,
  }) async => 0;
  @override
  Future<int> countResidents({
    String? flatId, String? wingId, String? residentType, bool? isActive, bool? movedIn, String? search,
  }) async => 0;
  @override
  Future<List<TenantModel>> listTenants({
    String? flatId, String? wingId, bool? isActive, bool? movedIn, String? agreement, String? police,
    bool? kycVerified, String? search, int skip = 0, int limit = 50,
  }) async => [];
}

/// Records what the Print button asked the server to print.
class _Report extends TenantReportApi {
  _Report() : super(dio: Dio());
  final calls = <Map<String, Object?>>[];
  @override
  Future<Uint8List> pdf({
    bool? isActive, String? search, String? flatId, String? wingId, bool? movedIn, String? agreement,
    String? police, bool? kycVerified,
  }) async {
    calls.add({
      'active': isActive, 'search': search, 'flat': flatId, 'wing': wingId, 'movedIn': movedIn,
      'agreement': agreement, 'police': police, 'kyc': kycVerified,
    });
    return Uint8List.fromList([0x25, 0x50, 0x44, 0x46]);
  }
}

class _Flats extends FlatsBySocietyNotifier {
  @override
  Future<List<FlatModel>> build() async => [
        FlatModel(id: 'f1', flatNumber: '101', wingId: 'wa', wingName: 'Wing A', occupancyStatus: 'vacant'),
      ];
}

Widget _app(_Report report, {List<String> roles = const ['Society Admin']}) => ProviderScope(
      overrides: [
        currentUserProvider
            .overrideWithValue(UserEntity(id: 'u', email: 'u@t.com', fullName: 'U', roles: roles, societyId: 's1')),
        flatsBySocietyProvider.overrideWith(() => _Flats()),
        residentMasterRepositoryProvider.overrideWithValue(ResidentMasterRepository(ds: _Ds())),
        tenantReportApiProvider.overrideWithValue(report),
      ],
      child: MaterialApp(theme: AppTheme.lightTheme, home: const TenantListScreen()),
    );

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUp(() {
    // The share sheet is a platform plugin (and writes the PDF to a temporary folder first); answer both so the
    // test only looks at what the Print button asked the server for.
    final messenger = TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger;
    messenger.setMockMethodCallHandler(const MethodChannel('dev.fluttercommunity.plus/share'),
        (_) async => 'dev.fluttercommunity.plus/share/success');
    messenger.setMockMethodCallHandler(
        const MethodChannel('plugins.flutter.io/path_provider'), (_) async => Directory.systemTemp.path);
  });

  // A window wide enough for every filter chip and tall enough for every filter row to be open at once.
  void phone(WidgetTester t) {
    t.view.physicalSize = const Size(1000, 1400);
    t.view.devicePixelRatio = 1;
    addTearDown(t.view.resetPhysicalSize);
    addTearDown(t.view.resetDevicePixelRatio);
  }

  Future<void> print(WidgetTester t) async {
    await t.tap(find.byKey(const ValueKey('tenants-print')));
    await t.pumpAndSettle();
    await t.tap(find.text('Share PDF'));
    await t.pump();
    // The request goes out first; what follows (the share sheet) is a platform plugin this test does not exercise.
    await t.runAsync(() => Future<void>.delayed(const Duration(milliseconds: 200)));
    await t.pump();
  }

  testWidgets('printing with no filter asks for the report of current tenants', (t) async {
    phone(t);
    final report = _Report();
    await t.pumpWidget(_app(report));
    await t.pumpAndSettle();
    await print(t);
    expect(report.calls, hasLength(1));
    expect(report.calls.single, {
      'active': true, 'search': '', 'flat': null, 'wing': null, 'movedIn': null,
      'agreement': null, 'police': null, 'kyc': null,
    });
  });

  testWidgets('the report is asked for under exactly the filters on screen', (t) async {
    phone(t);
    final report = _Report();
    await t.pumpWidget(_app(report));
    await t.pumpAndSettle();
    await t.enterText(find.byType(TextField).first, 'sharma');
    await t.pump(const Duration(milliseconds: 500));
    await t.tap(find.byKey(const ValueKey('tenant-more-filters')));
    await t.pumpAndSettle();
    await t.tap(find.byKey(const ValueKey('filter-police-pending')));
    await t.pumpAndSettle();
    await t.tap(find.byKey(const ValueKey('filter-agreement-expiring')));
    await t.pumpAndSettle();
    await t.tap(find.byKey(const ValueKey('filter-kyc-false')));
    await t.pumpAndSettle();
    await print(t);
    expect(report.calls.single, {
      'active': true, 'search': 'sharma', 'flat': null, 'wing': null, 'movedIn': null,
      'agreement': 'expiring', 'police': 'pending', 'kyc': false,
    });
  });

  testWidgets('a resident or staff member has no Print button', (t) async {
    await t.pumpWidget(_app(_Report(), roles: const ['Resident']));
    await t.pumpAndSettle();
    expect(find.byKey(const ValueKey('tenants-print')), findsNothing);
  });
}
