import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/layout/app_sheet.dart';
import 'package:ar_society_app/core/motion/loading.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/features/governance/data/committee_api.dart';
import 'package:ar_society_app/features/maintenance_billing/presentation/widgets/billing_sheet_frame.dart';
import 'package:ar_society_app/features/resident_master/data/models/resident_master_models.dart' show ResidentModel;
import 'package:ar_society_app/features/resident_master/presentation/providers/resident_master_providers.dart';
import 'package:ar_society_app/features/resident_master/data/repositories/resident_master_repository.dart' show RmSuccess;
import 'package:ar_society_app/features/vendor/presentation/widgets/procurement_widgets.dart' show DateField;
import 'package:ar_society_app/shared/widgets/app_data_table.dart' show StatusPill;
import 'package:ar_society_app/shared/widgets/app_form.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';

String _day(DateTime? d) => d == null ? '—' : DateFormat('d MMM yyyy').format(d);
String _inr(int v) => NumberFormat.decimalPattern('en_IN').format(v);

/// The managing committee: its term, its office-bearers with their powers and contacts, and the committees before it.
/// Every member sees it; admins and committee members keep it.
class CommitteeScreen extends ConsumerWidget {
  const CommitteeScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final user = ref.watch(currentUserProvider);
    final sid = user?.societyId ?? '';
    final office = user?.isAdminOrCommittee == true;
    final async = ref.watch(committeeRegisterProvider(sid));
    return AppPage(
      title: 'Managing Committee',
      subtitle: 'Office-bearers, their term, powers and contacts',
      maxWidth: 960,
      body: async.when(
        loading: () => const SkeletonList(),
        error: (e, _) => AppErrorState(message: friendlyErrorMessage(e), onRetry: () => ref.invalidate(committeeRegisterProvider(sid))),
        data: (reg) {
          final c = reg.current;
          if (c == null) {
            return AppEmptyState(
              icon: Icons.groups_2_rounded,
              title: 'No committee recorded yet',
              subtitle: office ? 'Record the committee elected, then add its office-bearers.' : 'The committee will appear here.',
              actionLabel: office ? 'Record the committee' : null,
              onAction: office ? () => showAppSheet(context: context, builder: (_) => _NewCommitteeSheet(sid: sid)) : null,
            );
          }
          return RefreshIndicator(
            onRefresh: () async => ref.invalidate(committeeRegisterProvider(sid)),
            child: ListView(padding: const EdgeInsets.fromLTRB(16, 8, 16, 96), children: [
              _TermCard(c: c, office: office, sid: sid),
              for (final w in c.warnings)
                Padding(
                  padding: const EdgeInsets.only(top: 8),
                  child: _Warning(w),
                ),
              const SizedBox(height: 16),
              Row(children: [
                Expanded(child: Text('Office-bearers', style: Theme.of(context).textTheme.titleMedium)),
                if (office)
                  FilledButton.icon(
                    key: const Key('add-committee-member'),
                    onPressed: () => showAppSheet(context: context, builder: (_) => _MemberSheet(committee: c, sid: sid)),
                    icon: const Icon(Icons.person_add_alt_1_rounded, size: 18),
                    label: const Text('Add member'),
                  ),
              ]),
              const SizedBox(height: 8),
              if (c.members.isEmpty)
                Text('No members added yet.', style: TextStyle(color: AppTheme.textSecondary)),
              LayoutBuilder(builder: (context, box) {
                final cols = box.maxWidth > 720 ? 2 : 1;
                final w = (box.maxWidth - (cols - 1) * 12) / cols;
                return Wrap(spacing: 12, runSpacing: 12, children: [
                  for (final m in c.members)
                    SizedBox(width: w, child: _MemberCard(m: m, office: office, committee: c, sid: sid)),
                ]);
              }),
              if (c.formerMembers.isNotEmpty) ...[
                const SizedBox(height: 20),
                Text('Left the committee', style: Theme.of(context).textTheme.titleMedium),
                for (final m in c.formerMembers)
                  ListTile(
                    dense: true,
                    contentPadding: EdgeInsets.zero,
                    leading: const Icon(Icons.history_rounded),
                    title: Text('${m.fullName} · ${m.positionLabel}'),
                    subtitle: Text('${_day(m.fromDate)} – ${_day(m.toDate)}'),
                  ),
              ],
              if (reg.past.isNotEmpty) ...[
                const SizedBox(height: 20),
                Text('Earlier committees', style: Theme.of(context).textTheme.titleMedium),
                for (final p in reg.past)
                  ExpansionTile(
                    tilePadding: EdgeInsets.zero,
                    title: Text(p.name),
                    subtitle: Text('${_day(p.formedOn)} – ${_day(p.termEndsOn)}'),
                    children: [
                      for (final m in p.members)
                        ListTile(dense: true, title: Text(m.fullName), subtitle: Text(m.positionLabel)),
                    ],
                  ),
              ],
            ]),
          );
        },
      ),
    );
  }
}

