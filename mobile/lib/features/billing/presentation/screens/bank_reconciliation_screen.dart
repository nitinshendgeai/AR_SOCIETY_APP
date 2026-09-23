import 'dart:io';
import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/features/billing/domain/entities/billing_entities.dart';
import 'package:ar_society_app/features/billing/presentation/providers/billing_providers.dart';

/// FMC Manager/Admin/Committee: import a bank statement (CSV) and match
/// its credit rows against payments residents said they made, closing the
/// loop that update_online_payment_status() alone can't — a manual
/// "Reconciled" tap without ever checking the statement is just trust,
/// not reconciliation.
class BankReconciliationScreen extends ConsumerStatefulWidget {
  const BankReconciliationScreen({super.key});

  @override
  ConsumerState<BankReconciliationScreen> createState() => _BankReconciliationScreenState();
}

class _BankReconciliationScreenState extends ConsumerState<BankReconciliationScreen> {
  String? _statusFilter;
  bool _importing = false;

  Future<void> _importStatement(String societyId) async {
    final result = await FilePicker.platform.pickFiles(
      type: FileType.custom,
      allowedExtensions: ['csv'],
      withData: true,
    );
    final picked = result?.files.single;
    if (picked == null) return;

    final bytes = picked.bytes ?? (picked.path != null ? await File(picked.path!).readAsBytes() : null);
    if (bytes == null) return;

    setState(() => _importing = true);
    try {
      final imported = await ref
          .read(bankStatementEntriesProvider(societyId).notifier)
          .importStatement(csvBytes: bytes, fileName: picked.name);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(
          content: Text('Imported ${imported.length} row${imported.length == 1 ? '' : 's'} from the statement'),
          backgroundColor: AppTheme.success,
        ));
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(
            content: Text(friendlyErrorMessage(e)), backgroundColor: AppTheme.error));
      }
    } finally {
      if (mounted) setState(() => _importing = false);
    }
  }

  Future<void> _openEntry(BankStatementEntryEntity entry) async {
    if (!entry.isUnmatched) {
      showDialog(
        context: context,
        builder: (ctx) => AlertDialog(
          title: Text(entry.isMatched ? 'Matched' : 'Ignored'),
          content: Text(entry.isMatched
              ? 'Linked to receipt ${entry.matchedSubmissionReceiptNumber ?? '-'}.'
              : (entry.ignoreReason?.isNotEmpty == true ? entry.ignoreReason! : 'No reason recorded.')),
          actions: [TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Close'))],
        ),
      );
      return;
    }
    await showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (_) => _MatchEntrySheet(entry: entry),
    );
  }

  @override
  Widget build(BuildContext context) {
    final societyId = ref.watch(currentUserProvider)?.societyId;
    if (societyId == null) {
      return const Scaffold(body: Center(child: Text('No society context')));
    }
    final entriesAsync = ref.watch(bankStatementEntriesProvider(societyId));

    return Scaffold(
      backgroundColor: AppTheme.surface,
      appBar: AppBar(
        title: const Text('Bank Reconciliation'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh_rounded),
            onPressed: () => ref.read(bankStatementEntriesProvider(societyId).notifier).refresh(),
          ),
        ],
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: _importing ? null : () => _importStatement(societyId),
        icon: _importing
            ? const SizedBox(width: 18, height: 18,
                child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
            : const Icon(Icons.upload_file_rounded),
        label: Text(_importing ? 'Importing…' : 'Import Statement'),
      ),
      body: Column(
        children: [
          Container(
            padding: const EdgeInsets.fromLTRB(16, 12, 16, 0),
            child: Row(children: [
              Icon(Icons.info_outline_rounded, size: 16, color: AppTheme.textSecondary),
              const SizedBox(width: 6),
              Expanded(
                child: Text(
                  'CSV needs columns: Date, Description, Amount (Reference optional)',
                  style: TextStyle(fontSize: 11, color: AppTheme.textSecondary),
                ),
              ),
            ]),
          ),
          SizedBox(
            height: 48,
            child: ListView(
              scrollDirection: Axis.horizontal,
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
              children: [
                _FilterChip(label: 'All', selected: _statusFilter == null,
                    onTap: () => setState(() => _statusFilter = null)),
                for (final s in const ['unmatched', 'matched', 'ignored'])
                  Padding(
                    padding: const EdgeInsets.only(left: 8),
                    child: _FilterChip(
                      label: bankMatchStatusLabel(s), selected: _statusFilter == s,
                      onTap: () => setState(() => _statusFilter = s),
                    ),
                  ),
              ],
            ),
          ),
          Expanded(
            child: entriesAsync.when(
              loading: () => const Center(child: CircularProgressIndicator()),
              error: (e, _) => Center(
                  child: Text(friendlyErrorMessage(e), style: const TextStyle(color: AppTheme.error))),
              data: (entries) {
                final filtered = _statusFilter == null
                    ? entries
                    : entries.where((e) => e.matchStatus == _statusFilter).toList();
                if (filtered.isEmpty) {
                  return const Center(
                    child: Padding(
                      padding: EdgeInsets.all(24),
                      child: Text(
                        'No statement rows yet. Tap "Import Statement" to bring in your bank\'s '
                        'transactions and match them against pending payments.',
                        textAlign: TextAlign.center,
                        style: TextStyle(color: AppTheme.textSecondary),
                      ),
                    ),
                  );
                }
                return RefreshIndicator(
                  onRefresh: () => ref.read(bankStatementEntriesProvider(societyId).notifier).refresh(),
                  child: ListView.builder(
                    padding: const EdgeInsets.fromLTRB(16, 8, 16, 88),
                    itemCount: filtered.length,
                    itemBuilder: (_, i) => _EntryCard(entry: filtered[i], onTap: () => _openEntry(filtered[i])),
                  ),
                );
              },
            ),
          ),
        ],
      ),
    );
  }
}

