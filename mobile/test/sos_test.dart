import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/notices/data/notices_api.dart';
import 'package:ar_society_app/features/notices/presentation/providers/notices_providers.dart';
import 'package:ar_society_app/features/notices/presentation/widgets/sos_sheet.dart';

class _FakeApi extends NoticesApi {
  final bool fail;
  String? type;
  String? note;
  String? cancelled;
  _FakeApi({this.fail = false}) : super(dio: Dio());

  @override
  Future<EmergencyAlertItem> raiseSos({required String type, String? description}) async {
    if (fail) throw Exception('network down');
    this.type = type;
    note = description;
    return EmergencyAlertItem(
        id: 'a1', type: type, title: 'SOS from A-101', location: 'A-101', triggeredAt: DateTime(2026, 11, 6), isSos: true, reached: 3);
  }

  @override
  Future<void> cancelSos(String id) async => cancelled = id;
}

Widget _app(_FakeApi api) => ProviderScope(
      overrides: [noticesApiProvider.overrideWithValue(api)],
      child: MaterialApp(
        theme: AppTheme.lightTheme,
        home: Builder(
          builder: (context) => Scaffold(body: Center(child: ElevatedButton(onPressed: () => showSosSheet(context), child: const Text('open')))),
        ),
      ),
    );

void main() {
  testWidgets('choosing a type and sending tells the resident help has been told', (tester) async {
    final api = _FakeApi();
    await tester.pumpWidget(_app(api));
    await tester.tap(find.text('open'));
    await tester.pumpAndSettle();

    expect(find.text('Send an SOS'), findsOneWidget);
    await tester.tap(find.text('Fire'));
    await tester.pump();
    await tester.enterText(find.byType(TextField), 'Smoke in the kitchen');
    await tester.tap(find.byKey(const Key('sos-send')));
    await tester.pumpAndSettle();

    expect(api.type, 'fire');
    expect(api.note, 'Smoke in the kitchen');
    expect(find.text('Help has been told'), findsOneWidget);
    expect(find.textContaining('from A-101'), findsOneWidget);
    expect(find.textContaining('3 people notified'), findsOneWidget);
  });

  testWidgets('the default is a medical SOS', (tester) async {
    final api = _FakeApi();
    await tester.pumpWidget(_app(api));
    await tester.tap(find.text('open'));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('sos-send')));
    await tester.pumpAndSettle();
    expect(api.type, 'medical');
  });

  testWidgets('"I am safe" ends the SOS and closes the sheet', (tester) async {
    final api = _FakeApi();
    await tester.pumpWidget(_app(api));
    await tester.tap(find.text('open'));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('sos-send')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('sos-cancel')));
    await tester.pumpAndSettle();
    expect(api.cancelled, 'a1');
    expect(find.text('Help has been told'), findsNothing);
    expect(find.textContaining('SOS ended'), findsOneWidget);
  });

  testWidgets('a failed send says so and lets the resident try again', (tester) async {
    await tester.pumpWidget(_app(_FakeApi(fail: true)));
    await tester.tap(find.text('open'));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('sos-send')));
    await tester.pumpAndSettle();
    expect(find.text('Help has been told'), findsNothing);
    expect(find.byKey(const Key('sos-send')), findsOneWidget);
  });
}
