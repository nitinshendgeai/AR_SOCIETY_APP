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
///    payments and deposits the bank has not cleared yet, and the balance the bank statement should show, checked
///    against the balance the bank's own statement closes with (read from the uploaded PDF, or typed). Upload the
///    statement here; tick the lines the bank has cleared and say on which day; record the bank's own charges and
///    interest in the books from the "in the bank, not in your books" list.
///  * **Match** — two grids side by side: our bank entries not yet cleared, and the bank statement's rows not yet matched.
///    Tick what belongs together; when the totals are equal, *Match selected* clears them.
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
  // the Match tab: lines of the books and rows of the bank statement ticked by hand
  final _pickedEntries = <String>{};
  final _pickedRows = <String>{};
  final _today = DateTime.now();
  String _gridSearch = '';
  String? _rowFilter = 'unmatched';
  bool _busy = false;

  /// Everything a clearing or a match can change.
  void _refresh(String societyId) {
    ref.invalidate(bankReconciliationProvider);
    ref.invalidate(clearedLinesProvider);
    ref.invalidate(statementRowsProvider(societyId));
    ref.invalidate(rowSuggestionsProvider);
    setState(() {
      _picked.clear();
      _pickedEntries.clear();
      _pickedRows.clear();
    });
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
    final result = await FilePicker.platform
        .pickFiles(type: FileType.custom, allowedExtensions: ['pdf', 'csv'], withData: true);
    final picked = result?.files.single;
    if (picked == null) return;
    final bytes = picked.bytes ?? (picked.path != null ? await File(picked.path!).readAsBytes() : null);
    if (bytes == null) return;
    await _run(societyId, () async {
      final api = ref.read(bankReconciliationApiProvider);
      final imported = await api.importStatement(societyId, bytes: bytes, fileName: picked.name, accountId: _accountId);
      var message = imported.message(formatAccountsDate);
      // reconcile as on the day the statement closes, and match what can only mean one entry of the books
      final on = imported.statementDate;
      if (on != null && mounted) {
        final today = DateTime.now();
        setState(() => _asOn = on.isAfter(today) ? today : DateTime(on.year, on.month, on.day));
      }
      if (imported.imported > 0) {
        final r = await api.autoMatch(societyId, accountId: _accountId);
        if (r.matched > 0) message += ' · ${r.matched} matched with your books automatically';
      }
      return message;
    });
  }

  /// The closing balance the bank statement shows on the "as on" day, typed in (a PDF import stores it by itself).
  Future<void> _enterBalance(String societyId, BankReconciliation b) async {
    final accountId = _accountId;
    if (accountId == null) return;
    final c = TextEditingController(text: b.statementBalance?.toStringAsFixed(2) ?? '');
    final value = await showDialog<double>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Balance on the bank statement'),
        content: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text('The closing balance the bank\'s statement shows on ${formatAccountsDate(_asOn)}.',
              style: const TextStyle(fontSize: 13, color: AppTheme.textSecondary)),
          const SizedBox(height: 12),
          TextField(
            key: const ValueKey('statement-balance-field'),
            controller: c,
            autofocus: true,
            keyboardType: const TextInputType.numberWithOptions(decimal: true),
            decoration: const InputDecoration(prefixText: '₹ '),
          ),
        ]),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Cancel')),
          TextButton(
            onPressed: () {
              final n = double.tryParse(c.text.replaceAll(',', '').trim());
              if (n != null) Navigator.pop(ctx, n);
            },
            child: const Text('Save'),
          ),
        ],
      ),
    );
    if (value == null || !mounted) return;
    await _run(societyId, () async {
      await ref.read(bankReconciliationApiProvider).setStatementBalance(societyId,
          accountId: accountId, asOn: DateTime(_asOn.year, _asOn.month, _asOn.day), balance: value);
      return 'Statement balance saved';
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
      length: 4,
      child: AppPage(
        title: 'Bank Reconciliation',
        subtitle: 'Match the bank statement with the books',
        bottom: const TabBar(tabs: [Tab(text: 'Statement'), Tab(text: 'Match'), Tab(text: 'Bank rows'), Tab(text: 'Cleared')]),
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
                      _matchTab(societyId),
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
                  _pickedEntries.clear();
                  _pickedRows.clear();
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
                _uploadBar(societyId),
                _SummaryCard(b, onEnterBalance: _busy ? null : () => _enterBalance(societyId, b)),
                if (b.bankOnlyRows.isNotEmpty)
                  Padding(
                    padding: const EdgeInsets.only(top: 18),
                    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                      const Text('In the bank, not in your books',
                          style: TextStyle(fontSize: 15, fontWeight: FontWeight.w700)),
                      const SizedBox(height: 2),
                      const Text(
                          'Charges, interest or credits the bank made on its own. Tap one to record it in the books, or to match it to an entry.',
                          style: TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
                      const SizedBox(height: 8),
                      for (final r in b.bankOnlyRows) _RowTile(row: r, onTap: () => _openRow(societyId, r)),
                    ]),
                  ),
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

  /// Step one of a reconciliation: hand over the bank's statement. It is read, checked, matched and compared.
  Widget _uploadBar(String societyId) => Padding(
        padding: const EdgeInsets.only(bottom: 12),
        child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          FilledButton.tonalIcon(
            key: const ValueKey('upload-statement'),
            onPressed: _busy ? null : () => _import(societyId),
            icon: const Icon(Icons.upload_file_rounded),
            label: const Text('Upload bank statement'),
          ),
          const SizedBox(height: 4),
          const Text(
              'Any bank\'s PDF (downloaded from net banking) or a CSV. It is read, checked, matched with your books and compared with the balance below.',
              style: TextStyle(fontSize: 11.5, color: AppTheme.textSecondary)),
        ]),
      );

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

  // ── Match: two grids ───────────────────────────────────────────────────────

  bool _hit(List<String?> parts, double amount) {
    final q = _gridSearch.trim().toLowerCase();
    if (q.isEmpty) return true;
    return parts.any((p) => (p ?? '').toLowerCase().contains(q)) || amount.toStringAsFixed(2).contains(q);
  }

  Widget _matchTab(String societyId) {
    final brs = ref.watch(bankReconciliationProvider((societyId: societyId, accountId: _accountId, asOn: _today)));
    final rowsAsync = ref.watch(statementRowsProvider(societyId));
    Widget failed(Object e) =>
        ListView(padding: const EdgeInsets.all(16), children: [AppErrorBanner(message: friendlyErrorMessage(e))]);
    return brs.when(
      loading: () => const AppLoader(),
      error: (e, _) => failed(e),
      data: (b) => rowsAsync.when(
        loading: () => const AppLoader(),
        error: (e, _) => failed(e),
        data: (all) {
          final entries = [...b.paymentsNotCleared, ...b.depositsNotCleared]..sort((a, c) => a.date.compareTo(c.date));
          final rows = all
              .where((r) => r.isUnmatched && (r.bankAccountId == null || r.bankAccountId == _accountId))
              .toList()
            ..sort((a, c) => a.txnDate.compareTo(c.txnDate));
          final shownEntries = entries
              .where((l) => _hit([l.voucherNumber, l.party, l.narration, l.reference], l.amount))
              .toList();
          final shownRows = rows.where((r) => _hit([r.description, r.reference], r.amount)).toList();
          final entriesPanel = _GridPanel(
            title: 'Our bank entries',
            count: entries.length,
            empty: 'Nothing waiting: every entry has been cleared',
            children: [
              for (final l in shownEntries)
                CheckboxListTile(
                  key: ValueKey('match-entry-${l.entryId}'),
                  dense: true,
                  value: _pickedEntries.contains(l.entryId),
                  onChanged: (v) => setState(() => v == true ? _pickedEntries.add(l.entryId) : _pickedEntries.remove(l.entryId)),
                  controlAffinity: ListTileControlAffinity.leading,
                  title: Text('${l.voucherNumber}${l.party == null ? '' : ' · ${l.party}'}',
                      maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontWeight: FontWeight.w600)),
                  subtitle: Text(
                      [
                        formatAccountsDate(l.date),
                        if ((l.reference ?? '').isNotEmpty) l.reference!,
                        if ((l.narration ?? '').isNotEmpty) l.narration!,
                      ].join(' · '),
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis),
                  secondary: Text('${l.isDeposit ? '' : '− '}${formatInr(l.amount)}',
                      style: TextStyle(fontWeight: FontWeight.w700, color: l.isDeposit ? AppTheme.success : AppTheme.textPrimary)),
                ),
            ],
          );
          final rowsPanel = _GridPanel(
            title: 'Bank statement rows',
            count: rows.length,
            empty: 'No unmatched rows: upload the bank statement on the Statement tab',
            children: [
              for (final r in shownRows)
                CheckboxListTile(
                  key: ValueKey('match-row-${r.id}'),
                  dense: true,
                  value: _pickedRows.contains(r.id),
                  onChanged: (v) => setState(() => v == true ? _pickedRows.add(r.id) : _pickedRows.remove(r.id)),
                  controlAffinity: ListTileControlAffinity.leading,
                  title: Text(r.description, maxLines: 2, overflow: TextOverflow.ellipsis),
                  subtitle: Text([formatAccountsDate(r.txnDate), if ((r.reference ?? '').isNotEmpty) r.reference!].join(' · ')),
                  secondary: Text('${r.isCredit ? '' : '− '}${formatInr(r.amount)}',
                      style: TextStyle(fontWeight: FontWeight.w700, color: r.isCredit ? AppTheme.success : AppTheme.textPrimary)),
                ),
            ],
          );
          return Column(children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 4, 16, 8),
              child: TextField(
                key: const ValueKey('grid-search'),
                decoration: const InputDecoration(
                    hintText: 'Search both lists: amount, reference, name',
                    prefixIcon: Icon(Icons.search_rounded),
                    isDense: true),
                onChanged: (v) => setState(() => _gridSearch = v),
              ),
            ),
            Expanded(
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 12),
                child: LayoutBuilder(
                  builder: (_, c) => c.maxWidth >= 720
                      ? Row(children: [Expanded(child: entriesPanel), const SizedBox(width: 8), Expanded(child: rowsPanel)])
                      : Column(children: [Expanded(child: entriesPanel), const SizedBox(height: 8), Expanded(child: rowsPanel)]),
                ),
              ),
            ),
            _matchBar(societyId, entries, rows),
          ]);
        },
      ),
    );
  }

  /// The totals of what is ticked on each side, and Match selected once they agree.
  Widget _matchBar(String societyId, List<BrsLine> entries, List<StatementRow> rows) {
    final selE = entries.where((l) => _pickedEntries.contains(l.entryId)).toList();
    final selR = rows.where((r) => _pickedRows.contains(r.id)).toList();
    int cents(double v) => (v * 100).round();
    final eTotal = selE.fold<int>(0, (s, l) => s + cents(l.amount));
    final rTotal = selR.fold<int>(0, (s, r) => s + cents(r.amount));
    String? problem;
    if (selE.isEmpty || selR.isEmpty) {
      problem = 'Tick the entries on one side and the bank rows they belong to on the other.';
    } else if (selE.any((l) => l.isDeposit != selE.first.isDeposit) || selR.any((r) => r.isCredit != selR.first.isCredit)) {
      problem = 'Tick deposits with bank credits, or payments with bank debits, not both together.';
    } else if (selE.first.isDeposit != selR.first.isCredit) {
      problem = 'A bank credit belongs to a deposit, and a bank debit to a payment.';
    } else if (selE.length > 1 && selR.length > 1) {
      problem = 'Match one bank row to several entries, or several bank rows to one entry.';
    } else if (eTotal != rTotal) {
      problem = 'The totals differ by ${formatInr((eTotal - rTotal).abs() / 100)}.';
    }
    final ok = problem == null;
    return Material(
      elevation: 8,
      color: Colors.white,
      child: SafeArea(
        top: false,
        child: Padding(
          padding: const EdgeInsets.fromLTRB(16, 10, 16, 10),
          child: Row(children: [
            Expanded(
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text('Entries ${selE.length} · ${formatInr(eTotal / 100)}    Bank rows ${selR.length} · ${formatInr(rTotal / 100)}',
                    key: const ValueKey('match-totals'), style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600)),
                const SizedBox(height: 2),
                Text(problem ?? 'Totals agree: ready to match.',
                    key: const ValueKey('match-hint'),
                    style: TextStyle(fontSize: 12, color: ok ? AppTheme.success : AppTheme.textSecondary)),
              ]),
            ),
            const SizedBox(width: 12),
            FilledButton(
              key: const ValueKey('match-selected'),
              onPressed: !ok || _busy
                  ? null
                  : () => _run(societyId, () async {
                        await ref.read(bankReconciliationApiProvider).matchSelected(societyId,
                            rowIds: [for (final r in selR) r.id], entryIds: [for (final l in selE) l.entryId]);
                        return '${selE.length} ${selE.length == 1 ? 'entry' : 'entries'} matched with '
                            '${selR.length} bank ${selR.length == 1 ? 'row' : 'rows'}';
                      }),
              child: const Text('Match selected'),
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
              'Import your bank\'s statement (any bank\'s text PDF), or a CSV with Date, Description, Amount (negative = debit) or Debit and Credit, Reference optional',
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

/// One of the two grids of the Match tab: a titled card with a scrolling list of tick rows.
class _GridPanel extends StatelessWidget {
  final String title;
  final int count;
  final String empty;
  final List<Widget> children;
  const _GridPanel({required this.title, required this.count, required this.empty, required this.children});

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: EdgeInsets.zero,
      clipBehavior: Clip.antiAlias,
      child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(14, 10, 14, 6),
          child: Text('$title ($count)', style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w700)),
        ),
        const Divider(height: 1),
        Expanded(
          child: children.isEmpty
              ? Center(
                  child: Padding(
                      padding: const EdgeInsets.all(16),
                      child: Text(empty,
                          textAlign: TextAlign.center,
                          style: const TextStyle(fontSize: 12.5, color: AppTheme.textSecondary))))
              : ListView(children: children),
        ),
      ]),
    );
  }
}

