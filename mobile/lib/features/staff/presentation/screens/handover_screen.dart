import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/staff/domain/entities/staff_entities.dart';
import 'package:ar_society_app/features/staff/presentation/providers/staff_providers.dart';
import 'package:ar_society_app/features/staff/presentation/widgets/staff_widgets.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';

class HandoverScreen extends ConsumerStatefulWidget {
  final String staffId;
  final String societyId;

  const HandoverScreen({
    super.key,
    required this.staffId,
    required this.societyId,
  });

  @override
  ConsumerState<HandoverScreen> createState() => _HandoverScreenState();
}

class _HandoverScreenState extends ConsumerState<HandoverScreen>
    with SingleTickerProviderStateMixin {
  late final TabController _tabController;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 3, vsync: this);
    WidgetsBinding.instance.addPostFrameCallback((_) {
      ref.read(handoverProvider.notifier).loadHandovers(widget.staffId);
    });
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    ref.listen(handoverProvider, (_, next) {
      if (next is HandoverCreated) {
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
          content: Text('Handover submitted successfully'),
          backgroundColor: AppTheme.success,
          behavior: SnackBarBehavior.floating,
        ));
        ref.read(handoverProvider.notifier).loadHandovers(widget.staffId);
      } else if (next is HandoverError) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(
          content: Text(next.message),
          backgroundColor: AppTheme.error,
          behavior: SnackBarBehavior.floating,
        ));
      }
    });

    return Scaffold(
      backgroundColor: AppTheme.surface,
      appBar: AppBar(
        title: const Text('Handover / Takeover'),
        bottom: TabBar(
          controller: _tabController,
          tabs: const [
            Tab(text: 'Pending'),
            Tab(text: 'History'),
            Tab(text: 'Create'),
          ],
        ),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh_rounded),
            onPressed: () =>
                ref.read(handoverProvider.notifier).loadHandovers(widget.staffId),
          ),
        ],
      ),
      body: TabBarView(
        controller: _tabController,
        children: [
          _PendingTab(staffId: widget.staffId),
          _HistoryTab(staffId: widget.staffId),
          _CreateTab(staffId: widget.staffId, societyId: widget.societyId),
        ],
      ),
    );
  }
}

// ── Pending tab ───────────────────────────────────────────────────────────────

class _PendingTab extends ConsumerWidget {
  final String staffId;
  const _PendingTab({required this.staffId});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(handoverProvider);

    if (state is HandoverLoading) {
      return const Center(child: CircularProgressIndicator(color: AppTheme.primary));
    }

    final pending = state is HandoverLoaded ? state.pending : <HandoverEntity>[];

    if (pending.isEmpty) {
      return const EmptyState(
        icon: Icons.swap_horiz_rounded,
        title: 'No pending handovers',
        subtitle: 'Handovers waiting for your acceptance will appear here',
      );
    }

    return RefreshIndicator(
      onRefresh: () => ref.read(handoverProvider.notifier).loadHandovers(staffId),
      child: ListView.separated(
        padding: const EdgeInsets.all(20),
        itemCount: pending.length,
        separatorBuilder: (_, __) => const SizedBox(height: 12),
        itemBuilder: (_, i) => _HandoverCard(
          handover: pending[i],
          staffId: staffId,
          showActions: true,
        ),
      ),
    );
  }
}

// ── History tab ───────────────────────────────────────────────────────────────

class _HistoryTab extends ConsumerWidget {
  final String staffId;
  const _HistoryTab({required this.staffId});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(handoverProvider);
    final history = state is HandoverLoaded ? state.history : <HandoverEntity>[];

    if (state is HandoverLoading) {
      return const Center(child: CircularProgressIndicator(color: AppTheme.primary));
    }

    if (history.isEmpty) {
      return const EmptyState(
        icon: Icons.history_rounded,
        title: 'No handover history',
        subtitle: 'Your past handovers will appear here',
      );
    }

