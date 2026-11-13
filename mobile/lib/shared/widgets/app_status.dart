import 'package:flutter/material.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/core/theme/design_tokens.dart';

/// A small pill that says where something stands ("Paid", "Overdue", "Pending"). Colour never carries the meaning
/// alone: the label is always shown, and [icon] adds a second cue.
class AppStatusChip extends StatelessWidget {
  final String label;
  final AppTone tone;
  final IconData? icon;
  const AppStatusChip({super.key, required this.label, this.tone = AppTone.neutral, this.icon});

  @override
  Widget build(BuildContext context) {
    final c = kToneColors[tone]!;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(color: c.background, borderRadius: BorderRadius.circular(999)),
      child: Row(mainAxisSize: MainAxisSize.min, children: [
        if (icon != null) ...[Icon(icon, size: 14, color: c.foreground), const SizedBox(width: 4)],
        Flexible(
          child: Text(label,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: c.foreground)),
        ),
      ]),
    );
  }
}

/// A heading above a group of cards or rows, with an optional action on the right ("See all").
class AppSectionHeader extends StatelessWidget {
  final String title;
  final String? actionLabel;
  final VoidCallback? onAction;
  const AppSectionHeader({super.key, required this.title, this.actionLabel, this.onAction});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(AppSpacing.pageGutter, AppSpacing.l, AppSpacing.pageGutter, AppSpacing.s),
      child: Row(children: [
        Expanded(
          child: Semantics(
            header: true,
            child: Text(title, style: Theme.of(context).textTheme.titleMedium),
          ),
        ),
        if (actionLabel != null && onAction != null)
          TextButton(
            onPressed: onAction,
            style: TextButton.styleFrom(minimumSize: const Size(AppSpacing.minTouch, AppSpacing.minTouch)),
            child: Text(actionLabel!),
          ),
      ]),
    );
  }
}

/// Shown after something worked and the person needs to see it did ("Payment recorded"), with the next step.
class AppSuccessState extends StatelessWidget {
  final String title;
  final String? message;
  final String? actionLabel;
  final VoidCallback? onAction;
  const AppSuccessState({super.key, required this.title, this.message, this.actionLabel, this.onAction});

  @override
  Widget build(BuildContext context) {
    final c = kToneColors[AppTone.success]!;
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.xl),
        child: Semantics(
          liveRegion: true,
          child: Column(mainAxisSize: MainAxisSize.min, children: [
            Container(
              width: 64,
              height: 64,
              decoration: BoxDecoration(color: c.background, shape: BoxShape.circle),
              child: Icon(Icons.check_rounded, size: 36, color: c.foreground),
            ),
            const SizedBox(height: AppSpacing.l),
            Text(title, textAlign: TextAlign.center, style: Theme.of(context).textTheme.titleLarge),
            if (message != null) ...[
              const SizedBox(height: AppSpacing.s),
              Text(message!, textAlign: TextAlign.center, style: Theme.of(context).textTheme.bodySmall),
            ],
            if (actionLabel != null && onAction != null) ...[
              const SizedBox(height: AppSpacing.xl),
              FilledButton(onPressed: onAction, child: Text(actionLabel!)),
            ],
          ]),
        ),
      ),
    );
  }
}

/// A strip under the app bar for "you are offline" or "reconnecting". Pure presentation: whoever detects the state
/// decides when to show it, so this adds no dependency.
class AppConnectionBanner extends StatelessWidget {
  final String message;
  final VoidCallback? onRetry;
  const AppConnectionBanner({super.key, required this.message, this.onRetry});

  @override
  Widget build(BuildContext context) {
    final c = kToneColors[AppTone.warning]!;
    return Semantics(
      liveRegion: true,
      container: true,
      child: Material(
        color: c.background,
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: AppSpacing.pageGutter, vertical: AppSpacing.s),
          child: Row(children: [
            Icon(Icons.cloud_off_rounded, size: 18, color: c.foreground),
            const SizedBox(width: AppSpacing.s),
            Expanded(child: Text(message, style: TextStyle(fontSize: 13, color: c.foreground))),
            if (onRetry != null)
              TextButton(
                onPressed: onRetry,
                style: TextButton.styleFrom(
                    foregroundColor: c.foreground, minimumSize: const Size(AppSpacing.minTouch, AppSpacing.minTouch)),
                child: const Text('Retry'),
              ),
          ]),
        ),
      ),
    );
  }
}
