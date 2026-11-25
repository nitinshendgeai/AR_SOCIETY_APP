import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:ar_society_app/features/auth/domain/entities/user_entity.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/features/maintenance_billing/data/defaulters_api.dart';
import 'package:ar_society_app/features/maintenance_billing/presentation/screens/defaulters_screen.dart';

/// A server with two wings that each have one defaulter; it keeps the wings of the whole society in the summary and
/// limits the flats (and the totals) to the wing asked for.
class _FakeDues extends DefaultersApi {
  final List<String?> asked = [];
  _FakeDues() : super(dio: Dio());

  static const _flats = {'Tower A': ('A / 101', 'Asha Rao', 5000.0), 'Tower B': ('B / 201', 'Bela Shah', 7000.0)};

  @override
  Future<DefaultersReport> report(String societyId,
      {int minMonths = 3, bool includeAll = false, String? wing}) async {
    asked.add(wing);
    final shown = {for (final e in _flats.entries) if (wing == null || wing == e.key) e.key: e.value};
    final total = shown.values.fold(0.0, (a, b) => a + b.$3);
    return DefaultersReport.fromJson({
      'summary': {
        'as_of': '2030-06-15', 'min_months': minMonths, 'include_all': includeAll, 'wing': wing,
        'wings': ['Tower A', 'Tower B'], 'flats_with_dues': shown.length,
        'total_outstanding': total.toStringAsFixed(2), 'defaulters': shown.length,
        'defaulters_outstanding': total.toStringAsFixed(2), 'in_default': total.toStringAsFixed(2),
        'buckets': [
          {'key': 'not_due', 'label': 'Not yet due', 'amount': '0.00'},
          {'key': 'm6_12', 'label': '6–12 months', 'amount': total.toStringAsFixed(2)},
        ],
      },
      'flats': [
        for (final e in shown.entries)
          {
            'flat_id': e.value.$1, 'flat_label': e.value.$1, 'wing': e.key, 'member_name': e.value.$2,
            'total': e.value.$3.toStringAsFixed(2), 'in_default': e.value.$3.toStringAsFixed(2), 'is_defaulter': true,
            'buckets': {'m6_12': e.value.$3.toStringAsFixed(2)}, 'oldest_due_date': '2029-10-01',
            'days_overdue': 200, 'unpaid_bills': 2, 'on_account': '0.00', 'bills': [],
          },
      ],
    });
  }
}

void main() {
  testWidgets('the defaulters can be limited to one wing, and back to all', (tester) async {
    tester.view.physicalSize = const Size(1400, 2400);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.reset);
    final api = _FakeDues();
    await tester.pumpWidget(ProviderScope(
      overrides: [
        currentUserProvider.overrideWithValue(
            const UserEntity(id: 'u', email: 'u@t.com', fullName: 'U', roles: ['Society Admin'], societyId: 's1')),
        defaultersApiProvider.overrideWithValue(api),
      ],
      child: MaterialApp.router(
        routerConfig: GoRouter(routes: [GoRoute(path: '/', builder: (_, __) => const DefaultersScreen())]),
      ),
    ));
    await tester.pumpAndSettle();
    expect(find.text('Asha Rao'), findsOneWidget);
    expect(find.text('Bela Shah'), findsOneWidget);
    expect(api.asked, [null]);

    await tester.tap(find.byKey(const ValueKey('dues-wing')));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Tower B').last);
    await tester.pumpAndSettle();
    expect(api.asked.last, 'Tower B');
    expect(find.text('Bela Shah'), findsOneWidget);
    expect(find.text('Asha Rao'), findsNothing);

    await tester.tap(find.byKey(const ValueKey('dues-wing')));          // the picker still lists every wing
    await tester.pumpAndSettle();
    await tester.tap(find.text('All wings').last);
    await tester.pumpAndSettle();
    expect(api.asked.last, isNull);
    expect(find.text('Asha Rao'), findsOneWidget);
  });
}
