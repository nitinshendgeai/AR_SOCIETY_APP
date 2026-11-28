import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:ar_society_app/core/motion/motion.dart';

/// The two looks the user can choose between.
enum AppLook { light, deck }

/// The colours of one look.
class AppPalette {
  final Color primary, primaryDark, primarySoft, secondary;
  final Color success, successSoft, warning, warningSoft, error, errorSoft;
  final Color surface, cardBg, inputFill, fieldBorder;
  final Color textPrimary, textSecondary, textTertiary, border;
  final Color onPrimary; // text and icons on a primary-coloured button
  final List<BoxShadow> cardShadow;
  const AppPalette({
    required this.primary, required this.primaryDark, required this.primarySoft, required this.secondary,
    required this.success, required this.successSoft, required this.warning, required this.warningSoft,
    required this.error, required this.errorSoft, required this.surface, required this.cardBg,
    required this.inputFill, required this.fieldBorder, required this.textPrimary, required this.textSecondary,
    required this.textTertiary, required this.border, required this.onPrimary, required this.cardShadow,
  });

  /// The everyday light look (semantic colours match iOS system colours: recognisable, proven contrast).
  /// `surface` is the canvas a screen sits on; `cardBg` is what's placed on top of it — keeping them different is
  /// what makes a card read as lifted without a heavy shadow.
  static const light = AppPalette(
    primary: Color(0xFF0066FF), primaryDark: Color(0xFF0050CC), primarySoft: Color(0xFFE8F0FF), secondary: Color(0xFF5856D6),
    success: Color(0xFF34C759), successSoft: Color(0xFFE6F9EC),
    warning: Color(0xFFFF9500), warningSoft: Color(0xFFFFF3E0),
    error: Color(0xFFFF3B30), errorSoft: Color(0xFFFFEBEA),
    surface: Color(0xFFF2F2F7), cardBg: Color(0xFFFFFFFF), inputFill: Color(0xFFF2F3F6), fieldBorder: Color(0xFFDADCE2),
    textPrimary: Color(0xFF1C1C1E), textSecondary: Color(0xFF6C6C70), textTertiary: Color(0xFF6E6E73),
    border: Color(0xFFE3E3E8), onPrimary: Color(0xFFFFFFFF),
    cardShadow: [
      BoxShadow(color: Color(0x0F1C1C1E), blurRadius: 2, offset: Offset(0, 1)),
      BoxShadow(color: Color(0x0A1C1C1E), blurRadius: 16, offset: Offset(0, 8)),
    ],
  );

  /// The "Command deck": deep-space navy, glass panels, neon cyan and violet. Text colours keep at least 4.5:1
  /// contrast on the panels.
  static const deck = AppPalette(
    primary: Color(0xFF22D3EE), primaryDark: Color(0xFF06B6D4), primarySoft: Color(0xFF0E2A3A), secondary: Color(0xFFA78BFA),
    success: Color(0xFF34D399), successSoft: Color(0xFF0C2A25),
    warning: Color(0xFFFBBF24), warningSoft: Color(0xFF2B2310),
    error: Color(0xFFFB7185), errorSoft: Color(0xFF2E1220),
    surface: Color(0xB3070B19), cardBg: Color(0xE60B1326), inputFill: Color(0xFF0A1122), fieldBorder: Color(0xFF233457),
    textPrimary: Color(0xFFE6F1FF), textSecondary: Color(0xFF9DB0CC), textTertiary: Color(0xFF8397B5),
    border: Color(0xFF1C2A47), onPrimary: Color(0xFF03050C),
    cardShadow: [
      BoxShadow(color: Color(0x2622D3EE), blurRadius: 22, spreadRadius: -6),
      BoxShadow(color: Color(0x66000000), blurRadius: 16, offset: Offset(0, 8)),
    ],
  );
}

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
/// Two looks, chosen by each user (account menu → Appearance): the light one and the dark sci-fi "Command deck".
/// Screens read colours as `AppTheme.textSecondary` and the like; these come from the palette of the look in use, so
/// switching the look rebuilds the app with the other palette (see `app_look.dart`).
class AppTheme {
  // Bundled locally (assets/fonts/Inter-Variable.ttf) rather than fetched at
  // runtime via the google_fonts package: a runtime font fetch that fails
  // (offline, blocked/slow network, captive portal) previously left the
  // entire app's text unrendered, since Skia has no fallback glyphs for an
  // unresolved web font. A bundled asset font can never fail to load. Inter
  // is a variable font, so Skia interpolates every FontWeight from 100-900
  // out of this one asset — no separate weight files needed.
  static const String _fontFamily = 'Inter';

