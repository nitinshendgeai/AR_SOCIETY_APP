import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/accounts/data/accounts_api.dart' show LedgerAccount;
import 'package:ar_society_app/features/accounts/presentation/providers/accounts_providers.dart';
import 'package:ar_society_app/features/amenities/data/amenities_api.dart';
import 'package:ar_society_app/features/amenities/presentation/providers/amenities_providers.dart';
import 'package:ar_society_app/features/amenities/presentation/screens/amenities_screen.dart';
import 'package:ar_society_app/features/auth/domain/entities/user_entity.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';

class _Call {
  final String kind;
  final String id;
  final String mode;
  final String? ledger;
  final double retained;
  final String? reason;
  _Call(this.kind, this.id, this.mode, this.ledger, this.retained, this.reason);
}

class _FakeApi extends AmenitiesApi {
  _FakeApi() : super(dio: Dio());
  final calls = <_Call>[];

  BookingItem _b() => _booking();

  @override
  Future<BookingItem> receiveDeposit(String id,
      {required String mode, String? bankAccountId, String? reference, DateTime? paidOn}) async {
    calls.add(_Call('receive', id, mode, bankAccountId, 0, null));
    return _b();
  }

  @override
  Future<BookingItem> refundDeposit(String id,
      {required String mode,
      String? bankAccountId,
      String? reference,
      double retained = 0,
      String? reason,
      DateTime? paidOn}) async {
    calls.add(_Call('refund', id, mode, bankAccountId, retained, reason));
    return _b();
  }
}

BookingItem _booking({String status = 'approved', bool paid = false, bool refunded = false, String? charge}) =>
    BookingItem.fromJson({
      'id': 'b1',
      'amenity_id': 'a1',
      'amenity_name': 'Party hall',
      'booking_date': '2026-10-20',
      'start_time': '10:00:00',
      'end_time': '14:00:00',
      'guest_count': 20,
      'status': status,
      'charge_amount': 2000.0,
      'deposit_amount': 1000.0,
      'deposit_paid': paid,
      'deposit_refunded': refunded,
      'charge_bill_status': charge,
    });

LedgerAccount _ledger(String id, String name, {bool cash = false, bool bank = false, bool def = false}) =>
    LedgerAccount.fromJson({
      'id': id,
      'group_id': 'g',
      'name': name,
      'is_cash': cash,
      'is_bank': bank,
      'is_default_bank': def,
      'is_system': true,
      'is_active': true,
      'opening_balance': '0',
      'opening_type': 'dr',
    });

Widget _card(_FakeApi api, BookingItem b) => ProviderScope(
      overrides: [
        currentUserProvider.overrideWithValue(const UserEntity(
            id: 'u1',
            email: 'a@b.c',
            fullName: 'Asha',
            roles: ['Manager'],
            societyId: 's1',
            termsAccepted: true)),
        amenitiesApiProvider.overrideWithValue(api),
        ledgersProvider.overrideWith((ref, id) async => [
              _ledger('cash', 'Cash in Hand', cash: true),
              _ledger('hdfc', 'HDFC Current', bank: true),
              _ledger('sbi', 'SBI Savings', bank: true, def: true),
            ]),
      ],
      child: MaterialApp(
        theme: AppTheme.lightTheme,
        home: Scaffold(body: SingleChildScrollView(child: BookingCard(booking: b, manager: true, showWho: true))),
      ),
    );

void main() {
  test('a booking knows where its deposit and charge stand', () {
    final fresh = _booking();
    expect(fresh.canReceiveDeposit, isTrue);
    expect(fresh.canRefundDeposit, isFalse);
    expect(fresh.depositText, 'not received');

    final held = _booking(status: 'completed', paid: true);
    expect(held.canReceiveDeposit, isFalse);
    expect(held.canRefundDeposit, isTrue);
    expect(held.depositText, 'held');

    // Still running: the deposit is not given back before the booking is over.
    expect(_booking(paid: true).canRefundDeposit, isFalse);
    final done = _booking(status: 'completed', paid: true, refunded: true);
    expect(done.canRefundDeposit, isFalse);
    expect(done.depositText, 'settled');

    expect(_booking(charge: 'active').chargeText, 'on the next maintenance bill');
    expect(_booking(charge: 'billed').chargeText, 'billed to the flat');
    expect(_booking().chargeText, isNull);
  });

  testWidgets('the manager receives the deposit into the chosen account', (tester) async {
    final api = _FakeApi();
    await tester.pumpWidget(_card(api, _booking(charge: 'active')));
    await tester.pumpAndSettle();
    expect(find.textContaining('on the next maintenance bill'), findsOneWidget);
    expect(find.text('Give deposit back'), findsNothing);

    await tester.tap(find.text('Receive deposit'));
    await tester.pumpAndSettle();
    // Cash is the starting mode, so it goes into the cash ledger.
    await tester.tap(find.widgetWithText(FilledButton, 'Receive deposit'));
    await tester.pump(const Duration(seconds: 6));
    expect(api.calls, hasLength(1));
    expect(api.calls.single.kind, 'receive');
    expect((api.calls.single.id, api.calls.single.mode, api.calls.single.ledger), ('b1', 'cash', 'cash'));
  });

  testWidgets('giving the deposit back can keep part of it, with a reason', (tester) async {
    final api = _FakeApi();
    await tester.pumpWidget(_card(api, _booking(status: 'completed', paid: true)));
    await tester.pumpAndSettle();
    expect(find.text('Receive deposit'), findsNothing);

    await tester.tap(find.text('Give deposit back'));
    await tester.pumpAndSettle();
    expect(find.textContaining('Returned to the member: ₹1,000'), findsOneWidget);

    final amount = find.byType(TextFormField).first;
    await tester.enterText(amount, '300');
    await tester.pumpAndSettle();
    expect(find.textContaining('Returned to the member: ₹700'), findsOneWidget);

    // Keeping part needs a reason.
    await tester.ensureVisible(find.widgetWithText(FilledButton, 'Give back'));
    await tester.tap(find.widgetWithText(FilledButton, 'Give back'));
    await tester.pumpAndSettle();
    expect(find.text('Say why'), findsOneWidget);
    expect(api.calls, isEmpty);

    await tester.enterText(find.byType(TextFormField).at(1), 'Broken speaker');
    await tester.ensureVisible(find.widgetWithText(FilledButton, 'Give back'));
    await tester.tap(find.widgetWithText(FilledButton, 'Give back'));
    await tester.pump(const Duration(seconds: 6));
    final c = api.calls.single;
    expect((c.kind, c.retained, c.reason, c.ledger), ('refund', 300.0, 'Broken speaker', 'cash'));
  });

  testWidgets('a deposit kept in full needs no account to pay out of', (tester) async {
    final api = _FakeApi();
    await tester.pumpWidget(_card(api, _booking(status: 'cancelled', paid: true)));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Give deposit back'));
    await tester.pumpAndSettle();
    await tester.enterText(find.byType(TextFormField).first, '1000');
    await tester.pumpAndSettle();
    expect(find.textContaining('whole deposit is kept'), findsOneWidget);
    expect(find.text('Paid from'), findsNothing);
    await tester.enterText(find.byType(TextFormField).at(1), 'Cancelled on the day');
    await tester.ensureVisible(find.widgetWithText(FilledButton, 'Give back'));
    await tester.tap(find.widgetWithText(FilledButton, 'Give back'));
    await tester.pump(const Duration(seconds: 6));
    expect(api.calls.single.retained, 1000.0);
  });
}
