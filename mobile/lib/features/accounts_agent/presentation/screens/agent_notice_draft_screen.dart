import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/theme/design_tokens.dart';
import 'package:ar_society_app/features/accounts/data/accounts_api.dart' show formatInr;
import 'package:ar_society_app/features/accounts_agent/presentation/widgets/agent_hud.dart';
import 'package:ar_society_app/features/accounts_agent/data/assist_api.dart';
import 'package:ar_society_app/features/accounts_agent/presentation/providers/legal_providers.dart';
import 'package:ar_society_app/features/accounts_agent/presentation/widgets/agent_widgets.dart';
import 'package:ar_society_app/shared/widgets/app_form.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';

const noticeKinds = {
  'AGM': 'AGM notice & agenda',
  'SGM': 'SGM notice & agenda',
  'COMMITTEE': 'Committee meeting agenda',
  'DUES': 'Dues reminders',
};

/// What the notice form sends.
Map<String, dynamic> noticeDraftPayload({
  required String kind,
  DateTime? meetingDate,
  String? time,
  String? venue,
  String? subject,
  String? resolutions,
  String? extraItems,
  bool onlyDefaulters = true,
  int payWithinDays = 15,
  required bool save,
}) {
  String? clean(String? s) => (s == null || s.trim().isEmpty) ? null : s.trim();
  List<String> lines(String? s) => [for (final l in (s ?? '').split('\n')) if (l.trim().isNotEmpty) l.trim()];
  if (kind == 'SGM' && clean(subject) == null) throw const FormatException('Give the subject of the meeting');
  return {
    'kind': kind,
    if (meetingDate != null)
      'meeting_date': '${meetingDate.year.toString().padLeft(4, '0')}-${meetingDate.month.toString().padLeft(2, '0')}-${meetingDate.day.toString().padLeft(2, '0')}',
    if (clean(time) != null) 'time': clean(time),
    if (clean(venue) != null) 'venue': clean(venue),
    if (clean(subject) != null) 'subject': clean(subject),
    if (lines(resolutions).isNotEmpty) 'resolutions': lines(resolutions),
    if (lines(extraItems).isNotEmpty) 'extra_items': lines(extraItems),
    if (kind == 'DUES') ...{'only_defaulters': onlyDefaulters, 'pay_within_days': payWithinDays},
    'save': save,
  };
}

/// Notices and agendas drafted by the Accounts Agent from the society's records and the bye-law clauses in the Legal
/// Library. "Save as draft notice" stores DRAFT notices only; you edit and publish them from Notices.
class AgentNoticeDraftScreen extends ConsumerStatefulWidget {
  const AgentNoticeDraftScreen({super.key});
  @override
  ConsumerState<AgentNoticeDraftScreen> createState() => _AgentNoticeDraftScreenState();
}

class _AgentNoticeDraftScreenState extends ConsumerState<AgentNoticeDraftScreen> {
  String _kind = 'AGM';
  DateTime? _date;
  final _time = TextEditingController();
  final _venue = TextEditingController();
  final _subject = TextEditingController();
  final _resolutions = TextEditingController();
  final _extra = TextEditingController();
  bool _onlyDefaulters = true;
  NoticeDraftResult? _result;
  bool _busy = false;

  @override
  void dispose() {
    for (final c in [_time, _venue, _subject, _resolutions, _extra]) {
      c.dispose();
    }
    super.dispose();
  }

