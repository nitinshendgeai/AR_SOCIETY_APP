import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:intl/intl.dart';
import 'package:ar_society_app/core/l10n/app_locale.dart';
import 'package:ar_society_app/core/motion/loading.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/core/theme/design_tokens.dart';
import 'package:ar_society_app/shared/widgets/app_status.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart' show currentUserProvider;
import 'package:ar_society_app/features/visitor/data/repositories/visitor_repository.dart' show VisitorSuccess, VisitorFailure;
import 'package:ar_society_app/features/visitor/domain/entities/visitor_entities.dart';
import 'package:ar_society_app/features/visitor/domain/visitor_search.dart';
import 'package:ar_society_app/features/visitor/presentation/providers/visitor_providers.dart';
import 'package:ar_society_app/features/visitor/presentation/widgets/pending_visitors_banner.dart';
import 'package:ar_society_app/features/visitor/presentation/widgets/gate_pass.dart';
import 'package:ar_society_app/features/staff/presentation/widgets/staff_widgets.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';
import 'package:ar_society_app/shared/widgets/app_data_table.dart';
import 'package:ar_society_app/core/layout/app_shell.dart' show isDesktopLayout;
import 'package:ar_society_app/shared/widgets/app_form.dart';

/// How many of the latest visitors the society log loads (the server's default page).
const visitorLogLimit = 50;

class VisitorListScreen extends ConsumerStatefulWidget {
  final bool isMy;
  final String societyId;
  /// 1 opens on "Inside Now" (the gate's check-out view).
  final int initialTab;

  /// Opens the "verify guest code" box straight away (the security dashboard's Verify Code shortcut).
  final bool verifyOnOpen;
  const VisitorListScreen({super.key, this.isMy = false, this.societyId = '', this.initialTab = 0, this.verifyOnOpen = false});

  @override
  ConsumerState<VisitorListScreen> createState() => _VisitorListScreenState();
}

