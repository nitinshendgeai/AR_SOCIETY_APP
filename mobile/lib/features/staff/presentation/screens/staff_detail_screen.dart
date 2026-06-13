import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/staff/domain/entities/staff_entities.dart';
import 'package:ar_society_app/features/staff/presentation/widgets/staff_widgets.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';

/// Read-only view of a single staff member's master record.
/// Receives a [StaffEntity] via GoRouter extra.
class StaffDetailScreen extends ConsumerWidget {
  final StaffEntity staff;
  const StaffDetailScreen({super.key, required this.staff});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return Scaffold(
      backgroundColor: AppTheme.surface,
      appBar: AppBar(
        title: Text(staff.fullName),
        actions: [
          IconButton(
            icon: const Icon(Icons.edit_rounded),
            tooltip: 'Edit',
            onPressed: () => context.push(
              '/staff/${staff.id}/edit',
              extra: staff,
            ),
          ),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.all(20),
        children: [
          // Avatar + headline
          Center(
            child: Column(
              children: [
                Container(
                  width: 72,
                  height: 72,
                  decoration: BoxDecoration(
                    color: AppTheme.primary.withOpacity(0.12),
                    shape: BoxShape.circle,
                  ),
                  child: staff.photoUrl != null
                      ? ClipOval(child: Image.network(staff.photoUrl!, fit: BoxFit.cover))
                      : const Icon(Icons.person_rounded, color: AppTheme.primary, size: 38),
                ),
                const SizedBox(height: 12),
                Text(
                  staff.fullName,
                  style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w700, color: AppTheme.textPrimary),
                ),
                const SizedBox(height: 4),
                Text(
                  staff.employeeCode,
                  style: const TextStyle(fontSize: 13, color: AppTheme.textSecondary),
                ),
                const SizedBox(height: 8),
                _StatusBadge(status: staff.status),
              ],
            ),
          ),

          const SizedBox(height: 24),

          // Employment details
          _Section(
            title: 'Employment',
            children: [
              _Row(label: 'Department',  value: staff.departmentLabel),
              _Row(label: 'Designation', value: staff.designationName ?? '—'),
              _Row(label: 'Shift',       value: staff.shiftId != null ? 'Shift assigned' : '—'),
              _Row(label: 'Joining Date',value: staff.joiningDate ?? '—'),
              _Row(label: 'Status',      value: staff.status.replaceAll('_', ' ').toUpperCase()),
            ],
          ),

          const SizedBox(height: 16),

          // Reporting
          _Section(
            title: 'Reporting',
            children: [
              _Row(
                label: 'Reports To',
                value: staff.reportingManagerName ?? (staff.reportingManagerId != null ? 'Manager assigned' : '—'),
              ),
            ],
          ),

          const SizedBox(height: 16),

          // Contact
          _Section(
            title: 'Contact',
            children: [
              _Row(label: 'Mobile', value: staff.mobile),
              _Row(label: 'Email',  value: staff.email ?? '—'),
              _Row(label: 'Address', value: staff.address ?? '—'),
            ],
          ),

          const SizedBox(height: 16),

          // Emergency contact
          _Section(
            title: 'Emergency Contact',
            children: [
              _Row(label: 'Name',  value: staff.emergencyContactName ?? '—'),
              _Row(label: 'Phone', value: staff.emergencyContactPhone ?? '—'),
            ],
          ),

          if (staff.notes != null && staff.notes!.isNotEmpty) ...[
            const SizedBox(height: 16),
            _Section(
              title: 'Admin Notes',
              children: [
                Text(staff.notes!, style: const TextStyle(fontSize: 13, color: AppTheme.textSecondary)),
              ],
            ),
          ],

          const SizedBox(height: 32),

          // Edit button
          AppPrimaryButton(
            label: 'Edit Staff',
            icon: Icons.edit_rounded,
            onPressed: () => context.push('/staff/${staff.id}/edit', extra: staff),
          ),
        ],
      ),
    );
  }
}

class _Section extends StatelessWidget {
  final String title;
  final List<Widget> children;
  const _Section({required this.title, required this.children});

  @override
  Widget build(BuildContext context) {
    return AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title,
              style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w700,
                  color: AppTheme.primary, letterSpacing: 0.4)),
          const SizedBox(height: 12),
          ...children,
        ],
      ),
    );
  }
}

class _Row extends StatelessWidget {
  final String label;
  final String value;
  const _Row({required this.label, required this.value});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 120,
            child: Text(label,
                style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary, fontWeight: FontWeight.w500)),
          ),
          Expanded(
            child: Text(value,
                style: const TextStyle(fontSize: 13, color: AppTheme.textPrimary, fontWeight: FontWeight.w600)),
          ),
        ],
      ),
    );
  }
}

class _StatusBadge extends StatelessWidget {
  final String status;
  const _StatusBadge({required this.status});

  Color get _color {
    switch (status) {
      case 'active':    return AppTheme.success;
      case 'on_leave':  return AppTheme.warning;
      case 'inactive':  return AppTheme.textSecondary;
      case 'terminated':return AppTheme.error;
      default:          return AppTheme.primary;
    }
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 5),
      decoration: BoxDecoration(
        color: _color.withOpacity(0.12),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: _color.withOpacity(0.3)),
      ),
      child: Text(
        status.replaceAll('_', ' ').toUpperCase(),
        style: TextStyle(color: _color, fontSize: 11, fontWeight: FontWeight.w700),
      ),
    );
  }
}
