import 'package:flutter_test/flutter_test.dart';
import 'package:ar_society_app/features/maintenance_billing/data/maintenance_billing_api.dart';

void main() {
  test('a charge head reads its expense mode and defaults to the trailing average', () {
    final period = ChargeHead.fromJson({
      'id': 'c1', 'charge_type': 'maintenance', 'name': 'Housekeeping', 'basis': 'per_sqft',
      'auto_from_expenses': true, 'expense_mode': 'period',
    });
    expect(period.expenseMode, 'period');
    expect(period.isPeriodExpense, isTrue);

    final trailing = ChargeHead.fromJson({
      'id': 'c2', 'charge_type': 'maintenance', 'name': 'Security', 'auto_from_expenses': true,
    });
    expect(trailing.expenseMode, 'trailing');
    expect(trailing.isPeriodExpense, isFalse);

    // The mode means nothing unless the head bills from expenses at all.
    final off = ChargeHead.fromJson({
      'id': 'c3', 'charge_type': 'maintenance', 'name': 'Lift', 'auto_from_expenses': false, 'expense_mode': 'period',
    });
    expect(off.isPeriodExpense, isFalse);
  });

  test('the preview carries the working of each actual-expense head', () {
    final p = CyclePreview.fromJson({
      'months': 1, 'flats_count': 3, 'total': '10000.01', 'warnings': ['x'],
      'expense_allocations': [
        {
          'charge_name': 'Housekeeping', 'element_name': 'Housekeeping', 'method': 'area',
          'period_start': '2026-10-01', 'period_end': '2026-10-31', 'pool_amount': '10000.01',
          'allocated_amount': '10000.01', 'eligible_flats': 3, 'rate': '2.5000', 'pending_amount': '300.00',
          'sources': [
            {'voucher_number': 'PV-1', 'voucher_date': '2026-10-05', 'ledger_name': 'Housekeeping', 'amount': '10000.01'}
          ],
        }
      ],
      'flats': [],
    });
    final a = p.expenseAllocations.single;
    expect(a.byArea, isTrue);
    expect(a.reconciled, isTrue);
    expect(a.eligibleFlats, 3);
    expect(a.pendingAmount, '300.00');
    expect(a.sources.single.voucherNumber, 'PV-1');
    expect(a.periodEnd, DateTime(2026, 10, 31));
  });

  test('a preview from an older server has no allocations', () {
    final p = CyclePreview.fromJson({'months': 1, 'flats_count': 0, 'total': '0', 'flats': []});
    expect(p.expenseAllocations, isEmpty);
  });

  test('shares that do not match the pool are flagged as not reconciled', () {
    final a = ExpenseAllocation.fromJson({
      'charge_name': 'X', 'method': 'equal', 'period_start': '2026-10-01', 'period_end': '2026-10-31',
      'pool_amount': '100.00', 'allocated_amount': '99.99', 'eligible_flats': 3, 'rate': '33.3300',
    });
    expect(a.reconciled, isFalse);
    expect(a.byArea, isFalse);
  });
}
