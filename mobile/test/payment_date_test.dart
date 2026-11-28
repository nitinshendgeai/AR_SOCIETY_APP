import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/auth/domain/entities/user_entity.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/features/billing/data/datasources/billing_remote_datasource.dart';
import 'package:ar_society_app/features/billing/data/repositories/billing_repository.dart';
import 'package:ar_society_app/features/billing/domain/entities/billing_entities.dart';
import 'package:ar_society_app/features/billing/presentation/providers/billing_providers.dart';
import 'package:ar_society_app/features/billing/presentation/screens/online_payment_detail_screen.dart';

UserEntity _user(String role) =>
    UserEntity(id: 'u', email: 'u@t.com', fullName: 'U', roles: [role], societyId: 's1');

OnlinePaymentEntity _payment(DateTime date) => OnlinePaymentEntity(
      id: 'p1', societyId: 's1', flatId: 'f1', wingName: 'A', flatNumber: '2101', receiptNumber: 'OPS-2026-00051',
      amount: '15000.00', paymentDate: date, paymentMode: 'neft', status: 'reconciled',
    );

class _FakeRepo extends BillingRepository {
  _FakeRepo() : super(ds: BillingRemoteDataSource(dio: Dio()));
  DateTime date = DateTime(2026, 1, 10);
  final changes = <({DateTime date, String reason})>[];

  @override
  Future<BillingResult<List<OnlinePaymentEntity>>> listOnlinePayments(String societyId,
          {String? status, String? wingId, String? flatId}) async =>
      BillingSuccess([_payment(date)]);

  @override
  Future<BillingResult<OnlinePaymentEntity>> changePaymentDate(String id, DateTime d, String reason) async {
    changes.add((date: d, reason: reason));
    date = d;
    return BillingSuccess(_payment(d));
  }
}

Future<_FakeRepo> _open(WidgetTester t, String role) async {
  t.view.physicalSize = const Size(900, 3000);
  t.view.devicePixelRatio = 1.0;
  addTearDown(t.view.resetPhysicalSize);
  addTearDown(t.view.resetDevicePixelRatio);
  final repo = _FakeRepo();
  await t.pumpWidget(ProviderScope(
    overrides: [
      currentUserProvider.overrideWithValue(_user(role)),
      billingRepositoryProvider.overrideWithValue(repo),
    ],
    child: MaterialApp.router(
      theme: AppTheme.lightTheme,
      routerConfig: GoRouter(routes: [
        GoRoute(path: '/', builder: (_, __) => const OnlinePaymentDetailScreen(paymentId: 'p1')),
      ]),
    ),
  ));
  await t.pumpAndSettle();
  return repo;
}

void main() {
  testWidgets('an admin corrects the date a payment was received on, with a reason', (t) async {
    final repo = await _open(t, 'Society Admin');
    expect(find.text('10/1/2026'), findsOneWidget);
    await t.tap(find.byKey(const Key('payment-change-date')));
    await t.pumpAndSettle();
    // the date picker opens on the current date; go forward to a later month and take its 1st
    await t.tap(find.byIcon(Icons.chevron_right));
    await t.pumpAndSettle();
    await t.tap(find.text('1').first);
    await t.tap(find.text('OK'));
    await t.pumpAndSettle();
    expect(find.text('Change the payment date?'), findsOneWidget);
    await t.enterText(find.byKey(const Key('payment-date-reason')), 'Entered as dd/mm, was mm/dd');
    await t.tap(find.byKey(const Key('payment-date-confirm')));
    await t.pumpAndSettle();
    expect(repo.changes, hasLength(1));
    expect(repo.changes.single.date, DateTime(2026, 2, 1));
    expect(repo.changes.single.reason, 'Entered as dd/mm, was mm/dd');
    expect(find.text('1/2/2026'), findsOneWidget);                                        // the row follows
  });

  testWidgets('a manager is not offered the change', (t) async {
    await _open(t, 'Manager');
    expect(find.byKey(const Key('payment-change-date')), findsNothing);
  });
}
