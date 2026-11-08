import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/features/accounts/data/bank_reconciliation_api.dart';

final bankReconciliationApiProvider = Provider<BankReconciliationApi>((_) => BankReconciliationApi());

typedef BrsKey = ({String societyId, String? accountId, DateTime asOn});

/// The Bank Reconciliation Statement of one bank ledger as on a date.
final bankReconciliationProvider = FutureProvider.autoDispose.family<BankReconciliation, BrsKey>(
  (ref, k) => ref.watch(bankReconciliationApiProvider).statement(k.societyId, accountId: k.accountId, asOn: k.asOn),
);

typedef BrsAccountKey = ({String societyId, String? accountId});

/// How far back the Cleared tab looks: what was cleared long ago is out of the way (the books keep it all).
const clearedWindowDays = 90;

/// Lines of the bank ledger cleared in the last [clearedWindowDays] days (to review, or to take back a mistake).
final clearedLinesProvider = FutureProvider.autoDispose.family<List<BrsLine>, BrsAccountKey>(
  (ref, k) => ref
      .watch(bankReconciliationApiProvider)
      .cleared(k.societyId, accountId: k.accountId, dateFrom: DateTime.now().subtract(const Duration(days: clearedWindowDays))),
);

/// The imported bank statement rows of one bank ledger, each line once.
final statementRowsProvider = FutureProvider.autoDispose.family<List<StatementRow>, BrsAccountKey>(
  (ref, k) => ref.watch(bankReconciliationApiProvider).rows(k.societyId, accountId: k.accountId),
);

typedef RowKey = ({String societyId, String rowId});

/// The books' own lines a statement row could be (same amount, opposite side, not cleared, dated nearby).
final rowSuggestionsProvider = FutureProvider.autoDispose.family<List<BrsLine>, RowKey>(
  (ref, k) => ref.watch(bankReconciliationApiProvider).suggestions(k.societyId, k.rowId),
);
