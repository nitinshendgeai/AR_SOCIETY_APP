import 'package:flutter/material.dart';
import 'package:ar_society_app/core/motion/loading.dart';
import 'package:ar_society_app/core/l10n/app_locale.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';
import 'package:ar_society_app/core/layout/app_sheet.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/features/governance/data/governance_api.dart';
import 'package:ar_society_app/features/maintenance_billing/presentation/widgets/billing_sheet_frame.dart';
import 'package:ar_society_app/features/vendor/presentation/widgets/procurement_widgets.dart'
    show DateField;
import 'package:ar_society_app/shared/widgets/app_data_table.dart'
    show StatusPill;
import 'package:ar_society_app/shared/widgets/app_widgets.dart';

/// Polls the committee puts to the society. One vote per flat; totals only, never who voted what.
class PollsScreen extends ConsumerWidget {
  const PollsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final user = ref.watch(currentUserProvider);
    final sid = user?.societyId ?? '';
    final office = user?.isAdminOrCommittee == true;
    final async = ref.watch(pollsProvider(sid));
    return Scaffold(
      backgroundColor: AppTheme.surface,
      appBar: AppBar(title: Text(context.tr('Polls'))),
      floatingActionButton: office
          ? FloatingActionButton.extended(
              onPressed: () => showAppSheet(
                  context: context, builder: (_) => const _NewPollSheet()),
              icon: const Icon(Icons.add_rounded),
              label: Text(context.tr('New poll')))
          : null,
      body: async.when(
        loading: () => const SkeletonList(),
        error: (e, _) => Center(
            child: OutlinedButton(
                onPressed: () => ref.invalidate(pollsProvider(sid)),
                child: const Text('Could not load. Try again'))),
        data: (polls) => polls.isEmpty
            ? AppEmptyState(
                icon: Icons.how_to_vote_rounded,
                title: 'No polls yet',
                subtitle: office
                    ? 'Put a question to the society.'
                    : 'Polls from the committee will appear here.')
            : RefreshIndicator(
                onRefresh: () async => ref.invalidate(pollsProvider(sid)),
                child: ListView(
                    padding: const EdgeInsets.fromLTRB(16, 12, 16, 96),
                    children: [
                      for (final p in polls) _PollCard(poll: p, office: office),
                    ]),
              ),
      ),
    );
  }
}

class _PollCard extends ConsumerStatefulWidget {
  final Poll poll;
  final bool office;
  const _PollCard({required this.poll, required this.office});
  @override
  ConsumerState<_PollCard> createState() => _PollCardState();
}

class _PollCardState extends ConsumerState<_PollCard> {
  String? _choice;
  bool _busy = false;

