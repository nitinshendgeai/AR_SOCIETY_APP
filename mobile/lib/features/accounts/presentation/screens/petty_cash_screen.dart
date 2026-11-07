import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/layout/app_sheet.dart';
import 'package:ar_society_app/core/motion/loading.dart';
import 'package:ar_society_app/core/router/app_router.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/accounts/data/accounts_api.dart' show LedgerAccount, formatInr;
import 'package:ar_society_app/features/accounts/data/petty_cash_api.dart';
import 'package:ar_society_app/features/accounts/presentation/providers/accounts_providers.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/features/maintenance_billing/presentation/widgets/billing_sheet_frame.dart';
import 'package:ar_society_app/features/vendor/presentation/widgets/procurement_widgets.dart';
import 'package:ar_society_app/shared/widgets/app_form.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';

DateTime _today() {
  final n = DateTime.now();
  return DateTime(n.year, n.month, n.day);
}

String _day(DateTime d) => '${d.day.toString().padLeft(2, '0')}-${d.month.toString().padLeft(2, '0')}-${d.year}';

/// The society's petty cash, kept as an imprest: topped up from the bank, spent a day at a time against expense
/// heads, counted, and read back in the Petty Cash Book. Everything is posted to the books as it is entered.
class PettyCashScreen extends ConsumerWidget {
  const PettyCashScreen({super.key});

  void _open(BuildContext context, Widget sheet) => showAppSheet(context: context, builder: (_) => sheet);

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final user = ref.watch(currentUserProvider);
    final societyId = user?.societyId;
    if (societyId == null) return const Scaffold(body: Center(child: Text('No society context')));
    final box = ref.watch(pettyCashProvider(societyId));
    final counts = ref.watch(pettyCashCountsProvider(societyId));

    return AppPage(
      title: 'Petty Cash',
      subtitle: 'Small daily expenses, paid from a float and posted to the books',
      body: RefreshIndicator(
        onRefresh: () async => invalidateBooks(ref),
        child: ResponsiveBody(
          maxWidth: 820,
          child: ListView(padding: const EdgeInsets.fromLTRB(16, 16, 16, 96), children: [
            box.when(
              loading: () => const Padding(padding: EdgeInsets.all(32), child: AppLoader()),
              error: (e, _) => AppErrorBanner(message: friendlyErrorMessage(e)),
              data: (b) => _Box(box: b),
            ),
            const SizedBox(height: 16),
            Wrap(spacing: 10, runSpacing: 10, children: [
              FilledButton.icon(
                key: const ValueKey('petty-add-expenses'),
                onPressed: () => _open(context, const PettyExpensesSheet()),
                icon: const Icon(Icons.add_shopping_cart_rounded),
                label: const Text('Add expenses'),
              ),
              OutlinedButton.icon(
                key: const ValueKey('petty-top-up'),
                onPressed: () => _open(context, PettyTopUpSheet(box: box.valueOrNull)),
                icon: const Icon(Icons.account_balance_rounded),
                label: const Text('Top up from bank'),
              ),
              OutlinedButton.icon(
                key: const ValueKey('petty-count'),
                onPressed: () => _open(context, PettyCountSheet(box: box.valueOrNull)),
                icon: const Icon(Icons.fact_check_outlined),
                label: const Text('Count the cash'),
              ),
              OutlinedButton.icon(
                key: const ValueKey('petty-book'),
                onPressed: () => context.push(AppRoutes.accountsRegisterPettyCash),
                icon: const Icon(Icons.menu_book_rounded),
                label: const Text('Petty Cash Book'),
              ),
              if (user?.isAdminOrCommittee ?? false)
                OutlinedButton.icon(
                  key: const ValueKey('petty-settings'),
                  onPressed: () => _open(context, PettySettingsSheet(box: box.valueOrNull)),
                  icon: const Icon(Icons.tune_rounded),
                  label: const Text('Float and limit'),
                ),
            ]),
            const SizedBox(height: 24),
            const Text('Cash counts', style: TextStyle(fontSize: 15, fontWeight: FontWeight.w800)),
            const SizedBox(height: 8),
            counts.when(
              loading: () => const Padding(padding: EdgeInsets.all(16), child: AppLoader()),
              error: (e, _) => AppErrorBanner(message: friendlyErrorMessage(e)),
              data: (rows) => rows.isEmpty
                  ? const Card(
                      child: Padding(
                          padding: EdgeInsets.all(16),
                          child: Text('No count yet. Count the cash in the box now and then, and note it here.',
                              style: TextStyle(color: AppTheme.textSecondary))))
                  : Column(children: [for (final c in rows.take(8)) _CountTile(count: c)]),
            ),
          ]),
        ),
      ),
    );
  }
}

