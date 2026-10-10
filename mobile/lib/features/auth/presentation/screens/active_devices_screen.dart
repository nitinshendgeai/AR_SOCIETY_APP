import 'package:flutter/material.dart';
import 'package:ar_society_app/core/motion/loading.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/auth/data/repositories/auth_repository.dart';
import 'package:ar_society_app/features/auth/domain/entities/device_session.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/features/staff/presentation/widgets/staff_widgets.dart' show AppCard;
import 'package:ar_society_app/shared/widgets/app_widgets.dart';

/// Account → Signed-in devices: every device that is signed in with this login, when it was last
/// used, and a way to sign any of them out — for a lost phone, or a login that is being shared.
class ActiveDevicesScreen extends ConsumerStatefulWidget {
  const ActiveDevicesScreen({super.key});

  @override
  ConsumerState<ActiveDevicesScreen> createState() => _ActiveDevicesScreenState();
}

class _ActiveDevicesScreenState extends ConsumerState<ActiveDevicesScreen> {
  bool _busy = false;

  Future<void> _run(Future<AuthResult<void>> Function() action, String done) async {
    setState(() => _busy = true);
    final result = await action();
    if (!mounted) return;
    setState(() => _busy = false);
    switch (result) {
      case AuthSuccess():
        AppToast.success(context, done);
      case AuthFailure(:final message):
        AppToast.error(context, message);
    }
    ref.invalidate(deviceSessionsProvider);
  }

  Future<void> _confirm(String title, String body, String action, Future<void> Function() go) async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(title),
        content: Text(body),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancel')),
          FilledButton(
            style: FilledButton.styleFrom(backgroundColor: AppTheme.error),
            onPressed: () => Navigator.pop(ctx, true),
            child: Text(action),
          ),
        ],
      ),
    );
    if (ok == true) await go();
  }

  @override
  Widget build(BuildContext context) {
    final sessions = ref.watch(deviceSessionsProvider);
    final repo = ref.read(authRepositoryProvider);

    return Scaffold(
      backgroundColor: AppTheme.surface,
      appBar: AppBar(
        title: const Text('Signed-in devices'),
        actions: [
          IconButton(
            tooltip: 'Refresh',
            icon: const Icon(Icons.refresh_rounded),
            onPressed: () => ref.invalidate(deviceSessionsProvider),
          ),
        ],
      ),
      body: ResponsiveBody(
        child: sessions.when(
          loading: () => const AppLoader(),
          error: (e, _) => ListView(padding: const EdgeInsets.all(20), children: [
            AppErrorBanner(message: '$e'.replaceFirst('Exception: ', '')),
          ]),
          data: (list) {
            final others = list.where((s) => !s.current).toList();
            return ListView(
              padding: const EdgeInsets.fromLTRB(16, 16, 16, 40),
              children: [
                const Text(
                  'These devices are signed in with your login. If you do not recognise one, or you '
                  'lost a phone, sign it out — it stops working at once. Changing your password also '
                  'signs out every other device.',
                  style: TextStyle(fontSize: 13, color: AppTheme.textSecondary, height: 1.4),
                ),
                const SizedBox(height: 14),
                for (final s in list) ...[
                  _DeviceTile(
                    session: s,
                    busy: _busy,
                    onSignOut: () => _confirm(
                      'Sign out ${s.device}?',
                      'That device will have to sign in again.',
                      'Sign out',
                      () => _run(() => repo.signOutDevice(s.id), 'Device signed out'),
                    ),
                  ),
                  const SizedBox(height: 10),
                ],
                if (others.isNotEmpty) ...[
                  const SizedBox(height: 6),
                  OutlinedButton.icon(
                    onPressed: _busy
                        ? null
                        : () => _confirm(
                              'Sign out all other devices?',
                              'Every device except this one will have to sign in again.',
                              'Sign out all',
                              () => _run(repo.signOutOtherDevices, 'Other devices signed out'),
                            ),
                    icon: const Icon(Icons.devices_other_rounded),
                    label: Text('Sign out ${others.length} other device${others.length == 1 ? '' : 's'}'),
                  ),
                ] else
                  const Padding(
                    padding: EdgeInsets.only(top: 6),
                    child: Text('This is the only device signed in.',
                        style: TextStyle(fontSize: 13, color: AppTheme.textSecondary)),
                  ),
              ],
            );
          },
        ),
      ),
    );
  }
}

class _DeviceTile extends StatelessWidget {
  final DeviceSession session;
  final bool busy;
  final VoidCallback onSignOut;
  const _DeviceTile({required this.session, required this.busy, required this.onSignOut});

  IconData get _icon {
    final d = session.device;
    if (d.contains('iPhone') || d.contains('Android') || d.contains('app')) return Icons.smartphone_rounded;
    if (d.contains('iPad')) return Icons.tablet_mac_rounded;
    return Icons.computer_rounded;
  }

  @override
  Widget build(BuildContext context) {
    final used = session.current ? 'Active now' : 'Last used ${sinceLabel(session.lastSeenAt ?? session.signedInAt)}';
    final where = session.ipAddress == null ? '' : ' · ${session.ipAddress}';
    return AppCard(
      child: Row(children: [
        Icon(_icon, color: session.current ? AppTheme.primary : AppTheme.textSecondary),
        const SizedBox(width: 12),
        Expanded(
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Row(children: [
              Flexible(
                child: Text(session.device,
                    style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600, color: AppTheme.textPrimary)),
              ),
              if (session.current) ...[
                const SizedBox(width: 8),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                  decoration: BoxDecoration(
                    color: AppTheme.success.withOpacity(0.12), borderRadius: BorderRadius.circular(6)),
                  child: const Text('This device',
                      style: TextStyle(fontSize: 10, fontWeight: FontWeight.w600, color: AppTheme.success)),
                ),
              ],
            ]),
            const SizedBox(height: 2),
            Text('$used$where',
                style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
          ]),
        ),
        if (!session.current)
          TextButton(onPressed: busy ? null : onSignOut, child: const Text('Sign out')),
      ]),
    );
  }
}
