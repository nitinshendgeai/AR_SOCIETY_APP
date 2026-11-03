import 'package:flutter_test/flutter_test.dart';
import 'package:ar_society_app/features/accounts/data/bank_reconciliation_api.dart';

String _fmt(DateTime d) => '${d.day}/${d.month}/${d.year}';

void main() {
  group('what an imported statement says about itself', () {
    test('a PDF statement: lines added, its period, what was already there, and that its totals were checked', () {
      final r = StatementImportResult.fromJson({
        'entries': [],
        'summary': {
          'file_type': 'pdf',
          'imported': 97,
          'skipped_duplicates': 3,
          'totals_checked': true,
          'period_from': '2026-10-01',
          'period_to': '2026-11-03',
        },
      });
      expect(r.isPdf, isTrue);
      expect(r.message(_fmt),
          'Imported 97 lines from the statement · 1/10/2026 to 3/11/2026 · 3 already imported · totals checked against the statement');
    });

    test('a statement that was already imported says nothing is new', () {
      final r = StatementImportResult.fromJson({
        'entries': [],
        'summary': {'file_type': 'pdf', 'imported': 0, 'skipped_duplicates': 106, 'totals_checked': true},
      });
      expect(r.message(_fmt), startsWith('Nothing new: all 106 lines in this statement were already imported'));
    });

    test('a CSV (no period, nothing checked) and a single line read plainly', () {
      final r = StatementImportResult.fromJson({
        'entries': [{}],
        'summary': {'file_type': 'csv', 'imported': 1, 'skipped_duplicates': 0},
      });
      expect(r.isPdf, isFalse);
      expect(r.message(_fmt), 'Imported 1 line from the statement');
    });

    test('an older server that answers with no summary still gives a count', () {
      final r = StatementImportResult.fromJson({'entries': [{}, {}, {}]});
      expect(r.imported, 3);
    });
  });
}
