import 'dart:io';

import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/layout/app_sheet.dart';
import 'package:ar_society_app/core/motion/loading.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/accounts/data/accounts_api.dart'
    show LedgerAccount, formatAccountsDate, formatInr;
import 'package:ar_society_app/features/accounts/data/bank_reconciliation_api.dart';
import 'package:ar_society_app/features/accounts/presentation/providers/accounts_providers.dart';
import 'package:ar_society_app/features/accounts/presentation/providers/bank_reconciliation_providers.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/features/vendor/presentation/widgets/procurement_widgets.dart' show askReason;
import 'package:ar_society_app/shared/widgets/app_data_table.dart' show StatusPill;
import 'package:ar_society_app/shared/widgets/app_form.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';

/// The treasurer's monthly bank reconciliation against the books. Three tabs:
///
///  * **Statement** — the Bank Reconciliation Statement of one bank ledger as on a date: the balance in the books, the
///    payments and deposits the bank has not cleared yet, and the balance the bank statement should show. Tick the lines
///    the bank has cleared and say on which day.
///  * **Bank rows** — the rows of the imported bank statement (credits and debits), matched to the books' own lines.
///  * **Cleared** — what has been cleared, with Undo for a mistake.
class BankReconciliationStatementScreen extends ConsumerStatefulWidget {
  const BankReconciliationStatementScreen({super.key});

  @override
  ConsumerState<BankReconciliationStatementScreen> createState() => _BankReconciliationStatementScreenState();
}

class _BankReconciliationStatementScreenState extends ConsumerState<BankReconciliationStatementScreen> {
  String? _accountId;
  DateTime _asOn = DateTime.now();
  final _picked = <String>{};
  String? _rowFilter = 'unmatched';
  bool _busy = false;

  /// Everything a clearing or a match can change.
  void _refresh(String societyId) {
    ref.invalidate(bankReconciliationProvider);
    ref.invalidate(clearedLinesProvider);
    ref.invalidate(statementRowsProvider(societyId));
    ref.invalidate(rowSuggestionsProvider);
    setState(() => _picked.clear());
  }

