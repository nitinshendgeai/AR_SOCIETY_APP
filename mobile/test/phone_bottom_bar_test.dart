import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ar_society_app/core/layout/phone_bottom_bar.dart';
import 'package:ar_society_app/core/navigation/app_menu.dart';
import 'package:ar_society_app/core/router/app_router.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/shared/widgets/dux_logo.dart';
import 'package:ar_society_app/features/auth/domain/entities/user_entity.dart';
import 'package:ar_society_app/features/visitor/presentation/providers/visitor_providers.dart';

UserEntity _user(String role, {String? societyId}) =>
    UserEntity(id: 'u', email: 'u@t.com', fullName: 'U', roles: [role], societyId: societyId);

const _everything = {
  'visitors', 'complaints', 'notices', 'maintenance_billing', 'my_bills', 'residents', 'amenities',
};

void main() {
  group('phoneTabsFor', () {
    test('a resident gets Home, Bills, Visitors, Notices', () {
      final tabs = phoneTabsFor(_user('Resident'), _everything);
      expect(tabs.map((t) => t.label), ['Home', 'Bills', 'Visitors', 'Notices']);
      expect(tabs.first.route, AppRoutes.residentHome);
    });

    test('the admin gets Operations, Finance and People hubs', () {
      final tabs = phoneTabsFor(_user('Society Admin', societyId: 's1'), _everything);
      expect(tabs.map((t) => t.label), ['Home', 'Operations', 'Finance', 'People']);
      expect(tabs.map((t) => t.route), [AppRoutes.adminHome, '/hub/operations', '/hub/finance', '/hub/people']);
    });

    test('a hub leads to the society-wide lists, not the "my" lists', () {
      final tabs = phoneTabsFor(_user('Society Admin', societyId: 's1'), _everything);
      final operations = tabs[1].alsoRoutes;
      expect(operations, contains(AppRoutes.visitorsSociety.replaceFirst(':societyId', 's1')));
      expect(operations, contains(AppRoutes.complaintsSociety.replaceFirst(':societyId', 's1')));
      expect(operations, isNot(contains(AppRoutes.visitorsMy)));
    });

    test('committee and managers get the hubs too; a resident, security and field staff keep their own tabs', () {
      for (final role in ['Committee Treasurer', 'Manager']) {
        expect(phoneTabsFor(_user(role, societyId: 's1'), _everything).map((t) => t.label),
            ['Home', 'Operations', 'Finance', 'People'], reason: role);
      }
      expect(phoneTabsFor(_user('Resident'), _everything).map((t) => t.label), ['Home', 'Bills', 'Visitors', 'Notices']);
      expect(phoneTabsFor(_user('Security Staff', societyId: 's1'), _everything).map((t) => t.label),
          ['Home', 'Visitors', 'Notices', 'Complaints']);
    });

    test('only hubs holding a screen the person may open are offered', () {
      final tabs = phoneTabsFor(_user('Society Admin', societyId: 's1'), {'visitors', 'notices'});
      expect(tabs.map((t) => t.label), ['Home', 'Operations']);
      final money = phoneTabsFor(_user('Committee Treasurer', societyId: 's1'), {'maintenance_billing'});
      expect(money.map((t) => t.label), ['Home', 'Finance']);
    });

    test('with nothing granted there is still Home', () {
      expect(phoneTabsFor(_user('Resident'), const {}).map((t) => t.label), ['Home']);
    });
  });

  group('searchMenu', () {
    final admin = _user('Society Admin', societyId: 's1');
    final menu = visibleMenuCategories(_everything, user: admin);

    test('an empty query matches nothing, so the grouped menu shows', () {
      expect(searchMenu(menu, ''), isEmpty);
      expect(searchMenu(menu, '   '), isEmpty);
    });

    test('matches a screen by name, ignoring case', () {
      final hits = searchMenu(menu, 'AMEN').map((h) => h.$2.label);
      expect(hits, contains('Amenities'));
      expect(hits, isNot(contains('Residents')));
    });

    test('matches every screen of a group by the group name', () {
      final hits = searchMenu(menu, 'people').map((h) => h.$2.label);
      expect(hits, contains('Residents'));
    });

    test('also matches the translated name', () {
      String mr(String s) => s == 'Amenities' ? 'सुविधा' : s;
      expect(searchMenu(menu, 'सुविधा', translate: mr).map((h) => h.$2.label), contains('Amenities'));
      expect(searchMenu(menu, 'सुविधा'), isEmpty);
    });

    test('never offers a screen the person was not granted', () {
      final narrow = visibleMenuCategories({'notices'}, user: admin);
      expect(searchMenu(narrow, 'residents'), isEmpty);
      expect(searchMenu(narrow, 'notices').map((h) => h.$2.label), ['Notices']);
    });
  });

  group('which pages show the bar', () {
    final admin = _user('Society Admin', societyId: 's1');
    final tabs = phoneTabsFor(admin, _everything);
    final menu = visibleMenuCategories(_everything, user: admin);

    test('tabs and menu pages show it; records and forms do not', () {
      expect(showsPhoneBar(tabs, menu, AppRoutes.adminHome), isTrue);
      expect(showsPhoneBar(tabs, menu, AppRoutes.residentsList), isTrue);
      expect(showsPhoneBar(tabs, menu, '/residents/detail'), isFalse);
      expect(showsPhoneBar(tabs, menu, '/complaints/create'), isFalse);
    });

    test('a page belongs to the tab whose route, or whose hub screens, it sits under', () {
      final complaints = AppRoutes.complaintsSociety.replaceFirst(':societyId', 's1');
      expect(activePhoneTab(tabs, '/hub/operations'), 1);
      expect(activePhoneTab(tabs, complaints), 1);                            // a screen reached from the Operations hub
      expect(activePhoneTab(tabs, '$complaints/123'), 1);
      expect(activePhoneTab(tabs, AppRoutes.residentsList), 3);               // People
      expect(activePhoneTab(tabs, AppRoutes.maintenanceBilling), 2);          // Finance
      expect(activePhoneTab(tabs, AppRoutes.helpAssistant), isNull);          // not under any hub: More lights
    });
  });

  group('the bar', () {
    Widget wrap(UserEntity user, String location) {
      final tabs = phoneTabsFor(user, _everything);
      final menu = visibleMenuCategories(_everything, user: user);
      return ProviderScope(
        overrides: [pendingVisitorApprovalsProvider.overrideWith((ref) => Stream.value(const []))],
        child: MaterialApp(
          theme: AppTheme.lightTheme,
          home: Scaffold(
            bottomNavigationBar: PhoneBottomBar(location: location, user: user, tabs: tabs, menu: menu),
          ),
        ),
      );
    }

    testWidgets('shows the tabs and More; More opens the whole menu', (t) async {
      await t.pumpWidget(wrap(_user('Society Admin', societyId: 's1'), AppRoutes.adminHome));
      await t.pumpAndSettle();
      for (final label in ['Home', 'Operations', 'Finance', 'People', 'More']) {
        expect(find.text(label), findsWidgets);
      }
      await t.tap(find.text('More'));
      await t.pumpAndSettle();
      expect(find.text('People & Residents'), findsOneWidget);
      expect(find.text('Residents'), findsOneWidget);
    });

    testWidgets('More lists one group at a time; a group bubble switches it', (t) async {
      await t.pumpWidget(wrap(_user('Society Admin', societyId: 's1'), '/residents'));
      await t.pumpAndSettle();
      await t.tap(find.text('More'));
      await t.pumpAndSettle();
      expect(find.text('Residents'), findsOneWidget);
      expect(find.text('Amenities'), findsNothing);    // another group's screen is not listed yet
      await t.tap(find.text('Community & Services'));
      await t.pumpAndSettle();
      expect(find.text('Amenities'), findsOneWidget);
      expect(find.text('Residents'), findsNothing);
    });

    testWidgets('typing in More search lists matching screens across groups, clearing returns to groups', (t) async {
      await t.pumpWidget(wrap(_user('Society Admin', societyId: 's1'), '/residents'));
      await t.pumpAndSettle();
      await t.tap(find.text('More'));
      await t.pumpAndSettle();
      await t.enterText(find.byKey(const ValueKey('more-search')), 'amen');
      await t.pumpAndSettle();
      expect(find.text('Amenities'), findsOneWidget);
      expect(find.text('Residents'), findsNothing);
      await t.enterText(find.byKey(const ValueKey('more-search')), 'zzzz');
      await t.pumpAndSettle();
      expect(find.text('No screen matches'), findsOneWidget);
      await t.enterText(find.byKey(const ValueKey('more-search')), '');
      await t.pumpAndSettle();
      expect(find.text('Residents'), findsOneWidget);       // back to the group the person was on
    });

    testWidgets('More opens with who is signed in, then the menu, and ends with the account actions', (t) async {
      await t.pumpWidget(wrap(_user('Society Admin', societyId: 's1'), '/residents'));
      await t.pumpAndSettle();
      await t.tap(find.text('More'));
      await t.pumpAndSettle();
      expect(find.text('U'), findsOneWidget);                         // the signed-in person, at the top
      expect(find.byType(DuxLogo), findsOneWidget);
      // The account actions come last, under the menu.
      await t.dragUntilVisible(find.text('Sign out'), find.byType(ListView), const Offset(0, -300));
      expect(find.text('Signed-in devices'), findsOneWidget);
      expect(t.getTopLeft(find.text('Sign out')).dy, greaterThan(t.getTopLeft(find.text('Residents')).dy));
    });
  });
}
