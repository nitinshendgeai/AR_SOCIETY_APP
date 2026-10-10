import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/motion/motion.dart';
import 'package:ar_society_app/shared/widgets/app_form.dart' show insideAppPage;
import 'package:ar_society_app/core/theme/app_theme.dart';

// ── Responsive body wrapper ───────────────────────────────────────────────
//
// Every Master screen was built mobile-first with a full-bleed body — fine
// on phones, but a single ListView/Form stretched across a 1440px desktop
// window reads as unfinished (fields become absurdly wide, cards stretch
// edge to edge). Rather than rewriting each screen's layout per breakpoint,
// wrap the existing body once: below [breakpoint] nothing changes; above it,
// content is centered and capped at [maxWidth] so desktop/laptop/wide-tablet
// windows get a professional reading width while phones/narrow tablets are
// completely unaffected. Uses MediaQuery rather than a hard-coded per-device
// hack, per the Master Form responsive guidelines.
class ResponsiveBody extends StatelessWidget {
  final Widget child;
  final double maxWidth;
  final double breakpoint;

  const ResponsiveBody({
    super.key,
    required this.child,
    this.maxWidth = 720,
    this.breakpoint = 840,
  });

  @override
  Widget build(BuildContext context) {
    final width = MediaQuery.sizeOf(context).width;
    // An AppPage has already put its body on the page's content width.
    if (width < breakpoint || insideAppPage(context)) return child;
    return Align(
      alignment: Alignment.topCenter,
      child: ConstrainedBox(
        constraints: BoxConstraints(maxWidth: maxWidth),
        child: child,
      ),
    );
  }
}

// ── Loading Overlay ───────────────────────────────────────────────────────────
//
// A small rounded "activity card" floating over a light scrim, rather than a
// bare spinner on a flat black wash — the native-feeling pattern (think
// UIActivityIndicatorView in a translucent capsule) instead of the generic
// Material "darken everything" loading state.

class AppLoadingOverlay extends StatelessWidget {
  final bool isLoading;
  final Widget child;

  const AppLoadingOverlay({
    super.key,
    required this.isLoading,
    required this.child,
  });

  @override
  Widget build(BuildContext context) {
    return Stack(
      children: [
        child,
        // The scrim fades in and the card eases up from slightly smaller, then both fade out when the work is
        // done, instead of the whole screen flicking dark and light.
        Positioned.fill(
          child: IgnorePointer(
            ignoring: !isLoading,
            child: AnimatedSwitcher(
              duration: AppMotion.base,
              switchInCurve: AppMotion.curve,
              transitionBuilder: (child, animation) =>
                  FadeTransition(opacity: animation, child: child),
              child: !isLoading
                  ? const SizedBox.shrink(key: ValueKey('idle'))
                  : Container(
                      key: const ValueKey('busy'),
                      color: AppTheme.textPrimary.withOpacity(0.12),
                      child: Center(
                        child: TweenAnimationBuilder<double>(
                          tween: Tween(begin: 0.9, end: 1),
                          duration: AppMotion.slow,
                          curve: Curves.easeOutBack,
                          builder: (context, scale, child) =>
                              Transform.scale(scale: scale, child: child),
                          child: Container(
                            width: 84,
                            height: 84,
                            padding: const EdgeInsets.all(20),
                            decoration: BoxDecoration(
                              color: AppTheme.cardBg,
                              borderRadius:
                                  BorderRadius.circular(AppTheme.radiusL),
                              boxShadow: AppTheme.cardShadow,
                            ),
                            child: const CircularProgressIndicator(
                                strokeWidth: 2.6),
                          ),
                        ),
                      ),
                    ),
            ),
          ),
        ),
      ],
    );
  }
}

// ── Error Banner ──────────────────────────────────────────────────────────────

class AppErrorBanner extends StatelessWidget {
  final String message;
  final VoidCallback? onDismiss;

