import 'package:dio/dio.dart';
import 'package:ar_society_app/core/api/api_client.dart';

/// One line of a tenants import, as the server read it.
class TenantImportOutcome {
  final int? line;
  final String status; // created | skipped | error
  final String? message;
  TenantImportOutcome.fromJson(Map<String, dynamic> j)
      : line = j['line'] as int?,
        status = j['status'] as String,
        message = j['message'] as String?;
}

class TenantImportApi {
  final Dio _dio;
  TenantImportApi({Dio? dio}) : _dio = dio ?? ApiClient.instance;

  /// Rows are maps of the server's import fields (all text); `dryRun` checks them and writes nothing.
  Future<List<TenantImportOutcome>> importRows(List<Map<String, dynamic>> rows, {required bool dryRun}) async {
    // Each tenant is made through the same code as the Add Tenant form, so a big file takes a while.
    final r = await _dio.post('/tenants/import',
        data: {'rows': rows, 'dry_run': dryRun}, options: Options(receiveTimeout: const Duration(minutes: 3)));
    return [for (final o in r.data as List) TenantImportOutcome.fromJson(o as Map<String, dynamic>)];
  }
}
