import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ar_society_app/core/push/visitor_alert.dart';

/// A page with a button that raises the alert, as the push handler does.
Widget _app({required void Function() onReview, Duration ringEvery = const Duration(seconds: 4), int rings = 3}) =>
    MaterialApp(
      home: Builder(
        builder: (context) => Scaffold(
          body: Center(
            child: ElevatedButton(
              onPressed: () => showVisitorAlert(
                context,
                title: 'Visitor at Gate',
                body: 'John (guest) is at the gate',
                onReview: onReview,
                ringEvery: ringEvery,
                rings: rings,
              ),
              child: const Text('arrive'),
            ),
          ),
        ),
      ),
    );

void main() {
  testWidgets('a visitor alert shows who is at the gate and Review opens the approvals', (tester) async {
    var reviewed = 0;
    await tester.pumpWidget(_app(onReview: () => reviewed++));
    await tester.tap(find.text('arrive'));
    await tester.pump();

    expect(find.byKey(const Key('visitor-alert')), findsOneWidget);
    expect(find.text('Visitor at Gate'), findsOneWidget);
    expect(find.text('John (guest) is at the gate'), findsOneWidget);

    await tester.tap(find.byKey(const Key('visitor-alert-review')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('visitor-alert')), findsNothing);
    expect(reviewed, 1);
  });

  testWidgets('Later dismisses the alert without opening anything', (tester) async {
    var reviewed = 0;
    await tester.pumpWidget(_app(onReview: () => reviewed++));
    await tester.tap(find.text('arrive'));
    await tester.pump();
    await tester.tap(find.byKey(const Key('visitor-alert-later')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('visitor-alert')), findsNothing);
    expect(reviewed, 0);
  });

  testWidgets('a second visitor while an alert is up does not stack another', (tester) async {
    await tester.pumpWidget(_app(onReview: () {}));
    await tester.tap(find.text('arrive'));
    await tester.pump();
    // the dialog's barrier blocks the button, so raise a second alert the way the push handler would
    final context = tester.element(find.byKey(const Key('visitor-alert')));
    showVisitorAlert(context, title: 'Second', body: 'again', onReview: () {});
    await tester.pump();
    expect(find.byKey(const Key('visitor-alert')), findsOneWidget);
    expect(find.text('Second'), findsNothing);

    await tester.tap(find.byKey(const Key('visitor-alert-later')));
    await tester.pumpAndSettle();
  });

  testWidgets('answering the alert stops the repeating ring (no timer left running)', (tester) async {
    await tester.pumpWidget(_app(onReview: () {}, ringEvery: const Duration(milliseconds: 200), rings: 50));
    await tester.tap(find.text('arrive'));
    await tester.pump(const Duration(milliseconds: 650)); // several rings have fired
    await tester.tap(find.byKey(const Key('visitor-alert-later')));
    await tester.pumpAndSettle();
    // flutter_test fails the test if a periodic timer is still pending here
  });
}
