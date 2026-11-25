import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:ar_society_app/core/l10n/app_locale.dart';
import 'package:ar_society_app/core/theme/design_tokens.dart';
import 'package:ar_society_app/shared/widgets/app_form.dart' show AppPageSkin;

/// The Accounts Agent's look: a dark command-deck — deep space background, a faint perspective grid, neon
/// cyan / violet accents, glass panels with HUD corner brackets. Every agent screen is wrapped in [AgentHud] by the
/// router, so the rest of the app keeps its own light theme.
abstract final class Hud {
  static const Color void0 = Color(0xFF03050C); // deepest background
  static const Color void1 = Color(0xFF070B19);
  static const Color panel = Color(0xFF0B1326); // glass panel base
  static const Color panelHi = Color(0xFF101B33);
  static const Color line = Color(0xFF1C2A47); // hairlines and borders
  static const Color text = Color(0xFFE6F1FF);
  static const Color dim = Color(0xFF8DA2C0);
  static const Color faint = Color(0xFF5B6E8C);
  static const Color cyan = Color(0xFF22D3EE);
  static const Color violet = Color(0xFF8B5CF6);
  static const Color violetText = Color(0xFFB79CFF); // violet light enough to read as text
  static const Color green = Color(0xFF34D399);
  static const Color amber = Color(0xFFFBBF24);
  static const Color red = Color(0xFFF43F5E);
  static const Color blue = Color(0xFF60A5FA);

  /// Numbers line up in columns and read like an instrument panel.
  static const List<FontFeature> tabular = [FontFeature.tabularFigures()];

  static Color tone(AppTone t) => switch (t) {
        AppTone.success => green,
        AppTone.warning => amber,
        AppTone.danger => red,
        AppTone.info => cyan,
        AppTone.neutral => dim,
      };

  /// A small all-caps label ("LAST MONITORED").
  static TextStyle label({Color color = dim, double size = 11}) =>
      TextStyle(fontSize: size, fontWeight: FontWeight.w600, letterSpacing: 1.4, color: color);
}

