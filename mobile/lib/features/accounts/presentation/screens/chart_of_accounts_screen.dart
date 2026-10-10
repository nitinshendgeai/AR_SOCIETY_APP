import 'package:flutter/material.dart';
import 'package:ar_society_app/core/motion/loading.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/layout/app_sheet.dart';
import 'package:ar_society_app/core/layout/app_shell.dart' show isDesktopLayout;
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/accounts/data/accounts_api.dart';
import 'package:ar_society_app/features/accounts/presentation/providers/accounts_providers.dart';
import 'package:ar_society_app/features/accounts/presentation/screens/accounts_screen.dart' show ledgerRoute;
import 'package:ar_society_app/features/accounts/presentation/widgets/accounts_widgets.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/features/maintenance_billing/presentation/providers/maintenance_billing_providers.dart';
import 'package:ar_society_app/features/maintenance_billing/presentation/widgets/billing_sheet_frame.dart';
import 'package:ar_society_app/shared/widgets/app_data_table.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';
import 'package:ar_society_app/shared/widgets/app_form.dart';

/// The society's chart of accounts — Balance Sheet heads (funds,
/// liabilities, assets) then Income & Expenditure heads — each ledger with
/// its current balance. Standard ledgers come ready; add your own bank
/// accounts, fixed deposits or expense heads, and set opening balances.
class ChartOfAccountsScreen extends ConsumerStatefulWidget {
  const ChartOfAccountsScreen({super.key});

  @override
  ConsumerState<ChartOfAccountsScreen> createState() => _ChartOfAccountsScreenState();
}

class _ChartOfAccountsScreenState extends ConsumerState<ChartOfAccountsScreen> {
  String _q = '';

  void _openSheet(String societyId, List<AccountGroupRow> groups, [LedgerAccount? existing]) => showAppSheet(
        context: context,
        builder: (_) => _LedgerSheet(societyId: societyId, groups: groups, existing: existing),
      );

  @override
  Widget build(BuildContext context) {
    final societyId = ref.watch(currentUserProvider)?.societyId;
    if (societyId == null) return const Scaffold(body: Center(child: Text('No society context')));
    final chartAsync = ref.watch(chartOfAccountsProvider(societyId));
    final desktop = isDesktopLayout(context);
    final groups = chartAsync.valueOrNull ?? const <AccountGroupRow>[];

    return Scaffold(
      backgroundColor: AppTheme.surface,
      appBar: AppBar(title: const Text('Chart of Accounts'), actions: [
        if (desktop)
          HeaderActionButton(
            icon: Icons.add_rounded,
            label: 'Add Ledger',
            onPressed: groups.isEmpty ? null : () => _openSheet(societyId, groups),
          ),
      ]),
      floatingActionButton: desktop || groups.isEmpty
          ? null
          : FloatingActionButton.extended(
              onPressed: () => _openSheet(societyId, groups),
              icon: const Icon(Icons.add_rounded),
              label: const Text('Add Ledger'),
            ),
      body: RefreshIndicator(
        onRefresh: () async => ref.invalidate(chartOfAccountsProvider(societyId)),
        child: chartAsync.when(
          loading: () => const AppLoader(),
          error: (e, _) => ListView(children: [
            Padding(
              padding: const EdgeInsets.all(24),
              child: Text(friendlyErrorMessage(e), style: const TextStyle(color: AppTheme.error)),
            ),
          ]),
          data: (groups) {
            final q = _q.toLowerCase();
            bool matches(LedgerAccount a) =>
                q.isEmpty || a.name.toLowerCase().contains(q) || (a.code ?? '').contains(q);
            return ResponsiveBody(
              maxWidth: 1000,
              child: ListView(
                padding: const EdgeInsets.fromLTRB(16, 16, 16, 96),
                children: [
                  TableSearchField(hint: 'Search ledgers', onChanged: (v) => setState(() => _q = v)),
                  const SizedBox(height: 8),
                  for (final nature in kNatureLabels.keys) ...[
                    if (groups.any((g) => g.nature == nature && g.accounts.any(matches))) ...[
                      Padding(
                        padding: const EdgeInsets.fromLTRB(2, 18, 2, 8),
                        child: Row(children: [
                          Text(kNatureLabels[nature]!,
                              style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w700)),
                          const SizedBox(width: 8),
                          Text(nature == 'income' || nature == 'expense' ? 'Income & Expenditure' : 'Balance Sheet',
                              style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
                        ]),
                      ),
                      for (final g in groups.where((g) => g.nature == nature))
                        if (g.accounts.any(matches))
                          _GroupCard(
                            group: g,
                            accounts: g.accounts.where(matches).toList(),
                            onOpen: (a) => context.push(ledgerRoute(a.id)),
                            onEdit: (a) => _openSheet(societyId, groups, a),
                          ),
                    ],
                  ],
                ],
              ),
            );
          },
        ),
      ),
    );
  }
}

