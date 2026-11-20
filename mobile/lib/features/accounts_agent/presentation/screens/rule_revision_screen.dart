import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/motion/loading.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/core/theme/design_tokens.dart';
import 'package:ar_society_app/features/accounts_agent/data/legal_api.dart';
import 'package:ar_society_app/features/accounts_agent/presentation/providers/legal_providers.dart';
import 'package:ar_society_app/features/accounts_agent/presentation/screens/society_rule_form_screen.dart' show calcValueLabels;
import 'package:ar_society_app/features/accounts_agent/presentation/widgets/agent_widgets.dart';
import 'package:ar_society_app/shared/widgets/app_form.dart';
import 'package:ar_society_app/shared/widgets/app_status.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';

final _ruleProvider = FutureProvider.autoDispose.family<(LegalRule, List<LegalRule>), String>(
    (ref, id) => ref.watch(legalApiProvider).ruleWithVersions(id));

String _d(DateTime d) => '${d.year.toString().padLeft(4, '0')}-${d.month.toString().padLeft(2, '0')}-${d.day.toString().padLeft(2, '0')}';

/// The body of POST /accounts-agent/legal/rules/{id}/versions. Throws [FormatException] with a user-facing message.
Map<String, dynamic> buildRevisionPayload({
  required LegalRule current,
  required DateTime? effectiveFrom,
  required String changeNote,
  String? value,
  String? accountId,
  String? clause,
  String? page,
  String? text,
}) {
  if (effectiveFrom == null) throw const FormatException('Choose the date the new version takes effect');
  final from = DateTime.tryParse(current.effectiveFrom ?? '');
  if (from != null && !effectiveFrom.isAfter(from)) {
    throw FormatException('The new version must take effect after ${current.effectiveFrom}');
  }
  if (changeNote.trim().length < 3) throw const FormatException('Say what changed and why');
  Map<String, dynamic>? calc;
  final type = current.calcType;
  if (type == 'element_ledger') {
    if (accountId == null) throw const FormatException('Choose the ledger');
    calc = {'type': type, 'account_id': accountId};
  } else if (calcValueLabels.containsKey(type) && (value ?? '').trim().isNotEmpty) {
    final v = num.tryParse(value!.trim());
    if (v == null || v < 0) throw FormatException('${calcValueLabels[type]}: enter a number');
    calc = {...current.calculation, 'value': v};
  }
  String? opt(String? s) => (s == null || s.trim().isEmpty) ? null : s.trim();
  return {
    'effective_from': _d(effectiveFrom),
    'change_note': changeNote.trim(),
    if (calc != null) 'calculation_method': calc,
    if (opt(clause) != null) 'clause_reference': opt(clause),
    if (opt(page) != null) 'page_number': opt(page),
    if (opt(text) != null) 'original_text': opt(text),
  };
}

/// A rule's version history, and a new version of it. A change in a rate or provision is always a new version: the
/// earlier one is kept and stays the rule for dates before the new one takes effect.
class RuleRevisionScreen extends ConsumerStatefulWidget {
  final String ruleId;
  const RuleRevisionScreen({super.key, required this.ruleId});
  @override
  ConsumerState<RuleRevisionScreen> createState() => _RuleRevisionScreenState();
}

class _RuleRevisionScreenState extends ConsumerState<RuleRevisionScreen> {
  final _value = TextEditingController(), _note = TextEditingController(), _clause = TextEditingController();
  final _page = TextEditingController(), _text = TextEditingController();
  DateTime? _from;
  String? _account;
  bool _busy = false;

  @override
  void dispose() {
    for (final c in [_value, _note, _clause, _page, _text]) {
      c.dispose();
    }
    super.dispose();
  }

