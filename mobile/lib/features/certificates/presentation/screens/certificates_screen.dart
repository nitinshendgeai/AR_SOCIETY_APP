import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';
import 'package:ar_society_app/core/layout/app_sheet.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/features/certificates/data/certificates_api.dart';
import 'package:ar_society_app/features/maintenance_billing/presentation/widgets/billing_sheet_frame.dart';
import 'package:ar_society_app/shared/utils/file_saver.dart';
import 'package:ar_society_app/shared/widgets/app_data_table.dart'
    show StatusPill;
import 'package:ar_society_app/shared/widgets/app_widgets.dart';

Color _statusColor(String s) => switch (s) {
      'approved' => AppTheme.success,
      'rejected' => AppTheme.error,
      'cancelled' => AppTheme.textSecondary,
      _ => AppTheme.warning,
    };

String _statusLabel(String s) => switch (s) {
      'approved' => 'Approved',
      'rejected' => 'Not approved',
      'cancelled' => 'Withdrawn',
      _ => 'Waiting',
    };

/// NOCs and certificates: members ask, the office approves, the member downloads the PDF.
class CertificatesScreen extends ConsumerWidget {
  const CertificatesScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final user = ref.watch(currentUserProvider);
    final sid = user?.societyId ?? '';
    final office = user?.isAdminOrCommittee == true;
    final async = ref.watch(certificatesProvider(sid));
    return Scaffold(
      backgroundColor: AppTheme.surface,
      appBar: AppBar(title: const Text('Certificates & NOC')),
      floatingActionButton: FloatingActionButton.extended(
          onPressed: () => showAppSheet(
              context: context, builder: (_) => const _RequestSheet()),
          icon: const Icon(Icons.note_add_rounded),
          label: const Text('Request certificate')),
      body: async.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (e, _) => Center(
            child: OutlinedButton(
                onPressed: () => ref.invalidate(certificatesProvider(sid)),
                child: const Text('Could not load. Try again'))),
        data: (items) {
          if (items.isEmpty) {
            return AppEmptyState(
                icon: Icons.verified_outlined,
                title: 'No requests yet',
                subtitle: office
                    ? 'Requests from members will appear here for approval.'
                    : 'Ask for a NOC, a no dues certificate or an address certificate.');
          }
          return RefreshIndicator(
            onRefresh: () async => ref.invalidate(certificatesProvider(sid)),
            child: ListView(
              padding: const EdgeInsets.fromLTRB(16, 12, 16, 96),
              children: [
                for (final r in items)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 10),
                    child: DecoratedBox(
                      decoration: BoxDecoration(
                          color: AppTheme.cardBg,
                          borderRadius: BorderRadius.circular(AppTheme.radiusL),
                          boxShadow: AppTheme.cardShadow),
                      child: Material(
                        type: MaterialType.transparency,
                        child: InkWell(
                          borderRadius: BorderRadius.circular(AppTheme.radiusL),
                          onTap: () => showAppSheet(
                              context: context,
                              builder: (_) =>
                                  _DetailSheet(request: r, office: office)),
                          child: Padding(
                            padding: const EdgeInsets.all(16),
                            child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Row(children: [
                                    Expanded(
                                        child: Text(r.title,
                                            style: const TextStyle(
                                                fontSize: 15,
                                                fontWeight: FontWeight.w700,
                                                color: AppTheme.textPrimary))),
                                    const SizedBox(width: 8),
                                    StatusPill(_statusLabel(r.status),
                                        _statusColor(r.status)),
                                  ]),
                                  const SizedBox(height: 6),
                                  Text(
                                      [
                                        if (office) r.applicantName,
                                        if (r.flat != null) 'Flat ${r.flat}',
                                        if (r.createdAt != null)
                                          DateFormat('d MMM yyyy')
                                              .format(r.createdAt!),
                                      ].join(' · '),
                                      style: const TextStyle(
                                          fontSize: 13,
                                          color: AppTheme.textSecondary)),
                                  if (r.approved &&
                                      r.certificateNo != null) ...[
                                    const SizedBox(height: 4),
                                    Text('No. ${r.certificateNo}',
                                        style: const TextStyle(
                                            fontSize: 13,
                                            fontWeight: FontWeight.w600,
                                            color: AppTheme.primary)),
                                  ],
                                ]),
                          ),
                        ),
                      ),
                    ),
                  ),
              ],
            ),
          );
        },
      ),
    );
  }
}

