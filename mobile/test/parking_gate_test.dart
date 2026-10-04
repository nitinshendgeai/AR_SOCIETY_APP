import 'package:flutter_test/flutter_test.dart';
import 'package:ar_society_app/features/parking/data/models/parking_models.dart';
import 'package:ar_society_app/features/parking/domain/entities/parking_entities.dart';

void main() {
  Map<String, dynamic> lookup(Map<String, dynamic> over) => {
        'vehicle_number': 'MH12AB1234', 'authorized': false, 'category': 'resident',
        'message': 'm', ...over,
      };

  group('the gate answer', () {
    test('three statuses, as the server sends them', () {
      GateStatus of(Map<String, dynamic> j) => GateVehicleLookupModel.fromJson(lookup(j)).toEntity().status;
      expect(of({'authorized': true, 'status': 'allowed'}), GateStatus.allowed);
      expect(of({'authorized': false, 'status': 'no_parking'}), GateStatus.noParking);
      expect(of({'authorized': false, 'status': 'unregistered', 'category': 'unregistered'}), GateStatus.unregistered);
    });

    test('an older server without a status still gives the right colour', () {
      GateStatus of(bool authorized) =>
          GateVehicleLookupModel.fromJson(lookup({'authorized': authorized})).toEntity().status;
      expect(of(true), GateStatus.allowed);
      expect(of(false), GateStatus.unregistered);
    });

    test('a registered vehicle without parking is not "unregistered"', () {
      final e = GateVehicleLookupModel.fromJson(
          lookup({'status': 'no_parking', 'owner_name': 'Suresh', 'flat_number': '102'})).toEntity();
      expect(e.status, GateStatus.noParking);
      expect(e.authorized, isFalse);
      expect(e.category, GateVehicleCategory.resident);
    });
  });

  group('registered vehicles with their parking', () {
    final json = {
      'id': 'v1', 'vehicle_number': 'MH43CD5678', 'vehicle_type': 'car', 'flat_id': 'f1',
      'flat_number': '102', 'wing_name': 'A Wing', 'owner_name': 'Suresh Nair', 'category': 'tenant',
      'has_parking': false, 'parking_slot': null, 'allocation_id': null,
    };

    test('without a slot', () {
      final v = VehicleParkingModel.fromJson(json).toEntity();
      expect(v.hasParking, isFalse);
      expect(v.isTenant, isTrue);
      expect(v.flatLabel, 'A Wing — 102');
    });

    test('with a slot and its allocation', () {
      final v = VehicleParkingModel.fromJson({
        ...json, 'has_parking': true, 'parking_slot': 'B1-03', 'allocation_id': 'a1',
        'end_date': '2027-03-31', 'monthly_charge': 1500,
      }).toEntity();
      expect(v.hasParking, isTrue);
      expect(v.parkingSlot, 'B1-03');
      expect(v.allocationId, 'a1');
      expect(v.endDate, DateTime(2027, 3, 31));
      expect(v.monthlyCharge, 1500);
    });
  });
}