class _FilterChip extends StatelessWidget {
  final String label;
  final bool selected;
  final VoidCallback onTap;
  const _FilterChip({required this.label, required this.selected, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return ChoiceChip(
      label: Text(label, style: const TextStyle(fontSize: 12)),
      selected: selected,
      onSelected: (_) => onTap(),
      selectedColor: AppTheme.primary.withOpacity(0.15),
      labelStyle: TextStyle(color: selected ? AppTheme.primary : AppTheme.textSecondary),
    );
  }
}

class _EntryCard extends StatelessWidget {
  final BankStatementEntryEntity entry;
  final VoidCallback onTap;
  const _EntryCard({required this.entry, required this.onTap});

  Color get _statusColor => switch (entry.matchStatus) {
        'matched' => AppTheme.success,
        'ignored' => AppTheme.textSecondary,
        _ => AppTheme.warning,
      };

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      child: ListTile(
        onTap: onTap,
        title: Text('₹${entry.amount} — ${entry.description}',
            maxLines: 1, overflow: TextOverflow.ellipsis,
            style: const TextStyle(fontWeight: FontWeight.w600)),
        subtitle: Text(
            '${entry.txnDate.day}/${entry.txnDate.month}/${entry.txnDate.year}'
            '${entry.reference != null ? ' · Ref ${entry.reference}' : ''}'),
        trailing: Chip(
          label: Text(bankMatchStatusLabel(entry.matchStatus),
              style: TextStyle(fontSize: 11, color: _statusColor)),
          backgroundColor: _statusColor.withOpacity(0.12),
          side: BorderSide.none,
        ),
      ),
    );
  }
}

/// Bottom sheet for one unmatched entry: shows suggested PENDING payment
/// candidates (same amount, nearby date) to confirm, plus an ignore action
/// for rows that aren't a resident payment at all (bank interest, charges).
class _MatchEntrySheet extends ConsumerStatefulWidget {
  final BankStatementEntryEntity entry;
  const _MatchEntrySheet({required this.entry});

  @override
  ConsumerState<_MatchEntrySheet> createState() => _MatchEntrySheetState();
}

class _MatchEntrySheetState extends ConsumerState<_MatchEntrySheet> {
  bool _busy = false;

