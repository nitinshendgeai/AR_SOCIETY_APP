import 'package:flutter/gestures.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ar_society_app/core/motion/loading.dart';
import 'package:ar_society_app/core/motion/motion.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';

Widget _host(Widget child, {bool reduceMotion = false}) => MaterialApp(
      theme: AppTheme.lightTheme,
      home: MediaQuery(
        data: MediaQueryData(disableAnimations: reduceMotion),
        child: Scaffold(body: child),
      ),
    );

double _opacityOf(WidgetTester t, Finder f) =>
    t.widget<Opacity>(find.ancestor(of: f, matching: find.byType(Opacity)).first).opacity;

void main() {
  testWidgets('the loader shows nothing at first, fades in, and admits when it is slow', (tester) async {
    await tester.pumpWidget(_host(const AppLoader()));
    final spinner = find.byType(CircularProgressIndicator);
    expect(_opacityOf(tester, spinner), 0);

    await tester.pump(const Duration(milliseconds: 500));
    expect(_opacityOf(tester, spinner), 1);

    final slow = find.text('Still working… the server may be waking up');
    expect(_opacityOf(tester, slow), 0);
    await tester.pump(const Duration(seconds: 7));
    expect(_opacityOf(tester, slow), 1);
  });

  testWidgets('the loader is shown at once for people who asked for less motion', (tester) async {
    await tester.pumpWidget(_host(const AppLoader(), reduceMotion: true));
    expect(_opacityOf(tester, find.byType(CircularProgressIndicator)), 1);
  });

  testWidgets('a pressable control shrinks under a pointer and recovers, without eating the tap', (tester) async {
    var taps = 0;
    await tester.pumpWidget(_host(Center(
      child: PressableScale(child: ElevatedButton(onPressed: () => taps++, child: const Text('Save'))),
    )));
    double scale() => tester.widget<AnimatedScale>(find.byType(AnimatedScale)).scale;
    expect(scale(), 1);

    final g = await tester.startGesture(tester.getCenter(find.text('Save')), kind: PointerDeviceKind.mouse);
    await tester.pump();
    expect(scale(), lessThan(1));
    await g.up();
    await tester.pumpAndSettle();
    expect(scale(), greaterThanOrEqualTo(1));
    expect(taps, 1);
  });

  testWidgets('the primary button swaps its label for a spinner while it works', (tester) async {
    await tester.pumpWidget(_host(const AppPrimaryButton(label: 'Save', isLoading: false)));
    expect(find.text('Save'), findsOneWidget);
    await tester.pumpWidget(_host(const AppPrimaryButton(label: 'Save', isLoading: true)));
    await tester.pump(const Duration(milliseconds: 300));
    expect(find.text('Save'), findsNothing);
    expect(find.byType(CircularProgressIndicator), findsOneWidget);
  });

  testWidgets('reveal brings its child in, later items a beat after earlier ones', (tester) async {
    await tester.pumpWidget(_host(Column(children: const [
      AppReveal(index: 0, child: Text('first')),
      AppReveal(index: 5, child: Text('sixth')),
    ])));
    double fade(String t) => tester.widget<FadeTransition>(find.ancestor(of: find.text(t), matching: find.byType(FadeTransition)).first).opacity.value;
    await tester.pump(const Duration(milliseconds: 150));
    expect(fade('first'), greaterThan(fade('sixth')));
    await tester.pumpAndSettle();
    expect(fade('sixth'), 1);
  });

  testWidgets('placeholder rows shimmer without a ticker leak', (tester) async {
    await tester.pumpWidget(_host(const SizedBox(height: 600, child: SkeletonList(count: 3))));
    await tester.pump(const Duration(milliseconds: 700));
    expect(find.byType(SkeletonBox), findsWidgets);
    await tester.pumpWidget(_host(const SizedBox()));
  });
}
