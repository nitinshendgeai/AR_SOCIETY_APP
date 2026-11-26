import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/l10n/app_locale.dart';
import 'package:ar_society_app/core/motion/loading.dart';
import 'package:ar_society_app/core/router/app_router.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/core/theme/design_tokens.dart';
import 'package:ar_society_app/features/gym/data/gym_api.dart';
import 'package:ar_society_app/shared/widgets/app_form.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';
import 'package:ar_society_app/shared/widgets/premium.dart';

/// How long someone has been inside: "42 min", "1 h 05 min".
String gymStay(int minutes) => minutes >= 60 ? '${minutes ~/ 60} h ${(minutes % 60).toString().padLeft(2, '0')} min' : '$minutes min';

/// The Gym Trainer's desk: how many are inside now and how many came and left today, who is inside with a Check out
/// button, and the way to tick a flat's members in and to the weekly and monthly report.
class GymDeskScreen extends ConsumerStatefulWidget {
  const GymDeskScreen({super.key});

  @override
  ConsumerState<GymDeskScreen> createState() => _GymDeskScreenState();
}

class _GymDeskScreenState extends ConsumerState<GymDeskScreen> {
  bool _busy = false;

  Future<void> _run(Future<int> Function() action, String Function(int n) done) async {
    if (_busy) return;
    setState(() => _busy = true);
    try {
      final n = await action();
      ref.invalidate(gymLiveProvider);
      if (mounted) AppToast.success(context, done(n));
    } catch (e) {
      if (mounted) showErrorToast(context, e);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _checkOutAll(GymLive live) async {
    final everyone = live.insideNow + live.earlierOpen.length;
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(ctx.tr('Check everyone out?')),
        content: Text(ctx.trf('{n} still in the gym will be ticked out now.', {'n': everyone})),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: Text(ctx.tr('Cancel'))),
          FilledButton(onPressed: () => Navigator.pop(ctx, true), child: Text(ctx.tr('Check everyone out'))),
        ],
      ),
    );
    if (ok == true) {
      await _run(() => ref.read(gymApiProvider).checkOutAll(), (n) => context.trf('{n} checked out', {'n': n}));
    }
  }

  @override
  Widget build(BuildContext context) {
    final live = ref.watch(gymLiveProvider);
    return AppPage(
      title: 'Gym attendance',
      body: RefreshIndicator(
        onRefresh: () async => ref.invalidate(gymLiveProvider),
        child: live.when(
          loading: () => const SkeletonList(),
          error: (e, _) => AppErrorState(message: friendlyErrorMessage(e), onRetry: () => ref.invalidate(gymLiveProvider)),
          data: _content,
        ),
      ),
    );
  }

  Widget _content(GymLive live) {
    return ListView(
      physics: const AlwaysScrollableScrollPhysics(),
      padding: const EdgeInsets.fromLTRB(16, 8, 16, 32),
      children: [
        Row(children: [
          Expanded(child: _Stat(key: const Key('gym-inside'), label: 'Inside now', value: live.insideNow, tone: AppTone.warning)),
          const SizedBox(width: 10),
          Expanded(child: _Stat(key: const Key('gym-came'), label: 'Came today', value: live.checkedInToday, tone: AppTone.success)),
          const SizedBox(width: 10),
          Expanded(child: _Stat(key: const Key('gym-left'), label: 'Left today', value: live.checkedOutToday, tone: AppTone.info)),
        ]),
        const SizedBox(height: 14),
        SizedBox(
          height: 56,
          child: FilledButton.icon(
            key: const Key('gym-check-in'),
            onPressed: () => context.push(AppRoutes.gymCheckIn),
            icon: const Icon(Icons.how_to_reg_rounded),
            label: Text(context.tr('Check in members')),
          ),
        ),
        const SizedBox(height: 10),
        SizedBox(
          height: 48,
          child: OutlinedButton.icon(
            key: const Key('gym-reports'),
            onPressed: () => context.push(AppRoutes.gymReport),
            icon: const Icon(Icons.bar_chart_rounded),
            label: Text(context.tr('Weekly and monthly report')),
          ),
        ),
        const SizedBox(height: 22),
        Row(children: [
          Expanded(child: SectionHeading(context.tr('Inside now'))),
          if (live.insideNow + live.earlierOpen.length > 0)
            TextButton(
              key: const Key('gym-check-out-all'),
              onPressed: _busy ? null : () => _checkOutAll(live),
              child: Text(context.tr('Check everyone out')),
            ),
        ]),
        const SizedBox(height: 10),
        if (live.inside.isEmpty)
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 12),
            child: Text(context.tr('Nobody is in the gym.'), style: TextStyle(color: AppTheme.textSecondary)),
          )
        else
          for (final v in live.inside)
            _VisitTile(
              visit: v,
              busy: _busy,
              action: 'Tick out',
              onAction: () => _run(() => ref.read(gymApiProvider).checkOut([v.visitId]), (_) => context.trf('{name} checked out', {'name': v.name})),
            ),
        if (live.earlierOpen.isNotEmpty) ...[
          const SizedBox(height: 18),
          SectionHeading(context.tr('Not ticked out on an earlier day')),
          const SizedBox(height: 4),
          Text(context.tr('These were ticked in on an earlier day and never ticked out. Close them so they do not stay open.'),
              style: TextStyle(fontSize: 12.5, color: AppTheme.textSecondary)),
          const SizedBox(height: 10),
          for (final v in live.earlierOpen)
            _VisitTile(
              visit: v,
              busy: _busy,
              earlier: true,
              action: 'Close',
              onAction: () => _run(() => ref.read(gymApiProvider).checkOut([v.visitId]), (_) => context.trf('{name} closed', {'name': v.name})),
            ),
        ],
      ],
    );
  }
}

