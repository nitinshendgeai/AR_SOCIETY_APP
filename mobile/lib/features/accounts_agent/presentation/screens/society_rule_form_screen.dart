import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/motion/loading.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/accounts_agent/data/legal_api.dart';
import 'package:ar_society_app/features/accounts_agent/presentation/providers/legal_providers.dart';
import 'package:ar_society_app/features/accounts_agent/presentation/widgets/agent_widgets.dart';
import 'package:ar_society_app/shared/widgets/app_form.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';

/// Where a society's own rule comes from (the server accepts levels D–G only; law is recorded by the platform).
const societyRuleLevels = <String, String>{
  'D': 'Registered bye-law / approved amendment',
  'E': 'General Body resolution',
  'F': 'Managing Committee resolution',
  'G': 'Internal policy / accounting procedure',
};

/// Calculation kinds that take one figure, with the label for that figure.
const calcValueLabels = <String, String>{
  'max_pct': 'Maximum (%)',
  'min_pct': 'Minimum (%)',
  'max_amount': 'Maximum (₹)',
  'reference_pct': 'Reference rate (%)',
  'reference_amount': 'Reference amount (₹)',
};

/// A topic the agent checks, taken from the jurisdiction rule for it (so a society rule plugs into the same check).
class RuleTopic {
  final String topic, title, category;
  final String? calcType;
  const RuleTopic(this.topic, this.title, this.category, this.calcType);
}

/// The topics a society rule can usefully set: those whose jurisdiction rule has a single figure to compare with.
List<RuleTopic> numericTopics(List<LegalRule> rules) {
  final seen = <String>{};
  final out = <RuleTopic>[];
  for (final r in rules) {
    if (r.societySpecific || !r.isLatest || !calcValueLabels.containsKey(r.calcType) || !seen.add(r.topic)) continue;
    out.add(RuleTopic(r.topic, r.title, r.category, r.calcType));
  }
  out.sort((a, b) => a.title.compareTo(b.title));
  return out;
}

/// The request body for POST /accounts-agent/legal/rules. Throws [FormatException] with a user-facing message when
/// something required is missing or malformed.
Map<String, dynamic> buildSocietyRulePayload({
  required String ruleCode,
  required String title,
  required String level,
  required String? documentId,
  required RuleTopic? topic,
  String? otherTopic,
  String? value,
  String? byeLawNumber,
  String? clause,
  String? page,
  String? text,
  DateTime? effectiveFrom,
  String severity = 'MEDIUM',
}) {
  final code = ruleCode.trim().toUpperCase();
  if (!RegExp(r'^[A-Z0-9\-_.]{3,60}$').hasMatch(code)) {
    throw const FormatException('Rule code: 3–60 letters, digits, dashes, dots or underscores');
  }
  if (title.trim().length < 3) throw const FormatException('Give the rule a title');
  if (!societyRuleLevels.containsKey(level)) throw const FormatException('Choose where the rule comes from');
  if (documentId == null) throw const FormatException('Choose the society document the rule is taken from');
  final topicName = topic?.topic ?? (otherTopic ?? '').trim();
  if (topicName.length < 3) throw const FormatException('Choose what the rule governs');
  Map<String, dynamic>? calc;
  if (topic?.calcType != null) {
    final v = num.tryParse((value ?? '').trim());
    if (v == null || v < 0) throw FormatException('${calcValueLabels[topic!.calcType]}: enter a number');
    calc = {'type': topic!.calcType, 'value': v};
  }
  String two(int n) => n.toString().padLeft(2, '0');
  String? opt(String? s) => (s == null || s.trim().isEmpty) ? null : s.trim();
  return {
    'rule_code': code,
    'title': title.trim(),
    'topic': topicName,
    'rule_category': topic?.category ?? 'other',
    'source_level': level,
    'source_document_id': documentId,
    if (calc != null) 'calculation_method': calc,
    if (opt(byeLawNumber) != null) 'bye_law_number': opt(byeLawNumber),
    if (opt(clause) != null) 'clause_reference': opt(clause),
    if (opt(page) != null) 'page_number': opt(page),
    if (opt(text) != null) 'original_text': opt(text),
    if (effectiveFrom != null) 'effective_from': '${effectiveFrom.year}-${two(effectiveFrom.month)}-${two(effectiveFrom.day)}',
    'severity': severity,
  };
}

