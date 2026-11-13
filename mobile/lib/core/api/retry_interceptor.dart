import 'package:dio/dio.dart';
import 'package:ar_society_app/core/api/connection_status.dart';

/// Runs a request that only reads (GET) again when the network let it down, so a brief drop or a server that is just
/// waking up does not show the person an error.
///
/// Only GET, and only when nothing was received or the server said it was briefly unavailable (502, 503, 504).
/// Never a POST, PUT, PATCH or DELETE: repeating a payment, a check-in or a booking is not safe. Never a 4xx or a 500,
/// which a second try would not change.
///
/// Also keeps [ConnectionStatus] up to date.
class RetryInterceptor extends Interceptor {
  final Dio _dio;
  final int maxRetries;
  final Duration baseDelay;

  RetryInterceptor(this._dio, {this.maxRetries = 2, this.baseDelay = const Duration(milliseconds: 600)});

  /// Set `extra: {RetryInterceptor.skip: true}` on a request to try it exactly once.
  static const skip = 'no_retry';
  static const _attemptKey = 'retry_attempt';

  /// A failure that means nothing answered, as opposed to the server answering with an error.
  static bool isNetworkFailure(DioException e) =>
      e.response == null &&
      (e.type == DioExceptionType.connectionTimeout ||
          e.type == DioExceptionType.sendTimeout ||
          e.type == DioExceptionType.receiveTimeout ||
          e.type == DioExceptionType.connectionError);

  static bool _retryable(DioException e) {
    if (e.requestOptions.method.toUpperCase() != 'GET') return false;
    if (e.requestOptions.extra[skip] == true) return false;
    if (isNetworkFailure(e)) return true;
    final code = e.response?.statusCode;
    return code == 502 || code == 503 || code == 504;
  }

  @override
  void onResponse(Response response, ResponseInterceptorHandler handler) {
    ConnectionStatus.reachable.value = true;
    handler.next(response);
  }

  @override
  Future<void> onError(DioException err, ErrorInterceptorHandler handler) async {
    if (err.response != null) ConnectionStatus.reachable.value = true;     // the server answered, so we are connected
    if (_retryable(err)) {
      final attempt = (err.requestOptions.extra[_attemptKey] as int?) ?? 0;
      if (attempt < maxRetries) {
        await Future<void>.delayed(baseDelay * (1 << attempt));
        final options = err.requestOptions..extra[_attemptKey] = attempt + 1;
        try {
          return handler.resolve(await _dio.fetch<dynamic>(options));
        } on DioException catch (e) {
          return handler.next(e);
        }
      }
    }
    if (isNetworkFailure(err)) ConnectionStatus.reachable.value = false;
    handler.next(err);
  }
}
