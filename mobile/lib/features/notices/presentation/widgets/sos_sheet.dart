import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/api/api_client.dart' show friendlyErrorMessage;
import 'package:ar_society_app/core/layout/app_sheet.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/notices/data/notices_api.dart';
import 'package:ar_society_app/features/notices/presentation/providers/notices_providers.dart';

/// What an SOS can be about, in the order a person under stress needs them.
const kSosTypes = <(String, String, IconData)>[
  ('medical', 'Medical', Icons.medical_services_rounded),
  ('fire', 'Fire', Icons.local_fire_department_rounded),
  ('security_threat', 'Security', Icons.shield_rounded),
  ('other', 'Other', Icons.warning_amber_rounded),
];

/// The resident's panic button sheet: pick what is wrong, send; then it says help has been told and offers "I am safe".
Future<void> showSosSheet(BuildContext context) => showAppSheet<void>(
      context: context,
      builder: (_) => const SafeArea(child: SosSheet()),
    );

class SosSheet extends ConsumerStatefulWidget {
  const SosSheet({super.key});

  @override
  ConsumerState<SosSheet> createState() => _SosSheetState();
}

class _SosSheetState extends ConsumerState<SosSheet> {
  String _type = 'medical';
  final _note = TextEditingController();
  bool _busy = false;
  String? _error;
  EmergencyAlertItem? _sent;

  @override
  void dispose() {
    _note.dispose();
    super.dispose();
  }

  Future<void> _send() async {
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final alert = await ref.read(noticesApiProvider).raiseSos(type: _type, description: _note.text.trim());
      if (mounted) setState(() => _sent = alert);
    } catch (e) {
      if (mounted) setState(() => _error = friendlyErrorMessage(e));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _cancel() async {
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await ref.read(noticesApiProvider).cancelSos(_sent!.id);
      if (!mounted) return;
      Navigator.of(context).pop();
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('SOS ended. Glad you are safe')));
    } catch (e) {
      if (mounted) setState(() => _error = friendlyErrorMessage(e));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final sent = _sent;
    return Padding(
      padding: EdgeInsets.fromLTRB(20, 8, 20, 20 + MediaQuery.viewInsetsOf(context).bottom),
      child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        if (sent == null) ...[
          const Text('Send an SOS', style: TextStyle(fontSize: 20, fontWeight: FontWeight.w800)),
          const SizedBox(height: 4),
          const Text('Security and the committee are told at once, with your flat. Your neighbours are not.',
              style: TextStyle(fontSize: 13, color: AppTheme.textSecondary)),
          const SizedBox(height: 14),
          Wrap(spacing: 8, runSpacing: 8, children: [
            for (final t in kSosTypes)
              ChoiceChip(
                avatar: Icon(t.$3, size: 18, color: _type == t.$1 ? Colors.white : AppTheme.error),
                label: Text(t.$2),
                selected: _type == t.$1,
                selectedColor: AppTheme.error,
                labelStyle: TextStyle(color: _type == t.$1 ? Colors.white : AppTheme.textPrimary, fontWeight: FontWeight.w600),
                showCheckmark: false,
                onSelected: _busy ? null : (_) => setState(() => _type = t.$1),
              ),
          ]),
          const SizedBox(height: 12),
          TextField(
            controller: _note,
            maxLines: 2,
            maxLength: 200,
            decoration: const InputDecoration(hintText: 'Anything they should know (optional)'),
          ),
          if (_error != null) Text(_error!, style: const TextStyle(color: AppTheme.error, fontSize: 13)),
          const SizedBox(height: 8),
          ElevatedButton.icon(
            key: const Key('sos-send'),
            style: ElevatedButton.styleFrom(backgroundColor: AppTheme.error, minimumSize: const Size.fromHeight(52)),
            onPressed: _busy ? null : _send,
            icon: const Icon(Icons.sos_rounded),
            label: Text(_busy ? 'Sending…' : 'Send SOS'),
          ),
        ] else ...[
          const Icon(Icons.check_circle_rounded, color: AppTheme.success, size: 44),
          const SizedBox(height: 8),
          const Text('Help has been told',
              textAlign: TextAlign.center, style: TextStyle(fontSize: 20, fontWeight: FontWeight.w800)),
          const SizedBox(height: 6),
          Text(
            [
              'Security and the committee have your SOS${sent.location != null ? ' from ${sent.location}' : ''}.',
              if (sent.reached != null) '${sent.reached} people notified.',
              'Stay where you are if you can.',
            ].join(' '),
            textAlign: TextAlign.center,
            style: const TextStyle(fontSize: 13, color: AppTheme.textSecondary, height: 1.4),
          ),
          if (_error != null) Text(_error!, textAlign: TextAlign.center, style: const TextStyle(color: AppTheme.error, fontSize: 13)),
          const SizedBox(height: 14),
          OutlinedButton(
            key: const Key('sos-cancel'),
            onPressed: _busy ? null : _cancel,
            child: const Text('I am safe, end the SOS'),
          ),
          TextButton(onPressed: () => Navigator.of(context).pop(), child: const Text('Close')),
        ],
      ]),
    );
  }
}
