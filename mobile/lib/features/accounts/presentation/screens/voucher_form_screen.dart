import 'package:flutter/material.dart';
import 'package:ar_society_app/core/motion/loading.dart';
import 'package:ar_society_app/features/vendor/presentation/widgets/vendor_picker.dart';
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
import 'package:ar_society_app/shared/widgets/app_form.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';
import 'package:ar_society_app/shared/widgets/app_form.dart';

class _Line {
  LedgerAccount? account;
  MemberBalance? flat;
  String side; // dr | cr (journal only)
  final amount = TextEditingController();
  // Kept as they were when an existing voucher is edited.
  String? vendorId;
  String? narration;
  _Line({this.side = 'dr'});

  double get value => double.tryParse(amount.text.trim()) ?? 0;
}

/// Enter a Receipt, Payment, Contra or Journal voucher. Receipts and
/// payments are entered the way a cashier thinks — which cash/bank account,
/// and who it came from / went to — and the form builds the debit and
/// credit lines; a journal takes debit and credit lines directly.
///
/// With [voucherId]: correct that voucher (same type), giving a reason; the
/// earlier version stays in its history.
class VoucherFormScreen extends ConsumerStatefulWidget {
  final String type;
  final String? voucherId;
  const VoucherFormScreen({super.key, required this.type, this.voucherId});

  @override
  ConsumerState<VoucherFormScreen> createState() => _VoucherFormScreenState();
}

class _VoucherFormScreenState extends ConsumerState<VoucherFormScreen> {
  late String _type = kManualVoucherTypes.contains(widget.type) ? widget.type : 'receipt';
  DateTime _date = DateTime.now();
  final _reference = TextEditingController();
  String? _vendorId; // who was paid (a payment), from the Vendor Master
  final _narration = TextEditingController();
  LedgerAccount? _cashBank; // receipt: into, payment: from, contra: from
  LedgerAccount? _contraTo;
  final _contraAmount = TextEditingController();
  late List<_Line> _lines = _type == 'journal' ? [_Line(side: 'dr'), _Line(side: 'cr')] : [_Line()];
  final _reason = TextEditingController();
  bool _saving = false;
  Voucher? _editing;
  Object? _loadError;

  bool get _isEdit => widget.voucherId != null;

  @override
  void initState() {
    super.initState();
    if (_isEdit) _load();
  }

  /// Fill the form from the voucher being edited.
  Future<void> _load() async {
    final societyId = ref.read(currentUserProvider)?.societyId;
    if (societyId == null) return;
    try {
      final api = ref.read(accountsApiProvider);
      final v = await api.voucher(widget.voucherId!);
      final ledgers = await api.ledgers(societyId);
      final members =
          v.entries.any((e) => e.flatId != null) ? (await api.members(societyId)).members : const <MemberBalance>[];
      if (!mounted) return;
      LedgerAccount? find(String id) => ledgers.where((l) => l.id == id).firstOrNull;
      _Line line(VoucherEntry e) {
        final dr = e.debit > 0;
        return _Line(side: dr ? 'dr' : 'cr')
          ..account = find(e.accountId)
          ..flat = e.flatId == null ? null : members.where((m) => m.flatId == e.flatId).firstOrNull
          ..vendorId = e.vendorId
          ..narration = e.narration
          ..amount.text = (dr ? e.debit : e.credit).toStringAsFixed(2);
      }

      setState(() {
        _editing = v;
        _type = v.voucherType;
        _date = v.voucherDate;
        _reference.text = v.reference ?? '';
        _vendorId = v.vendorId;
        _narration.text = v.narration ?? '';
        for (final l in _lines) {
          l.amount.dispose();
        }
        switch (v.voucherType) {
          case 'contra':
            _contraTo = find(v.debits.first.accountId);
            _cashBank = find(v.credits.first.accountId);
            _contraAmount.text = v.amount.toStringAsFixed(2);
            _lines = [];
          case 'receipt':
            _cashBank = find(v.debits.first.accountId);
            _lines = v.credits.map(line).toList();
          case 'payment':
            _cashBank = find(v.credits.first.accountId);
            _lines = v.debits.map(line).toList();
          default:
            _lines = v.entries.map(line).toList();
        }
      });
    } catch (e) {
      if (mounted) setState(() => _loadError = e);
    }
  }

