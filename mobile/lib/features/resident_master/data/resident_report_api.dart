import 'dart:typed_data';
import 'package:dio/dio.dart';
import 'package:ar_society_app/core/api/api_client.dart';

/// One column the Residents report can show.
class ReportColumn {
  final String key, label;
  final bool isDefault, sensitive;
  const ReportColumn({required this.key, required this.label, required this.isDefault, required this.sensitive});

  factory ReportColumn.fromJson(Map<String, dynamic> j) => ReportColumn(
        key: j['key'] as String,
        label: j['label'] as String,
        isDefault: j['default'] as bool? ?? false,
        sensitive: j['sensitive'] as bool? ?? false,
      );
}

/// The Residents report: the columns it can show, and the report itself for the same filters as the list on screen, no
/// paging, as a PDF or an Excel file.
class ResidentReportApi {
  final Dio _dio;
  ResidentReportApi({Dio? dio}) : _dio = dio ?? ApiClient.instance;

  Future<List<ReportColumn>> columns() async => [
        for (final c in (await _dio.get('/residents/report-columns')).data as List)
          ReportColumn.fromJson(Map<String, dynamic>.from(c as Map))
      ];

  /// [format] is 'pdf' or 'xlsx'. Null filters are left out, so the server applies none for them.
  Future<Uint8List> file({
    required String format,
    required List<String> columns,
    bool? isActive,
    String? search,
    String? flatId,
    String? wingId,
    bool? movedIn,
  }) async {
    final r = await _dio.get<List<int>>(
      '/residents/report',
      queryParameters: {
        'format': format,
        'columns': columns.join(','),
        if (isActive != null) 'is_active': isActive,
        if (search != null && search.isNotEmpty) 'search': search,
        if (flatId != null) 'flat_id': flatId,
        if (wingId != null) 'wing_id': wingId,
        if (movedIn != null) 'moved_in': movedIn,
      },
      options: Options(responseType: ResponseType.bytes, receiveTimeout: const Duration(minutes: 2)),
    );
    return Uint8List.fromList(r.data!);
  }
}
