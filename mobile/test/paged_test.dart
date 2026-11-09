import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ar_society_app/core/api/paged.dart';

Dio _server(int total, List<List<int>> asked) {
  final dio = Dio();
  dio.interceptors.add(InterceptorsWrapper(onRequest: (options, handler) {
    final skip = options.queryParameters['skip'] as int;
    final limit = options.queryParameters['limit'] as int;
    asked.add([skip, limit]);
    final rows = [for (var n = skip; n < total && n < skip + limit; n++) {'n': n}];
    handler.resolve(Response(requestOptions: options, statusCode: 200, data: rows));
  }));
  return dio;
}

void main() {
  test('reads every page until a short one', () async {
    final asked = <List<int>>[];
    final rows = await getAllPages(_server(450, asked), '/x');
    expect(rows.length, 450);
    expect(rows.last['n'], 449);
    expect(asked, [[0, 200], [200, 200], [400, 200]]);
  });

  test('a list that exactly fills the last page costs one empty request more, not an error', () async {
    final asked = <List<int>>[];
    final rows = await getAllPages(_server(400, asked), '/x');
    expect(rows.length, 400);
    expect(asked, [[0, 200], [200, 200], [400, 200]]);
  });

  test('extra query values go with every page', () async {
    Map<String, dynamic>? seen;
    final dio = Dio();
    dio.interceptors.add(InterceptorsWrapper(onRequest: (options, handler) {
      seen = options.queryParameters;
      handler.resolve(Response(requestOptions: options, statusCode: 200, data: <Map<String, dynamic>>[]));
    }));
    await getAllPages(dio, '/x', query: {'is_paid': false});
    expect(seen!['is_paid'], false);
  });
}
