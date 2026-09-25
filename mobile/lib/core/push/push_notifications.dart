import 'dart:async';

import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/foundation.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/push/push_config.dart';

/// Push notifications through Firebase Cloud Messaging.
///
/// After sign-in the app asks for notification permission, gets this
/// device's FCM token and registers it with the backend
/// (POST /notifications/devices), which then pushes the user's alerts — a
/// visitor at the gate, a guard hearing the resident's decision — to it.
/// Tapping a notification opens the screen named in its `route` data.
/// Sign-out unregisters the device. Everything is a no-op when Firebase
/// isn't configured ([PushConfig.isConfigured]) or the user declines.
class PushNotifications {
  PushNotifications._();
  static final instance = PushNotifications._();

  Future<bool>? _ready;
  String? _token;
  final _subscriptions = <StreamSubscription<dynamic>>[];

  /// Starts Firebase in the background — call from main() without awaiting.
  /// On the web, Firebase loads its SDK from gstatic.com; if that's blocked
  /// (an ad blocker, an office network) the load can hang, so the app never
  /// waits on it and push simply stays off.
  void initialize() {
    if (!PushConfig.isConfigured) return;
    _ready = Firebase.initializeApp(options: PushConfig.options)
        .then((_) => true)
        .timeout(const Duration(seconds: 20))
        .catchError((Object e) {
      debugPrint('[push] Firebase unavailable: $e');
      return false;
    });
  }

  Future<bool> get _isReady => _ready ?? Future.value(false);

  /// After sign-in. [openRoute] navigates to a notification's screen;
  /// [onForegroundMessage] runs when one arrives while the app is open
  /// (the OS doesn't show it then, so the app refreshes what's on screen).
  Future<void> register({
    required void Function(String route) openRoute,
    required void Function(RemoteMessage message) onForegroundMessage,
  }) async {
    if (!await _isReady) return;
    try {
      final messaging = FirebaseMessaging.instance;
      final permission = await messaging.requestPermission();
      if (permission.authorizationStatus == AuthorizationStatus.denied) return;

      final token = await messaging.getToken(vapidKey: kIsWeb ? PushConfig.vapidKey : null);
      if (token == null) return;
      await _save(token);

      _cancelSubscriptions();
      _subscriptions
        ..add(messaging.onTokenRefresh.listen(_save))
        ..add(FirebaseMessaging.onMessage.listen(onForegroundMessage))
        ..add(FirebaseMessaging.onMessageOpenedApp.listen((m) => _open(m, openRoute)));

      // The app was launched by tapping a notification.
      final initial = await messaging.getInitialMessage();
      if (initial != null) _open(initial, openRoute);
    } catch (e) {
      debugPrint('[push] registration failed: $e');
    }
  }

  /// Before sign-out, while the session can still call the API.
  Future<void> unregister() async {
    _cancelSubscriptions();
    final token = _token;
    if (token == null || !await _isReady) return;
    _token = null;
    try {
      await ApiClient.instance.post('/notifications/devices/unregister', data: {'token': token});
      await FirebaseMessaging.instance.deleteToken();
    } catch (e) {
      debugPrint('[push] unregister failed: $e');
    }
  }

  Future<void> _save(String token) async {
    await ApiClient.instance.post('/notifications/devices',
        data: {'token': token, 'platform': PushConfig.platform});
    _token = token;
  }

  void _open(RemoteMessage message, void Function(String route) openRoute) {
    final route = message.data['route'];
    if (route is String && route.startsWith('/')) openRoute(route);
  }

  void _cancelSubscriptions() {
    for (final s in _subscriptions) {
      s.cancel();
    }
    _subscriptions.clear();
  }
}
