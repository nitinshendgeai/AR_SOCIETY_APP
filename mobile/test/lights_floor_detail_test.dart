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
  Future<List<FlatModel>> build(String wingId) async => const [];
}

class _FakeWings extends WingsNotifier {
  @override
  Future<List<WingModel>> build() async => const [WingModel(id: 'w1', name: 'Wing A', societyId: 's1')];
}

Map<String, dynamic> _pt(String loc, String label, {String? status, String? at, String? by, String? since}) => {
      'location': loc,
      'label': label,
      'status': status,
      'last_checked_at': at,
      'last_checked_by': by,
      'not_working_since': since,
    };

const _checked = '2026-11-05T05:00:00Z';

/// What the server returns; each request is remembered so a test can see what was asked.
class _Server {
  final asked = <String>[];
  final sheetQueries = <Map<String, dynamic>>[];
  bool failSpotOnce = false;
  bool withWingId = true;
  String? _month;

  Dio dio() {
    final dio = Dio();
    dio.interceptors.add(InterceptorsWrapper(onRequest: (o, h) {
      asked.add(o.path);
      Object data;
      if (o.path.endsWith('/report')) {
        _month = o.queryParameters['month'] as String?;        // the server answers for the month it was asked about
        data = _report();
      } else if (o.path.endsWith('/sheet') && !o.path.contains('/area/')) {
        sheetQueries.add(Map<String, dynamic>.from(o.queryParameters));
        final kind = o.queryParameters['kind'];
        if (kind == 'spot' && failSpotOnce) {
          failSpotOnce = false;
          h.reject(DioException(requestOptions: o, type: DioExceptionType.connectionError));
          return;
        }
        data = _sheet(kind as String);
      } else if (o.path.contains('/area/') && o.path.endsWith('/sheet')) {
        data = {
          'groups': [
            {'flat_id': null, 'label': 'Tube lights', 'points': [
              _pt('tube_1', 'Tube light 1', status: 'working', at: _checked, by: 'Eli'),
              _pt('tube_2', 'Tube light 2', status: 'not_working', at: _checked, by: 'Eli', since: _checked),
            ]},
            {'flat_id': null, 'label': 'Cameras', 'points': [_pt('camera_1', 'Camera')]},
          ],
        };
      } else if (o.path.endsWith('/not-working')) {
        data = {'rows': []};
      } else if (o.path.endsWith('/areas')) {
        data = [];
      } else {
        data = {};
      }
      h.resolve(Response(requestOptions: o, statusCode: 200, data: jsonDecode(jsonEncode(data))));
    }));
    return dio;
  }

  Map<String, dynamic> _report() => {
        'month': _month ?? '2026-11',
        'totals': {'checked': 9, 'working': 7, 'not_working': 2, 'replaced': 0, 'still_not_working': 2},
        'flat': null,
        'areas_not_checked': 0,
        'areas_partly_checked': 1,
        'areas': [
          {
            'id': 'a1', 'name': 'Parking', 'wing_name': null, 'status': 'partial',
            'items': [
              {'kind': 'tube', 'label': 'Tube lights', 'expected': 2, 'checked': 2, 'working': 1, 'not_working': 1},
              {'kind': 'camera', 'label': 'Cameras', 'expected': 1, 'checked': 0, 'working': 0, 'not_working': 0},
            ],
          },
        ],
        'floors_not_checked': 1,
        'floors_partly_checked': 1,
        'floors': [
          {
            if (withWingId) 'wing_id': 'w1',
            'wing_name': 'Wing A', 'floor_number': 2, 'floor_name': '2nd Floor', 'flats': 3, 'status': 'partial',
            'tube': {'expected': 4, 'checked': 4, 'working': 4, 'not_working': 0},
            'spot': {'expected': 9, 'checked': 4, 'working': 3, 'not_working': 1},
            'camera': {'expected': 1, 'checked': 1, 'working': 1, 'not_working': 0},
          },
          {
            if (withWingId) 'wing_id': 'w1',
            'wing_name': 'Wing A', 'floor_number': 3, 'floor_name': '3rd Floor', 'flats': 0, 'status': 'not_checked',
            'tube': {'expected': 4, 'checked': 0, 'working': 0, 'not_working': 0},
            'spot': {'expected': 0, 'checked': 0, 'working': 0, 'not_working': 0},
          },
        ],
      };

