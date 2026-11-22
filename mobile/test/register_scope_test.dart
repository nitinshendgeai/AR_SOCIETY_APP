import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/accounts/data/accounts_api.dart';
import 'package:ar_society_app/features/accounts/data/more_registers_api.dart';
import 'package:ar_society_app/features/accounts/data/registers_api.dart';
import 'package:ar_society_app/features/accounts/presentation/providers/accounts_providers.dart';
import 'package:ar_society_app/features/accounts/presentation/screens/cash_bank_book_screen.dart';
import 'package:ar_society_app/features/accounts/presentation/screens/financial_report_screen.dart';
import 'package:ar_society_app/features/accounts/presentation/screens/more_register_screen.dart';
import 'package:ar_society_app/features/auth/domain/entities/user_entity.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';

const _admin = UserEntity(id: 'u', email: 'u@t.com', fullName: 'U', roles: ['Society Admin'], societyId: 's1');

void _tall(WidgetTester t) {
  t.view.physicalSize = const Size(420, 2400);
  t.view.devicePixelRatio = 1.0;
  addTearDown(t.view.resetPhysicalSize);
  addTearDown(t.view.resetDevicePixelRatio);
}

CashBankBook _emptyBook() => CashBankBook.fromJson({
      'sections': [],
      'totals': {'opening': '0.00', 'receipts': '0.00', 'payments': '0.00', 'closing': '0.00'},
    });

FinancialReport _report(String key) => FinancialReport.fromJson({
      'report': key, 'title': 'Report', 'heading': 'Heading', 'fy': '2026-27', 'kind': 'table',
      'columns': ['Debit', 'Credit'], 'rows': [], 'totals': [], 'notes': [], 'balanced': true,
    });

MoreRegister _register(String kind) => MoreRegister.fromJson({
      'kind': kind, 'title': 'A Register', 'subtitle': 's', 'columns': [], 'rows': [], 'totals': [],
      'statuses': [], 'uses_period': false, 'uses_month': false,
    });

void main() {
  testWidgets('the cash and bank book can be limited to the residents or to operations', (t) async {
    _tall(t);
    final asked = <BookKey>[];
    await t.pumpWidget(ProviderScope(
      overrides: [
        currentUserProvider.overrideWithValue(_admin),
        cashBankBookProvider.overrideWith((ref, key) async {
          asked.add(key);
          return _emptyBook();
        }),
      ],
      child: MaterialApp(theme: AppTheme.lightTheme, home: const CashBankBookScreen()),
    ));
    await t.pumpAndSettle();
    expect(asked.last.scope, isNull);
    expect(find.byKey(const Key('scope-all')), findsOneWidget);

    await t.tap(find.byKey(const Key('scope-members')));
    await t.pumpAndSettle();
    expect(asked.last.scope, 'members');
    expect(find.textContaining('Residents'), findsWidgets);
    expect(find.textContaining('opening balances are not included'), findsOneWidget);

    await t.tap(find.byKey(const Key('scope-society')));
    await t.pumpAndSettle();
    expect(asked.last.scope, 'society');

    await t.tap(find.byKey(const Key('scope-all')));
    await t.pumpAndSettle();
    expect(asked.last.scope, isNull);
    expect(find.textContaining('opening balances are not included'), findsNothing);
  });

  testWidgets('the expenses register can be split, other registers have no such filter', (t) async {
    _tall(t);
    final asked = <MoreRegisterKey>[];
    Widget app(String kind) => ProviderScope(
          key: UniqueKey(),
          overrides: [
            currentUserProvider.overrideWithValue(_admin),
            moreRegisterProvider.overrideWith((ref, key) async {
              asked.add(key);
              return _register(kind);
            }),
          ],
          child: MaterialApp(theme: AppTheme.lightTheme, home: MoreRegisterScreen(kind: kind)),
        );
    await t.pumpWidget(app('expenses'));
    await t.pumpAndSettle();
    await t.tap(find.byKey(const Key('scope-society')));
    await t.pumpAndSettle();
    expect(asked.last.scope, 'society');

    await t.pumpWidget(app('rental'));
    await t.pumpAndSettle();
    expect(find.byKey(const Key('scope-society')), findsNothing);
    expect(asked.last.scope, isNull);
  });

  testWidgets('income & expenditure can be split; the balance sheet cannot', (t) async {
    _tall(t);
    final asked = <ReportKey>[];
    Widget app(String report) => ProviderScope(
          key: UniqueKey(),
          overrides: [
            currentUserProvider.overrideWithValue(_admin),
            financialReportProvider.overrideWith((ref, key) async {
              asked.add(key);
              return _report(report);
            }),
          ],
          child: MaterialApp(theme: AppTheme.lightTheme, home: FinancialReportScreen(report: report, fy: '2026-27')),
        );
    await t.pumpWidget(app('income-expenditure'));
    await t.pumpAndSettle();
    expect(find.text('Whole society'), findsOneWidget);
    await t.tap(find.byKey(const Key('scope-members')));
    await t.pumpAndSettle();
    expect(asked.last.scope, 'members');

    await t.pumpWidget(app('balance-sheet'));
    await t.pumpAndSettle();
    expect(find.byKey(const Key('scope-members')), findsNothing);
    expect(asked.last.scope, isNull);
  });
}
