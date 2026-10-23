import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ar_society_app/features/staff/domain/entities/staff_entities.dart';
import 'package:ar_society_app/features/staff/presentation/providers/staff_providers.dart';
import 'package:ar_society_app/features/staff/presentation/widgets/standard_checklists_sheet.dart';

Map<String, dynamic> _json(String code, String dept, String name, {bool added = false}) => {
      'code': code, 'department': dept, 'name': name, 'description': 'd',
      'item_count': 2, 'required_count': 1, 'already_added': added,
      'items': [
        {'title': 'Check pumps', 'description': 'Listen for noise', 'is_required': true},
        {'title': 'Handover note', 'description': null, 'is_required': false},
      ],
    };

Widget _sheet(List<StandardChecklistEntity> rows) => ProviderScope(
      overrides: [standardChecklistsProvider('soc').overrideWith((ref) async => rows)],
      child: const MaterialApp(home: Scaffold(body: StandardChecklistsSheet(societyId: 'soc'))),
    );

void main() {
  group('standard checklist entity', () {
    test('reads counts, department, added flag and lines', () {
      final c = StandardChecklistEntity.fromJson(_json('plumber_daily', 'plumbing', 'Plumber: daily round'));
      expect(c.department, 'plumbing');
      expect(c.itemCount, 2);
      expect(c.requiredCount, 1);
      expect(c.alreadyAdded, isFalse);
      expect(c.items.map((i) => i.title), ['Check pumps', 'Handover note']);
      expect(c.items[1].isRequired, isFalse);
    });

    test('missing optional fields fall back safely', () {
      final c = StandardChecklistEntity.fromJson({'code': 'x', 'department': 'maintenance', 'name': 'N'});
      expect(c.items, isEmpty);
      expect(c.itemCount, 0);
      expect(c.alreadyAdded, isFalse);
      expect(c.description, '');
    });
  });

  group('standard checklists sheet', () {
    testWidgets('lists each round with its department and required count', (tester) async {
      await tester.pumpWidget(_sheet([
        StandardChecklistEntity.fromJson(_json('plumber_daily', 'plumbing', 'Plumber: daily round')),
        StandardChecklistEntity.fromJson(_json('electrician_daily', 'electrical', 'Electrician: daily round')),
      ]));
      await tester.pumpAndSettle();
      expect(find.text('Plumber: daily round'), findsOneWidget);
      expect(find.text('Electrician: daily round'), findsOneWidget);
      expect(find.text('For Plumbing staff · 2 checks, 1 must be ticked'), findsOneWidget);
    });

    testWidgets('each round offers a Hindi and an English print', (tester) async {
      await tester.pumpWidget(_sheet([
        StandardChecklistEntity.fromJson(_json('plumber_daily', 'plumbing', 'Plumber: daily round')),
      ]));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Plumber: daily round'));
      await tester.pumpAndSettle();
      expect(find.byKey(const ValueKey('print-hi-plumber_daily')), findsOneWidget);
      expect(find.byKey(const ValueKey('print-en-plumber_daily')), findsOneWidget);
      expect(find.text('Print in Hindi (हिंदी)'), findsOneWidget);
    });

    testWidgets('add is disabled until one is picked, and a round already added cannot be picked', (tester) async {
      await tester.pumpWidget(_sheet([
        StandardChecklistEntity.fromJson(_json('plumber_daily', 'plumbing', 'Plumber: daily round')),
        StandardChecklistEntity.fromJson(
            _json('electrician_daily', 'electrical', 'Electrician: daily round', added: true)),
      ]));
      await tester.pumpAndSettle();
      ElevatedButton button() => tester.widget<ElevatedButton>(find.byKey(const Key('add-standard-checklists')));
      expect(button().onPressed, isNull);
      expect(find.text('Already in your templates'), findsOneWidget);

      await tester.tap(find.byType(Checkbox).first);
      await tester.pump();
      expect(button().onPressed, isNotNull);
      expect(find.text('Add 1 to my templates'), findsOneWidget);
    });
  });
}