class _Box extends StatelessWidget {
  final PettyCash box;
  const _Box({required this.box});

  @override
  Widget build(BuildContext context) {
    final low = box.topUpNeeded != null && box.topUpNeeded! > 0;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          const Text('In the box (per the books)', style: TextStyle(fontSize: 12.5, color: AppTheme.textSecondary)),
          const SizedBox(height: 2),
          Text(formatInr(box.balance),
              key: const ValueKey('petty-balance'), style: const TextStyle(fontSize: 30, fontWeight: FontWeight.w800)),
          const SizedBox(height: 12),
          Wrap(spacing: 24, runSpacing: 8, children: [
            _Fact('Free to spend', formatInr(box.available)),
            _Fact('Spent today', formatInr(box.spentToday)),
            _Fact('Spent this month', formatInr(box.spentMonth)),
            if (box.floatAmount != null) _Fact('Float', formatInr(box.floatAmount!)),
            if (box.expenseLimit != null) _Fact('Limit per expense', formatInr(box.expenseLimit!)),
            if (box.custodianName != null) _Fact('Held by', box.custodianName!),
          ]),
          if (box.pending > 0) ...[
            const SizedBox(height: 10),
            Text('${formatInr(box.pending)} more is set aside by expenses waiting for approval.',
                key: const ValueKey('petty-pending'),
                style: const TextStyle(fontSize: 12.5, color: AppTheme.warning, fontWeight: FontWeight.w600)),
          ],
          if (low) ...[
            const SizedBox(height: 10),
            Text('Top up ${formatInr(box.topUpNeeded!)} to bring it back to the float.',
                key: const ValueKey('petty-low'),
                style: const TextStyle(fontSize: 12.5, color: AppTheme.warning, fontWeight: FontWeight.w600)),
          ],
        ]),
      ),
    );
  }
}

class _Fact extends StatelessWidget {
  final String label, value;
  const _Fact(this.label, this.value);

  @override
  Widget build(BuildContext context) => Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text(label, style: const TextStyle(fontSize: 11.5, color: AppTheme.textSecondary)),
        Text(value, style: const TextStyle(fontSize: 14.5, fontWeight: FontWeight.w700)),
      ]);
}

class _CountTile extends StatelessWidget {
  final PettyCashCount count;
  const _CountTile({required this.count});

  @override
  Widget build(BuildContext context) {
    final (label, color) = switch (count.state) {
      'short' => ('Short ${formatInr(count.difference.abs())}', AppTheme.error),
      'excess' => ('Excess ${formatInr(count.difference)}', AppTheme.warning),
      _ => ('Tallies', AppTheme.success),
    };
    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      child: ListTile(
        title: Text('${_day(count.date)} · counted ${formatInr(count.counted)}',
            style: const TextStyle(fontWeight: FontWeight.w700)),
        subtitle: Text('Books said ${formatInr(count.book)}'
            '${count.note == null ? '' : ' · ${count.note}'}${count.countedBy == null ? '' : ' · ${count.countedBy}'}'),
        trailing: Text(label, style: TextStyle(color: color, fontWeight: FontWeight.w800)),
      ),
    );
  }
}

// ── Add the day's expenses ───────────────────────────────────────────────────

class _Row {
  String? head;
  final amount = TextEditingController();
  final note = TextEditingController();
  void dispose() {
    amount.dispose();
    note.dispose();
  }
}

class PettyExpensesSheet extends ConsumerStatefulWidget {
  const PettyExpensesSheet({super.key});

  @override
  ConsumerState<PettyExpensesSheet> createState() => _PettyExpensesSheetState();
}

class _PettyExpensesSheetState extends ConsumerState<PettyExpensesSheet> {
  final _rows = <_Row>[_Row()];
  DateTime _date = _today();
  bool _saving = false;

  @override
  void dispose() {
    for (final r in _rows) {
      r.dispose();
    }
    super.dispose();
  }

  double get _total => _rows.fold(0.0, (t, r) => t + (parseMoney(r.amount.text) ?? 0));

