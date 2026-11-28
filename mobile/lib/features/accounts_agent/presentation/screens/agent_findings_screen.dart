import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/theme/design_tokens.dart';
import 'package:ar_society_app/features/accounts_agent/presentation/widgets/agent_hud.dart';
import 'package:ar_society_app/features/accounts_agent/data/accounts_agent_api.dart';
import 'package:ar_society_app/features/accounts_agent/data/legal_api.dart' show classificationLabel;
import 'package:ar_society_app/features/accounts_agent/presentation/providers/accounts_agent_providers.dart';
import 'package:ar_society_app/features/accounts_agent/presentation/widgets/agent_widgets.dart';
import 'package:ar_society_app/shared/widgets/app_form.dart';

/// Every category a finding can carry: the accounting checks, then the legal / bye-law and residential checks (D-16).
const _categories = [
  // Accounting (per voucher)
  'duplicate', 'debit_credit', 'ledger_validation', 'sub_ledger', 'vendor_mapping', 'integrity', 'reversal',
  'unusual_journal', 'unusual_amount', 'unusual_vendor_payment', 'recurring_deviation', 'unusual_frequency',
  'ledger_mapping', 'unexpected_combination',
  // Legal, bye-law and society-wide checks
  'expenditure', 'expenditure_approval', 'funds', 'fund_monitoring', 'charges', 'maintenance_billing', 'member_ledger',
  'recovery', 'statutory_compliance', 'vendor_audit', 'budget', 'borrowing', 'transfer', 'element_ledger', 'legal_sources',
];

/// Findings, most severe first unless the person picks another order (when raised, transaction date, how certain the
/// agent is), with the filters an auditor reaches for: severity, category, status, dates and search.
class AgentFindingsScreen extends ConsumerStatefulWidget {
  final String? initialSeverity;
  final String? initialStatus;
  /// A dashboard section (e.g. "funds", "bye_law_compliance"): only that section's findings.
  final String? initialSection;
  final String? title;
  const AgentFindingsScreen({super.key, this.initialSeverity, this.initialStatus, this.initialSection, this.title});

  @override
  ConsumerState<AgentFindingsScreen> createState() => _AgentFindingsScreenState();
}

class _AgentFindingsScreenState extends ConsumerState<AgentFindingsScreen> {
  static const _pageSize = 25;
  late FindingsFilter _filter =
      FindingsFilter(severity: widget.initialSeverity, status: widget.initialStatus, section: widget.initialSection);
  final _search = TextEditingController();
  int _pages = 1;

  @override
  void dispose() {
    _search.dispose();
    super.dispose();
  }

  void _set(FindingsFilter f) => setState(() {
        _filter = f.copyWith(page: 1);
        _pages = 1;
      });

  Future<void> _pickDates() async {
    final now = DateTime.now();
    final r = await showDateRangePicker(
      context: context,
      firstDate: DateTime(now.year - 3),
      lastDate: now,
      initialDateRange: _filter.from != null && _filter.to != null ? DateTimeRange(start: _filter.from!, end: _filter.to!) : null,
    );
    if (r != null) _set(_filter.copyWith(from: r.start, to: r.end));
  }