class _VisitorListScreenState extends ConsumerState<VisitorListScreen>
    with SingleTickerProviderStateMixin {
  late final TabController _tabs;
  final _searchController = TextEditingController();
  String _query = '';

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
    _tabs = TabController(length: widget.isMy ? 3 : 2, vsync: this, initialIndex: widget.isMy ? 0 : widget.initialTab);
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _reload();
      if (widget.verifyOnOpen && !widget.isMy) _verifyCode();
    });
  }

  @override
  void dispose() {
    _searchController.dispose();
    _tabs.dispose();
    super.dispose();
  }

  Future<void> _logVisitor() async {
    // CreateVisitorScreen pops with `true` on a successful log —
    // this screen isn't rebuilt by that pop (same widget
    // instance), so without awaiting it the newly logged visitor
    // wouldn't appear until a manual pull-to-refresh.
    // The resident's own list is not tied to a society id; the signed-in person's society is the one to use.
    final societyId = widget.societyId.isNotEmpty ? widget.societyId : (ref.read(currentUserProvider)?.societyId ?? '');
    final logged = await context.push<bool>('/visitors/create', extra: societyId);
    if (logged == true) _reload();
  }

  /// The guard keys in the code a guest reads out; if it is good, show who it is and offer to check them in.
  Future<void> _verifyCode() async {
    final ctrl = TextEditingController();
    final code = await showDialog<String>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Verify guest code'),
        content: TextField(
          key: const Key('verify-code-field'),
          controller: ctrl,
          autofocus: true,
          keyboardType: TextInputType.number,
          inputFormatters: [FilteringTextInputFormatter.digitsOnly, LengthLimitingTextInputFormatter(6)],
          style: const TextStyle(fontSize: 28, letterSpacing: 6, fontWeight: FontWeight.w700),
          textAlign: TextAlign.center,
          decoration: const InputDecoration(hintText: '6-digit code'),
          onSubmitted: (v) => Navigator.pop(ctx, v),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Cancel')),
          ElevatedButton(onPressed: () => Navigator.pop(ctx, ctrl.text), child: const Text('Verify')),
        ],
      ),
    );
    if (code == null || code.trim().length < 4 || !mounted) return;
    final result = await ref.read(visitorRepositoryProvider).verifyPass(code.trim());
    if (!mounted) return;
    switch (result) {
      case VisitorSuccess(:final data):
        final checkIn = await showDialog<bool>(
          context: context,
          builder: (ctx) => AlertDialog(
            icon: const Icon(Icons.verified_rounded, color: AppTheme.success, size: 36),
            title: const Text('Valid code'),
            content: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text(data.name, style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w700)),
              const SizedBox(height: 4),
              Text([data.mobile, if (data.flatLabel != null) 'Visiting ${data.flatLabel}'].join('  ·  ')),
              if (data.purpose != null) Text(data.purpose!, style: const TextStyle(color: AppTheme.textSecondary)),
            ]),
            actions: [
              TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Not now')),
              ElevatedButton(
                style: ElevatedButton.styleFrom(backgroundColor: AppTheme.success),
                onPressed: () => Navigator.pop(ctx, true),
                child: const Text('Check in'),
              ),
            ],
          ),
        );
        if (checkIn == true) ref.read(visitorActionProvider.notifier).checkIn(data.id);
      case VisitorFailure(:final message):
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(
          content: Text(message),
          backgroundColor: AppTheme.error,
          behavior: SnackBarBehavior.floating,
        ));
    }
  }

  Future<void> _inviteAgain(VisitorEntity v) async {
    final invited = await context.push<bool>('/visitors/create', extra: v);
    if (invited == true) _reload();
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(visitorListProvider);
    final desktop = isDesktopLayout(context);

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

    return AppPage(
      title: widget.isMy ? 'My Visitors' : 'Visitor Log',
      actions: [
          IconButton(
            icon: const Icon(Icons.refresh_rounded),
            tooltip: 'Refresh',
            onPressed: _reload,
          ),
          if (!widget.isMy)
            IconButton(
              icon: const Icon(Icons.pin_outlined),
              tooltip: 'Verify guest code',
              onPressed: _verifyCode,
            ),
          if (desktop && !widget.isMy)
            HeaderActionButton(icon: Icons.person_add_rounded, label: 'Log Visitor', onPressed: _logVisitor),
        ],
      bottom: TabBar(
          controller: _tabs,
          tabs: widget.isMy
              ? const [Tab(text: 'Expected'), Tab(text: 'Inside'), Tab(text: 'History')]
              : const [Tab(text: 'All Visitors'), Tab(text: 'Inside Now')],
        ),
      floatingActionButton: desktop && !widget.isMy
          ? null
          : FloatingActionButton.extended(
              onPressed: _logVisitor,
              backgroundColor: AppTheme.primary,
              foregroundColor: Colors.white,
              icon: const Icon(Icons.person_add_rounded),
              label: Text(widget.isMy ? 'Invite guest' : 'Log Visitor'),
            ),
      body: _buildBody(state),
    );
  }

  Widget _buildBody(VisitorListState state) {
    if (state is VisitorListLoading) {
      return const SkeletonList();
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

    final TabBarView tabs;
    if (widget.isMy) {
      // A resident thinks in "who is coming", "who is in", "who came": three lists, newest first.
      bool coming(VisitorEntity v) => v.status == VisitorStatus.pending || v.status == VisitorStatus.approved;
      final expected = all.where(coming).toList();
      final history = all.where((v) => !coming(v) && v.status != VisitorStatus.checkedIn).toList();
      tabs = TabBarView(
        controller: _tabs,
        children: [
          _VisitorListView(
            visitors: expected,
            onRefresh: () async => _reload(),
            showActions: false,
            emptyTitle: 'No one expected',
            emptySubtitle: 'Tap Invite guest so the gate lets them in without calling you',
          ),
          _VisitorListView(
            visitors: inside,
            onRefresh: () async => _reload(),
            showActions: false,
            emptyTitle: 'No visitors inside',
            emptySubtitle: 'Guests who have entered and not yet left show here',
          ),
          _VisitorListView(
            visitors: history,
            onRefresh: () async => _reload(),
            showActions: false,
            emptyTitle: 'No past visitors',
            emptySubtitle: 'Visitors who came and went appear here',
            onInviteAgain: _inviteAgain,
          ),
        ],
      );
    } else {
      final searching = _query.trim().isNotEmpty;
      final shownAll = filterVisitors(all, _query);
      final shownInside = filterVisitors(inside, _query);
      tabs = TabBarView(
        controller: _tabs,
        children: [
          _VisitorListView(
            visitors: shownAll,
            onRefresh: () async => _reload(),
            showActions: true,
            emptyTitle: searching ? 'No visitor matches' : 'No visitors',
            emptySubtitle: searching ? 'Check the spelling, or the number or flat' : null,
          ),
          _VisitorListView(
            visitors: shownInside,
            onRefresh: () async => _reload(),
            showActions: true,
            emptyTitle: searching ? 'No visitor matches' : 'No visitors inside',
            emptySubtitle: searching ? 'Check the spelling, or the number or flat' : 'All checked-out or no check-ins yet',
          ),
        ],
      );
    }
    // The guard's log (phone): search above the tabs. The desktop table sorts and filters on its own.
    if (!widget.isMy && !isDesktopLayout(context)) {
      // The server returns the latest rows only and has no search, so say so rather than let "not found" mislead.
      final capped = all.length >= visitorLogLimit;
      return Column(children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 12, 16, 0),
          child: TextField(
            key: const Key('visitor-search'),
            controller: _searchController,
            onChanged: (v) => setState(() => _query = v),
            textInputAction: TextInputAction.search,
            decoration: InputDecoration(
              hintText: context.tr('Search name, mobile, flat or vehicle'),
              prefixIcon: const Icon(Icons.search_rounded),
              suffixIcon: _query.isEmpty
                  ? null
                  : IconButton(
                      icon: const Icon(Icons.close_rounded),
                      tooltip: context.tr('Clear search'),
                      onPressed: () {
                        _searchController.clear();
                        setState(() => _query = '');
                      },
                    ),
              isDense: true,
            ),
          ),
        ),
        if (capped && _query.trim().isNotEmpty)
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 6, 16, 0),
            child: Text(context.tr('Only the latest visitors are searched'),
                key: const Key('visitor-search-cap'),
                style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
          ),
        Expanded(child: tabs),
      ]);
    }
    // A resident's own list can't approve; point them at who's waiting.
    if (!widget.isMy) return tabs;
    return Column(children: [
      const PendingVisitorsBanner(padding: EdgeInsets.fromLTRB(16, 16, 16, 0)),
      Expanded(child: tabs),
    ]);
  }
}