    return RefreshIndicator(
      onRefresh: () => ref.read(handoverProvider.notifier).loadHandovers(staffId),
      child: ListView.separated(
        padding: const EdgeInsets.all(20),
        itemCount: history.length,
        separatorBuilder: (_, __) => const SizedBox(height: 12),
        itemBuilder: (_, i) => _HandoverCard(
          handover: history[i],
          staffId: staffId,
          showActions: false,
        ),
      ),
    );
  }
}

// ── Handover card ─────────────────────────────────────────────────────────────

class _HandoverCard extends ConsumerWidget {
  final HandoverEntity handover;
  final String staffId;
  final bool showActions;

  const _HandoverCard({
    required this.handover,
    required this.staffId,
    required this.showActions,
  });

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      handover.area ?? 'Shift Handover',
                      style: const TextStyle(
                          fontWeight: FontWeight.w600,
                          fontSize: 15,
                          color: AppTheme.textPrimary),
                    ),
                    const SizedBox(height: 2),
                    Text(
                      _formatDateTime(handover.createdAt),
                      style: const TextStyle(
                          fontSize: 12, color: AppTheme.textSecondary),
                    ),
                  ],
                ),
              ),
              HandoverStatusBadge(status: handover.status),
            ],
          ),
          const SizedBox(height: 12),
          Text(
            handover.summary,
            style: const TextStyle(
                fontSize: 13, color: AppTheme.textSecondary, height: 1.4),
            maxLines: 3,
            overflow: TextOverflow.ellipsis,
          ),
          if (handover.items.isNotEmpty) ...[
            const SizedBox(height: 12),
            Row(
              children: [
                Icon(Icons.list_alt_rounded,
                    size: 14, color: AppTheme.textSecondary),
                const SizedBox(width: 6),
                Text(
                  '${handover.items.length} item${handover.items.length > 1 ? 's' : ''}',
                  style: const TextStyle(
                      fontSize: 12, color: AppTheme.textSecondary),
                ),
                const SizedBox(width: 12),
                if (handover.items.any((i) => i.isUrgent))
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                    decoration: BoxDecoration(
                      color: AppTheme.error.withOpacity(0.1),
                      borderRadius: BorderRadius.circular(6),
                    ),
                    child: const Text('⚠️ Urgent items',
                        style: TextStyle(
                            fontSize: 11,
                            color: AppTheme.error,
                            fontWeight: FontWeight.w600)),
                  ),
              ],
            ),
          ],
          // Items list
          if (handover.items.isNotEmpty) ...[
            const SizedBox(height: 10),
            ...handover.items.take(3).map((item) => Padding(
                  padding: const EdgeInsets.only(bottom: 6),
                  child: Row(
                    children: [
                      Icon(
                        _itemIcon(item.itemType),
                        size: 14,
                        color: item.isUrgent ? AppTheme.error : AppTheme.textSecondary,
                      ),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Text(
                          item.title,
                          style: TextStyle(
                              fontSize: 12,
                              color: item.isUrgent
                                  ? AppTheme.error
                                  : AppTheme.textSecondary),
                        ),
                      ),
                      if (item.quantity != null)
                        Text('×${item.quantity}',
                            style: const TextStyle(
                                fontSize: 12, color: AppTheme.textSecondary)),
                    ],
                  ),
                )),
            if (handover.items.length > 3)
              Text('+${handover.items.length - 3} more',
                  style: const TextStyle(
                      fontSize: 12, color: AppTheme.textSecondary,
                      fontStyle: FontStyle.italic)),
          ],
          // Accept / Dispute buttons
          if (showActions && handover.status == HandoverStatus.submitted) ...[
            const SizedBox(height: 16),
            Row(
              children: [
                Expanded(
                  child: OutlinedButton.icon(
                    onPressed: () => _showDisputeDialog(context, ref),
                    style: OutlinedButton.styleFrom(
                      foregroundColor: AppTheme.error,
                      side: BorderSide(color: AppTheme.error.withOpacity(0.5)),
                    ),
                    icon: const Icon(Icons.flag_outlined, size: 16),
                    label: const Text('Dispute'),
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: ElevatedButton.icon(
                    onPressed: () => _showAcceptDialog(context, ref),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: AppTheme.success,
                    ),
                    icon: const Icon(Icons.check_rounded, size: 16),
                    label: const Text('Accept'),
                  ),
                ),
              ],
            ),
          ],
        ],
      ),
    );
  }

  Future<void> _showAcceptDialog(BuildContext context, WidgetRef ref) async {
    final notesCtrl = TextEditingController();
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Accept Handover?'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Text('Confirm you have received this handover.'),
            const SizedBox(height: 12),
            TextFormField(
              controller: notesCtrl,
              decoration: const InputDecoration(
                labelText: 'Notes (optional)',
                hintText: 'E.g., All keys received, confirmed count',
              ),
              maxLines: 2,
            ),
          ],
        ),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(ctx, false),
              child: const Text('Cancel')),
          ElevatedButton(
              style: ElevatedButton.styleFrom(backgroundColor: AppTheme.success),
              onPressed: () => Navigator.pop(ctx, true),
              child: const Text('Accept')),
        ],
      ),
    );
    if (confirmed == true) {
      await ref.read(handoverProvider.notifier).acceptHandover(
            handover.id,
            staffId,
            notes: notesCtrl.text.trim().isEmpty ? null : notesCtrl.text.trim(),
          );
    }
  }

  Future<void> _showDisputeDialog(BuildContext context, WidgetRef ref) async {
    final reasonCtrl = TextEditingController();
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Dispute Handover?'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Text('Describe the issue with this handover.'),
            const SizedBox(height: 12),
            TextFormField(
              controller: reasonCtrl,
              autofocus: true,
              decoration: const InputDecoration(
                labelText: 'Reason *',
                hintText: 'E.g., Gate keys missing, count mismatch',
              ),
              maxLines: 3,
            ),
          ],
        ),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(ctx, false),
              child: const Text('Cancel')),
          ElevatedButton(
              style: ElevatedButton.styleFrom(backgroundColor: AppTheme.error),
              onPressed: () {
                if (reasonCtrl.text.trim().isEmpty) return;
                Navigator.pop(ctx, true);
              },
              child: const Text('Dispute')),
        ],
      ),
    );
    if (confirmed == true && reasonCtrl.text.trim().isNotEmpty) {
      await ref.read(handoverProvider.notifier).disputeHandover(
            handover.id,
            staffId,
            reasonCtrl.text.trim(),
          );
    }
  }

  IconData _itemIcon(String type) {
    switch (type) {
      case 'key':          return Icons.vpn_key_rounded;
      case 'equipment':    return Icons.build_rounded;
      case 'incident':     return Icons.warning_rounded;
      case 'pending_task': return Icons.task_rounded;
      case 'visitor':      return Icons.person_outline_rounded;
      case 'maintenance':  return Icons.engineering_rounded;
      default:             return Icons.notes_rounded;
    }
  }

  String _formatDateTime(DateTime dt) {
    final months = ['Jan','Feb','Mar','Apr','May','Jun',
                    'Jul','Aug','Sep','Oct','Nov','Dec'];
    final h = dt.hour.toString().padLeft(2, '0');
    final m = dt.minute.toString().padLeft(2, '0');
    return '${dt.day} ${months[dt.month-1]} · $h:$m';
  }
}

