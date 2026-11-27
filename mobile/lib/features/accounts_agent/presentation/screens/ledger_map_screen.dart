import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/motion/loading.dart';
import 'package:ar_society_app/core/theme/design_tokens.dart';
import 'package:ar_society_app/features/accounts/data/accounts_api.dart' show formatInr;
import 'package:ar_society_app/features/accounts_agent/presentation/widgets/agent_hud.dart';
import 'package:ar_society_app/features/accounts_agent/data/legal_api.dart';
import 'package:ar_society_app/features/accounts_agent/presentation/providers/legal_providers.dart';
import 'package:ar_society_app/features/accounts_agent/presentation/widgets/agent_widgets.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/shared/widgets/app_form.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';

String ledgerStatusLabel(String s) => switch (s) {
      'differs_from_society_rule' => 'Differs from society rule',
      'rule_ledger_missing' => 'Rule names a missing ledger',
      'no_element' => 'No element linked',
      'fallback_ledger' => 'Default ledger (fallback)',
      _ => 'OK',
    };

AppTone ledgerStatusTone(String s) => switch (s) {
      'ok' => AppTone.success,
      'differs_from_society_rule' || 'rule_ledger_missing' => AppTone.danger,
      _ => AppTone.warning,
    };

/// The body of a society element → ledger rule (POST /accounts-agent/legal/rules). Throws [FormatException] with a
/// user-facing message when something required is missing.
Map<String, dynamic> buildLedgerRulePayload({
  required String elementCode,
  required String elementName,
  required String? accountId,
  required String? documentId,
  String level = 'D',
  String? byeLawNumber,
  String? page,
}) {
  if (accountId == null) throw const FormatException('Choose the ledger the rule names');
  if (documentId == null) throw const FormatException('Choose the society document the rule comes from');
  final code = 'SOC-LED-${elementCode.toUpperCase().replaceAll(RegExp(r'[^A-Z0-9]'), '-')}';
  String? opt(String? s) => (s == null || s.trim().isEmpty) ? null : s.trim();
  return {
    'rule_code': code.length > 60 ? code.substring(0, 60) : code,
    'title': 'Ledger for $elementName',
    'topic': 'ledger.element.$elementCode',
    'rule_category': 'ledger',
    'source_level': level,
    'source_document_id': documentId,
    'calculation_method': {'type': 'element_ledger', 'account_id': accountId},
    if (opt(byeLawNumber) != null) 'bye_law_number': opt(byeLawNumber),
    if (opt(page) != null) 'page_number': opt(page),
  };
}

/// Which ledger each maintenance element is credited to: the app's standard table, the society's own rule, and what
/// bills actually posted — for the committee or auditor to review and sign off.
class LedgerMapScreen extends ConsumerWidget {
  const LedgerMapScreen({super.key});

