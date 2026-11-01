import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/motion/loading.dart';
import 'package:ar_society_app/core/router/app_router.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/resident_master/presentation/providers/resident_master_providers.dart';
import 'package:ar_society_app/shared/utils/csv_file.dart';
import 'package:ar_society_app/shared/widgets/app_data_table.dart' show StatusPill;
import 'package:ar_society_app/shared/widgets/app_form.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';

/// One resident of the "Residents without a login" report.
class ResidentLoginRow {
  final String id, fullName, residentType, flatLabel, status;
  final String? phone, loginName, loginPhone;
  const ResidentLoginRow({
    required this.id,
    required this.fullName,
    required this.residentType,
    required this.flatLabel,
    required this.status,
    this.phone,
    this.loginName,
    this.loginPhone,
  });

  factory ResidentLoginRow.fromJson(Map<String, dynamic> j) {
    final login = j['login'] as Map<String, dynamic>?;
    return ResidentLoginRow(
      id: j['id'] as String,
      fullName: j['full_name'] as String,
      residentType: j['resident_type'] as String? ?? '',
      flatLabel: j['flat_label'] as String? ?? '',
      status: j['status'] as String,
      phone: j['phone'] as String?,
      loginName: login?['name'] as String?,
      loginPhone: login?['phone'] as String?,
    );
  }
}

class ResidentLoginReport {
  final Map<String, int> summary;
  final List<ResidentLoginRow> residents;
  const ResidentLoginReport(this.summary, this.residents);
  int count(String key) => summary[key] ?? 0;
}

/// Statuses in the order the report lists them, with what they say and what to do about each.
const _statusInfo = <String, (String, String, Color)>{
  'login_unlinked': ('Login exists, not linked', 'Open the resident and link the login', AppTheme.warning),
  'no_login': ('No login yet', 'Has a mobile number: a login can be made for it', AppTheme.error),
  'no_mobile': ('No mobile number', 'Add a mobile number to the resident', AppTheme.error),
  'login_disabled': ('Login disabled', 'The linked login is switched off: enable it under Users', AppTheme.error),
  'linked': ('Can sign in', '', AppTheme.success),
};

final residentLoginReportProvider = FutureProvider.autoDispose<ResidentLoginReport>((ref) async {
  final r = await ApiClient.instance.get('/residents/login-status');
  final data = Map<String, dynamic>.from(r.data as Map);
  return ResidentLoginReport(
    {for (final e in (data['summary'] as Map).entries) '${e.key}': (e.value as num).toInt()},
    [for (final x in data['residents'] as List) ResidentLoginRow.fromJson(Map<String, dynamic>.from(x as Map))],
  );
});

/// Which residents can sign in to the app and which cannot, and why. Tap a resident to fix it.
class ResidentLoginStatusScreen extends ConsumerStatefulWidget {
  const ResidentLoginStatusScreen({super.key});

  @override
  ConsumerState<ResidentLoginStatusScreen> createState() => _ResidentLoginStatusScreenState();
}

class _ResidentLoginStatusScreenState extends ConsumerState<ResidentLoginStatusScreen> {
  /// 'attention' (everyone who cannot sign in), 'all', or one status.
  String _filter = 'attention';
  String _query = '';

  bool _matches(ResidentLoginRow r) {
    if (_filter == 'attention' && r.status == 'linked') return false;
    if (_filter != 'attention' && _filter != 'all' && r.status != _filter) return false;
    if (_query.isEmpty) return true;
    final q = _query.toLowerCase();
    return r.fullName.toLowerCase().contains(q) ||
        r.flatLabel.toLowerCase().contains(q) ||
        (r.phone?.contains(q) ?? false);
  }

  Future<void> _open(ResidentLoginRow r) async {
    try {
      final resident = await ref.read(residentDetailProvider(r.id).future);
      if (!mounted) return;
      await context.push(AppRoutes.residentForm, extra: {'resident': resident});
      ref.invalidate(residentLoginReportProvider);
    } catch (e) {
      if (mounted) showErrorToast(context, e);
    }
  }

