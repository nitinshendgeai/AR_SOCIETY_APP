import 'package:flutter/material.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/l10n/app_locale.dart';
import 'package:ar_society_app/core/motion/loading.dart';
import 'package:ar_society_app/features/resident_master/data/family_requests_api.dart';
import 'package:ar_society_app/shared/widgets/premium.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/resident_master/data/models/resident_master_models.dart';
import 'package:ar_society_app/features/resident_master/presentation/providers/resident_master_providers.dart';
import 'package:ar_society_app/features/resident_master/presentation/widgets/resident_master_widgets.dart';
import 'package:ar_society_app/shared/widgets/app_form.dart';

/// Admin/Committee queue for Residents' self-service profile change
/// requests (see edit_my_profile_screen.dart) — approve applies the
/// requested changes to the Resident record, reject discards them with a
/// reason the resident can see on their own screen.
class PendingResidentChangesScreen extends ConsumerStatefulWidget {
  const PendingResidentChangesScreen({super.key});

  @override
  ConsumerState<PendingResidentChangesScreen> createState() => _PendingResidentChangesScreenState();
}

class _PendingResidentChangesScreenState extends ConsumerState<PendingResidentChangesScreen> {
  String? _actingOn;

  Future<void> _approve(ResidentEditRequestModel req) async {
    setState(() => _actingOn = req.id);
    await ref.read(editRequestActionProvider.notifier).approve(req.id);
    await _handleResult();
  }

  Future<void> _reject(ResidentEditRequestModel req, String reason) async {
    setState(() => _actingOn = req.id);
    await ref.read(editRequestActionProvider.notifier).reject(req.id, reason);
    await _handleResult();
  }

