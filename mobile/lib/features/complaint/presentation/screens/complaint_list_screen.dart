import 'package:flutter/material.dart';
import 'package:ar_society_app/core/l10n/app_locale.dart';
import 'package:ar_society_app/core/motion/loading.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/features/complaint/domain/entities/complaint_entities.dart';
import 'package:ar_society_app/features/complaint/presentation/providers/complaint_providers.dart';
import 'package:ar_society_app/features/complaint/presentation/widgets/complaint_progress.dart';
import 'package:ar_society_app/features/staff/presentation/widgets/staff_widgets.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';
import 'package:ar_society_app/shared/widgets/app_data_table.dart';
import 'package:ar_society_app/core/layout/app_shell.dart' show isDesktopLayout;
import 'package:ar_society_app/shared/widgets/app_form.dart';

// ── Status badge ──────────────────────────────────────────────────────────────

class _StatusBadge extends StatelessWidget {
  final ComplaintStatus status;
  const _StatusBadge(this.status);

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: status.color.withOpacity(0.12),
        borderRadius: BorderRadius.circular(AppTheme.radiusXl),
        border: Border.all(color: status.color.withOpacity(0.3)),
      ),
      child: Text(
        status.label,
        style: TextStyle(
          color: status.color,
          fontSize: 11,
          fontWeight: FontWeight.w600,
        ),
      ),
    );
  }
}

// ── Priority badge ────────────────────────────────────────────────────────────

class _PriorityBadge extends StatelessWidget {
  final ComplaintPriority priority;
  const _PriorityBadge(this.priority);

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: priority.color.withOpacity(0.10),
        borderRadius: BorderRadius.circular(6),
      ),
      child: Text(
        priority.label,
        style: TextStyle(
          color: priority.color,
          fontSize: 11,
          fontWeight: FontWeight.w600,
        ),
      ),
    );
  }
}

// ── Category chip ─────────────────────────────────────────────────────────────

class _CategoryChip extends StatelessWidget {
  final ComplaintCategory category;
  const _CategoryChip(this.category);

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: AppTheme.border,
        borderRadius: BorderRadius.circular(6),
      ),
      child: Text(
        category.label,
        style: const TextStyle(
          color: AppTheme.textSecondary,
          fontSize: 11,
          fontWeight: FontWeight.w500,
        ),
      ),
    );
  }
}

// ── Complaint list tile ───────────────────────────────────────────────────────

class _ComplaintListTile extends StatelessWidget {
  final ComplaintListEntity complaint;
  final VoidCallback onTap;

  /// A resident's own list says where each complaint stands in a line under the title.
  final bool showNote;

  const _ComplaintListTile({required this.complaint, required this.onTap, this.showNote = false});

