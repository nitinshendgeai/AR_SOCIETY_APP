import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:ar_society_app/core/motion/motion.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';

/// A page or section is loading. The spinner fades in after a beat, so a quick answer shows no flash of
/// spinner at all, and a slow one says so: after [patience] it adds a line telling the person it is still working
/// (the server may be waking up) instead of leaving them guessing.
class AppLoader extends StatefulWidget {
  final String? label;
  final Duration patience;
  final bool compact;

  const AppLoader(
      {super.key,
      this.label,
      this.patience = const Duration(seconds: 6),
      this.compact = false});

  @override
  State<AppLoader> createState() => _AppLoaderState();
}

class _AppLoaderState extends State<AppLoader>
    with SingleTickerProviderStateMixin {
  // One controller covers both the short fade-in and the long wait, so there is no timer to leak.
  static const _fadeIn = Duration(milliseconds: 350);
  late final AnimationController _c =
      AnimationController(vsync: this, duration: widget.patience + _fadeIn)
        ..forward();

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final total = _c.duration!.inMilliseconds;
    final fadeEnd = _fadeIn.inMilliseconds / total;
    final waitStart = widget.patience.inMilliseconds / total;
    return Semantics(
      label: widget.label ?? 'Loading',
      liveRegion: true,
      child: Center(
        child: AnimatedBuilder(
          animation: _c,
          builder: (context, _) {
            final reduced = AppMotion.reduced(context);
            // First 150ms nothing shows; then the spinner eases in.
            final show = reduced
                ? 1.0
                : Interval(0.4 * fadeEnd, fadeEnd, curve: Curves.easeOut)
                    .transform(_c.value);
            final slow = reduced
                ? 0.0
                : Interval(waitStart, math.min(1.0, waitStart + fadeEnd),
                        curve: Curves.easeOut)
                    .transform(_c.value);
            return Opacity(
              opacity: show,
              child: Padding(
                padding: EdgeInsets.all(widget.compact ? 12 : 32),
                child: Column(mainAxisSize: MainAxisSize.min, children: [
                  SizedBox(
                    width: widget.compact ? 22 : 32,
                    height: widget.compact ? 22 : 32,
                    child: const CircularProgressIndicator(),
                  ),
                  if (widget.label != null) ...[
                    const SizedBox(height: 14),
                    Text(widget.label!,
                        style: const TextStyle(
                            fontSize: 13.5, color: AppTheme.textSecondary)),
                  ],
                  if (!widget.compact)
                    Opacity(
                      opacity: slow,
                      child: const Padding(
                        padding: EdgeInsets.only(top: 10),
                        child: Text(
                            'Still working… the server may be waking up',
                            style: TextStyle(
                                fontSize: 12.5, color: AppTheme.textTertiary)),
                      ),
                    ),
                ]),
              ),
            );
          },
        ),
      ),
    );
  }
}

/// A soft light moving across its child: the standard "this is coming" cue for placeholder shapes.
class Shimmer extends StatefulWidget {
  final Widget child;
  const Shimmer({super.key, required this.child});

  @override
  State<Shimmer> createState() => _ShimmerState();
}

class _ShimmerState extends State<Shimmer> with SingleTickerProviderStateMixin {
  late final AnimationController _c = AnimationController(
      vsync: this, duration: const Duration(milliseconds: 1400));

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (AppMotion.reduced(context)) {
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
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _c,
      child: widget.child,
      builder: (context, child) => ShaderMask(
        blendMode: BlendMode.srcATop,
        shaderCallback: (rect) {
          final t = _c.value;
          return LinearGradient(
            begin: Alignment(-1.5 + 3 * t, -0.3),
            end: Alignment(-0.5 + 3 * t, 0.3),
            colors: const [
              Color(0xFFE9EBF0),
              Color(0xFFF7F8FA),
              Color(0xFFE9EBF0)
            ],
            stops: const [0.25, 0.5, 0.75],
          ).createShader(rect);
        },
        child: child,
      ),
    );
  }
}

/// A grey rounded block that stands in for a line of text, a number or an avatar while data loads.
class SkeletonBox extends StatelessWidget {
  final double? width;
  final double height;
  final double radius;
  const SkeletonBox({super.key, this.width, this.height = 14, this.radius = 6});

  @override
  Widget build(BuildContext context) => Container(
        width: width,
        height: height,
        decoration: BoxDecoration(
            color: const Color(0xFFE9EBF0),
            borderRadius: BorderRadius.circular(radius)),
      );
}

/// Placeholder rows shaped like the list that is about to appear (an avatar, two lines of text, a trailing
/// figure), shimmering until the real rows arrive.
class SkeletonList extends StatelessWidget {
  final int count;
  final EdgeInsetsGeometry padding;
  const SkeletonList(
      {super.key, this.count = 6, this.padding = const EdgeInsets.all(16)});

  @override
  Widget build(BuildContext context) {
    return Semantics(
      label: 'Loading',
      liveRegion: true,
      child: Shimmer(
        child: ListView.separated(
          padding: padding,
          physics: const NeverScrollableScrollPhysics(),
          itemCount: count,
          separatorBuilder: (_, __) => const SizedBox(height: 12),
          itemBuilder: (_, i) => Container(
            padding: const EdgeInsets.all(14),
            decoration: BoxDecoration(
              color: AppTheme.cardBg,
              borderRadius: BorderRadius.circular(AppTheme.radiusL),
              border: Border.all(color: AppTheme.border),
            ),
            child: Row(children: [
              const SkeletonBox(width: 40, height: 40, radius: 20),
              const SizedBox(width: 14),
              Expanded(
                child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      SkeletonBox(width: 120.0 + (i % 3) * 40, height: 14),
                      const SizedBox(height: 8),
                      SkeletonBox(width: 80.0 + (i % 2) * 60, height: 11),
                    ]),
              ),
              const SizedBox(width: 12),
              const SkeletonBox(width: 56, height: 14),
            ]),
          ),
        ),
      ),
    );
  }
}