  Map<String, dynamic> _sheet(String kind) {
    switch (kind) {
      case 'tube':
        return {'groups': [
          {'flat_id': null, 'label': 'This floor', 'points': [
            _pt('floor_1', 'Floor tube light 1', status: 'working', at: _checked, by: 'Eli'),
            _pt('floor_2', 'Floor tube light 2', status: 'working', at: _checked, by: 'Eli'),
            _pt('stair_1', 'Staircase tube light 1', status: 'working', at: _checked, by: 'Eli'),
            _pt('stair_2', 'Staircase tube light 2', status: 'working', at: _checked, by: 'Eli'),
          ]},
        ]};
      case 'camera':
        return {'groups': [
          {'flat_id': null, 'label': 'This floor', 'points': [_pt('camera', 'Floor camera', status: 'working', at: _checked, by: 'Eli')]},
        ]};
      default:
        return {'groups': [
          // listed in flat order on purpose: the one with a broken light must still come first on screen
          {'flat_id': 'f201', 'label': 'Flat 201', 'points': [
            _pt('hall', 'Hall', status: 'working', at: _checked, by: 'Eli'),
            _pt('bedroom', 'Bedroom', status: 'working', at: _checked, by: 'Eli'),
            _pt('kitchen', 'Kitchen', status: 'working', at: _checked, by: 'Eli'),
          ]},
          {'flat_id': 'f202', 'label': 'Flat 202', 'points': [
            _pt('hall', 'Hall'), _pt('bedroom', 'Bedroom'), _pt('kitchen', 'Kitchen'),
          ]},
          {'flat_id': 'f203', 'label': 'Flat 203', 'points': [
            _pt('hall', 'Hall', status: 'working', at: _checked, by: 'Eli'),
            _pt('bedroom', 'Bedroom', status: 'working', at: _checked, by: 'Eli'),
            _pt('kitchen', 'Kitchen', status: 'not_working', at: _checked, by: 'Eli', since: '2026-10-28T05:00:00Z'),
          ]},
        ]};
    }
  }
}

Widget _app(_Server s) => ProviderScope(
      overrides: [
        currentUserProvider.overrideWithValue(
            const UserEntity(id: 'u', email: 'e@t.com', fullName: 'Eli', roles: ['Technical Staff'], societyId: 's1', termsAccepted: true)),
        wingsProvider.overrideWith(() => _FakeWings()),
        flatsByWingProvider.overrideWith(() => _FakeFlats()),
        lightsApiProvider.overrideWithValue(LightsApi(dio: s.dio())),
      ],
      child: MaterialApp(theme: AppTheme.lightTheme, home: const LightsCheckScreen()),
    );

void _phone(WidgetTester t) {
  t.view.physicalSize = const Size(420, 2400);
  t.view.devicePixelRatio = 1;
  addTearDown(t.view.resetPhysicalSize);
  addTearDown(t.view.resetDevicePixelRatio);
}

Future<void> _openReport(WidgetTester t, _Server s) async {
  _phone(t);
  await t.pumpWidget(_app(s));
  await t.pumpAndSettle();
  await t.tap(find.text('Report'));
  await t.pumpAndSettle();
}

