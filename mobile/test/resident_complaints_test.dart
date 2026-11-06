import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/auth/domain/entities/user_entity.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/features/complaint/data/datasources/complaint_remote_datasource.dart';
import 'package:ar_society_app/features/complaint/data/repositories/complaint_repository.dart';
import 'package:ar_society_app/features/complaint/domain/entities/complaint_entities.dart';
import 'package:ar_society_app/features/complaint/presentation/providers/complaint_providers.dart';
import 'package:ar_society_app/features/complaint/presentation/screens/complaint_list_screen.dart';
import 'package:ar_society_app/features/complaint/presentation/widgets/complaint_progress.dart';

final _now = DateTime(2026, 11, 6, 12);

ComplaintListEntity _listed(String title, ComplaintStatus status, {String? who, int raisedDaysAgo = 3, DateTime? resolvedAt}) =>
    ComplaintListEntity(
      id: title,
      complaintNumber: 'C-${title.length}',
      title: title,
      category: ComplaintCategory.plumbing,
      priority: ComplaintPriority.medium,
      status: status,
      societyId: 's1',
      raisedBy: 'u',
      assignedToName: who,
      resolvedAt: resolvedAt,
      createdAt: _now.subtract(Duration(days: raisedDaysAgo)),
    );

ComplaintEntity _full(ComplaintStatus status, {String? who, String? reason, int reopened = 0}) => ComplaintEntity(
      id: 'c1',
      complaintNumber: 'C-1',
      title: 'Leaking tap',
      description: 'd',
      category: ComplaintCategory.plumbing,
      priority: ComplaintPriority.medium,
      status: status,
      societyId: 's1',
      raisedBy: 'u',
      assignedToName: who,
      rejectionReason: reason,
      reopenCount: reopened,
      createdAt: _now,
    );

class _FakeRepo extends ComplaintRepository {
  final List<ComplaintListEntity> mine;
  _FakeRepo(this.mine) : super(ds: ComplaintRemoteDataSource(dio: Dio()));

  @override
  Future<ComplaintResult<List<ComplaintListEntity>>> listMyComplaints() async => ComplaintSuccess(mine);
}

Widget _app(List<ComplaintListEntity> mine) => ProviderScope(
      overrides: [
        currentUserProvider.overrideWithValue(const UserEntity(
            id: 'u', email: 'r@x.c', fullName: 'R', roles: ['Resident'], societyId: 's1', termsAccepted: true)),
        complaintRepositoryProvider.overrideWithValue(_FakeRepo(mine)),
      ],
      child: MaterialApp(theme: AppTheme.lightTheme, home: const ComplaintListScreen(isMy: true)),
    );

void main() {
  group('plain-language status', () {
    test('each status is said in words a resident understands', () {
      expect(complaintStatusSentence(_full(ComplaintStatus.open)), contains('Waiting for the office'));
      expect(complaintStatusSentence(_full(ComplaintStatus.assigned, who: 'Raju')), 'Assigned to Raju. Work has not started yet.');
      expect(complaintStatusSentence(_full(ComplaintStatus.inProgress, who: 'Raju')), 'Raju is working on this.');
      expect(complaintStatusSentence(_full(ComplaintStatus.resolved)), contains('reopen it'));
      expect(complaintStatusSentence(_full(ComplaintStatus.reopened)), startsWith('Reopened'));
    });

    test('the steps run Raised, Assigned, In progress, Resolved; a rejected complaint is off the track', () {
      expect(complaintStep(ComplaintStatus.open), 0);
      expect(complaintStep(ComplaintStatus.reopened), 0);
      expect(complaintStep(ComplaintStatus.assigned), 1);
      expect(complaintStep(ComplaintStatus.inProgress), 2);
      expect(complaintStep(ComplaintStatus.resolved), 3);
      expect(complaintStep(ComplaintStatus.closed), 3);
      expect(complaintStep(ComplaintStatus.rejected), isNull);
    });

    test('ages are in whole days', () {
      expect(complaintAgo(_now, _now), 'today');
      expect(complaintAgo(_now.subtract(const Duration(days: 1)), _now), 'yesterday');
      expect(complaintAgo(_now.subtract(const Duration(days: 5)), _now), '5 days ago');
    });

    test('list notes say who has it and how long ago it was raised', () {
      expect(complaintListNote(_listed('a', ComplaintStatus.open), _now), 'Waiting to be assigned  ·  raised 3 days ago');
      expect(complaintListNote(_listed('a', ComplaintStatus.inProgress, who: 'Raju'), _now), 'Raju is on it  ·  raised 3 days ago');
      expect(complaintListNote(_listed('a', ComplaintStatus.resolved, resolvedAt: _now.subtract(const Duration(days: 1))), _now),
          'Resolved yesterday');
    });
  });

  testWidgets('the progress card shows the four steps and the sentence', (tester) async {
    await tester.pumpWidget(MaterialApp(
        theme: AppTheme.lightTheme,
        home: Scaffold(body: ComplaintProgressCard(complaint: _full(ComplaintStatus.inProgress, who: 'Raju', reopened: 2)))));
    for (final step in ['Raised', 'Assigned', 'In progress', 'Resolved']) {
      expect(find.text(step), findsOneWidget, reason: step);
    }
    expect(find.text('Raju is working on this.'), findsOneWidget);
    expect(find.text('Reopened 2 times'), findsOneWidget);
  });

  testWidgets('a rejected complaint shows the reason instead of the steps', (tester) async {
    await tester.pumpWidget(MaterialApp(
        theme: AppTheme.lightTheme,
        home: Scaffold(body: ComplaintProgressCard(complaint: _full(ComplaintStatus.rejected, reason: 'Duplicate')))));
    expect(find.text('This complaint was not taken up.'), findsOneWidget);
    expect(find.text('Reason: Duplicate'), findsOneWidget);
    expect(find.text('Raised'), findsNothing);
  });

  testWidgets("a resident's list splits Active and Done and says where each stands", (tester) async {
    await tester.pumpWidget(_app([
      _listed('Leaking tap', ComplaintStatus.inProgress, who: 'Raju'),
      _listed('Lift stuck', ComplaintStatus.open),
      _listed('Broken light', ComplaintStatus.resolved, resolvedAt: _now),
    ]));
    await tester.pumpAndSettle();

    expect(find.text('Active (2)'), findsOneWidget);
    expect(find.text('Done (1)'), findsOneWidget);
    expect(find.text('Leaking tap'), findsOneWidget);
    expect(find.text('Lift stuck'), findsOneWidget);
    expect(find.text('Broken light'), findsNothing);
    expect(find.textContaining('Raju is on it'), findsOneWidget);

    await tester.tap(find.text('Done (1)'));
    await tester.pumpAndSettle();
    expect(find.text('Broken light'), findsOneWidget);
    expect(find.text('Leaking tap'), findsNothing);
  });

  testWidgets('with nothing active it says so', (tester) async {
    await tester.pumpWidget(_app([_listed('Broken light', ComplaintStatus.closed)]));
    await tester.pumpAndSettle();
    expect(find.text('Nothing pending'), findsOneWidget);
  });
}