  /// Hindi and Marathi text is drawn with the bundled Devanagari font (Inter has no Devanagari glyphs).
  static const List<String> _fontFallback = ['NotoSansDevanagari'];

  // ── Colours ──────────────────────────────────────────────────────────────
  // Every colour comes from the palette of the look the user chose (Settings → Appearance): the light look, or
  // the dark sci-fi "Command deck". They are read when a widget builds, so switching the look rebuilds the app
  // (see [AppLookNotifier]). Values of the light look are in [AppPalette.light].
  static AppLook look = AppLook.light;
  static bool get isDeck => look == AppLook.deck;
  static AppPalette get palette => isDeck ? AppPalette.deck : AppPalette.light;

  static Color get primary => palette.primary;
  static Color get primaryDark => palette.primaryDark;
  static Color get primarySoft => palette.primarySoft;
  static Color get secondary => palette.secondary;
  static Color get success => palette.success;
  static Color get successSoft => palette.successSoft;
  static Color get warning => palette.warning;
  static Color get warningSoft => palette.warningSoft;
  static Color get error => palette.error;
  static Color get errorSoft => palette.errorSoft;
  static Color get surface => palette.surface;
  static Color get cardBg => palette.cardBg;
  static Color get inputFill => palette.inputFill;
  static Color get fieldBorder => palette.fieldBorder;
  static Color get textPrimary => palette.textPrimary;
  static Color get textSecondary => palette.textSecondary;
  static Color get textTertiary => palette.textTertiary;
  static Color get border => palette.border;
  static Color get onPrimary => palette.onPrimary;

  /// The banner at the top of a home screen and the sign-in panel: a deep blue sweep in the light look; in the
  /// Command deck a navy-to-indigo glass with a cyan edge. White text reads on both.
  static List<Color> get heroGradient => isDeck
      ? const [Color(0xFF0B1326), Color(0xFF1E1B4B), Color(0xFF0E7490)]
      : const [Color(0xFF0A2A6B), Color(0xFF0057D9), Color(0xFF2F8CFF)];

  /// Placeholder blocks while data loads, and the shimmer across them.
  static Color get skeleton => isDeck ? const Color(0xFF16203A) : const Color(0xFFE9EBF0);
  static Color get skeletonShine => isDeck ? const Color(0xFF22325A) : const Color(0xFFF7F8FA);
  /// Outline of desktop buttons and fields.
  static Color get hairline => isDeck ? const Color(0xFF233457) : const Color(0xFFD1D1D6);

  /// Behind a menu item or a quiet button while the pointer is over it: a pale blue tint in the light look, a
  /// cyan-tinted panel in the Command deck. Text and icons on it turn [primary].
  static Color get hoverFill => primarySoft;

  /// Snackbars and tooltips: a dark slab with white text in both looks (the light look's near-black, the deck's
  /// raised navy — its near-white text colour would leave white text unreadable).
  static Color get inverseSurface => isDeck ? const Color(0xFF1C2B4D) : textPrimary;
  static Color get onInverseSurface => Colors.white;

  /// A filled (primary) button: darker under the pointer, faded when disabled.
  static WidgetStateProperty<Color> get primaryFill => WidgetStateProperty.resolveWith((states) {
        if (states.contains(WidgetState.disabled)) return primary.withOpacity(0.35);
        if (states.contains(WidgetState.hovered) || states.contains(WidgetState.focused)) return primaryDark;
        return primary;
      });

  /// A soft, wide, low-opacity shadow in place of Material's harder elevation shadow — the "lifted card on a matte
  /// surface" look (a faint neon glow in the Command deck). Opt in per widget via
  /// `BoxDecoration(boxShadow: AppTheme.cardShadow)`.
  static List<BoxShadow> get cardShadow => palette.cardShadow;

  // ── Corner radii ─────────────────────────────────────────────────────────
  static const double radiusS  = 10;
  static const double radiusM  = 14;
  static const double radiusL  = 18;
  static const double radiusXl = 24;

