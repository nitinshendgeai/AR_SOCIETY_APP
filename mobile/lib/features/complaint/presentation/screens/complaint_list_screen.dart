import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/complaint/domain/entities/complaint_entities.dart';
import 'package:ar_society_app/features/complaint/presentation/providers/complaint_providers.dart';
import 'package:ar_society_app/features/staff/presentation/widgets/staff_widgets.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';

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
        borderRadius: BorderRadius.circular(20),
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

  const _ComplaintListTile({required this.complaint, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return AppCard(
      onTap: onTap,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Text(
                '#${complaint.complaintNumber}',
                style: const TextStyle(
                  fontSize: 12,
                  fontWeight: FontWeight.w600,
                  color: AppTheme.primary,
                ),
              ),
              const Spacer(),
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
}

// ── Complaint list screen ─────────────────────────────────────────────────────

class ComplaintListScreen extends ConsumerStatefulWidget {
  final bool isMy;
  final String? societyId;

  const ComplaintListScreen({
    super.key,
    required this.isMy,
    this.societyId,
  });

  @override
  ConsumerState<ComplaintListScreen> createState() =>
      _ComplaintListScreenState();
}

class _ComplaintListScreenState extends ConsumerState<ComplaintListScreen> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _load());
  }

  Future<void> _load() async {
    if (widget.isMy) {
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

    return Scaffold(
      backgroundColor: AppTheme.surface,
      appBar: AppBar(
        title: Text(widget.isMy ? 'My Complaints' : 'Society Complaints'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh_rounded),
            onPressed: _load,
          ),
        ],
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () {
          final sid = widget.societyId ?? '';
          context.push('/complaints/create?societyId=$sid');
        },
        backgroundColor: AppTheme.primary,
        foregroundColor: Colors.white,
        icon: const Icon(Icons.add_rounded),
        label: const Text('New Complaint'),
      ),
      body: RefreshIndicator(
        onRefresh: _load,
        child: _buildBody(state),
      ),
    );
  }

  Widget _buildBody(ComplaintListState state) {
    if (state is ComplaintListLoading) {
      return const Center(
        child: CircularProgressIndicator(color: AppTheme.primary),
      );
    }
    if (state is ComplaintListError) {
      return SingleChildScrollView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.all(16),
        child: Column(
          children: [
            AppErrorBanner(message: state.message),
            const SizedBox(height: 12),
            TextButton(onPressed: _load, child: const Text('Retry')),
          ],
        ),
      );
    }
    if (state is ComplaintListLoaded) {
      if (state.complaints.isEmpty) {
        return SingleChildScrollView(
          physics: const AlwaysScrollableScrollPhysics(),
          child: EmptyState(
            icon: Icons.inbox_rounded,
            title: widget.isMy ? 'No complaints yet' : 'No complaints',
            subtitle: widget.isMy
                ? 'Tap + to raise a new complaint'
                : 'No complaints have been raised in this society',
          ),
        );
      }
      return ListView.separated(
        padding: const EdgeInsets.all(16),
        itemCount: state.complaints.length,
        separatorBuilder: (_, __) => const SizedBox(height: 10),
        itemBuilder: (_, i) {
          final c = state.complaints[i];
          return _ComplaintListTile(
            complaint: c,
            onTap: () => context.push('/complaints/${c.id}'),
          );
        },
      );
    }
    return const SizedBox.shrink();
  }
}