  @override
  Widget build(BuildContext context) {
    return AppCard(
      onTap: onTap,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  _numberWithFlat(complaint),
                  style: const TextStyle(
                    fontSize: 12,
                    fontWeight: FontWeight.w600,
                    color: AppTheme.primary,
                  ),
                  overflow: TextOverflow.ellipsis,
                ),
              ),
              const SizedBox(width: 8),
              _StatusBadge(complaint.status),
            ],
          ),
          const SizedBox(height: 6),
          Text(
            complaint.title,
            style: const TextStyle(
              fontSize: 14,
              fontWeight: FontWeight.w600,
              color: AppTheme.textPrimary,
            ),
            maxLines: 2,
            overflow: TextOverflow.ellipsis,
          ),
          if (showNote) ...[
            const SizedBox(height: 4),
            Text(
              complaintListNote(complaint, DateTime.now()),
              style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: complaint.status.color),
            ),
          ],
          const SizedBox(height: 8),
          Row(
            children: [
              _CategoryChip(complaint.category),
              const SizedBox(width: 6),
              _PriorityBadge(complaint.priority),
              const Spacer(),
              Text(
                _formatDate(complaint.createdAt),
                style: const TextStyle(
                  fontSize: 11,
                  color: AppTheme.textSecondary,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  String _formatDate(DateTime dt) {
    const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                    'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    return '${dt.day} ${months[dt.month - 1]}';
  }

  String _numberWithFlat(ComplaintListEntity c) {
    final flat = [
      if (c.wingName != null) c.wingName,
      if (c.flatNumber != null) c.flatNumber,
    ].join(' — ');
    return flat.isEmpty ? '#${c.complaintNumber}' : '#${c.complaintNumber} · $flat';
  }
}

// ── Complaint list screen ─────────────────────────────────────────────────────

class ComplaintListScreen extends ConsumerStatefulWidget {
  final bool isMy;
  final String? societyId;
  final bool assignedToMe;

  const ComplaintListScreen({
    super.key,
    required this.isMy,
    this.societyId,
    this.assignedToMe = false,
  });

  @override
  ConsumerState<ComplaintListScreen> createState() =>
      _ComplaintListScreenState();
}

class _ComplaintListScreenState extends ConsumerState<ComplaintListScreen> {
  // Desktop table toolbar (client-side over the loaded list).
  String _query = '';
  ComplaintStatus? _statusFilter;

  // Complaints still being dealt with, or the finished ones: a resident's own list and the society's list.
  // "Active" is the very set the dashboards count as open, so the number on a dashboard is the number here.
  bool _showDone = false;

  Future<void> _newComplaint() async {
    final sid = (widget.societyId?.isNotEmpty == true)
        ? widget.societyId!
        : ref.read(currentUserProvider)?.societyId ?? '';
    // CreateComplaintScreen pops with `true` on a successful submit —
    // this screen isn't rebuilt by that pop (it's the same widget
    // instance, not re-pushed), so without this the newly created
    // complaint wouldn't appear until a manual pull-to-refresh.
    final created = await context.push<bool>('/complaints/create?societyId=$sid');
    if (created == true) _load();
  }

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _load());
  }

  Future<void> _load() async {
    if (widget.assignedToMe) {
      await ref.read(complaintListProvider.notifier).loadAssignedToMe();
    } else if (widget.isMy) {
      await ref.read(complaintListProvider.notifier).loadMyComplaints();
    } else if (widget.societyId != null) {
      await ref
          .read(complaintListProvider.notifier)
          .loadSocietyComplaints(widget.societyId!);
    }
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(complaintListProvider);
    final desktop = isDesktopLayout(context);

    return AppPage(
      title: widget.assignedToMe
            ? 'Assigned to Me'
            : widget.isMy
                ? 'My Complaints'
                : 'Society Complaints',
      actions: [
          IconButton(
            icon: const Icon(Icons.refresh_rounded),
            tooltip: 'Refresh',
            onPressed: _load,
          ),
          if (desktop)
            HeaderActionButton(icon: Icons.add_rounded, label: 'New Complaint', onPressed: _newComplaint),
        ],
      floatingActionButton: desktop
          ? null
          : FloatingActionButton.extended(
              onPressed: _newComplaint,
              backgroundColor: AppTheme.primary,
              foregroundColor: Colors.white,
              icon: const Icon(Icons.add_rounded),
              label: Text(context.tr('New Complaint')),
            ),
      body: RefreshIndicator(
        onRefresh: _load,
        child: desktop ? _table(state) : _buildBody(state),
      ),
    );
  }

  /// Desktop: complaints as a sortable table with search and a status filter.
  Widget _table(ComplaintListState state) {
    final all = state is ComplaintListLoaded ? state.complaints : const <ComplaintListEntity>[];
    final q = _query.trim().toLowerCase();
    final rows = all.where((c) {
      if (_statusFilter != null && c.status != _statusFilter) return false;
      if (q.isEmpty) return true;
      return c.title.toLowerCase().contains(q) ||
          c.complaintNumber.toLowerCase().contains(q) ||
          (c.flatNumber ?? '').toLowerCase().contains(q);
    }).toList();

    return ListView(padding: const EdgeInsets.fromLTRB(24, 8, 24, 32), children: [
      AppDataTable<ComplaintListEntity>(
        toolbar: Row(crossAxisAlignment: CrossAxisAlignment.end, children: [
          TableSearchField(
            hint: 'Search number, title, flat…',
            onChanged: (v) => setState(() => _query = v),
          ),
          const SizedBox(width: 12),
          SizedBox(
            width: 200,
            child: FormFieldBox(label: 'Status', child: DropdownButtonFormField<ComplaintStatus?>(
              initialValue: _statusFilter,
              isDense: true,
              decoration: const InputDecoration(),
              items: [
                DropdownMenuItem(value: null, child: Text(context.tr('All statuses'))),
                for (final st in ComplaintStatus.values) DropdownMenuItem(value: st, child: Text(st.label)),
              ],
              onChanged: (v) => setState(() => _statusFilter = v),
            )),
          ),
          const Spacer(),
          Text('${rows.length} of ${all.length}',
              style: const TextStyle(fontSize: 12.5, color: AppTheme.textSecondary)),
        ]),
        rows: rows,
        loading: state is ComplaintListLoading || state is ComplaintListInitial,
        error: state is ComplaintListError ? state.message : null,
        onRetry: _load,
        onRowTap: (c) => context.push('/complaints/${c.id}'),
        empty: const EmptyState(icon: Icons.inbox_rounded, title: 'No complaints'),
        columns: [
          AppDataColumn.text('No.', (c) => '#${c.complaintNumber}', width: 150, bold: true),
          AppDataColumn.text('Title', (c) => c.title, flex: 4),
          AppDataColumn.text('Flat', (c) => [
                if (c.wingName != null) c.wingName,
                if (c.flatNumber != null) c.flatNumber,
              ].join(' — ').ifEmpty('—'), flex: 3),
          AppDataColumn(
            label: 'Category',
            width: 120,
            sortKey: (c) => c.category.label,
            cell: (c) => _CategoryChip(c.category),
          ),
          AppDataColumn(
            label: 'Priority',
            width: 90,
            sortKey: (c) => c.priority.index,
            cell: (c) => _PriorityBadge(c.priority),
          ),
          AppDataColumn.text('Assigned to', (c) => c.assignedToName ?? 'Unassigned', flex: 3),
          AppDataColumn.text('Raised', (c) => tableDate(c.createdAt),
              width: 110, sortKey: (c) => c.createdAt.millisecondsSinceEpoch),
          AppDataColumn(
            label: 'Status',
            width: 110,
            sortKey: (c) => c.status.label,
            cell: (c) => _StatusBadge(c.status),
          ),
        ],
      ),
    ]);
  }

  Widget _buildBody(ComplaintListState state) {
    if (state is ComplaintListLoading) {
      return const SkeletonList();
    }
    if (state is ComplaintListError) {
      return AppErrorState(message: state.message, onRetry: _load);
    }
    if (state is ComplaintListLoaded) {
      if (state.complaints.isEmpty) {
        return SingleChildScrollView(
          physics: const AlwaysScrollableScrollPhysics(),
          child: EmptyState(
            icon: Icons.inbox_rounded,
            title: widget.assignedToMe
                ? 'Nothing assigned to you'
                : widget.isMy
                    ? 'No complaints yet'
                    : 'No complaints',
            subtitle: widget.assignedToMe
                ? 'Complaints assigned to you will show up here'
                : widget.isMy
                    ? 'Tap "New Complaint" to raise one'
                    : 'No complaints have been raised in this society',
          ),
        );
      }
      final split = !widget.assignedToMe;
      final all = state.complaints;
      final active = all.where((c) => complaintIsActive(c.status)).toList();
      final done = all.where((c) => !complaintIsActive(c.status)).toList();
      final shown = split ? (_showDone ? done : active) : all;
      final chips = split
          ? Padding(
              padding: const EdgeInsets.only(bottom: 4),
              child: Wrap(spacing: 8, children: [
                AppFilterPill(
                  label: 'Active (${active.length})',
                  selected: !_showDone,
                  onTap: () => setState(() => _showDone = false),
                ),
                AppFilterPill(
                  label: 'Done (${done.length})',
                  selected: _showDone,
                  onTap: () => setState(() => _showDone = true),
                ),
              ]),
            )
          : null;
      if (split && shown.isEmpty) {
        return SingleChildScrollView(
          physics: const AlwaysScrollableScrollPhysics(),
          padding: const EdgeInsets.fromLTRB(16, 16, 16, 96),
          child: Column(children: [
            chips!,
            EmptyState(
              icon: _showDone ? Icons.history_rounded : Icons.check_circle_outline_rounded,
              title: _showDone ? 'Nothing finished yet' : 'Nothing pending',
              subtitle: _showDone
                  ? 'Complaints that are resolved, closed or rejected appear here'
                  : widget.isMy
                      ? 'All your complaints are sorted. Tap "New Complaint" to raise one'
                      : 'No complaint in the society is waiting for attention',
            ),
          ]),
        );
      }
      return ListView.separated(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.fromLTRB(16, 16, 16, 96),
        itemCount: shown.length + (chips == null ? 0 : 1),
        separatorBuilder: (_, __) => const SizedBox(height: 10),
        itemBuilder: (_, i) {
          if (chips != null && i == 0) return chips;
          final c = shown[i - (chips == null ? 0 : 1)];
          return _ComplaintListTile(
            complaint: c,
            showNote: widget.isMy,
            onTap: () => context.push('/complaints/${c.id}'),
          );
        },
      );
    }
    return const SizedBox.shrink();
  }
}

extension on String {
  String ifEmpty(String fallback) => isEmpty ? fallback : this;
}
