import 'package:flutter/material.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';

/// [tint] at [opacity] laid over the white card colour, as one solid colour. A see-through fill on a box with a
/// shadow lets the shadow show through it and turns the fill a muddy grey.
Color solidTint(Color tint, [double opacity = 0.08]) => Color.alphaBlend(tint.withOpacity(opacity), AppTheme.cardBg);

/// A colour with a lighter partner, for gradient icon badges and accents. Every [dark] value is also dark enough
/// for white icons to sit on at 3:1 or better.
class AppAccent {
  final Color light;
  final Color dark;
  const AppAccent(this.light, this.dark);

  LinearGradient get gradient => LinearGradient(colors: [light, dark], begin: Alignment.topLeft, end: Alignment.bottomRight);
}

/// The palette that tells services apart at a glance (instead of one blue for everything).
const List<AppAccent> kAccents = [
  AppAccent(Color(0xFF4D9BFF), Color(0xFF0057D9)), // blue
  AppAccent(Color(0xFF9B8CFF), Color(0xFF5B43D6)), // violet
  AppAccent(Color(0xFF3DD6C0), Color(0xFF0B8577)), // teal
  AppAccent(Color(0xFFFFB454), Color(0xFFC25E00)), // amber
  AppAccent(Color(0xFFFF8FB1), Color(0xFFC72A63)), // rose
  AppAccent(Color(0xFF5BD98B), Color(0xFF168A47)), // green
  AppAccent(Color(0xFF6C8CFF), Color(0xFF2B3FB8)), // indigo
  AppAccent(Color(0xFFFF8A6B), Color(0xFFC2371B)), // coral
];

/// The same label always gets the same accent, so a service keeps its colour wherever it appears.
AppAccent accentFor(String key) {
  var h = 0;
  for (final c in key.codeUnits) {
    h = (h * 31 + c) & 0x7fffffff;
  }
  return kAccents[h % kAccents.length];
}

/// A rounded square with a gradient fill and a white icon.
class AccentBadge extends StatelessWidget {
  final IconData icon;
  final AppAccent accent;
  final double size;
  const AccentBadge({super.key, required this.icon, required this.accent, this.size = 44});

  @override
  Widget build(BuildContext context) => Container(
        width: size,
        height: size,
        decoration: BoxDecoration(
          gradient: accent.gradient,
          borderRadius: BorderRadius.circular(size * 0.32),
          boxShadow: [BoxShadow(color: accent.dark.withOpacity(0.28), blurRadius: 10, offset: const Offset(0, 4))],
        ),
        child: Icon(icon, color: Colors.white, size: size * 0.5),
      );
}

/// A white card lifted off the page by a soft shadow, with ink on a transparent Material inside (a shadow above a
/// coloured Material tints it grey and hides the ink).
class PremiumSurface extends StatelessWidget {
  final Widget child;
  final VoidCallback? onTap;
  final EdgeInsetsGeometry padding;
  final double radius;
  final Color color;
  const PremiumSurface({
    super.key,
    required this.child,
    this.onTap,
    this.padding = const EdgeInsets.all(16),
    this.radius = AppTheme.radiusL,
    this.color = AppTheme.cardBg,
  });

  @override
  Widget build(BuildContext context) => Container(
        decoration: BoxDecoration(
          color: color,
          borderRadius: BorderRadius.circular(radius),
          boxShadow: AppTheme.cardShadow,
        ),
        child: Material(
          type: MaterialType.transparency,
          child: InkWell(
            onTap: onTap,
            borderRadius: BorderRadius.circular(radius),
            child: Padding(padding: padding, child: child),
          ),
        ),
      );
}

/// The deep-blue banner at the top of a home screen: gradient, soft light circles, and room for any content.
class HeroBanner extends StatelessWidget {
  final Widget child;
  const HeroBanner({super.key, required this.child});

  @override
  Widget build(BuildContext context) => Container(
        width: double.infinity,
        decoration: BoxDecoration(
          gradient: const LinearGradient(
            colors: [Color(0xFF0A2A6B), Color(0xFF0057D9), Color(0xFF2F8CFF)],
            stops: [0, 0.6, 1],
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
          ),
          borderRadius: BorderRadius.circular(AppTheme.radiusXl),
          boxShadow: [BoxShadow(color: const Color(0xFF0057D9).withOpacity(0.32), blurRadius: 24, offset: const Offset(0, 10))],
        ),
        child: ClipRRect(
          borderRadius: BorderRadius.circular(AppTheme.radiusXl),
          child: Stack(children: [
            Positioned(right: -34, top: -44, child: _disc(150, 0.10)),
            Positioned(right: 46, bottom: -52, child: _disc(104, 0.07)),
            Positioned(left: -30, bottom: -60, child: _disc(120, 0.06)),
            Padding(padding: const EdgeInsets.fromLTRB(18, 16, 18, 16), child: child),
          ]),
        ),
      );

  static Widget _disc(double d, double opacity) => IgnorePointer(
        child: Container(width: d, height: d, decoration: BoxDecoration(shape: BoxShape.circle, color: Colors.white.withOpacity(opacity))),
      );
}

/// A section title with a short accent bar, in place of a plain grey label.
class SectionHeading extends StatelessWidget {
  final String text;
  const SectionHeading(this.text, {super.key});

  @override
  Widget build(BuildContext context) => Row(children: [
        Container(
          width: 4,
          height: 16,
          decoration: BoxDecoration(color: AppTheme.primary, borderRadius: BorderRadius.circular(2)),
        ),
        const SizedBox(width: 8),
        Expanded(
          child: Text(text,
              style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w700, color: AppTheme.textPrimary, letterSpacing: -0.1)),
        ),
      ]);
}
