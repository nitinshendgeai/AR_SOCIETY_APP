import 'dart:convert';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/auth/domain/entities/user_entity.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/features/lights_check/data/lights_api.dart';
import 'package:ar_society_app/features/lights_check/presentation/screens/lights_check_screen.dart';
import 'package:ar_society_app/features/society_structure/data/models/structure_models.dart';
import 'package:ar_society_app/features/society_structure/presentation/providers/structure_providers.dart';

class _FakeFlats extends FlatsByWingNotifier {
  @override
  Future<List<FlatModel>> build(String wingId) async => const [
        FlatModel(id: 'f201', flatNumber: '201', floor: 2, wingId: 'w1'),
        FlatModel(id: 'f202', flatNumber: '202', floor: 2, wingId: 'w1'),
        FlatModel(id: 'f301', flatNumber: '301', floor: 3, wingId: 'w1'),
      ];
}

class _FakeWings extends WingsNotifier {
  @override
  Future<List<WingModel>> build() async => const [WingModel(id: 'w1', name: 'Wing A', societyId: 's1')];
}

Map<String, dynamic> _point(String location, String label, {String? status, String? at, String? by}) => {
      'location': location,
      'label': label,
      'status': status,
      'last_checked_at': at,
      'last_checked_by': by,
      'not_working_since': null,
    };

/// A server with one wing, one floor and the 4 tube lights of it; remembers what was saved.
Dio _server(List<Map<String, dynamic>> saved,
    {List<Map<String, dynamic>> broken = const [], List<Map<String, dynamic>>? reports, List<String?>? sheetKinds, List<Map<String, dynamic>>? areaBodies}) {
  final asked = reports ?? <Map<String, dynamic>>[];
  final dio = Dio();
  dio.interceptors.add(InterceptorsWrapper(onRequest: (o, h) {
    Object data;
    if (o.method == 'POST' && o.path.endsWith('/areas')) {
      areaBodies?.add(Map<String, dynamic>.from(o.data as Map));
      data = {'id': 'a2', 'name': 'Lobby', 'wing_id': null, 'wing_name': null, 'items': []};
    } else if (o.path.endsWith('/areas')) {
      data = [
        {
          'id': 'a1',
          'name': 'Parking',
          'wing_id': null,
          'wing_name': null,
          'items': [
            {'kind': 'tube', 'label': 'Tube lights', 'count': 2},
            {'kind': 'camera', 'label': 'Cameras', 'count': 1},
          ],
        }
      ];
    } else if (o.path.contains('/area/') && o.path.endsWith('/sheet')) {
      data = {
        'groups': [
          {
            'flat_id': null,
            'label': 'Tube lights',
            'points': [_point('tube_1', 'Tube light 1'), _point('tube_2', 'Tube light 2', status: 'not_working', at: '2026-10-05T05:00:00Z', by: 'Eli')],
          },
          {
            'flat_id': null,
            'label': 'Cameras',
            'points': [_point('camera_1', 'Camera')],
          },
        ],
      };
    } else if (o.path.endsWith('/floors')) {
      data = [
        {'floor_number': 2, 'name': '2nd Floor'}
      ];
    } else if (o.path.endsWith('/sheet')) {
      sheetKinds?.add(o.queryParameters['kind'] as String?);
      data = {
        'groups': [
          {
            'flat_id': null,
            'label': 'This floor',
            'points': [
              _point('floor_1', 'Floor tube light 1', status: 'working', at: '2026-10-05T05:00:00Z', by: 'Eli'),
              _point('floor_2', 'Floor tube light 2'),
              _point('stair_1', 'Staircase tube light 1'),
              _point('stair_2', 'Staircase tube light 2'),
            ],
          }
        ]
      };
    } else if (o.path.endsWith('/check')) {
      saved.add(Map<String, dynamic>.from(o.data as Map));
      data = {'checked': 4, 'working': 3, 'not_working': 1};
    } else if (o.path.endsWith('/report')) {
      asked.add(Map<String, dynamic>.from(o.queryParameters));
      data = {
        'month': o.queryParameters['month'] ?? '2026-11',
        'totals': {'checked': 7, 'working': 6, 'not_working': 1, 'replaced': 1, 'still_not_working': 1},
        'flat': o.queryParameters['flat_id'] == null
            ? null
            : {
                'id': 'f202',
                'label': '202',
                'lights': [
                  {'location': 'hall', 'label': 'Hall', 'status': 'working', 'checked_at': '2026-11-05T05:00:00Z'},
                  {'location': 'bedroom', 'label': 'Bedroom', 'status': null, 'checked_at': null},
                  {'location': 'kitchen', 'label': 'Kitchen', 'status': 'not_working', 'checked_at': '2026-11-05T05:00:00Z'},
                ],
              },
        'areas_not_checked': 0,
        'areas_partly_checked': 1,
        'areas': [
          {
            'id': 'a1', 'name': 'Parking', 'wing_name': null, 'status': 'partial',
            'items': [
              {'kind': 'tube', 'label': 'Tube lights', 'expected': 4, 'checked': 3, 'working': 1, 'not_working': 2},
              {'kind': 'camera', 'label': 'Cameras', 'expected': 1, 'checked': 1, 'working': 1, 'not_working': 0},
            ],
          },
        ],
        'floors_not_checked': 1,
        'floors_partly_checked': 1,
        'floors': [
          {
            'wing_id': 'w1', 'wing_name': 'Wing A', 'floor_number': 2, 'floor_name': '2nd Floor', 'flats': 2, 'status': 'partial',
            'tube': {'expected': 4, 'checked': 4, 'working': 4, 'not_working': 0},
            'spot': {'expected': 6, 'checked': 3, 'working': 2, 'not_working': 1},
            'camera': {'expected': 1, 'checked': 1, 'working': 1, 'not_working': 0},
          },
          {
            'wing_id': 'w1', 'wing_name': 'Wing A', 'floor_number': 3, 'floor_name': '3rd Floor', 'flats': 1, 'status': 'not_checked',
            'tube': {'expected': 4, 'checked': 0, 'working': 0, 'not_working': 0},
            'spot': {'expected': 3, 'checked': 0, 'working': 0, 'not_working': 0},
          },
        ],
      };
    } else if (o.path.endsWith('/not-working')) {
      data = {'rows': broken};
    } else {
      data = {};
    }
    h.resolve(Response(requestOptions: o, statusCode: 200, data: jsonDecode(jsonEncode(data))));
  }));
  return dio;
}

