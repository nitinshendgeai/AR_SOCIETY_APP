import 'package:flutter/material.dart';
import 'package:ar_society_app/core/layout/app_shell.dart' show isDesktopLayout;
import 'package:ar_society_app/core/motion/loading.dart';
import 'package:ar_society_app/features/vendor/presentation/widgets/vendor_picker.dart';
import 'package:ar_society_app/features/vendor/presentation/providers/vendors_work_providers.dart' show vendorOpenBillsProvider;
import 'package:ar_society_app/features/vendor/presentation/screens/pay_vendor_bills_screen.dart' show openPayVendor;
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/router/app_router.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/accounts/data/accounts_api.dart';
import 'package:ar_society_app/features/accounts/presentation/providers/accounts_providers.dart';
import 'package:ar_society_app/features/accounts/presentation/widgets/accounts_widgets.dart';
import 'package:ar_society_app/features/accounts/presentation/widgets/quick_ledger_sheet.dart';
import 'package:ar_society_app/features/accounts/presentation/widgets/voucher_hotkeys.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/shared/widgets/app_form.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';

class _Line {
  LedgerAccount? account;
  MemberBalance? flat;
  String side; // dr | cr (journal only)
  final amount = TextEditingController();
  final ledgerFocus = FocusNode();
  // Kept as they were when an existing voucher is edited.
  String? vendorId;
  String? narration;
  _Line({this.side = 'dr'});

  double get value => double.tryParse(amount.text.trim()) ?? 0;

  void dispose() {
    amount.dispose();
    ledgerFocus.dispose();
  }
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
          l.dispose();
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
      l.dispose();
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
          l.dispose();
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

