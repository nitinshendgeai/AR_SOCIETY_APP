import 'dart:math' as math;

import 'dart:ui' show Tristate;

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter/semantics.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/auth/domain/entities/user_entity.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/features/complaint/presentation/providers/complaint_providers.dart';
import 'package:ar_society_app/features/dashboard/gate_summary.dart';
import 'package:ar_society_app/features/dashboard/role_dashboards.dart';
import 'package:ar_society_app/features/staff/data/datasources/staff_remote_datasource.dart';
import 'package:ar_society_app/features/staff/data/repositories/staff_repository.dart';
import 'package:ar_society_app/features/staff/presentation/providers/staff_providers.dart';
import 'package:ar_society_app/features/users/presentation/providers/user_providers.dart';
import 'package:ar_society_app/features/visitor/domain/entities/visitor_entities.dart';
import 'package:ar_society_app/features/visitor/presentation/providers/visitor_providers.dart';

/// Automated checks only (Flutter's accessibility guidelines and semantics): they catch missing labels, small touch
/// targets and low contrast on these dashboards, not everything a screen-reader user or a keyboard user would meet.

UserEntity _user(String role, {String? societyId = 's1'}) => UserEntity(
    id: 'u1', email: 'u@example.com', fullName: 'Test User', roles: [role], societyId: societyId,
    enabledServices: const ['complaints', 'visitors', 'staff']);

Widget _app(Widget screen, UserEntity user, List<Override> overrides, {double textScale = 1.0}) => ProviderScope(
      overrides: [
        currentUserProvider.overrideWithValue(user),
        myFormCodesProvider.overrideWith((ref) async => const []),
        staffRepositoryProvider.overrideWithValue(StaffRepository(ds: StaffRemoteDataSource(dio: Dio()))),
        ...overrides,
      ],
      child: MaterialApp(
        theme: AppTheme.lightTheme,
        builder: (context, child) => MediaQuery(
          data: MediaQuery.of(context).copyWith(textScaler: TextScaler.linear(textScale)),
          child: child!,
        ),
        home: screen,
      ),
    );

List<Override> _resident({bool failing = false}) => [
      myOpenComplaintsCountProvider.overrideWith((ref) async => failing ? throw Exception('offline') : 3),
      pendingVisitorApprovalsProvider.overrideWith((ref) => Stream.value(const <VisitorEntity>[])),
    ];

List<Override> _security() => [
      gateSummaryProvider('s1').overrideWith((ref) async =>
          GateSummary.fromJson({'today': {'visitors_today': 12, 'checked_in_today': 9, 'visitors_inside': 4}, 'errors': <String>[]})),
    ];

void _size(WidgetTester t, {double w = 420, double h = 3000}) {
  t.view.physicalSize = Size(w, h);
  t.view.devicePixelRatio = 1.0;
  addTearDown(t.view.resetPhysicalSize);
  addTearDown(t.view.resetDevicePixelRatio);
}

Future<void> _settle(WidgetTester t) async {
  await t.pump();
  await t.pump(const Duration(milliseconds: 50));
  await t.pump(const Duration(seconds: 2));
}

