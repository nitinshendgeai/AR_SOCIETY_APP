import 'package:flutter_test/flutter_test.dart';
import 'package:ar_society_app/features/maintenance_billing/data/maintenance_billing_api.dart';

void main() {
  test('the billing start date is read from the rules, and absent means each cycle bills its own period', () {
    expect(MaintenanceRules.fromJson({'billing_start_date': '2026-08-01'}).billingStartDate, DateTime(2026, 8, 1));
    expect(MaintenanceRules.fromJson({'billing_start_date': null}).billingStartDate, isNull);
    expect(MaintenanceRules.fromJson({}).billingStartDate, isNull);
  });

  test('a flat in the preview carries the days and months its bill charges for', () {
    final f = FlatPreview.fromJson({
      'flat_id': 'f1', 'flat_label': 'A / 101', 'area_sqft': 650.0, 'occupancy': null, 'previous_dues': '0',
      'lines': [], 'tax': '0', 'total': '1500.00',
      'period_start': '2026-09-16', 'period_end': '2026-10-31', 'months': '1.5',
    });
    expect(f.periodStart, DateTime(2026, 9, 16));
    expect(f.periodEnd, DateTime(2026, 10, 31));
    expect(f.months, '1.5');
    // an older answer without a period still reads
    final old = FlatPreview.fromJson({
      'flat_id': 'f2', 'flat_label': 'A / 102', 'previous_dues': '0', 'lines': [], 'tax': '0', 'total': '1000.00',
    });
    expect(old.periodStart, isNull);
    expect(old.months, isNull);
  });
}