/// Balance as per the books, plus the payments and less the deposits the bank has not cleared, is the balance the bank
/// statement shows.
class _SummaryCard extends StatelessWidget {
  final BankReconciliation b;
  final VoidCallback? onEnterBalance;
  const _SummaryCard(this.b, {this.onEnterBalance});

  /// The proof: does the balance the bank's statement shows agree with the balance worked out above?
  Widget _check() {
    if (!b.hasStatementBalance) {
      return Padding(
        padding: const EdgeInsets.only(top: 8),
        child: Row(children: [
          const Expanded(
              child: Text('Not checked against the bank statement yet — upload it, or enter its closing balance.',
                  style: TextStyle(fontSize: 12, color: AppTheme.textSecondary))),
          TextButton(
              key: const ValueKey('enter-statement-balance'), onPressed: onEnterBalance, child: const Text('Enter balance')),
        ]),
      );
    }
    final (color, soft, icon, text) = switch (b.status) {
      'reconciled' => (
          AppTheme.success,
          AppTheme.successSoft,
          Icons.check_circle_rounded,
          'Reconciled — the books agree with the bank statement.'
        ),
      'bank_items_to_book' => (
          AppTheme.warning,
          AppTheme.warningSoft,
          Icons.pending_rounded,
          'Differs by ${formatInr((b.difference ?? 0).abs())} — exactly the bank\'s own items listed below. Record them in the books to finish.'
        ),
      _ => (
          AppTheme.error,
          AppTheme.errorSoft,
          Icons.error_outline_rounded,
          '${formatInr((b.unexplained ?? 0).abs())} is still unexplained after the bank\'s own items. Check that the whole statement is uploaded and that "As on" is the statement\'s last day.'
        ),
    };
    return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      const SizedBox(height: 6),
      _row('Balance as per the bank statement', b.statementBalance!),
      Container(
        key: const ValueKey('reconciliation-verdict'),
        margin: const EdgeInsets.only(top: 6),
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(color: soft, borderRadius: BorderRadius.circular(10)),
        child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Icon(icon, color: color, size: 20),
          const SizedBox(width: 8),
          Expanded(child: Text(text, style: const TextStyle(fontSize: 13, height: 1.35))),
        ]),
      ),
      Align(
        alignment: Alignment.centerRight,
        child: TextButton(onPressed: onEnterBalance, child: const Text('Change statement balance')),
      ),
    ]);
  }

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
          _check(),
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
                      'Use this only for a row that is not the society\'s money. Bank charges and interest belong in the books: record them instead. It stays on record.',
                  action: 'Ignore',
                );
                if (reason == null || !mounted) return;
                await _do(() => api.ignore(row.id, reason), 'Row ignored');
              },
        child: const Text('Not in the books — ignore this row'),
      ),
      child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        _suggestionList(suggestions, api, row),
        _BookIt(
          societyId: widget.societyId,
          row: row,
          busy: _busy,
          onBook: (ledgerId) => _do(() => api.book(widget.societyId, row.id, ledgerId), 'Recorded in the books and cleared'),
        ),
      ]),
    );
  }

  Widget _suggestionList(AsyncValue<List<BrsLine>> suggestions, BankReconciliationApi api, StatementRow row) {
    return suggestions.when(
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
    );
  }
}