class _VisitorListView extends ConsumerWidget {
  final List<VisitorEntity> visitors;
  final Future<void> Function() onRefresh;
  final bool showActions;
  final String emptyTitle;
  final String? emptySubtitle;
  final void Function(VisitorEntity)? onInviteAgain;

  const _VisitorListView({
    required this.visitors,
    required this.onRefresh,
    required this.showActions,
    this.emptyTitle = 'No visitors',
    this.emptySubtitle,
    this.onInviteAgain,
  });

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    if (isDesktopLayout(context)) return _table(context, ref);
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
        padding: const EdgeInsets.fromLTRB(16, 16, 16, 96),
        itemCount: visitors.length,
        separatorBuilder: (_, __) => const SizedBox(height: 10),
        itemBuilder: (_, i) => _VisitorCard(
          visitor: visitors[i],
          showActions: showActions,
          onInviteAgain: onInviteAgain,
        ),
      ),
    );
  }
}

extension on _VisitorListView {
  /// Desktop: the visitor log as a sortable table with inline gate actions.
  Widget _table(BuildContext context, WidgetRef ref) {
    final isActing = ref.watch(visitorActionProvider) is VisitorActionLoading;
    final actions = ref.read(visitorActionProvider.notifier);
    return RefreshIndicator(
      onRefresh: onRefresh,
      child: ListView(padding: const EdgeInsets.fromLTRB(24, 16, 24, 32), children: [
        AppDataTable<VisitorEntity>(
          rows: visitors,
          empty: EmptyState(icon: Icons.people_outline_rounded, title: emptyTitle, subtitle: emptySubtitle),
          actionsWidth: showActions ? 130 : 0,
          actions: showActions
              ? (v) => [
                    if (v.canCheckIn)
                      OutlinedButton.icon(
                        onPressed: isActing ? null : () => actions.checkIn(v.id),
                        icon: const Icon(Icons.login_rounded, size: 16, color: AppTheme.success),
                        label: const Text('Check in'),
                      ),
                    if (v.canCheckOut)
                      OutlinedButton.icon(
                        onPressed: isActing ? null : () => actions.checkOut(v.id),
                        icon: const Icon(Icons.logout_rounded, size: 16, color: AppTheme.warning),
                        label: const Text('Check out'),
                      ),
                  ]
              : null,
          columns: [
            AppDataColumn(
              label: 'Visitor',
              flex: 3,
              sortKey: (v) => v.name.toLowerCase(),
              cell: (v) => TwoLineCell(v.name, v.mobile),
            ),
            AppDataColumn.text('Type', (v) => v.visitorType.label, width: 120),
            AppDataColumn.text('Purpose', (v) => v.purpose ?? '—', flex: 2),
            AppDataColumn.text('Flat', (v) => v.flatLabel ?? '—', width: 120),
            AppDataColumn.text('Checked in', (v) => tableDateTime(v.checkedInAt),
                width: 140, sortKey: (v) => v.checkedInAt?.millisecondsSinceEpoch),
            AppDataColumn.text('Checked out', (v) => tableDateTime(v.checkedOutAt),
                width: 140, sortKey: (v) => v.checkedOutAt?.millisecondsSinceEpoch),
            AppDataColumn(
              label: 'Status',
              width: 120,
              sortKey: (v) => v.status.label,
              cell: (v) => StatusPill(v.status.label, v.status.color),
            ),
          ],
        ),
      ]),
    );
  }
}

