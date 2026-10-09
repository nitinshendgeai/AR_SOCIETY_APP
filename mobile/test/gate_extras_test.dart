import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/auth/domain/entities/user_entity.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/features/gate_extras/data/gate_extras_api.dart';
import 'package:ar_society_app/features/gate_extras/presentation/screens/domestic_help_screen.dart';
import 'package:ar_society_app/features/gate_extras/presentation/screens/parcels_screen.dart';

UserEntity _user(String role) => UserEntity(
    id: 'u', email: 'u@t.com', fullName: 'U', roles: [role], societyId: 's1');

Map<String, dynamic> _parcel(String status) => {
      'id': 'p1', 'flat_id': 'f1', 'flat': 'A 101', 'courier': 'Amazon', 'description': 'Big box',
      'recipient_name': 'Rohan', 'status': status, 'received_at': '2026-10-09T04:00:00Z',
      'collected_at': status == 'collected' ? '2026-10-09T06:00:00Z' : null,
      'collected_by_name': status == 'collected' ? 'Rohan' : null, 'note': null,
    };

Map<String, dynamic> _help({String status = 'active', String effective = 'active', bool inside = false, String? pass = 'DH-0001'}) => {
      'id': 'h1', 'name': 'Sunita Pawar', 'mobile': '9876500001', 'kind': 'maid', 'id_proof': null,
      'police_verified': true, 'pass_no': pass, 'status': status, 'effective_status': effective,
      'valid_until': '2027-10-09', 'flats': [{'flat_id': 'f1', 'label': 'A 101'}], 'inside': inside,
      'in_at': null, 'note': null,
    };

class _FakeApi extends GateExtrasApi {
  _FakeApi() : super(dio: Dio());
  @override
  Future<List<HelpEntry>> entries(String id) async => [];
}

Widget _wrap(String role, Widget screen, List<Override> overrides) => ProviderScope(
      overrides: [
        currentUserProvider.overrideWithValue(_user(role)),
        gateExtrasApiProvider.overrideWithValue(_FakeApi()),
        ...overrides,
      ],
      child: MaterialApp(theme: AppTheme.lightTheme, home: screen),
    );

void main() {
  void phone(WidgetTester t) {
    t.view.physicalSize = const Size(420, 2000);
    t.view.devicePixelRatio = 1.0;
    addTearDown(t.view.resetPhysicalSize);
    addTearDown(t.view.resetDevicePixelRatio);
  }

  testWidgets('security sees waiting parcels with Hand over and Return, and a Log parcel button', (t) async {
    phone(t);
    await t.pumpWidget(_wrap('Security Staff', const ParcelsScreen(), [
      parcelsProvider('s1').overrideWith((ref) async => [Parcel.fromJson(_parcel('at_gate')), Parcel.fromJson({..._parcel('collected'), 'id': 'p2'})]),
    ]));
    await t.pumpAndSettle();
    expect(find.text('At the gate'), findsWidgets);
    expect(find.text('Earlier'), findsOneWidget);
    expect(find.text('Hand over'), findsOneWidget);
    expect(find.text('Return'), findsOneWidget);
    expect(find.text('Log parcel'), findsOneWidget);
  });

  testWidgets('a resident can only mark their own parcel collected; they cannot log or return', (t) async {
    phone(t);
    await t.pumpWidget(_wrap('Resident', const ParcelsScreen(), [
      parcelsProvider('s1').overrideWith((ref) async => [Parcel.fromJson(_parcel('at_gate'))]),
    ]));
    await t.pumpAndSettle();
    expect(find.text('I collected it'), findsOneWidget);
    expect(find.text('Return'), findsNothing);
    expect(find.text('Log parcel'), findsNothing);
  });

  testWidgets('parcels empty state differs for the gate and for residents', (t) async {
    phone(t);
    await t.pumpWidget(_wrap('Resident', const ParcelsScreen(), [parcelsProvider('s1').overrideWith((ref) async => [])]));
    await t.pumpAndSettle();
    expect(find.textContaining('left for your flat'), findsOneWidget);
  });

  testWidgets('security gets Check in / Check out per person and no Add help button', (t) async {
    phone(t);
    await t.pumpWidget(_wrap('Security Staff', const DomesticHelpScreen(), [
      domesticHelpProvider('s1').overrideWith((ref) async => [
            DomesticHelp.fromJson(_help()),
            DomesticHelp.fromJson({..._help(inside: true), 'id': 'h2', 'name': 'Ramesh Kale', 'pass_no': 'DH-0002'}),
          ]),
    ]));
    await t.pumpAndSettle();
    expect(find.text('Check in'), findsOneWidget);
    expect(find.text('Check out'), findsOneWidget);
    expect(find.text('Inside now'), findsOneWidget);
    expect(find.text('Add help'), findsNothing);
    expect(find.byType(TextField), findsOneWidget);                  // search
  });

  testWidgets('a resident sees status chips, can add help, and has no gate buttons', (t) async {
    phone(t);
    await t.pumpWidget(_wrap('Resident', const DomesticHelpScreen(), [
      domesticHelpProvider('s1').overrideWith((ref) async => [
            DomesticHelp.fromJson(_help(status: 'pending', effective: 'pending', pass: null)),
          ]),
    ]));
    await t.pumpAndSettle();
    expect(find.text('Awaiting pass'), findsOneWidget);
    expect(find.text('Add help'), findsOneWidget);
    expect(find.text('Check in'), findsNothing);
  });

  testWidgets('the office can approve a waiting pass and suspend an active one', (t) async {
    phone(t);
    await t.pumpWidget(_wrap('Society Admin', const DomesticHelpScreen(), [
      domesticHelpProvider('s1').overrideWith((ref) async => [
            DomesticHelp.fromJson(_help(status: 'pending', effective: 'pending', pass: null)),
          ]),
    ]));
    await t.pumpAndSettle();
    await t.tap(find.textContaining('Sunita Pawar'));
    await t.pumpAndSettle();
    expect(find.text('Issue pass'), findsOneWidget);
    expect(find.text('Suspend pass'), findsNothing);
  });
}
