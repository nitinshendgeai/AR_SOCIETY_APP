import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/resident_master/data/models/resident_master_models.dart';
import 'package:ar_society_app/features/resident_master/presentation/providers/resident_master_providers.dart';
import 'package:ar_society_app/features/resident_master/presentation/widgets/resident_master_widgets.dart';

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
          child: TextFormField(
            controller: reasonCtrl,
            maxLines: 3,
            autofocus: true,
            decoration: const InputDecoration(labelText: 'Reason *'),
            validator: (v) => (v == null || v.trim().isEmpty) ? 'Required' : null,
          ),
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
            child: const Text('Reject', style: TextStyle(color: Colors.white)),
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

  @override
  Widget build(BuildContext context) {
    final requestsAsync = ref.watch(pendingEditRequestsProvider);

    return Scaffold(
      backgroundColor: AppTheme.surface,
      appBar: AppBar(
        title: const Text('Pending Resident Changes'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh_rounded),
            onPressed: () => ref.invalidate(pendingEditRequestsProvider),
          ),
        ],
      ),
      body: requestsAsync.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (e, _) => Center(child: Text('Could not load requests: $e')),
        data: (requests) {
          if (requests.isEmpty) {
            return const RmEmptyState(
              icon: Icons.fact_check_outlined,
              title: 'No pending change requests',
              subtitle: 'Residents\' profile edit requests will appear here for approval.',
            );
          }
          return ListView.separated(
            padding: const EdgeInsets.all(20),
            itemCount: requests.length,
            separatorBuilder: (_, __) => const SizedBox(height: 10),
            itemBuilder: (_, i) {
              final req = requests[i];
              final busy = _actingOn == req.id;
              return Container(
                padding: const EdgeInsets.all(14),
                decoration: BoxDecoration(
                  color: AppTheme.cardBg,
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(color: AppTheme.border),
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
                            style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
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
            },
          );
        },
      ),
    );
  }
}
