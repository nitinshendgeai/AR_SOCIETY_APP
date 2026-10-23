import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

/// The sound and buzz of a visitor alert. On Android it plays the same ring the notification channel uses
/// (MainActivity.kt, channel `ar_society/visitor_ring`); Flutter's own system alert sound is silent there.
/// Elsewhere it falls back to the system alert sound, and a browser tab (no sound API here) is visual only.
class VisitorRinger {
  static const _channel = MethodChannel('ar_society/visitor_ring');

  static Future<void> ring() async {
    HapticFeedback.vibrate();
    if (!kIsWeb && defaultTargetPlatform == TargetPlatform.android) {
      try {
        await _channel.invokeMethod<void>('play');
        return;
      } catch (_) {
        // no native side (a test, an old build): use the system sound below
      }
    }
    await SystemSound.play(SystemSoundType.alert);
  }

  static Future<void> stop() async {
    if (kIsWeb || defaultTargetPlatform != TargetPlatform.android) return;
    try {
      await _channel.invokeMethod<void>('stop');
    } catch (_) {}
  }
}

bool _showing = false;

/// A visitor is waiting at the gate and the app is open: the OS shows no notification for a push in that case,
/// so ring and put a blocking alert on screen. Rings now and every [ringEvery] up to [rings] times, until the
/// resident answers: **Review** opens the approvals ([onReview]); **Later** dismisses it (the visitor stays in the
/// pending list). A second visitor while an alert is up does not stack another.
Future<void> showVisitorAlert(
  BuildContext context, {
  required String title,
  required String body,
  required VoidCallback onReview,
  Duration ringEvery = const Duration(seconds: 4),
  int rings = 3,
}) async {
  if (_showing) return;
  _showing = true;
  var count = 1;
  VisitorRinger.ring();
  final timer = Timer.periodic(ringEvery, (t) {
    if (count >= rings) {
      t.cancel();
      return;
    }
    count++;
    VisitorRinger.ring();
  });
  try {
    final review = await showDialog<bool>(
      context: context,
      barrierDismissible: false,
      builder: (ctx) => AlertDialog(
        key: const Key('visitor-alert'),
        icon: const Icon(Icons.notifications_active_rounded, size: 36),
        title: Text(title),
        content: Text(body),
        actions: [
          TextButton(
            key: const Key('visitor-alert-later'),
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text('Later'),
          ),
          FilledButton(
            key: const Key('visitor-alert-review'),
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('Review'),
          ),
        ],
      ),
    );
    if (review == true) onReview();
  } finally {
    timer.cancel();
    VisitorRinger.stop();
    _showing = false;
  }
}
