import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:ar_society_app/core/l10n/app_locale.dart';
import 'package:ar_society_app/core/router/app_router.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/core/theme/design_tokens.dart';
import 'package:ar_society_app/features/dashboard/resident_dues_card.dart';
import 'package:ar_society_app/features/maintenance_billing/data/maintenance_billing_api.dart' show MyBillsSummary;
import 'package:ar_society_app/features/maintenance_billing/presentation/providers/maintenance_billing_providers.dart'
    show myBillsProvider;

MyBillsSummary _summary(String total, {int open = 0, int overdue = 0}) =>
    MyBillsSummary(totalOutstanding: total, openCount: open, overdueCount: overdue, bills: const []);

Widget _app(Future<MyBillsSummary> Function() load, {List<String>? visited, Locale? locale}) {
  final router = GoRouter(routes: [
    GoRoute(path: '/', builder: (_, __) => const Scaffold(body: SingleChildScrollView(child: ResidentDuesCard()))),
    GoRoute(
      path: AppRoutes.myBills,
      builder: (_, __) {
        visited?.add(AppRoutes.myBills);
        return const Scaffold(body: Text('bills page'));
      },
    ),
  ]);
  return ProviderScope(
    overrides: [myBillsProvider.overrideWith((ref) => load())],
    child: MaterialApp.router(
      theme: AppTheme.lightTheme,
      routerConfig: router,
      locale: locale,
      supportedLocales: kSupportedLocales,
      localizationsDelegates: GlobalMaterialLocalizations.delegates,
    ),
  );
}

void main() {
  group('statusFor', () {
    test('overdue wins over merely due', () {
      final (tone, _, label) = ResidentDuesCard.statusFor(_summary('4500.00', open: 2, overdue: 1));
      expect(tone, AppTone.danger);
      expect(label, '1 overdue');
    });
    test('money owed but nothing overdue is "Payment due"', () {
      final (tone, _, label) = ResidentDuesCard.statusFor(_summary('4500.00', open: 1));
      expect(tone, AppTone.warning);
      expect(label, 'Payment due');
    });
    test('nothing owed is "All paid"', () {
      final (tone, _, label) = ResidentDuesCard.statusFor(_summary('0.00'));
      expect(tone, AppTone.success);
      expect(label, 'All paid');
    });
  });

  testWidgets('shows the amount in rupees, the bill count and an overdue chip', (t) async {
    await t.pumpWidget(_app(() async => _summary('12345.50', open: 3, overdue: 2)));
    await t.pumpAndSettle();
    expect(find.text('Outstanding maintenance'), findsOneWidget);
    expect(find.text('₹12,345.50'), findsOneWidget);
    expect(find.text('Across 3 open bills'), findsOneWidget);
    expect(find.text('2 overdue'), findsOneWidget);
    expect(find.text('View and pay'), findsOneWidget);
  });

  testWidgets('the fixed words follow the chosen language (Marathi)', (t) async {
    await t.pumpWidget(_app(() async => _summary('800.00', open: 1), locale: const Locale('mr')));
    await t.pumpAndSettle();
    expect(find.text('थकीत देखभाल शुल्क'), findsOneWidget);
    expect(find.text('पहा आणि भरा'), findsOneWidget);
    expect(find.text('भरणा बाकी'), findsOneWidget);
    expect(find.text('₹800.00'), findsOneWidget);   // the figure is the same in every language
  });

  testWidgets('one open bill is singular', (t) async {
    await t.pumpWidget(_app(() async => _summary('800.00', open: 1)));
    await t.pumpAndSettle();
    expect(find.text('Across 1 open bill'), findsOneWidget);
    expect(find.text('Payment due'), findsOneWidget);
  });

  testWidgets('with nothing owed it says so and offers the receipts, not payment', (t) async {
    await t.pumpWidget(_app(() async => _summary('0.00')));
    await t.pumpAndSettle();
    expect(find.text('All paid'), findsOneWidget);
    expect(find.text('You have no open bills'), findsOneWidget);
    expect(find.text('View bills and receipts'), findsOneWidget);
    expect(find.text('View and pay'), findsNothing);
  });

  testWidgets('the button opens My Bills and is at least 48dp tall', (t) async {
    final visited = <String>[];
    await t.pumpWidget(_app(() async => _summary('800.00', open: 1), visited: visited));
    await t.pumpAndSettle();
    expect(t.getSize(find.byType(FilledButton)).height, greaterThanOrEqualTo(AppSpacing.minTouch));
    await t.tap(find.text('View and pay'));
    await t.pumpAndSettle();
    expect(visited, [AppRoutes.myBills]);
    expect(find.text('bills page'), findsOneWidget);
  });

  testWidgets('while loading it shows a placeholder, not a wrong amount', (t) async {
    final never = Completer<MyBillsSummary>();
    await t.pumpWidget(_app(() => never.future));
    await t.pump();
    expect(find.text('Outstanding maintenance'), findsNothing);
    expect(find.textContaining('₹'), findsNothing);
    expect(find.bySemanticsLabel('Loading what is outstanding'), findsOneWidget);
  });

  testWidgets('a failure says so and Retry loads it again', (t) async {
    var calls = 0;
    await t.pumpWidget(_app(() async {
      calls++;
      if (calls == 1) throw Exception('network');
      return _summary('500.00', open: 1);
    }));
    await t.pumpAndSettle();
    expect(find.text('Could not check what is outstanding'), findsOneWidget);
    expect(find.textContaining('₹'), findsNothing);
    await t.tap(find.text('Retry'));
    await t.pumpAndSettle();
    expect(find.text('₹500.00'), findsOneWidget);
    expect(calls, 2);
  });
}
