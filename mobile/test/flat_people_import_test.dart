import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/resident_master/data/flat_people_import.dart';
import 'package:ar_society_app/features/resident_master/presentation/screens/flat_people_import_screen.dart';

void main() {
  group('reading a vehicles sheet by its headings', () {
    test("the society's own headings, in any order, are found", () {
      final cols = PeopleImportColumns.fromHeader(vehiclesImportSpec,
          ['Sr', 'Reg. No.', 'Block', 'Flat Number', 'Colour', 'Two/Four Wheeler', 'Brand', 'Owner'])!;
      final row = ['1', 'MH12 AB 1234', 'A', '101', 'White', 'Four wheeler', 'Honda', 'Asha Rao'];
      expect(cols.fields(row), {
        'wing': 'A', 'flat_number': '101', 'vehicle_number': 'MH12 AB 1234', 'vehicle_type': 'Four wheeler', 'make': 'Honda',
        'model': '', 'color': 'White', 'parking_slot': '', 'owner_name': 'Asha Rao', 'remarks': '',
      });
    });

    test('the template reads back as itself, and a sheet with no header is read by position', () {
      for (final spec in [vehiclesImportSpec, familyImportSpec]) {
        final cols = PeopleImportColumns.fromHeader(spec, spec.templateHeader);
        expect(cols, isNotNull, reason: spec.kind);
        for (final example in spec.templateExamples) {
          expect(example.length, spec.templateHeader.length, reason: spec.kind);
          expect(cols!.canonical(example), example, reason: spec.kind);
        }
        expect(PeopleImportColumns.positional(spec).canonical(spec.templateExamples.first), spec.templateExamples.first);
      }
    });

    test('a row of data is not mistaken for a header', () {
      expect(PeopleImportColumns.fromHeader(vehiclesImportSpec, ['A', '101', 'MH12AB1234', 'Car']), isNull);
      expect(PeopleImportColumns.fromHeader(familyImportSpec, ['A', '101', 'Sunita Rao', 'Wife']), isNull);
      expect(PeopleImportColumns.fromHeader(vehiclesImportSpec, ['Wing', 'Flat No', 'Owner Name']), isNull); // no vehicle number
    });
  });

  test('family sheets are read by their own headings', () {
    final cols = PeopleImportColumns.fromHeader(
        familyImportSpec, ['Flat', 'Family Member Name', 'Relation with Owner', 'DOB', 'Mobile No'])!;
    final row = ['101', 'Sunita Rao', 'Wife', '14/03/1982', '9876543210'];
    expect(cols.fields(row)['full_name'], 'Sunita Rao');
    expect(cols.fields(row)['relationship'], 'Wife');
    expect(cols.fields(row)['date_of_birth'], '14/03/1982');
    expect(cols.fields(row)['phone'], '9876543210');
    expect(cols.fields(row)['wing'], '');
  });

  for (final spec in [vehiclesImportSpec, familyImportSpec]) {
    testWidgets('the ${spec.kind} import opens with its instructions, a template and a file chooser', (t) async {
      t.view.physicalSize = const Size(420, 2200);
      t.view.devicePixelRatio = 1.0;
      addTearDown(t.view.resetPhysicalSize);
      addTearDown(t.view.resetDevicePixelRatio);
      await t.pumpWidget(ProviderScope(
        child: MaterialApp(theme: AppTheme.lightTheme, home: FlatPeopleImportScreen(spec: spec)),
      ));
      await t.pumpAndSettle();
      expect(find.text(spec.title), findsWidgets);
      expect(find.byKey(const Key('people-import-template')), findsOneWidget);
      expect(find.text('Choose CSV File'), findsOneWidget);
      expect(find.textContaining('nothing is saved until you press Import'), findsOneWidget);
      expect(find.textContaining(spec.kind == 'vehicles' ? 'One row per vehicle' : 'One row per person', findRichText: true), findsOneWidget);
    });
  }
}
