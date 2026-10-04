import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:ar_society_app/core/router/app_router.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/staff/data/repositories/staff_repository.dart';
import 'package:ar_society_app/features/staff/domain/entities/staff_entities.dart';
import 'package:ar_society_app/features/staff/presentation/providers/staff_providers.dart';
import 'package:ar_society_app/features/staff/presentation/widgets/duty_sheet_actions.dart';
import 'package:ar_society_app/features/staff/presentation/widgets/staff_widgets.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';

/// Supervisor/manager screen: every duty assigned for a chosen date, grouped
/// by where it stands in the duty lifecycle — Awaiting Verification (staff
/// marked complete, not yet confirmed), Pending, and Verified — with a
/// Verify action on the middle group.
///
/// Previously the only supervisor-facing signal for duties was a dashboard
/// count ("Duties Pending"/"Duties Done"), with no way to see who's behind
/// on what, and no way to actually verify a completed duty at all — the
/// backend's POST /staff/duties/{id}/verify had no caller anywhere.
class DutyOverviewScreen extends ConsumerStatefulWidget {
  final String societyId;
  const DutyOverviewScreen({super.key, required this.societyId});

  @override
  ConsumerState<DutyOverviewScreen> createState() => _DutyOverviewScreenState();
}

class _DutyOverviewScreenState extends ConsumerState<DutyOverviewScreen> {
  DateTime _selectedDate = DateTime.now();