  const AppErrorBanner({super.key, required this.message, this.onDismiss});

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.symmetric(vertical: 8),
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 13),
      decoration: BoxDecoration(
        color: AppTheme.errorSoft,
        borderRadius: BorderRadius.circular(AppTheme.radiusM),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Icon(Icons.error_outline_rounded,
              color: AppTheme.error, size: 20),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              message,
              style: const TextStyle(
                color: AppTheme.error,
                fontSize: 13.5,
                fontWeight: FontWeight.w500,
                height: 1.35,
              ),
            ),
          ),
          if (onDismiss != null)
            GestureDetector(
              onTap: onDismiss,
              child: Icon(Icons.close_rounded,
                  color: AppTheme.error.withOpacity(0.7), size: 18),
            ),
        ],
      ),
    );
  }
}

// ── Primary Button ────────────────────────────────────────────────────────────

class AppPrimaryButton extends StatelessWidget {
  final String label;
  final VoidCallback? onPressed;
  final bool isLoading;
  final IconData? icon;

  /// Full width (the phone layout) or only as wide as its label, with a sensible minimum (a form's action bar).
  final bool expand;

  const AppPrimaryButton({
    super.key,
    required this.label,
    this.onPressed,
    this.isLoading = false,
    this.icon,
    this.expand = true,
  });

  @override
  Widget build(BuildContext context) {
    // The button presses in under a finger or click; while it works the label gives way to a spinner (and back)
    // with a short cross-fade rather than jumping.
    return PressableScale(
      enabled: onPressed != null && !isLoading,
      child: SizedBox(
        width: expand ? double.infinity : null,
        height: expand ? 52 : 44,
        child: ElevatedButton(
          // The theme's phone buttons are full width; a button beside others must say how wide it is.
          style: expand ? null : ElevatedButton.styleFrom(minimumSize: const Size(150, 44)),
          onPressed: isLoading ? null : onPressed,
          child: AnimatedSwitcher(
            duration: AppMotion.base,
            switchInCurve: AppMotion.curve,
            transitionBuilder: (child, animation) => FadeTransition(
              opacity: animation,
              child: ScaleTransition(
                  scale: Tween<double>(begin: 0.85, end: 1).animate(animation),
                  child: child),
            ),
            child: isLoading
                ? const SizedBox(
                    key: ValueKey('busy'),
                    width: 22,
                    height: 22,
                    child: CircularProgressIndicator(
                      strokeWidth: 2.5,
                      color: Colors.white,
                    ),
                  )
                : Row(
                    key: const ValueKey('label'),
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      if (icon != null) ...[
                        Icon(icon, size: 20),
                        const SizedBox(width: 8),
                      ],
                      Text(label),
                    ],
                  ),
          ),
        ),
      ),
    );
  }
}

// ── Toasts ────────────────────────────────────────────────────────────────────
//
// Every screen that shows a result today hand-rolls its own
// ScaffoldMessenger.showSnackBar(SnackBar(...)) call, each free to pick its
// own color/icon/duration — the single interaction a user sees most often
// (every create/update/delete ends in one) is also the least consistent one
// in the app. AppToast is the one call site going forward: four semantic
// variants, each a colored icon + message on the theme's card background
// (not a plain dark bar), matching the soft-surface language the rest of
// AppTheme already uses for status colors.
enum _ToastKind { success, error, warning, info }

class AppToast {
  AppToast._();

  static void success(BuildContext context, String message) =>
      _show(context, message, _ToastKind.success);
  static void error(BuildContext context, String message) =>
      _show(context, message, _ToastKind.error);
  static void warning(BuildContext context, String message) =>
      _show(context, message, _ToastKind.warning);
  static void info(BuildContext context, String message) =>
      _show(context, message, _ToastKind.info);