  Future<void> _confirm(String submissionId, String societyId) async {
    setState(() => _busy = true);
    try {
      await ref.read(bankStatementEntriesProvider(societyId).notifier)
          .confirmMatch(widget.entry.id, submissionId);
      if (mounted) {
        Navigator.pop(context);
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
            content: Text('Payment reconciled'), backgroundColor: AppTheme.success));
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text(friendlyErrorMessage(e)), backgroundColor: AppTheme.error));
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _ignore(String societyId) async {
    final controller = TextEditingController();
    final reason = await showDialog<String>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Ignore this row?'),
        content: TextField(
          controller: controller,
          maxLines: 2,
          decoration: const InputDecoration(
              labelText: 'Reason (optional)', hintText: 'e.g. bank interest, not a resident payment'),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Cancel')),
          ElevatedButton(
            style: ElevatedButton.styleFrom(backgroundColor: AppTheme.warning),
            onPressed: () => Navigator.pop(ctx, controller.text.trim()),
            child: const Text('Ignore'),
          ),
        ],
      ),
    );
    if (reason == null) return;
    setState(() => _busy = true);
    try {
      await ref.read(bankStatementEntriesProvider(societyId).notifier)
          .ignoreEntry(widget.entry.id, reason: reason.isEmpty ? null : reason);
      if (mounted) Navigator.pop(context);
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text(friendlyErrorMessage(e)), backgroundColor: AppTheme.error));
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final societyId = ref.watch(currentUserProvider)?.societyId ?? '';
    final candidatesAsync = ref.watch(bankMatchCandidatesProvider(widget.entry.id));

    return DraggableScrollableSheet(
      initialChildSize: 0.6,
      minChildSize: 0.4,
      maxChildSize: 0.9,
      expand: false,
      builder: (context, scrollController) => Container(
        decoration: const BoxDecoration(
          color: AppTheme.cardBg,
          borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
        ),
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('₹${widget.entry.amount}',
                style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w700)),
            const SizedBox(height: 2),
            Text(widget.entry.description, style: const TextStyle(color: AppTheme.textSecondary)),
            Text(
                '${widget.entry.txnDate.day}/${widget.entry.txnDate.month}/${widget.entry.txnDate.year}'
                '${widget.entry.reference != null ? ' · Ref ${widget.entry.reference}' : ''}',
                style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
            const SizedBox(height: 16),
            const Text('Suggested matches', style: TextStyle(fontWeight: FontWeight.w700, fontSize: 14)),
            const SizedBox(height: 8),
            Expanded(
              child: candidatesAsync.when(
                loading: () => const Center(child: CircularProgressIndicator()),
                error: (e, _) => Text(friendlyErrorMessage(e), style: const TextStyle(color: AppTheme.error)),
                data: (candidates) {
                  if (candidates.isEmpty) {
                    return const Center(
                      child: Text(
                        'No pending payment found with this amount within 5 days of this date.',
                        textAlign: TextAlign.center,
                        style: TextStyle(color: AppTheme.textSecondary, fontSize: 13),
                      ),
                    );
                  }
                  return ListView.builder(
                    controller: scrollController,
                    itemCount: candidates.length,
                    itemBuilder: (_, i) {
                      final c = candidates[i];
                      return Card(
                        margin: const EdgeInsets.only(bottom: 8),
                        child: ListTile(
                          title: Text('${c.receiptNumber} — ${c.wingName ?? ''} ${c.flatNumber ?? ''}'.trim()),
                          subtitle: Text(
                              '${paymentModeLabel(c.paymentMode)} · '
                              '${c.paymentDate.day}/${c.paymentDate.month}/${c.paymentDate.year}'),
                          trailing: ElevatedButton(
                            onPressed: _busy ? null : () => _confirm(c.id, societyId),
                            child: const Text('Confirm'),
                          ),
                        ),
                      );
                    },
                  );
                },
              ),
            ),
            const SizedBox(height: 12),
            SizedBox(
              width: double.infinity,
              child: OutlinedButton.icon(
                onPressed: _busy ? null : () => _ignore(societyId),
                icon: const Icon(Icons.block_rounded, size: 18),
                label: const Text('Not a resident payment — ignore'),
                style: OutlinedButton.styleFrom(foregroundColor: AppTheme.warning),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
