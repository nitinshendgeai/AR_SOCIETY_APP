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
import 'package:ar_society_app/features/visitor/presentation/widgets/gate_pass.dart';

VisitorEntity _guest({String? code = '482913', VisitorStatus status = VisitorStatus.approved}) => VisitorEntity(
      id: 'v1',
      name: 'Asha Guest',
      mobile: '9876500001',
      visitorType: VisitorType.guest,
      purpose: 'Dinner',
      societyId: 's1',
      flatNumber: '101',
      wingName: 'A',
      status: status,
      passCode: code,
      logs: const [],
      createdAt: DateTime(2026, 11, 6),
    );

class _FakeRepo extends VisitorRepository {
  final List<VisitorEntity> mine;
  final VisitorResult<VisitorEntity> verifyResult;
  String? verified;
  _FakeRepo({this.mine = const [], required this.verifyResult}) : super(ds: VisitorRemoteDataSource(dio: Dio()));

  @override
  Future<VisitorResult<List<VisitorEntity>>> getMyVisitors() async => VisitorSuccess(mine);

  @override
  Future<VisitorResult<List<VisitorEntity>>> listSocietyVisitors(String societyId, {int limit = 50}) async => VisitorSuccess(const []);

  @override
  Future<VisitorResult<List<VisitorEntity>>> getPendingApprovals() async => VisitorSuccess(const []);

  @override
  Future<VisitorResult<VisitorEntity>> verifyPass(String code) async {
    verified = code;
    return verifyResult;
  }
}

Widget _app(_FakeRepo repo, Widget home, {List<String> roles = const ['Resident']}) => ProviderScope(
      overrides: [
        currentUserProvider.overrideWithValue(
            UserEntity(id: 'u', email: 'x@y.c', fullName: 'U', roles: roles, societyId: 's1', termsAccepted: true)),
        visitorRepositoryProvider.overrideWithValue(repo),
      ],
      child: MaterialApp(theme: AppTheme.lightTheme, home: home),
    );

void main() {
  test('the message to send a guest carries the code', () {
    expect(gatePassMessage(_guest()), contains('482913'));
    expect(gatePassMessage(_guest()), contains('Asha Guest'));
  });

  testWidgets('the gate code is shown large with Copy and Share', (tester) async {
    await tester.pumpWidget(MaterialApp(
      theme: AppTheme.lightTheme,
      home: Builder(builder: (context) => Scaffold(body: Center(
          child: ElevatedButton(onPressed: () => showGatePass(context, _guest()), child: const Text('open'))))),
    ));
    await tester.tap(find.text('open'));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('gate-code')), findsOneWidget);
    expect(find.text('482913'), findsOneWidget);
    expect(find.text('Copy'), findsOneWidget);
    expect(find.text('Share'), findsOneWidget);
  });

  testWidgets('a visitor with no code shows nothing', (tester) async {
    await tester.pumpWidget(MaterialApp(
      theme: AppTheme.lightTheme,
      home: Builder(builder: (context) => Scaffold(body: Center(
          child: ElevatedButton(onPressed: () => showGatePass(context, _guest(code: null)), child: const Text('open'))))),
    ));
    await tester.tap(find.text('open'));
    await tester.pumpAndSettle();
    expect(find.byType(AlertDialog), findsNothing);
  });

  testWidgets("an invited guest's card offers the gate code to the resident", (tester) async {
    final repo = _FakeRepo(mine: [_guest()], verifyResult: VisitorFailure('x'));
    await tester.pumpWidget(_app(repo, const VisitorListScreen(isMy: true)));
    await tester.pumpAndSettle();
    expect(find.text('Gate code 482913'), findsOneWidget);
    await tester.tap(find.text('Gate code 482913'));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('gate-code')), findsOneWidget);
  });

  testWidgets('the guard keys in a code and sees who it belongs to', (tester) async {
    final repo = _FakeRepo(verifyResult: VisitorSuccess(_guest()));
    await tester.pumpWidget(_app(repo, const VisitorListScreen(societyId: 's1'), roles: const ['Security Staff']));
    await tester.pumpAndSettle();

    await tester.tap(find.byTooltip('Verify guest code'));
    await tester.pumpAndSettle();
    await tester.enterText(find.byKey(const Key('verify-code-field')), '482913');
    await tester.tap(find.text('Verify'));
    await tester.pumpAndSettle();

    expect(repo.verified, '482913');
    expect(find.text('Valid code'), findsOneWidget);
    expect(find.text('Asha Guest'), findsOneWidget);
    expect(find.textContaining('Visiting A-101'), findsOneWidget);
  });

  testWidgets('a wrong code says so', (tester) async {
    final repo = _FakeRepo(verifyResult: VisitorFailure('That code is not valid. It may be wrong, used, or expired'));
    await tester.pumpWidget(_app(repo, const VisitorListScreen(societyId: 's1'), roles: const ['Security Staff']));
    await tester.pumpAndSettle();
    await tester.tap(find.byTooltip('Verify guest code'));
    await tester.pumpAndSettle();
    await tester.enterText(find.byKey(const Key('verify-code-field')), '000000');
    await tester.tap(find.text('Verify'));
    await tester.pumpAndSettle();
    expect(find.textContaining('That code is not valid'), findsOneWidget);
    expect(find.text('Valid code'), findsNothing);
  });
}