ThemeData agentHudTheme(ThemeData base) {
  final scheme = ColorScheme.fromSeed(
    seedColor: Hud.cyan,
    brightness: Brightness.dark,
  ).copyWith(
    primary: Hud.cyan,
    onPrimary: Hud.void0,
    secondary: Hud.violet,
    onSecondary: Colors.white,
    secondaryContainer: const Color(0xFF16254A),
    onSecondaryContainer: Hud.text,
    tertiary: Hud.green,
    error: Hud.red,
    surface: Hud.panel,
    onSurface: Hud.text,
    onSurfaceVariant: Hud.dim,
    surfaceContainerHighest: Hud.panelHi,
    surfaceContainerHigh: Hud.panelHi,
    surfaceContainer: Hud.panel,
    surfaceContainerLow: Hud.panel,
    outline: Hud.line,
    outlineVariant: Hud.line,
  );
  final shape = RoundedRectangleBorder(borderRadius: BorderRadius.circular(10));
  OutlineInputBorder field(Color c, [double w = 1]) =>
      OutlineInputBorder(borderRadius: BorderRadius.circular(10), borderSide: BorderSide(color: c, width: w));
  final text = base.textTheme.apply(bodyColor: Hud.text, displayColor: Hud.text);
  return base.copyWith(
    brightness: Brightness.dark,
    colorScheme: scheme,
    scaffoldBackgroundColor: Colors.transparent,
    canvasColor: Hud.panel,
    textTheme: text.copyWith(
      bodySmall: text.bodySmall?.copyWith(color: Hud.dim),
      labelMedium: text.labelMedium?.copyWith(color: Hud.dim),
      labelSmall: text.labelSmall?.copyWith(color: Hud.faint),
    ),
    iconTheme: const IconThemeData(color: Hud.cyan, size: 22),
    dividerTheme: DividerThemeData(color: Hud.cyan.withValues(alpha: 0.14), thickness: 1),
    progressIndicatorTheme: const ProgressIndicatorThemeData(color: Hud.cyan, linearTrackColor: Hud.line, circularTrackColor: Hud.line),
    appBarTheme: base.appBarTheme.copyWith(
      backgroundColor: Hud.void1,
      foregroundColor: Hud.text,
      surfaceTintColor: Colors.transparent,
      iconTheme: const IconThemeData(color: Hud.cyan, size: 22),
      actionsIconTheme: const IconThemeData(color: Hud.cyan, size: 22),
      titleTextStyle: base.appBarTheme.titleTextStyle?.copyWith(color: Hud.text, letterSpacing: 0.6) ??
          const TextStyle(fontSize: 17, fontWeight: FontWeight.w700, color: Hud.text, letterSpacing: 0.6),
    ),
    iconButtonTheme: IconButtonThemeData(
      style: IconButton.styleFrom(foregroundColor: Hud.cyan, highlightColor: Hud.cyan.withValues(alpha: 0.12)),
    ),
    filledButtonTheme: FilledButtonThemeData(
      style: FilledButton.styleFrom(
        backgroundColor: Hud.cyan,
        foregroundColor: Hud.void0,
        disabledBackgroundColor: Hud.line,
        disabledForegroundColor: Hud.faint,
        shape: shape,
        padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 14),
        textStyle: const TextStyle(fontWeight: FontWeight.w700, letterSpacing: 0.4),
        shadowColor: Hud.cyan,
        elevation: 0,
      ),
    ),
    outlinedButtonTheme: OutlinedButtonThemeData(
      style: OutlinedButton.styleFrom(
        foregroundColor: Hud.cyan,
        disabledForegroundColor: Hud.faint,
        backgroundColor: Hud.cyan.withValues(alpha: 0.04),
        side: BorderSide(color: Hud.cyan.withValues(alpha: 0.45)),
        shape: shape,
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
        textStyle: const TextStyle(fontWeight: FontWeight.w600, letterSpacing: 0.4),
      ),
    ),
    textButtonTheme: TextButtonThemeData(style: TextButton.styleFrom(foregroundColor: Hud.cyan, shape: shape)),
    elevatedButtonTheme: ElevatedButtonThemeData(
      style: ElevatedButton.styleFrom(backgroundColor: Hud.panelHi, foregroundColor: Hud.cyan, shape: shape),
    ),
    segmentedButtonTheme: SegmentedButtonThemeData(
      style: ButtonStyle(
        side: WidgetStatePropertyAll(BorderSide(color: Hud.cyan.withValues(alpha: 0.35))),
        shape: WidgetStatePropertyAll(shape),
        backgroundColor: WidgetStateProperty.resolveWith(
            (s) => s.contains(WidgetState.selected) ? Hud.cyan.withValues(alpha: 0.18) : Hud.panel.withValues(alpha: 0.6)),
        foregroundColor: WidgetStateProperty.resolveWith((s) => s.contains(WidgetState.selected) ? Hud.cyan : Hud.dim),
        iconColor: WidgetStateProperty.resolveWith((s) => s.contains(WidgetState.selected) ? Hud.cyan : Hud.dim),
      ),
    ),
    inputDecorationTheme: base.inputDecorationTheme.copyWith(
      filled: true,
      fillColor: Hud.void1.withValues(alpha: 0.75),
      border: field(Hud.line),
      enabledBorder: field(Hud.line),
      disabledBorder: field(Hud.line.withValues(alpha: 0.5)),
      focusedBorder: field(Hud.cyan, 1.4),
      errorBorder: field(Hud.red, 1.2),
      focusedErrorBorder: field(Hud.red, 1.6),
      labelStyle: base.inputDecorationTheme.labelStyle?.copyWith(color: Hud.dim),
      floatingLabelStyle: base.inputDecorationTheme.floatingLabelStyle?.copyWith(color: Hud.cyan, letterSpacing: 0.8),
      hintStyle: base.inputDecorationTheme.hintStyle?.copyWith(color: Hud.faint),
      helperStyle: const TextStyle(color: Hud.faint),
      prefixIconColor: Hud.dim,
      suffixIconColor: Hud.dim,
    ),
    dropdownMenuTheme: const DropdownMenuThemeData(textStyle: TextStyle(color: Hud.text), menuStyle: MenuStyle(backgroundColor: WidgetStatePropertyAll(Hud.panelHi))),
    popupMenuTheme: const PopupMenuThemeData(color: Hud.panelHi, textStyle: TextStyle(color: Hud.text)),
    switchTheme: SwitchThemeData(
      thumbColor: WidgetStateProperty.resolveWith((s) => s.contains(WidgetState.selected) ? Hud.void0 : Hud.dim),
      trackColor: WidgetStateProperty.resolveWith((s) => s.contains(WidgetState.selected) ? Hud.cyan : Hud.line),
      trackOutlineColor: WidgetStatePropertyAll(Hud.cyan.withValues(alpha: 0.3)),
    ),
    checkboxTheme: CheckboxThemeData(
      fillColor: WidgetStateProperty.resolveWith((s) => s.contains(WidgetState.selected) ? Hud.cyan : Colors.transparent),
      checkColor: const WidgetStatePropertyAll(Hud.void0),
      side: const BorderSide(color: Hud.dim),
    ),
    chipTheme: base.chipTheme.copyWith(
      backgroundColor: Hud.panel,
      selectedColor: Hud.cyan.withValues(alpha: 0.2),
      labelStyle: const TextStyle(color: Hud.text),
      side: BorderSide(color: Hud.cyan.withValues(alpha: 0.3)),
      checkmarkColor: Hud.cyan,
    ),
    listTileTheme: const ListTileThemeData(textColor: Hud.text, iconColor: Hud.cyan, subtitleTextStyle: TextStyle(color: Hud.dim)),
    expansionTileTheme: const ExpansionTileThemeData(
      textColor: Hud.text, collapsedTextColor: Hud.text, iconColor: Hud.cyan, collapsedIconColor: Hud.dim),
    tabBarTheme: base.tabBarTheme.copyWith(
      labelColor: Hud.cyan, unselectedLabelColor: Hud.dim, indicatorColor: Hud.cyan, dividerColor: Hud.line),
    tooltipTheme: TooltipThemeData(
      decoration: BoxDecoration(color: Hud.panelHi, border: Border.all(color: Hud.cyan.withValues(alpha: 0.4)), borderRadius: BorderRadius.circular(6)),
      textStyle: const TextStyle(color: Hud.text, fontSize: 12),
    ),
    cardTheme: base.cardTheme.copyWith(color: Hud.panel, surfaceTintColor: Colors.transparent),
    snackBarTheme: base.snackBarTheme,
  );
}