  static void _show(BuildContext context, String message, _ToastKind kind) {
    final (color, icon) = switch (kind) {
      _ToastKind.success => (AppTheme.success, Icons.check_circle_rounded),
      _ToastKind.error => (AppTheme.error, Icons.error_rounded),
      _ToastKind.warning => (AppTheme.warning, Icons.warning_rounded),
      _ToastKind.info => (AppTheme.primary, Icons.info_rounded),
    };
    ScaffoldMessenger.of(context)
      ..hideCurrentSnackBar()
      ..showSnackBar(
        SnackBar(
          backgroundColor: AppTheme.cardBg,
          duration: const Duration(seconds: 3),
          content: Row(
            children: [
              Icon(icon, color: color, size: 20),
              const SizedBox(width: 12),
              Expanded(
                child: Text(message,
                    style: const TextStyle(
                        color: AppTheme.textPrimary, fontSize: 14, fontWeight: FontWeight.w500)),
              ),
            ],
          ),
        ),
      );
  }
}

/// Shorthand for the common "catch (e) { AppToast.error(...) }" case —
/// resolves the exception to a user-facing message the same way every
/// screen already does via [friendlyErrorMessage].
void showErrorToast(BuildContext context, Object error) =>
    AppToast.error(context, friendlyErrorMessage(error));

// ── Empty state ───────────────────────────────────────────────────────────────
//
// Most list/dashboard screens either show a blank scroll view when data is
// empty, or hand-write their own Center(child: Padding(child: Text(...)))
// — each with slightly different icon size/color/spacing. One shared,
// properly styled version for every new list screen to reach for.
class AppEmptyState extends StatelessWidget {
  final IconData icon;
  final String title;
  final String? subtitle;
  final String? actionLabel;
  final VoidCallback? onAction;

  const AppEmptyState({
    super.key,
    required this.icon,
    required this.title,
    this.subtitle,
    this.actionLabel,
    this.onAction,
  });

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 64,
              height: 64,
              decoration: BoxDecoration(
                color: AppTheme.surface,
                borderRadius: BorderRadius.circular(AppTheme.radiusL),
              ),
              child: Icon(icon, size: 30, color: AppTheme.textTertiary),
            ),
            const SizedBox(height: 16),
            Text(title,
                textAlign: TextAlign.center,
                style: const TextStyle(
                    fontSize: 15, fontWeight: FontWeight.w600, color: AppTheme.textPrimary)),
            if (subtitle != null) ...[
              const SizedBox(height: 6),
              Text(subtitle!,
                  textAlign: TextAlign.center,
                  style: const TextStyle(fontSize: 13, color: AppTheme.textSecondary, height: 1.4)),
            ],
            if (actionLabel != null && onAction != null) ...[
              const SizedBox(height: 20),
              OutlinedButton(onPressed: onAction, child: Text(actionLabel!)),
            ],
          ],
        ),
      ),
    );
  }
}

// ── KPI cards ─────────────────────────────────────────────────────────────────
//
// A stat tile for dashboard summary numbers — one shared, shadow-based
// (not bordered) version rather than each screen defining its own private
// summary-card widget with slightly different styling. Digits use
// tabular figures so a grid of these lines up cleanly even as numbers
// change width.
class KpiCard extends StatelessWidget {
  final IconData icon;
  final String label;
  final String value;
  final Color color;
  final String? note;
  final VoidCallback? onTap;

