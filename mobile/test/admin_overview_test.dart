import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/dashboard/admin_overview.dart';

Map<String, dynamic> _json({bool collection = true, List<Map<String, dynamic>> attention = const []}) => {
      'as_of': '2026-10-09',
      'collection': collection
          ? {
              'cycle_name': 'October 2026',
              'due_date': '2026-10-20',
              'billed': '58500.00',
              'collected': '13025.00',
              'outstanding': '45475.00',
              'percent': 22,
              'bills': 5,
              'paid_bills': 1,
              'overdue_bills': 0,
              'trend': [
                {'name': 'September 2026', 'billed': '58500.00', 'collected': '39075.00'},
                {'name': 'October 2026', 'billed': '58500.00', 'collected': '13025.00'},
              ],
            }
          : null,
      'money': {
        'cash': '1000', 'bank': '5000', 'members_dues': '200', 'creditors': '0',
        'fy': '2026-27', 'fy_income': '9000', 'fy_expense': '4000',
      },
      'occupancy': {'flats': 5, 'occupied': 3, 'vacant': 2, 'residents': 4},
      'today': {'visitors_today': 1, 'visitors_inside': 1},
      'attention': attention,
    };

Widget _wrap(Future<DashboardOverview> Function() load) => ProviderScope(
      overrides: [dashboardOverviewProvider('s1').overrideWith((ref) => load())],
      child: MaterialApp(
        theme: AppTheme.lightTheme,
        // The test font is wider and taller than the app's; scale it down so
        // fixed-height tiles are judged on layout, not on the font.
        builder: (context, child) => MediaQuery(
          data: MediaQuery.of(context).copyWith(textScaler: const TextScaler.linear(0.7)),
          child: child!,
        ),
        home: const Scaffold(body: SingleChildScrollView(child: AdminOverview(societyId: 's1', activeStaff: '2'))),
      ),
    );

void main() {
  void phone(WidgetTester t) {
    t.view.physicalSize = const Size(420, 2400);
    t.view.devicePixelRatio = 1.0;
    addTearDown(t.view.resetPhysicalSize);
    addTearDown(t.view.resetDevicePixelRatio);
  }

  testWidgets('shows collection, the things waiting on the office, money and today', (t) async {
    phone(t);
    await t.pumpWidget(_wrap(() async => DashboardOverview.fromJson(_json(attention: [
          {'key': 'overdue_bills', 'count': 2, 'severity': 'high', 'amount': '51650'},
          {'key': 'complaints_open', 'count': 1, 'severity': 'info'},
          {'key': 'something_new_from_a_newer_server', 'count': 9, 'severity': 'high'},
        ]))));
    await t.pumpAndSettle();

    expect(find.text('Maintenance collection'), findsOneWidget);
    expect(find.text('₹13,025'), findsOneWidget);
    expect(find.text('22%'), findsOneWidget);
    expect(find.text('Oct 26'), findsOneWidget);                      // short cycle label
    expect(find.text('2 flats have overdue maintenance (₹51,650)'), findsOneWidget);
    expect(find.text('1 open complaint'), findsOneWidget);
    expect(find.textContaining('newer_server'), findsNothing);        // unknown keys are skipped, not shown
    expect(find.text('Needs attention'), findsOneWidget);
    expect(find.text('3 of 5 flats occupied'), findsOneWidget);
    expect(find.text('Active staff'), findsOneWidget);
  });

  testWidgets('no billing cycle and nothing waiting', (t) async {
    phone(t);
    await t.pumpWidget(_wrap(() async => DashboardOverview.fromJson(_json(collection: false))));
    await t.pumpAndSettle();

    expect(find.text('No billing cycle yet.'), findsOneWidget);
    expect(find.textContaining('All clear'), findsOneWidget);
  });

  testWidgets('a failed load says so and offers to try again', (t) async {
    phone(t);
    await t.pumpWidget(_wrap(() async => throw Exception('offline')));
    await t.pumpAndSettle();

    expect(find.text('The overview could not be loaded.'), findsOneWidget);
    expect(find.text('Try again'), findsOneWidget);
  });
}
