import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:share_plus/share_plus.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/visitor/domain/entities/visitor_entities.dart';

/// What to send a guest so they know what to say at the gate.
String gatePassMessage(VisitorEntity v) =>
    'Hi ${v.name}, your gate entry code is ${v.passCode}. Tell it to the security guard at the gate when you arrive.';

/// Shows the gate code of an invited guest, large, with Copy and Share. Does nothing for a visitor with no code.
Future<void> showGatePass(BuildContext context, VisitorEntity visitor) async {
  final code = visitor.passCode;
  if (code == null) return;
  await showDialog<void>(
    context: context,
    builder: (ctx) => AlertDialog(
      title: const Text('Gate code'),
      content: Column(mainAxisSize: MainAxisSize.min, children: [
        Text('For ${visitor.name}', style: const TextStyle(color: AppTheme.textSecondary)),
        const SizedBox(height: 12),
        Semantics(
          label: 'Gate code ${code.split('').join(' ')}',
          excludeSemantics: true,
          child: Text(code,
              key: const Key('gate-code'),
              style: const TextStyle(fontSize: 38, fontWeight: FontWeight.w800, letterSpacing: 6, color: AppTheme.primary)),
        ),
        const SizedBox(height: 12),
        const Text('The guest tells this code to the guard at the gate. It works once.',
            textAlign: TextAlign.center, style: TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
      ]),
      actions: [
        TextButton.icon(
          onPressed: () {
            Clipboard.setData(ClipboardData(text: code));
            ScaffoldMessenger.of(ctx).showSnackBar(const SnackBar(content: Text('Code copied')));
          },
          icon: const Icon(Icons.copy_rounded, size: 18),
          label: const Text('Copy'),
        ),
        TextButton.icon(
          onPressed: () => Share.share(gatePassMessage(visitor)),
          icon: const Icon(Icons.ios_share_rounded, size: 18),
          label: const Text('Share'),
        ),
        TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Done')),
      ],
    ),
  );
}