  @override
  void dispose() {
    for (final l in _lines) {
      l.amount.dispose();
    }
    _reference.dispose();
    _narration.dispose();
    _contraAmount.dispose();
    _reason.dispose();
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
      return _type == 'receipt'
          ? 'Choose the cash or bank account received into'
          : 'Choose the cash or bank account paid from';
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
    if (_isEdit && _reason.text.trim().length < 3) return 'Give the reason for the change';
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
        vendorId: l.vendorId,
        narration: l.narration,
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
      final api = ref.read(accountsApiProvider);
      final v = _isEdit
          ? await api.updateVoucher(
              widget.voucherId!,
              date: _date,
              lines: _build(),
              narration: _narration.text.trim(),
              reference: _reference.text.trim(),
              vendorId: _type == 'payment' ? _vendorId : null,
              reason: _reason.text.trim(),
            )
          : await api.createVoucher(
              societyId: societyId,
              type: _type,
              date: _date,
              lines: _build(),
              narration: _narration.text.trim(),
              reference: _reference.text.trim(),
              vendorId: _type == 'payment' ? _vendorId : null,
            );
      invalidateBooks(ref);
      if (mounted) {
        AppToast.success(context, _isEdit ? '${v.voucherNumber} updated' : '${v.voucherNumber} saved');
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
    if (!_isEdit) _cashBank ??= _type == 'journal' ? null : cashBank.where((l) => l.isDefaultBank).firstOrNull;
    final loadError = _loadError ?? (ledgers.isEmpty ? ledgersAsync.error : null);
    final editing = _editing;

    final title = _isEdit ? 'Edit ${editing?.voucherNumber ?? 'voucher'}' : 'New ${voucherTypeLabel(_type)}';
    Widget waiting(Widget body) => AppPage(
      title: title,
      body: body,
    );
    if (loadError != null) {
      return waiting(Center(child: Text(friendlyErrorMessage(loadError), style: const TextStyle(color: AppTheme.error))));
    }
    if ((ledgersAsync.isLoading && ledgers.isEmpty) || (_isEdit && editing == null)) return waiting(const AppLoader());
    if (editing != null && !editing.canEdit) {
      return waiting(Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Text(
              editing.isLocked
                  ? 'The books for FY ${editing.fiscalYear} are closed — ${editing.voucherNumber} can\'t be changed.'
                  : '${editing.voucherNumber} can\'t be edited.',
              textAlign: TextAlign.center,
              style: const TextStyle(color: AppTheme.textSecondary)),
        ),
      ));
    }

