import 'package:flutter_test/flutter_test.dart';
import 'package:ar_society_app/features/maintenance_billing/data/maintenance_billing_api.dart';

void main() {
  test('the tower parking preview reads zones, holders and their parking lines', () {
    final p = TowerParkingPreview.fromJson({
      'cycle_name': 'Nov 2026', 'months': 1, 'total': '1650.00', 'warnings': [],
      'zones': [
        {'zone_id': 'z1', 'zone_name': 'Tower', 'heads': ['Tower Parking AMC'], 'holders': 2, 'slots': 3, 'total': '1650.00'},
      ],
      'flats': [
        {
          'flat_label': 'A / 101', 'zone_id': 'z1', 'zone_name': 'Tower', 'slots': 2, 'total': '1100.00',
          'lines': [
            {'description': 'Tower Parking AMC', 'total': '800.00', 'is_zone_head': true},
            {'description': 'Car Parking', 'total': '300.00', 'is_zone_head': false},
          ],
        },
      ],
    });
    expect(p.zones.single.slots, 3);
    expect(p.flats.single.slots, 2);
    expect(p.flats.single.lines.map((l) => l.isZoneHead), [true, false]);
    expect(formatRupees(p.total), contains('1,650'));
  });

  test('an empty answer (no tower heads) reads as nothing to show', () {
    final p = TowerParkingPreview.fromJson({'zones': [], 'flats': [], 'total': '0.00'});
    expect(p.zones, isEmpty);
    expect(p.flats, isEmpty);
  });
}
