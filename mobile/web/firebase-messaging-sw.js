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

// A visitor at the gate (an "urgent" push) while the app's tab is open but in the background: the browser shows its
// own notification, which cannot ring, so also tell the open page, which plays the ring itself. A visible tab hears
// about it from the Firebase SDK, and a closed browser has no page to ring (the notification stays up until answered).
self.addEventListener('push', (event) => {
  let payload = {};
  try { payload = event.data ? event.data.json() : {}; } catch (e) { return; }
  const data = payload.data || {};
  if (data.urgent !== '1') return;
  const note = payload.notification || {};
  event.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((clients) => {
      clients.filter((c) => c.visibilityState !== 'visible').forEach((c) => c.postMessage({
        source: 'dux-push', title: note.title, body: note.body, route: data.route,
      }));
    })
  );
});
