import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ar_society_app/features/accounts/data/accounts_api.dart';
import 'package:ar_society_app/features/accounts/data/recurring_api.dart';
import 'package:ar_society_app/features/vendor/data/vendors_work_api.dart';
import 'package:ar_society_app/features/vendor/presentation/providers/vendors_work_providers.dart';
import 'package:ar_society_app/features/vendor/presentation/widgets/vendor_picker.dart';

Map<String, dynamic> _vendor(String id, String name, {String status = 'active'}) => {
      'id': id, 'vendor_code': 'VND-$id', 'company_name': name, 'mobile': '9876543210',
      'category': 'security', 'status': status,
    };

Widget _picker({String? value, String? legacy, required ValueChanged<VendorRecord?> onChanged}) => ProviderScope(
      overrides: [
        vendorRecordsProvider('s1').overrideWith((ref) async => [
              VendorRecord.fromJson(_vendor('1', 'Shield Security')),
              VendorRecord.fromJson(_vendor('2', 'Acme Lifts')),
              VendorRecord.fromJson(_vendor('3', 'Banned Co', status: 'blacklisted')),
            ]),
      ],
      child: MaterialApp(
        home: Scaffold(
          body: Padding(
            padding: const EdgeInsets.all(16),
            child: VendorPicker(societyId: 's1', value: value, legacyName: legacy, onChanged: onChanged),
          ),
        ),
      ),
    );

void main() {
  test('a voucher carries the vendor it was paid to', () {
    final v = Voucher.fromJson({
      'id': 'v1', 'voucher_type': 'payment', 'voucher_number': 'PV/2026-27/0001', 'voucher_date': '2026-10-09',
      'amount': '1000.00', 'vendor_id': 'ven1', 'vendor_name': 'Shield Security', 'reference': 'BILL-7',
      'entries': [],
    });
    expect(v.vendorId, 'ven1');
    expect(v.vendorName, 'Shield Security');
    expect(v.reference, 'BILL-7');
  });

  testWidgets('the picker lists the Vendor Master (not blacklisted vendors) and reports the choice', (tester) async {
    VendorRecord? chosen;
    await tester.pumpWidget(_picker(onChanged: (v) => chosen = v));
    await tester.pumpAndSettle();

    await tester.tap(find.byType(DropdownButtonFormField<String?>));
    await tester.pumpAndSettle();
    expect(find.textContaining('Shield Security'), findsWidgets);
    expect(find.textContaining('Acme Lifts'), findsOneWidget);
    expect(find.textContaining('Banned Co'), findsNothing);

    await tester.tap(find.textContaining('Acme Lifts').last);
    await tester.pumpAndSettle();
    expect(chosen?.id, '2');
  });

  testWidgets('a payee typed before the master was linked is flagged, and a vendor can be added on the spot', (tester) async {
    await tester.pumpWidget(_picker(legacy: 'Shield Security Services', onChanged: (_) {}));
    await tester.pumpAndSettle();
    expect(find.textContaining('Was typed as "Shield Security Services"'), findsOneWidget);

    // "+" opens the Vendor Master form itself, with its GSTIN / PAN / bank fields, not a cut-down copy
    await tester.tap(find.byTooltip('Add a new vendor'));
    await tester.pumpAndSettle();
    expect(find.text('Add Vendor'), findsWidgets);
    expect(find.text('Company / name *'), findsOneWidget);
    expect(find.text('Tax and bank'), findsOneWidget);
    expect(find.text('GSTIN'), findsOneWidget);
    expect(find.text('Bank account no.'), findsOneWidget);
    // an empty form does not go through
    await tester.dragUntilVisible(find.text('Add Vendor').last, find.byType(SingleChildScrollView).last, const Offset(0, -200));
    await tester.tap(find.text('Add Vendor').last);
    await tester.pumpAndSettle();
    expect(find.text('Enter the name'), findsOneWidget);
  });

  testWidgets('a bill needs a vendor, so there is no "No vendor" entry', (tester) async {
    await tester.pumpWidget(ProviderScope(
      overrides: [
        vendorRecordsProvider('s1').overrideWith((ref) async => [VendorRecord.fromJson(_vendor('1', 'Shield Security'))]),
      ],
      child: MaterialApp(
        home: Scaffold(body: VendorPicker(societyId: 's1', value: null, required: true, label: 'Vendor *', onChanged: (_) {})),
      ),
    ));
    await tester.pumpAndSettle();
    await tester.tap(find.byType(DropdownButtonFormField<String?>));
    await tester.pumpAndSettle();
    expect(find.text('No vendor'), findsNothing);
    expect(find.textContaining('Shield Security'), findsWidgets);
  });

  testWidgets('a vendor already chosen stays listed even if it was blacklisted since', (tester) async {
    await tester.pumpWidget(_picker(value: '3', onChanged: (_) {}));
    await tester.pumpAndSettle();
    expect(find.textContaining('Banned Co'), findsOneWidget);
  });
}
