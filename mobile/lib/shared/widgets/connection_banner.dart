import 'package:flutter/material.dart';
import 'package:dio/dio.dart' show Options;
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/api/connection_status.dart';
import 'package:ar_society_app/core/api/retry_interceptor.dart';
import 'package:ar_society_app/core/l10n/app_locale.dart';
import 'package:ar_society_app/shared/widgets/app_status.dart';

/// A strip across the top of every signed-in page while the server cannot be reached. It goes away by itself as soon
/// as any request is answered; Retry checks right now.
class ConnectionBanner extends StatelessWidget {
  /// Checks whether the server answers. Replaceable for tests.
  final Future<void> Function()? probe;
  const ConnectionBanner({super.key, this.probe});

  static Future<void> _defaultProbe() async {
    try {
      await ApiClient.instance.get('/health', options: Options(extra: {RetryInterceptor.skip: true}));
    } catch (_) {/* the interceptor has already recorded the outcome */}
  }

  @override
  Widget build(BuildContext context) {
    return ValueListenableBuilder<bool>(
      valueListenable: ConnectionStatus.reachable,
      builder: (context, reachable, _) {
        if (reachable) return const SizedBox.shrink();
        return AppConnectionBanner(
          message: context.tr('Cannot reach the server. Check your internet connection.'),
          onRetry: probe ?? _defaultProbe,
        );
      },
    );
  }
}
