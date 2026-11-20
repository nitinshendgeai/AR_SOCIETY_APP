import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ar_society_app/features/accounts/data/accounts_api.dart' show Voucher;
import 'package:ar_society_app/features/accounts/data/more_registers_api.dart';
import 'package:ar_society_app/features/accounts/presentation/providers/accounts_providers.dart' show voucherProvider;
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

MoreRegister _expenses() => MoreRegister.fromJson({
      'kind': 'expenses',
      'title': 'Expenses Register',
      'subtitle': 'Every expense booked',
      'columns': [
        {'key': 'date', 'label': 'Date', 'right': false, 'phone': true},
        {'key': 'head', 'label': 'Expense head', 'right': false, 'phone': true},
        {'key': 'amount', 'label': 'Amount Rs.', 'right': true, 'phone': true},
        {'key': 'document', 'label': 'Document', 'right': false, 'phone': true},
      ],
      'rows': [
        {'voucher_id': 'v1', 'date': '05-11-2026', 'head': 'Security Charges', 'amount': '30000.00', 'document': '1 filed'},
        {'voucher_id': 'v2', 'date': '06-11-2026', 'head': 'Lift Maintenance', 'amount': '1500.00', 'document': 'None'},
      ],
      'totals': [
        {'label': 'Entries', 'value': '2'},
        {'label': 'With a document', 'value': '1'},
      ],
      'statuses': [
        {'value': null, 'label': 'All'},
        {'value': 'with_document', 'label': 'With a document'},
        {'value': 'without_document', 'label': 'No document'},
      ],
      'uses_period': true,
      'uses_month': false,
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
  testWidgets('an expense opens its voucher, with the bill filed against it', (tester) async {
    final asked = <MoreRegisterKey>[];
    await tester.pumpWidget(ProviderScope(
      overrides: [
        currentUserProvider.overrideWithValue(
            const UserEntity(id: 'u', email: 'u@t.com', fullName: 'U', roles: ['Society Admin'], societyId: 's1')),
        moreRegisterProvider.overrideWith((ref, key) async {
          asked.add(key);
          return _expenses();
        }),
        voucherProvider.overrideWith((ref, id) async => Voucher.fromJson({
              'id': id,
              'voucher_type': 'payment',
              'voucher_number': 'PV/26-27/0007',
              'voucher_date': '2026-11-05',
              'amount': '30000.00',
              'entries': [],
              'documents': [
                {'id': 'd1', 'file_name': 'security-bill.pdf', 'mime_type': 'application/pdf', 'size_bytes': 2048},
              ],
            })),
      ],
      child: const MaterialApp(home: MoreRegisterScreen(kind: 'expenses')),
    ));
    await tester.pumpAndSettle();
    expect(find.text('Expense head: Security Charges'), findsOneWidget);   // a phone card: headed by the date
    expect(find.text('Document: 1 filed'), findsOneWidget);
    expect(asked.last.status, isNull);

    await tester.tap(find.byKey(const ValueKey('register-status-with_document')));
    await tester.pumpAndSettle();
    expect(asked.last.status, 'with_document');                         // the register can be narrowed to expenses with a bill

    await tester.tap(find.text('Expense head: Security Charges'));
    await tester.pumpAndSettle();
    expect(find.text('PV/26-27/0007'), findsOneWidget);                 // the voucher opened
    expect(find.text('Documents (1)'), findsOneWidget);
    expect(find.text('security-bill.pdf'), findsOneWidget);
    expect(find.byKey(const ValueKey('voucher-attach')), findsOneWidget);
  });

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
    expect(find.text('A 101'), findsOneWidget);                          // a card is headed by the unit
    expect(find.text('Tenant: Ravi Tenant'), findsOneWidget);
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
    tester.view.physicalSize = const Size(800, 1600);   // all eight tiles fit; a list builds only what is on screen
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.reset);
    await tester.pumpWidget(const MaterialApp(home: RegistersHubScreen()));
    for (final id in ['invoices', 'bills', 'expenses', 'cash', 'receipts', 'rental', 'attendance', 'petty_cash']) {
      expect(find.byKey(ValueKey('register-$id')), findsOneWidget, reason: id);
    }
    expect(find.text('Rental Register'), findsOneWidget);
    expect(find.text('Staff Attendance Register'), findsOneWidget);
  });
}