  Future<void> _vote() async {
    setState(() => _busy = true);
    try {
      await ref.read(governanceApiProvider).vote(widget.poll.id, _choice!);
      ref.invalidate(
          pollsProvider(ref.read(currentUserProvider)?.societyId ?? ''));
      if (mounted) AppToast.success(context, 'Your flat\'s vote is recorded');
    } catch (e) {
      if (mounted) showErrorToast(context, e);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _close() async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Close this poll now?'),
        content: const Text(
            'No more votes are accepted and everyone sees the results.'),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(ctx, false),
              child: const Text('Keep it open')),
          FilledButton(
              onPressed: () => Navigator.pop(ctx, true),
              child: const Text('Close poll')),
        ],
      ),
    );
    if (ok != true) return;
    try {
      await ref.read(governanceApiProvider).closePoll(widget.poll.id);
      ref.invalidate(
          pollsProvider(ref.read(currentUserProvider)?.societyId ?? ''));
    } catch (e) {
      if (mounted) showErrorToast(context, e);
    }
  }

  @override
  Widget build(BuildContext context) {
    final p = widget.poll;
    final total = p.options.fold<int>(0, (s, o) => s + (o.votes ?? 0));
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: DecoratedBox(
        decoration: BoxDecoration(
            color: AppTheme.cardBg,
            borderRadius: BorderRadius.circular(AppTheme.radiusL),
            boxShadow: AppTheme.cardShadow),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child:
              Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Row(children: [
              Expanded(
                  child: Text(p.question,
                      style: const TextStyle(
                          fontSize: 15.5,
                          fontWeight: FontWeight.w700,
                          color: AppTheme.textPrimary))),
              const SizedBox(width: 8),
              p.open
                  ? StatusPill(context.tr('Open'), AppTheme.success)
                  : StatusPill(context.tr('Closed'), AppTheme.textSecondary),
            ]),
            if ((p.description ?? '').isNotEmpty) ...[
              const SizedBox(height: 4),
              Text(p.description!,
                  style: const TextStyle(
                      fontSize: 13,
                      color: AppTheme.textSecondary,
                      height: 1.4)),
            ],
            const SizedBox(height: 12),
            if (p.canVote)
              RadioGroup<String>(
                groupValue: _choice,
                onChanged: (v) => setState(() => _choice = v),
                child: Material(
                  type: MaterialType.transparency,
                  child: Column(children: [
                    for (final o in p.options)
                      RadioListTile<String>(
                          contentPadding: EdgeInsets.zero,
                          dense: true,
                          value: o.id,
                          title: Text(o.label)),
                  ]),
                ),
              )
            else
              for (final o in p.options)
                _ResultRow(
                    option: o,
                    total: total,
                    mine: p.myOptionId == o.id,
                    visible: p.resultsVisible),
            const SizedBox(height: 6),
            Text(
              '${p.votes} of ${p.flats} flats voted · '
              '${p.open ? 'closes ${DateFormat('d MMM').format(p.closesOn)}' : 'closed'}'
              '${!p.resultsVisible ? '\nResults show ${p.resultsAfter == 'close' ? 'when the poll closes' : 'after you vote'}.' : ''}',
              style: const TextStyle(
                  fontSize: 12.5, color: AppTheme.textSecondary, height: 1.4),
            ),
            if (p.canVote) ...[
              const SizedBox(height: 10),
              AppPrimaryButton(
                  label: context.tr('Vote'),
                  isLoading: _busy,
                  onPressed: _choice == null ? null : _vote),
            ],
            if (widget.office && p.open)
              Align(
                  alignment: Alignment.centerRight,
                  child: TextButton(
                      onPressed: _close, child: Text(context.tr('Close now')))),
          ]),
        ),
      ),
    );
  }
}

class _ResultRow extends StatelessWidget {
  final PollOptionView option;
  final int total;
  final bool mine, visible;
  const _ResultRow(
      {required this.option,
      required this.total,
      required this.mine,
      required this.visible});

  @override
  Widget build(BuildContext context) {
    final v = option.votes;
    final fraction = (!visible || v == null || total == 0) ? 0.0 : v / total;
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Expanded(
              child: Text('${option.label}${mine ? '  ✓ your vote' : ''}',
                  style: TextStyle(
                      fontSize: 13.5,
                      fontWeight: mine ? FontWeight.w700 : FontWeight.w500))),
          if (visible && v != null)
            Text('$v (${(fraction * 100).round()}%)',
                style:
                    const TextStyle(fontSize: 13, fontWeight: FontWeight.w600)),
        ]),
        const SizedBox(height: 4),
        ClipRRect(
          borderRadius: BorderRadius.circular(4),
          child: LinearProgressIndicator(
              value: fraction,
              minHeight: 7,
              backgroundColor: AppTheme.border,
              color: mine ? AppTheme.success : AppTheme.primary),
        ),
      ]),
    );
  }
}

class _NewPollSheet extends ConsumerStatefulWidget {
  const _NewPollSheet();
  @override
  ConsumerState<_NewPollSheet> createState() => _NewPollSheetState();
}

