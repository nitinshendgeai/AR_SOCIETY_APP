import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/auth/domain/entities/user_entity.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/features/certificates/data/certificates_api.dart';
import 'package:ar_society_app/features/certificates/presentation/screens/certificates_screen.dart';

UserEntity _user(String role) => UserEntity(
    id: 'u', email: 'u@t.com', fullName: 'U', roles: [role], societyId: 's1');

Map<String, dynamic> _req(String status, {String kind = 'noc_sale'}) => {
      'id': 'r1',
      'society_id': 's1',
      'flat_id': 'f1',
      'flat': 'A 101',
      'applicant_name': 'Asha Rao',
      'kind': kind,
      'title': 'No Objection Certificate for sale / transfer of flat',
      'purpose': 'Selling to a relative',
      'party_name': 'Mr Kulkarni',
      'status': status,
      'decided_on': status == 'pending' ? null : '2026-10-09',
      'decision_note': null,
      'certificate_no': status == 'approved' ? 'NOC/2026-27/0001' : null,
      'dues_at_decision': 0.0,
      'created_at': '2026-10-09T04:00:00Z',
    };

Widget _wrap(String role, List<Map<String, dynamic>> items) => ProviderScope(
      overrides: [
        currentUserProvider.overrideWithValue(_user(role)),
        certificatesProvider('s1').overrideWith(
            (ref) async => [for (final j in items) CertificateRequest.fromJson(j)]),
      ],
      child: MaterialApp(theme: AppTheme.lightTheme, home: const CertificatesScreen()),
    );

void main() {
  void phone(WidgetTester t) {
    t.view.physicalSize = const Size(420, 2000);
    t.view.devicePixelRatio = 1.0;
    addTearDown(t.view.resetPhysicalSize);
    addTearDown(t.view.resetDevicePixelRatio);
  }

  testWidgets('the office sees who asked and can approve or decline a waiting request', (t) async {
    phone(t);
    await t.pumpWidget(_wrap('Society Admin', [_req('pending')]));
    await t.pumpAndSettle();
    expect(find.textContaining('Asha Rao'), findsOneWidget);
    expect(find.text('Waiting'), findsOneWidget);
    await t.tap(find.textContaining('No Objection'));
    await t.pumpAndSettle();
    expect(find.text('Approve'), findsOneWidget);
    expect(find.text('Decline'), findsOneWidget);
    expect(find.text('Withdraw request'), findsNothing);
  });

  testWidgets('a resident can withdraw a waiting request but not decide it', (t) async {
    phone(t);
    await t.pumpWidget(_wrap('Resident', [_req('pending')]));
    await t.pumpAndSettle();
    await t.tap(find.textContaining('No Objection'));
    await t.pumpAndSettle();
    expect(find.text('Withdraw request'), findsOneWidget);
    expect(find.text('Approve'), findsNothing);
  });

  testWidgets('an approved certificate shows its number and a download button', (t) async {
    phone(t);
    await t.pumpWidget(_wrap('Resident', [_req('approved')]));
    await t.pumpAndSettle();
    expect(find.text('No. NOC/2026-27/0001'), findsOneWidget);
    await t.tap(find.textContaining('No Objection'));
    await t.pumpAndSettle();
    expect(find.text('Download PDF'), findsOneWidget);
  });

  testWidgets('empty state differs for members and the office; anyone can start a request', (t) async {
    phone(t);
    await t.pumpWidget(_wrap('Resident', []));
    await t.pumpAndSettle();
    expect(find.text('No requests yet'), findsOneWidget);
    expect(find.textContaining('Ask for a NOC'), findsOneWidget);
    await t.tap(find.text('Request certificate'));
    await t.pumpAndSettle();
    expect(find.text('Request a certificate'), findsOneWidget);
    expect(find.text('Send request'), findsOneWidget);
  });
}
