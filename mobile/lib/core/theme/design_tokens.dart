import 'package:flutter/material.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';

/// Spacing on an 8-point grid (with a 4 for tight icon gaps). Use these instead of loose numbers in new phone screens.
class AppSpacing {
  AppSpacing._();
  static const double xs = 4;
  static const double s = 8;
  static const double m = 12;
  static const double l = 16;
  static const double xl = 24;
  static const double xxl = 32;

  /// Side gutter of a phone page.
  static const double pageGutter = 16;

  /// Smallest touch target (Material and WCAG 2.5.8 guidance).
  static const double minTouch = 48;
}

/// The meaning a status carries. Each tone has a soft background and a text colour that meets 4.5:1 contrast on it,
/// which the bright iOS-style [AppTheme.success], [AppTheme.warning] and [AppTheme.error] do not when used as text.
enum AppTone { neutral, info, success, warning, danger }

class AppToneColors {
  final Color background;
  final Color foreground;
  final Color accent;
  const AppToneColors(this.background, this.foreground, this.accent);
}

const Map<AppTone, AppToneColors> kToneColors = {
  AppTone.neutral: AppToneColors(Color(0xFFEDEDF2), Color(0xFF48484A), AppTheme.textSecondary),
  AppTone.info: AppToneColors(AppTheme.primarySoft, Color(0xFF0047B3), AppTheme.primary),
  AppTone.success: AppToneColors(AppTheme.successSoft, Color(0xFF1B6B33), AppTheme.success),
  AppTone.warning: AppToneColors(AppTheme.warningSoft, Color(0xFF8A4B00), AppTheme.warning),
  AppTone.danger: AppToneColors(AppTheme.errorSoft, Color(0xFFB3261E), AppTheme.error),
};
