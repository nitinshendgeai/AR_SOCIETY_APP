import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/accounts/data/outstanding_api.dart';
import 'package:ar_society_app/features/accounts/presentation/screens/outstanding_screen.dart';
import 'package:ar_society_app/features/auth/domain/entities/user_entity.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';

Map<String, dynamic> _party(String key, String name, String? sub, Map<String, String> buckets, List<Map<String, dynamic>> bills,
        {int days = 0}) =>
    {
      'key': key,
      'name': name,
      'sub': sub,
      'total': buckets.values.fold<double>(0, (a, b) => a + double.parse(b)).toStringAsFixed(2),
      'buckets': {'not_due': '0.00', 'd1_30': '0.00', 'd31_60': '0.00', 'd61_90': '0.00', 'over_90': '0.00', ...buckets},
      'oldest_due_date': '2026-04-10',
      'days_overdue': days,
      'bill_count': bills.length,
      'bills': bills,
    };

Map<String, dynamic> _bill(String ref, String bucket, String amount, int days, {bool noDue = false}) => {
      'ref': ref,
      'label': null,
      'date': '2026-04-01',
      'due_date': '2026-04-10',
      'outstanding': amount,
      'days_overdue': days,
      'bucket': bucket,
      if (noDue) 'no_due_date': true,
    };

Map<String, dynamic> _report(String kind, List<Map<String, dynamic>> parties) => {
      'kind': kind,
      'as_of': '2026-10-24',
      'bucket_labels': [
        {'key': 'not_due', 'label': 'Not yet due'},
        {'key': 'd1_30', 'label': '1–30 days'},
        {'key': 'd31_60', 'label': '31–60 days'},
        {'key': 'd61_90', 'label': '61–90 days'},
        {'key': 'over_90', 'label': 'Over 90 days'},
      ],
      'totals': {
        'parties': parties.length,
        'bills': parties.fold<int>(0, (a, p) => a + (p['bill_count'] as int)),
        'outstanding': '7500.00',
        'overdue': '5000.00',
        'buckets': {'not_due': '2500.00', 'd1_30': '0.00', 'd31_60': '0.00', 'd61_90': '0.00', 'over_90': '5000.00'},
      },
      'parties': parties,
    };

class _FakeOutstanding extends OutstandingApi {
  final List<String> asked = [];
  _FakeOutstanding() : super(dio: Dio());

  @override
  Future<OutstandingReport> report(String societyId, String kind) async {
    asked.add(kind);
    if (kind == 'payable') {
      return OutstandingReport.fromJson(_report('payable', [
        _party('v1', 'Shield Security', null, {'over_90': '5000.00'}, [_bill('SS/1', 'over_90', '5000.00', 197)], days: 197),
      ]));
    }
    return OutstandingReport.fromJson(_report('receivable', [
      _party('f1', 'A-101', 'Asha Rao', {'over_90': '5000.00', 'not_due': '2500.00'},
          [_bill('INV-1', 'over_90', '5000.00', 197), _bill('INV-2', 'not_due', '2500.00', 0)],
          days: 197),
      _party('f2', 'A-102', 'Bhaskar Iyer', {'not_due': '0.01'}, [_bill('INV-3', 'not_due', '0.01', 0)]),
    ]));
  }
}

Widget _screen(_FakeOutstanding api, {String kind = 'receivable'}) => ProviderScope(
      overrides: [
        currentUserProvider.overrideWithValue(
            const UserEntity(id: 'u', email: 'u@t.com', fullName: 'U', roles: ['Society Admin'], societyId: 's1')),
        outstandingApiProvider.overrideWithValue(api),
      ],
      child: MaterialApp(theme: AppTheme.lightTheme, home: OutstandingScreen(initialKind: kind)),
    );

void main() {
  test('the report is read from the api json', () {
    final r = OutstandingReport.fromJson(_report('receivable', [
      _party('f1', 'A-101', 'Asha Rao', {'over_90': '5000.00'}, [_bill('INV-1', 'over_90', '5000.00', 197)], days: 197),
    ]));
    expect(r.rows.single.name, 'A-101');
    expect(r.rows.single.buckets['over_90'], 5000.0);
    expect(r.rows.single.bills.single.daysOverdue, 197);
    expect(r.bucketLabels.last, ('over_90', 'Over 90 days'));
    expect(r.overdue, 5000.0);
  });

  testWidgets('lists each flat with its total, and a band chip narrows the list to flats with dues in it', (tester) async {
    await tester.binding.setSurfaceSize(const Size(900, 1400));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    final api = _FakeOutstanding();
    await tester.pumpWidget(_screen(api));
    await tester.pumpAndSettle();

    expect(find.text('Outstanding Receivable'), findsWidgets);
    expect(find.text('A-101'), findsOneWidget);
    expect(find.text('A-102'), findsOneWidget);
    expect(find.textContaining('Asha Rao'), findsOneWidget);
    expect(find.textContaining('197 days overdue'), findsOneWidget);

    await tester.tap(find.byKey(const Key('band-over_90')));
    await tester.pumpAndSettle();
    expect(find.text('A-101'), findsOneWidget);
    expect(find.text('A-102'), findsNothing);

    await tester.tap(find.byKey(const Key('band-all')));
    await tester.pumpAndSettle();
    expect(find.text('A-102'), findsOneWidget);
  });

  testWidgets('opening a party shows the bills behind it, and search finds a member by name', (tester) async {
    await tester.binding.setSurfaceSize(const Size(900, 1400));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    await tester.pumpWidget(_screen(_FakeOutstanding()));
    await tester.pumpAndSettle();

    expect(find.text('INV-1'), findsNothing);
    await tester.tap(find.text('A-101'));
    await tester.pumpAndSettle();
    expect(find.text('INV-1'), findsOneWidget);
    expect(find.text('INV-2'), findsOneWidget);

    await tester.enterText(find.byType(TextField), 'bhaskar');
    await tester.pumpAndSettle();
    expect(find.text('A-101'), findsNothing);
    expect(find.text('A-102'), findsOneWidget);
  });

  testWidgets('the Payable chip switches to the vendors', (tester) async {
    await tester.binding.setSurfaceSize(const Size(900, 1400));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    final api = _FakeOutstanding();
    await tester.pumpWidget(_screen(api));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('outstanding-payable')));
    await tester.pumpAndSettle();
    expect(api.asked, containsAllInOrder(['receivable', 'payable']));
    expect(find.text('Outstanding Payable'), findsWidgets);
    expect(find.text('Shield Security'), findsOneWidget);
    expect(find.text('A-101'), findsNothing);
  });

  testWidgets('opens on the payable side when asked to', (tester) async {
    await tester.binding.setSurfaceSize(const Size(900, 1400));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    await tester.pumpWidget(_screen(_FakeOutstanding(), kind: 'payable'));
    await tester.pumpAndSettle();
    expect(find.text('Shield Security'), findsOneWidget);
  });
}
