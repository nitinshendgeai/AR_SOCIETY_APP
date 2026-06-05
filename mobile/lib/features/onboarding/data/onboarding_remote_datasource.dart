import 'package:dio/dio.dart';
import 'package:ar_society_app/core/api/api_client.dart';

class OnboardingRemoteDataSource {
  final Dio _dio;

  OnboardingRemoteDataSource({Dio? dio}) : _dio = dio ?? ApiClient.instance;

  Future<Map<String, dynamic>> registerSociety({
    required String societyName,
    required String societyCode,
    required String contactPersonName,
    required String contactEmail,
    required String contactMobile,
    required String city,
    required String state,
    String country = 'India',
    int totalWings = 1,
    int totalFlats = 1,
  }) async {
    final response = await _dio.post('/public/register', data: {
      'society_name':         societyName,
      'society_code':         societyCode,
      'contact_person_name':  contactPersonName,
      'contact_email':        contactEmail,
      'contact_mobile':       contactMobile,
      'city':                 city,
      'state':                state,
      'country':              country,
      'total_wings':          totalWings,
      'total_flats':          totalFlats,
      'terms_accepted':       true,
    });
    return response.data as Map<String, dynamic>;
  }
}