  Future<void> _save(LegalRule current) async {
    final Map<String, dynamic> body;
    try {
      body = buildRevisionPayload(current: current, effectiveFrom: _from, changeNote: _note.text, value: _value.text,
          accountId: _account, clause: _clause.text, page: _page.text, text: _text.text);
    } on FormatException catch (e) {
      showErrorToast(context, Exception(e.message));
      return;
    }
    setState(() => _busy = true);
    try {
      await ref.read(legalApiProvider).reviseRule(current.id, body);
      invalidateLegal(ref);
      ref.invalidate(_ruleProvider(widget.ruleId));
      if (mounted) {
        AppToast.success(context, 'New version saved — verify it before it governs');
        context.pop();
      }
    } catch (e) {
      if (mounted) showErrorToast(context, e);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final async = ref.watch(_ruleProvider(widget.ruleId));
    final ledgers = ref.watch(ledgerMapProvider).valueOrNull?.ledgers ?? const [];
    return AppPage(
      title: 'Revise rule',
      subtitle: 'Each change is a new version; earlier versions are kept',
      maxWidth: 800,
      body: async.when(
        loading: () => const AppLoader(),
        error: (e, _) => AppErrorState(message: friendlyErrorMessage(e), onRetry: () => ref.invalidate(_ruleProvider(widget.ruleId))),
        data: (pair) {
          final (rule, versions) = pair;
          final latest = versions.isEmpty ? rule : versions.last;
          final type = latest.calcType;
          return ListView(padding: const EdgeInsets.fromLTRB(16, 12, 16, 96), children: [
            AgentCard(
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text(latest.title, style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w700)),
                KeyValue('Rule', '${latest.code} (latest: version ${latest.version})'),
                KeyValue('Reference', latest.reference),
              ]),
            ),
            const AgentSectionTitle('Versions'),
            for (final v in versions.reversed)
              Padding(
                padding: const EdgeInsets.only(bottom: 8),
                child: AgentCard(
                  child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    Wrap(spacing: 8, runSpacing: 6, children: [
                      AppStatusChip(label: 'v${v.version}', tone: AppTone.neutral),
                      AppStatusChip(label: titleCase(v.legalStatus), tone: v.legalStatus == 'SUPERSEDED' ? AppTone.neutral : AppTone.info),
                      AppStatusChip(label: verificationLabel(v.verification), tone: v.isVerified ? AppTone.success : AppTone.warning),
                    ]),
                    KeyValue('In force', [if (v.effectiveFrom != null) 'from ${v.effectiveFrom}', if (v.effectiveUntil != null) 'until ${v.effectiveUntil}'].join(' ')),
                    if (v.calcValue != null) KeyValue('Figure', '${v.calcValue}'),
                    if (v.raw['change_note'] != null) KeyValue('Change', '${v.raw['change_note']}'),
                  ]),
                ),
              ),
            if (!latest.isLatest)
              const Text('Only the latest version can be revised.', style: TextStyle(color: AppTheme.warning))
            else ...[
              const AgentSectionTitle('New version'),
              OutlinedButton.icon(
                icon: const Icon(Icons.event_outlined),
                label: Text(_from == null ? 'Takes effect from (required)' : 'Takes effect from ${day(_from!)}'),
                onPressed: () async {
                  final p = await showDatePicker(context: context, initialDate: _from ?? DateTime.now(),
                      firstDate: DateTime(1960), lastDate: DateTime(2100));
                  if (p != null) setState(() => _from = p);
                },
              ),
              if (type == 'element_ledger')
                DropdownButtonFormField<String>(
                  initialValue: _account,
                  isExpanded: true,
                  decoration: const InputDecoration(labelText: 'Ledger'),
                  items: [for (final l in ledgers) DropdownMenuItem(value: l['id'] as String, child: Text('${l['name']}', overflow: TextOverflow.ellipsis))],
                  onChanged: (v) => setState(() => _account = v),
                )
              else if (calcValueLabels.containsKey(type))
                TextField(
                  controller: _value,
                  keyboardType: const TextInputType.numberWithOptions(decimal: true),
                  decoration: InputDecoration(labelText: '${calcValueLabels[type]} (now ${latest.calcValue})'),
                ),
              TextField(controller: _note, maxLines: 2, decoration: const InputDecoration(labelText: 'What changed and why (required)')),
              Row(children: [
                Expanded(child: TextField(controller: _clause, decoration: const InputDecoration(labelText: 'Clause'))),
                const SizedBox(width: 10),
                Expanded(child: TextField(controller: _page, decoration: const InputDecoration(labelText: 'Page'))),
              ]),
              TextField(controller: _text, maxLines: 3, decoration: const InputDecoration(labelText: 'New text of the clause')),
              const SizedBox(height: 16),
              FilledButton.icon(
                onPressed: _busy ? null : () => _save(latest),
                icon: _busy ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2)) : const Icon(Icons.save_outlined),
                label: const Text('Save new version'),
              ),
              const SizedBox(height: 8),
              const Text('The new version is unverified until checked against the society document, like any rule.',
                  style: TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
            ],
          ]);
        },
      ),
    );
  }
}