/// Wraps one agent screen in the command-deck theme and its animated backdrop.
class AgentHud extends StatelessWidget {
  final Widget child;
  const AgentHud({super.key, required this.child});

  @override
  Widget build(BuildContext context) {
    final theme = agentHudTheme(Theme.of(context));
    return Theme(
      data: theme,
      child: AppPageSkin(
        background: Colors.transparent,
        title: Hud.text,
        subtitle: Hud.dim,
        backBackground: Hud.panel,
        backBorder: Hud.cyan.withValues(alpha: 0.4),
        child: ColoredBox(
          color: Hud.void0,
          child: Stack(fit: StackFit.expand, children: [
            const Positioned.fill(child: HudBackdrop()),
            DefaultTextStyle.merge(style: const TextStyle(color: Hud.text), child: child),
          ]),
        ),
      ),
    );
  }
}

/// Deep-space gradient, two nebula glows, a perspective grid falling away to a horizon, a few stars and a slow scan
/// line. The scan line stands still when the user has asked for less motion.
class HudBackdrop extends StatefulWidget {
  const HudBackdrop({super.key});
  @override
  State<HudBackdrop> createState() => _HudBackdropState();
}

class _HudBackdropState extends State<HudBackdrop> with SingleTickerProviderStateMixin {
  late final AnimationController _c = AnimationController(vsync: this, duration: const Duration(seconds: 9));

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    final still = MediaQuery.maybeDisableAnimationsOf(context) ?? false;
    if (still || TickerMode.valuesOf(context).enabled == false) {
      _c.stop();
      _c.value = 0.35;
    } else if (!_c.isAnimating) {
      _c.repeat();
    }
  }

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => IgnorePointer(
        child: ExcludeSemantics(
          child: RepaintBoundary(child: CustomPaint(painter: _BackdropPainter(_c), isComplex: true)),
        ),
      );
}

