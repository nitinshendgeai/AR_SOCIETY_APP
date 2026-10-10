import 'package:flutter/material.dart';
import 'package:ar_society_app/core/config/env.dart';
import 'package:ar_society_app/core/l10n/app_locale.dart';
import 'package:ar_society_app/core/layout/app_shell.dart' show kDesktopBreakpoint;
import 'package:ar_society_app/core/motion/motion.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';

/// The one frame for every page shown before (or instead of) the app itself: sign in, register a society, set a
/// new password, unlock, the first-run wizard. On a computer a brand panel at the left and the form at the
/// right; on a phone the logo, the heading and the form in a card, one under the other.
///
/// [scrollable] false gives [child] the height left under the heading (a step-by-step form with its own
/// scrolling pages); true (the default) scrolls the whole page.
class AuthPage extends StatelessWidget {
  final String title;
  final String? subtitle;
  final Widget child;
  final bool scrollable;

  /// Shows a back link above the heading.
  final VoidCallback? onBack;

  /// Under the form, outside the card (a "register your society" link, say).
  final Widget? footer;
  final double maxWidth;

  /// Shown above the heading (a progress bar of steps, say).
  final Widget? top;

  const AuthPage({
    super.key,
    required this.title,
    this.subtitle,
    required this.child,
    this.scrollable = true,
    this.onBack,
    this.footer,
    this.top,
    this.maxWidth = 440,
  });

  @override
  Widget build(BuildContext context) {
    final desktop = MediaQuery.sizeOf(context).width >= kDesktopBreakpoint;
    return Scaffold(
      backgroundColor: desktop ? AppTheme.cardBg : AppTheme.surface,
      body: desktop ? _desktop(context) : _phone(context),
    );
  }

  Widget _heading(BuildContext context, {required bool centered}) {
    final align = centered ? CrossAxisAlignment.center : CrossAxisAlignment.start;
    final textAlign = centered ? TextAlign.center : TextAlign.start;
    return Column(crossAxisAlignment: align, mainAxisSize: MainAxisSize.min, children: [
      if (onBack != null)
        Align(
          alignment: Alignment.centerLeft,
          child: TextButton.icon(
            onPressed: onBack,
            icon: const Icon(Icons.arrow_back_rounded, size: 18),
            label: Text(context.tr('Back')),
            style: TextButton.styleFrom(padding: const EdgeInsets.symmetric(horizontal: 8), foregroundColor: AppTheme.textSecondary),
          ),
        ),
      if (top != null) ...[top!, const SizedBox(height: 16)],
      Text(context.tr(title),
          textAlign: textAlign,
          style: TextStyle(
              fontSize: centered ? 24 : 28,
              fontWeight: FontWeight.w700,
              height: 1.2,
              letterSpacing: -0.5,
              color: AppTheme.textPrimary)),
      if (subtitle != null) ...[
        const SizedBox(height: 6),
        Text(context.tr(subtitle!),
            textAlign: textAlign, style: const TextStyle(fontSize: 15, height: 1.4, color: AppTheme.textSecondary)),
      ],
    ]);
  }

  Widget _desktop(BuildContext context) {
    return Row(children: [
      const Expanded(flex: 5, child: _BrandPanel()),
      Expanded(
        flex: 4,
        child: SafeArea(
          child: Center(
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 48, vertical: 24),
              child: ConstrainedBox(
                constraints: BoxConstraints(maxWidth: maxWidth),
                child: scrollable
                    ? SingleChildScrollView(child: _desktopColumn(context, bounded: false))
                    : _desktopColumn(context, bounded: true),
              ),
            ),
          ),
        ),
      ),
    ]);
  }

  Widget _desktopColumn(BuildContext context, {required bool bounded}) {
    final body = bounded ? Expanded(child: child) : child;
    return Column(
      mainAxisSize: bounded ? MainAxisSize.max : MainAxisSize.min,
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        if (bounded) const SizedBox(height: 24),
        AppReveal(index: 0, child: _heading(context, centered: false)),
        const SizedBox(height: 28),
        if (bounded) body else AppReveal(index: 1, child: body),
        if (footer != null) ...[const SizedBox(height: 20), footer!],
      ],
    );
  }

  Widget _phone(BuildContext context) {
    final card = Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: AppTheme.cardBg,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppTheme.border),
      ),
      child: child,
    );
    final head = Column(mainAxisSize: MainAxisSize.min, children: [
      ClipRRect(
        borderRadius: BorderRadius.circular(18),
        child: Image.asset('assets/branding/duxos_logo.png', width: 72, height: 72, fit: BoxFit.cover),
      ),
      const SizedBox(height: 16),
      _heading(context, centered: true),
      const SizedBox(height: 24),
    ]);
    return SafeArea(
      child: Center(
        child: ConstrainedBox(
          constraints: BoxConstraints(maxWidth: maxWidth + 40),
          child: scrollable
              ? SingleChildScrollView(
                  padding: const EdgeInsets.fromLTRB(20, 32, 20, 32),
                  child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
                    head,
                    card,
                    if (footer != null) ...[const SizedBox(height: 20), footer!],
                  ]),
                )
              : Padding(
                  padding: const EdgeInsets.fromLTRB(20, 16, 20, 16),
                  child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
                    if (onBack != null || top != null) _heading(context, centered: true) else head,
                    const SizedBox(height: 12),
                    Expanded(child: child),
                    if (footer != null) ...[const SizedBox(height: 12), footer!],
                  ]),
                ),
        ),
      ),
    );
  }
}

/// The left side of [AuthPage] on a computer: the product and what it does.
class _BrandPanel extends StatelessWidget {
  const _BrandPanel();

  static const _points = [
    (Icons.receipt_long_rounded, 'Maintenance bills, receipts and accounts'),
    (Icons.door_front_door_rounded, 'Visitors, parking and gate in one register'),
    (Icons.campaign_rounded, 'Notices, meetings and polls for every member'),
  ];

  @override
  Widget build(BuildContext context) {
    return DecoratedBox(
      decoration: const BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [AppTheme.primary, AppTheme.primaryDark, Color(0xFF00348F)],
        ),
      ),
      child: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(56),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, mainAxisAlignment: MainAxisAlignment.center, children: [
            ClipRRect(
              borderRadius: BorderRadius.circular(18),
              child: Image.asset('assets/branding/duxos_logo.png', width: 68, height: 68, fit: BoxFit.cover),
            ),
            const SizedBox(height: 28),
            Text(Env.appName,
                style: const TextStyle(fontSize: 36, fontWeight: FontWeight.w800, letterSpacing: -0.5, color: Colors.white)),
            const SizedBox(height: 10),
            Text(context.tr('Everything your society runs on, in one place.'),
                style: TextStyle(fontSize: 18, height: 1.4, color: Colors.white.withOpacity(0.88))),
            const SizedBox(height: 40),
            for (final p in _points) ...[
              Row(children: [
                Container(
                  width: 40,
                  height: 40,
                  decoration: BoxDecoration(color: Colors.white.withOpacity(0.16), borderRadius: BorderRadius.circular(10)),
                  child: Icon(p.$1, size: 20, color: Colors.white),
                ),
                const SizedBox(width: 14),
                Expanded(child: Text(context.tr(p.$2), style: TextStyle(fontSize: 15, color: Colors.white.withOpacity(0.92)))),
              ]),
              const SizedBox(height: 18),
            ],
          ]),
        ),
      ),
    );
  }
}
