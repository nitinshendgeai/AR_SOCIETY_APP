import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/features/accounts/data/accounts_api.dart';

final accountsApiProvider = Provider<AccountsApi>((_) => AccountsApi());

final accountsSummaryProvider = FutureProvider.autoDispose.family<AccountsSummary, String>(
  (ref, societyId) => ref.watch(accountsApiProvider).summary(societyId),
);

final chartOfAccountsProvider = FutureProvider.autoDispose.family<List<AccountGroupRow>, String>(
  (ref, societyId) => ref.watch(accountsApiProvider).chart(societyId),
);

/// Active ledgers — for the pickers on the voucher and vendor-bill forms.
final ledgersProvider = FutureProvider.autoDispose.family<List<LedgerAccount>, String>(
  (ref, societyId) => ref.watch(accountsApiProvider).ledgers(societyId),
);

final membersLedgerProvider = FutureProvider.autoDispose.family<MembersLedger, String>(
  (ref, societyId) => ref.watch(accountsApiProvider).members(societyId),
);

typedef StatementKey = ({String accountId, DateTime? from, DateTime? to, String? flatId, String? vendorId});

final ledgerStatementProvider = FutureProvider.autoDispose.family<LedgerStatement, StatementKey>(
  (ref, k) => ref
      .watch(accountsApiProvider)
      .statement(k.accountId, from: k.from, to: k.to, flatId: k.flatId, vendorId: k.vendorId),
);

typedef VouchersKey = ({String societyId, String? type, DateTime? from, DateTime? to});

final vouchersProvider = FutureProvider.autoDispose.family<List<Voucher>, VouchersKey>(
  (ref, k) => ref.watch(accountsApiProvider).vouchers(k.societyId, type: k.type, from: k.from, to: k.to),
);

final voucherProvider = FutureProvider.autoDispose.family<Voucher, String>(
  (ref, id) => ref.watch(accountsApiProvider).voucher(id),
);

final financialYearsProvider = FutureProvider.autoDispose.family<List<FinancialYear>, String>(
  (ref, societyId) => ref.watch(accountsApiProvider).years(societyId),
);

typedef ExpensePeriodKey = ({String societyId, DateTime from, DateTime to});

final expensesByElementProvider = FutureProvider.autoDispose.family<ExpensesByElement, ExpensePeriodKey>(
  (ref, k) => ref.watch(accountsApiProvider).expensesByElement(k.societyId, k.from, k.to),
);

typedef ReportKey = ({String societyId, String report, String fy});

final financialReportProvider = FutureProvider.autoDispose.family<FinancialReport, ReportKey>(
  (ref, k) => ref.watch(accountsApiProvider).report(k.societyId, k.report, k.fy),
);

/// Everything a new or cancelled voucher can change.
void invalidateBooks(WidgetRef ref) {
  ref.invalidate(accountsSummaryProvider);
  ref.invalidate(chartOfAccountsProvider);
  ref.invalidate(membersLedgerProvider);
  ref.invalidate(ledgerStatementProvider);
  ref.invalidate(vouchersProvider);
  ref.invalidate(voucherProvider);
  ref.invalidate(financialYearsProvider);
  ref.invalidate(financialReportProvider);
  ref.invalidate(expensesByElementProvider);
  ref.invalidate(ledgersProvider);
}
