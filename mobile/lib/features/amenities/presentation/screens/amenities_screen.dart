import 'package:flutter/material.dart';
import 'package:ar_society_app/core/motion/loading.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/layout/app_shell.dart' show isDesktopLayout;
import 'package:ar_society_app/core/layout/app_sheet.dart';
import 'package:ar_society_app/core/router/app_router.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/amenities/data/amenities_api.dart';
import 'package:ar_society_app/features/amenities/presentation/providers/amenities_providers.dart';
import 'package:ar_society_app/features/amenities/presentation/screens/amenity_sheets.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/shared/widgets/app_data_table.dart' show HeaderActionButton, StatusPill;
import 'package:ar_society_app/shared/widgets/app_widgets.dart';
import 'package:ar_society_app/shared/widgets/app_form.dart';

String amenityRoute(String id) => AppRoutes.amenityDetail.replaceFirst(':id', id);

/// Clubhouse, gym, pool, party hall… Residents see what is on offer and book a time; the committee and manager
/// also decide the bookings that need approval and set the amenities up.
class AmenitiesScreen extends ConsumerStatefulWidget {
  const AmenitiesScreen({super.key});

  @override
  ConsumerState<AmenitiesScreen> createState() => _AmenitiesScreenState();
}

class _AmenitiesScreenState extends ConsumerState<AmenitiesScreen> with TickerProviderStateMixin {
  TabController? _tabs;
  bool? _managerSeen;

  @override
  void dispose() {
    _tabs?.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final user = ref.watch(currentUserProvider);
    final societyId = user?.societyId;
    if (user == null || societyId == null) return const Scaffold(body: Center(child: Text('No society context')));
    final manager = user.isAdminOrCommittee || user.isManager;
    final setup = user.isAdminOrCommittee;
    if (_tabs == null || _managerSeen != manager) {
      _tabs?.dispose();
      _tabs = TabController(length: manager ? 4 : 2, vsync: this);
      _managerSeen = manager;
    }
    final pending = manager ? ref.watch(pendingBookingsProvider(societyId)).valueOrNull?.length ?? 0 : 0;
    final desktop = isDesktopLayout(context);
    void add() => showAppSheet(context: context, builder: (_) => const AmenityFormSheet());

    return AppPage(
      title: 'Amenities',
      actions: [if (setup && desktop) HeaderActionButton(icon: Icons.add_rounded, label: 'Add amenity', onPressed: add)],
      bottom: TabBar(
          controller: _tabs,
          isScrollable: manager,
          tabs: [
            const Tab(text: 'Amenities'),
            const Tab(text: 'My bookings'),
            if (manager) Tab(text: pending > 0 ? 'Requests ($pending)' : 'Requests'),
            if (manager) const Tab(text: 'All bookings'),
          ],
        ),
      floatingActionButton: setup && !desktop && _tabs!.index == 0
          ? FloatingActionButton.extended(onPressed: add, icon: const Icon(Icons.add_rounded), label: const Text('Add amenity'))
          : null,
      body: TabBarView(controller: _tabs, children: [
        _AmenityList(societyId: societyId, setup: setup),
        const _MyBookings(),
        if (manager) _Requests(societyId: societyId),
        if (manager) _AllBookings(societyId: societyId),
      ]),
    );
  }
}

// ── What is on offer ─────────────────────────────────────────────────────────

class _AmenityList extends ConsumerStatefulWidget {
  final String societyId;
  final bool setup;
  const _AmenityList({required this.societyId, required this.setup});

  @override
  ConsumerState<_AmenityList> createState() => _AmenityListState();
}

class _AmenityListState extends ConsumerState<_AmenityList> {
  bool _closed = false;

  @override
  Widget build(BuildContext context) {
    final async = ref.watch(amenityListProvider((societyId: widget.societyId, includeClosed: _closed && widget.setup)));
    return RefreshIndicator(
      onRefresh: () async => invalidateAmenities(ref),
      child: ResponsiveBody(
        maxWidth: 820,
        child: ListView(padding: const EdgeInsets.fromLTRB(16, 16, 16, 96), children: [
          if (widget.setup)
            Align(
              alignment: Alignment.centerRight,
              child: FilterChip(label: const Text('Show closed ones'), selected: _closed, onSelected: (v) => setState(() => _closed = v)),
            ),
          async.when(
            loading: () => const SkeletonList(),
            error: (e, _) => AppErrorBanner(message: friendlyErrorMessage(e)),
            data: (rows) => rows.isEmpty
                ? Padding(
                    padding: const EdgeInsets.only(top: 24),
                    child: AppEmptyState(
                      icon: Icons.pool_rounded,
                      title: 'No amenities yet',
                      subtitle: widget.setup
                          ? 'Add the clubhouse, gym, pool or hall so residents can book them.'
                          : 'When the committee adds an amenity you can book it here.',
                    ),
                  )
                : Column(children: [for (final a in rows) _AmenityCard(amenity: a)]),
          ),
        ]),
      ),
    );
  }
}

class _AmenityCard extends StatelessWidget {
  final AmenityItem amenity;
  const _AmenityCard({required this.amenity});

