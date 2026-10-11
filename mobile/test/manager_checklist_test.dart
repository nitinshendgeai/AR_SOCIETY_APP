import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/auth/domain/entities/user_entity.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/features/manager_checklist/data/checklist_api.dart';
import 'package:ar_society_app/features/manager_checklist/presentation/screens/manager_checklist_screen.dart';

UserEntity _user() => const UserEntity(id: 'u', email: 'u@t.com', fullName: 'Meera Manager', roles: ['Manager'], societyId: 's1');

void _size(WidgetTester t, Size s) {
  t.view.physicalSize = s;
  t.view.devicePixelRatio = 1.0;
  addTearDown(t.view.resetPhysicalSize);
  addTearDown(t.view.resetDevicePixelRatio);
}

Map<String, dynamic> _item(String id, String title, {String group = 'daily', String state = 'due', String freq = 'daily', Map<String, dynamic>? extra}) => {
      'id': id, 'code': id, 'title': title, 'detail': 'Detail of $title', 'category': 'assets', 'category_label': 'Assets & equipment',
      'frequency': freq, 'schedule': freq == 'daily' ? 'Every day' : 'Jan, Jul, by the last day', 'group': group,
      'due_months': <int>[], 'lead_days': 0, 'statutory': group == 'compliance', 'is_enabled': true, 'is_standard': true,
      'applies_because': '2 lifts in your assets', 'due_on': '2026-10-11', 'state': state, 'log': null,
      ...?extra,
    };

Map<String, dynamic> _jurisdiction({bool loaded = true}) => {
      'state': loaded ? 'Maharashtra' : 'Karnataka', 'state_pack_loaded': loaded,
      'note': loaded ? 'Built-in legal items are a starting list, not legal advice.' : 'Rules specific to Karnataka are not built in — add them as your own items.',
      'packs': loaded
          ? [{'key': 'central', 'label': 'All-India (central) rules'}, {'key': 'maharashtra', 'label': 'Maharashtra'}]
          : [{'key': 'central', 'label': 'All-India (central) rules'}],
    };

TodayChecklist _today({bool loaded = true, List<Map<String, dynamic>> live = const []}) => TodayChecklist.fromJson({
      'as_of': '2026-10-11',
      'items': [
        _item('lift_check', 'Lifts: running, alarm, intercom'),
        _item('walk_round', 'Walk round the premises', state: 'done', extra: {
          'log': {'id': 'l1', 'for_date': '2026-10-11', 'status': 'done', 'done_on': '2026-10-11', 'done_by': 'Meera Manager'}
        }),
        _item('mh_fire_form_b', 'Fire Form B inspection report', group: 'compliance', freq: 'on_dates', state: 'soon',
            extra: {'days_left': 20, 'legal_basis': 'Maharashtra Fire Act, 2006', 'due_on': '2026-10-31'}),
      ],
      'live': live,
      'summary': {'total': 3, 'done': 1, 'overdue': 0, 'live_open': live.length, 'live_high': 0, 'compliance_unrecorded': 2, 'compliance_unconfirmed': 3},
      'signoff': null,
      'jurisdiction': _jurisdiction(loaded: loaded),
    });

Widget _app(TodayChecklist today, {ComplianceCalendar? compliance}) => ProviderScope(
      overrides: [
        currentUserProvider.overrideWithValue(_user()),
        todayChecklistProvider.overrideWith((ref, id) async => today),
        complianceProvider.overrideWith((ref, id) async =>
            compliance ?? ComplianceCalendar.fromJson({'items': [], 'jurisdiction': _jurisdiction(), 'summary': {}})),
      ],
      child: MaterialApp(theme: AppTheme.lightTheme, home: const ManagerChecklistScreen()),
    );

void main() {
  testWidgets("today shows progress, the routine for the society's assets, what the records flag and the legal dates", (t) async {
    _size(t, const Size(420, 2400));
    await t.pumpWidget(_app(_today(live: [
      {'key': 'assets_service_overdue', 'category': 'assets', 'link_key': 'assets', 'severity': 'high',
       'title': '2 asset(s) are overdue for service', 'count': 2, 'detail': 'Lift 1, Pump 2'},
    ])));
    await t.pumpAndSettle();
    expect(find.text("Manager's Checklist"), findsWidgets);
    expect(find.text('1 of 3 done'), findsOneWidget);
    expect(find.text('Lifts: running, alarm, intercom'), findsOneWidget);
    expect(find.text('2 lifts in your assets'), findsWidgets);
    expect(find.text('2 asset(s) are overdue for service'), findsOneWidget);
    expect(find.text('Lift 1, Pump 2'), findsOneWidget);
    expect(find.text('Statutory and compliance dates'), findsOneWidget);
    expect(find.text('Due in 20 days · 31 Oct 2026'), findsOneWidget);
    expect(find.textContaining('3 statutory date(s) have passed'), findsOneWidget);
    expect(find.textContaining('2 licence or certificate date(s) are not recorded yet'), findsOneWidget);
    expect(find.text('Close the day'), findsOneWidget);
    // A ticked item reads as done and says who did it.
    expect(find.textContaining('By Meera Manager'), findsOneWidget);
  });

  testWidgets('a society whose state has no built-in rules is told to add its own', (t) async {
    _size(t, const Size(420, 2400));
    await t.pumpWidget(_app(_today(loaded: false)));
    await t.pumpAndSettle();
    expect(find.textContaining('Rules loaded: All-India (central) rules'), findsOneWidget);
    expect(find.textContaining('Rules specific to Karnataka are not built in'), findsOneWidget);
  });

  testWidgets('opening an item shows its details and legal basis', (t) async {
    _size(t, const Size(420, 2400));
    await t.pumpWidget(_app(_today()));
    await t.pumpAndSettle();
    await t.tap(find.text('Fire Form B inspection report'));
    await t.pumpAndSettle();
    expect(find.textContaining('Detail of Fire Form B inspection report'), findsOneWidget);
    expect(find.textContaining('Basis: Maharashtra Fire Act, 2006'), findsOneWidget);
  });

  testWidgets('the compliance tab lists each date with its state and legal basis', (t) async {
    _size(t, const Size(420, 2400));
    final c = ComplianceCalendar.fromJson({
      'items': [
        _item('mh_agm', 'Hold the Annual General Meeting', group: 'compliance', freq: 'on_dates', state: 'overdue',
            extra: {'due_on': '2026-09-30', 'legal_basis': 'Maharashtra Co-operative Societies Act, 1960 — section 75'}),
        _item('mh_lift_licence', 'Lift licence: renew', group: 'compliance', freq: 'licence', state: 'unrecorded', extra: {'due_on': null}),
      ],
      'jurisdiction': _jurisdiction(),
      'summary': {'overdue': 1, 'unconfirmed': 0, 'soon': 0, 'unrecorded': 1, 'total': 2},
    });
    await t.pumpWidget(_app(_today(), compliance: c));
    await t.pumpAndSettle();
    await t.tap(find.text('Compliance'));
    await t.pumpAndSettle();
    expect(find.text('Hold the Annual General Meeting'), findsOneWidget);
    expect(find.text('Overdue · was due 30 Sep 2026'), findsOneWidget);
    expect(find.text('Not recorded yet'), findsOneWidget);
    expect(find.textContaining('section 75'), findsOneWidget);
  });
}