  String get _dateStr =>
      '${_selectedDate.year}-${_selectedDate.month.toString().padLeft(2, '0')}-${_selectedDate.day.toString().padLeft(2, '0')}';

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _load());
  }

  void _load() {
    if (widget.societyId.isEmpty) return;
    ref.read(dutyOverviewProvider.notifier).load(widget.societyId, _dateStr);
    ref.read(staffListProvider.notifier).load(widget.societyId);
  }

  void _changeDate(int deltaDays) {
    setState(() => _selectedDate = _selectedDate.add(Duration(days: deltaDays)));
    _load();
  }

  /// One sheet per staff member per day, for the chosen day or 7 days from it. A supervisor
  /// gets their own department's. The `floors-` choices print the housekeeping floor-wise
  /// layout (every floor a row, one page per wing) for the housekeeping staff.
  Future<void> _printSheets(String choice) {
    final floors = choice.startsWith('floors-');
    final days = choice.endsWith('week') ? 7 : 1;
    final last = _selectedDate.add(Duration(days: days - 1));
    final prefix = floors ? 'floor-sheets' : 'duty-sheets';
    return deliverSheet(
      context,
      ref.read(staffRepositoryProvider).dutySheetsPdf(
            widget.societyId, _dateStr,
            toDate: days > 1 ? isoDay(last) : null,
            department: floors ? 'housekeeping' : null,
            floors: floors),
      days > 1 ? '$prefix-$_dateStr-to-${isoDay(last)}.pdf' : '$prefix-$_dateStr.pdf',
    );
  }

  Future<void> _pickDate() async {
    final picked = await showDatePicker(
      context: context,
      initialDate: _selectedDate,
      firstDate: DateTime.now().subtract(const Duration(days: 90)),
      lastDate: DateTime.now().add(const Duration(days: 30)),
    );
    if (picked != null) {
      setState(() => _selectedDate = picked);
      _load();
    }
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(dutyOverviewProvider);
    final staffState = ref.watch(staffListProvider);
    final staffById = <String, StaffEntity>{
      for (final s in (staffState is StaffListLoaded ? staffState.staff : const <StaffEntity>[]))
        s.id: s,
    };

    ref.listen(dutyOverviewProvider, (_, next) {
      if (next is DutyOverviewError) {
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
        title: const Text('Duties'),
        actions: [
          PopupMenuButton<String>(
            icon: const Icon(Icons.print_rounded),
            tooltip: 'Print duty sheets',
            onSelected: _printSheets,
            itemBuilder: (_) => const [
              PopupMenuItem(value: 'day', child: Text('Print sheets for this day')),
              PopupMenuItem(value: 'week', child: Text('Print sheets for 7 days')),
              PopupMenuDivider(),
              PopupMenuItem(value: 'floors-day', child: Text('Housekeeping floor-wise sheets, this day')),
              PopupMenuItem(value: 'floors-week', child: Text('Housekeeping floor-wise sheets, 7 days')),
            ],
          ),
          IconButton(icon: const Icon(Icons.refresh_rounded), onPressed: _load),
        ],
      ),
      body: Column(
        children: [
          _DateBar(
            date: _selectedDate,
            onPrev: () => _changeDate(-1),
            onNext: () => _changeDate(1),
            onPick: _pickDate,
          ),
          Expanded(child: _buildBody(state, staffById)),
        ],
      ),
    );
  }

  Widget _buildBody(DutyOverviewState state, Map<String, StaffEntity> staffById) {
    if (widget.societyId.isEmpty) {
      return const Center(
        child: Padding(
          padding: EdgeInsets.all(20),
          child: Text(
            'Society context is missing. Please go back and try again.',
            textAlign: TextAlign.center,
            style: TextStyle(color: AppTheme.error),
          ),
        ),
      );
    }
    if (state is DutyOverviewLoading || state is DutyOverviewInitial) {
      return const Center(child: CircularProgressIndicator(color: AppTheme.primary));
    }
    if (state is DutyOverviewError) {
      return Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            AppErrorBanner(message: state.message),
            const SizedBox(height: 12),
            TextButton(onPressed: _load, child: const Text('Retry')),
          ],
        ),
      );
    }

    final duties = (state as DutyOverviewLoaded).duties;
    if (duties.isEmpty) {
      return const EmptyState(
        icon: Icons.assignment_outlined,
        title: 'No duties for this date',
        subtitle: 'Assign one from Quick Actions, or pick another date.',
      );
    }

    final awaitingVerification = duties.where((d) => d.needsVerification).toList();
    final pending = duties.where((d) => !d.isCompleted).toList();
    final verified = duties.where((d) => d.isVerified).toList();

    return RefreshIndicator(
      onRefresh: () async => _load(),
      child: ListView(
        padding: const EdgeInsets.all(20),
        children: [
          Row(children: [
            _StatChip(label: 'To Verify', value: awaitingVerification.length, color: AppTheme.warning),
            const SizedBox(width: 10),
            _StatChip(label: 'Pending', value: pending.length, color: AppTheme.textSecondary),
            const SizedBox(width: 10),
            _StatChip(label: 'Verified', value: verified.length, color: AppTheme.success),
          ]),
          const SizedBox(height: 20),
          if (awaitingVerification.isNotEmpty) ...[
            const SectionHeader(title: 'Awaiting Verification'),
            const SizedBox(height: 12),
            ...awaitingVerification.map((d) => Padding(
                  padding: const EdgeInsets.only(bottom: 10),
                  child: _DutyOverviewCard(
                    duty: d,
                    staffName: staffById[d.staffId]?.fullName,
                    societyId: widget.societyId,
                    dateStr: _dateStr,
                  ),
                )),
          ],
          if (pending.isNotEmpty) ...[
            const SectionHeader(title: 'Pending'),
            const SizedBox(height: 12),
            ...pending.map((d) => Padding(
                  padding: const EdgeInsets.only(bottom: 10),
                  child: _DutyOverviewCard(
                    duty: d,
                    staffName: staffById[d.staffId]?.fullName,
                    societyId: widget.societyId,
                    dateStr: _dateStr,
                  ),
                )),
          ],
          if (verified.isNotEmpty) ...[
            const SectionHeader(title: 'Verified'),
            const SizedBox(height: 12),
            ...verified.map((d) => Padding(
                  padding: const EdgeInsets.only(bottom: 10),
                  child: _DutyOverviewCard(
                    duty: d,
                    staffName: staffById[d.staffId]?.fullName,
                    societyId: widget.societyId,
                    dateStr: _dateStr,
                  ),
                )),
          ],
        ],
      ),
    );
  }
}

// ── Date navigation bar ───────────────────────────────────────────────────────

class _DateBar extends StatelessWidget {
  final DateTime date;
  final VoidCallback onPrev;
  final VoidCallback onNext;
  final VoidCallback onPick;
  const _DateBar({
    required this.date, required this.onPrev, required this.onNext, required this.onPick,
  });

