import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ar_society_app/features/parking/data/models/parking_models.dart';
import 'package:ar_society_app/features/parking/domain/entities/parking_entities.dart';
import 'package:ar_society_app/features/parking/presentation/screens/parking_management_screen.dart';

void main() {
  test('vehicle types fall into four-wheeler, two-wheeler or neither', () {
    for (final t in ['car', 'van', 'truck', 'CAR']) {
      expect(wheelerClassOf(t), WheelerClass.four, reason: t);
    }
    for (final t in ['motorcycle', 'scooter', 'bicycle']) {
      expect(wheelerClassOf(t), WheelerClass.two, reason: t);
    }
    for (final t in ['auto', 'other', null, '']) {
      expect(wheelerClassOf(t), isNull, reason: '$t');
    }
  });

  test('the filter keeps only the chosen group; All keeps everything', () {
    const types = ['car', 'scooter', 'auto', 'motorcycle', null];
    List<String?> pick(WheelerClass w) => types.where((t) => matchesWheeler(w, t)).toList();
    expect(pick(WheelerClass.all), types);
    expect(pick(WheelerClass.four), ['car']);
    expect(pick(WheelerClass.two), ['scooter', 'motorcycle']);
  });

  test('an allocation carries its vehicle type from the server', () {
    final a = ParkingAllocationModel.fromJson({
      'id': 'a1', 'society_id': 's1', 'slot_id': 'p1', 'allocation_type': 'resident', 'status': 'active',
      'start_date': '2026-11-01', 'vehicle_number': 'MH12SC0002', 'vehicle_type': 'scooter',
    }).toEntity();
    expect(a.vehicleType, 'scooter');
    expect(matchesWheeler(WheelerClass.two, a.vehicleType), isTrue);
  });

  testWidgets('the chips show counts and report the choice', (tester) async {
    WheelerClass? chosen;
    await tester.pumpWidget(MaterialApp(
      home: Scaffold(
        body: WheelerFilter(
          value: WheelerClass.all,
          types: const ['car', 'car', 'scooter', 'auto'],
          onChanged: (w) => chosen = w,
        ),
      ),
    ));
    expect(find.text('All (4)'), findsOneWidget);
    expect(find.text('Four wheeler (2)'), findsOneWidget);
    expect(find.text('Two wheeler (1)'), findsOneWidget);
    await tester.tap(find.text('Two wheeler (1)'));
    expect(chosen, WheelerClass.two);
  });
}
