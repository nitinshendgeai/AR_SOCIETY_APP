import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/core/theme/design_tokens.dart';
import 'package:ar_society_app/features/accounts/data/accounts_api.dart' show LedgerAccount, formatInr;
import 'package:ar_society_app/features/accounts/presentation/providers/accounts_providers.dart';
import 'package:ar_society_app/features/accounts_agent/data/accounts_agent_api.dart' show ProposalLine;
import 'package:ar_society_app/features/accounts_agent/data/assist_api.dart';
import 'package:ar_society_app/features/accounts_agent/presentation/providers/legal_providers.dart';
import 'package:ar_society_app/features/accounts_agent/presentation/widgets/agent_widgets.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/features/vendor/data/vendors_work_api.dart' show VendorRecord;
import 'package:ar_society_app/features/vendor/presentation/providers/vendors_work_providers.dart';
import 'package:ar_society_app/shared/widgets/app_form.dart';
import 'package:ar_society_app/shared/widgets/app_status.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';

final _vendorsProvider = FutureProvider.autoDispose.family<List<VendorRecord>, String>(
  (ref, societyId) => ref.watch(vendorsWorkApiProvider).vendors(societyId),
);

/// Draft a payment or receipt with the Accounts Agent. The agent fills in the ledger (your choice, else where this
/// vendor's payments usually go, else read from your description) and shows the voucher first. "Save for approval"
/// creates it as PENDING: it counts in the books only after another admin or committee member approves it.
class AgentEntryDraftScreen extends ConsumerStatefulWidget {
  const AgentEntryDraftScreen({super.key});
  @override
  ConsumerState<AgentEntryDraftScreen> createState() => _AgentEntryDraftScreenState();
}

class _AgentEntryDraftScreenState extends ConsumerState<AgentEntryDraftScreen> {
  final _text = TextEditingController();
  final _amount = TextEditingController();
  final _reference = TextEditingController();
  String _type = 'payment';
  String _money = 'bank';
  String? _vendorId;
  String? _ledgerId;
  DateTime? _date;
  EntryDraftResult? _result;
  bool _busy = false;

  @override
  void dispose() {
    _text.dispose();
    _amount.dispose();
    _reference.dispose();
    super.dispose();
  }