  Future<void> _save(String societyId, {bool another = false}) async {
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
        AppToast.success(
            context,
            '${_isEdit ? '${v.voucherNumber} updated' : '${v.voucherNumber} saved'}'
            '${v.isPending ? ' — it counts in the books once the admin or committee approves it' : ''}');
        if (another && !_isEdit) {
          _startNext();
        } else {
          // Opened from a link rather than from within the app: land on the day book.
          context.canPop() ? context.pop() : context.go(AppRoutes.accountsDayBook);
        }
      }
    } catch (e) {
      if (mounted) showErrorToast(context, e);
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  /// After "Save and add another": a clean voucher of the same kind, same day, same cash or bank account.
  void _startNext() {
    setState(() {
      for (final l in _lines) {
        l.dispose();
      }
      _lines = _type == 'journal' ? [_Line(side: 'dr'), _Line(side: 'cr')] : [_Line()];
      _reference.clear();
      _narration.clear();
      _vendorId = null;
      _contraAmount.clear();
      _contraTo = null;
    });
    _focusFirstLine();
  }

  void _focusFirstLine() => WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted && _lines.isNotEmpty) _lines.first.ledgerFocus.requestFocus();
      });

  void _addLine() {
    if (_type == 'contra') return;
    final line = _Line(side: _type == 'journal' && _drTotal > _crTotal ? 'cr' : 'dr');
    setState(() => _lines.add(line));
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) line.ledgerFocus.requestFocus();
    });
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
    final desktop = isDesktopLayout(context);
    return CallbackShortcuts(
      bindings: {
        if (!_isEdit && _type != 'contra') const SingleActivator(LogicalKeyboardKey.keyL, alt: true): _addLine,
        // F4 Contra, F5 Payment, F6 Receipt, F7 Journal: switch what is being entered (a voucher being corrected keeps its type).
        if (!_isEdit)
          ...voucherHotkeyBindings((t) {
            if (t != _type) _setType(t);
          }),
      },
      child: _page(societyId, title, editing, needsCashBank, cashBank, others, desktop),
    );
  }

  Widget _page(String societyId, String title, Voucher? editing, bool needsCashBank, List<LedgerAccount> cashBank,
      List<LedgerAccount> others, bool desktop) {
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
      onSubmitAndNew: _isEdit ? null : () => _save(societyId, another: true),
      extraActions: [
        if (!_isEdit)
          OutlinedButton(
            onPressed: _saving ? null : () => _save(societyId, another: true),
            style: OutlinedButton.styleFrom(minimumSize: const Size(150, 44)),
            child: const Text('Save and add another'),
          ),
      ],
      footerNote: desktop
          ? Text(_isEdit
              ? 'Enter moves to the next field · Ctrl+S saves'
              : 'Enter: next field · Ctrl+S: save · Ctrl+Enter: save and add another · Alt+L: add a line · '
                  'Alt+C: create a ledger · F4 Contra · F5 Payment · F6 Receipt · F7 Journal')
          : null,
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
                textInputAction: TextInputAction.next,
                decoration: const InputDecoration(hintText: 'Cheque, UTR or supplier\'s bill no.'),
              ),
            ),
            if (needsCashBank)
              LedgerChooser(
                label: switch (_type) {
                  'receipt' => 'Received into',
                  'payment' => 'Paid from',
                  _ => 'From (cash / bank)',
                },
                value: _cashBank,
                options: cashBank,
                sheetTitle: 'Cash or bank account',
                onChanged: (l) => setState(() => _cashBank = l),
              ),
            if (_type == 'contra')
              LedgerChooser(
                label: 'To (cash / bank)',
                value: _contraTo,
                options: cashBank,
                sheetTitle: 'Cash or bank account',
                autofocus: !_isEdit,
                onChanged: (l) => setState(() => _contraTo = l),
              ),
            if (_type == 'contra') _AmountField(controller: _contraAmount, onChanged: () => setState(() {})),
            if (_type == 'payment')
              FormFieldBox(
                label: 'Paid to',
                helper: 'Vendor, optional',
                child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
                  VendorPicker(
                    societyId: societyId,
                    value: _vendorId,
                    label: '',
                    onChanged: (v) => setState(() => _vendorId = v?.id),
                  ),
                  if (_vendorId != null) _UnpaidBillsNote(vendorId: _vendorId!),
                ]),
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
                  preferNature: switch (_type) { 'receipt' => 'income', 'payment' => 'expense', _ => null },
                  autofocus: i == 0 && !_isEdit,
                  onChanged: () => setState(() {}),
                  // Enter on the last amount of an unbalanced journal opens the next line.
                  onAmountEnter: () {
                    if (_type == 'journal' && i == _lines.length - 1 && (_drTotal - _crTotal).abs() > 0.001) _addLine();
                  },
                  onRemove: _lines.length > (_type == 'journal' ? 2 : 1)
                      ? () => setState(() {
                            _lines.removeAt(i);
                            l.dispose();
                          })
                      : null,
                ),
              Align(
                alignment: Alignment.centerLeft,
                // Out of the Enter-key path (the keyboard adds a line with Alt+L); the mouse still clicks it.
                child: ExcludeFocus(
                  child: TextButton.icon(
                    onPressed: _addLine,
                    icon: const Icon(Icons.add_rounded, size: 18),
                    label: const Text('Add line'),
                  ),
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


class _AmountField extends StatelessWidget {
  final TextEditingController controller;
  final VoidCallback onChanged;
  final VoidCallback? onEnter;
  const _AmountField({required this.controller, required this.onChanged, this.onEnter});

  @override
  Widget build(BuildContext context) => FormFieldBox(label: 'Amount (₹)', child: TextField(
        controller: controller,
        onChanged: (_) => onChanged(),
        onSubmitted: (_) => onEnter?.call(),
        textInputAction: TextInputAction.next,
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
  final String? preferNature;
  final bool autofocus;
  final VoidCallback onChanged;
  final VoidCallback? onAmountEnter;
  final VoidCallback? onRemove;
  const _LineCard({
    super.key,
    required this.line,
    required this.journal,
    required this.ledgers,
    required this.societyId,
    this.preferNature,
    this.autofocus = false,
    required this.onChanged,
    this.onAmountEnter,
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
              final ledgerField = LedgerChooser(
                label: 'Ledger',
                value: line.account,
                options: ledgers,
                focusNode: line.ledgerFocus,
                autofocus: autofocus,
                // A ledger that does not exist yet can be made here (Alt+C), without leaving the voucher.
                onCreate: (name) => showQuickLedger(context, societyId: societyId, name: name, preferNature: preferNature),
                onChanged: (l) {
                  line.account = l;
                  if (!l.isMembersDues) line.flat = null;
                  onChanged();
                },
              );
              final amount = _AmountField(controller: line.amount, onChanged: onChanged, onEnter: onAmountEnter);
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
              FlatChooser(
                value: line.flat,
                options: ref.watch(membersLedgerProvider(societyId)).valueOrNull?.members ?? const [],
                onChanged: (f) {
                  line.flat = f;
                  onChanged();
                },
              ),
              // preferNature is 'income' only on a Receipt: a resident's payment belongs in Online Payments.
              if (preferNature == 'income') const _ResidentPaymentNote(),
            ],
          ]),
        ),
        ExcludeFocus(
          child: IconButton(
            tooltip: 'Remove line',
            onPressed: onRemove,
            icon: const Icon(Icons.close_rounded, size: 18),
          ),
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

/// Under the vendor on a Payment voucher: when the vendor has bills still to be paid, say so and offer the screen that
/// pays them — a loose voucher would leave the bills unpaid and the books out of step with what is owed.
class _UnpaidBillsNote extends ConsumerWidget {
  final String vendorId;
  const _UnpaidBillsNote({required this.vendorId});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final open = ref.watch(vendorOpenBillsProvider(vendorId)).valueOrNull;
    if (open == null || open.bills.isEmpty) return const SizedBox.shrink();
    return Padding(
      padding: const EdgeInsets.only(top: 8),
      child: DecoratedBox(
        decoration: BoxDecoration(color: AppTheme.warningSoft, borderRadius: BorderRadius.circular(AppTheme.radiusS)),
        child: Padding(
          padding: const EdgeInsets.fromLTRB(12, 8, 8, 8),
          child: Row(children: [
            const Icon(Icons.info_outline_rounded, size: 18, color: AppTheme.warning),
            const SizedBox(width: 8),
            Expanded(
              child: Text(
                '${open.vendorName} has ${open.bills.length} unpaid ${open.bills.length == 1 ? 'bill' : 'bills'} '
                '(${formatInr(open.total)}). Pay them from Pay Vendor so each bill is marked paid.',
                style: const TextStyle(fontSize: 12.5, height: 1.4),
              ),
            ),
            TextButton(onPressed: () => openPayVendor(context, vendorId: vendorId), child: const Text('Pay bills')),
          ]),
        ),
      ),
    );
  }
}

/// On a Receipt line for Members' Dues: a resident's payment is recorded in Online Payments, which settles the flat's bills
/// and issues the receipt. The server refuses a Receipt voucher here for a flat with unpaid bills.
class _ResidentPaymentNote extends StatelessWidget {
  const _ResidentPaymentNote();

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(top: 8),
      child: DecoratedBox(
        decoration: BoxDecoration(color: AppTheme.warningSoft, borderRadius: BorderRadius.circular(AppTheme.radiusS)),
        child: Padding(
          padding: const EdgeInsets.fromLTRB(12, 8, 8, 8),
          child: Row(children: [
            const Icon(Icons.info_outline_rounded, size: 18, color: AppTheme.warning),
            const SizedBox(width: 8),
            const Expanded(
              child: Text(
                'A resident\'s payment is recorded in Online Payments, which marks the bills paid and issues the receipt. '
                'Use a voucher here only for an advance from a flat with nothing unpaid.',
                style: TextStyle(fontSize: 12.5, height: 1.4),
              ),
            ),
            TextButton(onPressed: () => context.push(AppRoutes.onlinePayments), child: const Text('Open')),
          ]),
        ),
      ),
    );
  }
}