  Future<void> _save(String societyId) async {
    final items = <Map<String, dynamic>>[];
    for (var i = 0; i < _rows.length; i++) {
      final r = _rows[i];
      final amount = parseMoney(r.amount.text) ?? 0;
      if (r.head == null && amount == 0 && r.note.text.trim().isEmpty && _rows.length > 1) continue; // an empty spare row
      if (r.head == null) {
        AppToast.warning(context, 'Expense ${i + 1}: choose what it was for');
        return;
      }
      if (amount <= 0) {
        AppToast.warning(context, 'Expense ${i + 1}: enter the amount');
        return;
      }
      items.add({
        'expense_account_id': r.head,
        'amount': amount,
        if (r.note.text.trim().isNotEmpty) 'note': r.note.text.trim(),
      });
    }
    if (items.isEmpty) {
        AppToast.warning(context, 'Add at least one expense');
        return;
      }
    setState(() => _saving = true);
    try {
      final v = await ref.read(pettyCashApiProvider).spend(societyId, date: _date, items: items);
      invalidateBooks(ref);
      if (!mounted) return;
      AppToast.success(
          context,
          '${formatInr(v.amount)} saved as ${v.voucherNumber}'
          '${v.isPending ? ' — it counts in the books once the admin or committee approves it' : ''}');
      Navigator.of(context).pop();
    } catch (e) {
      if (mounted) {
        setState(() => _saving = false);
        showErrorToast(context, e);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final societyId = ref.watch(currentUserProvider)?.societyId ?? '';
    final ledgers = ref.watch(ledgersProvider(societyId));
    return BillingSheetFrame(
      title: 'Add petty cash expenses',
      subtitle: 'One entry for the day. Each line goes to its own expense head.',
      child: ledgers.when(
        loading: () => const Padding(padding: EdgeInsets.all(24), child: AppLoader()),
        error: (e, _) => AppErrorBanner(message: friendlyErrorMessage(e)),
        data: (all) {
          final heads = all.where((l) => l.nature == 'expense' && l.isActive).toList()
            ..sort((a, b) => a.name.compareTo(b.name));
          return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
            FormFieldBox(
                label: 'Date',
                child: DateField(label: '', value: _date, required: true, lastDate: _today(), onChanged: (d) => setState(() => _date = d ?? _date))),
            const SizedBox(height: 12),
            for (var i = 0; i < _rows.length; i++) _line(i, heads),
            Align(
              alignment: Alignment.centerLeft,
              child: TextButton.icon(
                key: const ValueKey('petty-add-line'),
                onPressed: () => setState(() => _rows.add(_Row())),
                icon: const Icon(Icons.add_rounded),
                label: const Text('Add another expense'),
              ),
            ),
            const SizedBox(height: 8),
            Text('Total ${formatInr(_total)}',
                key: const ValueKey('petty-total'), style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w800)),
            const SizedBox(height: 12),
            AppPrimaryButton(
                label: 'Save expenses', isLoading: _saving, onPressed: _saving ? null : () => _save(societyId)),
          ]);
        },
      ),
    );
  }

  Widget _line(int i, List<LedgerAccount> heads) {
    final r = _rows[i];
    return Padding(
      padding: const EdgeInsets.only(bottom: 14),
      child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Expanded(
            flex: 3,
            child: DropdownButtonFormField<String>(
              key: ValueKey('petty-head-$i'),
              initialValue: heads.any((h) => h.id == r.head) ? r.head : null,
              isExpanded: true,
              decoration: InputDecoration(labelText: 'Expense ${i + 1} — what for'),
              items: [
                for (final h in heads) DropdownMenuItem(value: h.id, child: Text(h.name, overflow: TextOverflow.ellipsis)),
              ],
              onChanged: (v) => setState(() => r.head = v),
            ),
          ),
          const SizedBox(width: 10),
          Expanded(
            flex: 2,
            child: TextField(
              key: ValueKey('petty-amount-$i'),
              controller: r.amount,
              keyboardType: const TextInputType.numberWithOptions(decimal: true),
              inputFormatters: moneyInput,
              onChanged: (_) => setState(() {}),
              decoration: const InputDecoration(labelText: 'Amount', prefixText: '₹ '),
            ),
          ),
          if (_rows.length > 1)
            IconButton(
              tooltip: 'Remove',
              onPressed: () => setState(() => _rows.removeAt(i).dispose()),
              icon: const Icon(Icons.close_rounded, size: 18),
            ),
        ]),
        const SizedBox(height: 8),
        TextField(
          key: ValueKey('petty-note-$i'),
          controller: r.note,
          textCapitalization: TextCapitalization.sentences,
          decoration: const InputDecoration(labelText: 'What was bought (optional)'),
        ),
      ]),
    );
  }
}

// ── Top up from the bank ─────────────────────────────────────────────────────

class PettyTopUpSheet extends ConsumerStatefulWidget {
  final PettyCash? box;
  const PettyTopUpSheet({super.key, this.box});

