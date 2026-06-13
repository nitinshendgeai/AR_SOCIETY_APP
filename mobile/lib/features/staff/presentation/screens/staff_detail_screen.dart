import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/staff/data/repositories/staff_repository.dart';
import 'package:ar_society_app/features/staff/domain/entities/staff_entities.dart';
import 'package:ar_society_app/features/staff/presentation/providers/staff_providers.dart';
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

          if (staff.userId != null) ...[
            const SizedBox(height: 16),
            _LoginAccountCard(
              userId: staff.userId!,
              email: staff.email ?? '',
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

// ── Login Account Card ────────────────────────────────────────────────────────

class _LoginAccountCard extends ConsumerStatefulWidget {
  final String userId;
  final String email;
  const _LoginAccountCard({required this.userId, required this.email});

  @override
  ConsumerState<_LoginAccountCard> createState() => _LoginAccountCardState();
}

class _LoginAccountCardState extends ConsumerState<_LoginAccountCard> {
  String? _userStatus;
  bool _loading = true;
  String? _error;
  bool _actionLoading = false;

  @override
  void initState() {
    super.initState();
    _fetchUser();
  }

  Future<void> _fetchUser() async {
    setState(() { _loading = true; _error = null; });
    final result = await ref.read(staffRepositoryProvider).getUserById(widget.userId);
    if (!mounted) return;
    switch (result) {
      case StaffSuccess(:final data):
        setState(() { _userStatus = data['status'] as String?; _loading = false; });
      case StaffFailure(:final message):
        setState(() { _error = message; _loading = false; });
    }
  }

  Future<void> _resetPassword() async {
    setState(() { _actionLoading = true; });
    final result = await ref.read(staffRepositoryProvider).resetStaffPassword(widget.userId);
    if (!mounted) return;
    setState(() { _actionLoading = false; });
    switch (result) {
      case StaffSuccess(:final data): _showPasswordDialog(data);
      case StaffFailure(:final message):
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(message), backgroundColor: AppTheme.error));
    }
  }

  void _showPasswordDialog(String password) {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Password Reset'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Email: ${widget.email}',
              style: const TextStyle(fontSize: 13, color: AppTheme.textSecondary)),
            const SizedBox(height: 12),
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: AppTheme.primary.withOpacity(0.07),
                borderRadius: BorderRadius.circular(8),
              ),
              child: SelectableText(
                password,
                style: const TextStyle(fontSize: 22, fontWeight: FontWeight.bold,
                  color: AppTheme.primary, letterSpacing: 3),
                textAlign: TextAlign.center,
              ),
            ),
            const SizedBox(height: 8),
            const Text('Staff must change this password on first login.',
              style: TextStyle(fontSize: 11, color: AppTheme.textSecondary)),
          ],
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Close')),
        ],
      ),
    );
  }

  Future<void> _toggleStatus() async {
    if (_userStatus == null) return;
    final setActive = _userStatus != 'active';
    setState(() { _actionLoading = true; });
    final result = await ref.read(staffRepositoryProvider)
        .setStaffLoginStatus(widget.userId, active: setActive);
    if (!mounted) return;
    setState(() { _actionLoading = false; });
    switch (result) {
      case StaffSuccess():
        setState(() { _userStatus = setActive ? 'active' : 'suspended'; });
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(setActive ? 'Login enabled' : 'Login disabled')));
      case StaffFailure(:final message):
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(message), backgroundColor: AppTheme.error));
    }
  }

  @override
  Widget build(BuildContext context) {
    return AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Text('Login Account',
                style: TextStyle(fontSize: 13, fontWeight: FontWeight.w700,
                  color: AppTheme.primary, letterSpacing: 0.4)),
              const Spacer(),
              if (!_loading && _userStatus != null)
                _UserStatusChip(status: _userStatus!),
            ],
          ),
          const SizedBox(height: 12),
          _Row(label: 'Email', value: widget.email.isEmpty ? '—' : widget.email),
          if (_loading)
            const Padding(
              padding: EdgeInsets.symmetric(vertical: 12),
              child: Center(child: SizedBox(
                width: 20, height: 20,
                child: CircularProgressIndicator(strokeWidth: 2),
              )),
            )
          else if (_error != null)
            Padding(
              padding: const EdgeInsets.only(top: 4, bottom: 4),
              child: Text(_error!,
                style: const TextStyle(color: AppTheme.error, fontSize: 12)),
            )
          else if (_actionLoading)
            const Padding(
              padding: EdgeInsets.symmetric(vertical: 12),
              child: Center(child: SizedBox(
                width: 20, height: 20,
                child: CircularProgressIndicator(strokeWidth: 2),
              )),
            )
          else ...[
            const SizedBox(height: 8),
            Row(
              children: [
                Expanded(
                  child: OutlinedButton.icon(
                    icon: const Icon(Icons.lock_reset_rounded, size: 18),
                    label: const Text('Reset Password', style: TextStyle(fontSize: 12)),
                    onPressed: _resetPassword,
                  ),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: OutlinedButton.icon(
                    style: OutlinedButton.styleFrom(
                      foregroundColor: _userStatus == 'active'
                          ? AppTheme.error : AppTheme.success,
                      side: BorderSide(
                        color: _userStatus == 'active'
                            ? AppTheme.error.withOpacity(0.5)
                            : AppTheme.success.withOpacity(0.5),
                      ),
                    ),
                    icon: Icon(
                      _userStatus == 'active'
                          ? Icons.block_rounded
                          : Icons.check_circle_outline_rounded,
                      size: 18,
                    ),
                    label: Text(
                      _userStatus == 'active' ? 'Disable' : 'Enable',
                      style: const TextStyle(fontSize: 12),
                    ),
                    onPressed: _toggleStatus,
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

class _UserStatusChip extends StatelessWidget {
  final String status;
  const _UserStatusChip({required this.status});

  Color get _color {
    switch (status) {
      case 'active':    return AppTheme.success;
      case 'suspended': return AppTheme.error;
      case 'inactive':  return AppTheme.textSecondary;
      case 'pending':   return AppTheme.warning;
      default:          return AppTheme.primary;
    }
  }

  String get _label {
    switch (status) {
      case 'active':    return 'Active';
      case 'suspended': return 'Disabled';
      case 'inactive':  return 'Inactive';
      case 'pending':   return 'Pending';
      default:          return status.toUpperCase();
    }
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 3),
      decoration: BoxDecoration(
        color: _color.withOpacity(0.12),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: _color.withOpacity(0.3)),
      ),
      child: Text(_label,
        style: TextStyle(color: _color, fontSize: 11, fontWeight: FontWeight.w700)),
    );
  }
}
