import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/router/app_router.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/accounts/data/accounts_api.dart';
import 'package:ar_society_app/features/accounts/presentation/providers/accounts_providers.dart';
import 'package:ar_society_app/features/accounts/presentation/widgets/accounts_widgets.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';

class _Line {
  LedgerAccount? account;
  MemberBalance? flat;
  String side; // dr | cr (journal only)
  final amount = TextEditingController();
  _Line({this.side = 'dr'});

  double get value => double.tryParse(amount.text.trim()) ?? 0;
}

/// Enter a Receipt, Payment, Contra or Journal voucher. Receipts and
/// payments are entered the way a cashier thinks — which cash/bank account,
/// and who it came from / went to — and the form builds the debit and
/// credit lines; a journal takes debit and credit lines directly.
class VoucherFormScreen extends ConsumerStatefulWidget {
  final String type;
  const VoucherFormScreen({super.key, required this.type});

  @override
  ConsumerState<VoucherFormScreen> createState() => _VoucherFormScreenState();
}

class _VoucherFormScreenState extends ConsumerState<VoucherFormScreen> {
  late String _type = kManualVoucherTypes.contains(widget.type) ? widget.type : 'receipt';
  DateTime _date = DateTime.now();
  final _reference = TextEditingController();
  final _narration = TextEditingController();
  LedgerAccount? _cashBank; // receipt: into, payment: from, contra: from
  LedgerAccount? _contraTo;
  final _contraAmount = TextEditingController();
  late List<_Line> _lines = _type == 'journal' ? [_Line(side: 'dr'), _Line(side: 'cr')] : [_Line()];
  bool _saving = false;

  @override
  void dispose() {
    for (final l in _lines) {
      l.amount.dispose();
    }
    _reference.dispose();
    _narration.dispose();
    _contraAmount.dispose();
    super.dispose();
  }

  void _setType(String t) => setState(() {
        _type = t;
        _contraTo = null;
        for (final l in _lines) {
          l.amount.dispose();
        }
        _lines = t == 'journal' ? [_Line(side: 'dr'), _Line(side: 'cr')] : [_Line()];
      });

  double get _linesTotal => _lines.fold(0, (s, l) => s + l.value);
  double get _drTotal => _lines.where((l) => l.side == 'dr').fold(0, (s, l) => s + l.value);
  double get _crTotal => _lines.where((l) => l.side == 'cr').fold(0, (s, l) => s + l.value);

  String? _validate() {
    if (_type == 'contra') {
      final amt = double.tryParse(_contraAmount.text.trim()) ?? 0;
      if (_cashBank == null || _contraTo == null) return 'Choose both cash/bank accounts';
      if (_cashBank!.id == _contraTo!.id) return 'Choose two different accounts';
      if (amt <= 0) return 'Enter the amount';
      return null;
    }
    if (_type != 'journal' && _cashBank == null) {
      return _type == 'receipt' ? 'Choose the cash or bank account received into' : 'Choose the cash or bank account paid from';
    }
    for (final l in _lines) {
      if (l.account == null) return 'Choose a ledger on every line';
      if (l.account!.isMembersDues && l.flat == null) return 'Choose the flat for ${l.account!.name}';
      if (l.value <= 0) return 'Enter an amount on every line';
    }
    if (_type == 'journal') {
      if (_drTotal == 0 || _crTotal == 0) return 'A journal needs at least one debit and one credit line';
      if ((_drTotal - _crTotal).abs() > 0.001) return 'Debits and credits must be equal';
    }
    return null;
  }

  List<VoucherLineInput> _build() {
    if (_type == 'contra') {
      final amt = double.parse(_contraAmount.text.trim());
      return [
        VoucherLineInput(accountId: _contraTo!.id, debit: amt),
        VoucherLineInput(accountId: _cashBank!.id, credit: amt),
      ];
    }
    final lines = _lines.map((l) {
      final side = _type == 'journal' ? l.side : (_type == 'receipt' ? 'cr' : 'dr');
      return VoucherLineInput(
        accountId: l.account!.id,
        debit: side == 'dr' ? l.value : 0,
        credit: side == 'cr' ? l.value : 0,
        flatId: l.flat?.flatId,
      );
    }).toList();
    if (_type == 'receipt') return [VoucherLineInput(accountId: _cashBank!.id, debit: _linesTotal), ...lines];
    if (_type == 'payment') return [...lines, VoucherLineInput(accountId: _cashBank!.id, credit: _linesTotal)];
    return lines;
  }