class _TermCard extends StatelessWidget {
  final Committee c;
  final bool office;
  final String sid;
  const _TermCard({required this.c, required this.office, required this.sid});

  @override
  Widget build(BuildContext context) {
    final left = c.daysLeft;
    final status = c.termOver
        ? StatusPill('Term ended', AppTheme.error)
        : (left != null && left <= 120 ? StatusPill('Elections due in $left days', AppTheme.warning) : StatusPill('In office', AppTheme.success));
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            Expanded(child: Text(c.name, style: const TextStyle(fontSize: 17, fontWeight: FontWeight.w700))),
            status,
          ]),
          const SizedBox(height: 6),
          Text('Term: ${_day(c.formedOn)} – ${_day(c.termEndsOn)}', style: TextStyle(color: AppTheme.textSecondary)),
          if ((c.electionNote ?? '').isNotEmpty) ...[
            const SizedBox(height: 4),
            Text(c.electionNote!, style: TextStyle(color: AppTheme.textSecondary, fontSize: 12.5)),
          ],
          if (office) ...[
            const SizedBox(height: 8),
            TextButton.icon(
              onPressed: () => showAppSheet(context: context, builder: (_) => _NewCommitteeSheet(sid: sid)),
              icon: const Icon(Icons.how_to_vote_rounded, size: 18),
              label: const Text('Record a new committee (after elections)'),
            ),
          ],
        ]),
      ),
    );
  }
}

class _MemberCard extends ConsumerWidget {
  final CommitteeMember m;
  final bool office;
  final Committee committee;
  final String sid;
  const _MemberCard({required this.m, required this.office, required this.committee, required this.sid});

  void _copy(BuildContext context, String v) {
    Clipboard.setData(ClipboardData(text: v));
    AppToast.success(context, 'Copied $v');
  }

