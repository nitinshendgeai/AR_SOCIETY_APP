import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/visitor/domain/entities/visitor_entities.dart';
import 'package:ar_society_app/features/visitor/presentation/providers/visitor_providers.dart';
import 'package:ar_society_app/features/staff/presentation/widgets/staff_widgets.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';

/// Resident's screen: visitors waiting for their approval.
class VisitorApprovalsScreen extends ConsumerStatefulWidget {
  const VisitorApprovalsScreen({super.key});

  @override
  ConsumerState<VisitorApprovalsScreen> createState() => _VisitorApprovalsScreenState();
}

class _VisitorApprovalsScreenState extends ConsumerState<VisitorApprovalsScreen> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      ref.read(visitorListProvider.notifier).loadPendingApprovals();
    });
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(visitorListProvider);

    ref.listen(visitorActionProvider, (_, next) {
      if (next is VisitorActionSuccess) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(
          content: Text(next.message),
          backgroundColor: AppTheme.success,
          behavior: SnackBarBehavior.floating,
        ));
        ref.read(visitorListProvider.notifier).loadPendingApprovals();
        ref.read(visitorActionProvider.notifier).reset();
      } else if (next is VisitorActionError) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(
          content: Text(next.message),
          backgroundColor: AppTheme.error,
          behavior: SnackBarBehavior.floating,
        ));
        ref.read(visitorActionProvider.notifier).reset();
      }
    });

    return Scaffold(
      backgroundColor: AppTheme.surface,
      appBar: AppBar(
        title: const Text('Pending Approvals'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh_rounded),
            onPressed: () =>
                ref.read(visitorListProvider.notifier).loadPendingApprovals(),
          ),
        ],
      ),
      body: _buildBody(state),
    );
  }

  Widget _buildBody(VisitorListState state) {
    if (state is VisitorListLoading) {
      return const Center(child: CircularProgressIndicator(color: AppTheme.primary));
    }
    if (state is VisitorListError) {
      return Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            AppErrorBanner(message: state.message),
            const SizedBox(height: 12),
            TextButton(
              onPressed: () =>
                  ref.read(visitorListProvider.notifier).loadPendingApprovals(),
              child: const Text('Retry'),
            ),
          ],
        ),
      );
    }

    final visitors = state is VisitorListLoaded ? state.visitors : <VisitorEntity>[];
    if (visitors.isEmpty) {
      return const EmptyState(
        icon: Icons.how_to_reg_rounded,
        title: 'No pending approvals',
        subtitle: 'You\'ll be notified when a visitor arrives for your flat',
      );
    }

    return RefreshIndicator(
      onRefresh: () => ref.read(visitorListProvider.notifier).loadPendingApprovals(),
      child: ListView.separated(
        padding: const EdgeInsets.all(16),
        itemCount: visitors.length,
        separatorBuilder: (_, __) => const SizedBox(height: 12),
        itemBuilder: (_, i) => _ApprovalCard(visitor: visitors[i]),
      ),
    );
  }
}

class _ApprovalCard extends ConsumerWidget {
  final VisitorEntity visitor;
  const _ApprovalCard({required this.visitor});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final isActing = ref.watch(visitorActionProvider) is VisitorActionLoading;

    return AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                width: 44,
                height: 44,
                decoration: BoxDecoration(
                  color: AppTheme.warning.withOpacity(0.12),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: const Icon(Icons.person_rounded,
                    color: AppTheme.warning, size: 24),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(visitor.name,
                        style: const TextStyle(
                            fontWeight: FontWeight.w700,
                            fontSize: 15,
                            color: AppTheme.textPrimary)),
                    Text(visitor.mobile,
                        style: const TextStyle(
                            fontSize: 12, color: AppTheme.textSecondary)),
                  ],
                ),
              ),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                decoration: BoxDecoration(
                  color: AppTheme.warning.withOpacity(0.1),
                  borderRadius: BorderRadius.circular(6),
                ),
                child: Text(visitor.visitorType.label,
                    style: const TextStyle(
                        fontSize: 11,
                        color: AppTheme.warning,
                        fontWeight: FontWeight.w600)),
              ),
            ],
          ),
          if (visitor.purpose != null) ...[
            const SizedBox(height: 10),
            Row(
              children: [
                const Icon(Icons.info_outline_rounded,
                    size: 14, color: AppTheme.textSecondary),
                const SizedBox(width: 6),
                Expanded(
                  child: Text(visitor.purpose!,
                      style: const TextStyle(
                          fontSize: 13, color: AppTheme.textSecondary)),
                ),
              ],
            ),
          ],
          const SizedBox(height: 16),
          Row(
            children: [
              Expanded(
                child: OutlinedButton.icon(
                  onPressed: isActing
                      ? null
                      : () => _reject(context, ref),
                  style: OutlinedButton.styleFrom(
                    foregroundColor: AppTheme.error,
                    side: BorderSide(color: AppTheme.error.withOpacity(0.5)),
                    minimumSize: const Size(0, 42),
                  ),
                  icon: const Icon(Icons.close_rounded, size: 16),
                  label: const Text('Deny'),
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: ElevatedButton.icon(
                  onPressed: isActing
                      ? null
                      : () => ref
                          .read(visitorActionProvider.notifier)
                          .approve(visitor.id),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: AppTheme.success,
                    minimumSize: const Size(0, 42),
                  ),
                  icon: const Icon(Icons.check_rounded, size: 16),
                  label: const Text('Approve'),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Future<void> _reject(BuildContext context, WidgetRef ref) async {
    final reasonCtrl = TextEditingController();
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Deny Visitor?'),
        content: TextFormField(
          controller: reasonCtrl,
          autofocus: true,
          decoration: const InputDecoration(
            labelText: 'Reason *',
            hintText: 'e.g., Not expected',
          ),
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
            child: const Text('Deny'),
          ),
        ],
      ),
    );
    if (ok == true && reasonCtrl.text.trim().isNotEmpty) {
      ref
          .read(visitorActionProvider.notifier)
          .reject(visitor.id, reasonCtrl.text.trim());
    }
  }
}