  Future<void> _handleResult() async {
    final state = ref.read(editRequestActionProvider);
    if (!mounted) return;
    switch (state) {
      case EditRequestActionSuccess(:final message):
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(
          content: Text(message), backgroundColor: AppTheme.success,
        ));
        ref.invalidate(pendingEditRequestsProvider);
      case EditRequestActionError(:final message):
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(
          content: Text(message), backgroundColor: AppTheme.error,
        ));
      default:
        break;
    }
    ref.read(editRequestActionProvider.notifier).reset();
    setState(() => _actingOn = null);
  }

  void _showRejectDialog(ResidentEditRequestModel req) {
    final reasonCtrl = TextEditingController();
    final formKey = GlobalKey<FormState>();
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Reject Change Request?'),
        content: Form(
          key: formKey,
          child: FormFieldBox(label: 'Reason', required: true, child: TextFormField(
            controller: reasonCtrl,
            maxLines: 3,
            autofocus: true,
            decoration: const InputDecoration(),
            validator: (v) => (v == null || v.trim().isEmpty) ? 'Required' : null,
          )),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Cancel')),
          ElevatedButton(
            style: ElevatedButton.styleFrom(backgroundColor: AppTheme.error),
            onPressed: () {
              if (!(formKey.currentState?.validate() ?? true)) return;
              Navigator.pop(ctx);
              _reject(req, reasonCtrl.text.trim());
            },
            child: Text('Reject', style: TextStyle(color: AppTheme.onPrimary)),
          ),
        ],
      ),
    );
  }

  String _fieldLabel(String field) => switch (field) {
        'full_name' => 'Full Name',
        'phone' => 'Mobile',
        'email' => 'Email',
        'date_of_birth' => 'Date of Birth',
        'emergency_contact_name' => 'Emergency Contact Name',
        'emergency_contact_phone' => 'Emergency Contact Phone',
        'comm_preference' => 'Communication Preference',
        _ => field,
      };

  Widget _editCard(ResidentEditRequestModel req) {
    final busy = _actingOn == req.id;
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: AppTheme.cardBg,
        borderRadius: BorderRadius.circular(AppTheme.radiusM),
        boxShadow: AppTheme.cardShadow,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(children: [
            Expanded(
              child: Text(req.residentName ?? 'Resident',
                  style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 14)),
            ),
            if (req.flatDisplay != null)
              Text(req.flatDisplay!,
                  style: TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
          ]),
          const SizedBox(height: 8),
          ...req.changes.entries.map((e) => Padding(
                padding: const EdgeInsets.symmetric(vertical: 2),
                child: Text('${_fieldLabel(e.key)}: ${e.value ?? '—'}',
                    style: const TextStyle(fontSize: 13)),
              )),
          const SizedBox(height: 12),
          Row(children: [
            Expanded(
              child: OutlinedButton(
                onPressed: busy ? null : () => _showRejectDialog(req),
                style: OutlinedButton.styleFrom(foregroundColor: AppTheme.error),
                child: const Text('Reject'),
              ),
            ),
            const SizedBox(width: 10),
            Expanded(
              child: ElevatedButton(
                onPressed: busy ? null : () => _approve(req),
                child: busy
                    ? const SizedBox(
                        width: 18, height: 18,
                        child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                      )
                    : const Text('Approve'),
              ),
            ),
          ]),
        ],
      ),
    );
  }

  // ── New family members ──────────────────────────────────────────────────────────────────────────────────────────

  Future<void> _familyAct(FamilyRequest req, Future<void> Function() action, String done) async {
    setState(() => _actingOn = req.id);
    try {
      await action();
      ref.invalidate(pendingFamilyRequestsProvider);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(done), backgroundColor: AppTheme.success));
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(friendlyErrorMessage(e)), backgroundColor: AppTheme.error));
      }
    } finally {
      if (mounted) setState(() => _actingOn = null);
    }
  }

  void _rejectFamily(FamilyRequest req) {
    final reasonCtrl = TextEditingController();
    final formKey = GlobalKey<FormState>();
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(ctx.tr('Reject this family member?')),
        content: Form(
          key: formKey,
          child: FormFieldBox(label: 'Reason', required: true, child: TextFormField(
            key: const Key('family-reject-reason'),
            controller: reasonCtrl,
            maxLines: 3,
            autofocus: true,
            decoration: const InputDecoration(),
            validator: (v) => (v == null || v.trim().isEmpty) ? 'Required' : null,
          )),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: Text(ctx.tr('Cancel'))),
          ElevatedButton(
            style: ElevatedButton.styleFrom(backgroundColor: AppTheme.error),
            onPressed: () {
              if (!(formKey.currentState?.validate() ?? true)) return;
              Navigator.pop(ctx);
              _familyAct(req, () => ref.read(familyRequestsApiProvider).reject(req.id, reasonCtrl.text.trim()), 'Rejected');
            },
            child: Text(ctx.tr('Reject'), style: TextStyle(color: AppTheme.onPrimary)),
          ),
        ],
      ),
    );
  }

  Widget _familyCard(FamilyRequest req) {
    final busy = _actingOn == req.id;
    return Container(
      key: Key('family-request-${req.id}'),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(color: AppTheme.cardBg, borderRadius: BorderRadius.circular(AppTheme.radiusM), boxShadow: AppTheme.cardShadow),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Expanded(child: Text(req.fullName, style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 14))),
          if (req.flatDisplay != null) Text(req.flatDisplay!, style: TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
        ]),
        const SizedBox(height: 6),
        Text(context.tr(req.typeLabel), style: const TextStyle(fontSize: 13)),
        if (req.phone != null && req.phone!.isNotEmpty) Text('${context.tr('Mobile')}: ${req.phone}', style: const TextStyle(fontSize: 13)),
        if (req.dateOfBirth != null)
          Text('${context.tr('Date of Birth')}: ${req.dateOfBirth!.day}/${req.dateOfBirth!.month}/${req.dateOfBirth!.year}',
              style: const TextStyle(fontSize: 13)),
        if (req.requesterName != null)
          Text('${context.tr('Asked by')} ${req.requesterName}', style: TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
        const SizedBox(height: 12),
        Row(children: [
          Expanded(
            child: OutlinedButton(
              key: Key('family-reject-${req.id}'),
              onPressed: busy ? null : () => _rejectFamily(req),
              style: OutlinedButton.styleFrom(foregroundColor: AppTheme.error),
              child: Text(context.tr('Reject')),
            ),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: ElevatedButton(
              key: Key('family-approve-${req.id}'),
              onPressed: busy ? null : () => _familyAct(req, () => ref.read(familyRequestsApiProvider).approve(req.id), 'Added to the family list'),
              child: busy
                  ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                  : Text(context.tr('Approve')),
            ),
          ),
        ]),
      ]),
    );
  }

  @override
  Widget build(BuildContext context) {
    final requestsAsync = ref.watch(pendingEditRequestsProvider);

    return AppPage(
      title: 'Pending Resident Changes',
      actions: [
          IconButton(
            icon: const Icon(Icons.refresh_rounded),
            onPressed: () {
              ref.invalidate(pendingEditRequestsProvider);
              ref.invalidate(pendingFamilyRequestsProvider);
            },
          ),
        ],
      body: requestsAsync.when(
        loading: () => const AppLoader(),
        error: (e, _) => Center(child: Text('Could not load requests: $e')),
        data: (requests) {
          final family = ref.watch(pendingFamilyRequestsProvider).valueOrNull ?? const <FamilyRequest>[];
          if (requests.isEmpty && family.isEmpty) {
            return const RmEmptyState(
              icon: Icons.fact_check_outlined,
              title: 'No pending change requests',
              subtitle: 'Residents\' profile edit requests and new family members will appear here for approval.',
            );
          }
          return ListView(
            padding: const EdgeInsets.all(20),
            children: [
              if (family.isNotEmpty) ...[
                SectionHeading(context.tr('New family members')),
                const SizedBox(height: 10),
                for (final f in family) ...[_familyCard(f), const SizedBox(height: 10)],
                if (requests.isNotEmpty) const SizedBox(height: 10),
              ],
              if (requests.isNotEmpty) ...[
                if (family.isNotEmpty) ...[SectionHeading(context.tr('Profile changes')), const SizedBox(height: 10)],
                for (final req in requests) ...[_editCard(req), const SizedBox(height: 10)],
              ],
            ],
          );
        },
      ),
    );
  }
}