  Future<void> _leave(BuildContext context, WidgetRef ref) async {
    final picked = await showDatePicker(
        context: context, initialDate: DateTime.now(), firstDate: m.fromDate, lastDate: DateTime.now().add(const Duration(days: 365)),
        helpText: 'Last day in the office');
    if (picked == null) return;
    try {
      await ref.read(committeeApiProvider).updateMember(m.id, {'to_date': DateFormat('yyyy-MM-dd').format(picked)});
      ref.invalidate(committeeRegisterProvider(sid));
      if (context.mounted) AppToast.success(context, '${m.fullName} leaves the office on ${_day(picked)}');
    } catch (e) {
      if (context.mounted) showErrorToast(context, e);
    }
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) => Card(
        margin: EdgeInsets.zero,
        child: Padding(
          padding: const EdgeInsets.fromLTRB(14, 12, 8, 12),
          child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
            CircleAvatar(
              radius: 20,
              backgroundColor: AppTheme.primarySoft,
              child: Text(m.fullName.isEmpty ? '?' : m.fullName[0].toUpperCase(),
                  style: TextStyle(color: AppTheme.primary, fontWeight: FontWeight.w700)),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text(m.positionLabel.toUpperCase(),
                    style: TextStyle(fontSize: 11, letterSpacing: 1, fontWeight: FontWeight.w700, color: AppTheme.primary)),
                Text(m.fullName, style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w700)),
                if ((m.flat ?? '').isNotEmpty) Text('Flat ${m.flat}', style: TextStyle(color: AppTheme.textSecondary, fontSize: 12.5)),
                const SizedBox(height: 6),
                if ((m.phone ?? '').isNotEmpty)
                  InkWell(
                    onTap: () => _copy(context, m.phone!),
                    child: Row(mainAxisSize: MainAxisSize.min, children: [
                      Icon(Icons.call_rounded, size: 15, color: AppTheme.textSecondary),
                      const SizedBox(width: 6),
                      SelectableText(m.phone!, style: const TextStyle(fontSize: 13)),
                    ]),
                  ),
                if ((m.email ?? '').isNotEmpty)
                  InkWell(
                    onTap: () => _copy(context, m.email!),
                    child: Row(mainAxisSize: MainAxisSize.min, children: [
                      Icon(Icons.mail_outline_rounded, size: 15, color: AppTheme.textSecondary),
                      const SizedBox(width: 6),
                      Flexible(child: SelectableText(m.email!, style: const TextStyle(fontSize: 13))),
                    ]),
                  ),
                if (m.authorities.isNotEmpty || m.spendingLimit != null) ...[
                  const SizedBox(height: 8),
                  Wrap(spacing: 6, runSpacing: 6, children: [
                    for (final a in m.authorities) StatusPill(a, AppTheme.primary),
                    if (m.spendingLimit != null) StatusPill('Up to ₹${_inr(m.spendingLimit!)}', AppTheme.success),
                  ]),
                ],
                if ((m.responsibilities ?? '').isNotEmpty) ...[
                  const SizedBox(height: 6),
                  Text(m.responsibilities!, style: TextStyle(color: AppTheme.textSecondary, fontSize: 12.5)),
                ],
                const SizedBox(height: 4),
                Text('Since ${_day(m.fromDate)}${m.toDate == null ? '' : ' · until ${_day(m.toDate)}'}',
                    style: TextStyle(color: AppTheme.textTertiary, fontSize: 12)),
              ]),
            ),
            if (office)
              PopupMenuButton<String>(
                tooltip: 'More',
                onSelected: (v) async {
                  if (v == 'edit') {
                    showAppSheet(context: context, builder: (_) => _MemberSheet(committee: committee, sid: sid, member: m));
                  } else if (v == 'leave') {
                    await _leave(context, ref);
                  } else if (v == 'remove') {
                    try {
                      await ref.read(committeeApiProvider).removeMember(m.id);
                      ref.invalidate(committeeRegisterProvider(sid));
                    } catch (e) {
                      if (context.mounted) showErrorToast(context, e);
                    }
                  }
                },
                itemBuilder: (_) => const [
                  PopupMenuItem(value: 'edit', child: Text('Edit')),
                  PopupMenuItem(value: 'leave', child: Text('Left the office…')),
                  PopupMenuItem(value: 'remove', child: Text('Remove (entered by mistake)')),
                ],
              ),
          ]),
        ),
      );
}

class _NewCommitteeSheet extends ConsumerStatefulWidget {
  final String sid;
  const _NewCommitteeSheet({required this.sid});
  @override
  ConsumerState<_NewCommitteeSheet> createState() => _NewCommitteeSheetState();
}

class _NewCommitteeSheetState extends ConsumerState<_NewCommitteeSheet> {
  DateTime? _formed = DateTime.now();
  DateTime? _ends;
  final _note = TextEditingController();
  bool _busy = false;

  @override
  void dispose() {
    _note.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => BillingSheetFrame(
        title: 'Record the managing committee',
        subtitle: 'The term is five years unless you set another end date',
        child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          DateField(label: 'Elected / formed on', value: _formed, required: true, onChanged: (d) => setState(() => _formed = d)),
          const SizedBox(height: 10),
          DateField(label: 'Term ends on (optional)', value: _ends, onChanged: (d) => setState(() => _ends = d)),
          const SizedBox(height: 10),
          TextField(controller: _note, maxLines: 2,
              decoration: const InputDecoration(labelText: 'Election details (optional)', hintText: 'Returning officer, AGM resolution no., …')),
          const SizedBox(height: 14),
          AppPrimaryButton(
            label: 'Save',
            isLoading: _busy,
            onPressed: _busy || _formed == null
                ? null
                : () async {
                    setState(() => _busy = true);
                    try {
                      await ref.read(committeeApiProvider).create(widget.sid, formedOn: _formed!, termEndsOn: _ends, note: _note.text);
                      ref.invalidate(committeeRegisterProvider(widget.sid));
                      if (context.mounted) Navigator.of(context).pop();
                    } catch (e) {
                      if (context.mounted) showErrorToast(context, e);
                      if (mounted) setState(() => _busy = false);
                    }
                  },
          ),
        ]),
      );
}