  Future<void> _run({required bool save}) async {
    Map<String, dynamic> payload;
    try {
      payload = noticeDraftPayload(
        kind: _kind, meetingDate: _date, time: _time.text, venue: _venue.text, subject: _subject.text,
        resolutions: _resolutions.text, extraItems: _extra.text, onlyDefaulters: _onlyDefaulters, save: save,
      );
    } on FormatException catch (e) {
      showErrorToast(context, Exception(e.message));
      return;
    }
    setState(() => _busy = true);
    try {
      final r = await ref.read(assistApiProvider).draftNotice(payload);
      if (!mounted) return;
      setState(() => _result = r);
      if (save) AppToast.success(context, '${r.savedNoticeIds.length} draft notice(s) saved — publish them from Notices');
    } catch (e) {
      if (mounted) showErrorToast(context, e);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final meeting = _kind != 'DUES';
    final r = _result;
    return AppPage(
      title: 'Notices & agendas',
      subtitle: 'Drafts from your records and bye-laws — you edit and publish',
      maxWidth: 900,
      body: ListView(padding: const EdgeInsets.fromLTRB(16, 12, 16, 96), children: [
        AgentCard(
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Wrap(spacing: 8, runSpacing: 8, children: [
              for (final e in noticeKinds.entries)
                ChoiceChip(label: Text(e.value), selected: _kind == e.key, onSelected: (_) => setState(() {
                      _kind = e.key;
                      _result = null;
                    })),
            ]),
            const SizedBox(height: 12),
            if (meeting) ...[
              Wrap(spacing: 12, runSpacing: 12, crossAxisAlignment: WrapCrossAlignment.center, children: [
                OutlinedButton.icon(
                  onPressed: () async {
                    final now = DateTime.now();
                    final d = await showDatePicker(context: context, initialDate: _date ?? now, firstDate: now.subtract(const Duration(days: 30)), lastDate: DateTime(now.year + 1, 12, 31));
                    if (d != null) setState(() => _date = d);
                  },
                  icon: const Icon(Icons.event_outlined, size: 18),
                  label: Text(_date == null ? 'Meeting date' : day(_date!)),
                ),
                SizedBox(width: 160, child: TextField(controller: _time, decoration: const InputDecoration(labelText: 'Time'))),
                SizedBox(width: 280, child: TextField(controller: _venue, decoration: const InputDecoration(labelText: 'Venue'))),
              ]),
              if (_kind == 'SGM') ...[
                const SizedBox(height: 12),
                TextField(controller: _subject, decoration: const InputDecoration(labelText: 'Subject of the meeting')),
                const SizedBox(height: 12),
                TextField(controller: _resolutions, maxLines: 3, decoration: const InputDecoration(labelText: 'Resolutions to pass (one per line)')),
              ],
              const SizedBox(height: 12),
              TextField(controller: _extra, maxLines: 2, decoration: const InputDecoration(labelText: 'Other agenda items (one per line, optional)')),
            ] else
              SwitchListTile(
                contentPadding: EdgeInsets.zero,
                title: const Text('Only members beyond the defaulter period'),
                subtitle: const Text('Off: every flat with any amount outstanding'),
                value: _onlyDefaulters,
                onChanged: (v) => setState(() => _onlyDefaulters = v),
              ),
            const SizedBox(height: 16),
            Wrap(spacing: 10, runSpacing: 10, children: [
              OutlinedButton.icon(onPressed: _busy ? null : () => _run(save: false), icon: const Icon(Icons.preview_outlined), label: const Text('Generate draft')),
              FilledButton.icon(
                onPressed: _busy || r == null || r.savedNoticeIds.isNotEmpty ? null : () => _run(save: true),
                icon: const Icon(Icons.save_outlined),
                label: Text(_kind == 'DUES' ? 'Save as draft notices' : 'Save as draft notice'),
              ),
            ]),
          ]),
        ),
        if (r != null && r.content != null) ...[
          AgentSectionTitle(r.title),
          AgentCard(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              SelectableText(r.content!, style: const TextStyle(fontSize: 13.5, height: 1.45)),
              Align(
                alignment: Alignment.centerRight,
                child: TextButton.icon(
                  onPressed: () {
                    Clipboard.setData(ClipboardData(text: r.content!));
                    AppToast.success(context, 'Copied');
                  },
                  icon: const Icon(Icons.copy_rounded, size: 16),
                  label: const Text('Copy'),
                ),
              ),
            ]),
          ),
        ],
        if (r != null && r.dues.isNotEmpty) ...[
          AgentSectionTitle(r.title),
          for (final d in r.dues)
            Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: AgentCard(
                child: Theme(
                  data: Theme.of(context).copyWith(dividerColor: Colors.transparent),
                  child: ExpansionTile(
                    tilePadding: EdgeInsets.zero,
                    title: Text('${d['flat']}', style: const TextStyle(fontWeight: FontWeight.w700)),
                    subtitle: Text('${formatInr(double.tryParse('${d['outstanding']}') ?? 0)} outstanding'),
                    children: [Align(alignment: Alignment.centerLeft, child: SelectableText('${d['content']}', style: const TextStyle(fontSize: 13, height: 1.4)))],
                  ),
                ),
              ),
            ),
        ],
        if (r != null && r.bylawRefs.isNotEmpty) ...[
          const AgentSectionTitle('Bye-law clauses used'),
          for (final b in r.bylawRefs)
            Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: AgentCard(
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Wrap(spacing: 8, runSpacing: 6, children: [
                    Text('${b['source']} — clause ${b['clause_ref']}${b['page'] == null ? '' : ', page ${b['page']}'}', style: const TextStyle(fontWeight: FontWeight.w700)),
                    HudChip(label: b['society_specific'] == true ? 'Your bye-laws' : 'Model bye-laws', tone: b['society_specific'] == true ? AppTone.success : AppTone.info),
                  ]),
                  const SizedBox(height: 6),
                  Text('${b['text']}', style: const TextStyle(fontSize: 12.5, color: Hud.dim)),
                ]),
              ),
            ),
        ],
      ]),
    );
  }
}
