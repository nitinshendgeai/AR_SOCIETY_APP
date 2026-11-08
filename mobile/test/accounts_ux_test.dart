import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/accounts/data/accounts_api.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';

void main() {
  group('formatInrShort (phone tiles)', () {
    test('lakhs and crores', () {
      expect(formatInrShort(1144973.82), '₹11.45 L');
      expect(formatInrShort(12000000), '₹1.20 Cr');
      expect(formatInrShort(-250000), '-₹2.50 L');
    });

    test('just under a crore reads as a crore, not "100.00 L"', () {
      expect(formatInrShort(9999999), '₹1.00 Cr');
      expect(formatInrShort(9999000), '₹99.99 L');
    });

    test('below a lakh it is written in full', () {
      expect(formatInrShort(99999), '₹99,999.00');
    });
  });

  testWidgets('a failed list inside a scrolling page offers Try again without a scroll view of its own', (t) async {
    var retries = 0;
    await t.pumpWidget(MaterialApp(
      theme: AppTheme.lightTheme,
      home: Scaffold(
        body: ListView(children: [
          AppErrorState(compact: true, message: 'Check your connection.', onRetry: () => retries++),
        ]),
      ),
    ));

    expect(find.text('This could not be loaded'), findsOneWidget);
    expect(find.text('Check your connection.'), findsOneWidget);
    await t.tap(find.text('Try again'));
    expect(retries, 1);
  });
}
