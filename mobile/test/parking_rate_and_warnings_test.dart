import 'package:flutter_test/flutter_test.dart';
import 'package:ar_society_app/features/accounts/data/accounts_api.dart';
import 'package:ar_society_app/features/maintenance_billing/data/maintenance_billing_api.dart';

void main() {
  test('parking head shows its two-wheeler rate beside the car rate', () {
    final both = ChargeHead.fromJson({
      'id': 'c1', 'charge_type': 'parking', 'name': 'Parking', 'default_amount': '500.00',
      'basis': 'parking', 'two_wheeler_rate': '150.00',
    });
    expect(both.twoWheelerRate, '150.00');
    expect(both.rateLabel, contains('2-wheeler'));
    expect(both.rateLabel, contains('150'));

    final carOnly = ChargeHead.fromJson({
      'id': 'c2', 'charge_type': 'parking', 'name': 'Parking', 'default_amount': '500.00',
      'basis': 'parking', 'two_wheeler_rate': null,
    });
    expect(carOnly.twoWheelerRate, isNull);
    expect(carOnly.rateLabel, isNot(contains('2-wheeler')));
  });

  test('accounts summary carries the warnings about the books', () {
    final base = {
      'fy': '2026-27', 'cash': '-5000.00', 'bank': '0.00', 'creditors': '0.00',
      'fy_income': '0.00', 'fy_expense': '5000.00', 'fy_surplus': '-5000.00',
    };
    final s = AccountsSummary.fromJson({
      ...base,
      'warnings': [
        {'code': 'negative_cash', 'account_id': 'a1', 'message': 'Cash in Hand is ₹5,000 in credit'},
        {'code': 'opening_unbalanced', 'account_id': null, 'message': 'Opening balances don\'t agree'},
      ],
    });
    expect(s.warnings.map((w) => w.code), ['negative_cash', 'opening_unbalanced']);
    expect(s.warnings.first.accountId, 'a1');
    expect(s.warnings.last.accountId, isNull);
    expect(AccountsSummary.fromJson(base).warnings, isEmpty);
  });
}
