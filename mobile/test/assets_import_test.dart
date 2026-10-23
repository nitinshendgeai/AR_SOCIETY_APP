import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ar_society_app/features/assets/data/assets_api.dart';
import 'package:ar_society_app/features/assets/presentation/providers/assets_providers.dart';
import 'package:ar_society_app/features/assets/presentation/screens/assets_import_screen.dart';
import 'package:ar_society_app/features/auth/domain/entities/user_entity.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart' show AppPrimaryButton;

const _fields = [
  {'field': 'asset_code', 'label': 'Asset code'},
  {'field': 'name', 'label': 'Name'},
  {'field': 'asset_category', 'label': 'Category'},
  {'field': 'location', 'label': 'Location'},
];

Map<String, dynamic> _result({
  bool dryRun = true,
  String? nameColumn = 'name',
  String? thirdField,
  int created = 0,
  String? message,
  List<Map<String, dynamic>>? rows,
}) =>
    {
      'dry_run': dryRun, 'file_name': 'register.xlsx', 'sheet': 'Register', 'total_rows': 3,
      'columns': [
        {'index': 0, 'heading': 'Asset Name', 'field': nameColumn, 'field_label': 'Name', 'sample': 'Lift A'},
        {'index': 1, 'heading': 'Kind', 'field': 'asset_category', 'field_label': 'Category', 'sample': 'Lift'},
        {'index': 2, 'heading': 'Where', 'field': thirdField, 'field_label': thirdField == null ? null : 'Location', 'sample': 'Wing A'},
      ],
      'fields': _fields,
      'ready': message != null ? 0 : 2, 'created': created, 'duplicates': 1, 'errors': 0,
      'message': message,
      'rows': rows ??
          [
            {'line': 2, 'status': dryRun ? 'ready' : 'created', 'asset_code': 'AST-0001', 'name': 'Lift A', 'category': 'lift'},
            {'line': 3, 'status': dryRun ? 'ready' : 'created', 'asset_code': 'AST-0002', 'name': 'Pump', 'category': 'pump',
              'message': "Category 'Moto' not recognised, imported as Other"},
            {'line': 4, 'status': 'duplicate', 'asset_code': 'A-9', 'name': 'Old pump', 'category': 'pump',
              'message': 'Asset code A-9 already exists in this society; skipped'},
          ],
    };

class _FakeApi extends AssetsApi {
  _FakeApi() : super(dio: Dio());
  final calls = <({bool dryRun, Map<String, String?>? mapping})>[];
  Map<String, dynamic> Function(bool dryRun, Map<String, String?>? mapping) answer =
      (dryRun, mapping) => _result(dryRun: dryRun, created: dryRun ? 0 : 2, thirdField: mapping?['Where']);

  @override
  Future<AssetImportResult> importFile(String societyId, Uint8List bytes, String fileName,
      {required bool dryRun, Map<String, String?>? mapping}) async {
    calls.add((dryRun: dryRun, mapping: mapping));
    return AssetImportResult.fromJson(answer(dryRun, mapping));
  }
}

Widget _app(_FakeApi api) => ProviderScope(
      overrides: [
        assetsApiProvider.overrideWithValue(api),
        currentUserProvider.overrideWithValue(const UserEntity(
            id: 'u1', email: 'admin@x.io', fullName: 'Admin', roles: ['Society Admin'], societyId: 'soc')),
      ],
      child: MaterialApp(
        home: AssetsImportScreen(pickFile: () async => (name: 'register.xlsx', bytes: Uint8List.fromList([1, 2, 3]))),
      ),
    );

Future<void> _choose(WidgetTester tester) async {
  await tester.tap(find.byKey(const Key('assets-import-choose')));
  await tester.pumpAndSettle();
}

void main() {
  test('an import result reads columns, fields and rows', () {
    final r = AssetImportResult.fromJson(_result());
    expect(r.columns.map((c) => c.heading), ['Asset Name', 'Kind', 'Where']);
    expect(r.columns[2].field, isNull);
    expect(r.fields.first, ('asset_code', 'Asset code'));
    expect((r.ready, r.duplicates, r.errors), (2, 1, 0));
    expect(r.rows[1].message, contains('not recognised'));
  });

  testWidgets('choosing a file shows what will be imported and checks nothing is saved', (tester) async {
    final api = _FakeApi();
    await tester.pumpWidget(_app(api));
    expect(find.byKey(const Key('assets-import-template')), findsOneWidget);

    await _choose(tester);
    expect(api.calls.single.dryRun, isTrue);
    expect(find.text('register.xlsx · Register · 3 rows'), findsOneWidget);
    expect(find.text('Columns: 2 of 3 will be imported'), findsOneWidget);
    expect(find.text('2 ready'), findsOneWidget);
    expect(find.text('1 already registered'), findsOneWidget);
    expect(find.text('Row 2: Lift A'), findsOneWidget);
    expect(find.text('Asset code A-9 already exists in this society; skipped'), findsOneWidget);
    expect(find.text('Import 2 Assets'), findsOneWidget);
  });

  testWidgets('pointing a column at a field checks the file again with that choice', (tester) async {
    final api = _FakeApi();
    await tester.pumpWidget(_app(api));
    await _choose(tester);

    await tester.tap(find.byKey(const Key('assets-import-columns')));
    await tester.pumpAndSettle();
    await tester.ensureVisible(find.byKey(const ValueKey('col-2')));
    await tester.tap(find.byKey(const ValueKey('col-2')));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Location').last);
    await tester.pumpAndSettle();

    expect(api.calls.length, 2);
    expect(api.calls.last.dryRun, isTrue);
    expect(api.calls.last.mapping, {'Asset Name': 'name', 'Kind': 'asset_category', 'Where': 'location'});
    expect(find.text('Columns: 3 of 3 will be imported'), findsOneWidget);
  });

  testWidgets('Import adds the rows and reports how many', (tester) async {
    final api = _FakeApi();
    await tester.pumpWidget(_app(api));
    await _choose(tester);

    await tester.tap(find.byKey(const Key('assets-import-go')));
    await tester.pumpAndSettle();

    expect(api.calls.last.dryRun, isFalse);
    expect(find.text('2 added'), findsOneWidget);
    expect(find.text('Done'), findsOneWidget);
    expect(find.byKey(const Key('assets-import-go')), findsNothing);
  });

  testWidgets('with no Name column the message shows and Import is not offered', (tester) async {
    final api = _FakeApi()
      ..answer = (dryRun, mapping) => _result(
            nameColumn: null, rows: const [],
            message: 'No Name column was found. Name each asset in a column headed Name (or Asset Name), '
                'or choose which column holds the name.');
    await tester.pumpWidget(_app(api));
    await _choose(tester);

    expect(find.textContaining('No Name column was found'), findsOneWidget);
    final go = tester.widget<AppPrimaryButton>(find.byKey(const Key('assets-import-go')));
    expect(go.onPressed, isNull);
  });
}
