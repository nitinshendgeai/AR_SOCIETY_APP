import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/motion/loading.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/accounts/data/accounts_api.dart';
import 'package:ar_society_app/features/accounts/data/outstanding_api.dart';
import 'package:ar_society_app/features/accounts/presentation/widgets/accounts_widgets.dart';
import 'package:ar_society_app/features/accounts/presentation/widgets/register_widgets.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/shared/widgets/app_form.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';

/// Outstandings, Tally style: what members owe the society (receivable) or the society owes vendors (payable),
/// aged in days past the due date. A band chip narrows the list to the parties with something in that band; a
/// party opens to the bills behind it. The PDF is the statement for the chosen side.
class OutstandingScreen extends ConsumerStatefulWidget {
  /// 'receivable' or 'payable'.
  final String initialKind;
  const OutstandingScreen({super.key, this.initialKind = 'receivable'});

  @override
  ConsumerState<OutstandingScreen> createState() => _OutstandingScreenState();
}

class _OutstandingScreenState extends ConsumerState<OutstandingScreen> {
  late String _kind = widget.initialKind == 'payable' ? 'payable' : 'receivable';
  String? _band;
  String _search = '';

  bool get _receivable => _kind == 'receivable';

  @override
  Widget build(BuildContext context) {
    final societyId = ref.watch(currentUserProvider)?.societyId ?? '';
    final key = (societyId: societyId, kind: _kind);
    final async = ref.watch(outstandingProvider(key));
    return AppPage(
      title: _receivable ? 'Outstanding Receivable' : 'Outstanding Payable',
      subtitle: _receivable
          ? 'What members owe the society, aged from the due date'
          : 'What the society owes vendors, aged from the due date',
      actions: [
        PdfActions(
          load: async.valueOrNull == null ? null : () => ref.read(outstandingApiProvider).pdf(societyId, _kind),
          fileName: 'Outstanding-${_receivable ? 'Receivable' : 'Payable'}.pdf',
          subject: _receivable ? 'Outstanding receivable' : 'Outstanding payable',
        ),
      ],
      body: RefreshIndicator(
        onRefresh: () async => ref.invalidate(outstandingProvider(key)),
        child: ListView(
          padding: const EdgeInsets.fromLTRB(16, 12, 16, 96),
          children: [
            Wrap(spacing: 8, runSpacing: 8, children: [
              ChoiceChip(
                key: const Key('outstanding-receivable'),
                label: const Text('Receivable (members)'),
                selected: _receivable,
                onSelected: (_) => setState(() {
                  _kind = 'receivable';
                  _band = null;
                }),
              ),
              ChoiceChip(
                key: const Key('outstanding-payable'),
                label: const Text('Payable (vendors)'),
                selected: !_receivable,
                onSelected: (_) => setState(() {
                  _kind = 'payable';
                  _band = null;
                }),
              ),
            ]),
            const SizedBox(height: 12),
            ...async.when(
              loading: () => [const AppLoader()],
              error: (e, _) => [Text(friendlyErrorMessage(e), style: const TextStyle(color: AppTheme.error))],
              data: (r) => _content(r),
            ),
          ],
        ),
      ),
    );
  }