  Future<void> _run(String societyId, Future<String> Function() action) async {
    setState(() => _busy = true);
    try {
      final message = await action();
      _refresh(societyId);
      if (mounted) AppToast.success(context, message);
    } catch (e) {
      if (mounted) showErrorToast(context, e);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _pickAsOn() async {
    final d = await showDatePicker(
        context: context, initialDate: _asOn, firstDate: DateTime(DateTime.now().year - 5), lastDate: DateTime.now());
    if (d != null) {
      setState(() {
        _asOn = d;
        _picked.clear();
      });
    }
  }

  /// Marks the ticked lines as cleared on the day the bank cleared them (not before the latest voucher date).
  Future<void> _clearPicked(String societyId, BankReconciliation b) async {
    final lines = [...b.paymentsNotCleared, ...b.depositsNotCleared].where((l) => _picked.contains(l.entryId)).toList();
    if (lines.isEmpty) return;
    final earliest = lines.map((l) => l.date).reduce((a, c) => a.isAfter(c) ? a : c);
    final today = DateTime.now();
    final on = await showDatePicker(
      context: context,
      helpText: 'Day the bank cleared ${lines.length == 1 ? 'it' : 'them'}',
      initialDate: today.isBefore(earliest) ? earliest : today,
      firstDate: earliest,
      lastDate: today,
    );
    if (on == null || !mounted) return;
    await _run(societyId, () async {
      final n = await ref.read(bankReconciliationApiProvider).clear(societyId, [for (final l in lines) l.entryId], on);
      return '$n ${n == 1 ? 'line' : 'lines'} marked as cleared on ${formatAccountsDate(on)}';
    });
  }

  Future<void> _import(String societyId) async {
    final result =
        await FilePicker.platform.pickFiles(type: FileType.custom, allowedExtensions: ['csv'], withData: true);
    final picked = result?.files.single;
    if (picked == null) return;
    final bytes = picked.bytes ?? (picked.path != null ? await File(picked.path!).readAsBytes() : null);
    if (bytes == null) return;
    await _run(societyId, () async {
      final n = await ref
          .read(bankReconciliationApiProvider)
          .importStatement(societyId, csvBytes: bytes, fileName: picked.name, accountId: _accountId);
      return 'Imported $n ${n == 1 ? 'row' : 'rows'} from the statement';
    });
  }

  Future<void> _autoMatch(String societyId) => _run(societyId, () async {
        final r = await ref.read(bankReconciliationApiProvider).autoMatch(societyId, accountId: _accountId);
        return r.matched == 0
            ? 'Nothing could be matched on its own — choose the lines yourself'
            : '${r.matched} matched on their own${r.leftForAPerson > 0 ? ' · ${r.leftForAPerson} left for you' : ''}';
      });

  @override
  Widget build(BuildContext context) {
    final societyId = ref.watch(currentUserProvider)?.societyId;
    if (societyId == null) return const Scaffold(body: Center(child: Text('No society context')));
    final ledgers = ref.watch(ledgersProvider(societyId));
    final banks = (ledgers.valueOrNull ?? const <LedgerAccount>[]).where((l) => l.isBank && l.isActive).toList();
    if (_accountId == null && banks.isNotEmpty) {
      _accountId = (banks.where((l) => l.isDefaultBank).firstOrNull ?? banks.first).id;
    }

    return DefaultTabController(
      length: 3,
      child: AppPage(
        title: 'Bank Reconciliation',
        subtitle: 'Match the bank statement with the books',
        bottom: const TabBar(tabs: [Tab(text: 'Statement'), Tab(text: 'Bank rows'), Tab(text: 'Cleared')]),
        actions: [
          IconButton(icon: const Icon(Icons.refresh_rounded), tooltip: 'Refresh', onPressed: () => _refresh(societyId)),
        ],
        body: ledgers.when(
          loading: () => const AppLoader(),
          error: (e, _) =>
              ListView(padding: const EdgeInsets.all(16), children: [AppErrorBanner(message: friendlyErrorMessage(e))]),
          data: (_) => banks.isEmpty
              ? const AppEmptyState(
                  icon: Icons.account_balance_rounded,
                  title: 'No bank account yet',
                  subtitle: 'Add your bank account as a ledger in the Chart of Accounts, then reconcile it here.',
                )
              : Column(children: [
                  _controls(banks),
                  Expanded(
                    child: TabBarView(children: [
                      _statementTab(societyId),
                      _rowsTab(societyId),
                      _clearedTab(societyId),
                    ]),
                  ),
                ]),
        ),
      ),
    );
  }

  Widget _controls(List<LedgerAccount> banks) => Padding(
        padding: const EdgeInsets.fromLTRB(16, 12, 16, 4),
        child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Expanded(
            flex: 3,
            child: FormFieldBox(
              label: 'Bank account',
              child: DropdownButtonFormField<String>(
                key: ValueKey('bank-$_accountId'),
                initialValue: _accountId,
                isExpanded: true,
                items: [
                  for (final b in banks)
                    DropdownMenuItem(value: b.id, child: Text(b.name, overflow: TextOverflow.ellipsis))
                ],
                onChanged: (v) => setState(() {
                  _accountId = v;
                  _picked.clear();
                }),
              ),
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            flex: 2,
            child: FormFieldBox(
              label: 'As on',
              child: FormDateField(value: _asOn, hint: 'Pick a date', format: formatAccountsDate, onTap: _pickAsOn),
            ),
          ),
        ]),
      );

  // ── Statement ──────────────────────────────────────────────────────────────

  Widget _statementTab(String societyId) {
    final key = (societyId: societyId, accountId: _accountId, asOn: _asOn);
    return ref.watch(bankReconciliationProvider(key)).when(
          loading: () => const AppLoader(),
          error: (e, _) =>
              ListView(padding: const EdgeInsets.all(16), children: [AppErrorBanner(message: friendlyErrorMessage(e))]),
          data: (b) => Column(children: [
            Expanded(
              child: ListView(padding: const EdgeInsets.fromLTRB(16, 8, 16, 24), children: [
                _SummaryCard(b),
                if (b.isFullyCleared)
                  const Padding(
                    padding: EdgeInsets.only(top: 12),
                    child: AppEmptyState(
                      icon: Icons.check_circle_outline_rounded,
                      title: 'Everything is cleared',
                      subtitle: 'Every payment and deposit up to this date has been through the bank.',
                    ),
                  ),
                if (b.paymentsNotCleared.isNotEmpty)
                  _lines(
                    'Payments not yet cleared',
                    'Cheques and transfers the society has paid that the bank has not debited.',
                    b.paymentsNotCleared,
                  ),
                if (b.depositsNotCleared.isNotEmpty)
                  _lines(
                    'Deposits not yet cleared',
                    'Money the society has recorded as received that the bank has not credited.',
                    b.depositsNotCleared,
                  ),
              ]),
            ),
            if (_picked.isNotEmpty) _clearBar(societyId, b),
          ]),
        );
  }

  Widget _lines(String title, String hint, List<BrsLine> lines) => Padding(
        padding: const EdgeInsets.only(top: 18),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(title, style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w700)),
          const SizedBox(height: 2),
          Text(hint, style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
          const SizedBox(height: 8),
          for (final l in lines)
            _LineTile(
              line: l,
              picked: _picked.contains(l.entryId),
              onChanged: (v) => setState(() => v ? _picked.add(l.entryId) : _picked.remove(l.entryId)),
            ),
        ]),
      );

  Widget _clearBar(String societyId, BankReconciliation b) {
    final all = [...b.paymentsNotCleared, ...b.depositsNotCleared].where((l) => _picked.contains(l.entryId));
    final deposits = all.where((l) => l.isDeposit).fold<double>(0, (s, l) => s + l.amount);
    final payments = all.where((l) => !l.isDeposit).fold<double>(0, (s, l) => s + l.amount);
    return Material(
      elevation: 8,
      color: Colors.white,
      child: SafeArea(
        top: false,
        child: Padding(
          padding: const EdgeInsets.fromLTRB(16, 10, 16, 10),
          child: Row(children: [
            Expanded(
              child: Text(
                '${all.length} selected · deposits ${formatInr(deposits)} · payments ${formatInr(payments)}',
                key: const ValueKey('selected-summary'),
                style: const TextStyle(fontSize: 13),
              ),
            ),
            const SizedBox(width: 12),
            FilledButton(
              onPressed: _busy ? null : () => _clearPicked(societyId, b),
              child: const Text('Mark cleared'),
            ),
          ]),
        ),
      ),
    );
  }

  // ── Bank rows ──────────────────────────────────────────────────────────────

  Widget _rowsTab(String societyId) {
    final rowsAsync = ref.watch(statementRowsProvider(societyId));
    return Column(children: [
      Padding(
        padding: const EdgeInsets.fromLTRB(16, 4, 16, 0),
        child: Wrap(spacing: 8, runSpacing: 4, crossAxisAlignment: WrapCrossAlignment.center, children: [
          for (final (value, label) in const [
            ('unmatched', 'Unmatched'),
            ('matched', 'Matched'),
            ('ignored', 'Ignored'),
            (null, 'All'),
          ])
            ChoiceChip(
              label: Text(label, style: const TextStyle(fontSize: 12)),
              selected: _rowFilter == value,
              onSelected: (_) => setState(() => _rowFilter = value),
            ),
          OutlinedButton.icon(
            onPressed: _busy ? null : () => _import(societyId),
            icon: const Icon(Icons.upload_file_rounded, size: 18),
            label: const Text('Import statement'),
          ),
          OutlinedButton.icon(
            onPressed: _busy ? null : () => _autoMatch(societyId),
            icon: const Icon(Icons.auto_fix_high_rounded, size: 18),
            label: const Text('Auto-match'),
          ),
        ]),
      ),
      const Padding(
        padding: EdgeInsets.fromLTRB(16, 4, 16, 0),
        child: Align(
          alignment: Alignment.centerLeft,
          child: Text(
              'CSV columns: Date, Description, Amount (negative = debit) or Debit and Credit, Reference optional',
              style: TextStyle(fontSize: 11.5, color: AppTheme.textSecondary)),
        ),
      ),
      Expanded(
        child: rowsAsync.when(
          loading: () => const AppLoader(),
          error: (e, _) =>
              ListView(padding: const EdgeInsets.all(16), children: [AppErrorBanner(message: friendlyErrorMessage(e))]),
          data: (all) {
            final rows = all
                .where((r) => r.bankAccountId == null || r.bankAccountId == _accountId)
                .where((r) => _rowFilter == null || r.matchStatus == _rowFilter)
                .toList();
            if (rows.isEmpty) {
              return const AppEmptyState(
                icon: Icons.account_balance_rounded,
                title: 'No statement rows here',
                subtitle: 'Import the bank\'s statement and match each row to a payment or deposit in the books.',
              );
            }
            return ListView.builder(
              padding: const EdgeInsets.fromLTRB(16, 8, 16, 24),
              itemCount: rows.length,
              itemBuilder: (_, i) => _RowTile(row: rows[i], onTap: () => _openRow(societyId, rows[i])),
            );
          },
        ),
      ),
    ]);
  }

  Future<void> _openRow(String societyId, StatementRow row) async {
    if (row.isUnmatched) {
      await showAppSheet(
        context: context,
        builder: (_) => _RowSheet(societyId: societyId, row: row, onChanged: () => _refresh(societyId)),
      );
      return;
    }
    if (row.isMatched && row.matchedEntryId != null) {
      final back = await showDialog<bool>(
        context: context,
        builder: (ctx) => AlertDialog(
          title: const Text('Matched to the books'),
          content: const Text('Take the match back? The line goes back to "not yet cleared" on the statement.'),
          actions: [
            TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Keep')),
            TextButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('Take back')),
          ],
        ),
      );
      if (back == true) {
        await _run(societyId, () async {
          await ref.read(bankReconciliationApiProvider).unmatch(societyId, row.id);
          return 'Match taken back';
        });
      }
      return;
    }
    if (!mounted) return;
    await showDialog<void>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(row.isMatched ? 'Matched' : 'Ignored'),
        content: Text(row.isMatched
            ? 'Linked to resident payment ${row.matchedReceiptNumber ?? ''}. Use Online Payments to review it.'
            : 'This row was set aside as not belonging to the books.'),
        actions: [TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Close'))],
      ),
    );
  }

  // ── Cleared ────────────────────────────────────────────────────────────────

  Widget _clearedTab(String societyId) {
    final async = ref.watch(clearedLinesProvider((societyId: societyId, accountId: _accountId)));
    return async.when(
      loading: () => const AppLoader(),
      error: (e, _) =>
          ListView(padding: const EdgeInsets.all(16), children: [AppErrorBanner(message: friendlyErrorMessage(e))]),
      data: (lines) => lines.isEmpty
          ? const AppEmptyState(
              icon: Icons.history_rounded,
              title: 'Nothing cleared yet',
              subtitle: 'Lines you mark as cleared, or match to the bank statement, are listed here.',
            )
          : ListView.builder(
              padding: const EdgeInsets.fromLTRB(16, 8, 16, 24),
              itemCount: lines.length,
              itemBuilder: (_, i) {
                final l = lines[i];
                return Card(
                  margin: const EdgeInsets.only(bottom: 8),
                  child: ListTile(
                    title: Text('${l.voucherNumber}${l.party == null ? '' : ' · ${l.party}'}',
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: const TextStyle(fontWeight: FontWeight.w600)),
                    subtitle: Text(
                        '${l.isDeposit ? 'Deposit' : 'Payment'} ${formatInr(l.amount)} · cleared ${l.clearedDate == null ? '' : formatAccountsDate(l.clearedDate!)}'),
                    trailing: TextButton(
                      onPressed: _busy
                          ? null
                          : () => _run(societyId, () async {
                                await ref.read(bankReconciliationApiProvider).unclear(societyId, [l.entryId]);
                                return '${l.voucherNumber} is not cleared again';
                              }),
                      child: const Text('Undo'),
                    ),
                  ),
                );
              },
            ),
    );
  }
}