// ── Create tab ────────────────────────────────────────────────────────────────

class _CreateTab extends ConsumerStatefulWidget {
  final String staffId;
  final String societyId;
  const _CreateTab({required this.staffId, required this.societyId});

  @override
  ConsumerState<_CreateTab> createState() => _CreateTabState();
}

class _CreateTabState extends ConsumerState<_CreateTab> {
  final _formKey        = GlobalKey<FormState>();
  final _summaryCtrl    = TextEditingController();
  final _areaCtrl       = TextEditingController();
  final _incomingIdCtrl = TextEditingController();
  final List<_HandoverItemDraft> _items = [];

  @override
  void dispose() {
    _summaryCtrl.dispose();
    _areaCtrl.dispose();
    _incomingIdCtrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final isLoading = ref.watch(handoverProvider) is HandoverLoading;

    return SingleChildScrollView(
      padding: const EdgeInsets.all(20),
      child: Form(
        key: _formKey,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            AppCard(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text('Handover Details',
                      style: TextStyle(
                          fontSize: 15,
                          fontWeight: FontWeight.w700,
                          color: AppTheme.textPrimary)),
                  const SizedBox(height: 16),
                  AppTextField(
                    label: 'Area / Location',
                    hint: 'e.g., Main Gate, Lobby, B-Block',
                    controller: _areaCtrl,
                  ),
                  const SizedBox(height: 14),
                  AppTextField(
                    label: 'Handover Summary *',
                    hint: 'Describe the shift situation and key notes',
                    controller: _summaryCtrl,
                    validator: (v) =>
                        (v == null || v.trim().isEmpty) ? 'Summary is required' : null,
                  ),
                  const SizedBox(height: 14),
                  AppTextField(
                    label: 'Incoming Staff ID',
                    hint: 'UUID of incoming staff member',
                    controller: _incomingIdCtrl,
                  ),
                ],
              ),
            ),
            const SizedBox(height: 16),

            // Items
            AppCard(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      const Text('Handover Items',
                          style: TextStyle(
                              fontSize: 15,
                              fontWeight: FontWeight.w700,
                              color: AppTheme.textPrimary)),
                      const Spacer(),
                      TextButton.icon(
                        onPressed: () => _addItem(context),
                        icon: const Icon(Icons.add_rounded, size: 18),
                        label: const Text('Add'),
                      ),
                    ],
                  ),
                  if (_items.isEmpty)
                    Padding(
                      padding: const EdgeInsets.symmetric(vertical: 12),
                      child: Text(
                        'Add keys, pending tasks, incidents, or equipment',
                        style: TextStyle(
                            color: AppTheme.textSecondary, fontSize: 13),
                      ),
                    ),
                  ..._items.asMap().entries.map((e) => _ItemDraftTile(
                        item: e.value,
                        onRemove: () => setState(() => _items.removeAt(e.key)),
                      )),
                ],
              ),
            ),
            const SizedBox(height: 24),

            AppPrimaryButton(
              label: 'Submit Handover',
              isLoading: isLoading,
              icon: Icons.send_rounded,
              onPressed: _submit,
            ),
          ],
        ),
      ),
    );
  }

  Future<void> _addItem(BuildContext context) async {
    final draft = await showModalBottomSheet<_HandoverItemDraft>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (_) => const _AddItemSheet(),
    );
    if (draft != null) setState(() => _items.add(draft));
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    await ref.read(handoverProvider.notifier).createAndSubmit(
      societyId: widget.societyId,
      outgoingStaffId: widget.staffId,
      incomingStaffId: _incomingIdCtrl.text.trim().isEmpty
          ? null
          : _incomingIdCtrl.text.trim(),
      area: _areaCtrl.text.trim().isEmpty ? null : _areaCtrl.text.trim(),
      summary: _summaryCtrl.text.trim(),
      items: _items.map((i) => i.toJson()).toList(),
    );
    // Reset form on success
    if (mounted) {
      _summaryCtrl.clear();
      _areaCtrl.clear();
      _incomingIdCtrl.clear();
      setState(() => _items.clear());
    }
  }
}

