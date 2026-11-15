import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/l10n/app_locale.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/accounts/presentation/widgets/accounts_widgets.dart' show PdfMenuButton;
import 'package:ar_society_app/features/gym/data/gym_api.dart';
import 'package:ar_society_app/features/gym/presentation/screens/gym_desk_screen.dart' show gymStay;
import 'package:ar_society_app/shared/widgets/app_form.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';
import 'package:ar_society_app/shared/widgets/premium.dart';

/// The gym's attendance for a week (Monday to Sunday) or a calendar month: visits, different members, the average stay,
/// day by day, and each member's visits. Can be printed (a PDF from the server).
class GymReportScreen extends ConsumerStatefulWidget {
  const GymReportScreen({super.key});

  @override
  ConsumerState<GymReportScreen> createState() => _GymReportScreenState();
}

class _GymReportScreenState extends ConsumerState<GymReportScreen> {
  String _period = 'week';
  DateTime _on = DateTime.now();
  Future<GymReport>? _load;

  @override
  void initState() {
    super.initState();
    _reload();
  }

  void _reload() => _load = ref.read(gymApiProvider).report(_period, on: _on);

  /// The same kind of period before (-1) or after (+1) this one.
  void _step(int direction) {
    setState(() {
      _on = _period == 'week'
          ? _on.add(Duration(days: 7 * direction))
          : DateTime(_on.year, _on.month + direction, 1);
      _reload();
    });
  }

  bool _isCurrent(GymReport r) {
    final today = DateTime.now();
    return !r.to.isBefore(DateTime(today.year, today.month, today.day));
  }

  @override
  Widget build(BuildContext context) {
    return AppPage(
      title: 'Gym report',
      body: FutureBuilder<GymReport>(
        future: _load,
        builder: (context, snap) {
          return ListView(
            padding: const EdgeInsets.fromLTRB(16, 8, 16, 32),
            children: [
              SegmentedButton<String>(
                key: const Key('gym-period'),
                segments: [
                  ButtonSegment(value: 'week', label: Text(context.tr('Weekly'))),
                  ButtonSegment(value: 'month', label: Text(context.tr('Monthly'))),
                ],
                selected: {_period},
                onSelectionChanged: (s) => setState(() {
                  _period = s.first;
                  _on = DateTime.now();
                  _reload();
                }),
              ),
              const SizedBox(height: 12),
              if (snap.connectionState != ConnectionState.done)
                const Padding(padding: EdgeInsets.only(top: 40), child: Center(child: CircularProgressIndicator()))
              else if (snap.hasError)
                AppErrorState(
                    message: friendlyErrorMessage(snap.error!), onRetry: () => setState(_reload), compact: true)
              else
                ..._report(snap.data!),
            ],
          );
        },
      ),
    );
  }

