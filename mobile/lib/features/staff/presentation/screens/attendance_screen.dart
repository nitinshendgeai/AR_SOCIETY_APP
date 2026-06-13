import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/staff/domain/entities/staff_entities.dart';
import 'package:ar_society_app/features/staff/presentation/providers/staff_providers.dart';
import 'package:ar_society_app/features/staff/presentation/widgets/staff_widgets.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';

class AttendanceScreen extends ConsumerStatefulWidget {
  final String staffId;
  const AttendanceScreen({super.key, required this.staffId});

  @override
  ConsumerState<AttendanceScreen> createState() => _AttendanceScreenState();
}

class _AttendanceScreenState extends ConsumerState<AttendanceScreen> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      ref.read(attendanceProvider.notifier).loadHistory(widget.staffId);
    });
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(attendanceProvider);

    // Show snackbar on success/error transitions
    ref.listen(attendanceProvider, (prev, next) {
      if (next is AttendanceSuccess) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(next.message),
            backgroundColor: AppTheme.success,
            behavior: SnackBarBehavior.floating,
          ),
        );
      } else if (next is AttendanceError) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(next.message),
            backgroundColor: next.isDuplicate ? AppTheme.warning : AppTheme.error,
            behavior: SnackBarBehavior.floating,
          ),
        );
      }
    });

    return Scaffold(
      backgroundColor: AppTheme.surface,
      appBar: AppBar(
        title: const Text('Attendance'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh_rounded),
            onPressed: () => ref
                .read(attendanceProvider.notifier)
                .loadHistory(widget.staffId),
          )
        ],
      ),
      body: _buildBody(state),
    );
  }

  Widget _buildBody(AttendanceState state) {
    if (state is AttendanceLoading) {
      return const Center(child: CircularProgressIndicator(color: AppTheme.primary));
    }
    if (state is AttendanceError) {
      return Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            AppErrorBanner(message: state.message),
            const SizedBox(height: 12),
            TextButton(
              onPressed: () => ref.read(attendanceProvider.notifier).loadHistory(widget.staffId),
              child: const Text('Retry'),
            ),
          ],
        ),
      );
    }
    return _Body(
      staffId: widget.staffId,
      today: _getTodayRecord(state),
      history: _getHistory(state),
    );
  }

  AttendanceEntity? _getTodayRecord(AttendanceState state) {
    if (state is AttendanceLoaded) return state.today;
    return null;
  }

  List<AttendanceEntity> _getHistory(AttendanceState state) {
    if (state is AttendanceLoaded) return state.history;
    return [];
  }

  AttendanceLoaded? _getLoaded(AttendanceState state) {
    if (state is AttendanceLoaded) return state;
    return null;
  }
}

class _Body extends ConsumerWidget {
  final String staffId;
  final AttendanceEntity? today;
  final List<AttendanceEntity> history;

  const _Body({
    required this.staffId,
    required this.today,
    required this.history,
  });

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final isLoading = ref.watch(attendanceProvider) is AttendanceLoading;

    return RefreshIndicator(
      onRefresh: () => ref.read(attendanceProvider.notifier).loadHistory(staffId),
      child: ListView(
        padding: const EdgeInsets.all(20),
        children: [
          // Today's status card
          _TodayCard(today: today, staffId: staffId, isLoading: isLoading),
          const SizedBox(height: 24),
          // History
          const SectionHeader(title: 'Recent Attendance'),
          const SizedBox(height: 12),
          if (history.isEmpty)
            const EmptyState(
              icon: Icons.calendar_today_outlined,
              title: 'No attendance records',
              subtitle: 'Records will appear after your first check-in',
            )
          else
            ...history.map((a) => Padding(
              padding: const EdgeInsets.only(bottom: 10),
              child: _AttendanceHistoryTile(record: a),
            )),
        ],
      ),
    );
  }
}

// ── Today's card ──────────────────────────────────────────────────────────────

class _TodayCard extends ConsumerWidget {
  final AttendanceEntity? today;
  final String staffId;
  final bool isLoading;

