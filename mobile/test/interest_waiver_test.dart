import 'package:flutter_test/flutter_test.dart';
import 'package:ar_society_app/features/maintenance_billing/data/maintenance_billing_api.dart';

void main() {
  test('interest waiver reads its mode, dates and flat', () {
    final none = InterestWaiver.fromJson({
      'id': 'w1', 'flat_id': 'f1', 'flat_number': '101', 'wing_name': 'A', 'mode': 'waive',
      'rate_pct': null, 'from_date': '2026-09-01', 'to_date': null, 'reason': 'Bank error', 'status': 'active',
    });
    expect(none.title, 'No interest');
    expect(none.flatLabel, 'A / 101');
    expect(none.to, isNull);

    final lower = InterestWaiver.fromJson({
      'id': 'w2', 'flat_id': 'f1', 'flat_number': '101', 'mode': 'rate', 'rate_pct': '6.00',
      'from_date': '2026-09-01', 'to_date': '2026-09-30', 'reason': 'Hardship',
    });
    expect(lower.title, 'Interest at 6% a year');
    expect(lower.flatLabel, '101');
    expect(lower.to, DateTime(2026, 9, 30));
    expect(lower.status, 'active');

    final fractional = InterestWaiver.fromJson({
      'id': 'w3', 'flat_id': 'f1', 'flat_number': '102', 'mode': 'rate', 'rate_pct': '7.50',
      'from_date': '2026-09-01', 'reason': 'x',
    });
    expect(fractional.title, 'Interest at 7.5% a year');
  });
}
