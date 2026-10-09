import 'package:flutter_test/flutter_test.dart';
import 'package:ar_society_app/features/shops/data/shop_import_columns.dart';
import 'package:ar_society_app/features/shops/data/shops_api.dart';

void main() {
  test('a shop reads its owner, possession date and meter from the API', () {
    final s = Shop.fromJson({
      'id': 's1', 'shop_number': 'S-1', 'owner_name': 'Mehta', 'occupancy': 'rented', 'floor': 0,
      'area_sqft': 250.0, 'possession_date': '2019-04-01', 'electric_meter_no': 'M1',
    });
    expect(s.rented, isTrue);
    expect(s.vacant, isFalse);
    expect(s.hasMeter, isTrue);
    expect(s.possessionDate, DateTime(2019, 4, 1));
    expect(occupancyLabel('owner_run'), 'Run by the owner');
    expect(Shop.fromJson({'id': 's2', 'shop_number': 'S-2', 'owner_name': 'X'}).hasMeter, isFalse);
  });

  group('the shops file is read by its headings', () {
    test('the template', () {
      final c = ShopImportColumns.fromHeader(shopImportTemplateHeader)!;
      final row = List.generate(shopImportTemplateHeader.length, (i) => 'v$i');
      expect(c.cell(row, 'shop_number'), 'v0');
      expect(c.cell(row, 'possession_date'), 'v11');
      expect(c.canonical(row), row);
    });

    test("a society's own sheet", () {
      final c = ShopImportColumns.fromHeader(
          ['Sr', 'Shop No.', 'Name of Owner', 'Mobile', 'Date of Possession', 'Meter Number', 'Name of Shop', 'Status'])!;
      final row = ['1', 'G-4', 'Iyer', '9820000000', '12-Jan-2018', 'MT-9', 'Iyer Pharmacy', 'Rented'];
      final f = c.fields(row);
      expect(f['shop_number'], 'G-4');
      expect(f['owner_name'], 'Iyer');
      expect(f['owner_phone'], '9820000000');
      expect(f['possession_date'], '12-Jan-2018');
      expect(f['electric_meter_no'], 'MT-9');
      expect(f['business_name'], 'Iyer Pharmacy');
      expect(f['occupancy'], 'Rented');
      expect(f['floor'], '');
    });

    test('without a header the template order is used; a lone heading is not a header', () {
      expect(ShopImportColumns.fromHeader(['S-1', 'Mehta', '98']), isNull);
      expect(ShopImportColumns.fromHeader(['Shop No']), isNull);
      expect(ShopImportColumns.positional().cell(['S-1', 'Mehta'], 'owner_name'), 'Mehta');
    });
  });
}