class _BackdropPainter extends CustomPainter {
  final Animation<double> t;
  _BackdropPainter(this.t) : super(repaint: t);

  static final List<Offset> _stars = () {
    final r = math.Random(7);
    return [for (var i = 0; i < 70; i++) Offset(r.nextDouble(), r.nextDouble() * 0.6)];
  }();

  @override
  void paint(Canvas canvas, Size size) {
    final rect = Offset.zero & size;
    canvas.drawRect(
      rect,
      Paint()
        ..shader = const LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          colors: [Color(0xFF060A1A), Hud.void0, Color(0xFF050817)],
          stops: [0, 0.55, 1],
        ).createShader(rect),
    );
    void glow(Offset c, double r, Color color) => canvas.drawCircle(
          c,
          r,
          Paint()
            ..shader = RadialGradient(colors: [color, color.withValues(alpha: 0)]).createShader(Rect.fromCircle(center: c, radius: r)),
        );
    final w = size.width, h = size.height;
    glow(Offset(w * 0.85, h * 0.05), math.max(w, h) * 0.55, Hud.violet.withValues(alpha: 0.16));
    glow(Offset(w * 0.1, h * 0.3), math.max(w, h) * 0.45, Hud.cyan.withValues(alpha: 0.09));

    final star = Paint()..color = Colors.white;
    for (var i = 0; i < _stars.length; i++) {
      final s = _stars[i];
      final twinkle = 0.25 + 0.35 * (0.5 + 0.5 * math.sin((t.value * 2 * math.pi) + i));
      star.color = Colors.white.withValues(alpha: twinkle * 0.6);
      canvas.drawCircle(Offset(s.dx * w, s.dy * h), i % 9 == 0 ? 1.2 : 0.7, star);
    }

    // Perspective floor grid from the horizon (62%) down.
    final horizon = h * 0.62;
    final grid = Paint()
      ..strokeWidth = 1
      ..color = Hud.cyan.withValues(alpha: 0.07);
    final vanish = Offset(w / 2, horizon);
    for (var i = -14; i <= 14; i++) {
      canvas.drawLine(vanish, Offset(w / 2 + i * w * 0.12, h), grid);
    }
    final drift = t.value; // rows slide toward the viewer
    for (var k = 0; k < 12; k++) {
      final p = (k + drift) / 12;
      final y = horizon + (h - horizon) * p * p;
      grid.color = Hud.cyan.withValues(alpha: 0.02 + 0.09 * p);
      canvas.drawLine(Offset(0, y), Offset(w, y), grid);
    }
    canvas.drawRect(
      Rect.fromLTWH(0, horizon - 40, w, 80),
      Paint()
        ..shader = LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          colors: [Hud.cyan.withValues(alpha: 0), Hud.cyan.withValues(alpha: 0.06), Hud.cyan.withValues(alpha: 0)],
        ).createShader(Rect.fromLTWH(0, horizon - 40, w, 80)),
    );

    // Scan line.
    final sy = h * t.value;
    canvas.drawRect(
      Rect.fromLTWH(0, sy - 60, w, 60),
      Paint()
        ..shader = LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          colors: [Hud.cyan.withValues(alpha: 0), Hud.cyan.withValues(alpha: 0.035)],
        ).createShader(Rect.fromLTWH(0, sy - 60, w, 60)),
    );
  }

  @override
  bool shouldRepaint(_BackdropPainter old) => false;
}