void main() {
  testWidgets('tapping a floor opens its lights: the floor\'s tube lights, each flat\'s spot lights and the camera', (t) async {
    final s = _Server();
    await _openReport(t, s);
    await t.tap(find.text('Wing A · 2nd Floor'));
    await t.pumpAndSettle();

    expect(find.text('Tube lights'), findsOneWidget);          // the section title
    expect(find.text('Spot lights'), findsOneWidget);
    expect(find.text('Camera'), findsOneWidget);
    expect(find.text('Floor tube light 1'), findsOneWidget);
    expect(find.text('Staircase tube light 2'), findsOneWidget);
    expect(find.text('Floor camera'), findsOneWidget);
    for (final flat in ['Flat 201', 'Flat 202', 'Flat 203']) {
      expect(find.text(flat), findsOneWidget, reason: flat);
    }
  });

  testWidgets('each kind of light is a bordered box with a bold header, and its lights are inside the box', (t) async {
    final s = _Server();
    await _openReport(t, s);
    await t.tap(find.text('Wing A · 2nd Floor'));
    await t.pumpAndSettle();

    for (final (header, inside) in [('Tube lights', 'Floor tube light 1'), ('Spot lights', 'Flat 203'), ('Camera', 'Floor camera')]) {
      final text = t.widget<Text>(find.text(header));
      expect(text.style?.fontWeight, FontWeight.w800, reason: '$header is bold');
      expect(text.style?.fontSize, greaterThanOrEqualTo(16), reason: '$header is larger than the body text');
      final box = find.ancestor(
        of: find.text(header),
        matching: find.byWidgetPredicate(
            (w) => w is Container && w.decoration is BoxDecoration && (w.decoration as BoxDecoration).border != null),
      );
      expect(box, findsOneWidget, reason: '$header sits in a bordered box');
      expect(find.descendant(of: box, matching: find.text(inside)), findsOneWidget, reason: '$inside is in the $header box');
    }
  });

  testWidgets('it asks the server for exactly the kinds the floor has, for that wing and floor', (t) async {
    final s = _Server();
    await _openReport(t, s);
    await t.tap(find.text('Wing A · 2nd Floor'));
    await t.pumpAndSettle();
    expect(s.sheetQueries.map((q) => q['kind']).toSet(), {'tube', 'spot', 'camera'});
    for (final q in s.sheetQueries) {
      expect(q['wing_id'], 'w1');
      expect(q['floor_number'], 2);
    }
  });

  testWidgets('a floor with no flats and no camera shows only its tube lights', (t) async {
    final s = _Server();
    await _openReport(t, s);
    await t.tap(find.text('Wing A · 3rd Floor'));
    await t.pumpAndSettle();
    expect(s.sheetQueries.map((q) => q['kind']).toList(), ['tube']);
    expect(find.text('Spot lights'), findsNothing);
    expect(find.text('Camera'), findsNothing);
  });

  testWidgets('the flat with a broken light comes first and is already open; the others stay folded', (t) async {
    final s = _Server();
    await _openReport(t, s);
    await t.tap(find.text('Wing A · 2nd Floor'));
    await t.pumpAndSettle();

    // 203 (the broken one) is listed above 201 and 202 although it is last in the server's order
    expect(t.getTopLeft(find.text('Flat 203')).dy, lessThan(t.getTopLeft(find.text('Flat 201')).dy));
    expect(t.getTopLeft(find.text('Flat 201')).dy, lessThan(t.getTopLeft(find.text('Flat 202')).dy));
    expect(find.text('Kitchen'), findsOneWidget);               // only 203's lights are showing
    expect(find.text('Not working since 28 Oct'), findsOneWidget);
    // and each flat says how it stands
    expect(find.text('All working'), findsOneWidget);           // 201
    expect(find.text('Not checked'), findsWidgets);             // 202
  });

  testWidgets('opening a folded flat shows its three lights with who checked them and when', (t) async {
    final s = _Server();
    await _openReport(t, s);
    await t.tap(find.text('Wing A · 2nd Floor'));
    await t.pumpAndSettle();
    await t.ensureVisible(find.text('Flat 201'));
    await t.tap(find.text('Flat 201'));
    await t.pumpAndSettle();
    expect(find.text('Hall'), findsWidgets);
    expect(find.text('Bedroom'), findsWidgets);
    expect(find.textContaining(RegExp(r'^Checked 5 Nov, \d{1,2}:\d{2} (AM|PM) by\sEli$')), findsWidgets);
  });

  testWidgets('a floor on the current month has no "last found" note; an earlier month has one', (t) async {
    final s = _Server();
    await _openReport(t, s);
    await t.tap(find.text('Wing A · 2nd Floor'));
    await t.pumpAndSettle();
    expect(find.byKey(const Key('older-month-note')), findsNothing);
    t.state<NavigatorState>(find.byType(Navigator)).pop();
    await t.pumpAndSettle();

    await t.tap(find.byKey(const Key('report-prev')));
    await t.pumpAndSettle();
    await t.tap(find.text('Wing A · 2nd Floor'));
    await t.pumpAndSettle();
    expect(find.byKey(const Key('older-month-note')), findsOneWidget);
    expect(find.textContaining('as it was last found'), findsOneWidget);
  });

  testWidgets('if the wing cannot be identified it says so instead of asking for the wrong lights', (t) async {
    final s = _Server()..withWingId = false;
    await _openReport(t, s);
    await t.tap(find.text('Wing A · 2nd Floor'));
    await t.pumpAndSettle();
    expect(find.textContaining('could not be found'), findsOneWidget);
    expect(s.sheetQueries, isEmpty);
  });

  testWidgets('one section that fails to load can be tried again without losing the others', (t) async {
    final s = _Server()..failSpotOnce = true;
    await _openReport(t, s);
    await t.tap(find.text('Wing A · 2nd Floor'));
    await t.pumpAndSettle();
    expect(find.text('Floor tube light 1'), findsOneWidget);   // the tube section loaded
    expect(find.text('Flat 203'), findsNothing);
    await t.ensureVisible(find.text('Try again'));
    await t.tap(find.text('Try again'));
    await t.pumpAndSettle();
    expect(find.text('Flat 203'), findsOneWidget);
    expect(find.text('Floor tube light 1'), findsOneWidget);
  });

  testWidgets('a common area opens too, with a group for each kind of light it holds', (t) async {
    final s = _Server();
    await _openReport(t, s);
    await t.ensureVisible(find.text('Parking'));
    await t.tap(find.text('Parking'));
    await t.pumpAndSettle();
    expect(find.text('Tube lights'), findsOneWidget);          // a group per kind of light the area holds
    expect(find.text('Cameras'), findsOneWidget);
    expect(find.text('Tube light 2'), findsOneWidget);         // the group with a broken light is open
    expect(find.textContaining('Not working since'), findsOneWidget);
  });

  testWidgets('the cards read as buttons to a screen reader and show a chevron', (t) async {
    final s = _Server();
    final handle = t.ensureSemantics();
    await _openReport(t, s);
    expect(find.bySemanticsLabel(RegExp(r'Wing A · 2nd Floor, Partly.*Opens the lights')), findsOneWidget);
    expect(find.byIcon(Icons.chevron_right_rounded), findsWidgets);
    handle.dispose();
  });
}
