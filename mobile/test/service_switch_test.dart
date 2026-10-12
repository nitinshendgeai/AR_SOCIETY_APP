import 'package:flutter_test/flutter_test.dart';
import 'package:ar_society_app/features/auth/data/models/auth_models.dart';
import 'package:ar_society_app/features/platform/data/platform_api.dart';

void main() {
  Map<String, dynamic> user({Object? services}) => {
        'id': 'u1', 'email': 'a@b.com', 'full_name': 'A B', 'status': 'active',
        'society_id': 's1', 'roles': ['Resident'], 'enabled_services': services,
      };

  test('a user is limited to the services the society has switched on', () {
    final u = UserModel.fromJson(user(services: ['complaints', 'notices'])).toEntity();
    expect(u.hasService('complaints'), isTrue);
    expect(u.hasService('parking'), isFalse);
  });

  test('no list from the server means no limit (platform admin, older server)', () {
    final u = UserModel.fromJson(user()).toEntity();
    expect(u.enabledServices, isNull);
    expect(u.hasService('parking'), isTrue);
  });

  test('a society service switch and its history line read well', () {
    final s = SocietyServiceSwitch.fromJson({'key': 'parking', 'label': 'Parking', 'description': 'Slots', 'enabled': false});
    expect(s.enabled, isFalse);
    expect(eventLabel('service_switched'), 'Service switched');
    expect(eventDetail('service_switched', {'service': 'gate_extras', 'enabled': false}), 'gate extras turned off');
    expect(eventDetail('service_switched', {'service': 'parking', 'enabled': true}), 'parking turned on');
  });
}
