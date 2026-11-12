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
Dio _server(List<Map<String, dynamic>> saved, {List<Map<String, dynamic>> broken = const []}) {
  final dio = Dio();
  dio.interceptors.add(InterceptorsWrapper(onRequest: (o, h) {
    Object data;
    if (o.path.endsWith('/floors')) {
      data = [
        {'floor_number': 2, 'name': '2nd Floor'}
      ];
    } else if (o.path.endsWith('/sheet')) {
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
    } else if (o.path.endsWith('/not-working')) {
      data = {'rows': broken};
    } else {
      data = {};
    }
    h.resolve(Response(requestOptions: o, statusCode: 200, data: jsonDecode(jsonEncode(data))));
  }));
  return dio;
}

Widget _wrap(Dio dio) => ProviderScope(
      overrides: [
        currentUserProvider.overrideWithValue(const UserEntity(
            id: 'u', email: 'e@t.com', fullName: 'Eli', roles: ['Technical Staff'], societyId: 's1', termsAccepted: true)),
        wingsProvider.overrideWith(() => _FakeWings()),
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
}
