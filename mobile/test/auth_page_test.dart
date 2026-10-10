import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/shared/widgets/auth_page.dart';

Widget _page({VoidCallback? onBack, bool scrollable = true, Widget? footer}) => MaterialApp(
      theme: AppTheme.lightTheme,
      home: AuthPage(
        title: 'Welcome back',
        subtitle: 'Sign in to the app',
        onBack: onBack,
        scrollable: scrollable,
        footer: footer,
        child: Column(mainAxisSize: MainAxisSize.min, children: const [TextField(), Text('the form')]),
      ),
    );

void main() {
  testWidgets('a wide screen puts the brand panel at the left and the form at the right', (tester) async {
    tester.view.physicalSize = const Size(1440, 900);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.reset);
    await tester.pumpWidget(_page(footer: const Text('under the form')));
    await tester.pumpAndSettle();

    expect(find.text('Everything your society runs on, in one place.'), findsOneWidget);
    expect(find.text('Welcome back'), findsOneWidget);
    expect(find.text('Sign in to the app'), findsOneWidget);
    expect(find.text('under the form'), findsOneWidget);
    expect(tester.getTopLeft(find.text('Welcome back')).dx, greaterThan(tester.getTopLeft(find.text('Everything your society runs on, in one place.')).dx + 600));
    // The heading and the field share a left edge.
    expect(tester.getTopLeft(find.byType(TextField)).dx, tester.getTopLeft(find.text('Welcome back')).dx);
  });

  testWidgets('a phone shows the logo, the heading and the form in a card, with no brand panel', (tester) async {
    tester.view.physicalSize = const Size(390, 844);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.reset);
    await tester.pumpWidget(_page());
    await tester.pumpAndSettle();

    expect(find.text('Everything your society runs on, in one place.'), findsNothing);
    expect(find.text('Welcome back'), findsOneWidget);
    expect(find.byType(Image), findsOneWidget);
    expect(find.text('the form'), findsOneWidget);
  });

  testWidgets('Back shows only when there is somewhere to go and calls onBack', (tester) async {
    tester.view.physicalSize = const Size(1440, 900);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.reset);
    await tester.pumpWidget(_page());
    await tester.pumpAndSettle();
    expect(find.text('Back'), findsNothing);

    var back = 0;
    await tester.pumpWidget(_page(onBack: () => back++));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Back'));
    expect(back, 1);
  });

  testWidgets('a page that is not scrollable gives its child the height under the heading', (tester) async {
    tester.view.physicalSize = const Size(390, 700);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.reset);
    await tester.pumpWidget(MaterialApp(
      theme: AppTheme.lightTheme,
      home: AuthPage(
        title: 'Steps',
        scrollable: false,
        onBack: () {},
        child: PageView(children: const [Center(child: Text('step one'))]),
      ),
    ));
    await tester.pumpAndSettle();
    expect(find.text('step one'), findsOneWidget);
    expect(tester.getSize(find.byType(PageView)).height, greaterThan(300));
  });
}
