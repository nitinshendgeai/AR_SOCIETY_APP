import 'package:flutter/material.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';

/// Asks before something entered by mistake is removed. True when the person confirms.
///
/// A removed record is taken off its lists, not erased (see the server's `core/removal.py`), and the server refuses while
/// something still depends on it; its reason is shown to the person as it is.
Future<bool> confirmRemove(
  BuildContext context, {
  required String title,
  required String message,
  String action = 'Remove',
}) async {
  final ok = await showDialog<bool>(
    context: context,
    builder: (dialogContext) => AlertDialog(
      title: Text(title),
      content: Text(message),
      actions: [
        TextButton(onPressed: () => Navigator.pop(dialogContext, false), child: const Text('Keep it')),
        FilledButton(
          style: FilledButton.styleFrom(backgroundColor: AppTheme.error),
          onPressed: () => Navigator.pop(dialogContext, true),
          child: Text(action),
        ),
      ],
    ),
  );
  return ok == true;
}

/// The red "Remove ..." button at the foot of an edit form.
class RemoveButton extends StatelessWidget {
  final String label;
  final VoidCallback? onPressed;
  const RemoveButton({super.key, required this.label, required this.onPressed});

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.only(top: 8),
        child: TextButton.icon(
          onPressed: onPressed,
          icon: const Icon(Icons.delete_outline_rounded, size: 18),
          label: Text(label),
          style: TextButton.styleFrom(foregroundColor: AppTheme.error),
        ),
      );
}
