import 'package:dio/dio.dart';
import 'package:logger/logger.dart';
import 'package:ar_society_app/core/config/constants.dart';
import 'package:ar_society_app/core/config/env.dart';
import 'package:ar_society_app/core/auth/token_storage.dart';

final _logger = Logger();

/// Dio HTTP client with:
/// - JWT Bearer auth injection
/// - 401 → token refresh → retry
/// - Consistent error parsing
class ApiClient {
  static late Dio _dio;

  static Dio get instance => _dio;

  static void initialize() {
    _dio = Dio(BaseOptions(
      baseUrl: Env.apiBaseUrl,
      connectTimeout: const Duration(milliseconds: AppConstants.connectTimeoutMs),
      receiveTimeout: const Duration(milliseconds: AppConstants.receiveTimeoutMs),
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      },
    ));

    _dio.interceptors.addAll([
      _AuthInterceptor(),
      if (!Env.isProduction) _LogInterceptor(),
    ]);
  }
}

/// Injects Authorization header and handles 401 → token refresh.
class _AuthInterceptor extends QueuedInterceptor {
  @override
  Future<void> onRequest(
    RequestOptions options,
    RequestInterceptorHandler handler,
  ) async {
    // Skip auth header for login/register/refresh endpoints
    final isAuthEndpoint = options.path.contains('/auth/login') ||
        options.path.contains('/auth/register') ||
        options.path.contains('/auth/refresh') ||
        options.path.contains('/public/');

    if (!isAuthEndpoint) {
      final token = await TokenStorage.getAccessToken();
      if (token != null) {
        options.headers['Authorization'] = 'Bearer $token';
      }
    }
    handler.next(options);
  }

  @override
  Future<void> onError(
    DioException err,
    ErrorInterceptorHandler handler,
  ) async {
    if (err.response?.statusCode == 401) {
      // Attempt token refresh
      final refreshed = await _tryRefreshToken();
      if (refreshed) {
        // Retry original request with new token
        final opts = err.requestOptions;
        final token = await TokenStorage.getAccessToken();
        opts.headers['Authorization'] = 'Bearer $token';
        try {
          final response = await ApiClient.instance.fetch(opts);
          return handler.resolve(response);
        } catch (_) {}
      }
      // Refresh failed — clear tokens (session expired)
      await TokenStorage.clearTokens();
    }
    handler.next(err);
  }

  Future<bool> _tryRefreshToken() async {
    try {
      final refreshToken = await TokenStorage.getRefreshToken();
      if (refreshToken == null) return false;

      final response = await ApiClient.instance.post(
        '/auth/refresh',
        data: {'refresh_token': refreshToken},
        options: Options(extra: {'skipAuth': true}),
      );

      final data = response.data as Map<String, dynamic>;
      await TokenStorage.saveTokens(
        accessToken: data['access_token'] as String,
        refreshToken: data['refresh_token'] as String,
      );
      return true;
    } catch (_) {
      return false;
    }
  }
}

/// Development request/response logger
class _LogInterceptor extends Interceptor {
  @override
  void onRequest(RequestOptions options, RequestInterceptorHandler handler) {
    _logger.d('[API] → ${options.method} ${options.uri}');
    if (options.data != null) _logger.d('[API]   body: ${options.data}');
    handler.next(options);
  }

  @override
  void onResponse(Response response, ResponseInterceptorHandler handler) {
    _logger.d('[API] ← ${response.statusCode} ${response.requestOptions.uri}');
    handler.next(response);
  }

  @override
  void onError(DioException err, ErrorInterceptorHandler handler) {
    _logger.e('[API] ✗ ${err.response?.statusCode} ${err.requestOptions.uri}: ${err.message}');
    handler.next(err);
  }
}

/// Parse Dio errors into human-readable messages.
String parseApiError(DioException e) {
  if (e.response?.data is Map) {
    final data = e.response!.data as Map<String, dynamic>;
    if (data.containsKey('detail')) return data['detail'].toString();
    if (data.containsKey('message')) return data['message'].toString();
  }
  switch (e.type) {
    case DioExceptionType.connectionTimeout:
    case DioExceptionType.receiveTimeout:
      return 'Connection timed out. Check your internet.';
    case DioExceptionType.connectionError:
      return 'Cannot connect to server. Check your internet.';
    default:
      return 'Something went wrong. Please try again.';
  }
}
