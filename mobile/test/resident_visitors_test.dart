import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/auth/domain/entities/user_entity.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/features/visitor/data/datasources/visitor_remote_datasource.dart';
import 'package:ar_society_app/features/visitor/data/repositories/visitor_repository.dart';
import 'package:ar_society_app/features/visitor/domain/entities/visitor_entities.dart';
import 'package:ar_society_app/features/visitor/presentation/providers/visitor_providers.dart';
import 'package:ar_society_app/features/visitor/presentation/screens/visitor_list_screen.dart';

VisitorEntity _visitor(String name, VisitorStatus status, {DateTime? expected}) => VisitorEntity(
      id: name,
      name: name,
      mobile: '9876543210',
      visitorType: VisitorType.guest,
      societyId: 's1',
      status: status,
      expectedArrival: expected,
      checkedInAt: status == VisitorStatus.checkedIn || status == VisitorStatus.checkedOut ? DateTime(2026, 11, 5, 10) : null,
      checkedOutAt: status == VisitorStatus.checkedOut ? DateTime(2026, 11, 5, 12) : null,
      logs: const [],
      createdAt: DateTime(2026, 11, 5, 9),
    );

class _FakeRepo extends VisitorRepository {
  final List<VisitorEntity> mine;
  _FakeRepo(this.mine) : super(ds: VisitorRemoteDataSource(dio: Dio()));

  @override
  Future<VisitorResult<List<VisitorEntity>>> getMyVisitors() async => VisitorSuccess(mine);

  @override
  Future<VisitorResult<List<VisitorEntity>>> getPendingApprovals() async => VisitorSuccess(const []);
}

Widget _app(List<VisitorEntity> mine) => ProviderScope(
      overrides: [
        currentUserProvider.overrideWithValue(const UserEntity(
            id: 'u', email: 'r@x.c', fullName: 'R', roles: ['Resident'], societyId: 's1', termsAccepted: true)),
        visitorRepositoryProvider.overrideWithValue(_FakeRepo(mine)),
      ],
      child: MaterialApp(theme: AppTheme.lightTheme, home: const VisitorListScreen(isMy: true)),
    );

void main() {
  final visitors = [
    _visitor('Asha Expected', VisitorStatus.approved, expected: DateTime(2026, 11, 7, 17, 30)),
    _visitor('Ravi Inside', VisitorStatus.checkedIn),
    _visitor('Meena Gone', VisitorStatus.checkedOut),
  ];

  testWidgets('a resident sees Expected, Inside and History with the right visitors in each', (tester) async {
    await tester.pumpWidget(_app(visitors));
    await tester.pumpAndSettle();

    expect(find.text('Expected'), findsOneWidget);
    expect(find.text('Inside'), findsOneWidget);
    expect(find.text('History'), findsOneWidget);
    expect(find.text('Invite guest'), findsOneWidget);          // the button

    expect(find.text('Asha Expected'), findsOneWidget);
    expect(find.textContaining('Expected 7 Nov'), findsOneWidget);
    expect(find.text('Ravi Inside'), findsNothing);
    expect(find.text('Meena Gone'), findsNothing);

    await tester.tap(find.text('Inside'));
    await tester.pumpAndSettle();
    expect(find.text('Ravi Inside'), findsOneWidget);
    expect(find.textContaining('Inside since'), findsOneWidget);

    await tester.tap(find.text('History'));
    await tester.pumpAndSettle();
    expect(find.text('Meena Gone'), findsOneWidget);
    expect(find.text('Invite again'), findsOneWidget);
  });

  testWidgets('empty Expected tab suggests inviting a guest', (tester) async {
    await tester.pumpWidget(_app(const []));
    await tester.pumpAndSettle();
    expect(find.text('No one expected'), findsOneWidget);
  });
}
