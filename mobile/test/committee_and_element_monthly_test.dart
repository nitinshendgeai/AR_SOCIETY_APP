import 'package:flutter_test/flutter_test.dart';
import 'package:ar_society_app/features/accounts/data/element_monthly_api.dart';
import 'package:ar_society_app/features/accounts/presentation/screens/element_monthly_screen.dart';
import 'package:ar_society_app/features/governance/data/committee_api.dart';

void main() {
  group('committee', () {
    test('register parses the committee, its office-bearers and warnings', () {
      final r = CommitteeRegister.fromJson({
        'current': {
          'id': 'c1', 'name': 'Managing Committee 2025–2030', 'formed_on': '2025-04-01', 'term_ends_on': '2030-03-31',
          'days_left': 1500, 'term_over': false,
          'members': [
            {'id': 'm1', 'full_name': 'A Patil', 'flat': 'A 101', 'position': 'chairman', 'position_label': 'Chairman',
             'phone': '9800000001', 'from_date': '2025-04-01', 'cheque_signatory': true,
             'authorities': ['Cheque signatory'], 'spending_limit': 25000},
            {'id': 'm2', 'full_name': 'B Joshi', 'position': 'treasurer', 'from_date': '2025-04-01'},
          ],
          'former_members': [],
          'warnings': ['No Secretary in office.'],
        },
        'past': [
          {'id': 'c0', 'name': 'Old', 'formed_on': '2020-04-01', 'members': []},
        ],
      });
      final c = r.current!;
      expect(c.members.first.positionLabel, 'Chairman');
      expect(c.members.first.spendingLimit, 25000);
      expect(c.members.first.authorities, ['Cheque signatory']);
      expect(c.members[1].positionLabel, 'Treasurer');   // label filled in from the position
      expect(c.warnings, ['No Secretary in office.']);
      expect(r.past.single.name, 'Old');
      expect(c.termEndsOn, DateTime(2030, 3, 31));
    });

    test('member payload: resident or name needed, limit must be a number, replace only when asked', () {
      expect(() => committeeMemberPayload(position: 'member'), throwsFormatException);
      expect(() => committeeMemberPayload(fullName: 'X', position: 'member', spendingLimit: 'ten'), throwsFormatException);
      final p = committeeMemberPayload(
          residentId: 'r1', position: 'secretary', phone: ' 98 ', spendingLimit: '10,000', fromDate: DateTime(2025, 5, 2));
      expect(p, {'resident_id': 'r1', 'position': 'secretary', 'phone': '98', 'from_date': '2025-05-02',
                 'spending_limit': 10000});
      expect(committeeMemberPayload(fullName: 'Y', position: 'chairman', replace: true)['replace'], true);
    });

    test('every office has a label', () {
      for (final p in kCommitteePositions) {
        expect(positionLabel(p.$1), p.$2);
      }
      expect(positionLabel('unknown'), 'unknown');
    });
  });

  group('element-wise monthly', () {
    final report = ElementMonthly.fromJson({
      'date_from': '2026-04-01', 'date_to': '2026-05-31',
      'months': [{'month': '2026-04', 'label': 'Apr 2026'}, {'month': '2026-05', 'label': 'May 2026'}],
      'rows': [
        {'element_id': 'e1', 'element': 'Security', 'spent': ['30000.00', '31000.00'], 'billed': ['32000.00', '32000.00'],
         'spent_total': '61000.00', 'billed_total': '64000.00', 'difference': '3000.00', 'has_ledger': true},
        {'element_id': 'none', 'element': 'Not counted towards any element', 'spent': ['0.00', '500.00'],
         'billed': ['0.00', '0.00'], 'spent_total': '500.00', 'billed_total': '0.00', 'difference': '-500.00',
         'has_ledger': true},
      ],
      'totals': {'spent': ['30000.00', '31500.00'], 'billed': ['32000.00', '32000.00'], 'spent_total': '61500.00',
                 'billed_total': '64000.00', 'difference': '2500.00'},
      'note': 'n',
    });

    test('parses months, rows and totals', () {
      expect(report.months, ['Apr 2026', 'May 2026']);
      expect(report.rows.first.spent, [30000, 31000]);
      expect(report.rows.last.elementId, 'none');
      expect(report.totals.spentTotal, 61500);
      expect(report.totals.difference, 2500);
    });

    test('each view shows its own figures', () {
      final s = report.rows.first;
      void check(ElementView v, List<double> months, double total) {
        final (vals, sum) = elementViewValues(s, v);
        expect(vals, months);
        expect(sum, total);
      }
      check(ElementView.spent, [30000, 31000], 61000);
      check(ElementView.billed, [32000, 32000], 64000);
      check(ElementView.difference, [2000, 1000], 3000);
    });
  });
}
