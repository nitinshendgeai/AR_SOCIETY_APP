import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/visitor/domain/entities/visitor_entities.dart';
import 'package:ar_society_app/features/visitor/presentation/providers/visitor_providers.dart';
import 'package:ar_society_app/features/staff/presentation/widgets/staff_widgets.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';

class VisitorListScreen extends ConsumerStatefulWidget {
  final bool isMy;
  final String societyId;
  const VisitorListScreen({super.key, this.isMy = false, this.societyId = ''});

  @override
  ConsumerState<VisitorListScreen> createState() => _VisitorListScreenState();
}

class _VisitorListScreenState extends ConsumerState<VisitorListScreen>
    with SingleTickerProviderStateMixin {
  late final TabController _tabs;

  void _reload() {
    if (widget.isMy) {
      ref.read(visitorListProvider.notifier).loadMyVisitors();
    } else {
      ref.read(visitorListProvider.notifier).loadSocietyVisitors(widget.societyId);
    }
  }

  @override
  void initState() {
    super.initState();
    _tabs = TabController(length: 2, vsync: this);
    WidgetsBinding.instance.addPostFrameCallback((_) => _reload());
  }

  @override
  void dispose() {
    _tabs.dispose();
    super.dispose();
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
        _reload();
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
        title: Text(widget.isMy ? 'My Visitors' : 'Visitor Log'),
        bottom: TabBar(
          controller: _tabs,
          tabs: const [Tab(text: 'All Visitors'), Tab(text: 'Inside Now')],
        ),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh_rounded),
            onPressed: _reload,
          ),
        ],
      ),
      floatingActionButton: widget.isMy
          ? null
          : FloatingActionButton.extended(
              onPressed: () =>
                  context.push('/visitors/create', extra: widget.societyId),
              backgroundColor: AppTheme.primary,
              foregroundColor: Colors.white,
              icon: const Icon(Icons.person_add_rounded),
              label: const Text('Log Visitor'),
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
              onPressed: _reload,
              child: const Text('Retry'),
            ),
          ],
        ),
      );
    }

    final all = state is VisitorListLoaded ? state.visitors : <VisitorEntity>[];
    final inside = all.where((v) => v.status == VisitorStatus.checkedIn).toList();

    return TabBarView(
      controller: _tabs,
      children: [
        _VisitorListView(
          visitors: all,
          onRefresh: () async => _reload(),
          showActions: !widget.isMy,
        ),
        _VisitorListView(
          visitors: inside,
          onRefresh: () async => _reload(),
          showActions: !widget.isMy,
          emptyTitle: 'No visitors inside',
          emptySubtitle: 'All checked-out or no check-ins yet',
        ),
      ],
    );
  }
}

class _VisitorListView extends ConsumerWidget {
  final List<VisitorEntity> visitors;
  final Future<void> Function() onRefresh;
  final bool showActions;
  final String emptyTitle;
  final String? emptySubtitle;

  const _VisitorListView({
    required this.visitors,
    required this.onRefresh,
    required this.showActions,
    this.emptyTitle = 'No visitors',
    this.emptySubtitle,
  });

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    if (visitors.isEmpty) {
      return EmptyState(
        icon: Icons.people_outline_rounded,
        title: emptyTitle,
        subtitle: emptySubtitle,
      );
    }

    return RefreshIndicator(
      onRefresh: onRefresh,
      child: ListView.separated(
        padding: const EdgeInsets.all(16),
        itemCount: visitors.length,
        separatorBuilder: (_, __) => const SizedBox(height: 10),
        itemBuilder: (_, i) => _VisitorCard(
          visitor: visitors[i],
          showActions: showActions,
        ),
      ),
    );
  }
}

class _VisitorCard extends ConsumerWidget {
  final VisitorEntity visitor;
  final bool showActions;

  const _VisitorCard({required this.visitor, required this.showActions});

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
                width: 42,
                height: 42,
                decoration: BoxDecoration(
                  color: visitor.status.color.withOpacity(0.12),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Icon(
                  _typeIcon(visitor.visitorType),
                  color: visitor.status.color,
                  size: 22,
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(visitor.name,
                        style: const TextStyle(
                            fontWeight: FontWeight.w600,
                            fontSize: 14,
                            color: AppTheme.textPrimary)),
                    Text(visitor.mobile,
                        style: const TextStyle(
                            fontSize: 12, color: AppTheme.textSecondary)),
                  ],
                ),
              ),
              _StatusBadge(visitor.status),
            ],
          ),
          const SizedBox(height: 10),
          Row(
            children: [
              _TypeChip(visitor.visitorType),
              if (visitor.purpose != null) ...[
                const SizedBox(width: 8),
                Expanded(
                  child: Text(visitor.purpose!,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(
                          fontSize: 12, color: AppTheme.textSecondary)),
                ),
              ],
            ],
          ),
          if (showActions && (visitor.canCheckIn || visitor.canCheckOut)) ...[
            const SizedBox(height: 12),
            Row(
              children: [
                if (visitor.canCheckIn)
                  Expanded(
                    child: ElevatedButton.icon(
                      onPressed: isActing
                          ? null
                          : () => ref
                              .read(visitorActionProvider.notifier)
                              .checkIn(visitor.id),
                      style: ElevatedButton.styleFrom(
                        backgroundColor: AppTheme.success,
                        minimumSize: const Size(0, 40),
                        padding: const EdgeInsets.symmetric(horizontal: 12),
                      ),
                      icon: const Icon(Icons.login_rounded, size: 16),
                      label: const Text('Check In',
                          style: TextStyle(fontSize: 13)),
                    ),
                  ),
                if (visitor.canCheckOut)
                  Expanded(
                    child: ElevatedButton.icon(
                      onPressed: isActing
                          ? null
                          : () => ref
                              .read(visitorActionProvider.notifier)
                              .checkOut(visitor.id),
                      style: ElevatedButton.styleFrom(
                        backgroundColor: AppTheme.warning,
                        minimumSize: const Size(0, 40),
                        padding: const EdgeInsets.symmetric(horizontal: 12),
                      ),
                      icon: const Icon(Icons.logout_rounded, size: 16),
                      label: const Text('Check Out',
                          style: TextStyle(fontSize: 13)),
                    ),
                  ),
              ],
            ),
          ],
        ],
      ),
    );
  }

  IconData _typeIcon(VisitorType type) {
    switch (type) {
      case VisitorType.delivery:    return Icons.local_shipping_rounded;
      case VisitorType.cab:         return Icons.local_taxi_rounded;
      case VisitorType.maintenance: return Icons.engineering_rounded;
      case VisitorType.vendor:      return Icons.store_rounded;
      default:                      return Icons.person_rounded;
    }
  }
}

class _StatusBadge extends StatelessWidget {
  final VisitorStatus status;
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
            color: status.color, fontSize: 11, fontWeight: FontWeight.w600),
      ),
    );
  }
}

class _TypeChip extends StatelessWidget {
  final VisitorType type;
  const _TypeChip(this.type);

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: AppTheme.border,
        borderRadius: BorderRadius.circular(6),
      ),
      child: Text(type.label,
          style: const TextStyle(
              fontSize: 11,
              color: AppTheme.textSecondary,
              fontWeight: FontWeight.w500)),
    );
  }
}
