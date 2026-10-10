import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/auth/domain/entities/user_entity.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/features/governance/data/governance_api.dart';
import 'package:ar_society_app/features/governance/presentation/screens/documents_screen.dart';
import 'package:ar_society_app/features/governance/presentation/screens/meetings_screen.dart';
import 'package:ar_society_app/features/governance/presentation/screens/polls_screen.dart';

UserEntity _user(String role) => UserEntity(id: 'u', email: 'u@t.com', fullName: 'U', roles: [role], societyId: 's1');

Widget _wrap(Widget screen, String role, List<Override> overrides) => ProviderScope(
      overrides: [currentUserProvider.overrideWithValue(_user(role)), ...overrides],
      child: MaterialApp(theme: AppTheme.lightTheme, home: screen),
    );

Map<String, dynamic> _poll({bool canVote = true, bool visible = false, bool open = true, String? mine}) => {
      'id': 'p1', 'society_id': 's1', 'question': 'Repaint the building?', 'description': null,
      'closes_on': '2030-01-01', 'open': open, 'closed_early': false, 'results_after': 'vote',
      'votes': 2, 'flats': 5, 'can_vote': canVote, 'my_option_id': mine, 'results_visible': visible,
      'options': [
        {'id': 'o1', 'label': 'Yes', 'votes': visible ? 2 : null},
        {'id': 'o2', 'label': 'No', 'votes': visible ? 0 : null},
      ],
    };

void main() {
  void phone(WidgetTester t) {
    t.view.physicalSize = const Size(420, 2000);
    t.view.devicePixelRatio = 1.0;
    addTearDown(t.view.resetPhysicalSize);
    addTearDown(t.view.resetDevicePixelRatio);
  }

  testWidgets('a resident who can vote sees the options and a Vote button, but no results yet', (t) async {
    phone(t);
    await t.pumpWidget(_wrap(const PollsScreen(), 'Resident',
        [pollsProvider('s1').overrideWith((ref) async => [Poll.fromJson(_poll())])]));
    await t.pumpAndSettle();
    expect(find.text('Repaint the building?'), findsOneWidget);
    expect(find.text('Vote'), findsOneWidget);
    expect(find.textContaining('Results show after you vote'), findsOneWidget);
    expect(find.text('New poll'), findsNothing);                 // only the office starts polls
  });

  testWidgets('after voting the totals and the person\'s own choice show; the office can close the poll', (t) async {
    phone(t);
    await t.pumpWidget(_wrap(const PollsScreen(), 'Society Admin', [
      pollsProvider('s1').overrideWith((ref) async => [Poll.fromJson(_poll(canVote: false, visible: true, mine: 'o1'))]),
    ]));
    await t.pumpAndSettle();
    expect(find.textContaining('✓ your vote'), findsOneWidget);
    expect(find.text('2 (100%)'), findsOneWidget);
    expect(find.text('Close now'), findsOneWidget);
    expect(find.text('New poll'), findsOneWidget);
  });

  testWidgets('meetings: empty state for a resident, schedule button for the office', (t) async {
    phone(t);
    await t.pumpWidget(_wrap(const MeetingsScreen(), 'Resident', [meetingsProvider('s1').overrideWith((ref) async => [])]));
    await t.pumpAndSettle();
    expect(find.text('No meetings yet'), findsOneWidget);
    expect(find.text('Schedule meeting'), findsNothing);

    await t.pumpWidget(_wrap(const MeetingsScreen(), 'Society Admin', [meetingsProvider('s1').overrideWith((ref) async => [])]));
    await t.pumpAndSettle();
    expect(find.text('Schedule meeting'), findsOneWidget);
  });

  testWidgets('documents are grouped by kind and committee-only ones are marked', (t) async {
    phone(t);
    final docs = [
      SocietyDoc.fromJson({'id': 'd1', 'title': 'Society bye-laws', 'category': 'bylaws', 'visibility': 'everyone',
        'file_name': 'b.pdf', 'mime_type': 'application/pdf', 'size_bytes': 2048, 'created_at': '2026-10-09T04:00:00Z'}),
      SocietyDoc.fromJson({'id': 'd2', 'title': 'Audit draft', 'category': 'audit', 'visibility': 'committee',
        'file_name': 'a.pdf', 'mime_type': 'application/pdf', 'size_bytes': 3 * 1024 * 1024, 'created_at': '2026-10-09T04:00:00Z'}),
    ];
    await t.pumpWidget(_wrap(const DocumentsScreen(), 'Society Admin', [documentsProvider('s1').overrideWith((ref) async => docs)]));
    await t.pumpAndSettle();
    expect(find.text('Bye-laws'), findsOneWidget);
    expect(find.text('Audit and accounts'), findsOneWidget);
    expect(find.text('Committee'), findsOneWidget);
    expect(find.textContaining('3.0 MB'), findsOneWidget);
    expect(find.text('Add document'), findsOneWidget);
  });
}
