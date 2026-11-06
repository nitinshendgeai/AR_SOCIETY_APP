import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/auth/domain/entities/user_entity.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/features/maintenance_billing/data/maintenance_billing_api.dart';
import 'package:ar_society_app/features/maintenance_billing/data/payment_claims_api.dart';
import 'package:ar_society_app/features/maintenance_billing/presentation/screens/claim_payment_screen.dart';
import 'package:ar_society_app/features/maintenance_billing/presentation/screens/payment_claims_screen.dart';
import 'package:ar_society_app/features/maintenance_billing/presentation/widgets/pay_widgets.dart';

PaymentClaimItem _claim(String id, String status, {String? why}) => PaymentClaimItem(
      id: id,
      status: status,
      flatId: 'f1',
      flatLabel: 'A-101',
      billId: 'b1',
      billInvoiceNumber: 'INV-1',
      amount: '5500.00',
      paymentDate: DateTime(2026, 11, 5),
      paymentMode: 'upi',
      transactionRef: 'UTR123',
      claimedByName: 'Asha',
      hasScreenshot: true,
      reviewNotes: why,
    );

MaintenanceBill _bill() => MaintenanceBill(
      id: 'b1',
      cycleId: 'c',
      flatId: 'f1',
      invoiceNumber: 'INV-1',
      status: 'issued',
      billDate: DateTime(2026, 11, 1),
      dueDate: DateTime(2026, 11, 15),
      totalAmount: '5500.00',
      paidAmount: '0.00',
      outstanding: '5500.00',
    );

class _FakeApi extends PaymentClaimsApi {
  PaymentInfo infoResult;
  List<PaymentClaimItem> mineResult;
  List<PaymentClaimItem> pending;
  Map<String, dynamic>? created;
  String? confirmed;
  String? rejected;
  String? rejectReason;
  _FakeApi({this.infoResult = const PaymentInfo(), this.mineResult = const [], this.pending = const []}) : super(dio: Dio());

  @override
  Future<PaymentInfo> info() async => infoResult;

  @override
  Future<List<PaymentClaimItem>> mine() async => mineResult;

  @override
  Future<List<PaymentClaimItem>> forSociety(String societyId, {String? status}) async => pending;

  @override
  Future<PaymentClaimItem> create({
    required double amount,
    required DateTime paymentDate,
    required String paymentMode,
    String? flatId,
    String? billId,
    String? transactionRef,
    String? bankName,
    String? notes,
    Uint8List? screenshotBytes,
    String? screenshotName,
  }) async {
    created = {'amount': amount, 'mode': paymentMode, 'flat': flatId, 'bill': billId, 'ref': transactionRef};
    return _claim('new', 'pending');
  }

  @override
  Future<PaymentClaimItem> confirm(String id, {String? notes}) async {
    confirmed = id;
    return _claim(id, 'confirmed');
  }

  @override
  Future<PaymentClaimItem> reject(String id, String reason) async {
    rejected = id;
    rejectReason = reason;
    return _claim(id, 'rejected', why: reason);
  }
}

Widget _app(_FakeApi api, Widget home, {List<String> roles = const ['Resident']}) => ProviderScope(
      overrides: [
        paymentClaimsApiProvider.overrideWithValue(api),
        currentUserProvider.overrideWithValue(
            UserEntity(id: 'u', email: 'x@y.c', fullName: 'U', roles: roles, societyId: 's1', termsAccepted: true)),
      ],
      child: MaterialApp(theme: AppTheme.lightTheme, home: home),
    );

void _tall(WidgetTester t) {
  t.view.physicalSize = const Size(800, 2600);
  t.view.devicePixelRatio = 1.0;
  addTearDown(t.view.resetPhysicalSize);
  addTearDown(t.view.resetDevicePixelRatio);
}

