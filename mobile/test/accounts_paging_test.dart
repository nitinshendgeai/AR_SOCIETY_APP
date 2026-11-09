import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ar_society_app/features/accounts/data/accounts_api.dart';

/// A server holding [total] vouchers that returns at most `limit` per request, as the real one does.
Dio _server(int total, List<Map<String, dynamic>> asked) {
  final dio = Dio();
  dio.interceptors.add(InterceptorsWrapper(onRequest: (options, handler) {
    asked.add(Map.of(options.queryParameters));
    final skip = options.queryParameters['skip'] as int;
    final limit = options.queryParameters['limit'] as int;
    final rows = [
      for (var n = skip; n < total && n < skip + limit; n++)
        {
          'id': 'v$n',
          'voucher_type': 'payment',
          'voucher_number': 'PV-$n',
          'voucher_date': '2026-10-01',
          'amount': '10.00',
          'entries': [],
        }
    ];
    handler.resolve(Response(requestOptions: options, statusCode: 200, data: rows));
  }));
  return dio;
}

void main() {
  test('the Day Book reads every voucher, not just the first 500', () async {
    final asked = <Map<String, dynamic>>[];
    final list = await AccountsApi(dio: _server(1230, asked)).vouchers('s1', type: 'payment');
    expect(list.length, 1230);
    expect(list.last.voucherNumber, 'PV-1229');
    expect(asked.map((q) => q['skip']), [0, 500, 1000]);
    expect(asked.every((q) => q['limit'] == 500 && q['voucher_type'] == 'payment'), isTrue);
  });
}