  @override
  Widget build(BuildContext context) {
    const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                    'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    return Container(
      padding: const EdgeInsets.symmetric(vertical: 4),
      decoration: const BoxDecoration(
        color: AppTheme.cardBg,
        border: Border(bottom: BorderSide(color: AppTheme.border)),
      ),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          IconButton(icon: const Icon(Icons.chevron_left_rounded), onPressed: onPrev),
          InkWell(
            onTap: onPick,
            borderRadius: BorderRadius.circular(8),
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
              child: Row(mainAxisSize: MainAxisSize.min, children: [
                const Icon(Icons.calendar_today_rounded, size: 15, color: AppTheme.primary),
                const SizedBox(width: 8),
                Text('${date.day} ${months[date.month - 1]} ${date.year}',
                    style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 14)),
              ]),
            ),
          ),
          IconButton(icon: const Icon(Icons.chevron_right_rounded), onPressed: onNext),
        ],
      ),
    );
  }
}

// ── Stat chip ─────────────────────────────────────────────────────────────────

class _StatChip extends StatelessWidget {
  final String label;
  final int value;
  final Color color;
  const _StatChip({required this.label, required this.value, required this.color});

  @override
  Widget build(BuildContext context) {
    return Expanded(
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: 10),
        decoration: BoxDecoration(
          color: color.withOpacity(0.1),
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: color.withOpacity(0.25)),
        ),
        child: Column(children: [
          Text('$value', style: TextStyle(fontSize: 18, fontWeight: FontWeight.w800, color: color)),
          const SizedBox(height: 2),
          Text(label, style: TextStyle(fontSize: 11, color: color, fontWeight: FontWeight.w500)),
        ]),
      ),
    );
  }
}

// ── Duty card with Verify action ──────────────────────────────────────────────

class _DutyOverviewCard extends ConsumerWidget {
  final DutyEntity duty;
  final String? staffName;
  final String societyId;
  final String dateStr;
  const _DutyOverviewCard({
    required this.duty, this.staffName, required this.societyId, required this.dateStr,
  });

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    // A sheet can be entered once its day has come.
    final day = DateTime.tryParse(dateStr);
    final now = DateTime.now();
    final dayHasCome = day == null || !day.isAfter(DateTime(now.year, now.month, now.day));

    final IconData icon;
    final Color color;
    if (duty.isVerified) {
      icon = Icons.verified_rounded;
      color = AppTheme.success;
    } else if (duty.isCompleted) {
      icon = Icons.hourglass_top_rounded;
      color = AppTheme.warning;
    } else {
      icon = Icons.assignment_outlined;
      color = AppTheme.primary;
    }