class _RequestSheet extends ConsumerStatefulWidget {
  const _RequestSheet();
  @override
  ConsumerState<_RequestSheet> createState() => _RequestSheetState();
}

class _RequestSheetState extends ConsumerState<_RequestSheet> {
  String? _kind;
  final _purpose = TextEditingController();
  final _party = TextEditingController();
  bool _saving = false;

  @override
  void dispose() {
    _purpose.dispose();
    _party.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    if (_kind == null) {
      AppToast.error(context, 'Choose what you need');
      return;
    }
    setState(() => _saving = true);
    try {
      final sid = ref.read(currentUserProvider)?.societyId ?? '';
      await ref.read(certificatesApiProvider).request(sid,
          kind: _kind!,
          purpose: _purpose.text.trim(),
          partyName: _party.text.trim());
      ref.invalidate(certificatesProvider(sid));
      if (mounted) {
        AppToast.success(context, 'Request sent to the society office');
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
    final user = ref.watch(currentUserProvider);
    final tenant = user?.roles.contains('Tenant') == true &&
        user?.isAdminOrCommittee != true;
    final kinds = [
      for (final k in kCertificateKinds)
        if (!tenant || kTenantCertificateKinds.contains(k.$1)) k
    ];
    final needsParty =
        const {'noc_sale', 'noc_rent', 'noc_loan'}.contains(_kind);
    return BillingSheetFrame(
      title: 'Request a certificate',
      child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        DropdownButtonFormField<String>(
          initialValue: _kind,
          isExpanded: true,
          decoration: const InputDecoration(labelText: 'What do you need? *'),
          items: [
            for (final k in kinds)
              DropdownMenuItem(value: k.$1, child: Text(k.$2))
          ],
          onChanged: (v) => setState(() => _kind = v),
        ),
        if (kCertificateKinds.where((k) => k.$1 == _kind && k.$3).isNotEmpty)
          const Padding(
            padding: EdgeInsets.only(top: 8),
            child: Text(
                'Your flat\'s maintenance dues must be cleared for this one.',
                style:
                    TextStyle(fontSize: 12.5, color: AppTheme.textSecondary)),
          ),
        if (needsParty) ...[
          const SizedBox(height: 12),
          TextFormField(
              controller: _party,
              decoration: InputDecoration(
                  labelText: _kind == 'noc_loan'
                      ? 'Bank / lender'
                      : _kind == 'noc_rent'
                          ? 'Name of the tenant'
                          : 'Name of the buyer')),
        ],
        const SizedBox(height: 12),
        TextFormField(
            controller: _purpose,
            minLines: 1,
            maxLines: 3,
            decoration:
                const InputDecoration(labelText: 'Reason / note (optional)')),
        const SizedBox(height: 16),
        AppPrimaryButton(
            label: 'Send request', isLoading: _saving, onPressed: _save),
      ]),
    );
  }
}

class _DetailSheet extends ConsumerStatefulWidget {
  final CertificateRequest request;
  final bool office;
  const _DetailSheet({required this.request, required this.office});
  @override
  ConsumerState<_DetailSheet> createState() => _DetailSheetState();
}

class _DetailSheetState extends ConsumerState<_DetailSheet> {
  final _note = TextEditingController();
  bool _busy = false;

  @override
  void dispose() {
    _note.dispose();
    super.dispose();
  }

  Future<void> _run(Future<void> Function() action, String done) async {
    setState(() => _busy = true);
    try {
      await action();
      ref.invalidate(
          certificatesProvider(ref.read(currentUserProvider)?.societyId ?? ''));
      if (mounted) {
        AppToast.success(context, done);
        Navigator.pop(context);
      }
    } catch (e) {
      if (mounted) {
        setState(() => _busy = false);
        showErrorToast(context, e);
      }
    }
  }

