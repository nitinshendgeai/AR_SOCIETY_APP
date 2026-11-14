import 'dart:typed_data';
import 'package:dio/dio.dart';
import 'package:ar_society_app/core/api/api_client.dart';

/// The printed Tenants report: the same filters as the list on screen, no paging, as a PDF.
class TenantReportApi {
  final Dio _dio;
  TenantReportApi({Dio? dio}) : _dio = dio ?? ApiClient.instance;

  /// Null filters are left out, so the server applies no filter for them (and its default, current tenants, for
  /// [isActive] when it is true).
  Future<Uint8List> pdf({
    bool? isActive,
    String? search,
    String? flatId,
    String? wingId,
    bool? movedIn,
    String? agreement,
    String? police,
    bool? kycVerified,
  }) async {
    final r = await _dio.get<List<int>>(
      '/tenants/report.pdf',
      queryParameters: {
        if (isActive != null) 'is_active': isActive,
        if (search != null && search.isNotEmpty) 'search': search,
        if (flatId != null) 'flat_id': flatId,
        if (wingId != null) 'wing_id': wingId,
        if (movedIn != null) 'moved_in': movedIn,
        if (agreement != null) 'agreement': agreement,
        if (police != null) 'police': police,
        if (kycVerified != null) 'kyc_verified': kycVerified,
      },
      options: Options(responseType: ResponseType.bytes, receiveTimeout: const Duration(minutes: 2)),
    );
    return Uint8List.fromList(r.data!);
  }
}
