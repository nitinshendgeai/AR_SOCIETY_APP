import 'package:flutter_test/flutter_test.dart';
import 'package:ar_society_app/features/resident_master/data/import_columns.dart';

void main() {
  group('dates are read day first, as written in India', () {
    test('the usual spellings', () {
      expect(parseImportDate('01/04/2019'), DateTime(2019, 4, 1));
      expect(parseImportDate('1-4-19'), DateTime(2019, 4, 1));
      expect(parseImportDate('01.04.2019'), DateTime(2019, 4, 1));
      expect(parseImportDate('2019-04-01'), DateTime(2019, 4, 1));
      expect(parseImportDate('1-Apr-2019'), DateTime(2019, 4, 1));
      expect(parseImportDate('15 March 2021'), DateTime(2021, 3, 15));
      expect(parseImportDate('05/12/2020 00:00:00'), DateTime(2020, 12, 5));
    });
    test('day first: 03/04/2020 is 3 April', () => expect(parseImportDate('03/04/2020'), DateTime(2020, 4, 3)));
    test('two-digit years', () {
      expect(parseImportDate('1/1/99'), DateTime(1999, 1, 1));
      expect(parseImportDate('1/1/05'), DateTime(2005, 1, 1));
    });
    test('things that are not dates', () {
      for (final bad in ['', 'soon', '31/02/2020', '13/13/2020', '0/1/2020', '2020']) {
        expect(parseImportDate(bad), isNull, reason: bad);
      }
    });
  });

  group('columns are found by their headings, in any order', () {
    test('the template itself', () {
      final c = ImportColumns.fromHeader(importTemplateHeader)!;
      final row = ['A Wing', '101', 'Ramesh', 'owner', 'yes', '98', 'r@x.in', '1', '01/04/2019', 'M-1', 'C-1'];
      expect(c.cell(row, 'wing'), 'A Wing');
      expect(c.cell(row, 'possession'), '01/04/2019');
      expect(c.cell(row, 'meter'), 'M-1');
      expect(c.canonical(row), row);
    });

    test("a society's own sheet: other names, other order, extra columns", () {
      final c = ImportColumns.fromHeader(
          ['Sr No', 'Name of Member', 'Flat No', 'Block', 'Mobile', 'Date of Possession', 'Meter Number', 'Remarks'])!;
      final row = ['1', 'Meera Patil', '101', 'A', '9820000000', '12-Jan-2018', 'MT-77', 'x'];
      expect(c.cell(row, 'name'), 'Meera Patil');
      expect(c.cell(row, 'flat'), '101');
      expect(c.cell(row, 'wing'), 'A');
      expect(c.cell(row, 'possession'), '12-Jan-2018');
      expect(c.cell(row, 'meter'), 'MT-77');
      expect(c.cell(row, 'email'), '');          // not in the file: empty
      expect(c.has('consumer'), isFalse);
    });

    test('a data row is not mistaken for a header', () {
      expect(ImportColumns.fromHeader(['A Wing', '101', 'Ramesh Kumar', 'owner', 'yes']), isNull);
      expect(ImportColumns.fromHeader(['Wing']), isNull);        // a lone heading is not enough
    });

    test('with no header the template order is used, and short rows read as empty', () {
      final c = ImportColumns.positional();
      final row = ['A Wing', '101', 'Ramesh', 'owner', 'yes', '98', 'r@x.in'];
      expect(c.cell(row, 'name'), 'Ramesh');
      expect(c.cell(row, 'floor'), '');
      expect(c.cell(row, 'possession'), '');
      expect(c.canonical(row).length, importTemplateHeader.length);
    });
  });
}
