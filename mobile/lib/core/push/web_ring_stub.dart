/// Not a browser: nothing to do (the Android app rings through its own notification channel and MainActivity).
void unlockWebAudio() {}

Future<void> playWebRing() async {}

void stopWebRing() {}

void listenForBackgroundUrgent(void Function(String title, String body, String? route) onUrgent) {}
