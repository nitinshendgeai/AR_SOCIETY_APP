import 'package:flutter/material.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';

/// Shows the login that was just made for a staff member (their mobile number and
/// temporary password). It is the only time the password is shown.
Future<void> showStaffLoginDialog(BuildContext context, {required String name, required String message}) {
  return showDialog<void>(
    context: context,
    barrierDismissible: false,
    builder: (ctx) => AlertDialog(
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(AppTheme.radiusL)),
      title: Row(
        children: const [
          Icon(Icons.check_circle_rounded, color: AppTheme.success, size: 22),
          SizedBox(width: 8),
          Text('Login ready', style: TextStyle(fontSize: 16)),
        ],
      ),
      content: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('$name can sign in with:', style: const TextStyle(fontSize: 13, color: AppTheme.textSecondary)),
          const SizedBox(height: 12),
          SelectableText(message, style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600)),
        ],
      ),
      actions: [
        TextButton(onPressed: () => Navigator.of(ctx).pop(), child: const Text('Done')),
      ],
    ),
  );
}