    return AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(children: [
            Container(
              width: 36,
              height: 36,
              decoration: BoxDecoration(color: color.withOpacity(0.1), borderRadius: BorderRadius.circular(10)),
              child: Icon(icon, color: color, size: 20),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(duty.dutyName,
                      style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 14, color: AppTheme.textPrimary)),
                  Text(staffName ?? 'Unassigned staff',
                      style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
                  if (duty.location != null)
                    Text(duty.location!, style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
                  if (duty.completedFromPaper)
                    const Text('Entered from the printed sheet',
                        style: TextStyle(fontSize: 11.5, color: AppTheme.textSecondary)),
                ],
              ),
            ),
          ]),
          if (duty.startTime != null) ...[
            const SizedBox(height: 8),
            Row(children: [
              const Icon(Icons.schedule_rounded, size: 13, color: AppTheme.textSecondary),
              const SizedBox(width: 4),
              Text('${duty.startTime} - ${duty.endTime ?? '?'}',
                  style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
            ]),
          ],
          if (!duty.isVerified && (dayHasCome || duty.needsVerification || !duty.isCompleted)) ...[
            const SizedBox(height: 10),
            Align(
              alignment: Alignment.centerRight,
              child: Wrap(
                spacing: 8,
                children: [
                  if (!duty.isCompleted)
                    TextButton.icon(
                      onPressed: () => _confirmCancel(context, ref),
                      icon: const Icon(Icons.event_busy_rounded, size: 18),
                      label: const Text('Cancel'),
                      style: TextButton.styleFrom(foregroundColor: AppTheme.error),
                    ),
                  if (dayHasCome)
                    OutlinedButton.icon(
                      onPressed: staffName == null ? null : () => _enterSheet(context, ref),
                      icon: const Icon(Icons.edit_note_rounded, size: 18),
                      label: const Text('Enter from sheet'),
                      style: OutlinedButton.styleFrom(
                        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                      ),
                    ),
                  if (duty.needsVerification)
                    ElevatedButton.icon(
                      onPressed: () => _showVerifyDialog(context, ref),
                      icon: const Icon(Icons.check_rounded, size: 16),
                      label: const Text('Verify'),
                      style: ElevatedButton.styleFrom(
                        backgroundColor: AppTheme.success,
                        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
                      ),
                    ),
                ],
              ),
            ),
          ],
        ],
      ),
    );
  }

  /// Cancels this duty, or (for a plan) this day and the days after it. A duty
  /// someone has already started stays; the server says how many were kept.
  Future<void> _confirmCancel(BuildContext context, WidgetRef ref) async {
    final inPlan = duty.seriesId != null && duty.isRecurring;
    final choice = await showDialog<String>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text('Cancel "${duty.dutyName}"?'),
        content: Text(
          '${staffName ?? 'This staff member'} will no longer have this duty on ${duty.dutyDate}'
          '${inPlan ? ', or on any day after it if you choose "This and later days". Other staff in the plan are not affected.' : '.'}',
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Keep')),
          if (inPlan)
            TextButton(
              onPressed: () => Navigator.pop(ctx, 'later'),
              child: const Text('This and later days', style: TextStyle(color: AppTheme.error)),
            ),
          ElevatedButton(
            style: ElevatedButton.styleFrom(backgroundColor: AppTheme.error),
            onPressed: () => Navigator.pop(ctx, 'one'),
            child: Text(inPlan ? 'Only this day' : 'Cancel duty'),
          ),
        ],
      ),
    );
    if (choice == null || !context.mounted) return;
    final repo = ref.read(staffRepositoryProvider);
    final result = choice == 'later'
        ? await repo.cancelDutySeries(duty.seriesId!, fromDate: duty.dutyDate, staffId: duty.staffId)
        : await repo.cancelDuty(duty.id);
    if (!context.mounted) return;
    switch (result) {
      case StaffSuccess(:final data):
        AppToast.success(
          context,
          data.cancelled == 1 ? 'Duty cancelled' : '${data.cancelled} duties cancelled'
              '${data.kept > 0 ? ' (${data.kept} kept: work already recorded)' : ''}',
        );
        ref.invalidate(societyDutiesProvider(societyId));
        await ref.read(dutyOverviewProvider.notifier).load(societyId, dateStr);
      case StaffFailure(:final message):
        AppToast.error(context, message);
    }
  }

  /// Opens the staff member's whole day (all their duties) to enter the sheet.
  Future<void> _enterSheet(BuildContext context, WidgetRef ref) async {
    final saved = await context.push<bool>(AppRoutes.staffPaperSheet, extra: {
      'societyId': societyId,
      'staffId': duty.staffId,
      'staffName': staffName,
      'date': dateStr,
    });
    if (saved == true) {
      await ref.read(dutyOverviewProvider.notifier).load(societyId, dateStr);
    }
  }

  Future<void> _showVerifyDialog(BuildContext context, WidgetRef ref) async {
    final ctrl = TextEditingController();
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text('Verify "${duty.dutyName}"?'),
        content: TextField(
          controller: ctrl,
          maxLines: 2,
          decoration: const InputDecoration(labelText: 'Notes (optional)'),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancel')),
          ElevatedButton(
            style: ElevatedButton.styleFrom(backgroundColor: AppTheme.success),
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('Verify'),
          ),
        ],
      ),
    );
    if (confirmed != true) return;
    await ref.read(dutyOverviewProvider.notifier).verify(
          duty.id,
          societyId: societyId,
          dateStr: dateStr,
          notes: ctrl.text.trim().isEmpty ? null : ctrl.text.trim(),
        );
  }
}