void main() {
  group('How to pay', () {
    testWidgets('shows the UPI id and bank account with Copy', (tester) async {
      final api = _FakeApi(
          infoResult: const PaymentInfo(
              upiId: 'society@okbank', accountName: 'Sunrise CHS', bankName: 'HDFC', accountNumber: '50100123456789', ifsc: 'HDFC0000001'));
      await tester.pumpWidget(_app(api, const Scaffold(body: SingleChildScrollView(child: HowToPayCard()))));
      await tester.pumpAndSettle();
      expect(find.text('society@okbank'), findsOneWidget);
      expect(find.text('50100123456789'), findsOneWidget);
      expect(find.text('HDFC0000001'), findsOneWidget);
      expect(find.byTooltip('Copy UPI ID'), findsOneWidget);
    });

    testWidgets('says to ask the office when the society has not set its details', (tester) async {
      await tester.pumpWidget(_app(_FakeApi(), const Scaffold(body: HowToPayCard())));
      await tester.pumpAndSettle();
      expect(find.textContaining('Ask the office where to pay'), findsOneWidget);
    });
  });

  group('I have paid', () {
    testWidgets('fills in the amount due and sends a cash payment against the bill', (tester) async {
      _tall(tester);
      final api = _FakeApi();
      await tester.pumpWidget(_app(api, ClaimPaymentScreen(bill: _bill())));
      await tester.pumpAndSettle();

      expect(find.text('Bill INV-1'), findsOneWidget);
      expect(tester.widget<TextFormField>(find.byKey(const Key('claim-amount'))).controller!.text, '5500.00');

      await tester.tap(find.text('UPI'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Cash').last);
      await tester.pumpAndSettle();
      await tester.tap(find.text('Send to the office'));
      await tester.pumpAndSettle();

      expect(api.created, {'amount': 5500.0, 'mode': 'cash', 'flat': 'f1', 'bill': 'b1', 'ref': null});
    });

    testWidgets('a UPI payment needs its reference and a screenshot before it is sent', (tester) async {
      _tall(tester);
      final api = _FakeApi();
      await tester.pumpWidget(_app(api, ClaimPaymentScreen(bill: _bill())));
      await tester.pumpAndSettle();

      await tester.tap(find.text('Send to the office'));
      await tester.pumpAndSettle();
      expect(find.text('Enter the reference of the payment'), findsOneWidget);
      expect(api.created, isNull);

      await tester.enterText(find.byKey(const Key('claim-ref')), 'UTR999');
      await tester.tap(find.text('Send to the office'));
      await tester.pumpAndSettle();
      expect(find.text('Add a screenshot of the payment'), findsOneWidget);
      expect(api.created, isNull);
    });

    testWidgets('an amount above what is due is refused', (tester) async {
      _tall(tester);
      final api = _FakeApi();
      await tester.pumpWidget(_app(api, ClaimPaymentScreen(bill: _bill())));
      await tester.pumpAndSettle();
      await tester.enterText(find.byKey(const Key('claim-amount')), '9000');
      await tester.tap(find.text('Send to the office'));
      await tester.pumpAndSettle();
      expect(find.textContaining('More than the'), findsOneWidget);
      expect(api.created, isNull);
    });
  });

  group('payments the resident reported', () {
    testWidgets('pending and rejected ones show, confirmed ones do not', (tester) async {
      final api = _FakeApi(mineResult: [
        _claim('1', 'pending'),
        _claim('2', 'rejected', why: 'UTR not found'),
        _claim('3', 'confirmed'),
      ]);
      await tester.pumpWidget(_app(api, const Scaffold(body: SingleChildScrollView(child: PaymentClaimsStrip()))));
      await tester.pumpAndSettle();
      expect(find.text('Payments you reported'), findsOneWidget);
      expect(find.textContaining('Waiting for the office'), findsOneWidget);
      expect(find.textContaining('UTR not found'), findsOneWidget);
      expect(find.textContaining('₹5,500'), findsNWidgets(2));
    });

    testWidgets('nothing is drawn when there is nothing to report', (tester) async {
      await tester.pumpWidget(_app(_FakeApi(mineResult: [_claim('3', 'confirmed')]), const Scaffold(body: PaymentClaimsStrip())));
      await tester.pumpAndSettle();
      expect(find.text('Payments you reported'), findsNothing);
    });
  });

  group('the office', () {
    testWidgets('the banner counts the reports and opens the review screen', (tester) async {
      final api = _FakeApi(pending: [_claim('1', 'pending'), _claim('2', 'pending')]);
      await tester.pumpWidget(_app(api, const Scaffold(body: ResidentClaimsBanner(societyId: 's1'))));
      await tester.pumpAndSettle();
      expect(find.textContaining('2 payments reported by residents are waiting'), findsOneWidget);
      await tester.tap(find.byKey(const Key('claims-banner')));
      await tester.pumpAndSettle();
      expect(find.text('Payments reported by residents'), findsOneWidget);
    });

    testWidgets('confirming a report records it', (tester) async {
      _tall(tester);
      final api = _FakeApi(pending: [_claim('c1', 'pending')]);
      await tester.pumpWidget(_app(api, const PaymentClaimsScreen(), roles: const ['Manager']));
      await tester.pumpAndSettle();
      expect(find.text('A-101  ·  ₹5,500.00'), findsOneWidget);
      expect(find.text('Reference: UTR123'), findsOneWidget);

      await tester.tap(find.byKey(const Key('claim-confirm')));
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('claim-confirm-go')));
      await tester.pumpAndSettle();
      expect(api.confirmed, 'c1');
    });

    testWidgets('rejecting needs a reason the resident will read', (tester) async {
      _tall(tester);
      final api = _FakeApi(pending: [_claim('c1', 'pending')]);
      await tester.pumpWidget(_app(api, const PaymentClaimsScreen(), roles: const ['Manager']));
      await tester.pumpAndSettle();

      await tester.tap(find.byKey(const Key('claim-reject')));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Reject').last);          // no reason yet: nothing happens
      await tester.pumpAndSettle();
      expect(api.rejected, isNull);

      await tester.enterText(find.byKey(const Key('claim-reject-reason')), 'Not in the bank statement');
      await tester.tap(find.text('Reject').last);
      await tester.pumpAndSettle();
      expect(api.rejected, 'c1');
      expect(api.rejectReason, 'Not in the bank statement');
    });

    testWidgets('an empty list says nothing is waiting', (tester) async {
      await tester.pumpWidget(_app(_FakeApi(), const PaymentClaimsScreen(), roles: const ['Manager']));
      await tester.pumpAndSettle();
      expect(find.text('Nothing waiting'), findsOneWidget);
    });
  });
}
