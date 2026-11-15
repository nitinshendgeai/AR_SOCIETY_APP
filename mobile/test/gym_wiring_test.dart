import 'dart:io';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:ar_society_app/core/config/edition.dart';
import 'package:ar_society_app/core/layout/phone_bottom_bar.dart' show activePhoneTab;
import 'package:ar_society_app/core/navigation/app_menu.dart';
import 'package:ar_society_app/core/navigation/route_access.dart';
import 'package:ar_society_app/core/router/app_router.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/auth/domain/entities/user_entity.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/features/complaint/presentation/providers/complaint_providers.dart';
import 'package:ar_society_app/features/onboarding/presentation/providers/trial_status_provider.dart';
import 'package:ar_society_app/features/staff/data/datasources/staff_remote_datasource.dart';
import 'package:ar_society_app/features/staff/data/repositories/staff_repository.dart';
import 'package:ar_society_app/features/staff/presentation/providers/staff_providers.dart';
import 'package:ar_society_app/features/staff/presentation/screens/staff_home_screen.dart';
import 'package:ar_society_app/features/users/presentation/providers/user_providers.dart';

UserEntity _user(String role) =>
    UserEntity(id: 'u', email: 'u@x.c', fullName: 'Ravi Kale', roles: [role], societyId: 's1', termsAccepted: true);

/// What the server grants a Gym Trainer (see FORM_ROLE_GRANTS): the usual member screens and the gym's book.
const _trainerCodes = {'gym_desk', 'visitors', 'complaints', 'notices', 'amenities', 'meetings', 'polls', 'documents', 'certificates', 'parcels', 'domestic_help'};

Future<void> _loadInter() async {
  final loader = FontLoader('Inter')
    ..addFont(Future.value(ByteData.sublistView(File('assets/fonts/Inter-Variable.ttf').readAsBytesSync())));
  await loader.load();
}

void main() {
  setUpAll(_loadInter);
  group('the Gym Trainer\'s phone', () {
    test('Gym is the first tab after Home, then Notices and Complaints', () {
      final tabs = phoneTabsFor(_user('Gym Trainer'), _trainerCodes);
      expect(tabs.map((t) => t.label), ['Home', 'Gym', 'Notices', 'Complaints']);
      expect(tabs[1].route, AppRoutes.gym);
    });

    test('the other staff roles have no Gym tab (they are not granted the screen)', () {
      for (final role in ['Security Staff', 'Technical Staff', 'Housekeeping Staff']) {
        final granted = _trainerCodes.difference({'gym_desk'});
        expect(phoneTabsFor(_user(role), granted).map((t) => t.label), isNot(contains('Gym')), reason: role);
      }
    });

    test('the tab stays lit on the check-in and report pages', () {
      final tabs = phoneTabsFor(_user('Gym Trainer'), _trainerCodes);
      expect(activePhoneTab(tabs, AppRoutes.gym), 1);
      expect(activePhoneTab(tabs, AppRoutes.gymCheckIn), 1);
      expect(activePhoneTab(tabs, AppRoutes.gymReport), 1);
    });

    test('More lists Gym attendance, under Operations, for whoever is granted it', () {
      final groups = visibleMenuCategories({'gym_desk'}, user: _user('Gym Trainer'), fieldEdition: true);
      expect([for (final g in groups) for (final i in g.items) i.label], contains('Gym attendance'));
      final none = visibleMenuCategories({'visitors'}, user: _user('Gym Trainer'), fieldEdition: true);
      expect([for (final g in none) for (final i in g.items) i.label], isNot(contains('Gym attendance')));
    });

    test('the field build keeps the Gym screen for gym trainers (and the web app can show it to the office)', () {
      expect(AppEdition.fieldFormCodes, contains('gym_desk'));
      expect(AppEdition.allowsUser(_user('Gym Trainer')), isTrue);
    });

    test('the gym addresses are guarded by the gym form code', () {
      for (final p in [AppRoutes.gym, AppRoutes.gymCheckIn, AppRoutes.gymReport, '/gym/anything']) {
        expect(formCodeForPath(p), 'gym_desk', reason: p);
      }
    });
  });

  group('the Staff Portal', () {
    Widget app(UserEntity user, Set<String> codes) {
      final router = GoRouter(initialLocation: '/', routes: [
        GoRoute(path: '/', builder: (_, __) => const StaffHomeScreen()),
        GoRoute(path: AppRoutes.gym, builder: (_, __) => const Scaffold(body: Text('the gym desk'))),
      ]);
      return ProviderScope(
        overrides: [
          currentUserProvider.overrideWithValue(user),
          myFormCodesProvider.overrideWith((ref) async => codes.toList()),
          staffRepositoryProvider.overrideWithValue(StaffRepository(ds: StaffRemoteDataSource(dio: Dio()))),
          societyInfoProvider.overrideWith((ref) async => const SocietyInfo(id: 's1', name: 'Shree CHS')),
          myOpenComplaintsCountProvider.overrideWith((ref) async => 0),
        ],
        child: MaterialApp.router(theme: AppTheme.lightTheme, routerConfig: router),
      );
    }

    testWidgets('a Gym Trainer sees a Gym attendance card that opens the desk', (t) async {
      t.view.physicalSize = const Size(900, 2000);
      t.view.devicePixelRatio = 2;
      addTearDown(t.view.resetPhysicalSize);
      addTearDown(t.view.resetDevicePixelRatio);
      await t.pumpWidget(app(_user('Gym Trainer'), _trainerCodes));
      await t.pumpAndSettle();
      expect(find.text('Gym attendance'), findsOneWidget);
      await t.tap(find.text('Gym attendance'));
      await t.pumpAndSettle();
      expect(find.text('the gym desk'), findsOneWidget);
    });

    testWidgets('someone without the grant sees no such card', (t) async {
      t.view.physicalSize = const Size(900, 2000);
      t.view.devicePixelRatio = 2;
      addTearDown(t.view.resetPhysicalSize);
      addTearDown(t.view.resetDevicePixelRatio);
      await t.pumpWidget(app(_user('Technical Staff'), _trainerCodes.difference({'gym_desk'})));
      await t.pumpAndSettle();
      expect(find.text('Gym attendance'), findsNothing);
    });
  });
}
