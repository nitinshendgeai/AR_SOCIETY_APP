import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/features/accounts/data/bank_reconciliation_api.dart';

final bankReconciliationApiProvider = Provider<BankReconciliationApi>((_) => BankReconciliationApi());

typedef BrsKey = ({String societyId, String? accountId, DateTime asOn});

/// The Bank Reconciliation Statement of one bank ledger as on a date.
final bankReconciliationProvider = FutureProvider.autoDispose.family<BankReconciliation, BrsKey>(
  (ref, k) => ref.watch(bankReconciliationApiProvider).statement(k.societyId, accountId: k.accountId, asOn: k.asOn),
);

typedef BrsAccountKey = ({String societyId, String? accountId});

/// Lines of the bank ledger already cleared (to review, or to take back a mistake).
final clearedLinesProvider = FutureProvider.autoDispose.family<List<BrsLine>, BrsAccountKey>(
  (ref, k) => ref.watch(bankReconciliationApiProvider).cleared(k.societyId, accountId: k.accountId),
);

/// The imported bank statement rows of the society (all bank accounts; the screen narrows them to one).
final statementRowsProvider = FutureProvider.autoDispose.family<List<StatementRow>, String>(
  (ref, societyId) => ref.watch(bankReconciliationApiProvider).rows(societyId),
);

typedef RowKey = ({String societyId, String rowId});

/// The books' own lines a statement row could be (same amount, opposite side, not cleared, dated nearby).
final rowSuggestionsProvider = FutureProvider.autoDispose.family<List<BrsLine>, RowKey>(
  (ref, k) => ref.watch(bankReconciliationApiProvider).suggestions(k.societyId, k.rowId),
);
