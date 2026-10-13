import 'package:flutter/foundation.dart';

/// Starts the app over with every provider fresh (same stored sign-in). Used after switching society, so nothing
/// from the previous society (lists, counts, selections) is left on screen.
class AppReset {
  AppReset._();

  static final ValueNotifier<int> epoch = ValueNotifier<int>(0);

  static void restart() => epoch.value++;
}
