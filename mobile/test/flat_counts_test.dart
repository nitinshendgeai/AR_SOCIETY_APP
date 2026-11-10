import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/auth/domain/entities/user_entity.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/features/society_structure/data/models/structure_models.dart';
import 'package:ar_society_app/features/society_structure/presentation/providers/structure_providers.dart';
import 'package:ar_society_app/features/society_structure/presentation/screens/flat_list_screen.dart';

class _Flats extends FlatsBySocietyNotifier {
  final List<FlatModel> data;
  _Flats(this.data);
  @override
  Future<List<FlatModel>> build() async => data;
}

FlatModel _flat(String id, String number, String wingId, String wingName, String occupancy) =>
    FlatModel(id: id, flatNumber: number, wingId: wingId, wingName: wingName, occupancyStatus: occupancy);

Widget _app(Widget home) => ProviderScope(
      overrides: [
        currentUserProvider.overrideWithValue(
            const UserEntity(id: 'u', email: 'u@t.com', fullName: 'U', roles: ['Society Admin'], societyId: 's1')),
        flatsBySocietyProvider.overrideWith(() => _Flats([
              _flat('f1', '101', 'wa', 'Wing A', 'owner_occupied'),
              _flat('f2', '102', 'wa', 'Wing A', 'tenant_occupied'),
              _flat('f3', '201', 'wb', 'Wing B', 'vacant'),
              _flat('f4', '202', 'wb', 'Wing B', 'owner_occupied'),
            ])),
      ],
      child: MaterialApp(theme: AppTheme.lightTheme, home: home),
    );

void main() {
  testWidgets('the Flats list counts owner-occupied, tenant-occupied and vacant flats under the filters picked',
      (tester) async {
    await tester.pumpWidget(_app(const FlatListScreen()));
    await tester.pumpAndSettle();
    expect(find.text('All (4)'), findsOneWidget);
    expect(find.text('Owner (2)'), findsOneWidget);
    expect(find.text('Tenant (1)'), findsOneWidget);
    expect(find.text('Vacant (1)'), findsOneWidget);

    // choosing an occupancy narrows the list but not the counts: they stay a breakdown of the other filters
    await tester.tap(find.byKey(const ValueKey('flats-occupancy-tenant_occupied')));
    await tester.pumpAndSettle();
    expect(find.text('Owner (2)'), findsOneWidget);
    expect(find.text('Tenant (1)'), findsOneWidget);

    // a wing narrows every count
    await tester.tap(find.byKey(const ValueKey('flats-filter-wing')));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Wing A').last);
    await tester.pumpAndSettle();
    expect(find.text('All (2)'), findsOneWidget);
    expect(find.text('Owner (1)'), findsOneWidget);
    expect(find.text('Tenant (1)'), findsOneWidget);
    expect(find.text('Vacant (0)'), findsOneWidget);
  });
}