  @override
  Widget build(BuildContext context) {
    final a = amenity;
    return Card(
      margin: const EdgeInsets.only(bottom: 10),
      child: InkWell(
        borderRadius: BorderRadius.circular(AppTheme.radiusM),
        onTap: () => context.push(amenityRoute(a.id)),
        child: Padding(
          padding: const EdgeInsets.all(14),
          child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
            CircleAvatar(backgroundColor: AppTheme.primary.withOpacity(0.1), child: Icon(amenityTypeIcon(a.type), color: AppTheme.primary)),
            const SizedBox(width: 12),
            Expanded(
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text(a.name, style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 16)),
                const SizedBox(height: 2),
                Text(
                  [a.hours, if (a.capacity != null) 'up to ${a.capacity} people', if ((a.location ?? '').isNotEmpty) a.location!].join(' · '),
                  style: const TextStyle(color: AppTheme.textSecondary, fontSize: 12.5),
                ),
                const SizedBox(height: 8),
                Wrap(spacing: 6, runSpacing: 6, children: [
                  if (!a.active) const StatusPill('Closed', AppTheme.textSecondary),
                  if (!a.bookingRequired) const StatusPill('No booking needed', AppTheme.success),
                  if (a.bookingRequired && a.approvalRequired) const StatusPill('Needs approval', AppTheme.warning),
                  if (a.chargeable) const StatusPill('Chargeable', AppTheme.primary),
                ]),
              ]),
            ),
            const Icon(Icons.chevron_right_rounded, color: AppTheme.textTertiary),
          ]),
        ),
      ),
    );
  }
}

// ── Bookings ─────────────────────────────────────────────────────────────────

/// One booking, with the buttons that apply to the viewer.
class BookingCard extends ConsumerStatefulWidget {
  final BookingItem booking;
  final bool manager;
  final bool showWho;
  const BookingCard({super.key, required this.booking, this.manager = false, this.showWho = false});

  @override
  ConsumerState<BookingCard> createState() => _BookingCardState();
}

class _BookingCardState extends ConsumerState<BookingCard> {
  bool _busy = false;

  Future<void> _run(Future<void> Function() action, String done) async {
    setState(() => _busy = true);
    try {
      await action();
      invalidateAmenities(ref);
      if (mounted) AppToast.success(context, done);
    } catch (e) {
      if (mounted) showErrorToast(context, e);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final b = widget.booking;
    final api = ref.read(amenitiesApiProvider);
    final isMine = widget.showWho == false;
    final started = !b.notStarted;
    return Card(
      margin: const EdgeInsets.only(bottom: 10),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            Expanded(child: Text(b.amenityName, style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 16))),
            StatusPill(bookingStatusLabel(b.status), bookingStatusColor(b.status)),
          ]),
          const SizedBox(height: 4),
          Text(b.when, style: const TextStyle(fontWeight: FontWeight.w600)),
          if (widget.showWho)
            Text([if ((b.bookedBy ?? '').isNotEmpty) b.bookedBy!, if ((b.flat ?? '').isNotEmpty) b.flat!, '${b.guests} ${b.guests == 1 ? 'person' : 'people'}'].join(' · '),
                style: const TextStyle(color: AppTheme.textSecondary, fontSize: 12.5))
          else
            Text('${b.guests} ${b.guests == 1 ? 'person' : 'people'}', style: const TextStyle(color: AppTheme.textSecondary, fontSize: 12.5)),
          if ((b.purpose ?? '').isNotEmpty) Text(b.purpose!, style: const TextStyle(fontSize: 13)),
          if (b.charge != null || b.deposit != null)
            Padding(
              padding: const EdgeInsets.only(top: 2),
              child: Text([if (b.charge != null) 'Charge ${rupees(b.charge)}', if (b.deposit != null) 'Deposit ${rupees(b.deposit)}'].join(' · '),
                  style: const TextStyle(fontSize: 12.5, color: AppTheme.textSecondary)),
            ),
          if (b.status == 'rejected' && (b.rejectionReason ?? '').isNotEmpty)
            Padding(padding: const EdgeInsets.only(top: 4), child: Text('Why: ${b.rejectionReason}', style: const TextStyle(color: AppTheme.error, fontSize: 12.5))),
          if (b.status == 'cancelled' && (b.cancellationReason ?? '').isNotEmpty)
            Padding(padding: const EdgeInsets.only(top: 4), child: Text('Reason: ${b.cancellationReason}', style: const TextStyle(color: AppTheme.textSecondary, fontSize: 12.5))),
          if (b.isLive) ...[
            const SizedBox(height: 10),
            Wrap(spacing: 8, runSpacing: 8, children: [
              if (widget.manager && b.status == 'pending') ...[
                FilledButton.icon(
                  onPressed: _busy ? null : () => _run(() => api.approve(b.id), 'Approved'),
                  icon: const Icon(Icons.check_rounded, size: 18),
                  label: const Text('Approve'),
                ),
                OutlinedButton.icon(
                  onPressed: _busy
                      ? null
                      : () async {
                          final reason = await showAppSheet<String>(
                              context: context, builder: (_) => const ReasonSheet(title: 'Reject this booking', label: 'Why', action: 'Reject'));
                          if (reason != null) await _run(() => api.reject(b.id, reason), 'Rejected');
                        },
                  icon: const Icon(Icons.close_rounded, size: 18),
                  label: const Text('Reject'),
                ),
              ],
              if (widget.manager && b.status == 'approved' && started)
                FilledButton.icon(
                  onPressed: _busy
                      ? null
                      : () async {
                          final r = await showAppSheet<(bool, String)>(context: context, builder: (_) => const CompleteSheet());
                          if (r != null) await _run(() => api.complete(b.id, damage: r.$1, notes: r.$2), 'Marked as used');
                        },
                  icon: const Icon(Icons.done_all_rounded, size: 18),
                  label: const Text('Mark as used'),
                ),
              if ((isMine || widget.manager) && (widget.manager || b.notStarted))
                TextButton.icon(
                  onPressed: _busy
                      ? null
                      : () async {
                          final reason = await showAppSheet<String>(
                              context: context,
                              builder: (_) => const ReasonSheet(title: 'Cancel this booking', label: 'Why (optional)', action: 'Cancel booking', required: false));
                          if (reason != null) await _run(() => api.cancel(b.id, reason: reason), 'Cancelled');
                        },
                  icon: const Icon(Icons.event_busy_rounded, size: 18),
                  label: const Text('Cancel booking'),
                ),
            ]),
          ],
        ]),
      ),
    );
  }
}