  @override
  ConsumerState<PettyTopUpSheet> createState() => _PettyTopUpSheetState();
}

class _PettyTopUpSheetState extends ConsumerState<PettyTopUpSheet> {
  late final _amount = TextEditingController(
      text: (widget.box?.topUpNeeded ?? 0) > 0 ? widget.box!.topUpNeeded!.toStringAsFixed(2) : '');
  final _note = TextEditingController();
  DateTime _date = _today();
  String? _from;
  bool _saving = false;

  @override
  void dispose() {
    _amount.dispose();
    _note.dispose();
    super.dispose();
  }

  Future<void> _save(String societyId) async {
    final amount = parseMoney(_amount.text) ?? 0;
    if (amount <= 0) {
        AppToast.warning(context, 'Enter the amount to move into petty cash');
        return;
      }
    setState(() => _saving = true);
    try {
      final v = await ref.read(pettyCashApiProvider).topUp(societyId,
          amount: amount, date: _date, fromAccountId: _from, note: _note.text.trim());
      invalidateBooks(ref);
      if (!mounted) return;
      AppToast.success(context, '${formatInr(amount)} moved into petty cash as ${v.voucherNumber}');
      Navigator.of(context).pop();
    } catch (e) {
      if (mounted) {
        setState(() => _saving = false);
        showErrorToast(context, e);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final societyId = ref.watch(currentUserProvider)?.societyId ?? '';
    final ledgers = ref.watch(ledgersProvider(societyId));
    final petty = widget.box?.accountId;
    return BillingSheetFrame(
      title: 'Top up petty cash',
      subtitle: 'Money moves from the bank into the box. It is posted as a Contra voucher.',
      child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        TextField(
          key: const ValueKey('petty-topup-amount'),
          controller: _amount,
          keyboardType: const TextInputType.numberWithOptions(decimal: true),
          inputFormatters: moneyInput,
          decoration: const InputDecoration(labelText: 'Amount', prefixText: '₹ '),
        ),
        const SizedBox(height: 12),
        ledgers.when(
          loading: () => const LinearProgressIndicator(),
          error: (e, _) => AppErrorBanner(message: friendlyErrorMessage(e)),
          data: (all) {
            final sources = all.where((l) => l.isCashOrBank && l.isActive && l.id != petty).toList();
            return DropdownButtonFormField<String?>(
              initialValue: sources.any((c) => c.id == _from) ? _from : null,
              isExpanded: true,
              decoration: const InputDecoration(labelText: 'Take it from'),
              items: [
                const DropdownMenuItem<String?>(value: null, child: Text('The default bank account')),
                for (final c in sources) DropdownMenuItem<String?>(value: c.id, child: Text(c.name)),
              ],
              onChanged: (v) => setState(() => _from = v),
            );
          },
        ),
        const SizedBox(height: 12),
        FormFieldBox(
            label: 'Date',
            child: DateField(label: '', value: _date, required: true, lastDate: _today(), onChanged: (d) => setState(() => _date = d ?? _date))),
        const SizedBox(height: 12),
        TextField(controller: _note, decoration: const InputDecoration(labelText: 'Note (optional)')),
        const SizedBox(height: 16),
        AppPrimaryButton(label: 'Top up', isLoading: _saving, onPressed: _saving ? null : () => _save(societyId)),
      ]),
    );
  }
}

// ── Count the cash ───────────────────────────────────────────────────────────

class PettyCountSheet extends ConsumerStatefulWidget {
  final PettyCash? box;
  const PettyCountSheet({super.key, this.box});

  @override
  ConsumerState<PettyCountSheet> createState() => _PettyCountSheetState();
}

class _PettyCountSheetState extends ConsumerState<PettyCountSheet> {
  final _counted = TextEditingController();
  final _note = TextEditingController();
  bool _saving = false;

  @override
  void dispose() {
    _counted.dispose();
    _note.dispose();
    super.dispose();
  }

