import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ar_society_app/features/resident_master/presentation/screens/resident_login_status_screen.dart';

ResidentLoginRow _row(String id, String name, String status, {String? phone, String? loginName}) => ResidentLoginRow(
      id: id,
      fullName: name,
      residentType: 'owner',
      flatLabel: 'A / 10$id',
      status: status,
      phone: phone,
      loginName: loginName,
    );

Widget _app(ResidentLoginReport report) => ProviderScope(
      overrides: [residentLoginReportProvider.overrideWith((ref) async => report)],
      child: const MaterialApp(home: ResidentLoginStatusScreen()),
    );

void main() {
  final report = ResidentLoginReport({
    'linked': 1,
    'login_disabled': 0,
    'login_unlinked': 1,
    'no_login': 1,
    'no_mobile': 1,
    'total': 4,
    'needs_attention': 3,
  }, [
    _row('1', 'Linked Owner', 'linked', phone: '9000000001'),
    _row('2', 'Unlinked Owner', 'login_unlinked', phone: '9000000002', loginName: 'Unlinked Login'),
    _row('3', 'No Login Owner', 'no_login', phone: '9000000003'),
    _row('4', 'No Mobile Owner', 'no_mobile'),
  ]);

  testWidgets('it counts who can sign in and lists only the residents who cannot, until All is chosen', (tester) async {
    await tester.pumpWidget(_app(report));
    await tester.pumpAndSettle();

    expect(find.text('1 of 4 residents can sign in. 3 cannot.'), findsOneWidget);
    expect(find.textContaining('Unlinked Owner'), findsOneWidget);
    expect(find.textContaining('No Login Owner'), findsOneWidget);
    expect(find.textContaining('No Mobile Owner'), findsOneWidget);
    expect(find.textContaining('Linked Owner'), findsNothing);
    // A login with the resident's own mobile number is named, ready to link
    expect(find.textContaining('Login "Unlinked Login" has this mobile number'), findsOneWidget);

    await tester.tap(find.byKey(const ValueKey('login-filter-all')));
    await tester.pumpAndSettle();
    expect(find.textContaining('Linked Owner'), findsOneWidget);
  });

  testWidgets('a status chip narrows the list to that status and search narrows it further', (tester) async {
    await tester.pumpWidget(_app(report));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const ValueKey('login-filter-no_mobile')));
    await tester.pumpAndSettle();
    expect(find.textContaining('No Mobile Owner'), findsOneWidget);
    expect(find.textContaining('No Login Owner'), findsNothing);

    await tester.tap(find.byKey(const ValueKey('login-filter-all')));
    await tester.pumpAndSettle();
    await tester.enterText(find.byType(TextField), '9000000003');
    await tester.pumpAndSettle();
    expect(find.textContaining('No Login Owner'), findsOneWidget);
    expect(find.textContaining('Linked Owner'), findsNothing);
  });
}
