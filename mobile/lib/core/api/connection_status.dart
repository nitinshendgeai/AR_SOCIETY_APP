import 'package:flutter/foundation.dart';

/// Whether the app can currently reach the server, as seen by its own requests: any answer from the server (even an
/// error) means yes; a request that fails because nothing answered (no network, timeout) means no. It needs no extra
/// library and, unlike the phone's "connected to Wi-Fi" flag, it also notices a connection that is up but goes nowhere.
class ConnectionStatus {
  ConnectionStatus._();
  static final ValueNotifier<bool> reachable = ValueNotifier<bool>(true);
}
