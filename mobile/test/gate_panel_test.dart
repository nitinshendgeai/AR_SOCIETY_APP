import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:ar_society_app/core/l10n/app_locale.dart';
import 'package:ar_society_app/core/router/app_router.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/auth/domain/entities/user_entity.dart';
import 'package:ar_society_app/features/dashboard/gate_panel.dart';
import 'package:ar_society_app/features/dashboard/gate_summary.dart';
import 'package:ar_society_app/features/users/presentation/providers/user_providers.dart' show myFormCodesProvider;

UserEntity _guard({List<String>? services}) => UserEntity(
    id: 'g', email: 'g@t.com', fullName: 'Guard', roles: const ['Security Staff'], societyId: 's1', enabledServices: services);

Widget _app(
  Future<GateSummary> Function() load, {
  UserEntity? user,
  List<String> grants = const ['visitors', 'parcels'],
  List<String>? visited,
  Locale? locale,
}) {
  final router = GoRouter(routes: [
    GoRoute(
        path: '/',
        builder: (_, __) => Scaffold(body: SingleChildScrollView(child: GatePanel(user: user ?? _guard(), societyId: 's1')))),
    GoRoute(path: AppRoutes.visitorsCreate, builder: (_, __) => const Scaffold(body: Text('create page'))),
    GoRoute(
        path: AppRoutes.visitorsSociety,
        builder: (_, s) {
          visited?.add(s.uri.toString());
          return const Scaffold(body: Text('log page'));
        }),
    GoRoute(path: AppRoutes.parcels, builder: (_, __) => const Scaffold(body: Text('parcels page'))),
  ]);
  return ProviderScope(
    overrides: [
      gateSummaryProvider('s1').overrideWith((ref) => load()),
      myFormCodesProvider.overrideWith((ref) async => grants),
    ],
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
  test('log routes carry the tab or verify mode the existing log screen reads', () {
    expect(GatePanel.logRoute('s1'), '/visitors/society/s1');
    expect(GatePanel.logRoute('s1', query: 'tab=inside'), '/visitors/society/s1?tab=inside');
    expect(GatePanel.logRoute('s1', query: 'verify=1'), '/visitors/society/s1?verify=1');
  });

  testWidgets('shows who is inside, let in today and visitors today', (t) async {
    await t.pumpWidget(_app(() async => const GateSummary(visitorsToday: 15, checkedInToday: 12, inside: 3)));
    await t.pumpAndSettle();
    expect(find.text('3'), findsOneWidget);
    expect(find.text('12'), findsOneWidget);
    expect(find.text('15'), findsOneWidget);
    expect(find.text('Inside now'), findsOneWidget);
    expect(find.text('Let in today'), findsOneWidget);
  });

  testWidgets('a real zero is shown as 0', (t) async {
    await t.pumpWidget(_app(() async => const GateSummary(visitorsToday: 0, checkedInToday: 0, inside: 0)));
    await t.pumpAndSettle();
    expect(find.text('0'), findsNWidgets(3));
  });

  testWidgets('while loading it shows an ellipsis, never 0', (t) async {
    await t.pumpWidget(_app(() => Future<GateSummary>.delayed(const Duration(seconds: 5), () => const GateSummary())));
    await t.pump();
    expect(find.text('0'), findsNothing);
    expect(find.text('…'), findsNWidgets(3));
    await t.pump(const Duration(seconds: 6));
  });

  testWidgets('figures the server could not work out show -- and retry, never 0', (t) async {
    var calls = 0;
    await t.pumpWidget(_app(() async {
      calls++;
      return calls == 1 ? const GateSummary(failed: true) : const GateSummary(visitorsToday: 4, checkedInToday: 4, inside: 1);
    }));
    await t.pumpAndSettle();
    expect(find.text('--'), findsNWidgets(3));
    expect(find.text('0'), findsNothing);
    await t.tap(find.text('Tap to retry').first);
    await t.pumpAndSettle();
    expect(find.text('1'), findsOneWidget);
    expect(calls, 2);
  });

  testWidgets('a request error is also "--", not 0', (t) async {
    await t.pumpWidget(_app(() async => throw Exception('network')));
    await t.pumpAndSettle();
    expect(find.text('--'), findsNWidgets(3));
    expect(find.text('0'), findsNothing);
  });

  testWidgets('the buttons open the existing screens: log, check out, verify, parcels', (t) async {
    final visited = <String>[];
    await t.pumpWidget(_app(() async => const GateSummary(visitorsToday: 1, checkedInToday: 1, inside: 1), visited: visited));
    await t.pumpAndSettle();

    await t.tap(find.text('Log visitor'));
    await t.pumpAndSettle();
    expect(find.text('create page'), findsOneWidget);
    t.state<NavigatorState>(find.byType(Navigator)).pop();
    await t.pumpAndSettle();

    await t.tap(find.text('Check Out'));
    await t.pumpAndSettle();
    t.state<NavigatorState>(find.byType(Navigator)).pop();
    await t.pumpAndSettle();

    await t.tap(find.text('Verify code'));
    await t.pumpAndSettle();
    t.state<NavigatorState>(find.byType(Navigator)).pop();
    await t.pumpAndSettle();

    await t.tap(find.text('Parcels in'));
    await t.pumpAndSettle();
    expect(find.text('parcels page'), findsOneWidget);
    expect(visited, ['/visitors/society/s1?tab=inside', '/visitors/society/s1?verify=1']);
  });

  testWidgets('the button words use the app font (Inter), not the platform default', (t) async {
    await t.pumpWidget(_app(() async => const GateSummary(visitorsToday: 1, checkedInToday: 1, inside: 1)));
    await t.pumpAndSettle();
    for (final label in ['Log visitor', 'Check Out', 'Verify code', 'Parcels in']) {
      final rich = t.widget<RichText>(find.byWidgetPredicate((w) => w is RichText && w.text.toPlainText() == label));
      expect(rich.text.style?.fontFamily, 'Inter', reason: label);
    }
  });

  testWidgets('every button is at least 48dp tall', (t) async {
    await t.pumpWidget(_app(() async => const GateSummary(visitorsToday: 1, checkedInToday: 1, inside: 1)));
    await t.pumpAndSettle();
    for (final label in ['Log visitor', 'Check Out', 'Verify code', 'Parcels in']) {
      final button = find.ancestor(of: find.text(label), matching: find.byType(FilledButton));
      expect(t.getSize(button).height, greaterThanOrEqualTo(48), reason: label);
    }
  });

  testWidgets('parcels is offered only with the grant', (t) async {
    await t.pumpWidget(_app(() async => const GateSummary(), grants: const ['visitors']));
    await t.pumpAndSettle();
    expect(find.text('Parcels in'), findsNothing);
    expect(find.text('Log visitor'), findsOneWidget);
  });

  testWidgets('parcels is not offered when the society switched the service off', (t) async {
    await t.pumpWidget(_app(() async => const GateSummary(), user: _guard(services: const ['visitors', 'staff'])));
    await t.pumpAndSettle();
    expect(find.text('Parcels in'), findsNothing);
  });

  testWidgets('with the Visitors service off the panel is absent', (t) async {
    await t.pumpWidget(_app(() async => const GateSummary(), user: _guard(services: const ['staff'])));
    await t.pumpAndSettle();
    expect(find.text('Log visitor'), findsNothing);
    expect(find.text('Inside now'), findsNothing);
  });

  testWidgets('the words follow the chosen language (Marathi)', (t) async {
    await t.pumpWidget(_app(() async => const GateSummary(visitorsToday: 1, checkedInToday: 1, inside: 1), locale: const Locale('mr')));
    await t.pumpAndSettle();
    expect(find.text('पाहुणा नोंदवा'), findsOneWidget);
    expect(find.text('सध्या आत आहे'), findsOneWidget);
  });
}