void main() {
  group('semantics', () {
    testWidgets('a summary card is announced as one thing: its name and its value', (t) async {
      _size(t);
      final h = t.ensureSemantics();
      await t.pumpWidget(_app(const ResidentDashboardScreen(), _user('Resident'), _resident()));
      await _settle(t);

      expect(find.bySemanticsLabel('Open Complaints: 3'), findsOneWidget);
      expect(find.bySemanticsLabel('Visitors Waiting: 0'), findsOneWidget);
      h.dispose();
    });

    testWidgets('a card that failed to load says so and is a button that retries', (t) async {
      _size(t);
      final h = t.ensureSemantics();
      await t.pumpWidget(_app(const ResidentDashboardScreen(), _user('Resident'), _resident(failing: true)));
      await _settle(t);

      final node = find.bySemanticsLabel('Open Complaints: --, Could not load. Tap to retry');
      expect(node, findsOneWidget);
      final data = t.getSemantics(node).getSemanticsData();
      expect(data.flagsCollection.isButton, isTrue);
      expect(data.hasAction(SemanticsAction.tap), isTrue);
      h.dispose();
    });

    testWidgets('a quick action with nowhere to go is announced as unavailable, not as a working button', (t) async {
      _size(t);
      final h = t.ensureSemantics();
      // no society: "Log Visitor" has no society to log a visitor in
      await t.pumpWidget(_app(const SecurityDashboardScreen(), _user('Security Staff', societyId: null), const []));
      await _settle(t);

      final data = t.getSemantics(find.bySemanticsLabel('Log Visitor')).getSemanticsData();
      expect(data.flagsCollection.isEnabled, Tristate.isFalse);      // it has an enabled state, and it is off
      expect(data.hasAction(SemanticsAction.tap), isFalse);

      final ok = t.getSemantics(find.bySemanticsLabel('Visitor Log')).getSemanticsData();
      expect(ok.flagsCollection.isEnabled, Tristate.isTrue);
      h.dispose();
    });
  });

  group('Flutter accessibility guidelines', () {
    for (final (name, screen, user, overrides) in <(String, Widget, UserEntity, List<Override>)>[
      ('Resident dashboard', const ResidentDashboardScreen(), _user('Resident'), _resident()),
      ('Resident dashboard with a failed card', const ResidentDashboardScreen(), _user('Resident'), _resident(failing: true)),
      ('Security dashboard', const SecurityDashboardScreen(), _user('Security Staff'), _security()),
    ]) {
      testWidgets('$name: tappable things are at least 48 dp and have labels', (t) async {
        _size(t);
        final h = t.ensureSemantics();
        await t.pumpWidget(_app(screen, user, overrides));
        await _settle(t);
        await expectLater(t, meetsGuideline(androidTapTargetGuideline));
        await expectLater(t, meetsGuideline(iOSTapTargetGuideline));
        await expectLater(t, meetsGuideline(labeledTapTargetGuideline));
        h.dispose();
      });

      testWidgets('$name: text has enough contrast', (t) async {
        _size(t);
        final h = t.ensureSemantics();
        await t.pumpWidget(_app(screen, user, overrides));
        await _settle(t);
        await expectLater(t, meetsGuideline(textContrastGuideline));
        h.dispose();
      });
    }
  });

  group('contrast of the words a person must act on', () {
    double luminance(Color c) {
      double ch(double v) => v <= 0.03928 ? v / 12.92 : math.pow((v + 0.055) / 1.055, 2.4).toDouble();
      return 0.2126 * ch(c.r) + 0.7152 * ch(c.g) + 0.0722 * ch(c.b);
    }

    double ratio(Color a, Color b) {
      final la = luminance(a), lb = luminance(b);
      return (math.max(la, lb) + 0.05) / (math.min(la, lb) + 0.05);
    }

    // The automated text-contrast guideline reads the whole card as one node, so it cannot see this line; check
    // the colour the line is actually drawn in, against the card it sits on.
    testWidgets('"Could not load. Tap to retry" is readable against the card (WCAG AA, 4.5:1)', (t) async {
      _size(t);
      await t.pumpWidget(_app(const ResidentDashboardScreen(), _user('Resident'), _resident(failing: true)));
      await _settle(t);

      final note = t.widget<Text>(find.text('Could not load. Tap to retry'));
      expect(ratio(note.style!.color!, AppTheme.cardBg), greaterThanOrEqualTo(4.5));
    });
  });

  group('large text', () {
    for (final scale in [1.3, 2.0]) {
      testWidgets('the Resident dashboard lays out without overflow at ${scale}x text', (t) async {
        _size(t, h: 6000);
        await t.pumpWidget(_app(const ResidentDashboardScreen(), _user('Resident'), _resident(failing: true), textScale: scale));
        await _settle(t);
        expect(t.takeException(), isNull);        // an overflow would be reported as an exception
        expect(find.text('Open Complaints'), findsOneWidget);
      });

      testWidgets('the Security dashboard lays out without overflow at ${scale}x text', (t) async {
        _size(t, h: 6000);
        await t.pumpWidget(_app(const SecurityDashboardScreen(), _user('Security Supervisor'), _security(), textScale: scale));
        await _settle(t);
        expect(t.takeException(), isNull);
        expect(find.text('Inside Now'), findsOneWidget);
      });
    }
  });
}
