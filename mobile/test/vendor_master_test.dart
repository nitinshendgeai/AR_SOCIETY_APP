import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ar_society_app/features/auth/domain/entities/user_entity.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/features/vendor/data/vendor_master_api.dart';
import 'package:ar_society_app/features/vendor/presentation/screens/vendor_tds_review_screen.dart';
import 'package:ar_society_app/features/vendor/presentation/screens/vendors_import_screen.dart';

const _admin = UserEntity(id: 'u1', email: 'a@b.c', fullName: 'Asha', roles: ['Society Admin'], societyId: 's1', termsAccepted: true);
const _manager = UserEntity(id: 'u2', email: 'm@b.c', fullName: 'Manu', roles: ['Manager'], societyId: 's1', termsAccepted: true);

Map<String, dynamic> _row(String id, String name,
        {String? pan, String? type, String? section, List<Map<String, String>> issues = const [], String? sType, String? sSection}) =>
    {
      'id': id, 'vendor_code': 'VND-$id', 'company_name': name, 'pan_number': pan, 'constitution': type,
      'constitution_label': type, 'tds_section': section, 'tds_section_label': section, 'issues': issues,
      'suggested_constitution': sType, 'suggested_constitution_label': sType, 'suggested_section': sSection,
      'suggested_section_label': sSection, 'can_fix': sType != null || sSection != null,
    };

class _FakeApi extends VendorMasterApi {
  _FakeApi(this.review) : super(dio: Dio());
  Map<String, dynamic> review;
  final applied = <(bool, List<String>)>[];
  final imports = <bool>[];

  @override
  Future<TdsReview> tdsReview(String societyId) async => TdsReview.fromJson(review);

  @override
  Future<TdsFixResult> applyTdsFixes(String societyId,
      {List<({String vendorId, String? constitution, String? section})> items = const [], bool useSuggestions = false}) async {
    applied.add((useSuggestions, [for (final i in items) '${i.vendorId}:${i.constitution}:${i.section}']));
    return const TdsFixResult(1, []);
  }

  @override
  Future<VendorImportResult> importFile(String societyId, Uint8List bytes, String fileName,
      {required bool dryRun, Map<String, String?>? mapping}) async {
    imports.add(dryRun);
    return VendorImportResult.fromJson({
      'dry_run': dryRun, 'file_name': 'vendors.csv', 'sheet': 'CSV', 'total_rows': 2,
      'columns': [
        {'index': 0, 'heading': 'Vendor Name', 'field': 'company_name', 'sample': 'Sparkle'},
        {'index': 1, 'heading': 'Mobile', 'field': 'mobile', 'sample': '9876543210'},
      ],
      'fields': [
        {'field': 'company_name', 'label': 'Vendor name'},
        {'field': 'mobile', 'label': 'Mobile'},
      ],
      'ready': dryRun ? 1 : 0, 'created': dryRun ? 0 : 1, 'duplicates': 1, 'errors': 0,
      'rows': [
        {'line': 2, 'status': dryRun ? 'ready' : 'created', 'name': 'Sparkle', 'constitution_label': 'Pvt Ltd',
          'tds_section': '194C', 'message': 'Type worked out from its PAN: Pvt Ltd'},
        {'line': 3, 'status': 'duplicate', 'name': 'Old Co', 'message': 'A vendor named Old Co already exists; skipped'},
      ],
    });
  }
}

Widget _app(_FakeApi api, Widget home, {UserEntity user = _admin}) => ProviderScope(
      overrides: [currentUserProvider.overrideWithValue(user), vendorMasterApiProvider.overrideWithValue(api)],
      child: MaterialApp(home: home),
    );

Map<String, dynamic> _review() => {
      'total': 3, 'with_issues': 2, 'fixable': 1,
      'vendors': [
        _row('1', 'No Type Co', pan: 'AABCC1234F', sType: 'private_limited', sSection: '194C', issues: [
          {'code': 'no_type', 'message': 'No type: TDS can\'t be worked out (the PAN suggests Private Limited)'}
        ]),
        _row('2', 'No Pan Co', type: 'private_limited', section: '194C', issues: [
          {'code': 'no_pan', 'message': 'No PAN: TDS is deducted at 20% when this vendor is paid'}
        ]),
        _row('3', 'Fine Co', pan: 'AABCC1234G', type: 'private_limited', section: '194C'),
      ],
    };

void main() {
  testWidgets('the review lists vendors that need attention and applies the suggested fix to one', (tester) async {
    final api = _FakeApi(_review());
    await tester.pumpWidget(_app(api, const VendorTdsReviewScreen()));
    await tester.pumpAndSettle();
    expect(find.text('2 of 3 need attention'), findsOneWidget);
    expect(find.text('No Type Co'), findsOneWidget);
    expect(find.text('Fine Co'), findsNothing); // problems only, by default
    expect(find.textContaining('the PAN suggests Private Limited'), findsOneWidget);

    await tester.tap(find.text('Apply suggestion'));
    await tester.pump(const Duration(seconds: 1));
    expect(api.applied.single.$1, false);
    expect(api.applied.single.$2, ['1:private_limited:194C']);
  });

  testWidgets('all suggested fixes can be applied together after a confirmation', (tester) async {
    final api = _FakeApi(_review());
    await tester.pumpWidget(_app(api, const VendorTdsReviewScreen()));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('tds-apply-all')));
    await tester.pumpAndSettle();
    expect(api.applied, isEmpty); // nothing until confirmed
    await tester.tap(find.text('Apply to all'));
    await tester.pump(const Duration(seconds: 1));
    expect(api.applied.single.$1, true);
    expect(api.applied.single.$2, isEmpty);
  });

  testWidgets('a manager can see the review but not change the master', (tester) async {
    await tester.pumpWidget(_app(_FakeApi(_review()), const VendorTdsReviewScreen(), user: _manager));
    await tester.pumpAndSettle();
    expect(find.text('No Type Co'), findsOneWidget);
    expect(find.byKey(const Key('tds-apply-all')), findsNothing);
    expect(find.text('Apply suggestion'), findsNothing);
  });

  testWidgets('everything set up reads as such', (tester) async {
    final api = _FakeApi({'total': 1, 'with_issues': 0, 'fixable': 0, 'vendors': [_row('3', 'Fine Co', type: 'llp', section: '194C')]});
    await tester.pumpWidget(_app(api, const VendorTdsReviewScreen()));
    await tester.pumpAndSettle();
    expect(find.text('All 1 vendors are set up'), findsOneWidget);
    expect(find.text('Nothing to fix'), findsOneWidget);
  });

  testWidgets('the import previews the file, shows what was worked out, then imports', (tester) async {
    tester.view.physicalSize = const Size(800, 1800);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.reset);
    final api = _FakeApi(_review());
    await tester.pumpWidget(_app(
        api, VendorsImportScreen(pickFile: () async => (name: 'vendors.csv', bytes: Uint8List.fromList([1, 2, 3])))));
    await tester.tap(find.byKey(const Key('vendors-import-choose')));
    await tester.pumpAndSettle();
    expect(api.imports, [true]); // checked, not saved
    expect(find.textContaining('Type worked out from its PAN'), findsOneWidget);
    expect(find.textContaining('already exists; skipped'), findsOneWidget);
    expect(find.text('1 already in the master'), findsOneWidget);

    await tester.tap(find.byKey(const Key('vendors-import-go')));
    await tester.pumpAndSettle();
    expect(api.imports, [true, false]);
    expect(find.text('1 added'), findsOneWidget);
  });
}