  /// Gives residents who have never signed in one starting password they must change at first sign-in. Says how many
  /// would be set before doing anything, and leaves admins, committee, staff and anyone who has signed in alone.
  Future<void> _startingPassword() async {
    final ctrl = TextEditingController();
    final password = await showDialog<String>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Set a starting password'),
        content: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
          const Text(
            'Residents who have never signed in get this password and must change it the first time they sign in. '
            'Admins, committee, staff and anyone who has already signed in are not changed.',
            style: TextStyle(fontSize: 13, height: 1.4),
          ),
          const SizedBox(height: 8),
          const Text(
            'Until a resident signs in, anyone who knows this password and their mobile number could sign in as them.',
            style: TextStyle(fontSize: 12, color: AppTheme.warning, height: 1.4),
          ),
          const SizedBox(height: 12),
          TextField(
            key: const ValueKey('starting-password-field'),
            controller: ctrl,
            autofocus: true,
            decoration: const InputDecoration(labelText: 'Starting password', helperText: 'At least 8 characters'),
          ),
        ]),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Cancel')),
          FilledButton(onPressed: () => Navigator.pop(ctx, ctrl.text), child: const Text('Preview')),
        ],
      ),
    );
    ctrl.dispose();
    if (password == null) return;
    if (password.length < 8) {
      if (mounted) AppToast.warning(context, 'The password must be at least 8 characters');
      return;
    }
    try {
      final plan = Map<String, dynamic>.from((await ApiClient.instance
              .post('/users/starting-password', data: {'password': password, 'dry_run': true})).data as Map);
      final n = plan['set'] as int;
      if (!mounted) return;
      if (n == 0) {
        AppToast.warning(context, 'Nobody to set: no resident login is waiting for a first sign-in');
        return;
      }
      final ok = await showDialog<bool>(
        context: context,
        builder: (ctx) => AlertDialog(
          title: const Text('Set it for these residents?'),
          content: Text(
              'The starting password will be set for $n resident${n == 1 ? '' : 's'} who have never signed in. '
              '${plan['skipped_signed_in']} who have already signed in and ${plan['skipped_other_roles']} admin, '
              'committee or staff logins are left as they are.'),
          actions: [
            TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Back')),
            FilledButton(onPressed: () => Navigator.pop(ctx, true), child: Text('Set for $n')),
          ],
        ),
      );
      if (ok != true) return;
      final done = Map<String, dynamic>.from((await ApiClient.instance
              .post('/users/starting-password', data: {'password': password})).data as Map);
      if (!mounted) return;
      AppToast.success(context, 'Starting password set for ${done['set']} residents');
      // The list to hand the password out with: who, which flat, which mobile number (never the password itself).
      final people = (done['people'] as List).cast<Map>();
      String cell(Object? v) => '"${'${v ?? ''}'.replaceAll('"', '""')}"';
      final csv = ['Resident,Flat,Mobile', for (final p in people) [cell(p['name']), cell(p['flat']), cell(p['mobile'])].join(',')]
          .join('\n');
      await saveCsvFile(csv, 'residents_starting_password.csv');
    } catch (e) {
      if (mounted) showErrorToast(context, e);
    }
  }

  String _csv(List<ResidentLoginRow> rows) {
    String cell(String? v) => '"${(v ?? '').replaceAll('"', '""')}"';
    final lines = ['Flat,Resident,Type,Mobile,Status,Matching login'];
    for (final r in rows) {
      lines.add([
        cell(r.flatLabel),
        cell(r.fullName),
        cell(r.residentType),
        cell(r.phone),
        cell(_statusInfo[r.status]?.$1 ?? r.status),
        cell(r.loginName),
      ].join(','));
    }
    return lines.join('\n');
  }

  @override
  Widget build(BuildContext context) {
    final report = ref.watch(residentLoginReportProvider);
    final shown = report.valueOrNull?.residents.where(_matches).toList() ?? const <ResidentLoginRow>[];
    return AppPage(
      title: 'Residents without a login',
      subtitle: 'Who can sign in to the app, and who cannot',
      actions: [
        IconButton(
          key: const ValueKey('login-report-export'),
          tooltip: 'Download as a spreadsheet',
          icon: const Icon(Icons.download_rounded),
          onPressed: shown.isEmpty
              ? null
              : () async {
                  if (await saveCsvFile(_csv(shown), 'residents_login_status.csv') && context.mounted) {
                    AppToast.success(context, 'Downloaded');
                  }
                },
        ),
        IconButton(
          key: const ValueKey('starting-password'),
          tooltip: 'Set a starting password',
          icon: const Icon(Icons.key_rounded),
          onPressed: _startingPassword,
        ),
        IconButton(
          tooltip: 'Refresh',
          icon: const Icon(Icons.refresh_rounded),
          onPressed: () => ref.invalidate(residentLoginReportProvider),
        ),
      ],
      body: report.when(
        loading: () => const AppLoader(),
        error: (e, _) => Center(
          child: Padding(
            padding: const EdgeInsets.all(24),
            child: Text(friendlyErrorMessage(e), style: const TextStyle(color: AppTheme.error)),
          ),
        ),
        data: (data) => ResponsiveBody(
          maxWidth: 900,
          child: ListView(
            padding: const EdgeInsets.fromLTRB(16, 12, 16, 32),
            children: [
              Text(
                '${data.count('linked')} of ${data.count('total')} residents can sign in. '
                '${data.count('needs_attention')} cannot.',
                key: const ValueKey('login-report-headline'),
                style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w700),
              ),
              const SizedBox(height: 10),
              Wrap(spacing: 8, runSpacing: 8, children: [
                _chip('Needs attention', 'attention', data.count('needs_attention')),
                for (final e in _statusInfo.entries) _chip(e.value.$1, e.key, data.count(e.key)),
                _chip('All', 'all', data.count('total')),
              ]),
              const SizedBox(height: 12),
              TextField(
                onChanged: (v) => setState(() => _query = v.trim()),
                decoration: const InputDecoration(
                  prefixIcon: Icon(Icons.search_rounded, size: 20),
                  hintText: 'Search by name, flat or mobile',
                ),
              ),
              const SizedBox(height: 12),
              if (shown.isEmpty)
                const Padding(
                  padding: EdgeInsets.symmetric(vertical: 40),
                  child: Center(child: Text('No residents here')),
                ),
              for (final r in shown) _row(r),
            ],
          ),
        ),
      ),
    );
  }

  Widget _chip(String label, String value, int count) => ChoiceChip(
        key: ValueKey('login-filter-$value'),
        label: Text('$label · $count', style: const TextStyle(fontSize: 12)),
        selected: _filter == value,
        onSelected: (_) => setState(() => _filter = value),
      );

  Widget _row(ResidentLoginRow r) {
    final info = _statusInfo[r.status] ?? (r.status, '', AppTheme.textSecondary);
    final hint = r.status == 'login_unlinked' && r.loginName != null
        ? 'Login "${r.loginName}" has this mobile number: link it'
        : info.$2;
    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      child: ListTile(
        key: ValueKey('login-row-${r.id}'),
        onTap: () => _open(r),
        title: Text('${r.fullName} · ${r.flatLabel}', style: const TextStyle(fontWeight: FontWeight.w600)),
        subtitle: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(r.phone ?? 'No mobile number'),
          if (hint.isNotEmpty) Text(hint, style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
          const SizedBox(height: 4),
          StatusPill(info.$1, info.$3),
        ]),
        isThreeLine: true,
        trailing: r.status == 'linked' ? null : const Icon(Icons.chevron_right_rounded),
      ),
    );
  }
}