class _MyBookings extends ConsumerWidget {
  const _MyBookings();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final async = ref.watch(myBookingsProvider);
    return RefreshIndicator(
      onRefresh: () async => invalidateAmenities(ref),
      child: ResponsiveBody(
        maxWidth: 820,
        child: ListView(padding: const EdgeInsets.fromLTRB(16, 16, 16, 96), children: [
          async.when(
            loading: () => const SkeletonList(),
            error: (e, _) => AppErrorBanner(message: friendlyErrorMessage(e)),
            data: (rows) => rows.isEmpty
                ? const Padding(
                    padding: EdgeInsets.only(top: 24),
                    child: AppEmptyState(icon: Icons.event_available_rounded, title: 'You have no bookings', subtitle: 'Pick an amenity and choose a time to book it.'),
                  )
                : Column(children: [for (final b in rows) BookingCard(booking: b)]),
          ),
        ]),
      ),
    );
  }
}

class _Requests extends ConsumerWidget {
  final String societyId;
  const _Requests({required this.societyId});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final async = ref.watch(pendingBookingsProvider(societyId));
    return RefreshIndicator(
      onRefresh: () async => invalidateAmenities(ref),
      child: ResponsiveBody(
        maxWidth: 820,
        child: ListView(padding: const EdgeInsets.fromLTRB(16, 16, 16, 96), children: [
          async.when(
            loading: () => const SkeletonList(),
            error: (e, _) => AppErrorBanner(message: friendlyErrorMessage(e)),
            data: (rows) => rows.isEmpty
                ? const Padding(
                    padding: EdgeInsets.only(top: 24),
                    child: AppEmptyState(icon: Icons.inbox_rounded, title: 'Nothing waiting', subtitle: 'Bookings that need your approval appear here.'),
                  )
                : Column(children: [for (final b in rows) BookingCard(booking: b, manager: true, showWho: true)]),
          ),
        ]),
      ),
    );
  }
}

class _AllBookings extends ConsumerStatefulWidget {
  final String societyId;
  const _AllBookings({required this.societyId});

  @override
  ConsumerState<_AllBookings> createState() => _AllBookingsState();
}

class _AllBookingsState extends ConsumerState<_AllBookings> {
  String? _status;

  @override
  Widget build(BuildContext context) {
    final async = ref.watch(allBookingsProvider(widget.societyId));
    return RefreshIndicator(
      onRefresh: () async => invalidateAmenities(ref),
      child: ResponsiveBody(
        maxWidth: 820,
        child: ListView(padding: const EdgeInsets.fromLTRB(16, 12, 16, 96), children: [
          Wrap(spacing: 8, children: [
            for (final s in const [(null, 'All'), ('approved', 'Confirmed'), ('pending', 'Waiting'), ('completed', 'Done'), ('rejected', 'Rejected'), ('cancelled', 'Cancelled')])
              ChoiceChip(label: Text(s.$2), selected: _status == s.$1, onSelected: (_) => setState(() => _status = s.$1)),
          ]),
          const SizedBox(height: 10),
          async.when(
            loading: () => const SkeletonList(),
            error: (e, _) => AppErrorBanner(message: friendlyErrorMessage(e)),
            data: (all) {
              final rows = _status == null ? all : all.where((b) => b.status == _status).toList();
              return rows.isEmpty
                  ? const Padding(padding: EdgeInsets.only(top: 24), child: AppEmptyState(icon: Icons.event_note_rounded, title: 'No bookings here'))
                  : Column(children: [for (final b in rows) BookingCard(booking: b, manager: true, showWho: true)]);
            },
          ),
        ]),
      ),
    );
  }
}
