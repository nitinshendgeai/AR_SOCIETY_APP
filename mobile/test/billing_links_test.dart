import 'package:flutter_test/flutter_test.dart';
import 'package:ar_society_app/features/accounts/data/accounts_api.dart';
import 'package:ar_society_app/features/maintenance_billing/data/maintenance_billing_api.dart';

void main() {
  test('charge head reads the budget-from-expenses option', () {
    final c = ChargeHead.fromJson({
      'id': 'c1', 'charge_type': 'security', 'name': 'Security', 'default_amount': '1.00',
      'basis': 'budget_equal', 'auto_from_expenses': true, 'expense_months': 6,
    });
    expect(c.autoFromExpenses, isTrue);
    expect(c.expenseMonths, 6);
    final plain = ChargeHead.fromJson({'id': 'c2', 'charge_type': 'maintenance', 'name': 'M'});
    expect(plain.autoFromExpenses, isFalse);
    expect(plain.expenseMonths, 12);
  });

  test('budget suggestions list expense heads and unlinked ledgers by name', () {
    final s = BudgetSuggestions.fromJson({
      'period_start': '2025-10-01', 'period_end': '2026-09-30', 'months_covered': 3,
      'suggestions': [
        {
          'charge_id': 'c1', 'charge_name': 'Security', 'basis': 'budget_equal', 'current_amount': '1.00',
          'expense_heads': ['Security Charges', 'CCTV'], 'spent': '36000.00', 'annual_estimate': '144000.00',
          'suggested_amount': '144000.00', 'auto_from_expenses': false,
        }
      ],
      'unlinked': [
        {'account_id': 'a1', 'name': 'Repairs — Plumbing', 'spent': '5000.00'}
      ],
    });
    expect(s.suggestions.single.expenseHeads, ['Security Charges', 'CCTV']);
    expect(s.unlinked.single, ('Repairs — Plumbing', '5000.00'));
  });

  test('flat charge status wording', () {
    Map<String, dynamic> j(String status, {bool recurring = false, String? invoice}) => {
          'id': 'f1', 'flat_id': 'x', 'flat_number': '101', 'wing_name': 'A', 'kind': 'fine', 'title': 'Late',
          'amount': '500.00', 'effective_date': '2026-10-01', 'recurring': recurring, 'status': status,
          'invoice_number': invoice,
        };
    expect(FlatCharge.fromJson(j('active')).statusLabel, 'Waiting for next bill');
    expect(FlatCharge.fromJson(j('active', recurring: true)).statusLabel, 'Every bill');
    expect(FlatCharge.fromJson(j('billed', invoice: 'INV-1')).statusLabel, 'On bill INV-1');
    expect(FlatCharge.fromJson(j('billed')).canCancel, isFalse);
    expect(FlatCharge.fromJson(j('active')).canCancel, isTrue);
    expect(FlatCharge.fromJson(j('active')).flatLabel, 'A / 101');
  });

  test('ledger carries the element it counts towards', () {
    final a = LedgerAccount.fromJson({
      'id': 'a', 'group_id': 'g', 'name': 'Security Charges', 'maintenance_element_id': 'e1',
      'maintenance_element_name': 'Security',
    });
    expect(a.maintenanceElementId, 'e1');
    expect(a.maintenanceElementName, 'Security');
  });
}