  List<Widget> _report(GymReport r) {
    final maxVisits = r.days.fold<int>(0, (m, d) => d.visits > m ? d.visits : m);
    return [
      Row(children: [
        IconButton(key: const Key('gym-prev'), tooltip: context.tr('Previous'), onPressed: () => _step(-1), icon: const Icon(Icons.chevron_left_rounded)),
        Expanded(
          child: Text(r.label, key: const Key('gym-period-label'), textAlign: TextAlign.center, style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w700)),
        ),
        IconButton(
            key: const Key('gym-next'),
            tooltip: context.tr('Next'),
            onPressed: _isCurrent(r) ? null : () => _step(1),
            icon: const Icon(Icons.chevron_right_rounded)),
      ]),
      const SizedBox(height: 8),
      Row(children: [
        Expanded(child: _Figure(label: 'Visits', value: '${r.visits}')),
        const SizedBox(width: 10),
        Expanded(child: _Figure(label: 'Members', value: '${r.uniqueMembers}')),
        const SizedBox(width: 10),
        Expanded(child: _Figure(label: 'Average stay', value: r.averageMinutes == null ? '—' : gymStay(r.averageMinutes!))),
      ]),
      const SizedBox(height: 14),
      PdfMenuButton(
        load: () => ref.read(gymApiProvider).reportPdf(_period, on: _on),
        fileName: 'Gym-$_period-${DateFormat('yyyy-MM-dd').format(r.from)}.pdf',
        subject: 'Gym attendance report',
        label: context.tr('Print report'),
        icon: Icons.print_rounded,
      ),
      if (r.notCheckedOut > 0) ...[
        const SizedBox(height: 10),
        Text(context.trf('{n} visits were not ticked out. They count as visits but not as time in the gym.', {'n': r.notCheckedOut}),
            key: const Key('gym-not-out-note'), style: const TextStyle(fontSize: 12.5, color: AppTheme.textSecondary)),
      ],
      const SizedBox(height: 20),
      SectionHeading(context.tr('Day by day')),
      const SizedBox(height: 10),
      for (final d in r.days) _DayRow(day: d, max: maxVisits),
      const SizedBox(height: 20),
      SectionHeading(context.tr('Members')),
      const SizedBox(height: 10),
      if (r.members.isEmpty)
        Text(context.tr('Nobody used the gym in this period.'), key: const Key('gym-empty'), style: const TextStyle(color: AppTheme.textSecondary))
      else
        for (final m in r.members) _MemberRow(member: m),
    ];
  }
}

class _Figure extends StatelessWidget {
  final String label;
  final String value;
  const _Figure({required this.label, required this.value});

  @override
  Widget build(BuildContext context) => PremiumSurface(
        padding: const EdgeInsets.all(12),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          FittedBox(
            fit: BoxFit.scaleDown,
            alignment: Alignment.centerLeft,
            child: Text(value, style: const TextStyle(fontSize: 22, fontWeight: FontWeight.w800, fontFeatures: [FontFeature.tabularFigures()])),
          ),
          const SizedBox(height: 2),
          Text(context.tr(label), maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
        ]),
      );
}

class _DayRow extends StatelessWidget {
  final GymDay day;
  final int max;
  const _DayRow({required this.day, required this.max});

  @override
  Widget build(BuildContext context) {
    final share = max == 0 ? 0.0 : day.visits / max;
    return Padding(
      padding: const EdgeInsets.only(bottom: 6),
      child: Row(children: [
        SizedBox(width: 74, child: Text(DateFormat('EEE d MMM').format(day.date), style: const TextStyle(fontSize: 12.5, color: AppTheme.textSecondary))),
        Expanded(
          child: ClipRRect(
            borderRadius: BorderRadius.circular(6),
            child: LinearProgressIndicator(value: share, minHeight: 12, backgroundColor: AppTheme.primarySoft, color: AppTheme.primary),
          ),
        ),
        SizedBox(width: 34, child: Text('${day.visits}', textAlign: TextAlign.right, style: const TextStyle(fontWeight: FontWeight.w700))),
      ]),
    );
  }
}

class _MemberRow extends StatelessWidget {
  final GymReportMember member;
  const _MemberRow({required this.member});

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.only(bottom: 8),
        child: PremiumSurface(
          padding: const EdgeInsets.all(12),
          child: Row(children: [
            AccentBadge(icon: Icons.person_rounded, accent: accentFor(member.name), size: 36),
            const SizedBox(width: 12),
            Expanded(
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text(member.name, maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontWeight: FontWeight.w700)),
                Text(member.flatLabel, style: const TextStyle(fontSize: 12.5, color: AppTheme.textSecondary)),
              ]),
            ),
            Column(crossAxisAlignment: CrossAxisAlignment.end, children: [
              Text(context.trf(member.visits == 1 ? '{n} visit' : '{n} visits', {'n': member.visits}), style: const TextStyle(fontWeight: FontWeight.w700)),
              if (member.totalMinutes > 0)
                Text(gymStay(member.totalMinutes), style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
            ]),
          ]),
        ),
      );
}
