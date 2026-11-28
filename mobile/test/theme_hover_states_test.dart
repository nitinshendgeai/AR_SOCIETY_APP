import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';

double _contrast(Color a, Color b) {
  final la = a.computeLuminance(), lb = b.computeLuminance();
  final hi = la > lb ? la : lb, lo = la > lb ? lb : la;
  return (hi + 0.05) / (lo + 0.05);
}

void main() {
  tearDown(() => AppTheme.look = AppLook.light);

  for (final look in AppLook.values) {
    group('$look', () {
      setUp(() => AppTheme.look = look);

      test('filled buttons darken under the pointer and keep readable text', () {
        for (final t in [AppTheme.lightTheme, AppTheme.desktopTheme(AppTheme.lightTheme)]) {
          for (final style in [t.elevatedButtonTheme.style!, t.filledButtonTheme.style!]) {
            final rest = style.backgroundColor!.resolve({})!;
            final hover = style.backgroundColor!.resolve({WidgetState.hovered})!;
            final text = style.foregroundColor!.resolve({WidgetState.hovered})!;
            expect(rest, AppTheme.primary);
            expect(hover, AppTheme.primaryDark);
            expect(text, AppTheme.onPrimary);
            expect(_contrast(text, hover), greaterThanOrEqualTo(4.5));
          }
        }
      });

      test('outlined buttons take the accent and a tint on hover (desktop)', () {
        final s = AppTheme.desktopTheme(AppTheme.lightTheme).outlinedButtonTheme.style!;
        expect(s.side!.resolve({WidgetState.hovered})!.color, AppTheme.primary);
        expect(s.side!.resolve({})!.color, AppTheme.hairline);
        expect(s.foregroundColor!.resolve({WidgetState.hovered}), AppTheme.primary);
        expect(s.backgroundColor!.resolve({WidgetState.hovered}), AppTheme.hoverFill);
      });

      test('icon buttons and segments turn the accent on hover', () {
        final t = AppTheme.lightTheme;
        expect(t.iconButtonTheme.style!.foregroundColor!.resolve({WidgetState.hovered}), AppTheme.primary);
        expect(t.segmentedButtonTheme.style!.foregroundColor!.resolve({WidgetState.hovered}), AppTheme.primary);
      });

      test('snackbars, tooltips and checkbox ticks stay readable', () {
        final t = AppTheme.lightTheme;
        final snackText = t.snackBarTheme.contentTextStyle!.color!;
        expect(_contrast(snackText, t.snackBarTheme.backgroundColor!), greaterThanOrEqualTo(4.5));
        final tip = t.tooltipTheme.decoration as BoxDecoration;
        expect(_contrast(t.tooltipTheme.textStyle!.color!, tip.color!), greaterThanOrEqualTo(4.5));
        expect(_contrast(t.checkboxTheme.checkColor!.resolve({WidgetState.selected})!, AppTheme.primary),
            greaterThanOrEqualTo(4.5));
      });
    });
  }
}