class _HandoverItemDraft {
  final String type;
  final String title;
  final bool isUrgent;
  final int? quantity;

  _HandoverItemDraft({
    required this.type,
    required this.title,
    required this.isUrgent,
    this.quantity,
  });

  Map<String, dynamic> toJson() => {
    'item_type': type,
    'title': title,
    'is_urgent': isUrgent,
    if (quantity != null) 'quantity': quantity,
  };
}

class _ItemDraftTile extends StatelessWidget {
  final _HandoverItemDraft item;
  final VoidCallback onRemove;
  const _ItemDraftTile({required this.item, required this.onRemove});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(top: 8),
      child: Row(
        children: [
          Icon(
            item.isUrgent ? Icons.warning_rounded : Icons.check_box_outline_blank,
            size: 16,
            color: item.isUrgent ? AppTheme.error : AppTheme.textSecondary,
          ),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              '${item.type.replaceAll('_', ' ')} · ${item.title}',
              style: const TextStyle(fontSize: 13, color: AppTheme.textPrimary),
            ),
          ),
          if (item.quantity != null)
            Text('×${item.quantity}',
                style: const TextStyle(
                    fontSize: 12, color: AppTheme.textSecondary)),
          const SizedBox(width: 8),
          GestureDetector(
            onTap: onRemove,
            child: const Icon(Icons.close_rounded,
                size: 18, color: AppTheme.textSecondary),
          ),
        ],
      ),
    );
  }
}