class _GroupCard extends StatelessWidget {
  final AccountGroupRow group;
  final List<LedgerAccount> accounts;
  final ValueChanged<LedgerAccount> onOpen;
  final ValueChanged<LedgerAccount> onEdit;
  const _GroupCard({required this.group, required this.accounts, required this.onOpen, required this.onEdit});

  @override
  Widget build(BuildContext context) => Container(
        margin: const EdgeInsets.only(bottom: 10),
        decoration: BoxDecoration(color: AppTheme.cardBg, borderRadius: BorderRadius.circular(AppTheme.radiusM)),
        child: Column(children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(14, 12, 14, 10),
            child: Row(children: [
              Expanded(
                child: Text(group.name, style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w700)),
              ),
              DrCrText(group.total, weight: FontWeight.w700),
            ]),
          ),
          const Divider(height: 1),
          for (final a in accounts)
            InkWell(
              onTap: () => onOpen(a),
              child: Padding(
                padding: const EdgeInsets.fromLTRB(14, 8, 4, 8),
                child: Row(children: [
                  SizedBox(
                    width: 44,
                    child: Text(a.code ?? '',
                        style: const TextStyle(fontSize: 12, color: AppTheme.textTertiary,
                            fontFeatures: [FontFeature.tabularFigures()])),
                  ),
                  Expanded(
                    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                      Row(children: [
                        Flexible(
                          child: Text(a.name,
                              overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 13.5)),
                        ),
                        if (a.isDefaultBank) ...[
                          const SizedBox(width: 6),
                          const StatusPill('Default', AppTheme.primary),
                        ],
                        if (!a.isSystem) ...[
                          const SizedBox(width: 6),
                          const StatusPill('Custom', AppTheme.secondary),
                        ],
                      ]),
                      if (a.maintenanceElementName != null)
                        Text('Counts towards ${a.maintenanceElementName}',
                            overflow: TextOverflow.ellipsis,
                            style: const TextStyle(fontSize: 11.5, color: AppTheme.textSecondary)),
                    ]),
                  ),
                  if (a.balance != null) DrCrText(a.balance!, weight: FontWeight.w500),
                  IconButton(
                    tooltip: 'Edit ledger',
                    visualDensity: VisualDensity.compact,
                    icon: const Icon(Icons.edit_outlined, size: 18, color: AppTheme.textSecondary),
                    onPressed: () => onEdit(a),
                  ),
                ]),
              ),
            ),
        ]),
      );
}

/// Add or edit a ledger.
class _LedgerSheet extends ConsumerStatefulWidget {
  final String societyId;
  final List<AccountGroupRow> groups;
  final LedgerAccount? existing;
  const _LedgerSheet({required this.societyId, required this.groups, this.existing});

  @override
  ConsumerState<_LedgerSheet> createState() => _LedgerSheetState();
}

class _LedgerSheetState extends ConsumerState<_LedgerSheet> {
  final _form = GlobalKey<FormState>();
  late final _name = TextEditingController(text: widget.existing?.name);
  late final _code = TextEditingController(text: widget.existing?.code);
  late final _opening = TextEditingController(
      text: (widget.existing?.openingBalance ?? 0) == 0 ? '' : widget.existing!.openingBalance.toStringAsFixed(2));
  late final _bankName = TextEditingController(text: widget.existing?.bankName);
  late final _bankAcc = TextEditingController(text: widget.existing?.bankAccountNumber);
  late final _ifsc = TextEditingController(text: widget.existing?.bankIfsc);
  late final _branch = TextEditingController(text: widget.existing?.bankBranch);
  late String? _groupId = widget.existing?.groupId;
  late String _openingType = widget.existing?.openingType ?? 'dr';
  late String _kind = widget.existing == null
      ? 'ledger'
      : (widget.existing!.isBank ? 'bank' : (widget.existing!.isCash ? 'cash' : 'ledger'));
  late bool _defaultBank = widget.existing?.isDefaultBank ?? false;
  late bool _active = widget.existing?.isActive ?? true;
  late String? _elementId = widget.existing?.maintenanceElementId;
  bool _saving = false;