/// HUD corner brackets drawn over a panel's corners.
class HudCorners extends CustomPainter {
  final Color color;
  final double length;
  const HudCorners({this.color = Hud.cyan, this.length = 12});
  @override
  void paint(Canvas canvas, Size s) {
    final p = Paint()
      ..color = color
      ..strokeWidth = 1.6
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.square;
    final l = math.min(length, math.min(s.width, s.height) / 3);
    canvas.drawPath(
      Path()
        ..moveTo(0, l)
        ..lineTo(0, 0)
        ..lineTo(l, 0)
        ..moveTo(s.width - l, 0)
        ..lineTo(s.width, 0)
        ..lineTo(s.width, l)
        ..moveTo(s.width, s.height - l)
        ..lineTo(s.width, s.height)
        ..lineTo(s.width - l, s.height)
        ..moveTo(l, s.height)
        ..lineTo(0, s.height)
        ..lineTo(0, s.height - l),
      p,
    );
  }

  @override
  bool shouldRepaint(HudCorners old) => old.color != color || old.length != length;
}

/// A status tag: outlined in its tone's neon, all caps, with a lit dot.
class HudChip extends StatelessWidget {
  final String label;
  final AppTone tone;
  final IconData? icon;
  const HudChip({super.key, required this.label, this.tone = AppTone.neutral, this.icon});

  @override
  Widget build(BuildContext context) {
    final c = Hud.tone(tone);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 4),
      decoration: BoxDecoration(
        color: c.withValues(alpha: 0.10),
        border: Border.all(color: c.withValues(alpha: 0.55)),
        borderRadius: BorderRadius.circular(4),
      ),
      child: Row(mainAxisSize: MainAxisSize.min, children: [
        if (icon != null)
          Icon(icon, size: 13, color: c)
        else
          Container(
            width: 6,
            height: 6,
            decoration: BoxDecoration(color: c, shape: BoxShape.circle, boxShadow: [BoxShadow(color: c, blurRadius: 6)]),
          ),
        const SizedBox(width: 6),
        Flexible(
          child: Text(
            label,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: TextStyle(fontSize: 11.5, fontWeight: FontWeight.w700, letterSpacing: 0.6, color: c),
          ),
        ),
      ]),
    );
  }
}

/// The "agent online" core: concentric rings around a lit centre, slowly turning.
class HudCore extends StatefulWidget {
  final Color color;
  final IconData icon;
  final double size;
  const HudCore({super.key, required this.color, required this.icon, this.size = 84});
  @override
  State<HudCore> createState() => _HudCoreState();
}

class _HudCoreState extends State<HudCore> with SingleTickerProviderStateMixin {
  late final AnimationController _c = AnimationController(vsync: this, duration: const Duration(seconds: 12));

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    final still = MediaQuery.maybeDisableAnimationsOf(context) ?? false;
    if (still) {
      _c.stop();
    } else if (!_c.isAnimating) {
      _c.repeat();
    }
  }

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => ExcludeSemantics(
        child: SizedBox.square(
          dimension: widget.size,
          child: Stack(alignment: Alignment.center, children: [
            Positioned.fill(child: RepaintBoundary(child: CustomPaint(painter: _CorePainter(_c, widget.color)))),
            Icon(widget.icon, color: widget.color, size: widget.size * 0.32, shadows: [Shadow(color: widget.color, blurRadius: 16)]),
          ]),
        ),
      );
}

class _CorePainter extends CustomPainter {
  final Animation<double> t;
  final Color color;
  _CorePainter(this.t, this.color) : super(repaint: t);

