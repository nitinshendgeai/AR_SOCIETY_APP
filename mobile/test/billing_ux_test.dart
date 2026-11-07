import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/maintenance_billing/data/maintenance_billing_api.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';

void main() {
  testWidgets('a screen that failed to load says so and Try again asks for it again', (t) async {
    var retries = 0;
    await t.pumpWidget(MaterialApp(
      theme: AppTheme.lightTheme,
      home: Scaffold(body: AppErrorState(message: 'Check your connection.', onRetry: () => retries++)),
    ));

    expect(find.text('This could not be loaded'), findsOneWidget);
    expect(find.text('Check your connection.'), findsOneWidget);
    await t.tap(find.text('Try again'));
    expect(retries, 1);
  });

  group('collectedPercent', () {
    test('rounds down, so almost-all is not "100%"', () {
      expect(collectedPercent(996, 1000), 99);
      expect(collectedPercent(1999, 2000), 99);
      expect(collectedPercent(130, 590), 22);
    });

    test('is 100 only when everything billed is collected, and 0 when nothing is billed', () {
      expect(collectedPercent(1000, 1000), 100);
      expect(collectedPercent(1200, 1000), 100);
      expect(collectedPercent(0, 0), 0);
    });
  });

  test('amounts are written the Indian way, with the lakh grouping', () {
    expect(formatRupees('4500.00'), '₹4,500.00');
    expect(formatRupees('1234567.5'), '₹12,34,567.50');
  });
}
