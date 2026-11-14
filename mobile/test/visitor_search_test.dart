import 'dart:async';
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

/// Types in the search box, then waits out the pause before the server is asked and for its answer.
Future<void> _type(WidgetTester t, String text) async {
  await t.enterText(find.byKey(const Key('visitor-search')), text);
  await t.pump(const Duration(milliseconds: 400));
  await t.pumpAndSettle();
}

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
    Widget app(List<VisitorEntity> rows, {_Repo? repo}) => ProviderScope(
          overrides: [
            currentUserProvider.overrideWithValue(const UserEntity(
                id: 'u', email: 'x@y.c', fullName: 'Guard', roles: ['Security Staff'], societyId: 's1', termsAccepted: true)),
            visitorRepositoryProvider.overrideWithValue(repo ?? _Repo(rows)),
          ],
          child: MaterialApp(theme: AppTheme.lightTheme, home: const VisitorListScreen(societyId: 's1')),
        );

    testWidgets('typing narrows the list and clearing brings everyone back', (t) async {
      await t.pumpWidget(app(_all));
      await t.pumpAndSettle();
      expect(find.text('Asha Kulkarni'), findsOneWidget);
      expect(find.text('Ravi Patil'), findsOneWidget);

      await _type(t, 'ravi');
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
      await _type(t, 'nobody');
      expect(find.text('No visitor matches'), findsOneWidget);
      expect(find.text('Asha Kulkarni'), findsNothing);
    });

    testWidgets('the search also applies on the Inside Now tab', (t) async {
      await t.pumpWidget(app(_all));
      await t.pumpAndSettle();
      await t.tap(find.text('Inside Now'));
      await t.pumpAndSettle();
      expect(find.text('Ravi Patil'), findsOneWidget);          // the only one checked in
      await _type(t, 'asha');
      expect(find.text('Ravi Patil'), findsNothing);
      expect(find.text('No visitor matches'), findsOneWidget);
    });

    testWidgets('the search field is at least 48dp tall', (t) async {
      await t.pumpWidget(app(_all));
      await t.pumpAndSettle();
      expect(t.getSize(find.byKey(const Key('visitor-search'))).height, greaterThanOrEqualTo(40));
    });

    testWidgets('the server is asked, and finds a visitor who is not in the latest page', (t) async {
      final meena = _v('9', 'Meena Joshi', mobile: '9555500009', flat: '303', wing: 'C');
      final repo = _Repo(_all, serverRows: [..._all, meena]);        // the log holds more than the page that was loaded
      await t.pumpWidget(app(_all, repo: repo));
      await t.pumpAndSettle();
      expect(find.text('Meena Joshi'), findsNothing);
      await _type(t, 'meena');
      expect(repo.queries, ['meena']);
      expect(repo.societies, ['s1']);
      expect(find.text('Meena Joshi'), findsOneWidget);
      expect(find.text('Asha Kulkarni'), findsNothing);
      expect(find.byKey(const Key('visitor-search-cap')), findsNothing);
    });

    testWidgets('the server is asked once the person pauses, not on every key', (t) async {
      final repo = _Repo(_all);
      await t.pumpWidget(app(_all, repo: repo));
      await t.pumpAndSettle();
      for (final text in ['r', 'ra', 'rav', 'ravi']) {
        await t.enterText(find.byKey(const Key('visitor-search')), text);
        await t.pump(const Duration(milliseconds: 100));
      }
      expect(repo.queries, isEmpty);                                   // still typing
      await t.pump(const Duration(milliseconds: 400));
      await t.pumpAndSettle();
      expect(repo.queries, ['ravi']);
    });

    testWidgets('a slow answer to an earlier search never replaces the answer to the latest one', (t) async {
      final slow = Completer<VisitorResult<List<VisitorEntity>>>();
      final repo = _Repo(_all, onSearch: (q) => q == 'asha' ? slow.future : null);
      await t.pumpWidget(app(_all, repo: repo));
      await t.pumpAndSettle();
      await _type(t, 'asha');                // asked, not answered yet
      await _type(t, 'ravi');                // typed on; this answer comes straight back
      expect(find.text('Ravi Patil'), findsOneWidget);
      slow.complete(VisitorSuccess([_asha]));   // the old answer arrives late
      await t.pumpAndSettle();
      expect(find.text('Ravi Patil'), findsOneWidget);
      expect(find.text('Asha Kulkarni'), findsNothing);
    });

    testWidgets('clearing the search brings the log back and drops a late answer', (t) async {
      final slow = Completer<VisitorResult<List<VisitorEntity>>>();
      final repo = _Repo(_all, onSearch: (q) => slow.future);
      await t.pumpWidget(app(_all, repo: repo));
      await t.pumpAndSettle();
      await _type(t, 'zzz');
      await t.tap(find.byTooltip('Clear search'));
      await t.pumpAndSettle();
      slow.complete(VisitorSuccess(const []));
      await t.pumpAndSettle();
      expect(find.text('Asha Kulkarni'), findsOneWidget);
      expect(find.text('No visitor matches'), findsNothing);
    });

    testWidgets('if the server cannot search, the loaded rows are searched and a full page says so', (t) async {
      final many = [for (var i = 0; i < visitorLogLimit; i++) _v('m$i', 'Person $i')];
      await t.pumpWidget(app(many, repo: _Repo(many, searchFails: true)));
      await t.pumpAndSettle();
      expect(find.byKey(const Key('visitor-search-cap')), findsNothing);       // no query yet
      await _type(t, 'person 7');
      expect(find.text('Person 7'), findsOneWidget);                           // found among the loaded rows
      expect(find.byKey(const Key('visitor-search-cap')), findsOneWidget);

      await t.pumpWidget(const SizedBox());       // a fresh screen, so nothing of the first one is kept
      await t.pumpWidget(app(_all, repo: _Repo(_all, searchFails: true)));
      await t.pumpAndSettle();
      await _type(t, 'asha');
      expect(find.text('Asha Kulkarni'), findsOneWidget);
      expect(find.byKey(const Key('visitor-search-cap')), findsNothing);       // a short page is the whole log
    });

    testWidgets('a working server search never shows the "only the latest" note', (t) async {
      final many = [for (var i = 0; i < visitorLogLimit; i++) _v('m$i', 'Person $i')];
      await t.pumpWidget(app(many, repo: _Repo(many)));
      await t.pumpAndSettle();
      await _type(t, 'person 7');
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
  /// The page the log screen loads.
  final List<VisitorEntity> rows;

  /// The whole log, which the server searches (defaults to [rows]).
  final List<VisitorEntity>? serverRows;
  final bool searchFails;

  /// Lets a test answer a search itself (returns null to answer normally).
  final Future<VisitorResult<List<VisitorEntity>>>? Function(String q)? onSearch;
  final queries = <String>[];
  final societies = <String>[];
  _Repo(this.rows, {this.serverRows, this.searchFails = false, this.onSearch})
      : super(ds: VisitorRemoteDataSource(dio: Dio()));

  @override
  Future<VisitorResult<List<VisitorEntity>>> searchSocietyVisitors(String societyId, String query, {int limit = 200}) async {
    queries.add(query);
    societies.add(societyId);
    final custom = onSearch?.call(query);
    if (custom != null) return custom;
    if (searchFails) return VisitorFailure('offline');
    return VisitorSuccess(filterVisitors(serverRows ?? rows, query));
  }

  @override
  Future<VisitorResult<List<VisitorEntity>>> listSocietyVisitors(String societyId, {int limit = 50}) async => VisitorSuccess(rows);

  @override
  Future<VisitorResult<List<VisitorEntity>>> getMyVisitors() async => VisitorSuccess(rows);

  @override
  Future<VisitorResult<List<VisitorEntity>>> getPendingApprovals() async => VisitorSuccess(const []);
}
