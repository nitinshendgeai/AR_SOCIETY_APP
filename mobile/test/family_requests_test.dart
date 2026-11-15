import 'dart:io';

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/resident_master/data/family_requests_api.dart';
import 'package:ar_society_app/features/resident_master/data/models/resident_master_models.dart';
import 'package:ar_society_app/features/resident_master/presentation/providers/resident_master_providers.dart';
import 'package:ar_society_app/features/resident_master/presentation/screens/my_home_screen.dart';
import 'package:ar_society_app/features/resident_master/presentation/screens/pending_resident_changes_screen.dart';
import 'package:ar_society_app/shared/widgets/app_form.dart' show AppSheetFrame;
import 'package:ar_society_app/features/society_structure/data/models/structure_models.dart';
import 'package:ar_society_app/features/society_structure/presentation/providers/structure_providers.dart' show flatByIdProvider;

Future<void> _loadInter() async {
  final loader = FontLoader('Inter')
    ..addFont(Future.value(ByteData.sublistView(File('assets/fonts/Inter-Variable.ttf').readAsBytesSync())));
  await loader.load();
}

FamilyRequest _req(String id, String name, {String type = 'dependent', String status = 'pending', String? reason, String flat = 'f1'}) =>
    FamilyRequest(id: id, flatId: flat, flatDisplay: 'A-101', fullName: name, residentType: type, status: status, rejectionReason: reason,
        requesterName: 'Asha Rao', phone: '9876500011');

/// A server that remembers what the screens asked of it.
class FakeFamilyApi extends FamilyRequestsApi {
  FakeFamilyApi({this.mineList = const [], this.pendingList = const []}) : super(dio: Dio());
  List<FamilyRequest> mineList;
  List<FamilyRequest> pendingList;
  final created = <Map<String, Object?>>[];
  final approved = <String>[];
  final rejected = <(String, String)>[];
  Object? failCreate;

  @override
  Future<FamilyRequest> create({required String fullName, required String residentType, String? phone, DateTime? dateOfBirth, String? flatId}) async {
    if (failCreate != null) throw failCreate!;
    created.add({'name': fullName, 'type': residentType, 'phone': phone, 'dob': dateOfBirth, 'flat': flatId});
    final r = _req('new', fullName, type: residentType);
    mineList = [r, ...mineList];
    return r;
  }

  @override
  Future<List<FamilyRequest>> mine() async => mineList;

  @override
  Future<List<FamilyRequest>> pending() async => pendingList;

  @override
  Future<void> approve(String id) async {
    approved.add(id);
    pendingList = pendingList.where((r) => r.id != id).toList();
  }

  @override
  Future<void> reject(String id, String reason) async {
    rejected.add((id, reason));
    pendingList = pendingList.where((r) => r.id != id).toList();
  }
}

ResidentModel _person(String id, String name, ResidentType type) =>
    ResidentModel(id: id, flatId: 'f1', fullName: name, residentType: type, isPrimary: type == ResidentType.owner, phone: '9876543210');

class _NoVehicles extends VehiclesByFlatNotifier {
  @override
  Future<List<VehicleModel>> build(String flatId) async => const [];
}

Widget _home(FakeFamilyApi api, ResidentModel me) => ProviderScope(
      overrides: [
        familyRequestsApiProvider.overrideWithValue(api),
        myResidentProvider.overrideWith((ref) async => me),
        flatByIdProvider('f1').overrideWith((ref) async => const FlatModel(id: 'f1', flatNumber: '101', wingId: 'w', wingName: 'A')),
        residentsByFlatProvider('f1').overrideWith((ref) async => [me]),
        vehiclesByFlatProvider.overrideWith(() => _NoVehicles()),
        myEditRequestsProvider.overrideWith((ref) async => const []),
      ],
      child: MaterialApp(theme: AppTheme.lightTheme, home: const MyHomeScreen()),
    );

Widget _office(FakeFamilyApi api, {List<ResidentEditRequestModel> edits = const []}) => ProviderScope(
      overrides: [
        familyRequestsApiProvider.overrideWithValue(api),
        pendingEditRequestsProvider.overrideWith((ref) async => edits),
      ],
      child: MaterialApp(theme: AppTheme.lightTheme, home: const PendingResidentChangesScreen()),
    );

