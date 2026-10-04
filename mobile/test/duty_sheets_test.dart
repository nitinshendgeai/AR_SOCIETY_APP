import 'package:flutter_test/flutter_test.dart';
import 'package:ar_society_app/features/staff/data/models/staff_models.dart';
import 'package:ar_society_app/features/staff/presentation/widgets/staff_widgets.dart';

void main() {
  group('duties from a plan and from paper', () {
    final json = {
      'id': 'd1', 'staff_id': 's1', 'society_id': 'soc', 'duty_name': 'Gate round',
      'duty_date': '2026-10-05', 'is_completed': true, 'is_recurring': true,
      'series_id': 'series-1', 'completion_source': 'paper',
      'checklist_items': [
        {'id': 'i1', 'duty_id': 'd1', 'title': 'Check gate', 'is_required': true,
         'is_completed': true, 'entered_from_paper': true},
        {'id': 'i2', 'duty_id': 'd1', 'title': 'Log visitors', 'is_completed': true},
      ],
    };

    test('a duty keeps its series and where it was completed', () {
      final duty = DutyModel.fromJson(json).toEntity();
      expect(duty.seriesId, 'series-1');
      expect(duty.completedFromPaper, isTrue);
      expect(duty.isRecurring, isTrue);
    });

    test('each item says whether it was entered from the printed sheet', () {
      final items = DutyModel.fromJson(json).toEntity().checklistItems;
      expect(items[0].enteredFromPaper, isTrue);
      expect(items[1].enteredFromPaper, isFalse); // absent means ticked in the app
    });

    test('a duty completed in the app is not from paper', () {
      final duty = DutyModel.fromJson({...json, 'completion_source': 'app'}).toEntity();
      expect(duty.completedFromPaper, isFalse);
    });
  });

  group('a duty plan result', () {
    test('lists what was made and the days left out with the reason', () {
      final result = DutyPlanResultModel.fromJson({
        'series_id': 'x', 'created': 5, 'first_date': '2026-10-05', 'last_date': '2026-10-11',
        'skipped': [
          {'staff_id': 's1', 'staff_name': 'Ramesh', 'duty_date': '2026-10-07', 'reason': 'On approved leave'},
        ],
      }).toEntity();
      expect(result.created, 5);
      expect(result.firstDate, '2026-10-05');
      expect(result.skipped.single.staffName, 'Ramesh');
      expect(result.skipped.single.reason, 'On approved leave');
    });

    test('nothing made and nothing skipped still parses', () {
      final result = DutyPlanResultModel.fromJson({'created': 0, 'skipped': []}).toEntity();
      expect(result.created, 0);
      expect(result.skipped, isEmpty);
      expect(result.firstDate, isNull);
    });
  });

  group('attendance times', () {
    test('the server sends UTC with a Z, which is read as UTC and shown on the local clock', () {
      final parsed = DateTime.parse('2026-10-05T03:30:00Z');
      expect(parsed.isUtc, isTrue);
      final local = parsed.toLocal();
      expect(formatTime(parsed),
          '${local.hour.toString().padLeft(2, '0')}:${local.minute.toString().padLeft(2, '0')}');
      expect(formatTime(null), '--:--');
    });
  });
}
