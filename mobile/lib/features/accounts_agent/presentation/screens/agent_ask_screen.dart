import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/core/theme/design_tokens.dart';
import 'package:ar_society_app/features/accounts_agent/data/legal_api.dart';
import 'package:ar_society_app/features/accounts_agent/presentation/providers/legal_providers.dart';
import 'package:ar_society_app/features/accounts_agent/presentation/widgets/agent_widgets.dart';
import 'package:ar_society_app/shared/widgets/app_form.dart';
import 'package:ar_society_app/shared/widgets/app_status.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';

const _suggested = [
  'Is our maintenance calculation correct?',
  'Why has our sinking fund decreased?',
  'Which flats have outstanding dues?',
  'Is this vendor payment properly approved?',
  'Can our society use this fund for this repair?',
  'What is the applicable non-occupancy charge calculation?',
  'Is this transfer fee correctly calculated?',
  'Are any committee-approved amounts exceeded?',
  'What are our pending statutory compliance items?',
  'Which audit observations remain unresolved?',
];

/// Questions answered from the society's own records and the legal registry by fixed rules — no AI service. Every legal
/// answer shows its source, clause, effective date and whether it is verified.
class AgentAskScreen extends ConsumerStatefulWidget {
  const AgentAskScreen({super.key});
  @override
  ConsumerState<AgentAskScreen> createState() => _AgentAskScreenState();
}

class _AgentAskScreenState extends ConsumerState<AgentAskScreen> {
  final _q = TextEditingController();
  AssistantAnswer? _answer;
  bool _busy = false;

  @override
  void dispose() {
    _q.dispose();
    super.dispose();
  }

  Future<void> _ask(String q) async {
    if (q.trim().length < 3) return;
    _q.text = q;
    setState(() => _busy = true);
    try {
      final a = await ref.read(legalApiProvider).ask(q.trim());
      if (mounted) setState(() => _answer = a);
    } catch (e) {
      if (mounted) showErrorToast(context, e);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final a = _answer;
    return AppPage(
      title: 'Ask the Accounts Agent',
      subtitle: 'Answers from your books, resolutions and the legal registry',
      maxWidth: 900,
      body: ListView(padding: const EdgeInsets.fromLTRB(16, 12, 16, 96), children: [
        TextField(
          controller: _q,
          textInputAction: TextInputAction.send,
          onSubmitted: _ask,
          decoration: InputDecoration(
            hintText: 'e.g. Why has our sinking fund decreased?',
            suffixIcon: _busy
                ? const Padding(padding: EdgeInsets.all(12), child: SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2)))
                : IconButton(tooltip: 'Ask', icon: const Icon(Icons.send_rounded), onPressed: () => _ask(_q.text)),
          ),
        ),
        const SizedBox(height: 10),
        Wrap(spacing: 8, runSpacing: 8, children: [for (final s in _suggested) ActionChip(label: Text(s), onPressed: () => _ask(s))]),
        if (a != null) ...[
          const AgentSectionTitle('Answer'),
          AgentCard(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              if (a.sources.isNotEmpty)
                AppStatusChip(label: a.verifiedLaw ? 'Based on verified law' : 'Legal source not verified', tone: a.verifiedLaw ? AppTone.success : AppTone.warning),
              const SizedBox(height: 8),
              Text(a.answer, style: const TextStyle(fontSize: 14, height: 1.45)),
              if (a.uncertainty != null) ...[
                const SizedBox(height: 8),
                Text(a.uncertainty!, style: const TextStyle(fontSize: 12.5, color: AppTheme.warning)),
              ],
              if (a.disclaimer != null) ...[
                const SizedBox(height: 8),
                Text(a.disclaimer!, style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
              ],
            ]),
          ),
          for (final s in a.sources) ...[const AgentSectionTitle('Source'), LegalSourceCard(source: s)],
        ],
      ]),
    );
  }
}