/// Records one of the society's own rules — e.g. the interest rate its registered bye-law fixes. The rule is saved
/// UNVERIFIED and governs compliance only after it is verified against an operative (verified) society document. A
/// rule looser than the Act or Rules never overrides them: the agent applies the statutory figure and opens a review.
class SocietyRuleFormScreen extends ConsumerStatefulWidget {
  const SocietyRuleFormScreen({super.key});
  @override
  ConsumerState<SocietyRuleFormScreen> createState() => _SocietyRuleFormScreenState();
}

class _SocietyRuleFormScreenState extends ConsumerState<SocietyRuleFormScreen> {
  final _code = TextEditingController(), _title = TextEditingController(), _value = TextEditingController();
  final _byeLaw = TextEditingController(), _clause = TextEditingController(), _page = TextEditingController();
  final _text = TextEditingController(), _otherTopic = TextEditingController();
  String _level = 'D', _severity = 'MEDIUM';
  String? _doc;
  RuleTopic? _topic;
  bool _other = false, _busy = false;
  DateTime? _from;

  @override
  void dispose() {
    for (final c in [_code, _title, _value, _byeLaw, _clause, _page, _text, _otherTopic]) {
      c.dispose();
    }
    super.dispose();
  }

  Future<void> _save() async {
    final Map<String, dynamic> body;
    try {
      body = buildSocietyRulePayload(
        ruleCode: _code.text, title: _title.text, level: _level, documentId: _doc, topic: _other ? null : _topic,
        otherTopic: _other ? _otherTopic.text : null, value: _value.text, byeLawNumber: _byeLaw.text, clause: _clause.text,
        page: _page.text, text: _text.text, effectiveFrom: _from, severity: _severity);
    } on FormatException catch (e) {
      showErrorToast(context, Exception(e.message));
      return;
    }
    setState(() => _busy = true);
    try {
      await ref.read(legalApiProvider).createSocietyRule(body);
      invalidateLegal(ref);
      if (mounted) {
        AppToast.success(context, 'Rule saved — verify it to make it govern compliance');
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
    final rules = ref.watch(legalRulesProvider);
    final docs = ref.watch(legalDocumentsProvider);
    return AppPage(
      title: 'Add a society rule',
      subtitle: 'From your registered bye-laws, a resolution or a society policy',
      maxWidth: 760,
      body: rules.when(
        loading: () => const AppLoader(),
        error: (e, _) => AppErrorState(message: friendlyErrorMessage(e), onRetry: () => ref.invalidate(legalRulesProvider)),
        data: (all) {
          final topics = numericTopics(all);
          final ownDocs = [for (final d in docs.valueOrNull ?? const <LegalDocument>[]) if (d.societySpecific && d.status != 'SUPERSEDED' && d.status != 'REJECTED') d];
          return ListView(padding: const EdgeInsets.fromLTRB(16, 12, 16, 96), children: [
            const AgentCard(
              child: Text(
                'The rule is saved as unverified. It governs the agent\'s checks only after an admin verifies it against a '
                'verified society document. A bye-law or resolution cannot relax the Act or Rules: a looser figure is flagged '
                'as a conflict for legal review, a stricter one is applied.',
                style: TextStyle(fontSize: 13, height: 1.4),
              ),
            ),
            const AgentSectionTitle('What the rule governs'),
            DropdownButtonFormField<String>(
              initialValue: _other ? '__other' : _topic?.topic,
              isExpanded: true,
              decoration: const InputDecoration(labelText: 'Topic'),
              items: [
                for (final t in topics) DropdownMenuItem(value: t.topic, child: Text(t.title, overflow: TextOverflow.ellipsis)),
                const DropdownMenuItem(value: '__other', child: Text('Something else (recorded, not checked automatically)')),
              ],
              onChanged: (v) => setState(() {
                _other = v == '__other';
                _topic = _other ? null : topics.where((t) => t.topic == v).firstOrNull;
                if (_title.text.isEmpty && _topic != null) _title.text = _topic!.title;
              }),
            ),
            if (_other) TextField(controller: _otherTopic, decoration: const InputDecoration(labelText: 'Topic (e.g. parking.allotment)')),
            if (_topic?.calcType != null)
              TextField(
                controller: _value,
                keyboardType: const TextInputType.numberWithOptions(decimal: true),
                decoration: InputDecoration(labelText: calcValueLabels[_topic!.calcType]),
              ),
            TextField(controller: _title, decoration: const InputDecoration(labelText: 'Title')),
            TextField(
              controller: _code,
              textCapitalization: TextCapitalization.characters,
              decoration: const InputDecoration(labelText: 'Rule code', hintText: 'e.g. SOC-BL70-INTEREST'),
            ),
            const AgentSectionTitle('Where it comes from'),
            DropdownButtonFormField<String>(
              initialValue: _level,
              isExpanded: true,
              decoration: const InputDecoration(labelText: 'Source'),
              items: [for (final e in societyRuleLevels.entries) DropdownMenuItem(value: e.key, child: Text(e.value))],
              onChanged: (v) => setState(() => _level = v ?? _level),
            ),
            DropdownButtonFormField<String>(
              initialValue: _doc,
              isExpanded: true,
              decoration: InputDecoration(
                labelText: 'Society document',
                helperText: ownDocs.isEmpty ? 'Upload the document in the Legal Library first' : null,
              ),
              items: [
                for (final d in ownDocs)
                  DropdownMenuItem(value: d.id, child: Text('${d.title}${d.operative ? '' : ' (not yet verified)'}', overflow: TextOverflow.ellipsis)),
              ],
              onChanged: (v) => setState(() => _doc = v),
            ),
            Row(children: [
              Expanded(child: TextField(controller: _byeLaw, decoration: const InputDecoration(labelText: 'Bye-law no.'))),
              const SizedBox(width: 10),
              Expanded(child: TextField(controller: _clause, decoration: const InputDecoration(labelText: 'Clause'))),
              const SizedBox(width: 10),
              Expanded(child: TextField(controller: _page, decoration: const InputDecoration(labelText: 'Page'))),
            ]),
            TextField(controller: _text, maxLines: 4, decoration: const InputDecoration(labelText: 'Text of the clause (as written)')),
            const SizedBox(height: 8),
            Wrap(spacing: 12, runSpacing: 8, crossAxisAlignment: WrapCrossAlignment.center, children: [
              OutlinedButton.icon(
                icon: const Icon(Icons.event_outlined),
                label: Text(_from == null ? 'In force from (optional)' : 'In force from ${day(_from!)}'),
                onPressed: () async {
                  final p = await showDatePicker(context: context, initialDate: _from ?? DateTime.now(), firstDate: DateTime(1960), lastDate: DateTime(2100));
                  if (p != null) setState(() => _from = p);
                },
              ),
              DropdownButton<String>(
                value: _severity,
                items: const [
                  DropdownMenuItem(value: 'HIGH', child: Text('High severity')),
                  DropdownMenuItem(value: 'MEDIUM', child: Text('Medium severity')),
                  DropdownMenuItem(value: 'LOW', child: Text('Low severity')),
                ],
                onChanged: (v) => setState(() => _severity = v ?? _severity),
              ),
            ]),
            const SizedBox(height: 16),
            FilledButton.icon(
              onPressed: _busy ? null : _save,
              icon: _busy
                  ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2))
                  : const Icon(Icons.save_outlined),
              label: const Text('Save rule'),
            ),
            const SizedBox(height: 8),
            const Text('Rules can be revised later only as a new version; the earlier version is kept.',
                style: TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
          ]);
        },
      ),
    );
  }
}
