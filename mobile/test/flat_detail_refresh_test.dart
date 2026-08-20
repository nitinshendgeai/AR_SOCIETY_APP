import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/society_structure/data/models/structure_models.dart';
import 'package:ar_society_app/features/society_structure/presentation/providers/structure_providers.dart';
import 'package:ar_society_app/features/society_structure/presentation/screens/flat_detail_screen.dart';

// Regression for M1.9: FlatDetailScreen rendered directly from the FlatModel
// it was pushed with. Save Changes on Edit Flat pops back via a plain
// Navigator.pop(), so the already-mounted detail screen kept showing the
// pre-edit values (e.g. a missing Area row) even though flatsBySocietyProvider
// — and the flat list — had the correct, freshly-PATCHed data all along.
// Found live: edited a flat's Area from empty to 650 sq ft, the backend
// persisted it and the flat list showed "650 sqft", but the detail screen
// the edit had returned to still showed no Area row.
class _FakeFlatsNotifier extends FlatsBySocietyNotifier {
  final List<FlatModel> data;
  _FakeFlatsNotifier(this.data);
  @override
  Future<List<FlatModel>> build() async => data;
}

void main() {
  testWidgets(
      'FlatDetailScreen shows the live flatsBySocietyProvider value, not the '
      'possibly-stale FlatModel it was constructed with', (tester) async {
    const staleFlat = FlatModel(
      id: 'flat-1',
      flatNumber: 'A-101',
      wingId: 'wing-1',
      wingName: 'Wing A',
      occupancyStatus: 'vacant',
      // areaSqft intentionally null here, as it was before the edit.
    );
    const freshFlat = FlatModel(
      id: 'flat-1',
      flatNumber: 'A-101',
      wingId: 'wing-1',
      wingName: 'Wing A',
      occupancyStatus: 'vacant',
      areaSqft: 650,
    );

    await tester.pumpWidget(ProviderScope(
      overrides: [
        flatsBySocietyProvider.overrideWith(() => _FakeFlatsNotifier([freshFlat])),
      ],
      child: MaterialApp(
        theme: AppTheme.lightTheme,
        home: const FlatDetailScreen(flat: staleFlat),
      ),
    ));
    await tester.pumpAndSettle();

    expect(find.text('650 sq ft'), findsOneWidget);
  });
}
