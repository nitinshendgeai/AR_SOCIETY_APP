import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ar_society_app/core/navigation/app_menu.dart';
import 'package:ar_society_app/core/navigation/route_access.dart';
import 'package:ar_society_app/features/auth/domain/entities/user_entity.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/features/vendor/data/vendors_work_api.dart';
import 'package:ar_society_app/features/vendor/presentation/providers/vendors_work_providers.dart';
import 'package:ar_society_app/features/vendor/presentation/screens/vendor_master_screen.dart';

const _admin = UserEntity(id: 'u1', email: 'a@b.c', fullName: 'Asha', roles: ['Society Admin'], societyId: 's1', termsAccepted: true);
const _manager = UserEntity(id: 'u2', email: 'm@b.c', fullName: 'Manu', roles: ['Manager'], societyId: 's1', termsAccepted: true);

VendorRecord _v(String id, String name, {String? gst, String? pan}) => VendorRecord.fromJson({
      'id': id, 'vendor_code': 'VND-$id', 'company_name': name, 'mobile': '98765432$id$id', 'category': 'housekeeping',
      'status': 'active', 'gst_number': gst, 'pan_number': pan,
    });

Widget _app(UserEntity user) => ProviderScope(
      overrides: [
        currentUserProvider.overrideWithValue(user),
        vendorRecordsProvider.overrideWith((ref, id) async => [
              _v('11', 'Sparkle Services', pan: 'ABCPK1234F'),
              _v('22', 'Shield Security', gst: '27AABCS1234P1Z5'),
            ]),
      ],
      child: const MaterialApp(home: VendorMasterScreen()),
    );

void main() {
  test('Vendor Master is its own menu item, guarded by its own form code', () {
    final items = [for (final c in appMenuCategories) ...c.items];
    final item = items.firstWhere((i) => i.label == 'Vendor Master');
    expect(item.formCode, 'vendor_master');
    expect(formCodeForPath(item.route!), 'vendor_master');
    expect(formCodeForPath('/vendors/import'), 'vendor_master');
    expect(formCodeForPath('/vendors/tds-review'), 'vendor_master');
    expect(formCodeForPath('/vendors/work'), 'vendors'); // Vendors & Work keeps its own
  });

  testWidgets('the committee sees the vendors with search, Add, Import and TDS review', (tester) async {
    await tester.pumpWidget(_app(_admin));
    await tester.pumpAndSettle();
    expect(find.textContaining('Sparkle Services'), findsOneWidget);
    expect(find.textContaining('Shield Security'), findsOneWidget);
    expect(find.byKey(const Key('vendors-import')), findsOneWidget);
    expect(find.byKey(const Key('vendors-tds-review')), findsOneWidget);
    expect(find.byKey(const Key('vendor-add')), findsOneWidget);
  });

  testWidgets('search narrows the list by name, GSTIN or PAN', (tester) async {
    await tester.pumpWidget(_app(_admin));
    await tester.pumpAndSettle();
    await tester.enterText(find.byKey(const Key('vendor-search')), 'abcpk');
    await tester.pumpAndSettle();
    expect(find.textContaining('Sparkle Services'), findsOneWidget);
    expect(find.textContaining('Shield Security'), findsNothing);
    await tester.enterText(find.byKey(const Key('vendor-search')), '27AABCS');
    await tester.pumpAndSettle();
    expect(find.textContaining('Shield Security'), findsOneWidget);
    expect(find.textContaining('Sparkle Services'), findsNothing);
    await tester.enterText(find.byKey(const Key('vendor-search')), 'nothing like this');
    await tester.pumpAndSettle();
    expect(find.textContaining('No vendor matches'), findsOneWidget);
  });

  testWidgets('a manager can look vendors up but not add, import or review', (tester) async {
    await tester.pumpWidget(_app(_manager));
    await tester.pumpAndSettle();
    expect(find.textContaining('Sparkle Services'), findsOneWidget);
    expect(find.byKey(const Key('vendors-import')), findsNothing);
    expect(find.byKey(const Key('vendors-tds-review')), findsNothing);
    expect(find.byKey(const Key('vendor-add')), findsNothing);
  });
}
