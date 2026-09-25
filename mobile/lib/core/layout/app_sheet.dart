import 'package:flutter/material.dart';
import 'package:ar_society_app/core/layout/app_shell.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';

/// Opens a form/detail sheet the way the current screen size expects:
/// a bottom sheet on phones, and on desktop widths a full-height side panel
/// sliding in from the right (the web ERP pattern for create/edit forms —
/// the list stays visible behind it, Esc or a click outside closes it).
///
/// Drop-in for `showModalBottomSheet(isScrollControlled: true,
/// backgroundColor: Colors.transparent, ...)`: the same [builder] is used
/// in both cases and `Navigator.pop(context, result)` returns [T] either way.
Future<T?> showAppSheet<T>({
  required BuildContext context,
  required WidgetBuilder builder,
  double panelWidth = 520,
  BoxConstraints? constraints,
}) {
  if (!isDesktopLayout(context)) {
    return showModalBottomSheet<T>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      constraints: constraints,
      builder: builder,
    );
  }

  return showGeneralDialog<T>(
    context: context,
    barrierDismissible: true,
    barrierLabel: MaterialLocalizations.of(context).modalBarrierDismissLabel,
    barrierColor: Colors.black.withOpacity(0.32),
    transitionDuration: const Duration(milliseconds: 220),
    pageBuilder: (ctx, _, __) => Align(
      alignment: Alignment.centerRight,
      child: SizedBox(
        width: panelWidth,
        height: double.infinity,
        child: Material(
          color: AppTheme.cardBg,
          elevation: 16,
          shadowColor: Colors.black26,
          child: Stack(children: [
            // The sheet bodies size themselves to their content and pin to
            // the bottom on phones; in a panel they read top-down.
            Positioned.fill(
              child: Align(alignment: Alignment.topCenter, child: Builder(builder: builder)),
            ),
            Positioned(
              top: 10,
              right: 10,
              child: IconButton(
                tooltip: 'Close',
                icon: const Icon(Icons.close_rounded, size: 20),
                onPressed: () => Navigator.of(ctx).maybePop(),
              ),
            ),
          ]),
        ),
      ),
    ),
    transitionBuilder: (_, animation, __, child) => SlideTransition(
      position: Tween(begin: const Offset(1, 0), end: Offset.zero)
          .animate(CurvedAnimation(parent: animation, curve: Curves.easeOutCubic)),
      child: child,
    ),
  );
}