  Future<void> _signOff(BuildContext context, WidgetRef ref, LedgerMap m) async {
    final note = TextEditingController();
    var role = 'COMMITTEE';
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setS) => AlertDialog(
          title: const Text('Sign off the element → ledger map'),
          content: Column(mainAxisSize: MainAxisSize.min, children: [
            Text('You confirm that ${m.rows.length} charge head(s) post to the ledgers shown'
                '${m.flagged > 0 ? ', including ${m.flagged} flagged row(s)' : ''}.', style: const TextStyle(fontSize: 13)),
            DropdownButtonFormField<String>(
              initialValue: role,
              decoration: const InputDecoration(labelText: 'Signed off by'),
              items: const [
                DropdownMenuItem(value: 'COMMITTEE', child: Text('Managing Committee')),
                DropdownMenuItem(value: 'AUDITOR', child: Text('Auditor')),
              ],
              onChanged: (v) => setS(() => role = v ?? role),
            ),
            TextField(controller: note, maxLines: 2, decoration: const InputDecoration(labelText: 'Note (required)')),
          ]),
          actions: [
            TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancel')),
            FilledButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('Sign off')),
          ],
        ),
      ),
    );
    if (ok != true || !context.mounted) return;
    if (note.text.trim().length < 3) {
      showErrorToast(context, Exception('Add a short note'));
      return;
    }
    try {
      await ref.read(legalApiProvider).signOffLedgerMap(role: role, note: note.text.trim(), fingerprint: m.fingerprint);
      invalidateLegal(ref);
      if (context.mounted) AppToast.success(context, 'Signed off');
    } catch (e) {
      invalidateLegal(ref);
      if (context.mounted) showErrorToast(context, e);
    }
  }

  Future<void> _setRule(BuildContext context, WidgetRef ref, LedgerMap m, LedgerMapRow r) async {
    final docs = await ref.read(legalApiProvider).documents(scope: 'society');
    if (!context.mounted) return;
    final own = [for (final d in docs) if (d.status != 'SUPERSEDED' && d.status != 'REJECTED') d];
    String? account, doc;
    var level = 'D';
    final byeLaw = TextEditingController(), page = TextEditingController();
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setS) => AlertDialog(
          title: Text('Society rule: ${r.element ?? r.head}'),
          content: SingleChildScrollView(
            child: Column(mainAxisSize: MainAxisSize.min, children: [
              const Text('Record the ledger your bye-laws or accounting policy name for this element. It is saved unverified '
                  'and is checked only after it is verified.', style: TextStyle(fontSize: 12.5)),
              DropdownButtonFormField<String>(
                initialValue: account,
                isExpanded: true,
                decoration: const InputDecoration(labelText: 'Ledger'),
                items: [for (final l in m.ledgers) DropdownMenuItem(value: l['id'] as String, child: Text('${l['name']}', overflow: TextOverflow.ellipsis))],
                onChanged: (v) => setS(() => account = v),
              ),
              DropdownButtonFormField<String>(
                initialValue: level,
                isExpanded: true,
                decoration: const InputDecoration(labelText: 'Source'),
                items: const [
                  DropdownMenuItem(value: 'D', child: Text('Registered bye-law')),
                  DropdownMenuItem(value: 'E', child: Text('General Body resolution')),
                  DropdownMenuItem(value: 'G', child: Text('Accounting policy')),
                ],
                onChanged: (v) => setS(() => level = v ?? level),
              ),
              DropdownButtonFormField<String>(
                initialValue: doc,
                isExpanded: true,
                decoration: InputDecoration(labelText: 'Society document', helperText: own.isEmpty ? 'Upload it in the Legal Library first' : null),
                items: [for (final d in own) DropdownMenuItem(value: d.id, child: Text(d.title, overflow: TextOverflow.ellipsis))],
                onChanged: (v) => setS(() => doc = v),
              ),
              Row(children: [
                Expanded(child: TextField(controller: byeLaw, decoration: const InputDecoration(labelText: 'Bye-law no.'))),
                const SizedBox(width: 10),
                Expanded(child: TextField(controller: page, decoration: const InputDecoration(labelText: 'Page'))),
              ]),
            ]),
          ),
          actions: [
            TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancel')),
            FilledButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('Save rule')),
          ],
        ),
      ),
    );
    if (ok != true || !context.mounted) return;
    try {
      final body = buildLedgerRulePayload(
          elementCode: r.elementCode!, elementName: r.element ?? r.head, accountId: account, documentId: doc, level: level,
          byeLawNumber: byeLaw.text, page: page.text);
      await ref.read(legalApiProvider).createSocietyRule(body);
      invalidateLegal(ref);
      if (context.mounted) AppToast.success(context, 'Rule saved — verify it in Legal Library → Legal rules');
    } on FormatException catch (e) {
      if (context.mounted) showErrorToast(context, Exception(e.message));
    } catch (e) {
      if (context.mounted) showErrorToast(context, e);
    }
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final mayDecide = ref.watch(currentUserProvider)?.isAdminOrCommittee ?? false;
    final async = ref.watch(ledgerMapProvider);
    return AppPage(
      title: 'Element → ledger map',
      subtitle: 'Where each maintenance element is credited, checked against your society\'s rules',
      maxWidth: 1000,
      body: RefreshIndicator(
        onRefresh: () async => ref.invalidate(ledgerMapProvider),
        child: async.when(
          loading: () => const AppLoader(),
          error: (e, _) => HudErrorState(message: friendlyErrorMessage(e), onRetry: () => ref.invalidate(ledgerMapProvider)),
          data: (m) => ListView(padding: const EdgeInsets.fromLTRB(16, 12, 16, 96), children: [
            AgentCard(
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Wrap(spacing: 8, runSpacing: 6, children: [
                  HudChip(
                      label: m.signedOffCurrent ? 'Signed off' : (m.signedOff == null ? 'Not signed off' : 'Changed since sign-off'),
                      tone: m.signedOffCurrent ? AppTone.success : AppTone.warning),
                  HudChip(label: '${m.flagged} flagged', tone: m.flagged == 0 ? AppTone.success : AppTone.warning),
                ]),
                if (m.signedOff != null) ...[
                  const SizedBox(height: 6),
                  KeyValue('Last sign-off', '${titleCase('${m.signedOff!['role']}')} · ${stamp(DateTime.tryParse('${m.signedOff!['at']}'))}'),
                  KeyValue('Note', m.signedOff!['note'] as String?),
                ],
                const SizedBox(height: 6),
                Text(m.note, style: const TextStyle(fontSize: 12.5, color: Hud.dim)),
                if (mayDecide) ...[
                  const SizedBox(height: 8),
                  FilledButton.icon(
                      onPressed: () => _signOff(context, ref, m), icon: const Icon(Icons.how_to_reg_outlined), label: const Text('Sign off this map')),
                ],
              ]),
            ),
            const AgentSectionTitle('Agent review: elements & ledgers by the bye-laws'),
            _ElementReviewPanel(mayDecide: mayDecide),
            const AgentSectionTitle('Charge heads'),
            for (final r in m.rows)
              Padding(
                padding: const EdgeInsets.only(bottom: 10),
                child: AgentCard(
                  child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    Wrap(spacing: 8, runSpacing: 6, children: [
                      HudChip(label: ledgerStatusLabel(r.status), tone: ledgerStatusTone(r.status)),
                      HudChip(label: r.sourceLabel, tone: r.source == 'charge_type' ? AppTone.warning : AppTone.neutral),
                    ]),
                    const SizedBox(height: 6),
                    Text(r.head, style: const TextStyle(fontWeight: FontWeight.w700)),
                    KeyValue('Element', r.element == null ? 'None linked' : '${r.element} (${r.elementCode})'),
                    KeyValue('Posted to', r.postedLedger),
                    KeyValue('Society rule', r.ruleLedger == null ? null : '${r.ruleLedger} (${r.rule?.ruleCode ?? ''})'),
                    if (r.pendingRule != null)
                      KeyValue('Pending rule', '${r.pendingRule!['rule_code']} — not verified yet, so not checked'),
                    for (final p in r.recent) KeyValue('Recently posted', '${p['ledger']}: ${formatInr(double.tryParse('${p['amount']}') ?? 0)}'),
                    if (mayDecide && r.elementCode != null && r.ruleLedger == null && r.pendingRule == null)
                      Align(
                        alignment: Alignment.centerRight,
                        child: TextButton.icon(
                            onPressed: () => _setRule(context, ref, m, r), icon: const Icon(Icons.rule_rounded), label: const Text('Set society rule')),
                      ),
                  ]),
                ),
              ),
            if (m.unmatched.isNotEmpty) ...[
              const AgentSectionTitle('Bill lines matching no charge head'),
              for (final u in m.unmatched)
                AgentCard(
                  child: Text('${u['description']}: ${[for (final l in (u['ledgers'] as List)) '${(l as Map)['ledger']} ${l['amount']}'].join(', ')}',
                      style: const TextStyle(fontSize: 13)),
                ),
            ],
          ]),
        ),
      ),
    );
  }
}


