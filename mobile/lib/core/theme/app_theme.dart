import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

class AppTheme {
  // Brand colours
  static const Color primary = Color(0xFF1A56DB);
  static const Color primaryDark = Color(0xFF1239A6);
  static const Color secondary = Color(0xFF0EA5E9);
  static const Color surface = Color(0xFFF9FAFB);
  static const Color error = Color(0xFFDC2626);
  static const Color success = Color(0xFF16A34A);
  static const Color warning = Color(0xFFD97706);
  static const Color textPrimary = Color(0xFF111827);
  static const Color textSecondary = Color(0xFF6B7280);
  static const Color border = Color(0xFFE5E7EB);
  static const Color cardBg = Color(0xFFFFFFFF);

  static TextTheme _safeTextTheme() {
    try {
      print('[THEME] GoogleFonts.interTextTheme');
      final t = GoogleFonts.interTextTheme();
      print('[THEME] interTextTheme OK');
      return t;
    } catch (e) {
      print('[THEME_CRASH] interTextTheme threw: $e — using default');
      return const TextTheme();
    }
  }

  static TextStyle _safeInter(double size, FontWeight weight, [Color? color]) {
    try {
      return GoogleFonts.inter(fontSize: size, fontWeight: weight, color: color);
    } catch (e) {
      print('[THEME_CRASH] GoogleFonts.inter threw: $e — using default');
      return TextStyle(fontSize: size, fontWeight: weight, color: color);
    }
  }

  static ThemeData get lightTheme {
    print('[THEME] lightTheme start');
    final theme = ThemeData(
      useMaterial3: true,
      colorScheme: ColorScheme.fromSeed(
        seedColor: primary,
        brightness: Brightness.light,
      ),
      scaffoldBackgroundColor: surface,
      textTheme: _safeTextTheme(),
      appBarTheme: AppBarTheme(
        backgroundColor: cardBg,
        elevation: 0,
        scrolledUnderElevation: 1,
        titleTextStyle: _safeInter(18, FontWeight.w600, textPrimary),
        iconTheme: const IconThemeData(color: textPrimary),
      ),
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: primary,
          foregroundColor: Colors.white,
          minimumSize: const Size(double.infinity, 52),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(12),
          ),
          textStyle: _safeInter(16, FontWeight.w600),
        ),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: Colors.white,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: const BorderSide(color: border),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: const BorderSide(color: border),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: const BorderSide(color: primary, width: 2),
        ),
        errorBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: const BorderSide(color: error),
        ),
        contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 16),
        labelStyle: _safeInter(14, FontWeight.w400, textSecondary),
        hintStyle: _safeInter(14, FontWeight.w400, textSecondary),
      ),
      cardTheme: CardThemeData(
        color: cardBg,
        elevation: 0,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(16),
          side: const BorderSide(color: border),
        ),
      ),
    );
    print('[THEME] lightTheme done');
    return theme;
  }
}
