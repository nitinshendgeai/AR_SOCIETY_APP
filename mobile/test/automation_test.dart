import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/auth/domain/entities/user_entity.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/features/automation/data/automation_api.dart';
import 'package:ar_society_app/features/automation/presentation/screens/automation_screen.dart';

Map<String, dynamic> _json({bool dues = false}) => {
      'settings': {'reminder_every_days': 7, 'reminder_min_months': 1},
      'jobs': [
        {
          'key': 'dues_reminders', 'title': 'Maintenance dues reminders', 'description': 'Reminds members.',
          'schedule': 'daily', 'enabled': dues, 'last_run': null,
        },
        {
          'key': 'agreement_alerts', 'title': 'Tenant agreement alerts', 'description': 'Tells the office.',
          'schedule': 'daily', 'enabled': true,
          'last_run': {'status': 'ok', 'summary': '2 agreement alert(s) sent', 'manual': false, 'ran_at': '2026-10-09T04:00:00Z'},
        },
        {
          'key': 'asset_alerts', 'title': 'Asset digest', 'description': 'Weekly.',
          'schedule': 'weekly', 'enabled': true,
          'last_run': {'status': 'error', 'summary': 'ZeroDivisionError', 'manual': true, 'ran_at': '2026-10-09T04:00:00Z'},
        },
      ],
    };

Widget _wrap(Map<String, dynamic> json) => ProviderScope(
      overrides: [
        currentUserProvider.overrideWithValue(
            UserEntity(id: 'u', email: 'a@t.com', fullName: 'A', roles: const ['Society Admin'], societyId: 's1')),
        automationProvider('s1').overrideWith((ref) async => AutomationOverview.fromJson(json)),
      ],
      child: MaterialApp(theme: AppTheme.lightTheme, home: const AutomationScreen()),
    );

void main() {
  void phone(WidgetTester t) {
    t.view.physicalSize = const Size(420, 2400);
    t.view.devicePixelRatio = 1.0;
    addTearDown(t.view.resetPhysicalSize);
    addTearDown(t.view.resetDevicePixelRatio);
  }

  testWidgets('lists each task with its schedule and what it did last', (t) async {
    phone(t);
    await t.pumpWidget(_wrap(_json()));
    await t.pumpAndSettle();

    expect(find.text('Maintenance dues reminders'), findsOneWidget);
    expect(find.text('Has not run yet'), findsOneWidget);
    expect(find.textContaining('2 agreement alert(s) sent'), findsOneWidget);
    expect(find.textContaining('Failed'), findsOneWidget);          // an errored run is called out
    expect(find.text('Weekly'), findsOneWidget);
    expect(find.text('Run now'), findsNWidgets(3));
  });

  testWidgets('the dues reminder has no interval settings while it is off', (t) async {
    phone(t);
    await t.pumpWidget(_wrap(_json(dues: false)));
    await t.pumpAndSettle();
    expect(find.text('Remind a flat again after'), findsNothing);
  });

  testWidgets('the dues reminder shows its interval settings once switched on', (t) async {
    phone(t);
    await t.pumpWidget(_wrap(_json(dues: true)));
    await t.pumpAndSettle();
    expect(find.text('Remind a flat again after'), findsOneWidget);
    expect(find.text('7 days'), findsOneWidget);
    expect(find.text('1 month'), findsOneWidget);
  });
}
