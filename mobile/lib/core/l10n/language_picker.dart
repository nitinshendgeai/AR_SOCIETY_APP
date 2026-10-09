import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/l10n/app_locale.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';

/// A small dialog to choose English, हिन्दी or मराठी. The choice is remembered on this device.
Future<void> showLanguagePicker(BuildContext context, WidgetRef ref) {
  final current = ref.read(localeProvider).languageCode;
  return showDialog<void>(
    context: context,
    builder: (ctx) => SimpleDialog(
      title: Text(ctx.tr('Language')),
      children: [
        for (final e in kLanguageNames.entries)
          ListTile(
            leading: Icon(
                e.key == current
                    ? Icons.radio_button_checked_rounded
                    : Icons.radio_button_off_rounded,
                color: e.key == current
                    ? AppTheme.primary
                    : AppTheme.textSecondary),
            title: Text(e.value,
                style: const TextStyle(fontFamilyFallback: [kDevanagariFont])),
            onTap: () {
              ref.read(localeProvider.notifier).set(e.key);
              Navigator.pop(ctx);
            },
          ),
      ],
    ),
  );
}