  Future<void> _save(String societyId) async {
    final counted = parseMoney(_counted.text);
    if (counted == null) {
        AppToast.warning(context, 'Enter the cash you counted');
        return;
      }
    setState(() => _saving = true);
    try {
      final c = await ref.read(pettyCashApiProvider).count(societyId, counted: counted, note: _note.text.trim());
      invalidateBooks(ref);
      if (!mounted) return;
      AppToast.success(
          context,
          c.state == 'tallies'
              ? 'The cash tallies with the books'
              : c.state == 'short'
                  ? 'Short by ${formatInr(c.difference.abs())} against the books'
                  : 'Excess of ${formatInr(c.difference)} against the books');
      Navigator.of(context).pop();
    } catch (e) {
      if (mounted) {
        setState(() => _saving = false);
        showErrorToast(context, e);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final societyId = ref.watch(currentUserProvider)?.societyId ?? '';
    final book = widget.box?.balance;
    final counted = parseMoney(_counted.text);
    final diff = counted == null || book == null ? null : counted - book;
    return BillingSheetFrame(
      title: 'Count the cash',
      subtitle: book == null ? null : 'The books say ${formatInr(book)} should be in the box.',
      child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        TextField(
          key: const ValueKey('petty-counted'),
          controller: _counted,
          autofocus: true,
          keyboardType: const TextInputType.numberWithOptions(decimal: true),
          inputFormatters: moneyInput,
          onChanged: (_) => setState(() {}),
          decoration: const InputDecoration(labelText: 'Cash counted', prefixText: '₹ '),
        ),
        if (diff != null) ...[
          const SizedBox(height: 8),
          Text(
            diff == 0 ? 'Tallies with the books.' : diff < 0 ? 'Short by ${formatInr(-diff)}.' : 'Excess of ${formatInr(diff)}.',
            key: const ValueKey('petty-count-diff'),
            style: TextStyle(fontWeight: FontWeight.w700, color: diff == 0 ? AppTheme.success : AppTheme.warning),
          ),
        ],
        const SizedBox(height: 12),
        TextField(controller: _note, decoration: const InputDecoration(labelText: 'Note (optional)')),
        const SizedBox(height: 6),
        const Text('A count only records the difference. Nothing is posted to the books.',
            style: TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
        const SizedBox(height: 16),
        AppPrimaryButton(label: 'Save count', isLoading: _saving, onPressed: _saving ? null : () => _save(societyId)),
      ]),
    );
  }
}

// ── Float and limit ──────────────────────────────────────────────────────────

class PettySettingsSheet extends ConsumerStatefulWidget {
  final PettyCash? box;
  const PettySettingsSheet({super.key, this.box});

  @override
  ConsumerState<PettySettingsSheet> createState() => _PettySettingsSheetState();
}

class _PettySettingsSheetState extends ConsumerState<PettySettingsSheet> {
  String _fmt(double? v) => v == null ? '' : v.toStringAsFixed(v % 1 == 0 ? 0 : 2);
  late final _float = TextEditingController(text: _fmt(widget.box?.floatAmount));
  late final _limit = TextEditingController(text: _fmt(widget.box?.expenseLimit));
  late final _who = TextEditingController(text: widget.box?.custodianName ?? '');
  bool _saving = false;

  @override
  void dispose() {
    for (final c in [_float, _limit, _who]) {
      c.dispose();
    }
    super.dispose();
  }

  Future<void> _save(String societyId) async {
    setState(() => _saving = true);
    try {
      await ref.read(pettyCashApiProvider).saveSettings(societyId, {
        'float_amount': parseMoney(_float.text),
        'expense_limit': parseMoney(_limit.text),
        'custodian_name': _who.text.trim().isEmpty ? null : _who.text.trim(),
      });
      invalidateBooks(ref);
      if (!mounted) return;
      AppToast.success(context, 'Saved');
      Navigator.of(context).pop();
    } catch (e) {
      if (mounted) {
        setState(() => _saving = false);
        showErrorToast(context, e);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final societyId = ref.watch(currentUserProvider)?.societyId ?? '';
    return BillingSheetFrame(
      title: 'Float and limit',
      subtitle: 'Leave a box empty for no float or no limit.',
      child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        TextField(
          key: const ValueKey('petty-float'),
          controller: _float,
          keyboardType: const TextInputType.numberWithOptions(decimal: true),
          inputFormatters: moneyInput,
          decoration: const InputDecoration(
              labelText: 'Float', prefixText: '₹ ', helperText: 'The level the box is topped back up to'),
        ),
        const SizedBox(height: 12),
        TextField(
          key: const ValueKey('petty-limit'),
          controller: _limit,
          keyboardType: const TextInputType.numberWithOptions(decimal: true),
          inputFormatters: moneyInput,
          decoration: const InputDecoration(
              labelText: 'Most for one expense', prefixText: '₹ ', helperText: 'Anything bigger is paid from the bank'),
        ),
        const SizedBox(height: 12),
        TextField(controller: _who, decoration: const InputDecoration(labelText: 'Cash held by')),
        const SizedBox(height: 16),
        AppPrimaryButton(label: 'Save', isLoading: _saving, onPressed: _saving ? null : () => _save(societyId)),
      ]),
    );
  }
}