    final needsCashBank = _type == 'receipt' || _type == 'payment' || _type == 'contra';
    return AppFormPage(
      title: title,
      subtitle: editing != null
          ? 'Correct the ${voucherTypeLabel(_type).toLowerCase()} and give the reason. The voucher keeps its number; the earlier version stays in its history.'
          : voucherTypeHint(_type),
      status: editing != null ? VoucherTypeChip(_type) : null,
      submitLabel: _isEdit ? 'Save changes' : 'Save ${voucherTypeLabel(_type)}',
      submitIcon: Icons.check_rounded,
      saving: _saving,
      onSubmit: () => _save(societyId),
      children: [
        if (editing == null)
          Align(
            alignment: Alignment.centerLeft,
            child: SegmentedButton<String>(
              showSelectedIcon: false,
              style: const ButtonStyle(
                visualDensity: VisualDensity.compact,
                padding: WidgetStatePropertyAll(EdgeInsets.symmetric(horizontal: 12)),
                textStyle: WidgetStatePropertyAll(TextStyle(fontSize: 13, fontWeight: FontWeight.w600)),
              ),
              segments: [
                for (final t in kManualVoucherTypes)
                  ButtonSegment(value: t, label: Text(voucherTypeLabel(t), maxLines: 1, softWrap: false)),
              ],
              selected: {_type},
              onSelectionChanged: (s) => _setType(s.first),
            ),
          ),
        FormSection(
          title: 'Details',
          description: 'The date, the account the money moves through, and a reference.',
          children: [
            FormFieldBox(
              label: 'Date',
              child: FormDateField(value: _date, hint: 'Select date', format: formatAccountsDate, onTap: _pickDate),
            ),
            FormFieldBox(
              label: 'Cheque / UTR no.',
              child: TextField(
                controller: _reference,
                decoration: const InputDecoration(hintText: 'Cheque, UTR or supplier\'s bill no.'),
              ),
            ),
            if (needsCashBank)
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
            if (_type == 'contra')
              _LedgerField(
                label: 'To (cash / bank)',
                value: _contraTo,
                onTap: () async {
                  final l = await pickLedger(context, cashBank, title: 'Cash or bank account');
                  if (l != null) setState(() => _contraTo = l);
                },
              ),
            if (_type == 'contra') _AmountField(controller: _contraAmount, onChanged: () => setState(() {})),
            if (_type == 'payment')
              FormFieldBox(
                label: 'Paid to',
                helper: 'Vendor, optional',
                child: VendorPicker(
                  societyId: societyId,
                  value: _vendorId,
                  label: '',
                  onChanged: (v) => setState(() => _vendorId = v?.id),
                ),
              ),
            if (!_isEdit)
              FormFieldBox(
                label: 'Voucher no.',
                helper: 'Given automatically when you save',
                child: NextVoucherNumber(societyId: societyId, type: _type, date: _date, showLabel: false),
              ),
          ],
        ),
        if (_type != 'contra')
          FormSection(
            title: switch (_type) {
              'receipt' => 'Received from / towards',
              'payment' => 'Paid to / for',
              _ => 'Debit and credit lines',
            },
            description: _type == 'journal' ? 'Debits and credits must match.' : 'One line for each ledger the money is booked to.',
            columns: 1,
            children: [
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
                  onPressed: () =>
                      setState(() => _lines.add(_Line(side: _type == 'journal' && _drTotal > _crTotal ? 'cr' : 'dr'))),
                  icon: const Icon(Icons.add_rounded, size: 18),
                  label: const Text('Add line'),
                ),
              ),
              _Totals(journal: _type == 'journal', total: _linesTotal, dr: _drTotal, cr: _crTotal),
            ],
          ),
        FormSection(
          title: 'Narration',
          description: _isEdit ? 'What the voucher is for, and why it is being changed.' : 'What the voucher is for.',
          columns: 1,
          children: [
            FormFieldBox(
              label: 'Narration',
              child: TextField(
                controller: _narration,
                minLines: 2,
                maxLines: 4,
                decoration: const InputDecoration(hintText: 'e.g. MSEDCL electricity bill for Aug-2026'),
              ),
            ),
            if (_isEdit)
              FormFieldBox(
                label: 'Reason for the change',
                required: true,
                child: TextField(controller: _reason, decoration: const InputDecoration(hintText: 'e.g. Wrong amount entered')),
              ),
          ],
        ),
      ],
    );
  }
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
        child: FormFieldBox(label: label, child: InputDecorator(
          decoration: InputDecoration(suffixIcon: const Icon(Icons.arrow_drop_down_rounded)),
          child: Text(value?.name ?? 'Choose ledger',
              overflow: TextOverflow.ellipsis,
              style: TextStyle(color: value == null ? AppTheme.textTertiary : AppTheme.textPrimary)),
        )),
      );
}

class _AmountField extends StatelessWidget {
  final TextEditingController controller;
  final VoidCallback onChanged;
  const _AmountField({required this.controller, required this.onChanged});

  @override
  Widget build(BuildContext context) => FormFieldBox(label: 'Amount (₹)', child: TextField(
        controller: controller,
        onChanged: (_) => onChanged(),
        keyboardType: const TextInputType.numberWithOptions(decimal: true),
        inputFormatters: [FilteringTextInputFormatter.allow(RegExp(r'^\d*\.?\d{0,2}'))],
        textAlign: TextAlign.right,
        decoration: const InputDecoration(hintText: '0.00'),
      ));
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
                child: FormFieldBox(label: 'Flat', child: InputDecorator(
                  decoration: const InputDecoration(suffixIcon: Icon(Icons.arrow_drop_down_rounded)),
                  child: Text(line.flat == null ? 'Choose flat' : '${line.flat!.flatLabel} · ${line.flat!.memberName}',
                      style: TextStyle(color: line.flat == null ? AppTheme.textTertiary : AppTheme.textPrimary)),
                )),
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
