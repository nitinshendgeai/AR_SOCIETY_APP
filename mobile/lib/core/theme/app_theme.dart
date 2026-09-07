import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

/// Design language: a native-feeling, iOS-inspired system — vivid single
/// accent, layered neutral grays instead of heavy borders, generous corner
/// radii, soft ambient shadows instead of hard elevation, and a type scale
/// modelled on Apple's Human Interface Guidelines sizes/weights/tracking.
///
/// Scope note: this file (plus the shared widgets in
/// shared/widgets/app_widgets.dart) is the whole redesign surface for this
/// pass — every screen already reads these as static constants or through
/// ThemeData's component themes, so recoloring/retyping here reaches the
/// entire app without touching individual screens. What it can't reach:
/// screens that hand-roll their own `Container(decoration: BoxDecoration(...))`
/// "cards" with their own inline radius/border instead of using a themed
/// component — those keep their existing look until a later per-screen pass.
///
/// Light mode only for now: every color here is also read as a bare static
/// constant (e.g. `AppTheme.textSecondary`) directly in ~66 screen files,
/// not looked up via `Theme.of(context)` — so a `darkTheme` wired into
/// MaterialApp wouldn't reach most of the app and would look broken rather
/// than polished. Real dark-mode support means converting those call sites
/// too; that's its own follow-up project, not a byproduct of this one.
class AppTheme {
  // Bundled locally (assets/fonts/Inter-Variable.ttf) rather than fetched at
  // runtime via the google_fonts package: a runtime font fetch that fails
  // (offline, blocked/slow network, captive portal) previously left the
  // entire app's text unrendered, since Skia has no fallback glyphs for an
  // unresolved web font. A bundled asset font can never fail to load. Inter
  // is a variable font, so Skia interpolates every FontWeight from 100-900
  // out of this one asset — no separate weight files needed.
  static const String _fontFamily = 'Inter';

  // ── Brand & accent ──────────────────────────────────────────────────────
  static const Color primary      = Color(0xFF0066FF);
  static const Color primaryDark  = Color(0xFF0050CC);
  static const Color primarySoft  = Color(0xFFE8F0FF);
  static const Color secondary    = Color(0xFF5856D6);

  // ── Semantic (values match iOS system colors — recognizable, proven
  // contrast, and let a "success/warning/error" glance read instantly) ────
  static const Color success     = Color(0xFF34C759);
  static const Color successSoft = Color(0xFFE6F9EC);
  static const Color warning     = Color(0xFFFF9500);
  static const Color warningSoft = Color(0xFFFFF3E0);
  static const Color error       = Color(0xFFFF3B30);
  static const Color errorSoft   = Color(0xFFFFEBEA);

  // ── Surfaces ─────────────────────────────────────────────────────────────
  // `surface` is the canvas a screen sits on; `cardBg` is what's placed on
  // top of it. Keeping them different values (rather than both white) is
  // what makes a card read as "lifted" without needing a heavy shadow.
  static const Color surface   = Color(0xFFF2F2F7);
  static const Color cardBg    = Color(0xFFFFFFFF);
  static const Color inputFill = Color(0xFFF2F3F6);

  // ── Text ─────────────────────────────────────────────────────────────────
  static const Color textPrimary   = Color(0xFF1C1C1E);
  static const Color textSecondary = Color(0xFF6C6C70);
  static const Color textTertiary  = Color(0xFFAEAEB2);

  // ── Hairlines ────────────────────────────────────────────────────────────
  // Reserved for actual separator lines (Divider, a bottom rule under a
  // header) — cards lean on `cardShadow` below instead of a visible border.
  static const Color border = Color(0xFFE3E3E8);

  /// A soft, wide, low-opacity shadow in place of Material's harder
  /// elevation shadow — the "lifted card on a matte surface" look. Opt in
  /// per-widget via `BoxDecoration(boxShadow: AppTheme.cardShadow)`; not
  /// retrofitted onto existing hand-rolled cards in this pass.
  static const List<BoxShadow> cardShadow = [
    BoxShadow(color: Color(0x0F1C1C1E), blurRadius: 2, offset: Offset(0, 1)),
    BoxShadow(color: Color(0x0A1C1C1E), blurRadius: 16, offset: Offset(0, 8)),
  ];