  @override
  void paint(Canvas canvas, Size s) {
    final c = s.center(Offset.zero);
    final r = s.shortestSide / 2;
    canvas.drawCircle(
      c,
      r,
      Paint()..shader = RadialGradient(colors: [color.withValues(alpha: 0.35), color.withValues(alpha: 0)]).createShader(Rect.fromCircle(center: c, radius: r)),
    );
    final ring = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.2;
    final a = t.value * 2 * math.pi;
    ring.color = color.withValues(alpha: 0.85);
    canvas.drawArc(Rect.fromCircle(center: c, radius: r * 0.92), a, math.pi * 1.2, false, ring);
    ring.color = color.withValues(alpha: 0.4);
    canvas.drawArc(Rect.fromCircle(center: c, radius: r * 0.92), a + math.pi * 1.35, math.pi * 0.4, false, ring);
    ring
      ..strokeWidth = 2
      ..color = Hud.violet.withValues(alpha: 0.8);
    canvas.drawArc(Rect.fromCircle(center: c, radius: r * 0.74), -a * 1.6, math.pi * 0.7, false, ring);
    ring
      ..strokeWidth = 1
      ..color = color.withValues(alpha: 0.25);
    canvas.drawCircle(c, r * 0.56, ring);
    // tick marks
    final tick = Paint()
      ..color = color.withValues(alpha: 0.5)
      ..strokeWidth = 1;
    for (var i = 0; i < 24; i++) {
      final ang = i * math.pi / 12 + a * 0.3;
      final o = Offset(math.cos(ang), math.sin(ang));
      canvas.drawLine(c + o * r * 0.98, c + o * r * (i % 6 == 0 ? 0.84 : 0.92), tick);
    }
  }

  @override
  bool shouldRepaint(_CorePainter old) => old.color != color;
}

/// [AppErrorState] in the command-deck colours.
class HudErrorState extends StatelessWidget {
  final String message;
  final VoidCallback onRetry;
  final bool compact;
  const HudErrorState({super.key, required this.message, required this.onRetry, this.compact = false});
  @override
  Widget build(BuildContext context) {
    final body = Padding(
      padding: EdgeInsets.symmetric(vertical: compact ? 24 : 48, horizontal: 16),
      child: Semantics(
        liveRegion: true,
        child: Column(mainAxisSize: MainAxisSize.min, children: [
          Icon(Icons.portable_wifi_off_rounded, size: compact ? 28 : 40, color: Hud.red, shadows: const [Shadow(color: Hud.red, blurRadius: 14)]),
          const SizedBox(height: 12),
          Text('SIGNAL LOST', style: Hud.label(color: Hud.red, size: 12)),
          const SizedBox(height: 4),
          Text(context.tr('This could not be loaded'), textAlign: TextAlign.center, style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w700, color: Hud.text)),
          const SizedBox(height: 4),
          Text(message, textAlign: TextAlign.center, style: const TextStyle(fontSize: 13, color: Hud.dim, height: 1.4)),
          const SizedBox(height: 14),
          OutlinedButton.icon(onPressed: onRetry, icon: const Icon(Icons.refresh_rounded, size: 18), label: Text(context.tr('Try again'))),
        ]),
      ),
    );
    return compact ? body : Center(child: SingleChildScrollView(physics: const AlwaysScrollableScrollPhysics(), child: body));
  }
}

/// [AppEmptyState] in the command-deck colours.
class HudEmptyState extends StatelessWidget {
  final IconData icon;
  final String title;
  final String? subtitle;
  final String? actionLabel;
  final VoidCallback? onAction;
  const HudEmptyState({super.key, required this.icon, required this.title, this.subtitle, this.actionLabel, this.onAction});
  @override
  Widget build(BuildContext context) => Center(
        child: Padding(
          padding: const EdgeInsets.all(32),
          child: Column(mainAxisSize: MainAxisSize.min, children: [
            Container(
              width: 64,
              height: 64,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: Hud.cyan.withValues(alpha: 0.06),
                border: Border.all(color: Hud.cyan.withValues(alpha: 0.4)),
                boxShadow: [BoxShadow(color: Hud.cyan.withValues(alpha: 0.18), blurRadius: 24)],
              ),
              child: Icon(icon, size: 28, color: Hud.cyan),
            ),
            const SizedBox(height: 16),
            Text(context.tr(title), textAlign: TextAlign.center, style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w700, color: Hud.text)),
            if (subtitle != null) ...[
              const SizedBox(height: 6),
              Text(context.tr(subtitle!), textAlign: TextAlign.center, style: const TextStyle(fontSize: 13, color: Hud.dim, height: 1.4)),
            ],
            if (actionLabel != null && onAction != null) ...[
              const SizedBox(height: 16),
              OutlinedButton(onPressed: onAction, child: Text(context.tr(actionLabel!))),
            ],
          ]),
        ),
      );
}