class _Stat extends StatelessWidget {
  final String label;
  final int value;
  final AppTone tone;
  const _Stat({super.key, required this.label, required this.value, required this.tone});

  @override
  Widget build(BuildContext context) {
    final colors = kToneColors[tone]!;
    return Semantics(
      label: '${context.tr(label)}: $value',
      excludeSemantics: true,
      child: PremiumSurface(
        padding: const EdgeInsets.fromLTRB(12, 12, 12, 12),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text('$value',
              style: TextStyle(fontSize: 30, fontWeight: FontWeight.w800, color: colors.foreground, fontFeatures: const [FontFeature.tabularFigures()])),
          const SizedBox(height: 2),
          Text(context.tr(label), maxLines: 2, overflow: TextOverflow.ellipsis, style: TextStyle(fontSize: 12.5, color: AppTheme.textSecondary)),
        ]),
      ),
    );
  }
}

class _VisitTile extends StatelessWidget {
  final GymVisitRow visit;
  final bool busy;
  final bool earlier;
  final String action;
  final VoidCallback onAction;
  const _VisitTile({required this.visit, required this.busy, required this.action, required this.onAction, this.earlier = false});

  @override
  Widget build(BuildContext context) {
    final at = visit.checkedInAt;
    final since = at == null ? '' : (earlier ? DateFormat('d MMM, h:mm a').format(at) : DateFormat('h:mm a').format(at));
    final stay = !earlier && visit.minutesInside != null ? ' · ${gymStay(visit.minutesInside!)}' : '';
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: PremiumSurface(
        padding: const EdgeInsets.fromLTRB(14, 10, 10, 10),
        child: Row(children: [
          AccentBadge(icon: Icons.fitness_center_rounded, accent: accentFor(visit.name), size: 40),
          const SizedBox(width: 12),
          Expanded(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text(visit.name, maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontWeight: FontWeight.w700)),
              Text('${visit.flatLabel} · ${context.tr(earlier ? 'In' : 'Since')} $since$stay',
                  maxLines: 2, overflow: TextOverflow.ellipsis, style: TextStyle(fontSize: 12.5, color: AppTheme.textSecondary)),
            ]),
          ),
          const SizedBox(width: 8),
          SizedBox(
            height: 44,
            child: FilledButton.tonal(
              key: Key('gym-out-${visit.visitId}'),
              onPressed: busy ? null : onAction,
              style: FilledButton.styleFrom(minimumSize: const Size(64, 44), padding: const EdgeInsets.symmetric(horizontal: 14)),
              child: Text(context.tr(action)),
            ),
          ),
        ]),
      ),
    );
  }
}