  // ── Corner radii ─────────────────────────────────────────────────────────
  static const double radiusS  = 10;
  static const double radiusM  = 14;
  static const double radiusL  = 18;
  static const double radiusXl = 24;

  static const SystemUiOverlayStyle systemOverlay = SystemUiOverlayStyle(
    statusBarColor: Colors.transparent,
    statusBarIconBrightness: Brightness.dark,
    statusBarBrightness: Brightness.light,
  );

  static ThemeData get lightTheme {
    const onSurfaceVariant = textSecondary;

    final textTheme = TextTheme(
      // Apple's Large Title / Title 1-3 — tight tracking at large sizes,
      // easing toward neutral as size drops, matching SF Pro's own tracking.
      displayLarge:  const TextStyle(fontFamily: _fontFamily, fontSize: 34, height: 1.15, fontWeight: FontWeight.w700, letterSpacing: -0.4, color: textPrimary),
      displayMedium: const TextStyle(fontFamily: _fontFamily, fontSize: 28, height: 1.2,  fontWeight: FontWeight.w700, letterSpacing: -0.3, color: textPrimary),
      displaySmall:  const TextStyle(fontFamily: _fontFamily, fontSize: 24, height: 1.2,  fontWeight: FontWeight.w700, letterSpacing: -0.2, color: textPrimary),
      headlineLarge: const TextStyle(fontFamily: _fontFamily, fontSize: 22, height: 1.25, fontWeight: FontWeight.w600, letterSpacing: -0.2, color: textPrimary),
      headlineMedium:const TextStyle(fontFamily: _fontFamily, fontSize: 20, height: 1.25, fontWeight: FontWeight.w600, letterSpacing: -0.1, color: textPrimary),
      headlineSmall: const TextStyle(fontFamily: _fontFamily, fontSize: 18, height: 1.3,  fontWeight: FontWeight.w600, color: textPrimary),
      // Headline / Body — the workhorse sizes, tuned for comfortable reading
      // rather than density.
      titleLarge:  const TextStyle(fontFamily: _fontFamily, fontSize: 17, height: 1.3, fontWeight: FontWeight.w600, color: textPrimary),
      titleMedium: const TextStyle(fontFamily: _fontFamily, fontSize: 16, height: 1.3, fontWeight: FontWeight.w600, color: textPrimary),
      titleSmall:  const TextStyle(fontFamily: _fontFamily, fontSize: 14, height: 1.3, fontWeight: FontWeight.w600, color: textPrimary),
      bodyLarge:  const TextStyle(fontFamily: _fontFamily, fontSize: 17, height: 1.45, fontWeight: FontWeight.w400, color: textPrimary),
      bodyMedium: const TextStyle(fontFamily: _fontFamily, fontSize: 15, height: 1.45, fontWeight: FontWeight.w400, color: textPrimary),
      bodySmall:  const TextStyle(fontFamily: _fontFamily, fontSize: 13, height: 1.4,  fontWeight: FontWeight.w400, color: onSurfaceVariant),
      // Labels — buttons, chips, tabs, uppercase eyebrows.
      labelLarge:  const TextStyle(fontFamily: _fontFamily, fontSize: 16, height: 1.2, fontWeight: FontWeight.w600, color: textPrimary),
      labelMedium: const TextStyle(fontFamily: _fontFamily, fontSize: 13, height: 1.2, fontWeight: FontWeight.w600, color: onSurfaceVariant),
      labelSmall:  const TextStyle(fontFamily: _fontFamily, fontSize: 11, height: 1.2, fontWeight: FontWeight.w600, color: textTertiary, letterSpacing: 0.2),
    );

    return ThemeData(
      useMaterial3: true,
      fontFamily: _fontFamily,
      textTheme: textTheme,
      splashFactory: InkSparkle.splashFactory,
      colorScheme: ColorScheme.fromSeed(
        seedColor: primary,
        brightness: Brightness.light,
        primary: primary,
        onPrimary: Colors.white,
        secondary: secondary,
        error: error,
        surface: cardBg,
        onSurface: textPrimary,
        surfaceContainerHighest: surface,
      ),
      scaffoldBackgroundColor: surface,
      splashColor: primary.withOpacity(0.06),
      highlightColor: Colors.transparent,

      appBarTheme: AppBarTheme(
        backgroundColor: surface,
        surfaceTintColor: Colors.transparent,
        foregroundColor: textPrimary,
        elevation: 0,
        scrolledUnderElevation: 0,
        centerTitle: false,
        titleTextStyle: textTheme.titleLarge,
        iconTheme: const IconThemeData(color: textPrimary, size: 22),
        actionsIconTheme: const IconThemeData(color: textPrimary, size: 22),
      ),

      iconTheme: const IconThemeData(color: textPrimary, size: 22),

      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: primary,
          foregroundColor: Colors.white,
          disabledBackgroundColor: primary.withOpacity(0.35),
          disabledForegroundColor: Colors.white.withOpacity(0.8),
          minimumSize: const Size(double.infinity, 52),
          padding: const EdgeInsets.symmetric(horizontal: 20),
          elevation: 0,
          shadowColor: Colors.transparent,
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(radiusM)),
          textStyle: const TextStyle(fontFamily: _fontFamily, fontSize: 16, fontWeight: FontWeight.w600, letterSpacing: -0.1),
        ).copyWith(
          overlayColor: WidgetStateProperty.resolveWith(
            (states) => states.contains(WidgetState.pressed) ? Colors.white.withOpacity(0.14) : null,
          ),
        ),
      ),

      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          foregroundColor: primary,
          minimumSize: const Size(double.infinity, 52),
          padding: const EdgeInsets.symmetric(horizontal: 20),
          side: const BorderSide(color: border, width: 1.2),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(radiusM)),
          textStyle: const TextStyle(fontFamily: _fontFamily, fontSize: 16, fontWeight: FontWeight.w600, letterSpacing: -0.1),
        ).copyWith(
          overlayColor: WidgetStateProperty.resolveWith(
            (states) => states.contains(WidgetState.pressed) ? primary.withOpacity(0.06) : null,
          ),
        ),
      ),

      textButtonTheme: TextButtonThemeData(
        style: TextButton.styleFrom(
          foregroundColor: primary,
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(radiusS)),
          textStyle: const TextStyle(fontFamily: _fontFamily, fontSize: 15, fontWeight: FontWeight.w600),
        ),
      ),

      iconButtonTheme: IconButtonThemeData(
        style: IconButton.styleFrom(foregroundColor: textPrimary),
      ),

      // Border-less filled fields — an inset gray fill rather than an
      // outlined box, with the accent only appearing once a field is
      // actually focused.
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: inputFill,
        isDense: true,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(radiusM),
          borderSide: BorderSide.none,
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(radiusM),
          borderSide: BorderSide.none,
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(radiusM),
          borderSide: const BorderSide(color: primary, width: 1.6),
        ),
        errorBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(radiusM),
          borderSide: const BorderSide(color: error, width: 1.2),
        ),
        focusedErrorBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(radiusM),
          borderSide: const BorderSide(color: error, width: 1.6),
        ),
        contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 16),
        labelStyle: const TextStyle(fontFamily: _fontFamily, fontSize: 15, fontWeight: FontWeight.w400, color: textSecondary),
        floatingLabelStyle: const TextStyle(fontFamily: _fontFamily, fontSize: 13, fontWeight: FontWeight.w600, color: primary),
        hintStyle: const TextStyle(fontFamily: _fontFamily, fontSize: 15, fontWeight: FontWeight.w400, color: textTertiary),
        errorStyle: const TextStyle(fontFamily: _fontFamily, fontSize: 12.5, fontWeight: FontWeight.w500, color: error),
      ),

      cardTheme: CardThemeData(
        color: cardBg,
        surfaceTintColor: Colors.transparent,
        elevation: 0,
        margin: EdgeInsets.zero,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(radiusL)),
      ),

      dialogTheme: DialogThemeData(
        backgroundColor: cardBg,
        surfaceTintColor: Colors.transparent,
        elevation: 0,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(radiusXl)),
        titleTextStyle: textTheme.headlineSmall,
        contentTextStyle: textTheme.bodyMedium?.copyWith(color: textSecondary),
      ),

      bottomSheetTheme: BottomSheetThemeData(
        backgroundColor: cardBg,
        surfaceTintColor: Colors.transparent,
        elevation: 0,
        modalElevation: 0,
        showDragHandle: true,
        dragHandleColor: textTertiary.withOpacity(0.6),
        shape: const RoundedRectangleBorder(
          borderRadius: BorderRadius.vertical(top: Radius.circular(radiusXl)),
        ),
      ),

      snackBarTheme: SnackBarThemeData(
        backgroundColor: textPrimary,
        contentTextStyle: const TextStyle(fontFamily: _fontFamily, fontSize: 14, fontWeight: FontWeight.w500, color: Colors.white),
        behavior: SnackBarBehavior.floating,
        elevation: 0,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(radiusM)),
        insetPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      ),

      dividerTheme: const DividerThemeData(
        color: border,
        thickness: 1,
        space: 1,
      ),

      listTileTheme: ListTileThemeData(
        iconColor: textSecondary,
        textColor: textPrimary,
        titleTextStyle: textTheme.bodyLarge,
        subtitleTextStyle: textTheme.bodySmall,
        contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(radiusM)),
      ),

      chipTheme: ChipThemeData(
        backgroundColor: surface,
        selectedColor: primarySoft,
        disabledColor: surface,
        labelStyle: const TextStyle(fontFamily: _fontFamily, fontSize: 13, fontWeight: FontWeight.w600, color: textSecondary),
        secondaryLabelStyle: const TextStyle(fontFamily: _fontFamily, fontSize: 13, fontWeight: FontWeight.w600, color: primary),
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
        shape: const StadiumBorder(),
        side: BorderSide.none,
      ),

      switchTheme: SwitchThemeData(
        thumbColor: const WidgetStatePropertyAll(Colors.white),
        trackColor: WidgetStateProperty.resolveWith(
          (states) => states.contains(WidgetState.selected) ? success : const Color(0xFFE3E3E8),
        ),
        trackOutlineColor: const WidgetStatePropertyAll(Colors.transparent),
      ),

      checkboxTheme: CheckboxThemeData(
        fillColor: WidgetStateProperty.resolveWith(
          (states) => states.contains(WidgetState.selected) ? primary : Colors.transparent,
        ),
        checkColor: const WidgetStatePropertyAll(Colors.white),
        side: const BorderSide(color: border, width: 1.6),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(6)),
      ),

      radioTheme: RadioThemeData(
        fillColor: WidgetStateProperty.resolveWith(
          (states) => states.contains(WidgetState.selected) ? primary : textTertiary,
        ),
      ),

      progressIndicatorTheme: const ProgressIndicatorThemeData(
        color: primary,
        linearTrackColor: surface,
        circularTrackColor: surface,
      ),

      tabBarTheme: TabBarThemeData(
        labelColor: primary,
        unselectedLabelColor: textSecondary,
        labelStyle: const TextStyle(fontFamily: _fontFamily, fontSize: 14, fontWeight: FontWeight.w600),
        unselectedLabelStyle: const TextStyle(fontFamily: _fontFamily, fontSize: 14, fontWeight: FontWeight.w500),
        indicatorColor: primary,
        dividerColor: border,
      ),

      tooltipTheme: TooltipThemeData(
        decoration: BoxDecoration(
          color: textPrimary,
          borderRadius: BorderRadius.circular(8),
        ),
        textStyle: const TextStyle(fontFamily: _fontFamily, fontSize: 12.5, color: Colors.white),
      ),

      dropdownMenuTheme: DropdownMenuThemeData(
        menuStyle: MenuStyle(
          backgroundColor: const WidgetStatePropertyAll(cardBg),
          surfaceTintColor: const WidgetStatePropertyAll(Colors.transparent),
          elevation: const WidgetStatePropertyAll(6),
          shadowColor: WidgetStatePropertyAll(textPrimary.withOpacity(0.12)),
          shape: WidgetStatePropertyAll(RoundedRectangleBorder(borderRadius: BorderRadius.circular(radiusM))),
        ),
      ),

      popupMenuTheme: PopupMenuThemeData(
        color: cardBg,
        surfaceTintColor: Colors.transparent,
        elevation: 6,
        shadowColor: textPrimary.withOpacity(0.12),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(radiusM)),
        textStyle: textTheme.bodyMedium,
      ),
    );
  }
}