  List<Widget> _content(OutstandingReport r) {
    final q = _search.toLowerCase();
    final rows = [
      for (final p in r.rows)
        if ((_band == null || (p.buckets[_band] ?? 0) > 0) &&
            (q.isEmpty || p.name.toLowerCase().contains(q) || (p.sub ?? '').toLowerCase().contains(q)))
          p
    ];
    return [
      RegisterTotals(figures: [
        (_receivable ? 'Flats' : 'Vendors', '${r.parties}'),
        ('Bills', '${r.bills}'),
        ('Outstanding', formatInr(r.outstanding)),
        ('Overdue', formatInr(r.overdue)),
      ]),
      const SizedBox(height: 12),
      Wrap(spacing: 8, runSpacing: 8, children: [
        ChoiceChip(
            key: const Key('band-all'),
            label: const Text('All'),
            selected: _band == null,
            onSelected: (_) => setState(() => _band = null)),
        for (final (key, label) in r.bucketLabels)
          ChoiceChip(
            key: Key('band-$key'),
            label: Text('$label · ${formatInr(r.bucketTotals[key] ?? 0)}'),
            selected: _band == key,
            onSelected: (_) => setState(() => _band = key),
          ),
      ]),
      const SizedBox(height: 12),
      TextField(
        onChanged: (v) => setState(() => _search = v.trim()),
        decoration: InputDecoration(
            prefixIcon: const Icon(Icons.search_rounded),
            hintText: _receivable ? 'Search flat or member' : 'Search vendor'),
      ),
      const SizedBox(height: 14),
      if (rows.isEmpty)
        AppEmptyState(
          icon: Icons.task_alt_rounded,
          title: r.rows.isEmpty ? 'Nothing outstanding' : 'No match',
          subtitle: r.rows.isEmpty
              ? (_receivable ? 'No member has dues.' : 'No vendor bill is waiting to be paid.')
              : 'Try another band or search.',
        )
      else
        Material(
          color: AppTheme.cardBg,
          borderRadius: BorderRadius.circular(AppTheme.radiusM),
          clipBehavior: Clip.antiAlias,
          child: Column(children: [
            for (final (i, p) in rows.indexed) ...[
              if (i > 0) const Divider(height: 1),
              _PartyTile(party: p, labels: r.bucketLabels, band: _band),
            ],
          ]),
        ),
    ];
  }
}

class _PartyTile extends StatelessWidget {
  final OutstandingParty party;
  final List<(String, String)> labels;
  final String? band;
  const _PartyTile({required this.party, required this.labels, required this.band});

  @override
  Widget build(BuildContext context) {
    final isLate = party.daysOverdue > 0;
    final bills = [for (final b in party.bills) if (band == null || b.bucket == band) b];
    return Theme(
      data: Theme.of(context).copyWith(dividerColor: Colors.transparent),
      child: ExpansionTile(
        key: PageStorageKey('party-${party.key}'),
        tilePadding: const EdgeInsets.symmetric(horizontal: 14),
        childrenPadding: const EdgeInsets.fromLTRB(14, 0, 14, 12),
        title: Row(children: [
          Expanded(
            child: Text(party.name, style: const TextStyle(fontSize: 13.5, fontWeight: FontWeight.w700)),
          ),
          Text(formatInr(party.total), style: const TextStyle(fontSize: 13.5, fontWeight: FontWeight.w700)),
        ]),
        subtitle: Text(
          [
            if ((party.sub ?? '').isNotEmpty) party.sub!,
            '${party.bills.length} bill${party.bills.length == 1 ? '' : 's'}',
            isLate ? 'oldest ${party.daysOverdue} days overdue' : 'not yet due',
          ].join(' · '),
          style: TextStyle(fontSize: 12.5, color: isLate ? AppTheme.error : AppTheme.textSecondary),
        ),
        children: [
          Wrap(spacing: 14, runSpacing: 4, children: [
            for (final (key, label) in labels)
              if ((party.buckets[key] ?? 0) > 0)
                Text('$label: ${formatInr(party.buckets[key]!)}',
                    style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
          ]),
          const SizedBox(height: 8),
          for (final b in bills)
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 3),
              child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Expanded(
                  child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    Text('${b.ref}${(b.label ?? '').isEmpty ? '' : ' · ${b.label}'}',
                        style: const TextStyle(fontSize: 12.5, fontWeight: FontWeight.w600)),
                    Text(
                      'Due ${formatAccountsDate(b.dueDate)}${b.noDueDate ? ' (bill date)' : ''}'
                      '${b.daysOverdue > 0 ? ' · ${b.daysOverdue} days overdue' : ''}',
                      style: TextStyle(
                          fontSize: 12, color: b.daysOverdue > 0 ? AppTheme.error : AppTheme.textTertiary),
                    ),
                  ]),
                ),
                Text(formatInr(b.outstanding), style: const TextStyle(fontSize: 12.5, fontWeight: FontWeight.w600)),
              ]),
            ),
        ],
      ),
    );
  }
}
