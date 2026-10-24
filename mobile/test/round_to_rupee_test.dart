import 'package:flutter_test/flutter_test.dart';
import 'package:ar_society_app/features/maintenance_billing/data/maintenance_billing_api.dart';

void main() {
  test('the rounding setting is off unless the server says it is on', () {
    expect(MaintenanceRules.fromJson({}).roundToRupee, isFalse);
    expect(MaintenanceRules.fromJson({'round_to_rupee': false}).roundToRupee, isFalse);
    expect(MaintenanceRules.fromJson({'round_to_rupee': true}).roundToRupee, isTrue);
  });

  test('a preview flat and a bill carry their round off, nil when the server sends none', () {
    final flat = FlatPreview.fromJson({
      'flat_id': 'f1', 'flat_label': 'A / 101', 'previous_dues': '0', 'lines': [],
      'tax': '0.00', 'total': '1235.00', 'round_off': '0.44',
    });
    expect(flat.roundOff, '0.44');
    expect(FlatPreview.fromJson({
      'flat_id': 'f1', 'flat_label': 'A / 101', 'previous_dues': '0', 'lines': [], 'tax': '0', 'total': '10',
    }).roundOff, '0');
    expect(amountOf(flat.roundOff), 0.44);
    expect(amountOf('-0.49'), -0.49);
  });
}
