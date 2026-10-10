import 'dart:math' as math;

import 'package:flutter/material.dart';

/// One set of timings and curves for every animation in the app, so a hover, a press, a page change and a loader
/// feel like the same product. People who ask their device for less motion get none of it ([AppMotion.reduced]).
class AppMotion {
  AppMotion._();

  static const fast = Duration(milliseconds: 120);
  static const base = Duration(milliseconds: 200);
  static const slow = Duration(milliseconds: 320);
  static const curve = Curves.easeOutCubic;

  /// True when the device asks for reduced motion (or animations are turned off).
  static bool reduced(BuildContext context) =>
      MediaQuery.maybeDisableAnimationsOf(context) ?? false;
}

/// Gives whatever it wraps a small lift when the pointer is over it and a press when it is clicked or tapped.
/// It listens to raw pointer events, so it never takes a tap away from the button inside it.
class PressableScale extends StatefulWidget {
  final Widget child;
  final bool enabled;
  final double hoverScale;
  final double pressScale;

  const PressableScale({
    super.key,
    required this.child,
    this.enabled = true,
    this.hoverScale = 1.015,
    this.pressScale = 0.97,
  });

  @override
  State<PressableScale> createState() => _PressableScaleState();
}

class _PressableScaleState extends State<PressableScale> {
  bool _hover = false;
  bool _down = false;

  @override
  Widget build(BuildContext context) {
    if (!widget.enabled || AppMotion.reduced(context)) return widget.child;
    final scale =
        _down ? widget.pressScale : (_hover ? widget.hoverScale : 1.0);
    return MouseRegion(
      onEnter: (_) => setState(() => _hover = true),
      onExit: (_) => setState(() => _hover = false),
      child: Listener(
        behavior: HitTestBehavior.translucent,
        onPointerDown: (_) => setState(() => _down = true),
        onPointerUp: (_) => setState(() => _down = false),
        onPointerCancel: (_) => setState(() => _down = false),
        child: AnimatedScale(
          scale: scale,
          duration: _down ? AppMotion.fast : AppMotion.base,
          curve: AppMotion.curve,
          child: widget.child,
        ),
      ),
    );
  }
}

/// Fades its child in and lifts it a few pixels the first time it appears. Give list items and dashboard cards
/// their [index] and they arrive one after another instead of all at once.
class AppReveal extends StatefulWidget {
  final Widget child;
  final int index;
  const AppReveal({super.key, required this.child, this.index = 0});

  @override
  State<AppReveal> createState() => _AppRevealState();
}

class _AppRevealState extends State<AppReveal>
    with SingleTickerProviderStateMixin {
  static const _stagger = 45; // ms between neighbours
  static const _run = 280; // ms for one item
  late final int _lead = math.min(widget.index, 8) * _stagger;
  late final AnimationController _c = AnimationController(
      vsync: this, duration: Duration(milliseconds: _lead + _run))
    ..forward();

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    if (AppMotion.reduced(context)) return widget.child;
    final t = CurvedAnimation(
      parent: _c,
      curve: Interval(_lead / (_lead + _run), 1, curve: AppMotion.curve),
    );
    return FadeTransition(
      opacity: t,
      child: AnimatedBuilder(
        animation: t,
        child: widget.child,
        builder: (context, child) => Transform.translate(
            offset: Offset(0, 10 * (1 - t.value)), child: child),
      ),
    );
  }
}

/// Page change: the new page fades in while rising a few pixels; the old one fades slightly. Used for every route
/// on every platform, replacing the stock slide/zoom that feels like a phone app inside a browser.
class AppPageTransitions extends PageTransitionsBuilder {
  const AppPageTransitions();

  @override
  Widget buildTransitions<T>(
      PageRoute<T> route,
      BuildContext context,
      Animation<double> animation,
      Animation<double> secondaryAnimation,
      Widget child) {
    if (AppMotion.reduced(context)) return child;
    final enter = CurvedAnimation(
        parent: animation,
        curve: Curves.easeOutCubic,
        reverseCurve: Curves.easeInCubic);
    final leave =
        CurvedAnimation(parent: secondaryAnimation, curve: Curves.easeInOut);
    return FadeTransition(
      opacity: Tween<double>(begin: 1, end: 0.92).animate(leave),
      child: FadeTransition(
        opacity: enter,
        child: SlideTransition(
          position:
              Tween<Offset>(begin: const Offset(0, 0.012), end: Offset.zero)
                  .animate(enter),
          child: child,
        ),
      ),
    );
  }
}
