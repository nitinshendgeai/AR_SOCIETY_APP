import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:ar_society_app/core/navigation/app_menu.dart';
import 'package:ar_society_app/core/navigation/menu_hub_screen.dart';
import 'package:ar_society_app/core/router/app_router.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/auth/domain/entities/user_entity.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/features/users/presentation/providers/user_providers.dart' show myFormCodesProvider;

const _admin = UserEntity(id: 'a', email: 'a@t.com', fullName: 'Admin', roles: ['Society Admin'], societyId: 's1');

Widget _app(String slug, Future<List<String>> Function() grants, {List<String>? visited}) {
  final router = GoRouter(routes: [
    GoRoute(path: '/', builder: (_, __) => MenuHubScreen(slug: slug)),
    GoRoute(
      path: AppRoutes.residentsList,
      builder: (_, __) {
        visited?.add(AppRoutes.residentsList);
        return const Scaffold(body: Text('residents page'));
      },
    ),
  ]);
  return ProviderScope(
    overrides: [
      currentUserProvider.overrideWithValue(_admin),
      myFormCodesProvider.overrideWith((ref) => grants()),
    ],
    child: MaterialApp.router(theme: AppTheme.lightTheme, routerConfig: router),
  );
}

void main() {
  group('MenuHub', () {
    test('finds a hub by its address and rejects an unknown one', () {
      expect(MenuHub.fromSlug('finance'), MenuHub.finance);
      expect(MenuHub.fromSlug('people')?.route, '/hub/people');
      expect(MenuHub.fromSlug('nope'), isNull);
    });

    test('lists only its own groups, in its own order, with only the screens granted', () {
      final visible = visibleMenuCategories({'visitors', 'residents', 'maintenance_billing', 'vendors'}, user: _admin);
      expect(MenuHub.operations.categoriesIn(visible).map((c) => c.label), ['Community & Services', 'Operations']);
      expect(MenuHub.finance.categoriesIn(visible).map((c) => c.label), ['Finance & Maintenance']);
      expect(MenuHub.people.categoriesIn(visible).map((c) => c.label), ['People & Residents']);
    });

    test('a group with nothing granted is not listed', () {
      final visible = visibleMenuCategories({'visitors'}, user: _admin);
      expect(MenuHub.finance.categoriesIn(visible), isEmpty);
      expect(MenuHub.people.categoriesIn(visible), isEmpty);
    });

    test('every screen on a manager hub is in the menu, and no screen is on two hubs', () {
      final seen = <String>{};
      final inMenu = appMenuCategories.map((c) => c.label).toSet();
      for (final hub in MenuHub.values) {
        for (final g in hub.groups) {
          expect(inMenu, contains(g), reason: '${hub.label}: $g');
          expect(seen.add(g), isTrue, reason: '$g appears on two hubs');
        }
      }
    });
  });

  group('MenuHubScreen', () {
    testWidgets('shows the granted screens under their group and nothing else', (t) async {
      await t.pumpWidget(_app('people', () async => ['residents', 'staff', 'visitors']));
      await t.pumpAndSettle();
      expect(find.text('People & Residents'), findsOneWidget);
      expect(find.text('Residents'), findsOneWidget);
      expect(find.text('Staff'), findsOneWidget);
      expect(find.text('Tenants'), findsNothing);              // not granted
      expect(find.text('Visitors'), findsNothing);             // belongs on Operations
    });

    testWidgets('Operations gathers several groups', (t) async {
      await t.pumpWidget(_app('operations', () async => ['visitors', 'complaints', 'vendors', 'assets']));
      await t.pumpAndSettle();
      for (final label in ['Community & Services', 'Operations', 'Property & Parking', 'Visitors', 'Complaints', 'Assets']) {
        expect(find.text(label), findsWidgets, reason: label);
      }
      expect(find.text('Residents'), findsNothing);
    });

    testWidgets('a tile opens its screen', (t) async {
      final visited = <String>[];
      await t.pumpWidget(_app('people', () async => ['residents'], visited: visited));
      await t.pumpAndSettle();
      await t.tap(find.text('Residents'));
      await t.pumpAndSettle();
      expect(visited, [AppRoutes.residentsList]);
      expect(find.text('residents page'), findsOneWidget);
    });

    testWidgets('typing narrows the tiles and a miss says so', (t) async {
      await t.pumpWidget(_app('people', () async => ['residents', 'tenants', 'staff']));
      await t.pumpAndSettle();
      await t.enterText(find.byKey(const Key('hub-search')), 'ten');
      await t.pumpAndSettle();
      expect(find.text('Tenants'), findsOneWidget);
      expect(find.text('Residents'), findsNothing);
      await t.enterText(find.byKey(const Key('hub-search')), 'zzzz');
      await t.pumpAndSettle();
      expect(find.text('No screen matches'), findsOneWidget);
    });

    testWidgets('with nothing granted it says so instead of showing an empty page', (t) async {
      await t.pumpWidget(_app('finance', () async => ['visitors']));
      await t.pumpAndSettle();
      expect(find.text('Nothing here for your role'), findsOneWidget);
    });

    testWidgets('an unknown hub address shows nothing, not an error', (t) async {
      await t.pumpWidget(_app('bogus', () async => ['residents']));
      await t.pumpAndSettle();
      expect(find.text('Nothing here'), findsOneWidget);
      expect(find.text('Residents'), findsNothing);
    });

    testWidgets('if the grants cannot be loaded it offers Try again, then shows the screens', (t) async {
      var calls = 0;
      await t.pumpWidget(_app('people', () async {
        calls++;
        if (calls == 1) throw Exception('network');
        return ['residents'];
      }));
      await t.pumpAndSettle();
      expect(find.text('Residents'), findsNothing);
      await t.tap(find.text('Try again'));
      await t.pumpAndSettle();
      expect(find.text('Residents'), findsOneWidget);
    });
  });
}