  Future<void> _save(String societyId) async {
    final problem = _validate();
    if (problem != null) {
      AppToast.warning(context, problem);
      return;
    }
    setState(() => _saving = true);
    try {
      final v = await ref.read(accountsApiProvider).createVoucher(
            societyId: societyId,
            type: _type,
            date: _date,
            lines: _build(),
            narration: _narration.text.trim(),
            reference: _reference.text.trim(),
          );
      invalidateBooks(ref);
      if (mounted) {
        AppToast.success(context, '${v.voucherNumber} saved');
        // Opened from a link rather than from within the app: land on the day book.
        context.canPop() ? context.pop() : context.go(AppRoutes.accountsDayBook);
      }
    } catch (e) {
      if (mounted) showErrorToast(context, e);
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  Future<void> _pickDate() async {
    final d = await showDatePicker(
      context: context,
      initialDate: _date,
      firstDate: DateTime(2000),
      lastDate: DateTime.now().add(const Duration(days: 366)),
    );
    if (d != null) setState(() => _date = d);
  }

  @override
  Widget build(BuildContext context) {
    final societyId = ref.watch(currentUserProvider)?.societyId;
    if (societyId == null) return const Scaffold(body: Center(child: Text('No society context')));
    final ledgersAsync = ref.watch(ledgersProvider(societyId));
    final ledgers = ledgersAsync.valueOrNull ?? const <LedgerAccount>[];
    final cashBank = ledgers.where((l) => l.isCashOrBank).toList();
    final others = ledgers.where((l) => !l.isCashOrBank).toList();
    _cashBank ??= _type == 'journal' ? null : cashBank.where((l) => l.isDefaultBank).firstOrNull;

    return Scaffold(
      backgroundColor: AppTheme.surface,
      appBar: AppBar(title: Text('New ${voucherTypeLabel(_type)}')),
      body: ledgersAsync.isLoading && ledgers.isEmpty
          ? const Center(child: CircularProgressIndicator())
          : ledgersAsync.hasError && ledgers.isEmpty
              ? Center(child: Text(friendlyErrorMessage(ledgersAsync.error!), style: const TextStyle(color: AppTheme.error)))
              : ResponsiveBody(
                  maxWidth: 820,
                  child: ListView(
                    padding: const EdgeInsets.fromLTRB(16, 16, 16, 40),
                    children: [
                      SegmentedButton<String>(
                        showSelectedIcon: false,
                        style: const ButtonStyle(
                          visualDensity: VisualDensity.compact,
                          padding: WidgetStatePropertyAll(EdgeInsets.symmetric(horizontal: 4)),
                          textStyle: WidgetStatePropertyAll(TextStyle(fontSize: 13, fontWeight: FontWeight.w600)),
                        ),
                        segments: [
                          for (final t in kManualVoucherTypes)
                            ButtonSegment(value: t, label: Text(voucherTypeLabel(t), maxLines: 1, softWrap: false)),
                        ],
                        selected: {_type},
                        onSelectionChanged: (s) => _setType(s.first),
                      ),
                      const SizedBox(height: 8),
                      Text(voucherTypeHint(_type), style: const TextStyle(fontSize: 12.5, color: AppTheme.textSecondary)),
                      const SizedBox(height: 16),
                      _Card(children: [
                        Row(children: [
                          Expanded(
                            child: InkWell(
                              onTap: _pickDate,
                              child: InputDecorator(
                                decoration: const InputDecoration(
                                    labelText: 'Date', suffixIcon: Icon(Icons.calendar_today_rounded, size: 18)),
                                child: Text(formatAccountsDate(_date)),
                              ),
                            ),
                          ),
                          const SizedBox(width: 12),
                          Expanded(
                            child: TextField(
                              controller: _reference,
                              decoration: const InputDecoration(labelText: 'Reference', hintText: 'Cheque / UTR / bill no.'),
                            ),
                          ),
                        ]),
                        if (_type == 'receipt' || _type == 'payment' || _type == 'contra') ...[
                          const SizedBox(height: 12),
                          _LedgerField(
                            label: switch (_type) {
                              'receipt' => 'Received into',
                              'payment' => 'Paid from',
                              _ => 'From (cash / bank)',
                            },
                            value: _cashBank,
                            onTap: () async {
                              final l = await pickLedger(context, cashBank, title: 'Cash or bank account');
                              if (l != null) setState(() => _cashBank = l);
                            },
                          ),
                        ],
                        if (_type == 'contra') ...[
                          const SizedBox(height: 12),
                          _LedgerField(
                            label: 'To (cash / bank)',
                            value: _contraTo,
                            onTap: () async {
                              final l = await pickLedger(context, cashBank, title: 'Cash or bank account');
                              if (l != null) setState(() => _contraTo = l);
                            },
                          ),
                          const SizedBox(height: 12),
                          _AmountField(controller: _contraAmount, onChanged: () => setState(() {})),
                        ],
                      ]),
                      if (_type != 'contra') ...[
                        const SizedBox(height: 16),
                        Padding(
                          padding: const EdgeInsets.only(left: 2, bottom: 8),
                          child: Text(
                            switch (_type) {
                              'receipt' => 'Received from / towards',
                              'payment' => 'Paid to / for',
                              _ => 'Debit and credit lines',
                            },
                            style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w700),
                          ),
                        ),
                        for (final (i, l) in _lines.indexed)
                          _LineCard(
                            key: ObjectKey(l),
                            line: l,
                            journal: _type == 'journal',
                            ledgers: others,
                            societyId: societyId,
                            onChanged: () => setState(() {}),
                            onRemove: _lines.length > (_type == 'journal' ? 2 : 1)
                                ? () => setState(() {
                                      _lines.removeAt(i);
                                      l.amount.dispose();
                                    })
                                : null,
                          ),
                        Align(
                          alignment: Alignment.centerLeft,
                          child: TextButton.icon(
                            onPressed: () => setState(() => _lines.add(_Line(
                                side: _type == 'journal' && _drTotal > _crTotal ? 'cr' : 'dr'))),
                            icon: const Icon(Icons.add_rounded, size: 18),
                            label: const Text('Add line'),
                          ),
                        ),
                        _Totals(
                          journal: _type == 'journal',
                          total: _linesTotal,
                          dr: _drTotal,
                          cr: _crTotal,
                        ),
                      ],
                      const SizedBox(height: 16),
                      _Card(children: [
                        TextField(
                          controller: _narration,
                          minLines: 2,
                          maxLines: 4,
                          decoration: const InputDecoration(
                              labelText: 'Narration', hintText: 'e.g. MSEDCL electricity bill for Aug-2026'),
                        ),
                      ]),
                      const SizedBox(height: 20),
                      AppPrimaryButton(
                        label: 'Save ${voucherTypeLabel(_type)}',
                        icon: Icons.check_rounded,
                        isLoading: _saving,
                        onPressed: () => _save(societyId),
                      ),
                    ],
                  ),
                ),
    );
  }
}

class _Card extends StatelessWidget {
  final List<Widget> children;
  const _Card({required this.children});

