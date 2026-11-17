import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ar_society_app/core/navigation/route_access.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/users/data/datasources/user_remote_datasource.dart';
import 'package:ar_society_app/features/users/data/models/user_admin_models.dart';
import 'package:ar_society_app/features/users/data/repositories/user_admin_repository.dart';
import 'package:ar_society_app/features/users/presentation/providers/user_providers.dart';
import 'package:ar_society_app/features/users/presentation/screens/roles_screen.dart';

class _FakeRepo extends UserAdminRepository {
  _FakeRepo(this.roles) : super(ds: UserRemoteDataSource(dio: Dio()));
  List<RoleModel> roles;
  final created = <(String, String?, String?)>[];
  final renamed = <(String, String?, String?)>[];
  final deleted = <String>[];
  String? failWith;

  @override
  Future<List<RoleModel>> listRoles() async => roles;

  @override
  Future<RoleModel> createRole(String name, {String? description, String? copyFromRoleId}) async {
    if (failWith != null) throw Exception(failWith);
    created.add((name, description, copyFromRoleId));
    final r = RoleModel(id: 'new', name: name, description: description, isCustom: true);
    roles = [...roles, r];
    return r;
  }

  @override
  Future<RoleModel> updateRole(String roleId, {String? name, String? description}) async {
    renamed.add((roleId, name, description));
    return RoleModel(id: roleId, name: name ?? '', description: description, isCustom: true);
  }

  @override
  Future<void> deleteRole(String roleId) async {
    deleted.add(roleId);
    roles = roles.where((r) => r.id != roleId).toList();
  }
}

const _standard = [
  RoleModel(id: 'm', name: 'Manager', description: 'Runs the society day to day', userCount: 2),
  RoleModel(id: 'r', name: 'Resident', userCount: 40),
];

Widget _app(_FakeRepo repo) => ProviderScope(
      overrides: [userAdminRepoProvider.overrideWithValue(repo)],
      child: MaterialApp(theme: AppTheme.lightTheme, home: const RolesScreen()),
    );

void main() {
  test('a role reads whether it is the society\'s own and how many users hold it', () {
    final r = RoleModel.fromJson({'id': 'x', 'name': 'Gym Instructor', 'is_custom': true, 'user_count': 3});
    expect((r.isCustom, r.userCount), (true, 3));
    final old = RoleModel.fromJson({'id': 'y', 'name': 'Manager'});          // a server that doesn't send them yet
    expect((old.isCustom, old.userCount), (false, 0));
  });

  test('/roles is part of Users & Roles, so it is gated by that form code', () {
    expect(formCodeForPath('/roles'), 'users_roles');
  });

  testWidgets('standard roles are listed for reference, and the society is told it has none of its own', (t) async {
    await t.pumpWidget(_app(_FakeRepo(_standard)));
    await t.pumpAndSettle();
    expect(find.byKey(const Key('no-custom-roles')), findsOneWidget);
    expect(find.text('Manager'), findsOneWidget);
    expect(find.text('Standard'), findsNWidgets(2));
    expect(find.text('2 users'), findsOneWidget);
    expect(find.text('Rename'), findsNothing);      // a standard role is not edited here
  });

  testWidgets('an admin adds a role, starting from another role\'s permissions', (t) async {
    t.view.physicalSize = const Size(800, 1800);
    t.view.devicePixelRatio = 1;
    addTearDown(t.view.reset);
    final repo = _FakeRepo(_standard);
    await t.pumpWidget(_app(repo));
    await t.pumpAndSettle();
    await t.tap(find.byKey(const Key('role-add')));
    await t.pumpAndSettle();
    await t.enterText(find.byKey(const Key('role-name')), 'Gym Instructor');
    await t.enterText(find.byKey(const Key('role-description')), 'Runs the gym');
    await t.tap(find.byKey(const Key('role-copy-from')));
    await t.pumpAndSettle();
    await t.tap(find.text('Manager').last);
    await t.pumpAndSettle();
    await t.tap(find.widgetWithText(FilledButton, 'Add role'));
    await t.pump(const Duration(seconds: 6));
    expect(repo.created, [('Gym Instructor', 'Runs the gym', 'm')]);
    await t.pumpAndSettle();
    expect(find.text('Gym Instructor'), findsOneWidget);
    expect(find.text('Yours'), findsOneWidget);
    expect(find.text('What it may do'), findsOneWidget);
  });

  testWidgets('a name under three characters is refused before saving', (t) async {
    t.view.physicalSize = const Size(800, 1800);
    t.view.devicePixelRatio = 1;
    addTearDown(t.view.reset);
    final repo = _FakeRepo(_standard);
    await t.pumpWidget(_app(repo));
    await t.pumpAndSettle();
    await t.tap(find.byKey(const Key('role-add')));
    await t.pumpAndSettle();
    await t.enterText(find.byKey(const Key('role-name')), 'ab');
    await t.tap(find.widgetWithText(FilledButton, 'Add role'));
    await t.pumpAndSettle();
    expect(find.text('At least 3 characters'), findsOneWidget);
    expect(repo.created, isEmpty);
  });

  testWidgets('a role in use cannot be deleted; one nobody holds can, after a confirmation', (t) async {
    t.view.physicalSize = const Size(800, 1800);
    t.view.devicePixelRatio = 1;
    addTearDown(t.view.reset);
    final repo = _FakeRepo([
      ..._standard,
      const RoleModel(id: 'busy', name: 'Librarian', isCustom: true, userCount: 2),
      const RoleModel(id: 'idle', name: 'Gym Instructor', isCustom: true),
    ]);
    await t.pumpWidget(_app(repo));
    await t.pumpAndSettle();
    expect(find.text('In use'), findsOneWidget);
    await t.tap(find.byKey(const Key('role-delete-busy')), warnIfMissed: false);
    await t.pumpAndSettle();
    expect(find.text('Delete Librarian?'), findsNothing);

    await t.tap(find.byKey(const Key('role-delete-idle')));
    await t.pumpAndSettle();
    expect(find.text('Delete Gym Instructor?'), findsOneWidget);
    expect(repo.deleted, isEmpty);                 // nothing until confirmed
    await t.tap(find.widgetWithText(FilledButton, 'Delete'));
    await t.pump(const Duration(seconds: 6));
    expect(repo.deleted, ['idle']);
  });

  testWidgets('a role is renamed from its tile', (t) async {
    t.view.physicalSize = const Size(800, 1800);
    t.view.devicePixelRatio = 1;
    addTearDown(t.view.reset);
    final repo = _FakeRepo([..._standard, const RoleModel(id: 'g', name: 'Gym Instructor', isCustom: true)]);
    await t.pumpWidget(_app(repo));
    await t.pumpAndSettle();
    await t.tap(find.text('Rename'));
    await t.pumpAndSettle();
    expect(find.text('Start from'), findsNothing);        // that is for a new role only
    await t.enterText(find.byKey(const Key('role-name')), 'Fitness Coach');
    await t.tap(find.widgetWithText(FilledButton, 'Save'));
    await t.pump(const Duration(seconds: 6));
    expect(repo.renamed.single.$1, 'g');
    expect(repo.renamed.single.$2, 'Fitness Coach');
  });
}
