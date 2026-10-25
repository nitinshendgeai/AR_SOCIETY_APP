import 'package:flutter_test/flutter_test.dart';
import 'package:ar_society_app/features/maintenance_billing/data/maintenance_billing_api.dart';

void main() {
  test('a society that never chose a layout prints the standard bill', () {
    expect(MaintenanceRules.fromJson({}).billLayout, 'standard');
    expect(MaintenanceRules.fromJson({'bill_layout': null}).billLayout, 'standard');
  });

  test('the chosen layout is read from the rules', () {
    expect(MaintenanceRules.fromJson({'bill_layout': 'classic'}).billLayout, 'classic');
    expect(MaintenanceRules.fromJson({'bill_layout': 'standard'}).billLayout, 'standard');
  });
}