  const _TodayCard({required this.today, required this.staffId, required this.isLoading});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final now = DateTime.now();
    final todayStr = '${now.day} ${['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][now.month-1]} ${now.year}';

    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          colors: [AppTheme.primary, AppTheme.primaryDark],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(18),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.today_rounded, color: Colors.white70, size: 16),
              const SizedBox(width: 6),
              Text(todayStr,
                  style: const TextStyle(color: Colors.white70, fontSize: 13)),
              const Spacer(),
              if (today != null)
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                  decoration: BoxDecoration(
                    color: Colors.white.withOpacity(0.2),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Text(
                    today!.status.label,
                    style: const TextStyle(
                        color: Colors.white, fontSize: 12, fontWeight: FontWeight.w600),
                  ),
                ),
            ],
          ),
          const SizedBox(height: 16),
          Row(
            children: [
              _TimeBlock(
                label: 'Check In',
                time: formatTime(today?.checkInTime),
                icon: Icons.login_rounded,
              ),
              const SizedBox(width: 16),
              _TimeBlock(
                label: 'Check Out',
                time: formatTime(today?.checkOutTime),
                icon: Icons.logout_rounded,
              ),
              const Spacer(),
              if (today?.workingHours != null)
                Column(
                  crossAxisAlignment: CrossAxisAlignment.end,
                  children: [
                    Text(
                      formatHours(today!.workingHours),
                      style: const TextStyle(
                          color: Colors.white,
                          fontSize: 20,
                          fontWeight: FontWeight.w700),
                    ),
                    const Text('worked', style: TextStyle(color: Colors.white70, fontSize: 12)),
                    if (today!.overtimeHours != null && today!.overtimeHours! > 0) ...[
                      const SizedBox(height: 2),
                      Text(
                        '+${formatHours(today!.overtimeHours)} OT',
                        style: const TextStyle(
                            color: Colors.orangeAccent,
                            fontSize: 11,
                            fontWeight: FontWeight.w600),
                      ),
                    ],
                  ],
                ),
            ],
          ),
          const SizedBox(height: 20),
          // Action buttons
          Row(
            children: [
              if (today == null || !today!.isCheckedIn)
                Expanded(
                  child: _ActionButton(
                    label: 'Check In',
                    icon: Icons.login_rounded,
                    color: AppTheme.success,
                    isLoading: isLoading,
                    onPressed: () => ref.read(attendanceProvider.notifier).checkIn(staffId),
                  ),
                ),
              if (today != null && today!.isCheckedIn && !today!.isCheckedOut) ...[
                if (today!.isCheckedIn) const SizedBox(width: 10),
                Expanded(
                  child: _ActionButton(
                    label: 'Check Out',
                    icon: Icons.logout_rounded,
                    color: Colors.white,
                    textColor: AppTheme.primary,
                    isLoading: isLoading,
                    onPressed: () => ref.read(attendanceProvider.notifier).checkOut(staffId),
                  ),
                ),
              ],
              if (today != null && today!.isComplete)
                Expanded(
                  child: Container(
                    padding: const EdgeInsets.symmetric(vertical: 14),
                    decoration: BoxDecoration(
                      color: Colors.white.withOpacity(0.15),
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: const Row(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Icon(Icons.check_circle_rounded, color: Colors.white, size: 18),
                        SizedBox(width: 8),
                        Text('Shift Complete',
                            style: TextStyle(color: Colors.white, fontWeight: FontWeight.w600)),
                      ],
                    ),
                  ),
                ),
            ],
          ),
        ],
      ),
    );
  }
}

class _TimeBlock extends StatelessWidget {
  final String label;
  final String time;
  final IconData icon;

  const _TimeBlock({required this.label, required this.time, required this.icon});

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Icon(icon, size: 12, color: Colors.white54),
            const SizedBox(width: 4),
            Text(label, style: const TextStyle(color: Colors.white54, fontSize: 11)),
          ],
        ),
        const SizedBox(height: 2),
        Text(time,
            style: const TextStyle(
                color: Colors.white, fontSize: 20, fontWeight: FontWeight.w700)),
      ],
    );
  }
}

class _ActionButton extends StatelessWidget {
  final String label;
  final IconData icon;
  final Color color;
  final Color textColor;
  final bool isLoading;
  final VoidCallback onPressed;

  const _ActionButton({
    required this.label,
    required this.icon,
    required this.color,
    this.textColor = Colors.white,
    required this.isLoading,
    required this.onPressed,
  });

  @override
  Widget build(BuildContext context) {
    return ElevatedButton.icon(
      onPressed: isLoading ? null : onPressed,
      style: ElevatedButton.styleFrom(
        backgroundColor: color,
        foregroundColor: textColor,
        padding: const EdgeInsets.symmetric(vertical: 14),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
        elevation: 0,
      ),
      icon: isLoading
          ? SizedBox(
              width: 16, height: 16,
              child: CircularProgressIndicator(strokeWidth: 2, color: textColor))
          : Icon(icon, size: 18),
      label: Text(label, style: const TextStyle(fontWeight: FontWeight.w600)),
    );
  }
}

// ── History tile ──────────────────────────────────────────────────────────────

class _AttendanceHistoryTile extends StatelessWidget {
  final AttendanceEntity record;
  const _AttendanceHistoryTile({required this.record});

  @override
  Widget build(BuildContext context) {
    return AppCard(
      child: Row(
        children: [
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(formatDate(record.attendanceDate),
                  style: const TextStyle(
                      fontWeight: FontWeight.w600, fontSize: 14, color: AppTheme.textPrimary)),
              const SizedBox(height: 4),
              Row(
                children: [
                  Text(
                    '${formatTime(record.checkInTime)} → ${formatTime(record.checkOutTime)}',
                    style: const TextStyle(color: AppTheme.textSecondary, fontSize: 12),
                  ),
                  if (record.workingHours != null) ...[
                    const Text(' · ', style: TextStyle(color: AppTheme.textSecondary)),
                    Text(formatHours(record.workingHours),
                        style: const TextStyle(
                            color: AppTheme.primary, fontSize: 12, fontWeight: FontWeight.w600)),
                  ],
                ],
              ),
            ],
          ),
          const Spacer(),
          AttendanceStatusBadge(status: record.status),
        ],
      ),
    );
  }
}
