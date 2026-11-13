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
import 'package:ar_society_app/features/visitor/domain/visitor_search.dart';
import 'package:ar_society_app/features/visitor/presentation/providers/visitor_providers.dart';
import 'package:ar_society_app/features/visitor/presentation/screens/visitor_list_screen.dart';

VisitorEntity _v(
  String id,
  String name, {
  String mobile = '9000000000',
  String? flat,
  String? wing,
  String? plate,
  String? purpose,
  String? code,
  VisitorStatus status = VisitorStatus.checkedOut,
}) =>
    VisitorEntity(
      id: id,
      name: name,
      mobile: mobile,
      visitorType: VisitorType.guest,
      purpose: purpose,
      societyId: 's1',
      flatNumber: flat,
      wingName: wing,
      status: status,
      passCode: code,
      vehicle: plate == null ? null : VisitorVehicleEntity(id: 'x$id', vehicleType: 'car', vehicleNumber: plate),
      logs: const [],
      createdAt: DateTime(2026, 11, 6),
    );

final _asha = _v('1', 'Asha Kulkarni', mobile: '9876543210', flat: '101', wing: 'A', plate: 'MH 12 AB 1234', purpose: 'Dinner', code: '482913');
final _ravi = _v('2', 'Ravi Patil', mobile: '9123456780', flat: '202', wing: 'B', status: VisitorStatus.checkedIn);
final _zomato = _v('3', 'Zomato delivery', mobile: '9000011111', flat: '101', wing: 'A', purpose: 'Food');
final _all = [_asha, _ravi, _zomato];

List<String> _names(List<VisitorEntity> l) => l.map((v) => v.name).toList();

