import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/auth/data/datasources/auth_remote_datasource.dart';
import 'package:ar_society_app/features/auth/data/models/auth_models.dart';
import 'package:ar_society_app/features/auth/data/repositories/auth_repository.dart';
import 'package:ar_society_app/features/auth/domain/entities/society_choice.dart';
import 'package:ar_society_app/features/auth/domain/entities/user_entity.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/features/auth/presentation/screens/login_screen.dart';

const _alpha = SocietyChoice(societyId: 's1', societyName: 'Alpha Heights', roles: ['Resident']);
const _beta = SocietyChoice(societyId: 's2', societyName: 'Beta Towers', roles: ['Society Admin']);

/// Signing in finds two societies the first time; with a society chosen it signs in.
class _FakeRepo extends AuthRepository {
  final calls = <String?>[];

  _FakeRepo() : super(remote: AuthRemoteDataSource(dio: Dio()));

  @override
  Future<AuthResult<UserEntity>> login({required String email, required String password, String? societyId}) async {
    calls.add(societyId);
    if (societyId == null) return AuthNeedsChoice([_alpha, _beta]);
    return AuthSuccess(UserEntity(
      id: 'u1', email: 'a@b.com', fullName: 'A B', roles: const ['Resident'], societyId: societyId,
      societies: const [_alpha, _beta],
    ));
  }
}

void main() {
  test('/auth/me lists the societies a person can switch between', () {
    final u = UserModel.fromJson({
      'id': 'u1', 'email': 'a@b.com', 'full_name': 'A B', 'status': 'active', 'society_id': 's1',
      'roles': ['Resident'],
      'societies': [
        {'society_id': 's1', 'society_name': 'Alpha Heights', 'roles': ['Resident'], 'current': true},
        {'society_id': 's2', 'society_name': 'Beta Towers', 'roles': ['Society Admin'], 'current': false},
      ],
    }).toEntity();
    expect(u.societies.map((s) => s.societyName), ['Alpha Heights', 'Beta Towers']);
    expect(u.societies.first.current, isTrue);
    expect(u.societies.last.roleLabel, 'Society Admin');
    // A person in one society has nothing to switch to
    expect(UserModel.fromJson({
      'id': 'u1', 'email': 'a@b.com', 'full_name': 'A B', 'status': 'active', 'roles': ['Resident'],
    }).toEntity().societies, isEmpty);
  });

  testWidgets('sign-in with details in two societies asks which to open, then signs in to the chosen one', (tester) async {
    final repo = _FakeRepo();
    final container = ProviderContainer(overrides: [authRepositoryProvider.overrideWithValue(repo)]);
    addTearDown(container.dispose);
    await tester.pumpWidget(UncontrolledProviderScope(
      container: container,
      child: MaterialApp(theme: AppTheme.lightTheme, home: const LoginScreen()),
    ));
    await tester.pumpAndSettle();

    await container.read(authProvider.notifier).login(email: '9876543210', password: 'secret-pass');
    await tester.pumpAndSettle();
    expect(container.read(authProvider), isA<AuthChoosingSociety>());
    expect(find.text('Choose your society'), findsOneWidget);
    expect(find.text('Alpha Heights'), findsOneWidget);
    expect(find.text('Beta Towers'), findsOneWidget);
    expect(find.text('Society Admin'), findsOneWidget);

    await tester.tap(find.text('Beta Towers'));
    await tester.pumpAndSettle();
    expect(repo.calls, [null, 's2']);                       // the same details, now with the chosen society
    final state = container.read(authProvider);
    expect(state, isA<AuthAuthenticated>());
    expect((state as AuthAuthenticated).user.societyId, 's2');
  });

  testWidgets('Back from the society list returns to the sign-in form', (tester) async {
    final container = ProviderContainer(overrides: [authRepositoryProvider.overrideWithValue(_FakeRepo())]);
    addTearDown(container.dispose);
    await tester.pumpWidget(UncontrolledProviderScope(
      container: container,
      child: MaterialApp(theme: AppTheme.lightTheme, home: const LoginScreen()),
    ));
    await container.read(authProvider.notifier).login(email: '9876543210', password: 'secret-pass');
    await tester.pumpAndSettle();
    await tester.tap(find.text('Back'));
    await tester.pumpAndSettle();
    expect(container.read(authProvider), isA<AuthUnauthenticated>());
    expect(find.text('Welcome back'), findsOneWidget);
  });
}