void _phone(WidgetTester t) {
  t.view.physicalSize = const Size(900, 2600);
  t.view.devicePixelRatio = 2;
  addTearDown(t.view.resetPhysicalSize);
  addTearDown(t.view.resetDevicePixelRatio);
}

void main() {
  setUpAll(_loadInter);

  group('a resident adds a family member (My Home)', () {
    testWidgets('an owner can ask; the request goes to the office and is shown as waiting', (t) async {
      _phone(t);
      final api = FakeFamilyApi();
      await t.pumpWidget(_home(api, _person('r1', 'Asha Rao', ResidentType.owner)));
      await t.pumpAndSettle();
      expect(find.byKey(const Key('add-family')), findsOneWidget);
      await t.tap(find.byKey(const Key('add-family')));
      await t.pumpAndSettle();
      await t.enterText(find.byKey(const Key('family-name')), 'Tia Rao');
      await t.tap(find.text('Dependent'));
      await t.enterText(find.byKey(const Key('family-phone')), '9876500011');
      await t.pumpAndSettle();
      await t.tap(find.text('Send for approval'));
      await t.pumpAndSettle();
      expect(api.created.single, {'name': 'Tia Rao', 'type': 'dependent', 'phone': '9876500011', 'dob': null, 'flat': 'f1'});
      expect(find.byKey(const Key('family-name')), findsNothing);                       // the form closed
      expect(find.byKey(const Key('family-requests')), findsOneWidget);
      expect(find.text('Tia Rao'), findsOneWidget);
      expect(find.textContaining('Waiting for the office to approve'), findsOneWidget);
    });

    testWidgets('the form is drawn on the app\'s sheet (white, with its title and handle), not floating over the page', (t) async {
      _phone(t);
      await t.pumpWidget(_home(FakeFamilyApi(), _person('r1', 'Asha Rao', ResidentType.owner)));
      await t.pumpAndSettle();
      await t.tap(find.byKey(const Key('add-family')));
      await t.pumpAndSettle();
      expect(find.ancestor(of: find.byKey(const Key('family-name')), matching: find.byType(AppSheetFrame)), findsOneWidget);
      expect(find.text('Add a family member'), findsOneWidget);
    });

    testWidgets('a co-owner can ask too; a family member or dependent cannot (the office adds for them)', (t) async {
      _phone(t);
      await t.pumpWidget(_home(FakeFamilyApi(), _person('r1', 'Bela Shah', ResidentType.coOwner)));
      await t.pumpAndSettle();
      expect(find.byKey(const Key('add-family')), findsOneWidget);
      for (final type in [ResidentType.family, ResidentType.dependent]) {
        await t.pumpWidget(const SizedBox());
        await t.pumpWidget(_home(FakeFamilyApi(), _person('r2', 'Vik Rao', type)));
        await t.pumpAndSettle();
        expect(find.byKey(const Key('add-family')), findsNothing, reason: type.name);
        expect(find.textContaining('ask the society office'), findsWidgets);
      }
    });

    testWidgets('a name that is too short is refused on the form and nothing is sent', (t) async {
      _phone(t);
      final api = FakeFamilyApi();
      await t.pumpWidget(_home(api, _person('r1', 'Asha Rao', ResidentType.owner)));
      await t.pumpAndSettle();
      await t.tap(find.byKey(const Key('add-family')));
      await t.pumpAndSettle();
      await t.enterText(find.byKey(const Key('family-name')), 'T');
      await t.tap(find.text('Send for approval'));
      await t.pumpAndSettle();
      expect(find.text('Enter the full name'), findsOneWidget);
      expect(api.created, isEmpty);
    });

    testWidgets('if the server refuses (for example the name is already waiting) the reason is shown and the form stays', (t) async {
      _phone(t);
      final api = FakeFamilyApi()
        ..failCreate = DioException(
            requestOptions: RequestOptions(path: '/x'),
            response: Response(requestOptions: RequestOptions(path: '/x'), statusCode: 409, data: {'detail': 'Tia Rao is already waiting for approval'}),
            type: DioExceptionType.badResponse);
      await t.pumpWidget(_home(api, _person('r1', 'Asha Rao', ResidentType.owner)));
      await t.pumpAndSettle();
      await t.tap(find.byKey(const Key('add-family')));
      await t.pumpAndSettle();
      await t.enterText(find.byKey(const Key('family-name')), 'Tia Rao');
      await t.tap(find.text('Send for approval'));
      await t.pumpAndSettle();
      expect(find.byKey(const Key('family-error')), findsOneWidget);
      expect(find.textContaining('already waiting'), findsOneWidget);
      expect(find.byKey(const Key('family-name')), findsOneWidget);
    });

    testWidgets('waiting and turned-down requests are shown (with why); approved ones are just on the household list', (t) async {
      _phone(t);
      final api = FakeFamilyApi(mineList: [
        _req('1', 'Tia Rao'),
        _req('2', 'Neel Rao', type: 'family', status: 'rejected', reason: 'Please add their ID first'),
        _req('3', 'Done Person', status: 'approved'),
        _req('4', 'Other Flat Person', flat: 'f9'),
      ]);
      await t.pumpWidget(_home(api, _person('r1', 'Asha Rao', ResidentType.owner)));
      await t.pumpAndSettle();
      expect(find.text('Tia Rao'), findsOneWidget);
      expect(find.textContaining('Waiting for the office to approve'), findsOneWidget);
      expect(find.text('Neel Rao'), findsOneWidget);
      expect(find.textContaining('Please add their ID first'), findsOneWidget);
      expect(find.text('Done Person'), findsNothing);
      expect(find.text('Other Flat Person'), findsNothing);
    });
  });

  group('the office approves (Pending Resident Changes)', () {
    testWidgets('new family members are listed with who asked, and approving adds them', (t) async {
      _phone(t);
      final api = FakeFamilyApi(pendingList: [_req('a', 'Tia Rao'), _req('b', 'Neel Rao', type: 'family')]);
      await t.pumpWidget(_office(api));
      await t.pumpAndSettle();
      expect(find.text('New family members'), findsOneWidget);
      expect(find.text('Tia Rao'), findsOneWidget);
      expect(find.text('Neel Rao'), findsOneWidget);
      expect(find.textContaining('Asked by Asha Rao'), findsNWidgets(2));
      await t.tap(find.byKey(const Key('family-approve-a')));
      await t.pumpAndSettle();
      expect(api.approved, ['a']);
      expect(find.text('Tia Rao'), findsNothing);                     // gone from the queue
      expect(find.text('Neel Rao'), findsOneWidget);
    });

    testWidgets('rejecting needs a reason, and sends it', (t) async {
      _phone(t);
      final api = FakeFamilyApi(pendingList: [_req('a', 'Tia Rao')]);
      await t.pumpWidget(_office(api));
      await t.pumpAndSettle();
      await t.tap(find.byKey(const Key('family-reject-a')));
      await t.pumpAndSettle();
      await t.tap(find.widgetWithText(ElevatedButton, 'Reject'));         // no reason yet
      await t.pumpAndSettle();
      expect(api.rejected, isEmpty);
      await t.enterText(find.byKey(const Key('family-reject-reason')), 'Not a family member');
      await t.tap(find.widgetWithText(ElevatedButton, 'Reject'));
      await t.pumpAndSettle();
      expect(api.rejected.single, ('a', 'Not a family member'));
      expect(find.text('Tia Rao'), findsNothing);
    });

    testWidgets('with nothing waiting it says so; with both kinds waiting each has its own heading', (t) async {
      _phone(t);
      await t.pumpWidget(_office(FakeFamilyApi()));
      await t.pumpAndSettle();
      expect(find.text('No pending change requests'), findsOneWidget);

      await t.pumpWidget(const SizedBox());
      await t.pumpWidget(_office(
        FakeFamilyApi(pendingList: [_req('a', 'Tia Rao')]),
        edits: [
          ResidentEditRequestModel(
              id: 'e1', residentId: 'r1', societyId: 's1', createdAt: '2026-11-15T00:00:00', status: ResidentEditRequestStatus.pending, changes: const {'phone': '9000000001'}, residentName: 'Asha Rao', flatDisplay: 'A-101'),
        ],
      ));
      await t.pumpAndSettle();
      expect(find.text('New family members'), findsOneWidget);
      expect(find.text('Profile changes'), findsOneWidget);
      expect(find.textContaining('Mobile: 9000000001'), findsOneWidget);
    });
  });
}
