import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/features/staff/domain/entities/staff_entities.dart';
import 'package:ar_society_app/features/staff/presentation/providers/staff_providers.dart';
import 'package:ar_society_app/features/staff/presentation/widgets/staff_widgets.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';

/// Staff list screen for supervisors and managers.
/// Shows staff filtered by department with quick actions.
class StaffListScreen extends ConsumerStatefulWidget {
  final String? filterDepartment;
  const StaffListScreen({super.key, this.filterDepartment});

  @override
  ConsumerState<StaffListScreen> createState() => _StaffListScreenState();
}

class _StaffListScreenState extends ConsumerState<StaffListScreen> {
  String _search = '';
  String? _departmentFilter;

  static const _departments = [
    null,
    'security',
    'housekeeping',
    'technical',
    'gym',
    'admin',
  ];

  static const _deptLabels = {
    null: 'All',
    'security': 'Security',
    'housekeeping': 'Housekeeping',
    'technical': 'Technical',
    'gym': 'Gym',
    'admin': 'Admin',
  };

  @override
  void initState() {
    super.initState();
    _departmentFilter = widget.filterDepartment;
    WidgetsBinding.instance.addPostFrameCallback((_) => _load());
  }

  void _load() {
    final user = ref.read(currentUserProvider);
    if (user?.societyId == null) return;
    ref.read(staffListProvider.notifier).load(user!.societyId!, department: _departmentFilter);
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(staffListProvider);
    final user  = ref.watch(currentUserProvider);
    final societyId = user?.societyId;

    return Scaffold(
      backgroundColor: AppTheme.surface,
      appBar: AppBar(
        title: const Text('Staff'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh_rounded),
            onPressed: _load,
          ),
        ],
      ),
      body: Column(
        children: [
          // Search + filter bar
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 12, 16, 0),
            child: Column(
              children: [
                TextField(
                  onChanged: (v) => setState(() => _search = v.toLowerCase()),
                  decoration: InputDecoration(
                    hintText: 'Search staff…',
                    prefixIcon: const Icon(Icons.search_rounded, size: 20),
                    contentPadding: const EdgeInsets.symmetric(vertical: 10),
                    border: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(12),
                      borderSide: const BorderSide(color: AppTheme.border),
                    ),
                    filled: true,
                    fillColor: AppTheme.cardBg,
                  ),
                ),
                const SizedBox(height: 10),
                SizedBox(
                  height: 34,
                  child: ListView.separated(
                    scrollDirection: Axis.horizontal,
                    itemCount: _departments.length,
                    separatorBuilder: (_, __) => const SizedBox(width: 8),
                    itemBuilder: (_, i) {
                      final dept = _departments[i];
                      final selected = dept == _departmentFilter;
                      return GestureDetector(
                        onTap: () {
                          setState(() => _departmentFilter = dept);
                          if (societyId != null) {
                            ref.read(staffListProvider.notifier).load(societyId, department: dept);
                          }
                        },
                        child: AnimatedContainer(
                          duration: const Duration(milliseconds: 200),
                          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
                          decoration: BoxDecoration(
                            color: selected ? AppTheme.primary : AppTheme.cardBg,
                            borderRadius: BorderRadius.circular(20),
                            border: Border.all(
                              color: selected ? AppTheme.primary : AppTheme.border,
                            ),
                          ),
                          child: Text(
                            _deptLabels[dept]!,
                            style: TextStyle(
                              fontSize: 12,
                              fontWeight: FontWeight.w600,
                              color: selected ? Colors.white : AppTheme.textSecondary,
                            ),
                          ),
                        ),
                      );
                    },
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 8),

          // Staff list
          Expanded(
            child: switch (state) {
              StaffListLoading() => const Center(child: CircularProgressIndicator(color: AppTheme.primary)),
              StaffListError(:final message) => Center(child: AppErrorBanner(message: message)),
              StaffListLoaded(:final staff) => _buildList(staff, societyId),
              _ => const SizedBox.shrink(),
            },
          ),
        ],
      ),
    );
  }

  Widget _buildList(List<StaffEntity> allStaff, String? societyId) {
    final filtered = allStaff.where((s) {
      if (_search.isEmpty) return true;
      return s.fullName.toLowerCase().contains(_search) ||
             s.employeeCode.toLowerCase().contains(_search) ||
             s.department.toLowerCase().contains(_search);
    }).toList();

    if (filtered.isEmpty) {
      return const EmptyState(
        icon: Icons.badge_rounded,
        title: 'No staff found',
        subtitle: 'Try adjusting your filters.',
      );
    }

    return RefreshIndicator(
      onRefresh: () async => _load(),
      child: ListView.builder(
        padding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
        itemCount: filtered.length,
        itemBuilder: (_, i) => Padding(
          padding: const EdgeInsets.only(bottom: 10),
          child: _StaffCard(
            staff: filtered[i],
            societyId: societyId,
          ),
        ),
      ),
    );
  }
}

class _StaffCard extends ConsumerWidget {
  final StaffEntity staff;
  final String? societyId;

  const _StaffCard({required this.staff, this.societyId});

  Color _statusColor(String s) {
    switch (s) {
      case 'active':    return AppTheme.success;
      case 'on_leave':  return AppTheme.warning;
      case 'inactive':  return AppTheme.textSecondary;
      default:          return AppTheme.primary;
    }
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                width: 40,
                height: 40,
                decoration: BoxDecoration(
                  color: AppTheme.primary.withOpacity(0.1),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: const Icon(Icons.person_rounded, color: AppTheme.primary, size: 22),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(staff.fullName,
                        style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 14, color: AppTheme.textPrimary)),
                    Text('${staff.employeeCode} · ${staff.departmentLabel}',
                        style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
                  ],
                ),
              ),
              _StatusBadge(status: staff.status, color: _statusColor(staff.status)),
            ],
          ),
          if (staff.mobile.isNotEmpty) ...[
            const SizedBox(height: 10),
            const Divider(height: 1, color: AppTheme.border),
            const SizedBox(height: 10),
            Row(
              children: [
                const Icon(Icons.phone_rounded, size: 14, color: AppTheme.textSecondary),
                const SizedBox(width: 6),
                Text(staff.mobile,
                    style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
                const Spacer(),
                // Quick action: assign duty
                if (societyId != null)
                  TextButton.icon(
                    onPressed: () => context.push(
                      '/staff/assign-duty',
                      extra: {'societyId': societyId, 'staffId': staff.id},
                    ),
                    icon: const Icon(Icons.assignment_rounded, size: 14),
                    label: const Text('Assign Duty', style: TextStyle(fontSize: 11)),
                    style: TextButton.styleFrom(
                      foregroundColor: AppTheme.primary,
                      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                    ),
                  ),
              ],
            ),
          ],
        ],
      ),
    );
  }
}

class _StatusBadge extends StatelessWidget {
  final String status;
  final Color color;

  const _StatusBadge({required this.status, required this.color});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: color.withOpacity(0.1),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: color.withOpacity(0.3)),
      ),
      child: Text(
        status.replaceAll('_', ' ').toUpperCase(),
        style: TextStyle(color: color, fontSize: 10, fontWeight: FontWeight.w700),
      ),
    );
  }
}
