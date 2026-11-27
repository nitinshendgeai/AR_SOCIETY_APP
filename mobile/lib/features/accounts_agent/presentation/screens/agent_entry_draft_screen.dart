import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:ar_society_app/core/router/app_router.dart';
import 'package:ar_society_app/core/theme/design_tokens.dart';
import 'package:ar_society_app/features/accounts/data/accounts_api.dart' show LedgerAccount, formatInr;
import 'package:ar_society_app/features/accounts/presentation/providers/accounts_providers.dart';
import 'package:ar_society_app/features/accounts_agent/presentation/widgets/agent_hud.dart';
import 'package:ar_society_app/features/accounts_agent/data/accounts_agent_api.dart' show ProposalLine;
import 'package:ar_society_app/features/accounts_agent/data/assist_api.dart';
import 'package:ar_society_app/features/accounts_agent/presentation/providers/legal_providers.dart';
import 'package:ar_society_app/features/accounts_agent/presentation/widgets/agent_widgets.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/features/vendor/data/vendors_work_api.dart' show VendorRecord;
import 'package:ar_society_app/features/vendor/presentation/providers/vendors_work_providers.dart';
import 'package:ar_society_app/shared/widgets/app_form.dart';
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
  bool _notAgainstBill = false;
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
        ledgerId: _ledgerId, moneyAccount: _money, reference: _reference.text, notAgainstBill: _notAgainstBill, save: save,
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
                onPressed: _busy || r == null || r.saved || r.redirect != null ? null : () => _run(save: true),
                icon: const Icon(Icons.send_outlined),
                label: const Text('Save for approval'),
              ),
            ]),
            if (r == null)
              const Padding(
                padding: EdgeInsets.only(top: 8),
                child: Text('Preview first: nothing is saved until you choose "Save for approval".', style: TextStyle(fontSize: 12.5, color: Hud.dim)),
              ),
          ]),
        ),
        if (r?.redirect != null) ...[
          const AgentSectionTitle('Record this elsewhere'),
          _RedirectCard(
            redirect: r!.redirect!,
            text: _text.text,
            onNotAgainstBill: () {
              setState(() => _notAgainstBill = true);
              _run(save: false);
            },
          ),
        ] else if (r != null) ...[
          AgentSectionTitle(r.saved ? 'Saved — waiting for approval' : 'Proposed voucher'),
          AgentCard(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Wrap(spacing: 8, runSpacing: 6, children: [
                HudChip(label: titleCase(r.voucherType), tone: AppTone.info),
                if (r.saved) HudChip(label: '${r.voucherNumber} · pending approval', tone: AppTone.warning),
              ]),
              const SizedBox(height: 8),
              KeyValue('Date', r.voucherDate),
              KeyValue('Amount', formatInr(r.amount)),
              if ((r.narration ?? '').isNotEmpty) KeyValue('Narration', r.narration),
              if ((r.reference ?? '').isNotEmpty) KeyValue('Reference', r.reference),
              const Divider(height: 20),
              LinesTable(lines: [for (final l in r.lines) ProposalLine(l.account, l.debit, l.credit)]),
              for (final b in r.basis) Padding(padding: const EdgeInsets.only(top: 6), child: Text(b, style: const TextStyle(fontSize: 12.5, color: Hud.dim))),
              if (r.unclear.isNotEmpty)
                Padding(
                  padding: const EdgeInsets.only(top: 6),
                  child: Text('Not clear from your description: ${r.unclear.join(', ')}', style: const TextStyle(fontSize: 12.5, color: Hud.amber)),
                ),
            ]),
          ),
        ],
      ]),
    );
  }
}


/// Why the agent does not draft this entry here, the proper entry, and a button to the screen that records it.
class _RedirectCard extends ConsumerStatefulWidget {
  final EntryRedirect redirect;
  final String text;
  final VoidCallback onNotAgainstBill;
  const _RedirectCard({required this.redirect, required this.text, required this.onNotAgainstBill});
  @override
  ConsumerState<_RedirectCard> createState() => _RedirectCardState();
}

const _modes = <String, String>{
  'cash': 'Cash', 'cheque': 'Cheque', 'upi': 'UPI', 'bank_transfer': 'Bank transfer', 'neft': 'NEFT', 'rtgs': 'RTGS',
};

class _RedirectCardState extends ConsumerState<_RedirectCard> {
  bool _busy = false;
  EntryRecorded? _done;