/// Balance as per the books, plus the payments and less the deposits the bank has not cleared, is the balance the bank
/// statement shows.
class _SummaryCard extends StatelessWidget {
  final BankReconciliation b;
  const _SummaryCard(this.b);

  Widget _row(String label, double amount, {bool bold = false, String sign = ''}) => Padding(
        padding: const EdgeInsets.symmetric(vertical: 4),
        child: Row(children: [
          Expanded(child: Text(label, style: TextStyle(fontWeight: bold ? FontWeight.w700 : FontWeight.w400))),
          Text('$sign${formatInr(amount)}', style: TextStyle(fontWeight: bold ? FontWeight.w800 : FontWeight.w500)),
        ]),
      );

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          Text('${b.accountName} as on ${formatAccountsDate(b.asOn)}',
              style: const TextStyle(fontSize: 13, color: AppTheme.textSecondary)),
          const SizedBox(height: 8),
          _row('Balance as per the books', b.balancePerBooks),
          _row('Add: payments not yet cleared', b.paymentsNotClearedTotal, sign: '+ '),
          _row('Less: deposits not yet cleared', b.depositsNotClearedTotal, sign: '− '),
          const Divider(height: 20),
          _row('Balance as per the bank', b.balancePerBank, bold: true),
          const SizedBox(height: 6),
          const Text('This should equal the closing balance on the bank\'s statement for the same day.',
              style: TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
        ]),
      ),
    );
  }
}