  bool get _editing => widget.existing != null;
  AccountGroupRow? get _group => widget.groups.where((g) => g.id == _groupId).firstOrNull;

  @override
  void dispose() {
    for (final c in [_name, _code, _opening, _bankName, _bankAcc, _ifsc, _branch]) {
      c.dispose();
    }
    super.dispose();
  }

  Future<void> _save() async {
    if (!_form.currentState!.validate()) return;
    setState(() => _saving = true);
    final api = ref.read(accountsApiProvider);
    final bank = _kind == 'bank';
    final fields = <String, dynamic>{
      'name': _name.text.trim(),
      'code': _code.text.trim().isEmpty ? null : _code.text.trim(),
      'opening_balance': (double.tryParse(_opening.text.trim()) ?? 0).toStringAsFixed(2),
      'opening_type': _openingType,
      // Only an expense ledger counts towards an element; null clears the link.
      if (_group?.nature == 'expense') 'maintenance_element_id': _elementId,
      if (bank) ...{
        'bank_name': _bankName.text.trim(),
        'bank_account_number': _bankAcc.text.trim(),
        'bank_ifsc': _ifsc.text.trim().toUpperCase(),
        'bank_branch': _branch.text.trim(),
      },
    };
    try {
      if (_editing) {
        await api.updateLedger(widget.existing!.id, {
          ...fields,
          if (!widget.existing!.isSystem) 'group_id': _groupId,
          if (bank && _defaultBank && !widget.existing!.isDefaultBank) 'is_default_bank': true,
          if (!widget.existing!.isSystem) 'is_active': _active,
        });
      } else {
        await api.createLedger({
          ...fields,
          'society_id': widget.societyId,
          'group_id': _groupId,
          'is_bank': bank,
          'is_cash': _kind == 'cash',
          'is_default_bank': bank && _defaultBank,
        });
      }
      invalidateBooks(ref);
      ref.invalidate(ledgersProvider);
      if (mounted) {
        AppToast.success(context, _editing ? 'Ledger updated' : 'Ledger added');
        Navigator.pop(context);
      }
    } catch (e) {
      if (mounted) showErrorToast(context, e);
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  /// What this expense ledger pays for — what is spent on it counts towards
  /// that maintenance element when the monthly maintenance is worked out.
  List<Widget> _elementPicker() => [
        const SizedBox(height: 14),
        ref.watch(maintenanceElementsProvider((societyId: widget.societyId, includeInactive: false))).when(
              loading: () => const LinearProgressIndicator(),
              error: (e, _) => Text(friendlyErrorMessage(e), style: const TextStyle(color: AppTheme.error)),
              data: (elements) => FormFieldBox(label: 'Counts towards maintenance element', child: DropdownButtonFormField<String?>(
                initialValue: elements.any((e) => e.id == _elementId) ? _elementId : null,
                isExpanded: true,
                decoration: const InputDecoration(
                  helperText: 'Spend on this ledger feeds that element\'s budget in the monthly maintenance',
                  helperMaxLines: 2,
                ),
                items: [
                  const DropdownMenuItem<String?>(value: null, child: Text('None — not recovered from members')),
                  for (final el in elements)
                    DropdownMenuItem<String?>(value: el.id, child: Text(el.name, overflow: TextOverflow.ellipsis)),
                ],
                onChanged: (v) => setState(() => _elementId = v),
              )),
            ),
      ];

  @override
  Widget build(BuildContext context) {
    final system = widget.existing?.isSystem ?? false;
    final isAsset = _group?.nature == 'asset';
    return BillingSheetFrame(
      title: _editing ? 'Edit Ledger' : 'Add Ledger',
      child: Form(
        key: _form,
        child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          FormFieldBox(label: 'Group', child: DropdownButtonFormField<String>(
            initialValue: _groupId,
            isExpanded: true,
            decoration: const InputDecoration(),
            items: [
              for (final g in widget.groups)
                DropdownMenuItem(value: g.id, child: Text(g.name, overflow: TextOverflow.ellipsis)),
            ],
            onChanged: system
                ? null
                : (v) => setState(() {
                      _groupId = v;
                      final nature = _group?.nature;
                      _openingType = nature == 'asset' || nature == 'expense' ? 'dr' : 'cr';
                      if (nature != 'asset') _kind = 'ledger';
                    }),
            validator: (v) => v == null ? 'Choose the group this ledger belongs to' : null,
          )),
          if (system)
            const Padding(
              padding: EdgeInsets.only(top: 6),
              child: Text('A standard ledger — the automatic postings use it, so it stays in its group.',
                  style: TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
            ),
          const SizedBox(height: 12),
          Row(children: [
            Expanded(
              flex: 3,
              child: FormFieldBox(label: 'Ledger name', child: TextFormField(
                controller: _name,
                decoration: const InputDecoration(),
                validator: (v) => (v ?? '').trim().isEmpty ? 'Enter a name' : null,
              )),
            ),
            const SizedBox(width: 10),
            Expanded(
              child: FormFieldBox(label: 'Code', child: TextFormField(controller: _code, decoration: const InputDecoration(hintText: 'Auto'))),
            ),
          ]),
          if (_group?.nature == 'expense') ..._elementPicker(),
          if (isAsset && !_editing) ...[
            const SizedBox(height: 14),
            SegmentedButton<String>(
              segments: const [
                ButtonSegment(value: 'ledger', label: Text('Ledger')),
                ButtonSegment(value: 'bank', label: Text('Bank A/c'), icon: Icon(Icons.account_balance_outlined)),
                ButtonSegment(value: 'cash', label: Text('Cash'), icon: Icon(Icons.payments_outlined)),
              ],
              selected: {_kind},
              onSelectionChanged: (s) => setState(() => _kind = s.first),
            ),
          ],
          if (_kind == 'bank') ...[
            const SizedBox(height: 12),
            FormFieldBox(label: 'Bank name', child: TextFormField(controller: _bankName, decoration: const InputDecoration())),
            const SizedBox(height: 10),
            Row(children: [
              Expanded(
                child: FormFieldBox(label: 'Account number', child: TextFormField(
                    controller: _bankAcc, decoration: const InputDecoration())),
              ),
              const SizedBox(width: 10),
              Expanded(child: FormFieldBox(label: 'IFSC', child: TextFormField(controller: _ifsc, decoration: const InputDecoration()))),
            ]),
            const SizedBox(height: 10),
            FormFieldBox(label: 'Branch', child: TextFormField(controller: _branch, decoration: const InputDecoration())),
            SwitchListTile(
              contentPadding: EdgeInsets.zero,
              value: _defaultBank,
              onChanged: (widget.existing?.isDefaultBank ?? false) ? null : (v) => setState(() => _defaultBank = v),
              title: const Text('Default bank', style: TextStyle(fontSize: 14)),
              subtitle: const Text('Payments received and vendor payments not in cash are posted here',
                  style: TextStyle(fontSize: 12)),
            ),
          ],
          const SizedBox(height: 12),
          Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Expanded(
              child: FormFieldBox(label: 'Opening balance (₹)', child: TextFormField(
                controller: _opening,
                keyboardType: const TextInputType.numberWithOptions(decimal: true),
                inputFormatters: [FilteringTextInputFormatter.allow(RegExp(r'[0-9.]'))],
                decoration: const InputDecoration(hintText: '0.00'),
                validator: (v) =>
                    (v ?? '').trim().isNotEmpty && double.tryParse(v!.trim()) == null ? 'Enter an amount' : null,
              )),
            ),
            const SizedBox(width: 10),
            Padding(
              padding: const EdgeInsets.only(top: 4),
              child: SegmentedButton<String>(
                segments: const [
                  ButtonSegment(value: 'dr', label: Text('Dr')),
                  ButtonSegment(value: 'cr', label: Text('Cr')),
                ],
                selected: {_openingType},
                onSelectionChanged: (s) => setState(() => _openingType = s.first),
              ),
            ),
          ]),
          const Padding(
            padding: EdgeInsets.only(top: 6),
            child: Text('The balance brought forward when you start keeping books here.',
                style: TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
          ),
          if (_editing && !system)
            SwitchListTile(
              contentPadding: EdgeInsets.zero,
              value: _active,
              onChanged: (v) => setState(() => _active = v),
              title: const Text('Active', style: TextStyle(fontSize: 14)),
              subtitle: const Text('Inactive ledgers keep their history but can\'t be used in new vouchers',
                  style: TextStyle(fontSize: 12)),
            ),
          const SizedBox(height: 18),
          AppPrimaryButton(label: _editing ? 'Save' : 'Add Ledger', isLoading: _saving, onPressed: _save),
        ]),
      ),
    );
  }
}
