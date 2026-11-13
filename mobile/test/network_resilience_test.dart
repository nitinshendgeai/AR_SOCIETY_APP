import 'dart:typed_data';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ar_society_app/core/api/connection_status.dart';
import 'package:ar_society_app/core/api/retry_interceptor.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/shared/widgets/connection_banner.dart';

/// Answers each call from [script] in turn (the last step repeats): an int is an HTTP status, a
/// [DioExceptionType] is a failure where nothing answered.
class _Scripted implements HttpClientAdapter {
  final List<Object> script;
  final methods = <String>[];
  _Scripted(this.script);
  int get calls => methods.length;

  @override
  Future<ResponseBody> fetch(RequestOptions options, Stream<Uint8List>? requestStream, Future<void>? cancelFuture) async {
    final step = script[methods.length < script.length ? methods.length : script.length - 1];
    methods.add(options.method);
    if (step is DioExceptionType) throw DioException(requestOptions: options, type: step, message: 'scripted');
    return ResponseBody.fromString('{}', step as int, headers: {
      Headers.contentTypeHeader: ['application/json'],
    });
  }

  @override
  void close({bool force = false}) {}
}

Dio _dio(_Scripted adapter, {int maxRetries = 2}) {
  final dio = Dio()..httpClientAdapter = adapter;
  dio.interceptors.add(RetryInterceptor(dio, maxRetries: maxRetries, baseDelay: Duration.zero));
  return dio;
}

void main() {
  setUp(() => ConnectionStatus.reachable.value = true);

  group('RetryInterceptor', () {
    test('a read that fails twice for lack of network succeeds on the third try', () async {
      final a = _Scripted([DioExceptionType.connectionError, DioExceptionType.connectionTimeout, 200]);
      final r = await _dio(a).get('/x');
      expect(r.statusCode, 200);
      expect(a.calls, 3);
      expect(ConnectionStatus.reachable.value, isTrue);
    });

    test('a timeout while waiting for the answer is retried too', () async {
      final a = _Scripted([DioExceptionType.receiveTimeout, 200]);
      expect((await _dio(a).get('/x')).statusCode, 200);
      expect(a.calls, 2);
    });

    test('a briefly unavailable server (503) is retried', () async {
      final a = _Scripted([503, 200]);
      expect((await _dio(a).get('/x')).statusCode, 200);
      expect(a.calls, 2);
    });

    test('502 and 504 are retried as well', () async {
      for (final code in [502, 504]) {
        final a = _Scripted([code, 200]);
        expect((await _dio(a).get('/x')).statusCode, 200, reason: '$code');
      }
    });

    test('it gives up after the retries, tells the caller, and marks the server unreachable', () async {
      final a = _Scripted([DioExceptionType.connectionError]);
      await expectLater(_dio(a).get('/x'), throwsA(isA<DioException>().having((e) => e.type, 'type', DioExceptionType.connectionError)));
      expect(a.calls, 3);                                   // the first try and two retries
      expect(ConnectionStatus.reachable.value, isFalse);
    });

    test('a 404 is not retried, and it proves the server is reachable', () async {
      ConnectionStatus.reachable.value = false;
      final a = _Scripted([404]);
      await expectLater(_dio(a).get('/x'), throwsA(isA<DioException>()));
      expect(a.calls, 1);
      expect(ConnectionStatus.reachable.value, isTrue);
    });

    test('a 500 and a 403 are not retried', () async {
      for (final code in [500, 403, 422]) {
        final a = _Scripted([code]);
        await expectLater(_dio(a).get('/x'), throwsA(isA<DioException>()), reason: '$code');
        expect(a.calls, 1, reason: '$code');
      }
    });

    test('a write is never retried: a payment or check-in must not be repeated', () async {
      for (final method in ['POST', 'PUT', 'PATCH', 'DELETE']) {
        final a = _Scripted([DioExceptionType.connectionError, 200]);
        await expectLater(_dio(a).request('/x', options: Options(method: method)), throwsA(isA<DioException>()), reason: method);
        expect(a.calls, 1, reason: method);
        expect(a.methods, [method]);
      }
    });

    test('a write that got a 503 is not retried either', () async {
      final a = _Scripted([503, 200]);
      await expectLater(_dio(a).post('/x'), throwsA(isA<DioException>()));
      expect(a.calls, 1);
    });

    test('a request can opt out of retrying', () async {
      final a = _Scripted([DioExceptionType.connectionError, 200]);
      await expectLater(
          _dio(a).get('/x', options: Options(extra: {RetryInterceptor.skip: true})), throwsA(isA<DioException>()));
      expect(a.calls, 1);
      expect(ConnectionStatus.reachable.value, isFalse);
    });

    test('a successful answer clears the unreachable flag', () async {
      ConnectionStatus.reachable.value = false;
      await _dio(_Scripted([200])).get('/x');
      expect(ConnectionStatus.reachable.value, isTrue);
    });

    test('a cancelled request does not mark the server unreachable', () async {
      final a = _Scripted([DioExceptionType.cancel]);
      await expectLater(_dio(a).get('/x'), throwsA(isA<DioException>()));
      expect(a.calls, 1);
      expect(ConnectionStatus.reachable.value, isTrue);
    });
  });

  group('ConnectionBanner', () {
    Widget app({Future<void> Function()? probe}) =>
        MaterialApp(theme: AppTheme.lightTheme, home: Scaffold(body: Column(children: [ConnectionBanner(probe: probe)])));

    testWidgets('is invisible while the server is reachable', (t) async {
      await t.pumpWidget(app());
      expect(find.textContaining('Cannot reach the server'), findsNothing);
    });

    testWidgets('appears when the server cannot be reached and disappears when it can again', (t) async {
      await t.pumpWidget(app());
      ConnectionStatus.reachable.value = false;
      await t.pump();
      expect(find.text('Cannot reach the server. Check your internet connection.'), findsOneWidget);
      ConnectionStatus.reachable.value = true;
      await t.pump();
      expect(find.textContaining('Cannot reach the server'), findsNothing);
    });

    testWidgets('Retry checks the server right away', (t) async {
      var probes = 0;
      await t.pumpWidget(app(probe: () async {
        probes++;
        ConnectionStatus.reachable.value = true;
      }));
      ConnectionStatus.reachable.value = false;
      await t.pump();
      await t.tap(find.text('Retry'));
      await t.pump();
      expect(probes, 1);
      expect(find.textContaining('Cannot reach the server'), findsNothing);
    });
  });
}