  @override
  Widget build(BuildContext context) {
    final f = _filter;
    return AppPage(
      title: widget.title ?? 'Findings',
      subtitle: widget.initialSection == null ? 'What the agent noticed in the books' : 'Findings in this section',
      maxWidth: 960,
      body: RefreshIndicator(
        onRefresh: () async => invalidateAgent(ref),
        child: ListView(padding: const EdgeInsets.fromLTRB(16, 12, 16, 96), children: [
          TextField(
            controller: _search,
            textInputAction: TextInputAction.search,
            decoration: InputDecoration(
              hintText: 'Search voucher number, title or explanation',
              prefixIcon: const Icon(Icons.search_rounded),
              suffixIcon: f.query.isEmpty
                  ? null
                  : IconButton(
                      tooltip: 'Clear search',
                      icon: const Icon(Icons.close_rounded),
                      onPressed: () {
                        _search.clear();
                        _set(f.copyWith(query: ''));
                      }),
            ),
            onSubmitted: (v) => _set(f.copyWith(query: v)),
          ),
          const SizedBox(height: 10),
          SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            child: Row(children: [
              for (final s in severities) ...[
                FilterChip(
                  label: Text(titleCase(s)),
                  selected: f.severity == s,
                  onSelected: (on) => _set(on ? f.copyWith(severity: s) : f.copyWith(clearSeverity: true)),
                ),
                const SizedBox(width: 8),
              ],
            ]),
          ),
          const SizedBox(height: 8),
          Wrap(spacing: 8, runSpacing: 8, crossAxisAlignment: WrapCrossAlignment.center, children: [
            DropdownButton<String?>(
              value: f.category,
              hint: const Text('Category'),
              items: [
                const DropdownMenuItem<String?>(value: null, child: Text('All categories')),
                for (final c in _categories) DropdownMenuItem<String?>(value: c, child: Text(titleCase(c))),
              ],
              onChanged: (v) => _set(v == null ? f.copyWith(clearCategory: true) : f.copyWith(category: v)),
            ),
            DropdownButton<String?>(
              value: f.status,
              hint: const Text('Status'),
              items: [
                const DropdownMenuItem<String?>(value: null, child: Text('Any status')),
                for (final s in findingStatuses) DropdownMenuItem<String?>(value: s, child: Text(titleCase(s))),
              ],
              onChanged: (v) => _set(v == null ? f.copyWith(clearStatus: true) : f.copyWith(status: v)),
            ),
            Row(mainAxisSize: MainAxisSize.min, children: [
              const Icon(Icons.sort_rounded, size: 18, color: Hud.dim),
              const SizedBox(width: 6),
              DropdownButton<String>(
                key: const Key('findings-sort'),
                value: f.sort,
                underline: const SizedBox.shrink(),
                items: [for (final o in findingSorts) DropdownMenuItem<String>(value: o.$1, child: Text(o.$2))],
                onChanged: (v) => v == null ? null : _set(f.copyWith(sort: v)),
              ),
            ]),
            OutlinedButton.icon(
              onPressed: _pickDates,
              icon: const Icon(Icons.date_range_rounded, size: 18),
              label: Text(f.from == null ? 'Voucher dates' : '${day(f.from!)} – ${day(f.to!)}'),
            ),
            if (f.from != null) TextButton(onPressed: () => _set(f.copyWith(clearDates: true)), child: const Text('Clear dates')),
          ]),
          const SizedBox(height: 8),
          for (var p = 1; p <= _pages; p++) _FindingsPage(filter: f.copyWith(page: p), pageNo: p, pageSize: _pageSize, onMore: p == _pages ? () => setState(() => _pages++) : null),
        ]),
      ),
    );
  }
}

class _FindingsPage extends ConsumerWidget {
  final FindingsFilter filter;
  final int pageNo;
  final int pageSize;
  final VoidCallback? onMore;
  const _FindingsPage({required this.filter, required this.pageNo, required this.pageSize, this.onMore});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final async = ref.watch(agentFindingsProvider(filter));
    return async.when(
      loading: () => const Padding(padding: EdgeInsets.all(32), child: Center(child: CircularProgressIndicator())),
      error: (e, _) => HudErrorState(message: friendlyErrorMessage(e), compact: true, onRetry: () => ref.invalidate(agentFindingsProvider(filter))),
      data: (page) {
        if (page.items.isEmpty && pageNo == 1) {
          return const Padding(
            padding: EdgeInsets.only(top: 40),
            child: HudEmptyState(
                icon: Icons.verified_outlined, title: 'No findings', subtitle: 'Nothing matches these filters — the books look clean.'),
          );
        }
        return Column(children: [
          for (final f in page.items) Padding(padding: const EdgeInsets.only(bottom: 10), child: _FindingCard(f: f)),
          if (onMore != null && page.total > pageNo * pageSize)
            TextButton(onPressed: onMore, child: Text('Show more (${page.total - pageNo * pageSize} left)')),
        ]);
      },
    );
  }
}

class _FindingCard extends StatelessWidget {
  final AgentFinding f;
  const _FindingCard({required this.f});
  @override
  Widget build(BuildContext context) => AgentCard(
        onTap: () => context.push(agentFindingRoute(f.id)),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Wrap(spacing: 8, runSpacing: 6, children: [
            SeverityChip(f.severity),
            HudChip(label: titleCase(f.status), tone: f.isOpen ? AppTone.warning : AppTone.neutral),
            HudChip(label: classificationLabel(f.classification), tone: classificationTone(f.classification)),
            if (f.engine == 'legal') const HudChip(label: 'Legal & bye-law', tone: AppTone.info),
            if (f.onPendingVoucher) const HudChip(label: 'Voucher not yet approved', tone: AppTone.info),
          ]),
          const SizedBox(height: 8),
          Text(f.title, style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w700)),
          const SizedBox(height: 4),
          Text('${f.transactionRef ?? 'Transaction'}${f.voucherDate == null ? '' : ' · ${day(f.voucherDate!)}'} · ${titleCase(f.category)}',
              style: const TextStyle(fontSize: 12.5, color: Hud.dim)),
          const SizedBox(height: 6),
          Text(f.explanation, maxLines: 3, overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 13, height: 1.35)),
        ]),
      );
}
