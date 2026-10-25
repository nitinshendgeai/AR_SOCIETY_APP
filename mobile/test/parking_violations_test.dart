import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/parking/data/parking_violations_api.dart';
import 'package:ar_society_app/features/parking/presentation/screens/parking_violations_tab.dart';

class _FakeApi extends ParkingViolationsApi {
  _FakeApi(this.rows) : super(dio: Dio());
  List<ViolationItem> rows;
  final charged = <(String, String?, int?)>[];
  final waived = <(String, String)>[];
  final reported = <(String, String, int?)>[];

  @override
  Future<List<ViolationItem>> list(String societyId, {bool unresolvedOnly = false}) async => rows;

  @override
  Future<ViolationItem> chargeFine(String id, {String? flatId, int? amount}) async {
    charged.add((id, flatId, amount));
    return rows.first;
  }

  @override
  Future<ViolationItem> waiveFine(String id, String reason) async {
    waived.add((id, reason));
    return rows.first;
  }

  @override
  Future<ViolationItem> report(
      {required String societyId,
      required String vehicleNumber,
      required String type,
      String? description,
      int? fineAmount}) async {
    reported.add((vehicleNumber, type, fineAmount));
    return ViolationItem(id: 'new', vehicleNumber: vehicleNumber, type: type, fineAmount: fineAmount);
  }
}

ViolationItem _v(String id, {int? fine = 500, String? status, String number = 'MH12AB1234'}) =>
    ViolationItem.fromJson({
      'id': id,
      'vehicle_number': number,
      'violation_type': 'wrong_slot',
      'is_resolved': false,
      'fine_amount': fine,
      'fine_status': status,
    });

Widget _tab(_FakeApi api) => ProviderScope(
      overrides: [parkingViolationsApiProvider.overrideWithValue(api)],
      child: MaterialApp(theme: AppTheme.lightTheme, home: Scaffold(body: ViolationsTab(societyId: 's1'))),
    );

void main() {
  test('a fine can be charged until it is on a bill, and waived only before', () {
    expect(_v('a').canCharge, isTrue);
    expect(_v('a').canWaive, isFalse);
    final onBill = _v('a', status: 'active');
    expect((onBill.canCharge, onBill.canWaive, onBill.fine.label), (false, true, 'On the next bill'));
    final billed = _v('a', status: 'billed');
    expect((billed.canCharge, billed.canWaive), (false, false));
    final waived = _v('a', status: 'cancelled');
    expect((waived.canCharge, waived.canWaive, waived.fine.label), (true, false, 'Waived'));
    expect(violationTypeLabel('wrong_slot'), 'Wrong slot');
  });

  testWidgets('a recorded fine is charged to the vehicle\'s flat in one step', (tester) async {
    final api = _FakeApi([_v('v1')]);
    await tester.pumpWidget(_tab(api));
    await tester.pumpAndSettle();
    expect(find.text('MH12AB1234'), findsOneWidget);
    expect(find.text('Waive fine'), findsNothing);

    await tester.tap(find.text('Charge fine to flat'));
    await tester.pumpAndSettle();
    expect(find.textContaining('Fine ₹500 goes on the flat'), findsOneWidget);
    await tester.tap(find.widgetWithText(FilledButton, 'Charge fine'));
    await tester.pump(const Duration(seconds: 6));
    expect(api.charged, [('v1', null, null)]);
  });

  testWidgets('a violation recorded without a fine asks for the amount', (tester) async {
    final api = _FakeApi([_v('v2', fine: null)]);
    await tester.pumpWidget(_tab(api));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Charge fine to flat'));
    await tester.pumpAndSettle();

    await tester.tap(find.widgetWithText(FilledButton, 'Charge fine'));
    await tester.pumpAndSettle();
    expect(find.text('Enter the fine'), findsOneWidget);
    expect(api.charged, isEmpty);

    await tester.enterText(find.byType(TextFormField), '300');
    await tester.tap(find.widgetWithText(FilledButton, 'Charge fine'));
    await tester.pump(const Duration(seconds: 6));
    expect(api.charged, [('v2', null, 300)]);
  });

  testWidgets('a fine waiting for the next bill can be waived with a reason', (tester) async {
    final api = _FakeApi([_v('v3', status: 'active')]);
    await tester.pumpWidget(_tab(api));
    await tester.pumpAndSettle();
    expect(find.text('On the next bill'), findsOneWidget);
    expect(find.text('Charge fine to flat'), findsNothing);

    await tester.tap(find.text('Waive fine'));
    await tester.pumpAndSettle();
    await tester.tap(find.widgetWithText(FilledButton, 'Waive fine'));
    await tester.pumpAndSettle();
    expect(find.text('Say why (at least 3 letters)'), findsOneWidget);

    await tester.enterText(find.byType(TextFormField), 'First offence');
    await tester.tap(find.widgetWithText(FilledButton, 'Waive fine'));
    await tester.pump(const Duration(seconds: 6));
    expect(api.waived, [('v3', 'First offence')]);
  });

  testWidgets('a billed fine offers no action', (tester) async {
    await tester.pumpWidget(_tab(_FakeApi([_v('v4', status: 'billed')])));
    await tester.pumpAndSettle();
    expect(find.text('Billed'), findsOneWidget);
    expect(find.text('Waive fine'), findsNothing);
    expect(find.textContaining('Charge fine'), findsNothing);
  });

  testWidgets('a violation can be reported with a fine', (tester) async {
    final api = _FakeApi([]);
    await tester.pumpWidget(ProviderScope(
      overrides: [parkingViolationsApiProvider.overrideWithValue(api)],
      child: MaterialApp(
        theme: AppTheme.lightTheme,
        home: Scaffold(body: Consumer(builder: (context, ref, _) {
          return TextButton(onPressed: () => showReportViolation(context, ref, 's1'), child: const Text('open'));
        })),
      ),
    ));
    await tester.tap(find.text('open'));
    await tester.pumpAndSettle();
    await tester.tap(find.widgetWithText(FilledButton, 'Record violation'));
    await tester.pumpAndSettle();
    expect(find.text('Enter the vehicle number'), findsOneWidget);

    await tester.enterText(find.byType(TextFormField).first, 'KA01XY9999');
    await tester.enterText(find.byType(TextFormField).last, '250');
    await tester.ensureVisible(find.widgetWithText(FilledButton, 'Record violation'));
    await tester.tap(find.widgetWithText(FilledButton, 'Record violation'));
    await tester.pump(const Duration(seconds: 6));
    expect(api.reported, [('KA01XY9999', 'unauthorized', 250)]);
  });
}
