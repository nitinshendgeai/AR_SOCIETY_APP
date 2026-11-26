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

/// A button fill that white text can sit on at 4.5:1 or better, for the cautionary action (a guard's Check Out). The
/// bright [AppTheme.warning] orange is only 2.2:1 under white text.
const Color kWarningFill = Color(0xFFB45309);

/// The same for the affirmative action (a guard's Check In): bright [AppTheme.success] green is 2.2:1 under white text.
const Color kSuccessFill = Color(0xFF15803D);

/// The meaning a status carries. Each tone has a soft background and a text colour that meets 4.5:1 contrast on it,
/// which the bright iOS-style [AppTheme.success], [AppTheme.warning] and [AppTheme.error] do not when used as text.
enum AppTone { neutral, info, success, warning, danger }

class AppToneColors {
  final Color background;
  final Color foreground;
  final Color accent;
  const AppToneColors(this.background, this.foreground, this.accent);
}

/// The tone colours of the look in use (see [AppTheme.look]).
Map<AppTone, AppToneColors> get kToneColors => AppTheme.isDeck ? _deckTones : _lightTones;

const Map<AppTone, AppToneColors> _lightTones = {
  AppTone.neutral: AppToneColors(Color(0xFFEDEDF2), Color(0xFF48484A), Color(0xFF6C6C70)),
  AppTone.info: AppToneColors(Color(0xFFE8F0FF), Color(0xFF0047B3), Color(0xFF0066FF)),
  AppTone.success: AppToneColors(Color(0xFFE6F9EC), Color(0xFF1B6B33), Color(0xFF34C759)),
  AppTone.warning: AppToneColors(Color(0xFFFFF3E0), Color(0xFF8A4B00), Color(0xFFFF9500)),
  AppTone.danger: AppToneColors(Color(0xFFFFEBEA), Color(0xFFB3261E), Color(0xFFFF3B30)),
};

/// Neon on a dark tint of the same hue.
const Map<AppTone, AppToneColors> _deckTones = {
  AppTone.neutral: AppToneColors(Color(0xFF16203A), Color(0xFFB4C3DB), Color(0xFF9DB0CC)),
  AppTone.info: AppToneColors(Color(0xFF0E2A3A), Color(0xFF67E8F9), Color(0xFF22D3EE)),
  AppTone.success: AppToneColors(Color(0xFF0C2A25), Color(0xFF6EE7B7), Color(0xFF34D399)),
  AppTone.warning: AppToneColors(Color(0xFF2B2310), Color(0xFFFCD34D), Color(0xFFFBBF24)),
  AppTone.danger: AppToneColors(Color(0xFF2E1220), Color(0xFFFDA4AF), Color(0xFFFB7185)),
};