  const KpiCard({
    super.key,
    required this.icon,
    required this.label,
    required this.value,
    required this.color,
    this.note,
    this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    // Shadow sits on an outer box *behind* the white card: painted on a
    // transparent box above the Material it tinted the whole card gray.
    return PressableScale(
      enabled: onTap != null,
      child: DecoratedBox(
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(AppTheme.radiusL),
          boxShadow: AppTheme.cardShadow,
        ),
        child: Material(
          color: AppTheme.cardBg,
          borderRadius: BorderRadius.circular(AppTheme.radiusL),
          child: InkWell(
            onTap: onTap,
            borderRadius: BorderRadius.circular(AppTheme.radiusL),
            child: Padding(
              padding: const EdgeInsets.all(14),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Container(
                        width: 34,
                        height: 34,
                        decoration: BoxDecoration(
                          color: color.withOpacity(0.12),
                          borderRadius: BorderRadius.circular(10),
                        ),
                        child: Icon(icon, color: color, size: 17),
                      ),
                      const Spacer(),
                      if (onTap != null)
                        Icon(
                          Icons.chevron_right_rounded,
                          color: color.withOpacity(0.6),
                          size: 16,
                        ),
                    ],
                  ),
                  const SizedBox(height: 10),
                  Text(
                    value,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: TextStyle(
                      fontSize: 20,
                      fontWeight: FontWeight.w700,
                      color: AppTheme.textPrimary,
                      fontFeatures: const [FontFeature.tabularFigures()],
                    ),
                  ),
                  const SizedBox(height: 2),
                  Text(
                    label,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(
                      fontSize: 12,
                      color: AppTheme.textSecondary,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                  if (note != null) ...[
                    const SizedBox(height: 3),
                    Text(
                      note!,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(
                        fontSize: 11,
                        color: AppTheme.textTertiary,
                      ),
                    ),
                  ],
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

/// A responsive grid of [KpiCard]s — the standard layout for a
/// dashboard's summary row.
class KpiGrid extends StatelessWidget {
  final List<KpiCard> cards;
  const KpiGrid({super.key, required this.cards});

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(builder: (context, constraints) {
      // Phones: two tiles per row. Wider screens: up to four per row,
      // instead of two tiles stretched hundreds of pixels tall.
      final wide = constraints.maxWidth >= 600;
      final columns = wide ? (constraints.maxWidth ~/ 220).clamp(2, 4) : 2;
      return GridView(
        shrinkWrap: true,
        physics: const NeverScrollableScrollPhysics(),
        // Fixed tile height everywhere: an aspect ratio made phone tiles
        // too short for a card with a note line, which spilled below it.
        gridDelegate: SliverGridDelegateWithFixedCrossAxisCount(
            crossAxisCount: columns, mainAxisSpacing: 12, crossAxisSpacing: 12, mainAxisExtent: 136),
        children: cards,
      );
    });
  }
}

// ── Text Field ────────────────────────────────────────────────────────────────

class AppTextField extends StatelessWidget {
  final String label;
  final String? hint;
  final TextEditingController controller;
  final bool obscureText;
  final TextInputType keyboardType;
  final String? Function(String?)? validator;
  final Widget? suffixIcon;
  final Widget? prefixIcon;
  final bool autofocus;
  final TextInputAction textInputAction;
  final VoidCallback? onFieldSubmitted;
  final Iterable<String>? autofillHints;
  final FocusNode? focusNode;
  final TextCapitalization textCapitalization;

  /// Longest text the field takes (the server's limit); null for no limit.
  final int? maxLength;

  const AppTextField({
    super.key,
    required this.label,
    this.hint,
    required this.controller,
    this.obscureText = false,
    this.keyboardType = TextInputType.text,
    this.validator,
    this.suffixIcon,
    this.prefixIcon,
    this.autofocus = false,
    this.textInputAction = TextInputAction.next,
    this.onFieldSubmitted,
    this.autofillHints,
    this.focusNode,
    this.textCapitalization = TextCapitalization.none,
    this.maxLength,
  });

  @override
  Widget build(BuildContext context) {
    return TextFormField(
      controller: controller,
      focusNode: focusNode,
      textCapitalization: textCapitalization,
      inputFormatters: maxLength == null ? null : [LengthLimitingTextInputFormatter(maxLength)],
      obscureText: obscureText,
      keyboardType: keyboardType,
      validator: validator,
      autofocus: autofocus,
      textInputAction: textInputAction,
      autofillHints: autofillHints,
      onFieldSubmitted:
          onFieldSubmitted != null ? (_) => onFieldSubmitted!() : null,
      decoration: InputDecoration(
        labelText: label.isEmpty ? null : label,
        hintText: hint,
        prefixIcon: prefixIcon,
        suffixIcon: suffixIcon,
      ),
    );
  }
}
