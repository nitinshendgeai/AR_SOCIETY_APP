import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/resident_master/data/resident_report_api.dart';
import 'package:ar_society_app/features/resident_master/presentation/widgets/resident_report_sheet.dart';

const _cols = [
  ReportColumn(key: 'flat', label: 'Flat', isDefault: true, sensitive: false),
  ReportColumn(key: 'name', label: 'Name', isDefault: true, sensitive: false),
  ReportColumn(key: 'phone', label: 'Mobile', isDefault: false, sensitive: false),
  ReportColumn(key: 'id_proof', label: 'ID proof (last 4)', isDefault: false, sensitive: true),
];

Widget _app(Future<Uint8List> Function(String, List<String>) load) => ProviderScope(
      overrides: [residentReportColumnsProvider.overrideWith((ref) async => _cols)],
      child: MaterialApp(theme: AppTheme.lightTheme, home: Scaffold(body: SingleChildScrollView(child: ResidentReportSheet(load: load)))),
    );

void _size(WidgetTester t) {
  t.view.physicalSize = const Size(420, 2400);
  t.view.devicePixelRatio = 1.0;
  addTearDown(t.view.resetPhysicalSize);
  addTearDown(t.view.resetDevicePixelRatio);
}

void main() {
  testWidgets('the usual columns are ticked, sensitive ones are marked, and the choice goes to the report', (t) async {
    _size(t);
    final asked = <(String, List<String>)>[];
    await t.pumpWidget(_app((format, cols) async {
      asked.add((format, cols));
      return Uint8List.fromList([1, 2, 3]);
    }));
    await t.pumpAndSettle();

    bool ticked(String key) => t.widget<CheckboxListTile>(find.byKey(Key('report-col-$key'))).value == true;
    expect([ticked('flat'), ticked('name'), ticked('phone'), ticked('id_proof')], [true, true, false, false]);
    expect(find.text('Personal details'), findsOneWidget);                     // the ID column says so

    await t.tap(find.byKey(const Key('report-col-phone')));
    await t.pump();
    await t.tap(find.byKey(const Key('report-xlsx-download')));
    await t.pumpAndSettle();
    expect(asked.first.$1, 'xlsx');
    expect(asked.first.$2, ['flat', 'name', 'phone']);                         // the catalogue's order, only what was ticked
  });

  testWidgets('All, None and Usual columns; with none ticked nothing can be printed', (t) async {
    _size(t);
    var calls = 0;
    await t.pumpWidget(_app((_, __) async {
      calls++;
      return Uint8List(0);
    }));
    await t.pumpAndSettle();

    await t.tap(find.byKey(const Key('report-all')));
    await t.pump();
    expect(t.widget<CheckboxListTile>(find.byKey(const Key('report-col-id_proof'))).value, true);
    await t.tap(find.byKey(const Key('report-none')));
    await t.pump();
    expect(find.text('Tick at least one column.'), findsOneWidget);
    expect(t.widget<OutlinedButton>(find.byKey(const Key('report-pdf-share'))).onPressed, isNull);
    await t.tap(find.byKey(const Key('report-defaults')));
    await t.pump();
    expect(t.widget<OutlinedButton>(find.byKey(const Key('report-pdf-share'))).onPressed, isNotNull);
    expect(calls, 0);
  });
}