final _residentSearchProvider = FutureProvider.autoDispose.family<List<ResidentModel>, String>((ref, q) async {
  if (q.trim().length < 2) return const [];
  final r = await ref.read(residentMasterRepositoryProvider).listResidents(search: q.trim(), isActive: true, limit: 8);
  return r is RmSuccess<List<ResidentModel>> ? r.data : const [];
});

/// Add a member (from the residents, or by name) or edit one: office, contacts, powers.
class _MemberSheet extends ConsumerStatefulWidget {
  final Committee committee;
  final String sid;
  final CommitteeMember? member;
  const _MemberSheet({required this.committee, required this.sid, this.member});
  @override
  ConsumerState<_MemberSheet> createState() => _MemberSheetState();
}

class _MemberSheetState extends ConsumerState<_MemberSheet> {
  late final _name = TextEditingController(text: widget.member?.fullName ?? '');
  late final _flat = TextEditingController(text: widget.member?.flat ?? '');
  late final _phone = TextEditingController(text: widget.member?.phone ?? '');
  late final _email = TextEditingController(text: widget.member?.email ?? '');
  late final _limit = TextEditingController(text: widget.member?.spendingLimit?.toString() ?? '');
  late final _resp = TextEditingController(text: widget.member?.responsibilities ?? '');
  final _search = TextEditingController();
  String? _residentId;
  late String _position = widget.member?.position ?? 'member';
  bool? _cheque, _approve, _sign;
  DateTime? _from;
  bool _busy = false;

  @override
  void initState() {
    super.initState();
    final m = widget.member;
    if (m != null) {
      _cheque = m.chequeSignatory;
      _approve = m.approvesPayments;
      _sign = m.signsDocuments;
      _from = m.fromDate;
    }
  }

  @override
  void dispose() {
    for (final c in [_name, _flat, _phone, _email, _limit, _resp, _search]) {
      c.dispose();
    }
    super.dispose();
  }

  bool get _officeBearer => const ['chairman', 'secretary', 'treasurer'].contains(_position);

