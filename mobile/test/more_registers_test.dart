import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ar_society_app/features/accounts/data/more_registers_api.dart';
import 'package:ar_society_app/features/accounts/presentation/screens/more_register_screen.dart';
import 'package:ar_society_app/features/accounts/presentation/screens/registers_hub_screen.dart';
import 'package:ar_society_app/features/auth/domain/entities/user_entity.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';

MoreRegister _attendance() => MoreRegister.fromJson({
      'kind': 'attendance',
      'title': 'Staff Attendance Register',
      'subtitle': 'For September 2026',
      'columns': [
        {'key': 'name', 'label': 'Name', 'right': false, 'phone': true},
        {'key': 'd1', 'label': '1', 'right': false, 'phone': false},
        {'key': 'present', 'label': 'Pres.', 'right': true, 'phone': true},
        {'key': 'absent', 'label': 'Abs.', 'right': true, 'phone': true},
      ],
      'rows': [
        {'name': 'Guard One', 'd1': 'P', 'present': '3', 'absent': '1'},
        {'name': 'Cleaner One', 'd1': 'L', 'present': '0', 'absent': ''},
      ],
      'totals': [
        {'label': 'Staff', 'value': '2'},
        {'label': 'Present days', 'value': '3'},
      ],
      'statuses': [
        {'value': null, 'label': 'All'},
        {'value': 'security', 'label': 'Security'},
      ],
      'uses_period': false,
      'uses_month': true,
      'month': '2026-09',
    });

MoreRegister _rental() => MoreRegister.fromJson({
      'kind': 'rental',
      'title': 'Rental Register',
      'subtitle': 'Flats and shops let out',
      'columns': [
        {'key': 'unit', 'label': 'Unit', 'right': false, 'phone': true},
        {'key': 'tenant', 'label': 'Tenant', 'right': false, 'phone': true},
        {'key': 'rent', 'label': 'Rent', 'right': true, 'phone': true},
      ],
      'rows': [
        {'unit': 'A 101', 'tenant': 'Ravi Tenant', 'rent': '20000.00'},
      ],
      'totals': [
        {'label': 'Tenancies', 'value': '1'},
      ],
      'statuses': [
        {'value': null, 'label': 'All'},
        {'value': 'expiring', 'label': 'Expiring in 60 days'},
      ],
      'uses_period': false,
      'uses_month': false,
    });

Widget _app(String kind, MoreRegister Function() build, List<MoreRegisterKey> asked) => ProviderScope(
      overrides: [
        currentUserProvider.overrideWithValue(
            const UserEntity(id: 'u', email: 'u@t.com', fullName: 'U', roles: ['Society Admin'], societyId: 's1')),
        moreRegisterProvider.overrideWith((ref, key) async {
          asked.add(key);
          return build();
        }),
      ],
      child: MaterialApp(home: MoreRegisterScreen(kind: kind)),
    );

void main() {
  testWidgets('a phone shows one card per staff member with the totals, not thirty columns', (tester) async {
    final asked = <MoreRegisterKey>[];
    await tester.pumpWidget(_app('attendance', _attendance, asked));
    await tester.pumpAndSettle();

    expect(find.text('Staff Attendance Register'), findsWidgets);
    expect(find.text('Present days'), findsOneWidget);
    expect(find.text('Guard One'), findsOneWidget);
    expect(find.text('Pres.: 3'), findsOneWidget);
    expect(find.text('Abs.: 1'), findsOneWidget);
    expect(find.textContaining('1: P'), findsNothing);                 // the day columns are for the printout and a computer
    expect(find.text('Abs.: '), findsNothing);                          // a blank figure is left out
    expect(asked.first.kind, 'attendance');
    expect(asked.first.month, isNotNull);                              // a month register always asks for a month
  });

  testWidgets('the month arrows move to the month before and after, and ask the server for it', (tester) async {
    final asked = <MoreRegisterKey>[];
    await tester.pumpWidget(_app('attendance', _attendance, asked));
    await tester.pumpAndSettle();
    String shown() => tester.widget<Text>(find.byKey(const ValueKey('register-month'))).data!;
    final first = shown();
    final firstAsked = asked.last.month!;
    await tester.tap(find.byKey(const ValueKey('register-month-prev')));
    await tester.pumpAndSettle();
    expect(shown(), isNot(first));
    expect(asked.last.month, isNot(firstAsked));
    await tester.tap(find.byKey(const ValueKey('register-month-next')));
    await tester.pumpAndSettle();
    expect(shown(), first);
  });

  testWidgets('a status chip asks the server for that status, and a search narrows it', (tester) async {
    final asked = <MoreRegisterKey>[];
    await tester.pumpWidget(_app('rental', _rental, asked));
    await tester.pumpAndSettle();
    expect(find.text('Ravi Tenant'), findsOneWidget);
    expect(find.text('Rent: 20000.00'), findsOneWidget);
    expect(asked.last.status, isNull);

    await tester.tap(find.byKey(const ValueKey('register-status-expiring')));
    await tester.pumpAndSettle();
    expect(asked.last.status, 'expiring');

    await tester.enterText(find.byKey(const ValueKey('register-search')), 'ravi');
    await tester.pumpAndSettle();
    expect(asked.last.search, 'ravi');
    expect(asked.last.month, isNull);                                   // a register with no month asks for none
  });

  testWidgets('the Registers page lists every register once', (tester) async {
    await tester.pumpWidget(const MaterialApp(home: RegistersHubScreen()));
    for (final id in ['invoices', 'bills', 'cash', 'receipts', 'rental', 'attendance']) {
      expect(find.byKey(ValueKey('register-$id')), findsOneWidget, reason: id);
    }
    expect(find.text('Rental Register'), findsOneWidget);
    expect(find.text('Staff Attendance Register'), findsOneWidget);
  });
}
