import 'package:flutter/material.dart';
import 'package:ar_society_app/core/motion/loading.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/layout/app_sheet.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/platform/data/platform_api.dart';
import 'package:ar_society_app/features/platform/presentation/providers/platform_providers.dart';
import 'package:ar_society_app/features/platform/presentation/screens/platform_console_screen.dart' show EventTile;
import 'package:ar_society_app/features/platform/presentation/screens/platform_sheets.dart';
import 'package:ar_society_app/shared/widgets/app_data_table.dart' show StatusPill;
import 'package:ar_society_app/shared/widgets/app_widgets.dart';
import 'package:ar_society_app/shared/widgets/app_form.dart';

/// One society as the platform sees it.
class PlatformSocietyScreen extends ConsumerWidget {
  final String societyId;
  const PlatformSocietyScreen({super.key, required this.societyId});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final async = ref.watch(platformSocietyProvider(societyId));
    return AppPage(
      title: async.valueOrNull?.name ?? 'Society',
      body: RefreshIndicator(
        onRefresh: () async => invalidatePlatform(ref),
        child: async.when(
          loading: () => const AppLoader(),
          error: (e, _) => ListView(padding: const EdgeInsets.all(20), children: [AppErrorBanner(message: friendlyErrorMessage(e))]),
          data: (s) => ResponsiveBody(
            maxWidth: 760,
            child: ListView(padding: const EdgeInsets.fromLTRB(16, 16, 16, 40), children: [
              Row(children: [
                StatusPill(statusLabel(s.status), statusColor(s.status)),
                if (s.trialEnded && s.status == 'TRIAL') const Padding(padding: EdgeInsets.only(left: 8), child: StatusPill('Trial ended', AppTheme.warning)),
                const SizedBox(width: 10),
                Expanded(child: Text(s.standing, style: const TextStyle(fontWeight: FontWeight.w600))),
              ]),
              const SizedBox(height: 4),
              Text([if ((s.code ?? '').isNotEmpty) s.code!, if ((s.city ?? '').isNotEmpty) s.city!, if (s.createdAt != null) 'Joined ${dayText(s.createdAt)}'].join(' · '), style: const TextStyle(color: AppTheme.textSecondary)),
              const SizedBox(height: 14),
              _Actions(society: s),
              const SizedBox(height: 18),
              _section('Use'),
              _Usage(label: 'People', used: s.users, allowed: s.allowedUsers),
              _Usage(label: 'Flats', used: s.flats, allowed: s.allowedFlats),
              Text('${s.wings} wing${s.wings == 1 ? '' : 's'} · setup ${s.setupPct}% done · last sign-in ${ago(s.lastLogin)}', style: const TextStyle(color: AppTheme.textSecondary, fontSize: 12.5)),
              const SizedBox(height: 18),
              _section('Who runs it'),
              if (s.admins.isEmpty) const Text('No society admin yet.', style: TextStyle(color: AppTheme.textSecondary)),
              for (final a in s.admins)
                ListTile(
                  dense: true,
                  contentPadding: EdgeInsets.zero,
                  leading: const Icon(Icons.admin_panel_settings_outlined, size: 20),
                  title: Text(a.name),
                  subtitle: Text([if ((a.email ?? '').isNotEmpty) a.email!, if ((a.phone ?? '').isNotEmpty) a.phone!, 'last sign-in ${ago(a.lastLogin)}'].join(' · ')),
                ),
              if ((s.contactName ?? '').isNotEmpty || (s.contactEmail ?? '').isNotEmpty || (s.contactPhone ?? '').isNotEmpty) ...[
                const SizedBox(height: 6),
                Text('Contact on file: ${[if ((s.contactName ?? '').isNotEmpty) s.contactName!, if ((s.contactEmail ?? '').isNotEmpty) s.contactEmail!, if ((s.contactPhone ?? '').isNotEmpty) s.contactPhone!].join(' · ')}', style: const TextStyle(color: AppTheme.textSecondary, fontSize: 12.5)),
              ],
              const SizedBox(height: 18),
              _section('What has been done'),
              if (s.history.isEmpty) const Text('Nothing yet.', style: TextStyle(color: AppTheme.textSecondary)),
              for (final e in s.history) EventTile(event: e),
            ]),
          ),
        ),
      ),
    );
  }

  Widget _section(String t) => Padding(padding: const EdgeInsets.only(bottom: 8), child: Text(t, style: const TextStyle(fontWeight: FontWeight.w800, fontSize: 15)));
}

class _Usage extends StatelessWidget {
  final String label;
  final int used;
  final int allowed;
  const _Usage({required this.label, required this.used, required this.allowed});

  @override
  Widget build(BuildContext context) {
    final over = allowed > 0 && used > allowed;
    final share = allowed == 0 ? 0.0 : (used / allowed).clamp(0.0, 1.0);
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [Expanded(child: Text(label)), Text('$used of $allowed', style: TextStyle(fontWeight: FontWeight.w600, color: over ? AppTheme.error : null))]),
        const SizedBox(height: 4),
        ClipRRect(borderRadius: BorderRadius.circular(4), child: LinearProgressIndicator(value: share, minHeight: 8, color: over ? AppTheme.error : (share > 0.85 ? AppTheme.warning : AppTheme.primary), backgroundColor: AppTheme.border)),
      ]),
    );
  }
}

class _Actions extends ConsumerWidget {
  final PlatformSociety society;
  const _Actions({required this.society});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final s = society;
    final canExtend = s.status == 'TRIAL' || s.status == 'EXPIRED';
    final canActivate = s.status == 'TRIAL' || s.status == 'EXPIRED' || s.status == 'SUSPENDED';
    final canSuspend = s.status != 'SUSPENDED' && s.status != 'CANCELLED';
    void open(Widget sheet) => showAppSheet(context: context, builder: (_) => sheet);
    return Wrap(spacing: 10, runSpacing: 10, children: [
      if (canExtend) OutlinedButton.icon(onPressed: () => open(ExtendTrialSheet(society: s)), icon: const Icon(Icons.update_rounded, size: 18), label: const Text('Extend trial')),
      if (canActivate) FilledButton.icon(onPressed: () => open(ActivateSheet(society: s)), icon: Icon(s.suspended ? Icons.lock_open_rounded : Icons.verified_rounded, size: 18), label: Text(s.suspended ? 'Let them back in' : 'Put on a paid plan')),
      OutlinedButton.icon(onPressed: () => open(LimitsSheet(society: s)), icon: const Icon(Icons.tune_rounded, size: 18), label: const Text('Limits')),
      if (canSuspend)
        OutlinedButton.icon(
          style: OutlinedButton.styleFrom(foregroundColor: AppTheme.error),
          onPressed: () => open(SuspendSheet(society: s)),
          icon: const Icon(Icons.block_rounded, size: 18),
          label: const Text('Suspend'),
        ),
    ]);
  }
}