  Future<void> _run({required bool save}) async {
    Map<String, dynamic> payload;
    try {
      payload = entryDraftPayload(
        text: _text.text, voucherType: _type, amount: _amount.text, date: _date, vendorId: _vendorId,
        ledgerId: _ledgerId, moneyAccount: _money, reference: _reference.text, save: save,
      );
    } on FormatException catch (e) {
      showErrorToast(context, Exception(e.message));
      return;
    }
    setState(() => _busy = true);
    try {
      final r = await ref.read(assistApiProvider).draftEntry(payload);
      if (!mounted) return;
      setState(() => _result = r);
      if (r.saved) AppToast.success(context, '${r.voucherNumber} saved — waiting for approval');
    } catch (e) {
      if (mounted) showErrorToast(context, e);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final sid = ref.watch(currentUserProvider)?.societyId;
    final ledgers = sid == null ? const AsyncValue<List<LedgerAccount>>.data([]) : ref.watch(ledgersProvider(sid));
    final vendors = sid == null ? const AsyncValue<List<VendorRecord>>.data([]) : ref.watch(_vendorsProvider(sid));
    final nature = _type == 'payment' ? 'expense' : 'income';
    final r = _result;
    return AppPage(
      title: 'Draft an entry',
      subtitle: 'The agent prepares the voucher; another committee member approves it',
      maxWidth: 820,
      body: ListView(padding: const EdgeInsets.fromLTRB(16, 12, 16, 96), children: [
        AgentCard(
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            TextField(
              controller: _text,
              maxLines: 2,
              decoration: const InputDecoration(
                labelText: 'Describe the entry (optional)',
                hintText: 'e.g. Paid ₹12,000 to CleanPro for November housekeeping, bill CP-NOV-26',
              ),
            ),
            const SizedBox(height: 12),
            SegmentedButton<String>(
              segments: const [
                ButtonSegment(value: 'payment', label: Text('Payment')),
                ButtonSegment(value: 'receipt', label: Text('Receipt')),
              ],
              selected: {_type},
              onSelectionChanged: (s) => setState(() {
                _type = s.first;
                _ledgerId = null;
                if (_type == 'receipt') _vendorId = null;
              }),
            ),
            const SizedBox(height: 12),
            Wrap(spacing: 12, runSpacing: 12, children: [
              SizedBox(width: 220, child: TextField(controller: _amount, keyboardType: const TextInputType.numberWithOptions(decimal: true), decoration: const InputDecoration(labelText: 'Amount (₹)'))),
              SizedBox(width: 220, child: TextField(controller: _reference, decoration: const InputDecoration(labelText: 'Bill / cheque / UPI reference'))),
              OutlinedButton.icon(
                onPressed: () async {
                  final now = DateTime.now();
                  final d = await showDatePicker(context: context, initialDate: _date ?? now, firstDate: DateTime(now.year - 2), lastDate: now);
                  if (d != null) setState(() => _date = d);
                },
                icon: const Icon(Icons.event_outlined, size: 18),
                label: Text(_date == null ? 'Date: today' : 'Date: ${day(_date!)}'),
              ),
              SegmentedButton<String>(
                segments: const [ButtonSegment(value: 'bank', label: Text('Bank')), ButtonSegment(value: 'cash', label: Text('Cash'))],
                selected: {_money},
                onSelectionChanged: (s) => setState(() => _money = s.first),
              ),
            ]),
            const SizedBox(height: 12),
            if (_type == 'payment')
              vendors.when(
                loading: () => const LinearProgressIndicator(),
                error: (_, __) => const SizedBox.shrink(),
                data: (vs) => DropdownButtonFormField<String?>(
                  initialValue: _vendorId,
                  isExpanded: true,
                  decoration: const InputDecoration(labelText: 'Vendor (optional)'),
                  items: [
                    const DropdownMenuItem<String?>(value: null, child: Text('No vendor')),
                    for (final v in vs) DropdownMenuItem<String?>(value: v.id, child: Text(v.companyName, overflow: TextOverflow.ellipsis)),
                  ],
                  onChanged: (v) => setState(() => _vendorId = v),
                ),
              ),
            const SizedBox(height: 12),
            ledgers.when(
              loading: () => const LinearProgressIndicator(),
              error: (_, __) => const SizedBox.shrink(),
              data: (ls) {
                final pick = ls.where((l) => l.isActive && !l.isCash && !l.isBank && l.nature == nature).toList();
                return DropdownButtonFormField<String?>(
                  initialValue: _ledgerId,
                  isExpanded: true,
                  decoration: InputDecoration(labelText: _type == 'payment' ? 'Expense ledger (optional — the agent can choose)' : 'Income ledger (optional)'),
                  items: [
                    const DropdownMenuItem<String?>(value: null, child: Text('Let the agent choose')),
                    for (final l in pick) DropdownMenuItem<String?>(value: l.id, child: Text(l.name, overflow: TextOverflow.ellipsis)),
                  ],
                  onChanged: (v) => setState(() => _ledgerId = v),
                );
              },
            ),
            const SizedBox(height: 16),
            Wrap(spacing: 10, runSpacing: 10, children: [
              OutlinedButton.icon(onPressed: _busy ? null : () => _run(save: false), icon: const Icon(Icons.preview_outlined), label: const Text('Preview')),
              FilledButton.icon(
                onPressed: _busy || r == null || r.saved ? null : () => _run(save: true),
                icon: const Icon(Icons.send_outlined),
                label: const Text('Save for approval'),
              ),
            ]),
            if (r == null)
              const Padding(
                padding: EdgeInsets.only(top: 8),
                child: Text('Preview first: nothing is saved until you choose "Save for approval".', style: TextStyle(fontSize: 12.5, color: AppTheme.textSecondary)),
              ),
          ]),
        ),
        if (r != null) ...[
          AgentSectionTitle(r.saved ? 'Saved — waiting for approval' : 'Proposed voucher'),
          AgentCard(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Wrap(spacing: 8, runSpacing: 6, children: [
                AppStatusChip(label: titleCase(r.voucherType), tone: AppTone.info),
                if (r.saved) AppStatusChip(label: '${r.voucherNumber} · pending approval', tone: AppTone.warning),
              ]),
              const SizedBox(height: 8),
              KeyValue('Date', r.voucherDate),
              KeyValue('Amount', formatInr(r.amount)),
              if ((r.narration ?? '').isNotEmpty) KeyValue('Narration', r.narration),
              if ((r.reference ?? '').isNotEmpty) KeyValue('Reference', r.reference),
              const Divider(height: 20),
              LinesTable(lines: [for (final l in r.lines) ProposalLine(l.account, l.debit, l.credit)]),
              for (final b in r.basis) Padding(padding: const EdgeInsets.only(top: 6), child: Text(b, style: const TextStyle(fontSize: 12.5, color: AppTheme.textSecondary))),
              if (r.unclear.isNotEmpty)
                Padding(
                  padding: const EdgeInsets.only(top: 6),
                  child: Text('Not clear from your description: ${r.unclear.join(', ')}', style: const TextStyle(fontSize: 12.5, color: AppTheme.warning)),
                ),
            ]),
          ),
        ],
      ]),
    );
  }
}
