import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ar_society_app/features/onboarding/domain/registration_result.dart';
import 'package:ar_society_app/features/onboarding/presentation/screens/trial_success_screen.dart';

// A new society's first four accounts each have their own password, shown once on this screen.
const _result = RegistrationResult(
  societyId: 's1',
  societyName: 'Green Park CHS',
  societyCode: 'GPCHS',
  trialEndDate: '2026-11-23',
  trialDays: 30,
  message: 'ok',
  credentials: [
    RegistrationCredential(role: 'Society Admin', email: 'admin@gpchs.com', password: 'pw-for-admin'),
    RegistrationCredential(role: 'Committee Chairman', email: 'chairman@gpchs.com', password: 'pw-for-chairman'),
    RegistrationCredential(role: 'Committee Secretary', email: 'secretary@gpchs.com', password: 'pw-for-secretary'),
    RegistrationCredential(role: 'Committee Treasurer', email: 'treasurer@gpchs.com', password: 'pw-for-treasurer'),
  ],
);

void main() {
  testWidgets('each account is listed with its own password, not "all use the same"', (t) async {
    t.view.physicalSize = const Size(900, 2400);
    t.view.devicePixelRatio = 1.0;
    addTearDown(t.view.resetPhysicalSize);
    addTearDown(t.view.resetDevicePixelRatio);
    await t.pumpWidget(const ProviderScope(
      child: MaterialApp(home: TrialSuccessScreen(result: _result)),
    ));
    await t.pump();

    expect(find.textContaining('same password'), findsNothing);

    await t.tap(find.text('Additional Users Created'));       // the other three open
    await t.pumpAndSettle();
    expect(find.textContaining('each has its own password'), findsOneWidget);
    expect(find.text('pw-for-chairman'), findsNothing);          // masked until asked for
    await t.tap(find.text('Show passwords'));
    await t.pumpAndSettle();
    for (final pw in ['pw-for-chairman', 'pw-for-secretary', 'pw-for-treasurer']) {
      expect(find.text(pw), findsOneWidget, reason: pw);
    }
    expect(find.text('Admin@1234'), findsNothing);
  });
}