Widget _wrap(Dio dio, {List<String> roles = const ['Technical Staff']}) => ProviderScope(
      overrides: [
        currentUserProvider.overrideWithValue(
            UserEntity(id: 'u', email: 'e@t.com', fullName: 'Eli', roles: roles, societyId: 's1', termsAccepted: true)),
        wingsProvider.overrideWith(() => _FakeWings()),
        flatsByWingProvider.overrideWith(() => _FakeFlats()),
        lightsApiProvider.overrideWithValue(LightsApi(dio: dio)),
      ],
      child: MaterialApp(theme: AppTheme.lightTheme, home: const LightsCheckScreen()),
    );

void main() {
  void phone(WidgetTester t) {
    t.view.physicalSize = const Size(420, 1600);
    t.view.devicePixelRatio = 1.0;
    addTearDown(t.view.resetPhysicalSize);
    addTearDown(t.view.resetDevicePixelRatio);
  }

  Future<void> choose(WidgetTester t, Key dropdown, String text) async {
    await t.tap(find.byKey(dropdown));
    await t.pumpAndSettle();
    await t.tap(find.text(text).last);
    await t.pumpAndSettle();
  }

  testWidgets('pick a wing and a floor, mark each light, save with what was found', (t) async {
    phone(t);
    final saved = <Map<String, dynamic>>[];
    await t.pumpWidget(_wrap(_server(saved)));
    await t.pumpAndSettle();
    expect(find.text('Choose a wing and a floor'), findsOneWidget);

    await choose(t, const Key('light-wing'), 'Wing A');
    await choose(t, const Key('light-floor'), '2nd Floor');
    expect(find.text('Floor tube light 1'), findsOneWidget);
    expect(find.text('Staircase tube light 2'), findsOneWidget);
    expect(find.textContaining('Last: working'), findsOneWidget);          // when and by whom it was last checked
    expect(find.text('Not checked yet'), findsNWidgets(3));
    expect(find.text('0 of 4 marked'), findsOneWidget);
    expect(t.widget<ElevatedButton>(find.byKey(const Key('save-light-check'))).onPressed, isNull);

    await t.tap(find.byKey(const Key('mark-all-working')));
    await t.pump();
    await t.tap(find.byKey(const Key('|stair_1_not_working')));
    await t.pump();
    expect(find.text('4 of 4 marked'), findsOneWidget);

    await t.ensureVisible(find.byKey(const Key('save-light-check')));
    await t.tap(find.byKey(const Key('save-light-check')));
    await t.pumpAndSettle();
    expect(saved, hasLength(1));
    expect(saved.single['wing_id'], 'w1');
    expect(saved.single['floor_number'], 2);
    expect(saved.single['kind'], 'tube');
    final results = {for (final r in saved.single['results'] as List) r['location']: r['status']};
    expect(results, {'floor_1': 'working', 'floor_2': 'working', 'stair_1': 'not_working', 'stair_2': 'working'});
  });

  testWidgets('the To replace tab lists what was found not working', (t) async {
    phone(t);
    await t.pumpWidget(_wrap(_server([], broken: [
      {
        'id': 'p1', 'kind': 'spot', 'label': 'Kitchen', 'floor_number': 2, 'wing_name': 'Wing A', 'flat_label': '201',
        'not_working_since': '2026-10-05T05:00:00Z', 'last_checked_at': '2026-10-05T05:00:00Z', 'last_checked_by': 'Eli',
      }
    ])));
    await t.pumpAndSettle();
    expect(find.text('To replace (1)'), findsOneWidget);
    await t.tap(find.text('To replace (1)'));
    await t.pumpAndSettle();
    expect(find.text('Kitchen'), findsOneWidget);
    expect(find.text('Wing A · Floor 2 · Flat 201'), findsOneWidget);
    expect(find.textContaining('Not working since'), findsOneWidget);
    expect(find.byKey(const Key('replace-p1')), findsOneWidget);
  });

  testWidgets('the Report tab shows the month, the totals and every floor', (t) async {
    phone(t);
    final asked = <Map<String, dynamic>>[];
    await t.pumpWidget(_wrap(_server([], reports: asked)));
    await t.pumpAndSettle();
    await t.tap(find.text('Report'));
    await t.pumpAndSettle();
    expect(find.text('November 2026'), findsOneWidget);
    expect(find.text('7'), findsOneWidget);                                   // checked
    expect(find.text('6'), findsOneWidget);                                   // working
    expect(find.text('1 light still waiting to be replaced'), findsOneWidget);
    expect(find.text('1 floor not checked · 1 partly checked · 1 area partly checked'), findsOneWidget);
    expect(find.text('Wing A · 2nd Floor'), findsOneWidget);
    expect(find.text('Partly'), findsNWidgets(2));                              // floor 2 and the Parking area
    expect(find.text('Not checked'), findsOneWidget);
    expect(find.textContaining('Tube lights 4/4'), findsOneWidget);
    expect(find.textContaining('Spot lights 3/6 (2 flats)'), findsOneWidget);
    expect(find.textContaining('Camera 1/1'), findsOneWidget);
    // the common areas follow the floors
    expect(find.text('Common areas'), findsOneWidget);
    expect(find.text('Parking'), findsOneWidget);
    expect(find.text('Tube lights 3/4  ·  Cameras 1/1'), findsOneWidget);
    expect(find.text('2 not working'), findsOneWidget);
    expect(find.text('1 not working'), findsOneWidget);
    // the first read is the current month; "previous" asks for the one before
    expect(asked, [<String, dynamic>{}]);
    await t.tap(find.byKey(const Key('report-prev')));
    await t.pumpAndSettle();
    expect(asked.last['month'], matches(RegExp(r'^\d{4}-\d{2}$')));
  });

  testWidgets('the report can be narrowed by wing, floor and flat', (t) async {
    phone(t);
    final asked = <Map<String, dynamic>>[];
    await t.pumpWidget(_wrap(_server([], reports: asked)));
    await t.pumpAndSettle();
    await t.tap(find.text('Report'));
    await t.pumpAndSettle();
    // the floor needs a wing first
    expect(t.widget<DropdownButtonFormField<int?>>(find.byKey(const Key('report-floor'))).onChanged, isNull);
    expect(find.byKey(const Key('report-flat')), findsNothing);

    await choose(t, const Key('report-wing'), 'Wing A');
    expect(asked.last, {'wing_id': 'w1'});
    await choose(t, const Key('report-floor'), '2nd Floor');
    expect(asked.last, {'wing_id': 'w1', 'floor_number': 2});
    // only this floor's flats are offered
    await t.tap(find.byKey(const Key('report-flat')));
    await t.pumpAndSettle();
    expect(find.text('Flat 201'), findsWidgets);
    expect(find.text('Flat 301'), findsNothing);
    await t.tap(find.text('Flat 202').last);
    await t.pumpAndSettle();
    expect(asked.last, {'wing_id': 'w1', 'floor_number': 2, 'flat_id': 'f202'});
    // the flat's three spot lights, as they stood
    expect(find.text('Bedroom'), findsOneWidget);
    expect(find.text('Hall'), findsOneWidget);
    expect(find.text('Not working'), findsWidgets);
    expect(find.text('Not checked'), findsWidgets);

    await t.tap(find.byKey(const Key('report-clear')));
    await t.pumpAndSettle();
    expect(asked.last, <String, dynamic>{});
  });

  testWidgets('the camera of a floor is checked like the other lights', (t) async {
    phone(t);
    final kinds = <String?>[];
    await t.pumpWidget(_wrap(_server([], sheetKinds: kinds)));
    await t.pumpAndSettle();
    await choose(t, const Key('light-wing'), 'Wing A');
    await choose(t, const Key('light-floor'), '2nd Floor');
    expect(kinds, ['tube']);
    await t.tap(find.text('Camera'));
    await t.pumpAndSettle();
    expect(kinds.last, 'camera');
  });

  testWidgets('staff check a common area: its lights and cameras are numbered, and they cannot set areas up', (t) async {
    phone(t);
    final saved = <Map<String, dynamic>>[];
    await t.pumpWidget(_wrap(_server(saved)));
    await t.pumpAndSettle();
    await t.tap(find.text('Common areas'));
    await t.pumpAndSettle();
    expect(find.byKey(const Key('manage-areas')), findsNothing);
    await choose(t, const Key('light-area'), 'Parking');
    expect(find.text('Tube light 1'), findsOneWidget);
    expect(find.text('Tube light 2'), findsOneWidget);
    expect(find.text('Camera'), findsOneWidget);
    expect(find.textContaining('Last: not working'), findsOneWidget);

    await t.tap(find.byKey(const Key('mark-all-working')));
    await t.pump();
    await t.tap(find.byKey(const Key('|tube_2_not_working')));
    await t.pump();
    await t.ensureVisible(find.byKey(const Key('save-light-check')));
    await t.tap(find.byKey(const Key('save-light-check')));
    await t.pumpAndSettle();
    expect(saved, hasLength(1));
    final results = {for (final r in saved.single['results'] as List) r['location']: r['status']};
    expect(results, {'tube_1': 'working', 'tube_2': 'not_working', 'camera_1': 'working'});
  });

  testWidgets('the Manager adds an area and says how many of each it has', (t) async {
    phone(t);
    final bodies = <Map<String, dynamic>>[];
    await t.pumpWidget(_wrap(_server([], areaBodies: bodies), roles: ['Manager']));
    await t.pumpAndSettle();
    await t.tap(find.text('Common areas'));
    await t.pumpAndSettle();
    await t.tap(find.byKey(const Key('manage-areas')));
    await t.pumpAndSettle();
    expect(find.text('2 tube lights · 1 camera'), findsOneWidget);          // the area already there, and what it has
    await t.tap(find.byKey(const Key('add-area')));
    await t.pumpAndSettle();
    // nothing to save until it has a name and something to check
    expect(t.widget<ElevatedButton>(find.byKey(const Key('save-area'))).onPressed, isNull);
    await t.enterText(find.byKey(const Key('area-name')), 'Lobby');
    await t.pump();
    await t.ensureVisible(find.byKey(const Key('more-spot')));
    await t.tap(find.byKey(const Key('more-spot')));
    await t.pump();
    await t.tap(find.byKey(const Key('more-spot')));
    await t.pump();
    await t.ensureVisible(find.byKey(const Key('more-camera')));
    await t.tap(find.byKey(const Key('more-camera')));
    await t.pump();
    await t.ensureVisible(find.byKey(const Key('save-area')));
    await t.tap(find.byKey(const Key('save-area')));
    await t.pumpAndSettle();
    expect(bodies, hasLength(1));
    expect(bodies.single['name'], 'Lobby');
    expect(bodies.single.containsKey('wing_id'), isFalse);
    expect(bodies.single['items'], [
      {'kind': 'spot', 'count': 2},
      {'kind': 'camera', 'count': 1},
    ]);
  });

  testWidgets('a light in a common area is listed under its area', (t) async {
    phone(t);
    await t.pumpWidget(_wrap(_server([], broken: [
      {
        'id': 'p9', 'kind': 'tube', 'label': 'Tube light 3', 'floor_number': null, 'wing_name': null, 'flat_label': null,
        'area_name': 'Parking', 'not_working_since': '2026-10-05T05:00:00Z', 'last_checked_at': '2026-10-05T05:00:00Z',
        'last_checked_by': 'Eli',
      }
    ])));
    await t.pumpAndSettle();
    await t.tap(find.text('To replace (1)'));
    await t.pumpAndSettle();
    expect(find.text('Tube light 3'), findsOneWidget);
    expect(find.text('Parking'), findsOneWidget);
    expect(find.byKey(const Key('replace-p9')), findsOneWidget);
  });
}