void main() {
  group('filterVisitors', () {
    test('a blank query returns everyone, in order', () {
      expect(_names(filterVisitors(_all, '')), ['Asha Kulkarni', 'Ravi Patil', 'Zomato delivery']);
      expect(_names(filterVisitors(_all, '   ')), hasLength(3));
    });

    test('matches part of a name, ignoring case', () {
      expect(_names(filterVisitors(_all, 'ASH')), ['Asha Kulkarni']);
      expect(_names(filterVisitors(_all, 'patil')), ['Ravi Patil']);
    });

    test('matches part of a mobile number', () {
      expect(_names(filterVisitors(_all, '3210')), ['Asha Kulkarni']);
      expect(_names(filterVisitors(_all, '90000')), ['Zomato delivery']);
    });

    test('matches a flat as "A-101", "a101" or "101"', () {
      for (final q in ['A-101', 'a101', 'A 101', '101']) {
        expect(_names(filterVisitors(_all, q)), containsAll(['Asha Kulkarni', 'Zomato delivery']), reason: q);
      }
      expect(_names(filterVisitors(_all, 'B-202')), ['Ravi Patil']);
    });

    test('matches a vehicle number however it is typed', () {
      for (final q in ['MH12AB1234', 'mh 12 ab 1234', 'MH-12-AB-1234', 'ab1234']) {
        expect(_names(filterVisitors(_all, q)), ['Asha Kulkarni'], reason: q);
      }
    });

    test('every word must match, across different fields', () {
      expect(_names(filterVisitors(_all, 'asha 101')), ['Asha Kulkarni']);
      expect(filterVisitors(_all, 'asha 202'), isEmpty);
    });

    test('the secret pass code is not searchable', () {
      expect(filterVisitors(_all, '482913'), isEmpty);
    });

    test('nothing matches nothing', () {
      expect(filterVisitors(_all, 'zzzz'), isEmpty);
    });
  });

  group('the guard\'s visitor log (phone)', () {
    Widget app(List<VisitorEntity> rows) => ProviderScope(
          overrides: [
            currentUserProvider.overrideWithValue(const UserEntity(
                id: 'u', email: 'x@y.c', fullName: 'Guard', roles: ['Security Staff'], societyId: 's1', termsAccepted: true)),
            visitorRepositoryProvider.overrideWithValue(_Repo(rows)),
          ],
          child: MaterialApp(theme: AppTheme.lightTheme, home: const VisitorListScreen(societyId: 's1')),
        );

    testWidgets('typing narrows the list and clearing brings everyone back', (t) async {
      await t.pumpWidget(app(_all));
      await t.pumpAndSettle();
      expect(find.text('Asha Kulkarni'), findsOneWidget);
      expect(find.text('Ravi Patil'), findsOneWidget);

      await t.enterText(find.byKey(const Key('visitor-search')), 'ravi');
      await t.pumpAndSettle();
      expect(find.text('Ravi Patil'), findsOneWidget);
      expect(find.text('Asha Kulkarni'), findsNothing);

      await t.tap(find.byTooltip('Clear search'));
      await t.pumpAndSettle();
      expect(find.text('Asha Kulkarni'), findsOneWidget);
      expect(find.text('Ravi Patil'), findsOneWidget);
    });

    testWidgets('a search that finds no one says so', (t) async {
      await t.pumpWidget(app(_all));
      await t.pumpAndSettle();
      await t.enterText(find.byKey(const Key('visitor-search')), 'nobody');
      await t.pumpAndSettle();
      expect(find.text('No visitor matches'), findsOneWidget);
      expect(find.text('Asha Kulkarni'), findsNothing);
    });

    testWidgets('the search also applies on the Inside Now tab', (t) async {
      await t.pumpWidget(app(_all));
      await t.pumpAndSettle();
      await t.tap(find.text('Inside Now'));
      await t.pumpAndSettle();
      expect(find.text('Ravi Patil'), findsOneWidget);          // the only one checked in
      await t.enterText(find.byKey(const Key('visitor-search')), 'asha');
      await t.pumpAndSettle();
      expect(find.text('Ravi Patil'), findsNothing);
      expect(find.text('No visitor matches'), findsOneWidget);
    });

    testWidgets('the search field is at least 48dp tall', (t) async {
      await t.pumpWidget(app(_all));
      await t.pumpAndSettle();
      expect(t.getSize(find.byKey(const Key('visitor-search'))).height, greaterThanOrEqualTo(40));
    });

    testWidgets('a full page warns that only the latest visitors are searched; a short one does not', (t) async {
      final many = [for (var i = 0; i < visitorLogLimit; i++) _v('m$i', 'Person $i')];
      await t.pumpWidget(app(many));
      await t.pumpAndSettle();
      expect(find.byKey(const Key('visitor-search-cap')), findsNothing);       // no query yet
      await t.enterText(find.byKey(const Key('visitor-search')), 'person 7');
      await t.pumpAndSettle();
      expect(find.byKey(const Key('visitor-search-cap')), findsOneWidget);

      await t.pumpWidget(const SizedBox());       // a fresh screen, so nothing of the first one is kept
      await t.pumpWidget(app(_all));
      await t.pumpAndSettle();
      await t.enterText(find.byKey(const Key('visitor-search')), 'asha');
      await t.pumpAndSettle();
      expect(find.byKey(const Key('visitor-search-cap')), findsNothing);
    });
  });

  testWidgets('a resident\'s own list has no search box', (t) async {
    await t.pumpWidget(ProviderScope(
      overrides: [
        currentUserProvider.overrideWithValue(
            const UserEntity(id: 'u', email: 'x@y.c', fullName: 'R', roles: ['Resident'], societyId: 's1', termsAccepted: true)),
        visitorRepositoryProvider.overrideWithValue(_Repo(_all)),
      ],
      child: MaterialApp(theme: AppTheme.lightTheme, home: const VisitorListScreen(isMy: true)),
    ));
    await t.pumpAndSettle();
    expect(find.byKey(const Key('visitor-search')), findsNothing);
  });
}

class _Repo extends VisitorRepository {
  final List<VisitorEntity> rows;
  _Repo(this.rows) : super(ds: VisitorRemoteDataSource(dio: Dio()));

  @override
  Future<VisitorResult<List<VisitorEntity>>> listSocietyVisitors(String societyId, {int limit = 50}) async => VisitorSuccess(rows);

  @override
  Future<VisitorResult<List<VisitorEntity>>> getMyVisitors() async => VisitorSuccess(rows);

  @override
  Future<VisitorResult<List<VisitorEntity>>> getPendingApprovals() async => VisitorSuccess(const []);
}