/// One payment or deposit the bank has not cleared: tick it once the bank statement shows it.
class _LineTile extends StatelessWidget {
  final BrsLine line;
  final bool picked;
  final ValueChanged<bool> onChanged;
  const _LineTile({required this.line, required this.picked, required this.onChanged});

  @override
  Widget build(BuildContext context) {
    final details = [
      formatAccountsDate(line.date),
      if ((line.reference ?? '').isNotEmpty) line.reference!,
      if (line.daysPending > 0) '${line.daysPending} days',
    ].join(' · ');
    final who = line.party ?? line.narration;
    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      child: CheckboxListTile(
        key: ValueKey('line-${line.voucherNumber}'),
        value: picked,
        onChanged: (v) => onChanged(v ?? false),
        controlAffinity: ListTileControlAffinity.leading,
        title: Text(line.voucherNumber, style: const TextStyle(fontWeight: FontWeight.w600)),
        subtitle:
            Text('$details${who == null || who.isEmpty ? '' : '\n$who'}', maxLines: 3, overflow: TextOverflow.ellipsis),
        secondary: Text(formatInr(line.amount),
            style: TextStyle(
                fontWeight: FontWeight.w700, color: line.isDeposit ? AppTheme.success : AppTheme.textPrimary)),
      ),
    );
  }
}

