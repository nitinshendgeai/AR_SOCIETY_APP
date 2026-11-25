import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/motion/loading.dart';
import 'package:ar_society_app/core/theme/design_tokens.dart';
import 'package:ar_society_app/features/accounts/data/accounts_api.dart' show formatInr;
import 'package:ar_society_app/features/accounts_agent/presentation/widgets/agent_hud.dart';
import 'package:ar_society_app/features/accounts_agent/presentation/providers/legal_providers.dart';
import 'package:ar_society_app/features/accounts_agent/presentation/widgets/agent_widgets.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/shared/widgets/app_form.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';

const _categories = ['expense', 'contract', 'fund_utilisation', 'fund_transfer', 'budget', 'charges', 'recovery', 'borrowing', 'policy', 'other'];

/// The structured resolution register the agent compares payments and fund movements against.
class ResolutionsScreen extends ConsumerWidget {
  const ResolutionsScreen({super.key});

  Future<void> _import(BuildContext context, WidgetRef ref) async {
    try {
      final n = await ref.read(legalApiProvider).importResolutions();
      invalidateLegal(ref);
      if (context.mounted) AppToast.success(context, n == 0 ? 'Nothing new in the meetings' : 'Imported $n resolution(s) — check and verify them');
    } catch (e) {
      if (context.mounted) showErrorToast(context, e);
    }
  }

  Future<void> _add(BuildContext context, WidgetRef ref) async {
    final number = TextEditingController(), purpose = TextEditingController(), amount = TextEditingController();
    final attendance = TextEditingController(), quorum = TextEditingController();
    var meeting = 'COMMITTEE', category = 'expense';
    DateTime date = DateTime.now();
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setS) => AlertDialog(
          title: const Text('Record a resolution'),
          content: SingleChildScrollView(
            child: Column(mainAxisSize: MainAxisSize.min, children: [
              TextField(controller: number, decoration: const InputDecoration(labelText: 'Resolution number')),
              DropdownButtonFormField<String>(
                initialValue: meeting,
                decoration: const InputDecoration(labelText: 'Meeting'),
                items: const [
                  DropdownMenuItem(value: 'AGM', child: Text('Annual General Meeting')),
                  DropdownMenuItem(value: 'SGM', child: Text('Special General Meeting')),
                  DropdownMenuItem(value: 'COMMITTEE', child: Text('Managing Committee')),
                ],
                onChanged: (v) => setS(() => meeting = v ?? meeting),
              ),
              TextButton.icon(
                icon: const Icon(Icons.event_outlined),
                label: Text('Meeting date: ${day(date)}'),
                onPressed: () async {
                  final p = await showDatePicker(context: ctx, initialDate: date, firstDate: DateTime(2000), lastDate: DateTime.now());
                  if (p != null) setS(() => date = p);
                },
              ),
              DropdownButtonFormField<String>(
                initialValue: category,
                decoration: const InputDecoration(labelText: 'What it approves'),
                items: [for (final c in _categories) DropdownMenuItem(value: c, child: Text(titleCase(c)))],
                onChanged: (v) => setS(() => category = v ?? category),
              ),
              TextField(controller: purpose, maxLines: 2, decoration: const InputDecoration(labelText: 'Purpose / text')),
              TextField(controller: amount, keyboardType: TextInputType.number, decoration: const InputDecoration(labelText: 'Approved amount ₹ (optional)')),
              Row(children: [
                Expanded(child: TextField(controller: attendance, keyboardType: TextInputType.number, decoration: const InputDecoration(labelText: 'Present'))),
                const SizedBox(width: 10),
                Expanded(child: TextField(controller: quorum, keyboardType: TextInputType.number, decoration: const InputDecoration(labelText: 'Quorum'))),
              ]),
            ]),
          ),
          actions: [
            TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancel')),
            FilledButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('Save')),
          ],
        ),
      ),
    );
    if (ok != true || !context.mounted) return;
    String two(int v) => v.toString().padLeft(2, '0');
    try {
      await ref.read(legalApiProvider).createResolution({
        'resolution_number': number.text.trim(),
        'meeting_type': meeting,
        'meeting_date': '${date.year}-${two(date.month)}-${two(date.day)}',
        'category': category,
        'purpose': purpose.text.trim(),
        if (amount.text.trim().isNotEmpty) 'approved_amount': amount.text.trim(),
        if (int.tryParse(attendance.text) != null) 'attendance': int.parse(attendance.text),
        if (int.tryParse(quorum.text) != null) 'quorum_required': int.parse(quorum.text),
      });
      invalidateLegal(ref);
    } catch (e) {
      if (context.mounted) showErrorToast(context, e);
    }
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final mayDecide = ref.watch(currentUserProvider)?.isAdminOrCommittee ?? false;
    final async = ref.watch(resolutionsProvider);
    return AppPage(
      title: 'Governance & resolutions',
      subtitle: 'AGM, SGM and Managing Committee decisions the books are checked against',
      maxWidth: 960,
      actions: [
        if (mayDecide) IconButton(tooltip: 'Import from meetings', icon: const Icon(Icons.download_rounded), onPressed: () => _import(context, ref)),
      ],
      floatingActionButton: mayDecide
          ? FloatingActionButton.extended(onPressed: () => _add(context, ref), icon: const Icon(Icons.add_rounded), label: const Text('Resolution'))
          : null,
      body: async.when(
        loading: () => const AppLoader(),
        error: (e, _) => HudErrorState(message: friendlyErrorMessage(e), onRetry: () => ref.invalidate(resolutionsProvider)),
        data: (rows) => rows.isEmpty
            ? const HudEmptyState(icon: Icons.how_to_vote_outlined, title: 'No resolutions recorded',
                subtitle: 'Record the resolutions that approve contracts, fund use, borrowing and budgets.')
            : ListView(padding: const EdgeInsets.fromLTRB(16, 12, 16, 96), children: [
                for (final r in rows)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 10),
                    child: AgentCard(
                      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                        Wrap(spacing: 8, runSpacing: 6, children: [
                          HudChip(label: titleCase(r.status), tone: r.status == 'VERIFIED' ? AppTone.success : AppTone.warning),
                          HudChip(label: r.meetingType, tone: AppTone.neutral),
                          HudChip(label: titleCase(r.category), tone: AppTone.info),
                        ]),
                        const SizedBox(height: 6),
                        Text('${r.number} · ${r.meetingDate == null ? '' : day(r.meetingDate!)}', style: const TextStyle(fontWeight: FontWeight.w700)),
                        const SizedBox(height: 4),
                        Text(r.purpose, maxLines: 4, overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 13)),
                        KeyValue('Authority', titleCase(r.authority)),
                        if (r.amount != null) KeyValue('Approved', formatInr(double.tryParse(r.amount!) ?? 0)),
                        for (final p in r.problems)
                          Text('• $p', style: const TextStyle(fontSize: 12.5, color: Hud.red)),
                        if (mayDecide && r.status == 'RECORDED' && r.problems.isEmpty)
                          Align(
                            alignment: Alignment.centerRight,
                            child: TextButton.icon(
                              icon: const Icon(Icons.verified_outlined),
                              label: const Text('Verify against minutes'),
                              onPressed: () async {
                                try {
                                  await ref.read(legalApiProvider).verifyResolution(r.id);
                                  invalidateLegal(ref);
                                } catch (e) {
                                  if (context.mounted) showErrorToast(context, e);
                                }
                              },
                            ),
                          ),
                      ]),
                    ),
                  ),
              ]),
      ),
    );
  }
}
