import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/layout/app_sheet.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/accounts/data/accounts_api.dart';
import 'package:ar_society_app/features/accounts/presentation/providers/accounts_providers.dart';
import 'package:ar_society_app/shared/widgets/app_form.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';

/// Makes a ledger without leaving the voucher being entered (Tally's Alt+C): the name typed is kept, and only the
/// group it belongs to is asked. [preferNature] ('income' for a receipt, 'expense' for a payment) puts the likely
/// groups first and picks the first of them. Returns the new ledger, or null if cancelled.
Future<LedgerAccount?> showQuickLedger(
  BuildContext context, {
  required String societyId,
  required String name,
  String? preferNature,
}) =>
    showAppSheet<LedgerAccount>(
      context: context,
      builder: (_) => QuickLedgerSheet(societyId: societyId, name: name, preferNature: preferNature),
    );

class QuickLedgerSheet extends ConsumerStatefulWidget {
  final String societyId;
  final String name;
  final String? preferNature;
  const QuickLedgerSheet({super.key, required this.societyId, required this.name, this.preferNature});

  @override
  ConsumerState<QuickLedgerSheet> createState() => _QuickLedgerSheetState();
}

class _QuickLedgerSheetState extends ConsumerState<QuickLedgerSheet> {
  late final _name = TextEditingController(text: widget.name);
  String? _groupId;
  List<AccountGroupRow>? _groups;
  Object? _error;
  bool _saving = false;

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _name.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    try {
      final all = await ref.read(accountsApiProvider).chart(widget.societyId);
      // A ledger made here is an ordinary one: cash and bank accounts have their own screen (details, IFSC, default).
      final groups = all.where((g) => g.systemKey != 'cash_bank').toList();
      final nature = widget.preferNature;
      if (nature != null) {
        groups.sort((a, b) => (a.nature == nature ? 0 : 1).compareTo(b.nature == nature ? 0 : 1));
      }
      if (mounted) {
        setState(() {
          _groups = groups;
          _groupId = groups.where((g) => nature != null && g.nature == nature).firstOrNull?.id;
        });
      }
    } catch (e) {
      if (mounted) setState(() => _error = e);
    }
  }

  Future<void> _save() async {
    final name = _name.text.trim();
    if (name.isEmpty || _groupId == null) {
      AppToast.warning(context, name.isEmpty ? 'Enter the ledger name' : 'Choose the group it belongs to');
      return;
    }
    setState(() => _saving = true);
    try {
      final made = await ref.read(accountsApiProvider).createLedger({
        'society_id': widget.societyId,
        'group_id': _groupId,
        'name': name,
        'opening_balance': '0.00',
        'opening_type': 'dr',
        'is_bank': false,
        'is_cash': false,
        'is_default_bank': false,
      });
      ref.invalidate(ledgersProvider);
      if (mounted) Navigator.pop(context, made);
    } catch (e) {
      if (mounted) showErrorToast(context, e);
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final groups = _groups;
    return AppSheetFrame(
      title: 'New ledger',
      subtitle: 'Made now, and used on this voucher',
      child: _error != null
          ? Text(friendlyErrorMessage(_error!), style: const TextStyle(color: AppTheme.error))
          : groups == null
              ? const Padding(padding: EdgeInsets.all(24), child: Center(child: CircularProgressIndicator()))
              : Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
                  FormFieldBox(
                    label: 'Ledger name',
                    required: true,
                    child: TextField(
                      key: const Key('quick-ledger-name'),
                      controller: _name,
                      textInputAction: TextInputAction.next,
                    ),
                  ),
                  const SizedBox(height: 14),
                  FormFieldBox(
                    label: 'Group',
                    required: true,
                    child: DropdownButtonFormField<String>(
                      key: const Key('quick-ledger-group'),
                      initialValue: _groupId,
                      isExpanded: true,
                      autofocus: true,
                      decoration: const InputDecoration(),
                      hint: const Text('Choose the group'),
                      items: [for (final g in groups) DropdownMenuItem(value: g.id, child: Text(g.name, overflow: TextOverflow.ellipsis))],
                      onChanged: (v) => setState(() => _groupId = v),
                    ),
                  ),
                  const SizedBox(height: 20),
                  AppPrimaryButton(
                    key: const Key('quick-ledger-save'),
                    label: 'Create ledger',
                    isLoading: _saving,
                    onPressed: _saving ? null : _save,
                  ),
                ]),
    );
  }
}