class _NewPollSheetState extends ConsumerState<_NewPollSheet> {
  final _form = GlobalKey<FormState>();
  final _question = TextEditingController();
  final _description = TextEditingController();
  final List<TextEditingController> _options = [
    TextEditingController(text: 'Yes'),
    TextEditingController(text: 'No')
  ];
  DateTime? _closes;
  String _results = 'vote';
  bool _saving = false;

  @override
  void dispose() {
    _question.dispose();
    _description.dispose();
    for (final o in _options) {
      o.dispose();
    }
    super.dispose();
  }

  Future<void> _save() async {
    if (!_form.currentState!.validate()) return;
    final labels = [
      for (final o in _options)
        if (o.text.trim().isNotEmpty) o.text.trim()
    ];
    if (labels.length < 2) {
      AppToast.error(context, 'Give at least two options');
      return;
    }
    setState(() => _saving = true);
    try {
      final sid = ref.read(currentUserProvider)?.societyId ?? '';
      await ref.read(governanceApiProvider).createPoll(sid, {
        'question': _question.text.trim(),
        if (_description.text.trim().isNotEmpty)
          'description': _description.text.trim(),
        'options': labels,
        'closes_on': apiDay(_closes!),
        'results_after': _results,
      });
      ref.invalidate(pollsProvider(sid));
      if (mounted) {
        AppToast.success(context, 'Poll started and residents told');
        Navigator.pop(context);
      }
    } catch (e) {
      if (mounted) {
        setState(() => _saving = false);
        showErrorToast(context, e);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return BillingSheetFrame(
      title: context.tr('New poll'),
      child: Form(
        key: _form,
        child:
            Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          TextFormField(
              controller: _question,
              decoration: const InputDecoration(labelText: 'Question *'),
              validator: (v) =>
                  (v ?? '').trim().length < 3 ? 'Enter the question' : null),
          const SizedBox(height: 12),
          TextFormField(
              controller: _description,
              minLines: 2,
              maxLines: 5,
              decoration: const InputDecoration(labelText: 'More detail')),
          const SizedBox(height: 14),
          const Text('Options',
              style: TextStyle(
                  fontSize: 13,
                  fontWeight: FontWeight.w700,
                  color: AppTheme.primary)),
          for (var i = 0; i < _options.length; i++)
            Padding(
              padding: const EdgeInsets.only(top: 8),
              child: Row(children: [
                Expanded(
                    child: TextField(
                        controller: _options[i],
                        decoration:
                            InputDecoration(labelText: 'Option ${i + 1}'))),
                if (_options.length > 2)
                  IconButton(
                      onPressed: () => setState(() => _options.removeAt(i)),
                      icon: const Icon(Icons.close_rounded, size: 20)),
              ]),
            ),
          if (_options.length < 10)
            Align(
              alignment: Alignment.centerLeft,
              child: TextButton.icon(
                  onPressed: () =>
                      setState(() => _options.add(TextEditingController())),
                  icon: const Icon(Icons.add_rounded),
                  label: const Text('Add an option')),
            ),
          const SizedBox(height: 6),
          DateField(
              label: 'Voting closes on',
              required: true,
              value: _closes,
              lastDate: DateTime.now().add(const Duration(days: 365)),
              onChanged: (d) => setState(() => _closes = d)),
          const SizedBox(height: 12),
          DropdownButtonFormField<String>(
            initialValue: _results,
            decoration: const InputDecoration(labelText: 'Show results'),
            items: const [
              DropdownMenuItem(
                  value: 'vote', child: Text('After a flat has voted')),
              DropdownMenuItem(
                  value: 'close', child: Text('Only when the poll closes')),
            ],
            onChanged: (v) => setState(() => _results = v ?? 'vote'),
          ),
          const SizedBox(height: 16),
          AppPrimaryButton(
              label: 'Start poll', isLoading: _saving, onPressed: _save),
        ]),
      ),
    );
  }
}
