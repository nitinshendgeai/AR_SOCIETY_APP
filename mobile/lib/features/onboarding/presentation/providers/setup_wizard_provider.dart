import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/api/api_client.dart';

class SocietyDetails {
  final String id;
  final String name;
  final String? address;
  final String? city;
  final String? state;
  final String? pincode;
  final String? contactEmail;
  final String? contactPhone;

  const SocietyDetails({
    required this.id,
    required this.name,
    this.address,
    this.city,
    this.state,
    this.pincode,
    this.contactEmail,
    this.contactPhone,
  });

  factory SocietyDetails.fromJson(Map<String, dynamic> json) => SocietyDetails(
        id: json['id'] as String,
        name: json['name'] as String,
        address: json['address'] as String?,
        city: json['city'] as String?,
        state: json['state'] as String?,
        pincode: json['pincode'] as String?,
        contactEmail: json['contact_email'] as String?,
        contactPhone: json['contact_phone'] as String?,
      );
}

final societyDetailsProvider =
    FutureProvider.autoDispose.family<SocietyDetails, String>((ref, societyId) async {
  final response = await ApiClient.instance.get('/societies/$societyId');
  return SocietyDetails.fromJson(response.data as Map<String, dynamic>);
});
