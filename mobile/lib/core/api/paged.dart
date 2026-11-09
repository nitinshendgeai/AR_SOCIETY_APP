import 'package:dio/dio.dart';

/// Every row of a list the server cuts into pages (`skip` and `limit`), read page after page until a short one.
///
/// Reading only the first page left a society with more than the default 50 rows showing the newest 50, with counts
/// and totals that were too small. [pageSize] must be a value the endpoint allows (its `le=` limit).
Future<List<Map<String, dynamic>>> getAllPages(
  Dio dio,
  String path, {
  Map<String, dynamic> query = const {},
  int pageSize = 200,
  int maxPages = 50,
}) async {
  final rows = <Map<String, dynamic>>[];
  for (var page = 0; page < maxPages; page++) {
    final r = await dio.get(path, queryParameters: {...query, 'skip': page * pageSize, 'limit': pageSize});
    final got = (r.data as List).map((e) => e as Map<String, dynamic>).toList();
    rows.addAll(got);
    if (got.length < pageSize) break;
  }
  return rows;
}