/// Records a row the bank made on its own (charges, interest, a direct credit) in the books, against the ledger it
/// belongs to. The bank has already done it, so the entry is cleared at once.
class _BookIt extends ConsumerStatefulWidget {
  final String societyId;
  final StatementRow row;
  final bool busy;
  final ValueChanged<String> onBook;
  const _BookIt({required this.societyId, required this.row, required this.busy, required this.onBook});

  @override
  ConsumerState<_BookIt> createState() => _BookItState();
}

class _BookItState extends ConsumerState<_BookIt> {
  String? _ledgerId;

  @override
  Widget build(BuildContext context) {
    final credit = widget.row.isCredit;
    final all = ref.watch(ledgersProvider(widget.societyId)).valueOrNull ?? const <LedgerAccount>[];
    final options = all
        .where((l) =>
            l.isActive && !l.isBank && !l.isCash && l.systemKey != 'members_dues' && l.systemKey != 'sundry_creditors')
        .toList()
      ..sort((a, b) => a.name.toLowerCase().compareTo(b.name.toLowerCase()));
    if (options.isEmpty) return const SizedBox.shrink();
    // the usual home of a bank's own debit is bank charges, and of its own credit the savings interest
    _ledgerId ??= options.where((l) => l.systemKey == (credit ? 'interest_sb' : 'bank_charges')).firstOrNull?.id;
    return Padding(
      padding: const EdgeInsets.only(top: 16),
      child: Card(
        child: Padding(
          padding: const EdgeInsets.all(14),
          child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
            const Text('Not in your books yet?', style: TextStyle(fontWeight: FontWeight.w700)),
            const SizedBox(height: 4),
            Text(
                credit
                    ? 'Interest or a credit the bank made on its own. Record it as received into:'
                    : 'Charges or a payment the bank made on its own. Record it as paid to:',
                style: const TextStyle(fontSize: 12.5, color: AppTheme.textSecondary, height: 1.35)),
            const SizedBox(height: 8),
            DropdownButtonFormField<String>(
              key: ValueKey('book-ledger-$_ledgerId'),
              initialValue: _ledgerId,
              isExpanded: true,
              menuMaxHeight: 320,
              hint: const Text('Choose a ledger'),
              items: [for (final l in options) DropdownMenuItem(value: l.id, child: Text(l.name, overflow: TextOverflow.ellipsis))],
              onChanged: (v) => setState(() => _ledgerId = v),
            ),
            const SizedBox(height: 10),
            FilledButton(
              key: const ValueKey('book-row'),
              onPressed: widget.busy || _ledgerId == null ? null : () => widget.onBook(_ledgerId!),
              child: const Text('Record in books'),
            ),
          ]),
        ),
      ),
    );
  }
}
