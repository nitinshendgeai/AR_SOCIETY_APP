import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/core/theme/design_tokens.dart';
import 'package:ar_society_app/features/accounts_agent/data/assist_api.dart';
import 'package:ar_society_app/features/accounts_agent/data/legal_api.dart';
import 'package:ar_society_app/features/accounts_agent/presentation/providers/legal_providers.dart';
import 'package:ar_society_app/features/accounts_agent/presentation/widgets/agent_widgets.dart';
import 'package:ar_society_app/shared/widgets/app_form.dart';
import 'package:ar_society_app/shared/widgets/app_status.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';

const _suggestedBooks = [
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

const _suggestedBylaws = [
  'How many days notice is needed for the AGM?',
  'What is the quorum for a general meeting?',
  'Can we charge non-occupancy charges for a rented flat?',
  'What interest can be charged on unpaid dues?',
  'How is a flat transferred to a new member?',
  'How much can the committee spend without the general body?',
];

enum _Mode { bylaws, books }

/// Ask the Accounts Agent. "Bye-laws": answered only from the bye-laws in the Legal Library, with the clause, page and
/// source of each statement (worded by Claude when the society has switched it on). "Books & registry": the fixed
/// answers from the society's own records and the legal registry.
class AgentAskScreen extends ConsumerStatefulWidget {
  const AgentAskScreen({super.key});
  @override
  ConsumerState<AgentAskScreen> createState() => _AgentAskScreenState();
}

class _AgentAskScreenState extends ConsumerState<AgentAskScreen> {
  final _q = TextEditingController();
  _Mode _mode = _Mode.bylaws;
  AssistantAnswer? _books;
  BylawAnswer? _bylaws;
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
      if (_mode == _Mode.bylaws) {
        final a = await ref.read(assistApiProvider).askBylaws(q.trim());
        if (mounted) setState(() => _bylaws = a);
      } else {
        final a = await ref.read(legalApiProvider).ask(q.trim());
        if (mounted) setState(() => _books = a);
      }
    } catch (e) {
      if (mounted) showErrorToast(context, e);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final suggestions = _mode == _Mode.bylaws ? _suggestedBylaws : _suggestedBooks;
    return AppPage(
      title: 'Ask the Accounts Agent',
      subtitle: 'Answers from your bye-laws, books, resolutions and the legal registry',
      maxWidth: 900,
      body: ListView(padding: const EdgeInsets.fromLTRB(16, 12, 16, 96), children: [
        SegmentedButton<_Mode>(
          segments: const [
            ButtonSegment(value: _Mode.bylaws, icon: Icon(Icons.menu_book_outlined), label: Text('Bye-laws')),
            ButtonSegment(value: _Mode.books, icon: Icon(Icons.account_balance_outlined), label: Text('Books & registry')),
          ],
          selected: {_mode},
          onSelectionChanged: (s) => setState(() => _mode = s.first),
        ),
        const SizedBox(height: 12),
        TextField(
          controller: _q,
          textInputAction: TextInputAction.send,
          onSubmitted: _ask,
          decoration: InputDecoration(
            hintText: _mode == _Mode.bylaws ? 'e.g. How many days notice is needed for the AGM?' : 'e.g. Why has our sinking fund decreased?',
            suffixIcon: _busy
                ? const Padding(padding: EdgeInsets.all(12), child: SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2)))
                : IconButton(tooltip: 'Ask', icon: const Icon(Icons.send_rounded), onPressed: () => _ask(_q.text)),
          ),
        ),
        const SizedBox(height: 10),
        Wrap(spacing: 8, runSpacing: 8, children: [for (final s in suggestions) ActionChip(label: Text(s), onPressed: () => _ask(s))]),
        if (_mode == _Mode.bylaws && _bylaws != null) ..._bylawAnswer(_bylaws!),
        if (_mode == _Mode.books && _books != null) ..._booksAnswer(_books!),
      ]),
    );
  }

  List<Widget> _bylawAnswer(BylawAnswer a) => [
        const AgentSectionTitle('Answer'),
        AgentCard(
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Wrap(spacing: 8, runSpacing: 6, children: [
              if (a.aiGenerated) const AppStatusChip(label: 'Worded by AI from the clauses below', tone: AppTone.info),
              if (!a.answeredBySources) const AppStatusChip(label: 'Not answered by the bye-laws', tone: AppTone.warning),
              if (a.needsProfessionalReview) const AppStatusChip(label: 'Check with your committee / adviser', tone: AppTone.warning),
            ]),
            const SizedBox(height: 8),
            Text(a.answer, style: const TextStyle(fontSize: 14, height: 1.45)),
            for (final n in a.notes) ...[
              const SizedBox(height: 8),
              Text(n, style: const TextStyle(fontSize: 12.5, color: AppTheme.warning)),
            ],
            if (a.societyFacts != null) ...[
              const SizedBox(height: 8),
              Text('From your books: ${a.societyFacts}', style: const TextStyle(fontSize: 13, color: AppTheme.textSecondary)),
            ],
            const SizedBox(height: 8),
            Text(a.disclaimer, style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
          ]),
        ),
        if (a.cited.isNotEmpty) const AgentSectionTitle('Bye-law clauses'),
        for (final s in a.cited)
          Padding(padding: const EdgeInsets.only(bottom: 8), child: _ClauseCard(source: s)),
      ];

  List<Widget> _booksAnswer(AssistantAnswer a) => [
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
      ];
}

class _ClauseCard extends StatelessWidget {
  final BylawSource source;
  const _ClauseCard({required this.source});
  @override
  Widget build(BuildContext context) => AgentCard(
        child: Theme(
          data: Theme.of(context).copyWith(dividerColor: Colors.transparent),
          child: ExpansionTile(
            tilePadding: EdgeInsets.zero,
            childrenPadding: const EdgeInsets.only(bottom: 8),
            title: Text('[${source.cite}] ${source.label}', style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 14)),
            subtitle: Padding(
              padding: const EdgeInsets.only(top: 4),
              child: Wrap(spacing: 6, runSpacing: 4, children: [
                if (source.heading != null) Text(source.heading!, style: const TextStyle(fontSize: 12.5)),
                AppStatusChip(label: source.societySpecific ? 'Your bye-laws' : 'Model bye-laws', tone: source.societySpecific ? AppTone.success : AppTone.info),
                if (!source.verified) const AppStatusChip(label: 'Text not verified', tone: AppTone.warning),
              ]),
            ),
            children: [
              Align(alignment: Alignment.centerLeft, child: SelectableText(source.text, style: const TextStyle(fontSize: 13, height: 1.4))),
              const SizedBox(height: 6),
              Align(alignment: Alignment.centerLeft, child: Text(source.documentTitle, style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary))),
            ],
          ),
        ),
      );
}
