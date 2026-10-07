import 'package:flutter_test/flutter_test.dart';
import 'package:ar_society_app/features/accounts/data/recurring_api.dart';
import 'package:ar_society_app/features/assets/data/assets_api.dart';
import 'package:ar_society_app/features/assets/presentation/screens/asset_sheets.dart' show addMonths;

void main() {
  group('Asset', () {
    test('reads the register fields and the server-worked status', () {
      final a = Asset.fromJson({
        'id': 'a1',
        'asset_code': 'AST-0001',
        'name': 'Terrace water pump',
        'asset_category': 'pump',
        'status': 'active',
        'purchase_cost': '48500.00',
        'service_interval_months': 6,
        'last_serviced_on': '2026-03-31',
        'next_service_due': '2026-09-30',
        'warranty_status': 'expiring',
        'service_status': 'overdue',
        'days_to_service': -7,
      });
      expect(a.purchaseCost, 48500);
      expect(a.nextServiceDue, DateTime(2026, 9, 30));
      expect(a.serviceStatus, 'overdue');
      expect(a.isRetired, isFalse);
      expect(serviceLabel(a.serviceStatus, a.daysToService), 'Overdue by 7 days');
      expect(assetCategoryLabel(a.category), 'Water pump');
    });

    test('a retired asset is not counted as in use', () {
      final a = Asset.fromJson({'id': 'a2', 'asset_code': 'AST-0002', 'name': 'Old AC', 'asset_category': 'air_conditioner', 'status': 'disposed'});
      expect(a.isRetired, isTrue);
      expect(a.serviceStatus, 'none');
    });

    test('service labels read plainly', () {
      expect(serviceLabel('due_soon', 12), 'Service in 12 days');
      expect(serviceLabel('due_soon', 1), 'Service in 1 day');
      expect(serviceLabel('due_soon', 0), 'Service due today');
      expect(serviceLabel('overdue', -1), 'Overdue by 1 day');
      expect(serviceLabel('ok', 90), 'Service on schedule');
    });

    test('the history gathers services, contracts and the total spent', () {
      final h = AssetHistory.fromJson({
        'asset': {'id': 'a1', 'asset_code': 'AST-0001', 'name': 'Pump', 'asset_category': 'pump', 'status': 'active'},
        'maintenance': [
          {'id': 'm1', 'maintenance_type': 'preventive', 'status': 'completed', 'scheduled_date': '2026-10-01', 'completed_date': '2026-10-01', 'cost': '2350.00'},
          {'id': 'm2', 'maintenance_type': 'corrective', 'status': 'scheduled', 'scheduled_date': '2026-11-01'},
        ],
        'amc': [],
        'contracts': [
          {'id': 'c1', 'contract_number': 'AMC-2026-0001', 'contract_name': 'Pump AMC', 'status': 'active', 'start_date': '2026-04-01', 'end_date': '2027-03-31', 'annual_value': '12000.00'},
        ],
        'work_orders': [],
        'log': [],
        'total_service_cost': '2350.00',
      });
      expect(h.services.where((s) => s.isOpen).length, 1);
      expect(h.contracts.single.annualValue, 12000);
      expect(h.totalServiceCost, 2350);
      expect(h.currentAmc, isNull);
    });
  });

  group('addMonths', () {
    test('respects month ends', () {
      expect(addMonths(DateTime(2026, 1, 31), 1), DateTime(2026, 2, 28));
      expect(addMonths(DateTime(2027, 1, 31), 1), DateTime(2027, 2, 28));
      expect(addMonths(DateTime(2028, 1, 31), 1), DateTime(2028, 2, 29));
    });

    test('crosses the year', () {
      expect(addMonths(DateTime(2026, 11, 15), 3), DateTime(2027, 2, 15));
      expect(addMonths(DateTime(2026, 3, 15), 12), DateTime(2027, 3, 15));
    });
  });

  group('Recurring expense', () {
    test('a bill that changes every month has no amount', () {
      final r = RecurringExpense.fromJson({
        'id': 'r1',
        'name': 'Electricity',
        'expense_account_id': 'x',
        'amount': null,
        'day_of_month': 5,
        'start_month': '2026-09-01',
        'is_active': true,
        'due_months': 2,
      });
      expect(r.amount, isNull);
      expect(r.dueMonths, 2);
      expect(r.endMonth, isNull);
    });

    test('a due month carries what to record', () {
      final d = DueExpense.fromJson({
        'recurring_id': 'r1',
        'name': 'Security agency',
        'month': '2026-08-01',
        'due_date': '2026-08-01',
        'days_late': 67,
        'amount': '30000.00',
        'element_name': 'Security Services',
      });
      expect(d.amount, 30000);
      expect(d.daysLate, 67);
      expect(d.month, DateTime(2026, 8, 1));
      expect(d.elementName, 'Security Services');
    });
  });
}
