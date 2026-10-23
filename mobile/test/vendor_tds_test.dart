import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ar_society_app/features/vendor/data/vendors_work_api.dart';
import 'package:ar_society_app/features/vendor/presentation/providers/vendors_work_providers.dart';
import 'package:ar_society_app/features/vendor/presentation/widgets/payment_tds_card.dart';
import 'package:ar_society_app/features/vendor/presentation/widgets/vendor_master_sheet.dart';

const _options = {
  'constitutions': [
    {'value': 'individual_proprietor', 'label': 'Individual / Proprietorship (self business)'},
    {'value': 'private_limited', 'label': 'Private Limited company'},
  ],
  'sections': [
    {'value': '194C', 'label': 'Contract / work (194C)'},
    {'value': '194J_PROF', 'label': 'Professional fees (194J)'},
  ],
  'category_default_section': {'housekeeping': '194C', 'other': null},
};

Map<String, dynamic> _preview({bool applies = true, String note = '194C contract at 2% on ₹1,00,000'}) => {
      'applies': applies, 'amount': '100000.00', 'taxable_value': '100000.00', 'tds_base': '100000.00',
      'tds_amount': applies ? '2000.00' : '0.00', 'net_payable': applies ? '98000.00' : '100000.00',
      'rate': '2.0000', 'section_label': '194C contract', 'note': note,
    };

class _FakeApi extends VendorsWorkApi {
  _FakeApi() : super(dio: Dio());
  @override
  Future<TdsOptions> tdsOptions() async => TdsOptions.fromJson(_options);
}

void main() {
  group('reading the TDS fields', () {
    test('vendor types and sections with the usual section for each kind of vendor', () {
      final o = TdsOptions.fromJson(_options);
      expect(o.constitutions.map((c) => c.$1), ['individual_proprietor', 'private_limited']);
      expect(o.sections.first, ('194C', 'Contract / work (194C)'));
      expect(o.categoryDefaultSection['housekeeping'], '194C');
      expect(o.categoryDefaultSection['other'], isNull);
    });

    test('a vendor carries its type, section and lower-deduction certificate', () {
      final v = VendorRecord.fromJson({
        'id': 'v1', 'vendor_code': 'VND-1', 'company_name': 'Sparkle', 'mobile': '9876543210',
        'category': 'housekeeping', 'status': 'active', 'constitution': 'private_limited',
        'constitution_label': 'Private Limited company', 'tds_section': '194C', 'tds_lower_rate': '0.5000',
        'tds_lower_cert_no': 'LDC/77', 'tds_lower_valid_from': '2026-04-01', 'tds_lower_valid_to': '2026-09-30',
      });
      expect((v.constitution, v.tdsSection, v.tdsLowerRate, v.tdsLowerCertNo), ('private_limited', '194C', '0.5000', 'LDC/77'));
      expect(v.tdsLowerValidTo, '2026-09-30');
      final old = VendorRecord.fromJson({
        'id': 'v2', 'vendor_code': 'VND-2', 'company_name': 'Old', 'mobile': '9876543210',
        'category': 'other', 'status': 'active',
      });
      expect(old.constitution, isNull);
      expect(old.tdsSection, isNull);
    });

    test('a payment preview reads the TDS and what the vendor receives', () {
      final p = PaymentTdsPreview.fromJson(_preview());
      expect(p.applies, isTrue);
      expect((p.tdsAmount, p.netPayable, p.rate), ('2000.00', '98000.00', '2.0000'));
      expect(p.note, contains('194C'));
    });
  });

  group('the TDS card on the payment form', () {
    Widget host(PaymentTdsPreview? p, {bool loading = false}) =>
        MaterialApp(home: Scaffold(body: PaymentTdsCard(preview: p, loading: loading)));

    testWidgets('shows the TDS, why, and what the vendor receives', (tester) async {
      await tester.pumpWidget(host(PaymentTdsPreview.fromJson(_preview())));
      expect(find.byKey(const Key('tds-card')), findsOneWidget);
      expect(find.text('₹2,000.00'), findsOneWidget);
      expect(find.text('₹98,000.00'), findsOneWidget);
      expect(find.text('194C contract at 2% on ₹1,00,000'), findsOneWidget);
    });

    testWidgets('says why when no TDS is taken, and stays quiet when there is nothing to say', (tester) async {
      await tester.pumpWidget(host(PaymentTdsPreview.fromJson(_preview(applies: false, note: 'No TDS: under the ₹1,00,000 limit'))));
      expect(find.byKey(const Key('tds-card')), findsNothing);
      expect(find.text('No TDS: under the ₹1,00,000 limit'), findsOneWidget);

      await tester.pumpWidget(host(PaymentTdsPreview.fromJson(_preview(applies: false, note: ''))));
      expect(find.byKey(const Key('tds-note')), findsNothing);
      expect(find.byKey(const Key('tds-card')), findsNothing);

      await tester.pumpWidget(host(null));
      expect(find.byType(PaymentTdsCard), findsOneWidget);
      expect(find.byKey(const Key('tds-card')), findsNothing);
    });
  });

  group('the vendor form', () {
    Widget sheet() => ProviderScope(
          overrides: [vendorsWorkApiProvider.overrideWithValue(_FakeApi())],
          child: MaterialApp(
            home: Scaffold(
              body: VendorSheet(
                societyId: 'soc',
                existing: VendorRecord.fromJson({
                  'id': 'v1', 'vendor_code': 'VND-1', 'company_name': 'Sparkle', 'mobile': '9876543210',
                  'category': 'housekeeping', 'status': 'active',
                }),
              ),
            ),
          ),
        );

    testWidgets('choosing a type brings in the usual TDS section for the kind of work', (tester) async {
      tester.view.physicalSize = const Size(900, 3000);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.reset);
      await tester.pumpWidget(sheet());
      await tester.pumpAndSettle();
      expect(find.byKey(const Key('vendor-tds-section')), findsNothing);       // no type yet: nothing to deduct

      await tester.ensureVisible(find.byKey(const Key('vendor-constitution')));
      await tester.tap(find.byKey(const Key('vendor-constitution')));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Private Limited company').last);
      await tester.pumpAndSettle();

      expect(find.byKey(const Key('vendor-tds-section')), findsOneWidget);
      expect(find.text('Contract / work (194C)'), findsWidgets);                // housekeeping is usually 194C
      expect(find.textContaining('no PAN means 20%'), findsOneWidget);
    });
  });
}