  static SystemUiOverlayStyle get systemOverlay => SystemUiOverlayStyle(
        statusBarColor: Colors.transparent,
        statusBarIconBrightness: isDeck ? Brightness.light : Brightness.dark,
        statusBarBrightness: isDeck ? Brightness.dark : Brightness.light,
      );

  /// Buttons rise a little under the pointer and settle when pressed, so they feel like something you can push.
  static final WidgetStateProperty<double> _liftOnHover = WidgetStateProperty.resolveWith((states) {
    if (states.contains(WidgetState.disabled)) return 0;
    if (states.contains(WidgetState.pressed)) return 1;
    if (states.contains(WidgetState.hovered) || states.contains(WidgetState.focused)) return 5;
    // At rest the button already floats a little, with a soft glow in the brand colour.
    return 3;
  });

  static ThemeData get lightTheme {
    final onSurfaceVariant = textSecondary;

    final textTheme = TextTheme(
      // Apple's Large Title / Title 1-3 — tight tracking at large sizes,
      // easing toward neutral as size drops, matching SF Pro's own tracking.
      displayLarge:  TextStyle(fontFamily: _fontFamily, fontFamilyFallback: _fontFallback, fontSize: 34, height: 1.15, fontWeight: FontWeight.w700, letterSpacing: -0.4, color: textPrimary),
      displayMedium: TextStyle(fontFamily: _fontFamily, fontFamilyFallback: _fontFallback, fontSize: 28, height: 1.2,  fontWeight: FontWeight.w700, letterSpacing: -0.3, color: textPrimary),
      displaySmall:  TextStyle(fontFamily: _fontFamily, fontFamilyFallback: _fontFallback, fontSize: 24, height: 1.2,  fontWeight: FontWeight.w700, letterSpacing: -0.2, color: textPrimary),
      headlineLarge: TextStyle(fontFamily: _fontFamily, fontFamilyFallback: _fontFallback, fontSize: 22, height: 1.25, fontWeight: FontWeight.w600, letterSpacing: -0.2, color: textPrimary),
      headlineMedium:TextStyle(fontFamily: _fontFamily, fontFamilyFallback: _fontFallback, fontSize: 20, height: 1.25, fontWeight: FontWeight.w600, letterSpacing: -0.1, color: textPrimary),
      headlineSmall: TextStyle(fontFamily: _fontFamily, fontFamilyFallback: _fontFallback, fontSize: 18, height: 1.3,  fontWeight: FontWeight.w600, color: textPrimary),
      // Headline / Body — the workhorse sizes, tuned for comfortable reading
      // rather than density.
      titleLarge:  TextStyle(fontFamily: _fontFamily, fontFamilyFallback: _fontFallback, fontSize: 17, height: 1.3, fontWeight: FontWeight.w600, color: textPrimary),
      titleMedium: TextStyle(fontFamily: _fontFamily, fontFamilyFallback: _fontFallback, fontSize: 16, height: 1.3, fontWeight: FontWeight.w600, color: textPrimary),
      titleSmall:  TextStyle(fontFamily: _fontFamily, fontFamilyFallback: _fontFallback, fontSize: 14, height: 1.3, fontWeight: FontWeight.w600, color: textPrimary),
      bodyLarge:  TextStyle(fontFamily: _fontFamily, fontFamilyFallback: _fontFallback, fontSize: 17, height: 1.45, fontWeight: FontWeight.w400, color: textPrimary),
      bodyMedium: TextStyle(fontFamily: _fontFamily, fontFamilyFallback: _fontFallback, fontSize: 15, height: 1.45, fontWeight: FontWeight.w400, color: textPrimary),
      bodySmall:  TextStyle(fontFamily: _fontFamily, fontFamilyFallback: _fontFallback, fontSize: 13, height: 1.4,  fontWeight: FontWeight.w400, color: onSurfaceVariant),
      // Labels — buttons, chips, tabs, uppercase eyebrows.
      labelLarge:  TextStyle(fontFamily: _fontFamily, fontFamilyFallback: _fontFallback, fontSize: 16, height: 1.2, fontWeight: FontWeight.w600, color: textPrimary),
      labelMedium: TextStyle(fontFamily: _fontFamily, fontFamilyFallback: _fontFallback, fontSize: 13, height: 1.2, fontWeight: FontWeight.w600, color: onSurfaceVariant),
      labelSmall:  TextStyle(fontFamily: _fontFamily, fontFamilyFallback: _fontFallback, fontSize: 11, height: 1.2, fontWeight: FontWeight.w600, color: textTertiary, letterSpacing: 0.2),
    );

    return ThemeData(
      useMaterial3: true,
      fontFamily: _fontFamily, fontFamilyFallback: _fontFallback,
      textTheme: textTheme,
      splashFactory: InkSparkle.splashFactory,
      // Every page, on every platform, fades in and rises a few pixels (see AppPageTransitions).
      pageTransitionsTheme: PageTransitionsTheme(
        builders: {for (final p in TargetPlatform.values) p: const AppPageTransitions()},
      ),
      // Every spinner and progress bar in the app: the brand blue, round ends, no grey track.
      progressIndicatorTheme: ProgressIndicatorThemeData(
        color: primary,
        circularTrackColor: Colors.transparent,
        linearTrackColor: primarySoft,
        linearMinHeight: 3,
        strokeWidth: 3,
        strokeCap: StrokeCap.round,
      ),
      colorScheme: ColorScheme.fromSeed(
        seedColor: primary,
        brightness: isDeck ? Brightness.dark : Brightness.light,
        primary: primary,
        onPrimary: onPrimary,
        secondary: secondary,
        error: error,
        surface: cardBg,
        onSurface: textPrimary,
        surfaceContainerHighest: surface,
      ),
      // The Command deck draws its starfield behind every page (AppBackdrop), so pages stay see-through.
      scaffoldBackgroundColor: isDeck ? Colors.transparent : surface,
      splashColor: primary.withOpacity(0.06),
      highlightColor: Colors.transparent,
      hoverColor: primary.withOpacity(0.04),
      focusColor: primary.withOpacity(0.10),

      appBarTheme: AppBarTheme(
        backgroundColor: surface,
        surfaceTintColor: Colors.transparent,
        foregroundColor: textPrimary,
        elevation: 0,
        scrolledUnderElevation: 0,
        centerTitle: false,
        titleTextStyle: textTheme.titleLarge,
        iconTheme: IconThemeData(color: textPrimary, size: 22),
        actionsIconTheme: IconThemeData(color: textPrimary, size: 22),
      ),

      iconTheme: IconThemeData(color: textPrimary, size: 22),

      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: primary,
          foregroundColor: onPrimary,
          disabledBackgroundColor: primary.withOpacity(0.35),
          disabledForegroundColor: onPrimary.withOpacity(0.8),
          minimumSize: const Size(double.infinity, 52),
          padding: const EdgeInsets.symmetric(horizontal: 20),
          elevation: 0,
          shadowColor: Colors.transparent,
          shape: const StadiumBorder(),
          textStyle: const TextStyle(fontFamily: _fontFamily, fontFamilyFallback: _fontFallback, fontSize: 16, fontWeight: FontWeight.w600, letterSpacing: -0.1),
        ).copyWith(
          animationDuration: AppMotion.base,
          mouseCursor: const WidgetStatePropertyAll(SystemMouseCursors.click),
          elevation: _liftOnHover,
          shadowColor: WidgetStatePropertyAll(primary.withOpacity(0.35)),
          backgroundColor: primaryFill,
          foregroundColor: WidgetStateProperty.resolveWith(
              (states) => states.contains(WidgetState.disabled) ? onPrimary.withOpacity(0.8) : onPrimary),
          overlayColor: WidgetStateProperty.resolveWith(
            (states) => states.contains(WidgetState.pressed) ? onPrimary.withOpacity(0.14) : Colors.transparent,
          ),
        ),
      ),

      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          foregroundColor: primary,
          minimumSize: const Size(double.infinity, 52),
          padding: const EdgeInsets.symmetric(horizontal: 20),
          side: BorderSide(color: border, width: 1.2),
          shape: const StadiumBorder(),
          textStyle: const TextStyle(fontFamily: _fontFamily, fontFamilyFallback: _fontFallback, fontSize: 16, fontWeight: FontWeight.w600, letterSpacing: -0.1),
        ).copyWith(
          backgroundColor: WidgetStateProperty.resolveWith(
              (states) => states.contains(WidgetState.hovered) ? hoverFill : Colors.transparent),
          side: WidgetStateProperty.resolveWith((states) => states.contains(WidgetState.hovered) || states.contains(WidgetState.focused)
              ? BorderSide(color: primary, width: 1.2)
              : BorderSide(color: border, width: 1.2)),
          overlayColor: WidgetStateProperty.resolveWith(
            (states) => states.contains(WidgetState.pressed) ? primary.withOpacity(0.10) : Colors.transparent,
          ),
        ),
      ),

      textButtonTheme: TextButtonThemeData(
        style: TextButton.styleFrom(
          foregroundColor: primary,
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
          shape: const StadiumBorder(),
          textStyle: const TextStyle(fontFamily: _fontFamily, fontFamilyFallback: _fontFallback, fontSize: 15, fontWeight: FontWeight.w600),
        ).copyWith(
          overlayColor: WidgetStateProperty.resolveWith((states) {
            if (states.contains(WidgetState.pressed)) return primary.withOpacity(0.16);
            if (states.contains(WidgetState.hovered) || states.contains(WidgetState.focused)) return primary.withOpacity(0.10);
            return null;
          }),
        ),
      ),

      // FilledButton (used beside the elevated ones) gets the same bubble look.
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(
          minimumSize: const Size(64, 52),
          padding: const EdgeInsets.symmetric(horizontal: 20),
          shape: const StadiumBorder(),
          textStyle: const TextStyle(fontFamily: _fontFamily, fontFamilyFallback: _fontFallback, fontSize: 16, fontWeight: FontWeight.w600, letterSpacing: -0.1),
        ).copyWith(
          backgroundColor: primaryFill,
          foregroundColor: WidgetStateProperty.resolveWith(
              (states) => states.contains(WidgetState.disabled) ? onPrimary.withOpacity(0.8) : onPrimary),
          overlayColor: WidgetStateProperty.resolveWith(
              (states) => states.contains(WidgetState.pressed) ? onPrimary.withOpacity(0.14) : Colors.transparent),
        ),
      ),

      segmentedButtonTheme: SegmentedButtonThemeData(
        style: ButtonStyle(
          shape: const WidgetStatePropertyAll(StadiumBorder()),
          side: WidgetStatePropertyAll(BorderSide(color: border)),
          backgroundColor: WidgetStateProperty.resolveWith((s) => s.contains(WidgetState.selected) ? primarySoft : cardBg),
          foregroundColor: WidgetStateProperty.resolveWith((s) =>
              s.contains(WidgetState.selected) || s.contains(WidgetState.hovered) ? primary : textSecondary),
          overlayColor: WidgetStateProperty.resolveWith((s) => s.contains(WidgetState.pressed)
              ? primary.withOpacity(0.14)
              : s.contains(WidgetState.hovered) ? primary.withOpacity(0.08) : null),
        ),
      ),

      iconButtonTheme: IconButtonThemeData(
        style: IconButton.styleFrom(foregroundColor: textPrimary).copyWith(
          foregroundColor: WidgetStateProperty.resolveWith((s) {
            if (s.contains(WidgetState.disabled)) return textTertiary;
            if (s.contains(WidgetState.hovered) || s.contains(WidgetState.focused)) return primary;
            return textPrimary;   // an IconButton given its own `color` keeps it (the widget's style wins)
          }),
          overlayColor: WidgetStateProperty.resolveWith((s) => s.contains(WidgetState.pressed)
              ? primary.withOpacity(0.16)
              : s.contains(WidgetState.hovered) || s.contains(WidgetState.focused) ? primary.withOpacity(0.10) : null),
        ),
      ),

      // One look for every screen's main action button (some screens set
      // these colours themselves; the rest got Material's pale tonal FAB).
      floatingActionButtonTheme: FloatingActionButtonThemeData(
        backgroundColor: primary,
        foregroundColor: onPrimary,
        elevation: 3,
        extendedTextStyle: const TextStyle(fontFamily: _fontFamily, fontFamilyFallback: _fontFallback, fontSize: 16, fontWeight: FontWeight.w600),
        shape: const StadiumBorder(),
      ),

      // White fields with a hairline border. Most forms sit straight on
      // the gray `surface` canvas, where a gray fill disappeared into the
      // page; the accent only appears once a field is focused.
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: cardBg,
        hoverColor: Colors.transparent,
        isDense: true,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(radiusM),
          borderSide: BorderSide(color: fieldBorder),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(radiusM),
          borderSide: BorderSide(color: fieldBorder),
        ),
        disabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(radiusM),
          borderSide: BorderSide(color: border),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(radiusM),
          borderSide: BorderSide(color: primary, width: 1.6),
        ),
        errorBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(radiusM),
          borderSide: BorderSide(color: error, width: 1.2),
        ),
        focusedErrorBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(radiusM),
          borderSide: BorderSide(color: error, width: 1.6),
        ),
        contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 16),
        labelStyle: TextStyle(fontFamily: _fontFamily, fontFamilyFallback: _fontFallback, fontSize: 15, fontWeight: FontWeight.w400, color: textSecondary),
        floatingLabelStyle: TextStyle(fontFamily: _fontFamily, fontFamilyFallback: _fontFallback, fontSize: 13, fontWeight: FontWeight.w600, color: primary),
        hintStyle: TextStyle(fontFamily: _fontFamily, fontFamilyFallback: _fontFallback, fontSize: 15, fontWeight: FontWeight.w400, color: textTertiary),
        errorStyle: TextStyle(fontFamily: _fontFamily, fontFamilyFallback: _fontFallback, fontSize: 12.5, fontWeight: FontWeight.w500, color: error),
      ),

      cardTheme: CardThemeData(
        color: cardBg,
        surfaceTintColor: Colors.transparent,
        elevation: 2,
        shadowColor: const Color(0x331C1C1E),
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
        backgroundColor: inverseSurface,
        actionTextColor: isDeck ? primary : const Color(0xFF7FB2FF),
        contentTextStyle: TextStyle(fontFamily: _fontFamily, fontFamilyFallback: _fontFallback, fontSize: 14, fontWeight: FontWeight.w500, color: onInverseSurface),
        behavior: SnackBarBehavior.floating,
        elevation: 0,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(radiusM)),
        insetPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      ),

      dividerTheme: DividerThemeData(
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
        backgroundColor: isDeck ? cardBg : surface,
        selectedColor: primarySoft,
        disabledColor: surface,
        labelStyle: TextStyle(fontFamily: _fontFamily, fontFamilyFallback: _fontFallback, fontSize: 13, fontWeight: FontWeight.w600, color: textSecondary),
        secondaryLabelStyle: TextStyle(fontFamily: _fontFamily, fontFamilyFallback: _fontFallback, fontSize: 13, fontWeight: FontWeight.w600, color: primary),
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
        shape: const StadiumBorder(),
        side: BorderSide.none,
      ),

      switchTheme: SwitchThemeData(
        thumbColor: const WidgetStatePropertyAll(Colors.white),
        trackColor: WidgetStateProperty.resolveWith(
          (states) => states.contains(WidgetState.selected) ? success : border,
        ),
        trackOutlineColor: const WidgetStatePropertyAll(Colors.transparent),
      ),

      checkboxTheme: CheckboxThemeData(
        fillColor: WidgetStateProperty.resolveWith(
          (states) => states.contains(WidgetState.selected) ? primary : Colors.transparent,
        ),
        checkColor: WidgetStatePropertyAll(onPrimary),
        side: BorderSide(color: border, width: 1.6),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(6)),
      ),

      radioTheme: RadioThemeData(
        fillColor: WidgetStateProperty.resolveWith(
          (states) => states.contains(WidgetState.selected) ? primary : textTertiary,
        ),
      ),

      tabBarTheme: TabBarThemeData(
        labelColor: primary,
        unselectedLabelColor: textSecondary,
        labelStyle: const TextStyle(fontFamily: _fontFamily, fontFamilyFallback: _fontFallback, fontSize: 14, fontWeight: FontWeight.w600),
        unselectedLabelStyle: const TextStyle(fontFamily: _fontFamily, fontFamilyFallback: _fontFallback, fontSize: 14, fontWeight: FontWeight.w500),
        indicatorColor: primary,
        dividerColor: border,
      ),

      tooltipTheme: TooltipThemeData(
        decoration: BoxDecoration(
          color: inverseSurface,
          borderRadius: BorderRadius.circular(8),
        ),
        textStyle: TextStyle(fontFamily: _fontFamily, fontFamilyFallback: _fontFallback, fontSize: 12.5, color: onInverseSurface),
      ),

      dropdownMenuTheme: DropdownMenuThemeData(
        menuStyle: MenuStyle(
          backgroundColor: WidgetStatePropertyAll(cardBg),
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

  /// Density pass for desktop-width web (the ERP layout AppShell switches
  /// to at >=1024px), layered over [lightTheme]. Phones keep the roomy
  /// touch-first theme; on a mouse-driven wide screen the web-ERP norms
  /// apply instead (Material 3 desktop / Fluent / Fiori): 14px body text,
  /// 40px auto-width buttons rather than full-width 52px slabs, outlined
  /// fields with a clear focus ring, hover states, thin-bordered cards, and
  /// page titles set as left-aligned headings.
  static ThemeData desktopTheme(ThemeData base) {
    final t = base.textTheme;
    final textTheme = t.copyWith(
      titleLarge:  t.titleLarge?.copyWith(fontSize: 20, fontWeight: FontWeight.w700, letterSpacing: -0.2),
      titleMedium: t.titleMedium?.copyWith(fontSize: 15),
      titleSmall:  t.titleSmall?.copyWith(fontSize: 13.5),
      bodyLarge:   t.bodyLarge?.copyWith(fontSize: 15, height: 1.4),
      bodyMedium:  t.bodyMedium?.copyWith(fontSize: 14, height: 1.4),
      bodySmall:   t.bodySmall?.copyWith(fontSize: 12.5),
      labelLarge:  t.labelLarge?.copyWith(fontSize: 14),
    );
    const buttonText = TextStyle(fontFamily: _fontFamily, fontFamilyFallback: _fontFallback, fontSize: 14, fontWeight: FontWeight.w600);
    const buttonShape = StadiumBorder();
    const buttonSize = Size(64, 40);
    const buttonPadding = EdgeInsets.symmetric(horizontal: 22);
    // Desktop platforms default to compact density, which would shave the
    // 40px button height down to 32px — too small a click target.

    OutlineInputBorder outline(Color color, [double width = 1]) => OutlineInputBorder(
          borderRadius: BorderRadius.circular(8),
          borderSide: BorderSide(color: color, width: width),
        );

    return base.copyWith(
      textTheme: textTheme,
      splashFactory: InkRipple.splashFactory,
      hoverColor: primary.withOpacity(0.06),

      appBarTheme: base.appBarTheme.copyWith(
        toolbarHeight: 64,
        titleSpacing: 24,
        titleTextStyle: textTheme.titleLarge,
      ),

      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: primary,
          foregroundColor: onPrimary,
          disabledBackgroundColor: primary.withOpacity(0.35),
          disabledForegroundColor: onPrimary.withOpacity(0.8),
          minimumSize: buttonSize,
          padding: buttonPadding,
          visualDensity: VisualDensity.standard,
          elevation: 0,
          shadowColor: Colors.transparent,
          shape: buttonShape,
          textStyle: buttonText,
        ).copyWith(
          backgroundColor: primaryFill,
          foregroundColor: WidgetStateProperty.resolveWith(
              (states) => states.contains(WidgetState.disabled) ? onPrimary.withOpacity(0.8) : onPrimary),
          overlayColor: WidgetStateProperty.resolveWith(
              (states) => states.contains(WidgetState.pressed) ? onPrimary.withOpacity(0.14) : Colors.transparent),
          animationDuration: AppMotion.base,
          mouseCursor: const WidgetStatePropertyAll(SystemMouseCursors.click),
          elevation: _liftOnHover,
          shadowColor: WidgetStatePropertyAll(primary.withOpacity(0.35)),
        ),
      ),

      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(
          minimumSize: buttonSize,
          padding: buttonPadding,
          visualDensity: VisualDensity.standard,
          shape: buttonShape,
          textStyle: buttonText,
        ).copyWith(
          backgroundColor: primaryFill,
          foregroundColor: WidgetStateProperty.resolveWith(
              (states) => states.contains(WidgetState.disabled) ? onPrimary.withOpacity(0.8) : onPrimary),
          overlayColor: WidgetStateProperty.resolveWith(
              (states) => states.contains(WidgetState.pressed) ? onPrimary.withOpacity(0.14) : Colors.transparent),
          animationDuration: AppMotion.base,
          mouseCursor: const WidgetStatePropertyAll(SystemMouseCursors.click),
          elevation: _liftOnHover,
          shadowColor: WidgetStatePropertyAll(primary.withOpacity(0.30)),
        ),
      ),

      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          foregroundColor: textPrimary,
          backgroundColor: cardBg,
          minimumSize: buttonSize,
          padding: buttonPadding,
          visualDensity: VisualDensity.standard,
          side: BorderSide(color: hairline),
          shape: buttonShape,
          textStyle: buttonText,
        ).copyWith(
          animationDuration: AppMotion.base,
          mouseCursor: const WidgetStatePropertyAll(SystemMouseCursors.click),
          // Under the pointer the button takes the accent: its border and text turn the primary colour on a tint.
          side: WidgetStateProperty.resolveWith((states) => states.contains(WidgetState.hovered) || states.contains(WidgetState.focused)
              ? BorderSide(color: primary)
              : BorderSide(color: hairline)),
          foregroundColor: WidgetStateProperty.resolveWith((states) {
            if (states.contains(WidgetState.disabled)) return textTertiary;
            if (states.contains(WidgetState.hovered) || states.contains(WidgetState.focused)) return primary;
            return textPrimary;
          }),
          backgroundColor: WidgetStateProperty.resolveWith(
              (states) => states.contains(WidgetState.hovered) ? hoverFill : cardBg),
          overlayColor: WidgetStateProperty.resolveWith(
            (states) => states.contains(WidgetState.pressed) ? primary.withOpacity(0.10) : Colors.transparent,
          ),
        ),
      ),

      textButtonTheme: TextButtonThemeData(
        style: TextButton.styleFrom(
          foregroundColor: primary,
          minimumSize: const Size(48, 36),
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
          shape: buttonShape,
          textStyle: buttonText,
        ).copyWith(
          animationDuration: AppMotion.base,
          mouseCursor: const WidgetStatePropertyAll(SystemMouseCursors.click),
          overlayColor: WidgetStateProperty.resolveWith((states) {
            if (states.contains(WidgetState.pressed)) return primary.withOpacity(0.16);
            if (states.contains(WidgetState.hovered) || states.contains(WidgetState.focused)) return primary.withOpacity(0.10);
            return null;
          }),
        ),
      ),

      floatingActionButtonTheme: base.floatingActionButtonTheme.copyWith(
        backgroundColor: primary,
        foregroundColor: onPrimary,
        elevation: 2,
        hoverElevation: 4,
        extendedTextStyle: buttonText,
        shape: const StadiumBorder(),
      ),

      // Outlined white fields: on a large light-gray canvas a gray fill
      // reads as disabled, and forms need visible field boundaries.
      inputDecorationTheme: base.inputDecorationTheme.copyWith(
        fillColor: cardBg,
        hoverColor: Colors.transparent,
        border: outline(hairline),
        enabledBorder: outline(hairline),
        focusedBorder: outline(primary, 2),
        errorBorder: outline(error),
        focusedErrorBorder: outline(error, 2),
        disabledBorder: outline(border),
        contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 14),
        labelStyle: TextStyle(fontFamily: _fontFamily, fontFamilyFallback: _fontFallback, fontSize: 14, fontWeight: FontWeight.w400, color: textSecondary),
        hintStyle: TextStyle(fontFamily: _fontFamily, fontFamilyFallback: _fontFallback, fontSize: 14, fontWeight: FontWeight.w400, color: textTertiary),
      ),

      cardTheme: base.cardTheme.copyWith(
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(12),
          side: BorderSide(color: border),
        ),
      ),

      dialogTheme: base.dialogTheme.copyWith(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        titleTextStyle: textTheme.titleLarge,
        contentTextStyle: textTheme.bodyMedium?.copyWith(color: textSecondary),
      ),

      listTileTheme: base.listTileTheme.copyWith(
        titleTextStyle: textTheme.bodyLarge?.copyWith(fontSize: 14.5),
        subtitleTextStyle: textTheme.bodySmall,
        minVerticalPadding: 10,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      ),

      scrollbarTheme: const ScrollbarThemeData(
        thumbVisibility: WidgetStatePropertyAll(true),
        thickness: WidgetStatePropertyAll(8),
        radius: Radius.circular(4),
      ),

      tooltipTheme: base.tooltipTheme.copyWith(waitDuration: const Duration(milliseconds: 400)),
    );
  }
}
