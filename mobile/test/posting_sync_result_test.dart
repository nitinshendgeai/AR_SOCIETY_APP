import 'package:flutter_test/flutter_test.dart';
import 'package:ar_society_app/features/accounts/data/accounts_api.dart';

void main() {
  test('"Post now" counts what went in and lists what the books refused, with the reason', () {
    final r = PostingSyncResult.fromJson({
      'total': 5,
      'failed': 2,
      'errors': [
        {'type': 'Vendor bill', 'number': 'B-7', 'vendor': 'Sparkle Services', 'message': 'GST component is required'},
        {'type': 'Receipt', 'number': '', 'vendor': null, 'message': 'No bank ledger'},
      ],
    });
    expect(r.total, 5);
    expect(r.posted, 3);
    expect(r.failures.length, 2);
    expect(r.failures.first.label, 'Vendor bill B-7 of Sparkle Services');
    expect(r.failures.first.message, 'GST component is required');
    expect(r.failures.last.label, 'Receipt');
  });

  test('an answer without errors means everything was posted', () {
    final r = PostingSyncResult.fromJson({'total': 3});
    expect(r.posted, 3);
    expect(r.failures, isEmpty);
    expect(PostingSyncResult.fromJson({}).total, 0);
  });
}