// ── Add item bottom sheet ─────────────────────────────────────────────────────

class _AddItemSheet extends StatefulWidget {
  const _AddItemSheet();

  @override
  State<_AddItemSheet> createState() => _AddItemSheetState();
}

class _AddItemSheetState extends State<_AddItemSheet> {
  final _titleCtrl = TextEditingController();
  final _qtyCtrl   = TextEditingController();
  String _type     = 'key';
  bool _isUrgent   = false;

  final _types = [
    ('key', 'Key', Icons.vpn_key_rounded),
    ('equipment', 'Equipment', Icons.build_rounded),
    ('pending_task', 'Pending Task', Icons.task_rounded),
    ('incident', 'Incident', Icons.warning_rounded),
    ('visitor', 'Visitor', Icons.person_outline_rounded),
    ('remark', 'Remark', Icons.notes_rounded),
  ];

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: EdgeInsets.only(
        left: 20, right: 20, top: 20,
        bottom: MediaQuery.of(context).viewInsets.bottom + 20,
      ),
      decoration: const BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('Add Handover Item',
              style: TextStyle(
                  fontSize: 16, fontWeight: FontWeight.w700,
                  color: AppTheme.textPrimary)),
          const SizedBox(height: 16),
          // Type selector
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: _types.map((t) {
              final selected = _type == t.$1;
              return ChoiceChip(
                label: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(t.$3, size: 14,
                        color: selected ? Colors.white : AppTheme.textSecondary),
                    const SizedBox(width: 4),
                    Text(t.$2),
                  ],
                ),
                selected: selected,
                onSelected: (_) => setState(() => _type = t.$1),
                selectedColor: AppTheme.primary,
                labelStyle: TextStyle(
                    color: selected ? Colors.white : AppTheme.textPrimary,
                    fontSize: 12),
              );
            }).toList(),
          ),
          const SizedBox(height: 14),
          TextFormField(
            controller: _titleCtrl,
            autofocus: true,
            decoration: const InputDecoration(labelText: 'Description *'),
          ),
          const SizedBox(height: 12),
          Row(
            children: [
              Expanded(
                child: TextFormField(
                  controller: _qtyCtrl,
                  keyboardType: TextInputType.number,
                  decoration: const InputDecoration(
                      labelText: 'Quantity (optional)'),
                ),
              ),
              const SizedBox(width: 12),
              Row(
                children: [
                  Checkbox(
                    value: _isUrgent,
                    onChanged: (v) => setState(() => _isUrgent = v!),
                    activeColor: AppTheme.error,
                  ),
                  const Text('Urgent',
                      style: TextStyle(fontSize: 13, color: AppTheme.textSecondary)),
                ],
              ),
            ],
          ),
          const SizedBox(height: 20),
          AppPrimaryButton(
            label: 'Add Item',
            onPressed: () {
              if (_titleCtrl.text.trim().isEmpty) return;
              Navigator.pop(context, _HandoverItemDraft(
                type: _type,
                title: _titleCtrl.text.trim(),
                isUrgent: _isUrgent,
                quantity: int.tryParse(_qtyCtrl.text),
              ));
            },
          ),
        ],
      ),
    );
  }
}
