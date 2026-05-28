import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/staff/domain/entities/staff_entities.dart';
import 'package:ar_society_app/features/staff/presentation/providers/staff_providers.dart';
import 'package:ar_society_app/features/staff/presentation/widgets/staff_widgets.dart';

class DutiesScreen extends ConsumerStatefulWidget {
  final String staffId;
  const DutiesScreen({super.key, required this.staffId});

  @override
  ConsumerState<DutiesScreen> createState() => _DutiesScreenState();
}

class _DutiesScreenState extends ConsumerState<DutiesScreen> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      ref.read(dutyProvider.notifier).loadDuties(widget.staffId);
    });
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(dutyProvider);

    ref.listen(dutyProvider, (_, next) {
      if (next is DutyError) {
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
        title: const Text('My Duties'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh_rounded),
            onPressed: () => ref.read(dutyProvider.notifier).loadDuties(widget.staffId),
          ),
        ],
      ),
      body: switch (state) {
        DutyLoading() => const Center(
            child: CircularProgressIndicator(color: AppTheme.primary)),
        DutyError(:final message) => Center(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(message, style: const TextStyle(color: AppTheme.error)),
                const SizedBox(height: 12),
                TextButton(
                  onPressed: () => ref.read(dutyProvider.notifier).loadDuties(widget.staffId),
                  child: const Text('Retry'),
                ),
              ],
            ),
          ),
        DutyLoaded(:final duties) => _DutyList(
            duties: duties,
            staffId: widget.staffId,
          ),
        _ => const Center(child: CircularProgressIndicator(color: AppTheme.primary)),
      },
    );
  }
}

class _DutyList extends ConsumerWidget {
  final List<DutyEntity> duties;
  final String staffId;
  const _DutyList({required this.duties, required this.staffId});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final pending   = duties.where((d) => !d.isCompleted).toList();
    final completed = duties.where((d) => d.isCompleted).toList();

    return RefreshIndicator(
      onRefresh: () => ref.read(dutyProvider.notifier).loadDuties(staffId),
      child: ListView(
        padding: const EdgeInsets.all(20),
        children: [
          // Summary chips
          Row(
            children: [
              _StatChip(label: 'Pending', value: pending.length, color: AppTheme.warning),
              const SizedBox(width: 10),
              _StatChip(label: 'Completed', value: completed.length, color: AppTheme.success),
            ],
          ),
          const SizedBox(height: 20),

          if (pending.isNotEmpty) ...[
            const SectionHeader(title: 'Pending Duties'),
            const SizedBox(height: 12),
            ...pending.map((d) => Padding(
              padding: const EdgeInsets.only(bottom: 10),
              child: _DutyCard(duty: d, staffId: staffId, showComplete: true),
            )),
            const SizedBox(height: 8),
          ],

          if (completed.isNotEmpty) ...[
            const SectionHeader(title: 'Completed Today'),
            const SizedBox(height: 12),
            ...completed.map((d) => Padding(
              padding: const EdgeInsets.only(bottom: 10),
              child: _DutyCard(duty: d, staffId: staffId, showComplete: false),
            )),
          ],

          if (duties.isEmpty)
            const EmptyState(
              icon: Icons.assignment_outlined,
              title: 'No duties assigned',
              subtitle: 'Your supervisor will assign duties to you',
            ),
        ],
      ),
    );
  }
}

class _StatChip extends StatelessWidget {
  final String label;
  final int value;
  final Color color;
  const _StatChip({required this.label, required this.value, required this.color});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
      decoration: BoxDecoration(
        color: color.withOpacity(0.1),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: color.withOpacity(0.25)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text('$value',
              style: TextStyle(
                  fontSize: 18, fontWeight: FontWeight.w800, color: color)),
          const SizedBox(width: 6),
          Text(label,
              style: TextStyle(fontSize: 12, color: color, fontWeight: FontWeight.w500)),
        ],
      ),
    );
  }
}

class _DutyCard extends ConsumerWidget {
  final DutyEntity duty;
  final String staffId;
  final bool showComplete;
  const _DutyCard({required this.duty, required this.staffId, required this.showComplete});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                width: 36,
                height: 36,
                decoration: BoxDecoration(
                  color: duty.isCompleted
                      ? AppTheme.success.withOpacity(0.1)
                      : AppTheme.primary.withOpacity(0.1),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Icon(
                  duty.isCompleted ? Icons.check_circle_rounded : Icons.assignment_outlined,
                  color: duty.isCompleted ? AppTheme.success : AppTheme.primary,
                  size: 20,
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(duty.dutyName,
                        style: const TextStyle(
                            fontWeight: FontWeight.w600,
                            fontSize: 14,
                            color: AppTheme.textPrimary)),
                    if (duty.location != null)
                      Text(duty.location!,
                          style: const TextStyle(
                              fontSize: 12, color: AppTheme.textSecondary)),
                  ],
                ),
              ),
              if (duty.isCompleted)
                const Icon(Icons.check_circle_rounded,
                    color: AppTheme.success, size: 20),
            ],
          ),
          if (duty.description != null) ...[
            const SizedBox(height: 10),
            Text(duty.description!,
                style: const TextStyle(
                    fontSize: 13, color: AppTheme.textSecondary, height: 1.4)),
          ],
          const SizedBox(height: 10),
          Row(
            children: [
              Icon(Icons.calendar_today_rounded,
                  size: 13, color: AppTheme.textSecondary),
              const SizedBox(width: 4),
              Text(formatDate(duty.dutyDate),
                  style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
              if (duty.startTime != null) ...[
                const Text(' · ',
                    style: TextStyle(color: AppTheme.textSecondary, fontSize: 12)),
                Text('${duty.startTime} - ${duty.endTime ?? '?'}',
                    style: const TextStyle(
                        fontSize: 12, color: AppTheme.textSecondary)),
              ],
              const Spacer(),
              if (showComplete)
                TextButton(
                  onPressed: () async {
                    final confirmed = await showDialog<bool>(
                      context: context,
                      builder: (ctx) => AlertDialog(
                        title: const Text('Mark as Complete?'),
                        content: Text('Confirm completion of: ${duty.dutyName}'),
                        actions: [
                          TextButton(
                              onPressed: () => Navigator.pop(ctx, false),
                              child: const Text('Cancel')),
                          ElevatedButton(
                              onPressed: () => Navigator.pop(ctx, true),
                              child: const Text('Complete')),
                        ],
                      ),
                    );
                    if (confirmed == true) {
                      await ref
                          .read(dutyProvider.notifier)
                          .completeDuty(duty.id, staffId);
                    }
                  },
                  style: TextButton.styleFrom(
                    foregroundColor: AppTheme.success,
                    padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                  ),
                  child: const Text('Mark Complete',
                      style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600)),
                ),
            ],
          ),
        ],
      ),
    );
  }
}