/// The agent's review of the maintenance elements and their ledgers: each finding with the change that fixes it. Admin
/// and committee members select fixes and apply them; nothing changes until they do.
class _ElementReviewPanel extends ConsumerStatefulWidget {
  final bool mayDecide;
  const _ElementReviewPanel({required this.mayDecide});
  @override
  ConsumerState<_ElementReviewPanel> createState() => _ElementReviewPanelState();
}

class _ElementReviewPanelState extends ConsumerState<_ElementReviewPanel> {
  final Set<String> _picked = {};
  bool _busy = false;

  AppTone _tone(String severity) => switch (severity) {
        'HIGH' => AppTone.danger,
        'MEDIUM' => AppTone.warning,
        _ => AppTone.info,
      };

  Future<void> _apply(List<ElementFix> fixes) async {
    final chosen = fixes.where((f) => _picked.contains(f.id)).toList();
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text('Apply ${chosen.length} change${chosen.length == 1 ? '' : 's'}?'),
        content: Text([
          for (final f in chosen) '• ${f.title}',
          '',
          'Bills generated from now on follow these ledgers. Bills already posted are not changed.',
        ].join('\n')),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancel')),
          FilledButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('Apply')),
        ],
      ),
    );
    if (ok != true) return;
    setState(() => _busy = true);
    try {
      final done = await ref.read(legalApiProvider).applyElementFixes(chosen.map((f) => f.id).toList());
      ref.invalidate(elementReviewProvider);
      ref.invalidate(ledgerMapProvider);
      if (mounted) {
        setState(_picked.clear);
        AppToast.success(context, done.isEmpty ? 'Nothing needed changing' : '${done.length} change(s) applied');
      }
    } catch (e) {
      if (mounted) showErrorToast(context, e);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final async = ref.watch(elementReviewProvider);
    return async.when(
      loading: () => const Padding(padding: EdgeInsets.all(12), child: LinearProgressIndicator()),
      error: (e, _) => HudErrorState(message: friendlyErrorMessage(e), compact: true, onRetry: () => ref.invalidate(elementReviewProvider)),
      data: (r) {
        if (r.fixes.isEmpty) {
          return AgentCard(
            child: Row(children: [
              const Icon(Icons.verified_rounded, color: Hud.green),
              const SizedBox(width: 10),
              Expanded(child: Text('All ${r.elements} elements credit the right kind of ledger and their expense ledgers are linked.')),
            ]),
          );
        }
        return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          const Text(
              'Funds the bye-laws let a society collect (sinking, repairs, reserve…) must be held as funds, never income; '
              'charges recovered from members are income; the society\'s own verified rule wins. Each finding below '
              'comes with the exact change.',
              style: TextStyle(fontSize: 12.5, color: Hud.dim, height: 1.4)),
          const SizedBox(height: 8),
          for (final f in r.fixes)
            Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: AgentCard(
                padding: const EdgeInsets.fromLTRB(8, 10, 14, 10),
                child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  if (widget.mayDecide)
                    Checkbox(
                      key: Key('fix-${f.id}'),
                      value: _picked.contains(f.id),
                      onChanged: _busy ? null : (v) => setState(() => v == true ? _picked.add(f.id) : _picked.remove(f.id)),
                    )
                  else
                    const SizedBox(width: 8),
                  Expanded(
                    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                      Wrap(spacing: 8, runSpacing: 6, children: [
                        HudChip(label: f.severity == 'HIGH' ? 'Wrong' : (f.severity == 'MEDIUM' ? 'Should change' : 'Tidy-up'),
                            tone: _tone(f.severity)),
                        if (!f.inUse) const HudChip(label: 'Not billed yet', tone: AppTone.neutral),
                      ]),
                      const SizedBox(height: 6),
                      Text(f.title, style: const TextStyle(fontWeight: FontWeight.w700)),
                      const SizedBox(height: 4),
                      Text(f.detail, style: const TextStyle(fontSize: 13, color: Hud.dim, height: 1.35)),
                      const SizedBox(height: 4),
                      if (f.kind != 'link_expense') ...[
                        KeyValue('Now', f.currentLedger ?? 'No ledger'),
                        KeyValue('Change to', f.proposedLedger),
                      ],
                      KeyValue('Basis', f.byeLawRef),
                    ]),
                  ),
                ]),
              ),
            ),
          if (widget.mayDecide)
            Wrap(spacing: 8, runSpacing: 8, children: [
              FilledButton.icon(
                key: const Key('apply-element-fixes'),
                onPressed: _busy || _picked.isEmpty ? null : () => _apply(r.fixes),
                icon: const Icon(Icons.done_all_rounded),
                label: Text(_picked.isEmpty ? 'Select changes to apply' : 'Apply ${_picked.length} selected'),
              ),
              TextButton(
                onPressed: _busy ? null : () => setState(() => _picked..clear()..addAll(r.fixes.map((f) => f.id))),
                child: const Text('Select all'),
              ),
            ])
          else
            const Text('An admin or committee member applies these changes.', style: TextStyle(fontSize: 12.5, color: Hud.dim)),
        ]);
      },
    );
  }
}
