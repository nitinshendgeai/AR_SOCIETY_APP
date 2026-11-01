import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';

/// What the server says about push notifications: whether it can send them at all (the Firebase key is set), and
/// how many phones and browsers are registered to receive them.
class PushStatus {
  final bool enabled;
  final int devices;
  final int myDevices;
  final Map<String, int> platforms;
  const PushStatus({required this.enabled, required this.devices, required this.myDevices, required this.platforms});

  factory PushStatus.fromJson(Map<String, dynamic> j) => PushStatus(
        enabled: j['enabled'] as bool? ?? false,
        devices: j['devices'] as int? ?? 0,
        myDevices: j['my_devices'] as int? ?? 0,
        platforms: {for (final e in (j['platforms'] as Map? ?? {}).entries) '${e.key}': (e.value as num).toInt()},
      );
}

final pushStatusProvider = FutureProvider.autoDispose<PushStatus>((ref) async {
  final r = await ApiClient.instance.get('/notifications/push-status');
  return PushStatus.fromJson(Map<String, dynamic>.from(r.data as Map));
});

/// Shown in Society Settings: is push on, how many devices, and a button that sends a test to this person's own devices.
class PushStatusCard extends ConsumerStatefulWidget {
  const PushStatusCard({super.key});

  @override
  ConsumerState<PushStatusCard> createState() => _PushStatusCardState();
}

class _PushStatusCardState extends ConsumerState<PushStatusCard> {
  bool _testing = false;

  Future<void> _test() async {
    setState(() => _testing = true);
    try {
      final r = await ApiClient.instance.post('/notifications/push-test');
      final data = Map<String, dynamic>.from(r.data as Map);
      if (!mounted) return;
      if (data['enabled'] != true) {
        AppToast.warning(context, 'Push is off on the server: the Firebase key is not set');
      } else if ((data['sent'] as int? ?? 0) == 0) {
        AppToast.warning(context, 'No device of yours is registered. Sign in on your phone and allow notifications');
      } else {
        final n = data['sent'] as int;
        AppToast.success(context, 'Test sent to $n device${n == 1 ? '' : 's'}');
      }
      ref.invalidate(pushStatusProvider);
    } catch (e) {
      if (mounted) showErrorToast(context, e);
    } finally {
      if (mounted) setState(() => _testing = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final status = ref.watch(pushStatusProvider);
    return Container(
      key: const ValueKey('push-status-card'),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: AppTheme.cardBg,
        borderRadius: BorderRadius.circular(AppTheme.radiusS),
        border: Border.all(color: AppTheme.border),
      ),
      child: status.when(
        loading: () => const LinearProgressIndicator(),
        error: (e, _) => Text(friendlyErrorMessage(e), style: const TextStyle(color: AppTheme.error)),
        data: (s) {
          final on = s.enabled;
          final devices = s.platforms.entries.map((e) => '${e.value} ${e.key}').join(', ');
          return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Row(children: [
              Icon(on ? Icons.notifications_active_rounded : Icons.notifications_off_rounded,
                  size: 20, color: on ? AppTheme.success : AppTheme.warning),
              const SizedBox(width: 10),
              Expanded(
                child: Text(on ? 'Push notifications are on' : 'Push notifications are off',
                    style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w700)),
              ),
            ]),
            const SizedBox(height: 6),
            Text(
              on
                  ? 'A visitor at the gate rings the resident\'s phone, even when the app is closed.'
                  : 'The server has no Firebase key (FIREBASE_SERVICE_ACCOUNT_JSON), so nothing is pushed. '
                      'Residents still see waiting visitors in the app, refreshed every 15 seconds.',
              style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary, height: 1.4),
            ),
            const SizedBox(height: 8),
            Text(
              s.devices == 0
                  ? 'No phone or browser is registered yet.'
                  : '${s.devices} registered device${s.devices == 1 ? '' : 's'} ($devices) · '
                      '${s.myDevices} ${s.myDevices == 1 ? 'is' : 'are'} yours',
              style: const TextStyle(fontSize: 13),
            ),
            const SizedBox(height: 10),
            OutlinedButton.icon(
              key: const ValueKey('push-test'),
              onPressed: _testing ? null : _test,
              icon: _testing
                  ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2))
                  : const Icon(Icons.send_rounded, size: 18),
              label: const Text('Send a test to my devices'),
            ),
          ]);
        },
      ),
    );
  }
}