class _RowTile extends StatelessWidget {
  final StatementRow row;
  final VoidCallback onTap;
  const _RowTile({required this.row, required this.onTap});

  @override
  Widget build(BuildContext context) {
    final color = switch (row.matchStatus) {
      'matched' => AppTheme.success,
      'ignored' => AppTheme.textSecondary,
      _ => AppTheme.warning,
    };
    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      child: ListTile(
        key: ValueKey('row-${row.id}'),
        onTap: onTap,
        leading: Icon(row.isCredit ? Icons.south_west_rounded : Icons.north_east_rounded,
            color: row.isCredit ? AppTheme.success : AppTheme.error),
        title: Text(row.description, maxLines: 2, overflow: TextOverflow.ellipsis),
        subtitle:
            Text('${formatAccountsDate(row.txnDate)}${(row.reference ?? '').isEmpty ? '' : ' · ${row.reference}'}'),
        trailing:
            Column(mainAxisAlignment: MainAxisAlignment.center, crossAxisAlignment: CrossAxisAlignment.end, children: [
          Text('${row.isCredit ? '' : '− '}${formatInr(row.amount)}',
              style: const TextStyle(fontWeight: FontWeight.w700)),
          const SizedBox(height: 4),
          StatusPill(row.matchStatus[0].toUpperCase() + row.matchStatus.substring(1), color),
        ]),
      ),
    );
  }
}

