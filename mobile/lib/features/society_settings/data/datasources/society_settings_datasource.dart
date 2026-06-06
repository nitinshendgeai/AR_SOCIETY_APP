import 'package:dio/dio.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/features/society_settings/data/models/society_settings_model.dart';

class SocietySettingsDataSource {
  final Dio _dio;
  SocietySettingsDataSource({Dio? dio}) : _dio = dio ?? ApiClient.instance;

  Future<SocietySettingsModel> getSociety(String id) async {
    final r = await _dio.get('/societies/$id');
    return SocietySettingsModel.fromJson(r.data as Map<String, dynamic>);
  }

  Future<SocietySettingsModel> updateSociety(
      String id, Map<String, dynamic> data) async {
    final r = await _dio.patch('/societies/$id', data: data);
    return SocietySettingsModel.fromJson(r.data as Map<String, dynamic>);
  }
}
