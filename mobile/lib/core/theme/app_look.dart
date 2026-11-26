import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:ar_society_app/core/l10n/app_locale.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';

/// Which look the app wears — the everyday light one or the dark sci-fi "Command deck" — chosen by each user and
/// remembered on the device.
const _prefsKey = 'app_look';

/// Reads the saved look and makes it current. Called once before the app starts, so the first frame is right.
Future<void> loadSavedLook() async {
  try {
    final v = (await SharedPreferences.getInstance()).getString(_prefsKey);
    AppTheme.look = v == AppLook.deck.name ? AppLook.deck : AppLook.light;
  } catch (_) {
    AppTheme.look = AppLook.light;
  }
}

class AppLookNotifier extends Notifier<AppLook> {
  @override
  AppLook build() => AppTheme.look;

  /// Switches the look and redraws every screen in place: colours are read while widgets build, so the whole tree is
  /// marked to rebuild (state such as half-filled forms and the open page is kept).
  Future<void> set(AppLook look) async {
    if (look == AppTheme.look) return;
    AppTheme.look = look;
    state = look;
    WidgetsBinding.instance.addPostFrameCallback((_) => rebuildAllWidgets());
    try {
      await (await SharedPreferences.getInstance()).setString(_prefsKey, look.name);
    } catch (_) {
      // Not remembered on this device (storage unavailable); it still applies until the app is closed.
    }
  }
}

final appLookProvider = NotifierProvider<AppLookNotifier, AppLook>(AppLookNotifier.new);

/// Marks every element in the app to build again.
void rebuildAllWidgets() {
  void mark(Element e) {
    e.markNeedsBuild();
    e.visitChildren(mark);
  }

  WidgetsBinding.instance.rootElement?.visitChildren(mark);
}

/// A dialog to choose the look. The choice is remembered on this device.
Future<void> showLookPicker(BuildContext context, WidgetRef ref) {
  final current = ref.read(appLookProvider);
  Widget option(BuildContext ctx, AppLook look, IconData icon, String title, String subtitle) => ListTile(
        leading: Icon(look == current ? Icons.radio_button_checked_rounded : Icons.radio_button_off_rounded,
            color: look == current ? AppTheme.primary : AppTheme.textSecondary),
        title: Row(children: [Icon(icon, size: 18, color: AppTheme.textSecondary), const SizedBox(width: 8), Text(ctx.tr(title))]),
        subtitle: Text(ctx.tr(subtitle)),
        onTap: () {
          Navigator.pop(ctx);
          ref.read(appLookProvider.notifier).set(look);
        },
      );
  return showDialog<void>(
    context: context,
    builder: (ctx) => SimpleDialog(
      title: Text(ctx.tr('Appearance')),
      children: [
        option(ctx, AppLook.light, Icons.light_mode_outlined, 'Light', 'Clean and bright; best in daylight'),
        option(ctx, AppLook.deck, Icons.auto_awesome_outlined, 'Command deck', 'Dark sci-fi look with neon accents'),
      ],
    ),
  );
}

/// The Command deck's backdrop behind every page; nothing in the light look.
class AppBackdrop extends StatelessWidget {
  final Widget child;
  const AppBackdrop({super.key, required this.child});
  @override
  Widget build(BuildContext context) => AppTheme.isDeck
      ? ColoredBox(
          color: const Color(0xFF03050C),
          child: Stack(fit: StackFit.expand, children: [const Positioned.fill(child: HudBackdrop()), child]),
        )
      : child;
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
          colors: [Color(0xFF060A1A), _void0, Color(0xFF050817)],
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
    glow(Offset(w * 0.85, h * 0.05), math.max(w, h) * 0.55, _violet.withValues(alpha: 0.16));
    glow(Offset(w * 0.1, h * 0.3), math.max(w, h) * 0.45, _cyan.withValues(alpha: 0.09));

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
      ..color = _cyan.withValues(alpha: 0.07);
    final vanish = Offset(w / 2, horizon);
    for (var i = -14; i <= 14; i++) {
      canvas.drawLine(vanish, Offset(w / 2 + i * w * 0.12, h), grid);
    }
    final drift = t.value; // rows slide toward the viewer
    for (var k = 0; k < 12; k++) {
      final p = (k + drift) / 12;
      final y = horizon + (h - horizon) * p * p;
      grid.color = _cyan.withValues(alpha: 0.02 + 0.09 * p);
      canvas.drawLine(Offset(0, y), Offset(w, y), grid);
    }
    canvas.drawRect(
      Rect.fromLTWH(0, horizon - 40, w, 80),
      Paint()
        ..shader = LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          colors: [_cyan.withValues(alpha: 0), _cyan.withValues(alpha: 0.06), _cyan.withValues(alpha: 0)],
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
          colors: [_cyan.withValues(alpha: 0), _cyan.withValues(alpha: 0.035)],
        ).createShader(Rect.fromLTWH(0, sy - 60, w, 60)),
    );
  }

  @override
  bool shouldRepaint(_BackdropPainter old) => false;
}


const Color _cyan = Color(0xFF22D3EE);
const Color _violet = Color(0xFF8B5CF6);
const Color _void0 = Color(0xFF03050C);
