// Shows push notifications (a visitor at the gate…) while the app's tab is
// closed or in the background. Firebase Messaging registers this file itself
// when the app asks for a push token. Keep the SDK version in step with
// firebase_core_web's supportedFirebaseJsSdkVersion.
importScripts('https://www.gstatic.com/firebasejs/12.19.0/firebase-app-compat.js');
importScripts('https://www.gstatic.com/firebasejs/12.19.0/firebase-messaging-compat.js');
// Sets self.FIREBASE_CONFIG; the Docker build writes the real values.
importScripts('firebase-config.js');

if (self.FIREBASE_CONFIG) {
  firebase.initializeApp(self.FIREBASE_CONFIG);
  // Notification messages are displayed by the SDK; a click opens the
  // message's link (the app screen the backend set).
  firebase.messaging();
}
