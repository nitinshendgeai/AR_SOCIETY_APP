import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';

/// A temporary password for the admin to hand over — tap to copy. Shown
/// once, when a user is created or their password is reset; the user must
/// change it at first login.
Future<void> showTempPasswordDialog(BuildContext context, String pwd, {String? who}) {
  return showDialog(
    context: context,
    barrierDismissible: false,
    builder: (ctx) => AlertDialog(
      title: const Text('Temporary Password'),
      content: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Share this with ${who ?? 'the user'}. They must change it on login.',
              style: const TextStyle(fontSize: 13, color: AppTheme.textSecondary)),
          const SizedBox(height: 12),
          GestureDetector(
            onTap: () {
              Clipboard.setData(ClipboardData(text: pwd));
              ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(content: Text('Copied to clipboard')),
              );
            },
            child: Container(
              width: double.infinity,
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: AppTheme.surface,
                borderRadius: BorderRadius.circular(8),
                border: Border.all(color: AppTheme.border),
              ),
              child: Row(
                children: [
                  Expanded(
                    child: SelectableText(pwd,
                        style: const TextStyle(fontFamily: 'monospace', fontWeight: FontWeight.w700, fontSize: 16)),
                  ),
                  const Icon(Icons.copy_rounded, size: 16, color: AppTheme.primary),
                ],
              ),
            ),
          ),
          const SizedBox(height: 10),
          const Text('It is shown only now. If it is lost, reset the password from the user\'s page.',
              style: TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
        ],
      ),
      actions: [
        ElevatedButton(
          onPressed: () => Navigator.pop(ctx),
          child: const Text('Done'),
        ),
      ],
    ),
  );
}
