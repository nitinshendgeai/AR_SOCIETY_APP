import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ar_society_app/features/vendor/data/datasources/vendor_remote_datasource.dart';

Map<String, dynamic> _vendor(int n) => {
      'id': 'v$n',
      'society_id': 's1',
      'vendor_code': 'V$n',
      'company_name': 'Vendor $n',
      'mobile': '9876543210',
      'category': 'housekeeping',
    };

void main() {
  test('every page of the vendor list is read, not just the first 50', () async {
    final asked = <List<int>>[];
    final dio = Dio();
    dio.interceptors.add(InterceptorsWrapper(onRequest: (options, handler) {
      final skip = options.queryParameters['skip'] as int;
      final limit = options.queryParameters['limit'] as int;
      asked.add([skip, limit]);
      const total = 1120;
      final rows = [for (var n = skip; n < total && n < skip + limit; n++) _vendor(n)];
      handler.resolve(Response(requestOptions: options, statusCode: 200, data: rows));
    }));

    final vendors = await VendorRemoteDataSource(dio: dio).listVendors('s1');

    expect(vendors.length, 1120);
    expect(vendors.first.companyName, 'Vendor 0');
    expect(vendors.last.companyName, 'Vendor 1119');
    expect(asked, [[0, 500], [500, 500], [1000, 500]]);       // stops at the short page
  });

  test('a short list is one request', () async {
    var requests = 0;
    final dio = Dio();
    dio.interceptors.add(InterceptorsWrapper(onRequest: (options, handler) {
      requests++;
      handler.resolve(Response(requestOptions: options, statusCode: 200, data: [_vendor(1), _vendor(2)]));
    }));

    final vendors = await VendorRemoteDataSource(dio: dio).listVendors('s1');
    expect(vendors.length, 2);
    expect(requests, 1);
  });
}
