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
      final row = ['A Wing', '101', 'Ramesh', 'owner', 'yes', '98', 'r@x.in', '1', '01/04/2019', 'M-1', 'C-1', '2 BHK', '650'];
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

  group('flat type (BHK) as people write it', () {
    String? v(String t) => parseFlatType(t).value;
    test('the usual spellings', () {
      for (final t in ['2 BHK', '2bhk', '2-BHK', '2 B.H.K', '2BHK ', '2']) {
        expect(v(t), '2BHK', reason: t);
      }
      expect(v('1 bhk'), '1BHK');
      expect(v('3 BHK'), '3BHK');
      expect(v('4BHK'), '4BHK');
      expect(v('2.5 BHK'), '2BHK');
    });
    test('named types, and 1 RK as a studio (with a note)', () {
      expect(v('Studio'), 'Studio');
      expect(v('penthouse'), 'Penthouse');
      expect(v('Duplex'), 'Duplex');
      expect(v('shop'), 'Shop');
      expect(v('Office'), 'Office');
      expect(v('1 RK'), 'Studio');
      expect(parseFlatType('1 RK').note, isNotNull);
    });
    test('five or more BHK is kept as Other, said so', () {
      expect(v('5 BHK'), 'Other');
      expect(parseFlatType('6bhk').note, contains('Other'));
    });
    test('blank is nothing, nonsense is an error that lists what to use', () {
      expect(parseFlatType(''), (value: null, note: null, error: null));
      expect(parseFlatType('big').error, contains('2 BHK'));
      expect(parseFlatType('15').value, isNull);       // a bare 15 is not a BHK
      expect(parseFlatType('15').error, isNotNull);
    });
  });

  group('flat area in square feet', () {
    test('plain numbers and the usual decorations', () {
      expect(parseAreaSqft('650').sqft, 650);
      expect(parseAreaSqft('650.5').sqft, 650.5);
      expect(parseAreaSqft('1,050').sqft, 1050);
      expect(parseAreaSqft('650 sq ft').sqft, 650);
      expect(parseAreaSqft('650 sqft').sqft, 650);
      expect(parseAreaSqft('650 Sq.Ft.').sqft, 650);
    });
    test('square metres are converted', () {
      expect(parseAreaSqft('60 sq m').sqft, 645.83);
      expect(parseAreaSqft('60 sqm').sqft, 645.83);
    });
    test('blank is nothing; non-numbers, zero and absurd areas are errors', () {
      expect(parseAreaSqft('').error, isNull);
      expect(parseAreaSqft('').sqft, isNull);
      for (final bad in ['big', '0', '-5', '999999999']) {
        expect(parseAreaSqft(bad).sqft, isNull, reason: bad);
        expect(parseAreaSqft(bad).error, isNotNull, reason: bad);
      }
    });
  });

  group('the new columns are found by their headings', () {
    final header = ['Wing', 'Flat No', 'Name', 'BHK', 'Carpet Area (Sq.Ft.)', 'Date of Purchase'];
    final row = ['A', '101', 'Ramesh', '2 BHK', '650', '01/04/2019'];

    test('type, area and a purchase date read from a sheet of the society\'s own', () {
      final c = ImportColumns.fromHeader(header)!;
      expect(c.cell(row, 'bhk'), '2 BHK');
      expect(c.cell(row, 'area'), '650');
      final d = c.dateOf(row);
      expect(d.text, '01/04/2019');
      expect(d.heading, 'Purchase Date');
    });

    test('the possession date wins when a sheet has both', () {
      final c = ImportColumns.fromHeader(['Wing', 'Flat', 'Name', 'Purchase Date', 'Possession Date'])!;
      final r = ['A', '1', 'X', '01/01/2018', '01/04/2019'];
      expect(c.dateOf(r).text, '01/04/2019');
      expect(c.dateOf(r).heading, 'Possession Date');
      // ... and the purchase date stands in when the possession cell is empty
      expect(c.dateOf(['A', '1', 'X', '01/01/2018', '']).text, '01/01/2018');
    });

    test('the template carries the new columns last, so older files still read by position', () {
      expect(importTemplateHeader.sublist(importTemplateHeader.length - 2), ['Flat Type', 'Area (sq ft)']);
      final c = ImportColumns.fromHeader(importTemplateHeader)!;
      final t = ['A Wing', '101', 'Ramesh', 'owner', 'yes', '98', 'r@x.in', '1', '01/04/2019', 'M-1', 'C-1', '2 BHK', '650'];
      expect(c.cell(t, 'bhk'), '2 BHK');
      expect(c.cell(t, 'area'), '650');
      final old = ImportColumns.positional();
      expect(old.cell(['A Wing', '101', 'Ramesh', 'owner', 'yes', '98', 'r@x.in', '1', '01/04/2019', 'M-1', 'C-1'], 'bhk'), '');
    });
  });
}
