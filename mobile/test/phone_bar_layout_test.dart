import 'dart:io';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ar_society_app/core/layout/phone_bottom_bar.dart';
import 'package:ar_society_app/core/navigation/app_menu.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/auth/domain/entities/user_entity.dart';
import 'package:ar_society_app/features/visitor/presentation/providers/visitor_providers.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';

const _resident = UserEntity(id: 'u', email: 'u@t.com', fullName: 'U', roles: ['Resident'], societyId: 's1');

/// A real phone: 411 dp wide, with the text set larger (as in the screenshots that showed "Complain / ts").
Widget _phone(Widget child, {double textScale = 1.3}) => MediaQuery(
      data: MediaQueryData(size: const Size(411, 860), textScaler: TextScaler.linear(textScale)),
      child: child,
    );

/// The app's own font. Without it the test draws every letter as a wide square and labels wrap that never would.
Future<void> _loadInter() async {
  final loader = FontLoader('Inter')
    ..addFont(Future.value(ByteData.sublistView(File('assets/fonts/Inter-Variable.ttf').readAsBytesSync())));
  await loader.load();
}

void main() {
  setUpAll(_loadInter);

  testWidgets('five bottom-bar labels, including Complaints, stay on one line at large text', (t) async {
    t.view.physicalSize = const Size(411, 860);
    t.view.devicePixelRatio = 1;
    addTearDown(t.view.resetPhysicalSize);
    addTearDown(t.view.resetDevicePixelRatio);
    const tabs = [
      PhoneTab('Home', Icons.home_rounded, '/home'),
      PhoneTab('Bills', Icons.description_rounded, '/bills'),
      PhoneTab('Visitors', Icons.meeting_room_rounded, '/visitors'),
      PhoneTab('Complaints', Icons.report_problem_rounded, '/complaints'),
    ];
    for (final scale in [1.0, 1.3, 1.6]) {
      await t.pumpWidget(ProviderScope(
        overrides: [pendingVisitorApprovalsProvider.overrideWith((ref) => Stream.value(const []))],
        child: _phone(
          MaterialApp(
            theme: AppTheme.lightTheme,
            home: const Scaffold(
              bottomNavigationBar:
                  PhoneBottomBar(location: '/home', user: _resident, tabs: tabs, menu: <AppMenuCategory>[]),
            ),
          ),
          textScale: scale,
        ),
      ));
      await t.pumpAndSettle();
      // "Home" cannot wrap, so its height is one line; a label as tall as two lines of it has wrapped.
      final oneLine = t.renderObject<RenderParagraph>(find.text('Home')).size.height;
      for (final label in ['Bills', 'Visitors', 'Complaints', 'More']) {
        final height = t.renderObject<RenderParagraph>(find.text(label)).size.height;
        expect(height, lessThan(oneLine * 1.5), reason: '"$label" wrapped at text scale $scale');
      }
      // One line of label means the bar keeps its intended height instead of growing.
      expect(t.getSize(find.byType(NavigationBar)).height, lessThanOrEqualTo(90), reason: 'text scale $scale');
    }
  });

  testWidgets('the Summary tiles are not taller than their content needs when none has a note', (t) async {
    t.view.physicalSize = const Size(411, 860);
    t.view.devicePixelRatio = 1;
    addTearDown(t.view.resetPhysicalSize);
    addTearDown(t.view.resetDevicePixelRatio);
    await t.pumpWidget(MaterialApp(
      theme: AppTheme.lightTheme,
      home: const Scaffold(
        body: KpiGrid(cards: [
          KpiCard(icon: Icons.report, label: 'Open Complaints', value: '0', color: Colors.red),
          KpiCard(icon: Icons.person, label: 'Visitors Waiting', value: '0', color: Colors.blue),
        ]),
      ),
    ));
    await t.pumpAndSettle();
    expect(t.getSize(find.byType(KpiCard).first).height, lessThan(130));
  });
}
