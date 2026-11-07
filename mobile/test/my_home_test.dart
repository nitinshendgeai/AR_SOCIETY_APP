import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/resident_master/data/models/resident_master_models.dart';
import 'package:ar_society_app/features/resident_master/presentation/providers/resident_master_providers.dart';
import 'package:ar_society_app/features/resident_master/presentation/screens/my_home_screen.dart';
import 'package:ar_society_app/features/society_structure/data/models/structure_models.dart';
import 'package:ar_society_app/features/society_structure/presentation/providers/structure_providers.dart' show flatByIdProvider;

ResidentModel _person(String id, String name, ResidentType type, {bool primary = false}) =>
    ResidentModel(id: id, flatId: 'f1', fullName: name, residentType: type, isPrimary: primary, phone: '9876543210');

class _FakeVehicles extends VehiclesByFlatNotifier {
  final List<VehicleModel> list;
  _FakeVehicles(this.list);

  @override
  Future<List<VehicleModel>> build(String flatId) async => list;
}

Widget _app({required ResidentModel? me, List<ResidentModel> household = const [], List<VehicleModel> vehicles = const []}) =>
    ProviderScope(
      overrides: [
        myResidentProvider.overrideWith((ref) async => me),
        flatByIdProvider('f1').overrideWith((ref) async => const FlatModel(id: 'f1', flatNumber: '101', wingId: 'w', wingName: 'A')),
        residentsByFlatProvider('f1').overrideWith((ref) async => household),
        vehiclesByFlatProvider.overrideWith(() => _FakeVehicles(vehicles)),
        myEditRequestsProvider.overrideWith((ref) async => const []),
      ],
      child: MaterialApp(theme: AppTheme.lightTheme, home: const MyHomeScreen()),
    );

void main() {
  testWidgets('My Home shows the flat, the household and the vehicles', (tester) async {
    tester.view.physicalSize = const Size(800, 2400);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    final me = _person('r1', 'Asha Rao', ResidentType.owner, primary: true);
    await tester.pumpWidget(_app(
      me: me,
      household: [me, _person('r2', 'Kiran Rao', ResidentType.family)],
      vehicles: const [VehicleModel(id: 'v1', societyId: 's1', vehicleNumber: 'MH12AB1234', vehicleType: VehicleType.car, parkingSlot: 'P-7')],
    ));
    await tester.pumpAndSettle();

    expect(find.text('A-101'), findsOneWidget);
    expect(find.textContaining('Asha Rao'), findsOneWidget);          // header line "Asha Rao · Owner"
    expect(find.text('Kiran Rao'), findsOneWidget);                   // household shows the others, not me again
    expect(find.text('MH12AB1234'), findsOneWidget);
    expect(find.textContaining('Slot P-7'), findsOneWidget);
    expect(find.text('Add vehicle'), findsOneWidget);
    expect(find.textContaining('ask the society office'), findsWidgets);
  });

  testWidgets('with no one else and no vehicles it says so', (tester) async {
    tester.view.physicalSize = const Size(800, 2400);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    final me = _person('r1', 'Asha Rao', ResidentType.owner);
    await tester.pumpWidget(_app(me: me, household: [me]));
    await tester.pumpAndSettle();
    expect(find.text('No one else is registered on this flat.'), findsOneWidget);
    expect(find.textContaining('No vehicles registered'), findsOneWidget);
  });

  testWidgets('a login with no resident record is told to ask the office', (tester) async {
    await tester.pumpWidget(_app(me: null));
    await tester.pumpAndSettle();
    expect(find.textContaining('not linked to a flat'), findsOneWidget);
  });
}
