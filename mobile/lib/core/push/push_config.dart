import 'package:firebase_core/firebase_core.dart';
import 'package:flutter/foundation.dart';

/// Firebase project settings for push notifications (Firebase project
/// `society-app-186ff`). These identify the app to Firebase and aren't
/// secret — every browser that opens the site receives them — so they're
/// built in. A build can still override any of them with
/// `--dart-define=FIREBASE_…=…` (e.g. to point a test build at another
/// project). The secret half, the service-account key the backend sends
/// with, lives only in the backend's FIREBASE_SERVICE_ACCOUNT_JSON.
/// See docs/PUSH_NOTIFICATIONS.md.
class PushConfig {
  static String get apiKey => _or(const String.fromEnvironment('FIREBASE_API_KEY'),
      'AIzaSyCf0OCzzQ95vw-OtQa2m-KO_2DnJv8wjh8');
  static String get projectId => _or(const String.fromEnvironment('FIREBASE_PROJECT_ID'),
      'society-app-186ff');
  static String get messagingSenderId => _or(const String.fromEnvironment('FIREBASE_MESSAGING_SENDER_ID'),
      '666567205264');
  static String get webAppId => _or(const String.fromEnvironment('FIREBASE_WEB_APP_ID'),
      '1:666567205264:web:f36b3aa4c22329cb129315');
  /// Not registered yet: the Android app needs a Firebase app for package
  /// `com.arsociety.app`; until its id is added here (or passed with
  /// --dart-define) push stays off in the Android build.
  static String get androidAppId => _or(const String.fromEnvironment('FIREBASE_ANDROID_APP_ID'), '');
  /// Web push certificate key (Cloud Messaging → Web configuration).
  static String get vapidKey => _or(const String.fromEnvironment('FIREBASE_VAPID_KEY'),
      'BB1lhX-nQXM73kd9_FSal99Blt_YtsRFInQ49GT-qoR-4mCaqj0cymidC1Qx8EhPd2dCrN52DAAJumM1CcX0xLA');

  // A --dart-define left empty (the Dockerfile passes its build variables
  // through even when unset) means "use the built-in value".
  static String _or(String defined, String builtIn) => defined.isEmpty ? builtIn : defined;

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
