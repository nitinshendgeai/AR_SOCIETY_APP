// The browser side of a visitor alert: the ring, and hearing about a visitor while the tab is in the background.
// A browser has no native ring like the Android app's notification channel, so the open page plays the ring itself.
export 'web_ring_stub.dart' if (dart.library.js_interop) 'web_ring_web.dart';