  @override
  Widget build(BuildContext context) => Container(
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(color: AppTheme.cardBg, borderRadius: BorderRadius.circular(AppTheme.radiusM)),
        child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: children),
      );
}

class _LedgerField extends StatelessWidget {
  final String label;
  final LedgerAccount? value;
  final VoidCallback onTap;
  const _LedgerField({required this.label, required this.value, required this.onTap});

  @override
  Widget build(BuildContext context) => InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(AppTheme.radiusS),
        child: InputDecorator(
          decoration: InputDecoration(labelText: label, suffixIcon: const Icon(Icons.arrow_drop_down_rounded)),
          child: Text(value?.name ?? 'Choose ledger',
              overflow: TextOverflow.ellipsis,
              style: TextStyle(color: value == null ? AppTheme.textTertiary : AppTheme.textPrimary)),
        ),
      );
}

class _AmountField extends StatelessWidget {
  final TextEditingController controller;
  final VoidCallback onChanged;
  const _AmountField({required this.controller, required this.onChanged});

  @override
  Widget build(BuildContext context) => TextField(
        controller: controller,
        onChanged: (_) => onChanged(),
        keyboardType: const TextInputType.numberWithOptions(decimal: true),
        inputFormatters: [FilteringTextInputFormatter.allow(RegExp(r'^\d*\.?\d{0,2}'))],
        textAlign: TextAlign.right,
        decoration: const InputDecoration(labelText: 'Amount (₹)', hintText: '0.00'),
      );
}

