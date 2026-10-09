import 'package:flutter_test/flutter_test.dart';
import 'package:ar_society_app/features/stores/data/stores_api.dart';

void main() {
  test('quantities drop needless zeros', () {
    expect(qty(5), '5');
    expect(qty(2.5), '2.5');
    expect(qty(0.25), '0.25');
    expect(qty(1.5), '1.5');
  });

  test('an item says how much is in stock and whether it is low or out', () {
    final low = StoreItem.fromJson({
      'id': 'i1', 'item_code': 'ITM-0001', 'name': 'Floor cleaner', 'category': 'cleaning', 'unit_type': 'litre',
      'minimum_stock': 10, 'current_stock': 4, 'is_low_stock': true, 'unit_cost': '85.50',
    });
    expect(low.stockText, '4 litre');
    expect(low.low, isTrue);
    expect(low.out, isFalse);
    expect(low.unitCost, 85.5);
    final out = StoreItem.fromJson({'id': 'i2', 'item_code': 'ITM-0002', 'name': 'Bulbs', 'category': 'electrical', 'unit_type': 'piece', 'current_stock': 0, 'is_low_stock': true});
    expect(out.out, isTrue);
    expect(itemCategoryLabel(out.category), 'Electrical');
    expect(unitLabel('meter'), 'metre');
  });

  test('the summary reads the numbers the Stores screen shows', () {
    final s = StoresSummary.fromJson({'items': 12, 'low_stock': 3, 'out_of_stock': 1, 'stock_value': 4500.5, 'out_with_people': 4, 'overdue_returns': 2});
    expect(s.items, 12);
    expect(s.low, 3);
    expect(s.outOfStock, 1);
    expect(s.value, 4500.5);
    expect(s.withPeople, 4);
    expect(s.overdue, 2);
  });

  test('an issue still out says what is outstanding; an overdue one says so; a used-up one has nothing to return', () {
    IssueItem make(Map<String, dynamic> o) => IssueItem.fromJson({
          'id': 'x', 'item_id': 'i', 'item_name': 'Torch', 'unit': 'piece', 'status': 'issued', 'quantity_issued': 4,
          'quantity_returned': 1, 'outstanding': 3, 'issued_to_name': 'Hema', 'overdue': false, ...o,
        });
    final ok = make({});
    expect(ok.isOut, isTrue);
    expect(ok.outstanding, 3);
    expect(ok.statusLabel, 'With them');
    final late = make({'overdue': true});
    expect(late.statusLabel, 'Overdue');
    final done = make({'status': 'consumed', 'outstanding': 0});
    expect(done.isOut, isFalse);
    expect(done.statusLabel, 'Used up');
    expect(make({'status': 'returned', 'outstanding': 0}).statusLabel, 'Returned');
  });

  test('stock movements know which way they went', () {
    expect(txnAdds('stock_in'), isTrue);
    expect(txnAdds('return'), isTrue);
    expect(txnAdds('stock_out'), isFalse);
    expect(txnLabel('consumption'), 'Used up');
    final m = StockMove.fromJson({'transaction_type': 'stock_in', 'quantity': 8, 'quantity_before': 0, 'quantity_after': 8, 'performed_by_name': 'Manoj', 'reference_id': 'Bill 114'});
    expect(m.after, 8);
    expect(m.by, 'Manoj');
  });
}