  /// Shows exactly what will be recorded; the agent records it only when the person confirms.
  Future<void> _recordForMe() async {
    final redirect = widget.redirect;
    final member = redirect.kind == 'member_receipt';
    var mode = redirect.paymentMode;
    final refCtl = TextEditingController(text: redirect.reference ?? '');
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setD) => AlertDialog(
          title: Text(member ? 'Record the member\'s payment?' : 'Pay the vendor\'s bills?'),
          content: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(member
                ? 'The agent issues the receipt${redirect.flat == null ? '' : ' for ${redirect.flat}'}, credits the member\'s dues and sets it off against the oldest unpaid bills.'
                : 'The agent pays the vendor\'s oldest unpaid bills first, each with the TDS booked on it.'),
            const SizedBox(height: 10),
            KeyValue('Amount', formatInr(double.tryParse(redirect.amount) ?? 0)),
            KeyValue('Entry', redirect.accounting),
            const SizedBox(height: 8),
            DropdownButtonFormField<String>(
              initialValue: _modes.containsKey(mode) ? mode : 'bank_transfer',
              decoration: const InputDecoration(labelText: 'Paid by'),
              items: [for (final e in _modes.entries) DropdownMenuItem(value: e.key, child: Text(e.value))],
              onChanged: (v) => setD(() => mode = v ?? mode),
            ),
            const SizedBox(height: 8),
            TextField(
              controller: refCtl,
              decoration: InputDecoration(
                labelText: mode == 'cash' ? 'Reference (optional)' : 'Cheque no. / UTR',
                helperText: member && mode != 'cash' && mode != 'cheque' ? 'Needed for UPI and bank transfers' : null,
              ),
            ),
          ]),
          actions: [
            TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancel')),
            FilledButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('Record it')),
          ],
        ),
      ),
    );
    final reference = refCtl.text;
    refCtl.dispose();
    if (ok != true) return;
    setState(() => _busy = true);
    try {
      final done = await ref.read(assistApiProvider)
          .recordEntry(redirect.recordPayload(mode: mode, reference: reference, text: widget.text));
      if (!mounted) return;
      setState(() => _done = done);
      AppToast.success(context, done.reference == null ? 'Recorded' : '${done.reference} recorded');
    } catch (e) {
      if (mounted) showErrorToast(context, e);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }


  @override
  Widget build(BuildContext context) {
    final redirect = widget.redirect;
    final onNotAgainstBill = widget.onNotAgainstBill;
    if (_done != null) {
      return AgentCard(
        accent: Hud.green,
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          HudChip(label: _done!.status == 'pending' ? 'Recorded · waits for bank reconciliation' : 'Recorded',
              tone: AppTone.success, icon: Icons.check_circle_outline_rounded),
          const SizedBox(height: 8),
          Text(_done!.summary, style: const TextStyle(fontSize: 13.5, height: 1.4)),
          if (_done!.settled.isNotEmpty) KeyValue('Bills settled', _done!.settled.join(', ')),
        ]),
      );
    }
    final member = redirect.kind == 'member_receipt';
    return AgentCard(
      accent: Hud.amber,
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Wrap(spacing: 8, runSpacing: 6, children: [
          HudChip(label: member ? 'Member payment' : 'Vendor bill payment', tone: AppTone.warning,
              icon: member ? Icons.home_outlined : Icons.storefront_outlined),
          if (redirect.flat != null) HudChip(label: redirect.flat!, tone: AppTone.info),
        ]),
        const SizedBox(height: 8),
        Text(redirect.message, style: const TextStyle(fontSize: 13.5, height: 1.4)),
        const SizedBox(height: 8),
        KeyValue('Proper entry', redirect.accounting),
        if (redirect.amount.isNotEmpty) KeyValue('Amount', formatInr(double.tryParse(redirect.amount) ?? 0)),
        for (final b in redirect.bills)
          KeyValue('Open bill ${b['invoice_number']}', '${formatInr(double.tryParse('${b['due']}') ?? 0)} due · ${b['invoice_date']}'),
        const SizedBox(height: 10),
        Wrap(spacing: 10, runSpacing: 8, children: [
          if (redirect.canRecord)
            FilledButton.icon(
              key: const Key('record-for-me'),
              onPressed: _busy ? null : _recordForMe,
              icon: const Icon(Icons.auto_fix_high_rounded),
              label: const Text('Record it for me'),
            ),
          OutlinedButton.icon(
            onPressed: () => context.push(member ? AppRoutes.onlinePayments : AppRoutes.vendorBills),
            icon: Icon(member ? Icons.receipt_long_outlined : Icons.request_page_outlined),
            label: Text(member ? 'Open Billing' : 'Open Vendor Bills'),
          ),
          if (!member)
            OutlinedButton(onPressed: onNotAgainstBill, child: const Text('Not for these bills — draft it here')),
        ]),
      ]),
    );
  }
}
