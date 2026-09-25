import 'package:firebase_core/firebase_core.dart';
import 'package:flutter/foundation.dart';

/// Firebase project settings for push notifications, passed at build time:
///
///   flutter build web --dart-define=FIREBASE_API_KEY=… \
///     --dart-define=FIREBASE_PROJECT_ID=… --dart-define=FIREBASE_MESSAGING_SENDER_ID=… \
///     --dart-define=FIREBASE_WEB_APP_ID=… --dart-define=FIREBASE_VAPID_KEY=…
///
/// (Android builds pass FIREBASE_ANDROID_APP_ID instead of the web app id and
/// VAPID key.) The values come from the Firebase console — see
/// docs/PUSH_NOTIFICATIONS.md. Without them push stays off and the app works
/// as before.
class PushConfig {
  static const apiKey            = String.fromEnvironment('FIREBASE_API_KEY');
  static const projectId         = String.fromEnvironment('FIREBASE_PROJECT_ID');
  static const messagingSenderId = String.fromEnvironment('FIREBASE_MESSAGING_SENDER_ID');
  static const webAppId          = String.fromEnvironment('FIREBASE_WEB_APP_ID');
  static const androidAppId      = String.fromEnvironment('FIREBASE_ANDROID_APP_ID');
  /// Web push certificate key (Cloud Messaging → Web configuration).
  static const vapidKey          = String.fromEnvironment('FIREBASE_VAPID_KEY');

  static bool get _android => !kIsWeb && defaultTargetPlatform == TargetPlatform.android;

  static String get appId => kIsWeb ? webAppId : androidAppId;

  static String get platform => kIsWeb ? 'web' : 'android';

  static bool get isConfigured =>
      (kIsWeb || _android) &&
      apiKey.isNotEmpty &&
      projectId.isNotEmpty &&
      messagingSenderId.isNotEmpty &&
      appId.isNotEmpty &&
      (!kIsWeb || vapidKey.isNotEmpty);

  static FirebaseOptions get options => FirebaseOptions(
        apiKey: apiKey,
        appId: appId,
        messagingSenderId: messagingSenderId,
        projectId: projectId,
        authDomain: kIsWeb ? '$projectId.firebaseapp.com' : null,
      );
}
