import 'dart:math' as math;
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/core/theme/design_tokens.dart';
import 'package:ar_society_app/shared/widgets/app_status.dart';
import 'package:ar_society_app/features/maintenance_billing/presentation/screens/billing_cycle_screen.dart' show billStatusTone;

double _lum(Color c) {
  double f(double v) => v <= 0.03928 ? v / 12.92 : math.pow((v + 0.055) / 1.055, 2.4).toDouble();
  return 0.2126 * f(c.r) + 0.7152 * f(c.g) + 0.0722 * f(c.b);
}

double _contrast(Color a, Color b) {
  final x = _lum(a), y = _lum(b);
  return (math.max(x, y) + 0.05) / (math.min(x, y) + 0.05);
}

Widget _wrap(Widget child) => MaterialApp(theme: AppTheme.lightTheme, home: Scaffold(body: child));

void main() {
  test('every status tone has text that meets 4.5:1 on its own background', () {
    for (final tone in AppTone.values) {
      final c = kToneColors[tone]!;
      expect(_contrast(c.foreground, c.background), greaterThanOrEqualTo(4.5), reason: '$tone');
    }
  });

  test('every text colour in the theme meets 4.5:1 on white and on the page background', () {
    const text = {
      'textPrimary': AppTheme.textPrimary,
      'textSecondary': AppTheme.textSecondary,
      'textTertiary': AppTheme.textTertiary,
    };
    text.forEach((name, colour) {
      expect(_contrast(colour, AppTheme.cardBg), greaterThanOrEqualTo(4.5), reason: '$name on cards');
      expect(_contrast(colour, AppTheme.surface), greaterThanOrEqualTo(4.5), reason: '$name on the page');
      expect(_contrast(colour, AppTheme.inputFill), greaterThanOrEqualTo(4.5), reason: '$name on fields');
    });
  });

  test('the cautionary button fill carries white text at 4.5:1 (the bright orange is 2.2:1)', () {
    expect(_contrast(Colors.white, kWarningFill), greaterThanOrEqualTo(4.5));
    expect(_contrast(Colors.white, AppTheme.warning), lessThan(4.5));
  });

  test('every bill status is written in a tone whose words are readable on white', () {
    for (final status in ['paid', 'overdue', 'partially_paid', 'issued', 'draft', 'cancelled', 'unknown']) {
      final c = kToneColors[billStatusTone(status)]!.foreground;
      expect(_contrast(c, AppTheme.cardBg), greaterThanOrEqualTo(4.5), reason: status);
    }
  });

  testWidgets('status chip shows its label and icon', (tester) async {
    await tester.pumpWidget(_wrap(const AppStatusChip(label: 'Overdue', tone: AppTone.danger, icon: Icons.error_outline)));
    expect(find.text('Overdue'), findsOneWidget);
    expect(find.byIcon(Icons.error_outline), findsOneWidget);
  });

  testWidgets('section header action is tappable and at least 48dp', (tester) async {
    var taps = 0;
    await tester.pumpWidget(_wrap(AppSectionHeader(title: 'Recent bills', actionLabel: 'See all', onAction: () => taps++)));
    final size = tester.getSize(find.widgetWithText(TextButton, 'See all'));
    expect(size.height, greaterThanOrEqualTo(AppSpacing.minTouch));
    await tester.tap(find.text('See all'));
    expect(taps, 1);
  });

  testWidgets('success state and connection banner render and call back', (tester) async {
    var done = 0, retried = 0;
    await tester.pumpWidget(_wrap(Column(children: [
      AppConnectionBanner(message: 'You are offline', onRetry: () => retried++),
      Expanded(child: AppSuccessState(title: 'Payment recorded', message: 'Receipt saved', actionLabel: 'Done', onAction: () => done++)),
    ])));
    expect(find.text('Payment recorded'), findsOneWidget);
    await tester.tap(find.text('Done'));
    await tester.tap(find.text('Retry'));
    expect([done, retried], [1, 1]);
  });
}