/// A statement row with the lines of the books it could be. Matching clears that line.
class _RowSheet extends ConsumerStatefulWidget {
  final String societyId;
  final StatementRow row;
  final VoidCallback onChanged;
  const _RowSheet({required this.societyId, required this.row, required this.onChanged});

  @override
  ConsumerState<_RowSheet> createState() => _RowSheetState();
}

class _RowSheetState extends ConsumerState<_RowSheet> {
  bool _busy = false;

  Future<void> _do(Future<void> Function() action, String done) async {
    setState(() => _busy = true);
    try {
      await action();
      widget.onChanged();
      if (mounted) {
        AppToast.success(context, done);
        Navigator.pop(context);
      }
    } catch (e) {
      if (mounted) showErrorToast(context, e);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final row = widget.row;
    final api = ref.read(bankReconciliationApiProvider);
    final suggestions = ref.watch(rowSuggestionsProvider((societyId: widget.societyId, rowId: row.id)));
    return AppSheetFrame(
      title: '${row.isCredit ? 'Received' : 'Paid'} ${formatInr(row.amount)}',
      subtitle: '${formatAccountsDate(row.txnDate)} · ${row.description}',
      footer: TextButton(
        onPressed: _busy
            ? null
            : () async {
                final reason = await askReason(
                  context,
                  title: 'Ignore this row?',
                  message:
                      'Use this for bank charges, interest or anything that is not in the books. It stays on record.',
                  action: 'Ignore',
                );
                if (reason == null || !mounted) return;
                await _do(() => api.ignore(row.id, reason), 'Row ignored');
              },
        child: const Text('Not in the books — ignore this row'),
      ),
      child: suggestions.when(
        loading: () => const Padding(padding: EdgeInsets.symmetric(vertical: 24), child: AppLoader()),
        error: (e, _) => AppErrorBanner(message: friendlyErrorMessage(e)),
        data: (list) => list.isEmpty
            ? const Padding(
                padding: EdgeInsets.symmetric(vertical: 12),
                child: Text(
                  'No payment or deposit of this amount is waiting in the books. Check that the voucher is entered and '
                  'approved, or ignore the row if it is not a transaction of the society.',
                  style: TextStyle(color: AppTheme.textSecondary, height: 1.4),
                ),
              )
            : Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
                const Text('Could be', style: TextStyle(fontWeight: FontWeight.w700)),
                const SizedBox(height: 8),
                for (final l in list)
                  Card(
                    margin: const EdgeInsets.only(bottom: 8),
                    child: ListTile(
                      title: Text('${l.voucherNumber}${l.party == null ? '' : ' · ${l.party}'}',
                          style: const TextStyle(fontWeight: FontWeight.w600)),
                      subtitle:
                          Text('${formatAccountsDate(l.date)}${(l.reference ?? '').isEmpty ? '' : ' · ${l.reference}'}'
                              '${l.referenceMatches ? ' · reference agrees' : ''}'),
                      trailing: FilledButton(
                        key: ValueKey('match-${l.voucherNumber}'),
                        onPressed: _busy
                            ? null
                            : () =>
                                _do(() => api.match(widget.societyId, row.id, l.entryId), '${l.voucherNumber} cleared'),
                        child: const Text('Match'),
                      ),
                    ),
                  ),
              ]),
      ),
    );
  }
}