  Future<void> _approve() async {
    final api = ref.read(certificatesApiProvider);
    final id = widget.request.id;
    bool override = false;
    try {
      setState(() => _busy = true);
      await api.decide(id, approve: true, note: _note.text.trim());
    } on DioException catch (e) {
      final detail = (e.response?.data is Map
                  ? e.response!.data['detail'] ?? e.response!.data['message']
                  : null)
              ?.toString() ??
          '';
      if (e.response?.statusCode == 409 && detail.contains('in dues')) {
        if (!mounted) return;
        setState(() => _busy = false);
        final go = await showDialog<bool>(
            context: context,
            builder: (ctx) => AlertDialog(
                  title: const Text('Dues are pending'),
                  content: Text('$detail'),
                  actions: [
                    TextButton(
                        onPressed: () => Navigator.pop(ctx, false),
                        child: const Text('Not now')),
                    FilledButton(
                        onPressed: () => Navigator.pop(ctx, true),
                        child: const Text('Approve anyway')),
                  ],
                ));
        if (go != true) return;
        override = true;
      } else {
        if (mounted) {
          setState(() => _busy = false);
          showErrorToast(context, e);
        }
        return;
      }
    } catch (e) {
      if (mounted) {
        setState(() => _busy = false);
        showErrorToast(context, e);
      }
      return;
    }
    if (override) {
      await _run(
          () => api.decide(id,
              approve: true, note: _note.text.trim(), overrideDues: true),
          'Approved');
    } else if (mounted) {
      ref.invalidate(
          certificatesProvider(ref.read(currentUserProvider)?.societyId ?? ''));
      AppToast.success(context, 'Approved');
      Navigator.pop(context);
    }
  }

  Future<void> _decline() async {
    if (_note.text.trim().isEmpty) {
      AppToast.error(context, 'Write the reason in the note box first');
      return;
    }
    await _run(
        () => ref
            .read(certificatesApiProvider)
            .decide(widget.request.id, approve: false, note: _note.text.trim()),
        'Request turned down');
  }

  Future<void> _download() async {
    final r = widget.request;
    try {
      final bytes = await ref.read(certificatesApiProvider).pdf(r.id);
      final name =
          '${(r.certificateNo ?? 'certificate').replaceAll('/', '-')}.pdf';
      final saved =
          await saveFileBytes(bytes, name, mimeType: 'application/pdf');
      if (mounted && saved) AppToast.success(context, 'Saved $name');
    } catch (e) {
      if (mounted) showErrorToast(context, e);
    }
  }

  Widget _line(String label, String? value) => (value ?? '').isEmpty
      ? const SizedBox.shrink()
      : Padding(
          padding: const EdgeInsets.only(bottom: 8),
          child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
            SizedBox(
                width: 96,
                child: Text(label,
                    style: const TextStyle(
                        fontSize: 13, color: AppTheme.textSecondary))),
            Expanded(
                child: Text(value!,
                    style: const TextStyle(
                        fontSize: 14, color: AppTheme.textPrimary))),
          ]),
        );

  @override
  Widget build(BuildContext context) {
    final r = widget.request;
    return BillingSheetFrame(
      title: r.title,
      child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        Align(
            alignment: Alignment.centerLeft,
            child: StatusPill(_statusLabel(r.status), _statusColor(r.status))),
        const SizedBox(height: 12),
        _line('Member', r.applicantName),
        _line('Flat', r.flat),
        _line('For', r.partyName),
        _line('Reason', r.purpose),
        _line('Number', r.certificateNo),
        _line(
            'Decided',
            r.decidedOn == null
                ? null
                : DateFormat('d MMM yyyy').format(r.decidedOn!)),
        if (r.duesAtDecision != null && r.duesAtDecision! > 0)
          _line('Dues then', 'Rs. ${r.duesAtDecision!.toStringAsFixed(2)}'),
        _line(r.status == 'rejected' ? 'Reason given' : 'Note', r.decisionNote),
        const SizedBox(height: 8),
        if (r.approved)
          AppPrimaryButton(label: 'Download PDF', onPressed: _download),
        if (r.pending && widget.office) ...[
          TextFormField(
              controller: _note,
              minLines: 1,
              maxLines: 3,
              decoration:
                  const InputDecoration(labelText: 'Note (needed to decline)')),
          const SizedBox(height: 12),
          AppPrimaryButton(
              label: 'Approve', isLoading: _busy, onPressed: _approve),
          const SizedBox(height: 8),
          OutlinedButton(
              onPressed: _busy ? null : _decline,
              style: OutlinedButton.styleFrom(foregroundColor: AppTheme.error),
              child: const Text('Decline')),
        ] else if (r.pending)
          OutlinedButton(
              onPressed: _busy
                  ? null
                  : () => _run(
                      () => ref.read(certificatesApiProvider).cancel(r.id),
                      'Request withdrawn'),
              child: const Text('Withdraw request')),
      ]),
    );
  }
}