class _VisitorCard extends ConsumerWidget {
  final VisitorEntity visitor;
  final bool showActions;
  final void Function(VisitorEntity)? onInviteAgain;

  const _VisitorCard({required this.visitor, required this.showActions, this.onInviteAgain});

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
                  borderRadius: BorderRadius.circular(AppTheme.radiusM),
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
                    Text(
                        [visitor.mobile, if (visitor.flatLabel != null) visitor.flatLabel!]
                            .join('  ·  '),
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
          if (_whenLine(visitor) != null) ...[
            const SizedBox(height: 8),
            Row(children: [
              const Icon(Icons.schedule_rounded, size: 14, color: AppTheme.textSecondary),
              const SizedBox(width: 6),
              Expanded(
                child: Text(_whenLine(visitor)!,
                    style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
              ),
            ]),
          ],
          if (!showActions && visitor.passCode != null && visitor.status == VisitorStatus.approved) ...[
            const SizedBox(height: 8),
            Align(
              alignment: Alignment.centerLeft,
              child: OutlinedButton.icon(
                onPressed: () => showGatePass(context, visitor),
                icon: const Icon(Icons.pin_outlined, size: 18),
                label: Text('Gate code ${visitor.passCode}'),
              ),
            ),
          ],
          if (onInviteAgain != null && visitor.status == VisitorStatus.checkedOut) ...[
            const SizedBox(height: 8),
            Align(
              alignment: Alignment.centerRight,
              child: TextButton.icon(
                onPressed: () => onInviteAgain!(visitor),
                icon: const Icon(Icons.replay_rounded, size: 16),
                label: const Text('Invite again'),
              ),
            ),
          ],
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
                        backgroundColor: kWarningFill,
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

  /// When this visitor is expected, came or left, in the words a resident would use. Null when nothing is known.
  String? _whenLine(VisitorEntity v) {
    String t(DateTime d) => DateFormat('d MMM, h:mm a').format(d.toLocal());
    switch (v.status) {
      case VisitorStatus.checkedOut:
        if (v.checkedInAt == null) return v.checkedOutAt == null ? null : 'Left ${t(v.checkedOutAt!)}';
        return v.checkedOutAt == null ? 'In ${t(v.checkedInAt!)}' : 'In ${t(v.checkedInAt!)}  ·  Out ${t(v.checkedOutAt!)}';
      case VisitorStatus.checkedIn:
        return v.checkedInAt == null ? null : 'Inside since ${t(v.checkedInAt!)}';
      case VisitorStatus.rejected:
        return v.rejectionReason == null || v.rejectionReason!.isEmpty ? 'Entry refused' : 'Refused: ${v.rejectionReason}';
      case VisitorStatus.pending:
      case VisitorStatus.approved:
        return v.expectedArrival == null ? 'Added ${t(v.createdAt)}' : 'Expected ${t(v.expectedArrival!)}';
    }
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

  /// The words on a status stay readable: each status maps to a tone whose text meets 4.5:1 on its own background.
  static AppTone toneOf(VisitorStatus s) => switch (s) {
        VisitorStatus.pending => AppTone.warning,
        VisitorStatus.approved => AppTone.info,
        VisitorStatus.rejected => AppTone.danger,
        VisitorStatus.checkedIn => AppTone.success,
        VisitorStatus.checkedOut => AppTone.neutral,
      };

  @override
  Widget build(BuildContext context) => AppStatusChip(label: status.label, tone: toneOf(status));
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
