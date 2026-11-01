import 'dart:js_interop';

import 'package:web/web.dart' as web;

web.HTMLAudioElement? _audio;
bool _unlockHooked = false;
bool _listening = false;

web.HTMLAudioElement _ring() {
  return _audio ??= (web.HTMLAudioElement()
    ..src = 'visitor_ring.wav' // web/visitor_ring.wav, next to index.html (the <base href> makes it relative)
    ..preload = 'auto');
}

/// Browsers only let a page play sound after the person has touched it. So the first tap or key press after sign-in
/// plays the ring silently once; from then on the page may ring by itself when a visitor arrives.
void unlockWebAudio() {
  if (_unlockHooked) return;
  _unlockHooked = true;
  void unlock(web.Event _) {
    final audio = _ring();
    audio.muted = true;
    audio.play().toDart.then((_) {
      audio.pause();
      audio.currentTime = 0;
      audio.muted = false;
    }, onError: (Object _) {
      audio.muted = false;
    });
  }

  final options = web.AddEventListenerOptions(once: true);
  web.window.addEventListener('pointerdown', unlock.toJS, options);
  web.window.addEventListener('keydown', unlock.toJS, options);
}

Future<void> playWebRing() async {
  try {
    final audio = _ring();
    audio.muted = false;
    audio.currentTime = 0;
    await audio.play().toDart;
  } catch (_) {
    // The browser has not been allowed to play sound yet (no tap on the page): the on-screen alert still shows.
  }
}

void stopWebRing() {
  final audio = _audio;
  if (audio == null) return;
  audio.pause();
  audio.currentTime = 0;
}

/// A visitor push that arrives while this tab is open but in the background: the browser shows its own
/// notification, and the service worker (web/firebase-messaging-sw.js) also tells the page, so the page can ring.
void listenForBackgroundUrgent(void Function(String title, String body, String? route) onUrgent) {
  if (_listening) return;
  _listening = true;
  try {
    web.window.navigator.serviceWorker.addEventListener(
      'message',
      ((web.MessageEvent event) {
        final data = event.data.dartify();
        if (data is! Map || data['source'] != 'dux-push') return;
        final route = data['route'];
        onUrgent('${data['title'] ?? 'Visitor at the gate'}', '${data['body'] ?? ''}', route is String ? route : null);
      }).toJS,
    );
  } catch (_) {
    // No service worker here (an insecure page): background tabs just get the browser's notification.
  }
}