class _LineCard extends ConsumerWidget {
  final _Line line;
  final bool journal;
  final List<LedgerAccount> ledgers;
  final String societyId;
  final VoidCallback onChanged;
  final VoidCallback? onRemove;
  const _LineCard({
    super.key,
    required this.line,
    required this.journal,
    required this.ledgers,
    required this.societyId,
    required this.onChanged,
    this.onRemove,
  });

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final needsFlat = line.account?.isMembersDues ?? false;
    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      padding: const EdgeInsets.fromLTRB(14, 12, 6, 12),
      decoration: BoxDecoration(color: AppTheme.cardBg, borderRadius: BorderRadius.circular(AppTheme.radiusM)),
      child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Expanded(
          child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
            if (journal) ...[
              Align(
                alignment: Alignment.centerLeft,
                child: SegmentedButton<String>(
                  showSelectedIcon: false,
                  segments: const [
                    ButtonSegment(value: 'dr', label: Text('Debit (Dr)')),
                    ButtonSegment(value: 'cr', label: Text('Credit (Cr)')),
                  ],
                  selected: {line.side},
                  onSelectionChanged: (s) {
                    line.side = s.first;
                    onChanged();
                  },
                ),
              ),
              const SizedBox(height: 10),
            ],
            LayoutBuilder(builder: (context, c) {
              final ledgerField = _LedgerField(
                label: 'Ledger',
                value: line.account,
                onTap: () async {
                  final l = await pickLedger(context, ledgers);
                  if (l != null) {
                    line.account = l;
                    if (!l.isMembersDues) line.flat = null;
                    onChanged();
                  }
                },
              );
              final amount = _AmountField(controller: line.amount, onChanged: onChanged);
              if (c.maxWidth < 460) {
                return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
                  ledgerField,
                  const SizedBox(height: 10),
                  amount,
                ]);
              }
              return Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Expanded(flex: 3, child: ledgerField),
                const SizedBox(width: 10),
                Expanded(flex: 2, child: amount),
              ]);
            }),
            if (needsFlat) ...[
              const SizedBox(height: 10),
              InkWell(
                onTap: () async {
                  final members = await ref.read(membersLedgerProvider(societyId).future);
                  if (!context.mounted) return;
                  final f = await pickFlat(context, members.members);
                  if (f != null) {
                    line.flat = f;
                    onChanged();
                  }
                },
                child: InputDecorator(
                  decoration: const InputDecoration(labelText: 'Flat', suffixIcon: Icon(Icons.arrow_drop_down_rounded)),
                  child: Text(line.flat == null ? 'Choose flat' : '${line.flat!.flatLabel} · ${line.flat!.memberName}',
                      style: TextStyle(color: line.flat == null ? AppTheme.textTertiary : AppTheme.textPrimary)),
                ),
              ),
            ],
          ]),
        ),
        IconButton(
          tooltip: 'Remove line',
          onPressed: onRemove,
          icon: const Icon(Icons.close_rounded, size: 18),
        ),
      ]),
    );
  }
}

class _Totals extends StatelessWidget {
  final bool journal;
  final double total;
  final double dr;
  final double cr;
  const _Totals({required this.journal, required this.total, required this.dr, required this.cr});

  @override
  Widget build(BuildContext context) {
    const style = TextStyle(fontSize: 14, fontWeight: FontWeight.w700, fontFeatures: [FontFeature.tabularFigures()]);
    if (!journal) {
      return Padding(
        padding: const EdgeInsets.fromLTRB(4, 4, 4, 0),
        child: Row(children: [
          const Expanded(child: Text('Total', style: style)),
          Text(formatInr(total), style: style),
        ]),
      );
    }
    final diff = dr - cr;
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: diff.abs() < 0.001 && dr > 0 ? AppTheme.successSoft : AppTheme.warningSoft,
        borderRadius: BorderRadius.circular(AppTheme.radiusS),
      ),
      child: Row(children: [
        Expanded(child: Text('Dr ${formatInr(dr)}   ·   Cr ${formatInr(cr)}', style: style)),
        Text(
          diff.abs() < 0.001 ? (dr > 0 ? 'Balanced' : '') : 'Difference ${formatInr(diff.abs())}',
          style: TextStyle(
              fontSize: 13,
              fontWeight: FontWeight.w600,
              color: diff.abs() < 0.001 ? AppTheme.success : AppTheme.warning),
        ),
      ]),
    );
  }
}
