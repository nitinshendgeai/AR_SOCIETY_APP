import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/accounts/data/accounts_api.dart';
import 'package:ar_society_app/features/accounts/presentation/providers/accounts_providers.dart';
import 'package:ar_society_app/features/accounts/presentation/screens/accounts_screen.dart';
import 'package:ar_society_app/features/auth/domain/entities/user_entity.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';

Future<void> _loadInter() async {
  final loader = FontLoader('Inter')
    ..addFont(Future.value(ByteData.sublistView(File('assets/fonts/Inter-Variable.ttf').readAsBytesSync())));
  await loader.load();
}

void main() {
  setUpAll(_loadInter);

  testWidgets('on a phone the Accounts page links to All Registers, the TDS Ledger and Depreciation', (t) async {
    t.view.physicalSize = const Size(420, 4200);
    t.view.devicePixelRatio = 1.0;
    addTearDown(t.view.resetPhysicalSize);
    addTearDown(t.view.resetDevicePixelRatio);
    final summary = AccountsSummary.fromJson({'fy': '2026-27'});
    await t.pumpWidget(ProviderScope(
      overrides: [
        currentUserProvider.overrideWithValue(
            const UserEntity(id: 'u', email: 'u@t.com', fullName: 'U', roles: ['Manager'], societyId: 's1')),
        accountsSummaryProvider.overrideWith((ref, id) async => summary),
      ],
      child: MaterialApp(theme: AppTheme.lightTheme, home: const AccountsScreen()),
    ));
    await t.pumpAndSettle();
    for (final label in ['All Registers', 'TDS Ledger', 'Depreciation']) {
      expect(find.text(label), findsOneWidget, reason: label);
    }
  });
}