  Future<void> _save({bool replace = false}) async {
    setState(() => _busy = true);
    final api = ref.read(committeeApiProvider);
    try {
      if (widget.member == null) {
        await api.addMember(widget.committee.id, committeeMemberPayload(
          residentId: _residentId, fullName: _name.text, flat: _flat.text, position: _position, phone: _phone.text,
          email: _email.text, fromDate: _from, chequeSignatory: _cheque, approvesPayments: _approve, signsDocuments: _sign,
          spendingLimit: _limit.text, responsibilities: _resp.text, replace: replace));
      } else {
        await api.updateMember(widget.member!.id, {
          'full_name': _name.text.trim(), 'flat': _flat.text.trim(), 'position': _position, 'phone': _phone.text.trim(),
          'email': _email.text.trim(), 'cheque_signatory': _cheque ?? false, 'approves_payments': _approve ?? false,
          'signs_documents': _sign ?? false,
          'spending_limit': int.tryParse(_limit.text.replaceAll(',', '').trim()),
          'responsibilities': _resp.text.trim(), if (replace) 'replace': true,
        });
      }
      ref.invalidate(committeeRegisterProvider(widget.sid));
      if (mounted) Navigator.of(context).pop();
    } on FormatException catch (e) {
      if (mounted) showErrorToast(context, Exception(e.message));
    } catch (e) {
      final conflict = e.toString().contains('already');
      if (conflict && mounted) {
        final ok = await showDialog<bool>(
          context: context,
          builder: (ctx) => AlertDialog(
            title: Text('Replace the ${positionLabel(_position)}?'),
            content: Text('${friendlyErrorMessage(e)}\n\nThe present holder will be shown as having left the office the day before.'),
            actions: [
              TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancel')),
              FilledButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('Replace')),
            ],
          ),
        );
        if (ok == true) return _save(replace: true);
      } else if (mounted) {
        showErrorToast(context, e);
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final adding = widget.member == null;
    final results = ref.watch(_residentSearchProvider(_search.text));
    return BillingSheetFrame(
      title: adding ? 'Add a committee member' : 'Edit ${widget.member!.fullName}',
      child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        if (adding) ...[
          TextField(
            controller: _search,
            decoration: const InputDecoration(labelText: 'Find the resident', prefixIcon: Icon(Icons.search_rounded),
                hintText: 'Name, flat or phone'),
            onChanged: (_) => setState(() {}),
          ),
          for (final r in results.valueOrNull ?? const <ResidentModel>[])
            ListTile(
              dense: true,
              selected: _residentId == r.id,
              leading: Icon(_residentId == r.id ? Icons.check_circle_rounded : Icons.person_outline_rounded),
              title: Text(r.fullName),
              subtitle: Text([if ((r.phone ?? '').isNotEmpty) r.phone!, if ((r.email ?? '').isNotEmpty) r.email!].join(' · ')),
              onTap: () => setState(() {
                _residentId = r.id;
                _name.text = r.fullName;
                _phone.text = r.phone ?? '';
                _email.text = r.email ?? '';
              }),
            ),
          const SizedBox(height: 8),
        ],
        DropdownButtonFormField<String>(
          initialValue: _position,
          decoration: const InputDecoration(labelText: 'Office'),
          items: [for (final p in kCommitteePositions) DropdownMenuItem(value: p.$1, child: Text(p.$2))],
          onChanged: (v) => setState(() => _position = v ?? _position),
        ),
        const SizedBox(height: 10),
        TextField(controller: _name, decoration: const InputDecoration(labelText: 'Name')),
        const SizedBox(height: 10),
        Row(children: [
          Expanded(child: TextField(controller: _flat, decoration: const InputDecoration(labelText: 'Flat'))),
          const SizedBox(width: 10),
          Expanded(child: TextField(controller: _phone, keyboardType: TextInputType.phone, decoration: const InputDecoration(labelText: 'Phone'))),
        ]),
        const SizedBox(height: 10),
        TextField(controller: _email, keyboardType: TextInputType.emailAddress, decoration: const InputDecoration(labelText: 'Email')),
        if (adding) ...[
          const SizedBox(height: 10),
          DateField(label: 'In the office from (default: when the committee was formed)', value: _from, onChanged: (d) => setState(() => _from = d)),
        ],
        const SizedBox(height: 12),
        Text('Authorities', style: Theme.of(context).textTheme.titleSmall),
        SwitchListTile(
          contentPadding: EdgeInsets.zero, dense: true, title: const Text('Cheque signatory'),
          value: _cheque ?? _officeBearer, onChanged: (v) => setState(() => _cheque = v)),
        SwitchListTile(
          contentPadding: EdgeInsets.zero, dense: true, title: const Text('Approves payments'),
          value: _approve ?? _officeBearer, onChanged: (v) => setState(() => _approve = v)),
        SwitchListTile(
          contentPadding: EdgeInsets.zero, dense: true, title: const Text('Signs documents'),
          value: _sign ?? const ['chairman', 'secretary'].contains(_position), onChanged: (v) => setState(() => _sign = v)),
        TextField(controller: _limit, keyboardType: TextInputType.number,
            decoration: const InputDecoration(labelText: 'May approve alone up to ₹ (optional)')),
        const SizedBox(height: 10),
        TextField(controller: _resp, decoration: const InputDecoration(labelText: 'Looks after (optional)', hintText: 'Accounts, vendors, security…')),
        const SizedBox(height: 14),
        AppPrimaryButton(label: adding ? 'Add' : 'Save', isLoading: _busy, onPressed: _busy ? null : () => _save()),
      ]),
    );
  }
}

class _Warning extends StatelessWidget {
  final String text;
  const _Warning(this.text);
  @override
  Widget build(BuildContext context) => Container(
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
        decoration: BoxDecoration(
          color: AppTheme.warning.withValues(alpha: 0.10),
          borderRadius: BorderRadius.circular(10),
          border: Border.all(color: AppTheme.warning.withValues(alpha: 0.35)),
        ),
        child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Icon(Icons.warning_amber_rounded, size: 18, color: AppTheme.warning),
          const SizedBox(width: 8),
          Expanded(child: Text(text, style: const TextStyle(fontSize: 13))),
        ]),
      );
}
