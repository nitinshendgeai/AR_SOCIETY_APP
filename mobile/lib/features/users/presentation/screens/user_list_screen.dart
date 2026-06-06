import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/core/router/app_router.dart';
import 'package:ar_society_app/features/users/data/models/user_admin_models.dart';
import 'package:ar_society_app/features/users/presentation/providers/user_providers.dart';

class UserListScreen extends ConsumerStatefulWidget {
  const UserListScreen({super.key});

  @override
  ConsumerState<UserListScreen> createState() => _UserListScreenState();
}

class _UserListScreenState extends ConsumerState<UserListScreen> {
  final _searchCtrl = TextEditingController();
  String _filterRole = 'All';
  String _filterStatus = 'All';

  @override
  void dispose() {
    _searchCtrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final usersAsync = ref.watch(usersListProvider);

    return Scaffold(
      backgroundColor: AppTheme.surface,
      appBar: AppBar(
        title: const Text('Users & Roles'),
        actions: [
          IconButton(
            icon: const Icon(Icons.person_add_rounded),
            tooltip: 'Create user',
            onPressed: () async {
              await context.push(AppRoutes.usersCreate);
              ref.read(usersListProvider.notifier).refresh();
            },
          ),
        ],
      ),
      body: Column(
        children: [
          _SearchBar(controller: _searchCtrl, onChanged: (_) => setState(() {})),
          _FilterRow(
            selectedRole: _filterRole,
            selectedStatus: _filterStatus,
            onRoleChanged: (v) => setState(() => _filterRole = v),
            onStatusChanged: (v) => setState(() => _filterStatus = v),
          ),
          Expanded(
            child: usersAsync.when(
              loading: () =>
                  const Center(child: CircularProgressIndicator()),
              error: (e, _) => _ErrorView(
                message: e.toString(),
                onRetry: () =>
                    ref.read(usersListProvider.notifier).refresh(),
              ),
              data: (users) {
                final filtered = _applyFilters(users);
                if (filtered.isEmpty) {
                  return _EmptyView(hasFilters: _hasFilters);
                }
                return RefreshIndicator(
                  onRefresh: () =>
                      ref.read(usersListProvider.notifier).refresh(),
                  child: ListView.separated(
                    padding: const EdgeInsets.all(16),
                    itemCount: filtered.length,
                    separatorBuilder: (_, __) => const SizedBox(height: 8),
                    itemBuilder: (_, i) => _UserTile(
                      user: filtered[i],
                      onTap: () async {
                        await context.push(
                          AppRoutes.usersDetail.replaceFirst(':userId', filtered[i].id),
                        );
                        ref.read(usersListProvider.notifier).refresh();
                      },
                    ),
                  ),
                );
              },
            ),
          ),
        ],
      ),
    );
  }

  bool get _hasFilters =>
      _searchCtrl.text.isNotEmpty ||
      _filterRole != 'All' ||
      _filterStatus != 'All';

  List<AdminUserModel> _applyFilters(List<AdminUserModel> users) {
    var list = users;
    final q = _searchCtrl.text.trim().toLowerCase();
    if (q.isNotEmpty) {
      list = list
          .where((u) =>
              u.fullName.toLowerCase().contains(q) ||
              u.email.toLowerCase().contains(q))
          .toList();
    }
    if (_filterRole != 'All') {
      list = list.where((u) => u.roles.contains(_filterRole)).toList();
    }
    if (_filterStatus != 'All') {
      list = list
          .where((u) => u.status.toLowerCase() == _filterStatus.toLowerCase())
          .toList();
    }
    return list;
  }
}

// ── Components ────────────────────────────────────────────────────────────────

class _SearchBar extends StatelessWidget {
  final TextEditingController controller;
  final ValueChanged<String> onChanged;
  const _SearchBar({required this.controller, required this.onChanged});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 0),
      child: TextField(
        controller: controller,
        onChanged: onChanged,
        decoration: InputDecoration(
          hintText: 'Search by name or email…',
          hintStyle: const TextStyle(
              color: AppTheme.textSecondary, fontSize: 14),
          prefixIcon: const Icon(Icons.search_rounded,
              color: AppTheme.textSecondary, size: 20),
          suffixIcon: controller.text.isNotEmpty
              ? IconButton(
                  icon: const Icon(Icons.clear_rounded,
                      size: 18, color: AppTheme.textSecondary),
                  onPressed: () {
                    controller.clear();
                    onChanged('');
                  },
                )
              : null,
          contentPadding:
              const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
          filled: true,
          fillColor: AppTheme.cardBg,
          border: OutlineInputBorder(
            borderRadius: BorderRadius.circular(12),
            borderSide: const BorderSide(color: AppTheme.border),
          ),
          enabledBorder: OutlineInputBorder(
            borderRadius: BorderRadius.circular(12),
            borderSide: const BorderSide(color: AppTheme.border),
          ),
        ),
      ),
    );
  }
}

class _FilterRow extends StatelessWidget {
  final String selectedRole;
  final String selectedStatus;
  final ValueChanged<String> onRoleChanged;
  final ValueChanged<String> onStatusChanged;

  const _FilterRow({
    required this.selectedRole,
    required this.selectedStatus,
    required this.onRoleChanged,
    required this.onStatusChanged,
  });

  static const _roles = [
    'All', 'Society Admin', 'Committee Chairman', 'Committee Secretary',
    'Committee Treasurer', 'Security Supervisor', 'Security Staff',
    'Housekeeping Supervisor', 'Housekeeping Staff', 'Technical Supervisor',
    'Technical Staff', 'Resident', 'Tenant',
  ];

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 8, 16, 4),
      child: SingleChildScrollView(
        scrollDirection: Axis.horizontal,
        child: Row(
          children: [
            _Chip(
              label: selectedStatus == 'All' ? 'Status: All' : selectedStatus,
              active: selectedStatus != 'All',
              onTap: () => _showStatusPicker(context),
            ),
            const SizedBox(width: 8),
            _Chip(
              label: selectedRole == 'All' ? 'Role: All' : selectedRole,
              active: selectedRole != 'All',
              onTap: () => _showRolePicker(context),
            ),
          ],
        ),
      ),
    );
  }

  void _showStatusPicker(BuildContext ctx) {
    showModalBottomSheet(
      context: ctx,
      builder: (_) => _PickerSheet(
        title: 'Filter by Status',
        options: const ['All', 'active', 'inactive', 'suspended'],
        selected: selectedStatus,
        onSelect: onStatusChanged,
      ),
    );
  }

  void _showRolePicker(BuildContext ctx) {
    showModalBottomSheet(
      context: ctx,
      isScrollControlled: true,
      builder: (_) => _PickerSheet(
        title: 'Filter by Role',
        options: _roles,
        selected: selectedRole,
        onSelect: onRoleChanged,
      ),
    );
  }
}

class _Chip extends StatelessWidget {
  final String label;
  final bool active;
  final VoidCallback onTap;
  const _Chip({required this.label, required this.active, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding:
            const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
        decoration: BoxDecoration(
          color: active
              ? AppTheme.primary.withOpacity(0.1)
              : AppTheme.cardBg,
          borderRadius: BorderRadius.circular(20),
          border: Border.all(
            color: active ? AppTheme.primary : AppTheme.border,
          ),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(
              label,
              style: TextStyle(
                fontSize: 12,
                color: active ? AppTheme.primary : AppTheme.textSecondary,
                fontWeight:
                    active ? FontWeight.w600 : FontWeight.w400,
              ),
            ),
            const SizedBox(width: 4),
            Icon(Icons.expand_more_rounded,
                size: 14,
                color: active
                    ? AppTheme.primary
                    : AppTheme.textSecondary),
          ],
        ),
      ),
    );
  }
}

class _PickerSheet extends StatelessWidget {
  final String title;
  final List<String> options;
  final String selected;
  final ValueChanged<String> onSelect;
  const _PickerSheet(
      {required this.title,
      required this.options,
      required this.selected,
      required this.onSelect});

  @override
  Widget build(BuildContext context) {
    return DraggableScrollableSheet(
      expand: false,
      initialChildSize: 0.5,
      maxChildSize: 0.85,
      builder: (_, ctrl) => Column(
        children: [
          const SizedBox(height: 8),
          Container(
            width: 40,
            height: 4,
            decoration: BoxDecoration(
              color: AppTheme.border,
              borderRadius: BorderRadius.circular(2),
            ),
          ),
          Padding(
            padding: const EdgeInsets.all(16),
            child: Text(title,
                style: const TextStyle(
                    fontWeight: FontWeight.w700, fontSize: 16)),
          ),
          Expanded(
            child: ListView(
              controller: ctrl,
              children: options
                  .map((o) => ListTile(
                        title: Text(o),
                        trailing: selected == o
                            ? const Icon(Icons.check_rounded,
                                color: AppTheme.primary)
                            : null,
                        onTap: () {
                          onSelect(o);
                          Navigator.pop(context);
                        },
                      ))
                  .toList(),
            ),
          ),
        ],
      ),
    );
  }
}

class _UserTile extends StatelessWidget {
  final AdminUserModel user;
  final VoidCallback onTap;
  const _UserTile({required this.user, required this.onTap});

  @override
  Widget build(BuildContext context) {
    final isActive = user.status == 'active';
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          color: AppTheme.cardBg,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: AppTheme.border),
        ),
        child: Row(
          children: [
            _Avatar(initials: user.initials, isActive: isActive),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(user.fullName,
                      style: const TextStyle(
                          fontWeight: FontWeight.w600,
                          fontSize: 14,
                          color: AppTheme.textPrimary)),
                  const SizedBox(height: 2),
                  Text(user.email,
                      style: const TextStyle(
                          fontSize: 12, color: AppTheme.textSecondary)),
                  const SizedBox(height: 6),
                  Wrap(
                    spacing: 4,
                    runSpacing: 4,
                    children: user.roles.take(3).map((r) => _RoleBadge(r)).toList(),
                  ),
                ],
              ),
            ),
            const SizedBox(width: 8),
            Column(
              crossAxisAlignment: CrossAxisAlignment.end,
              children: [
                _StatusBadge(isActive: isActive),
                if (user.mustChangePassword) ...[
                  const SizedBox(height: 4),
                  const _PwdBadge(),
                ],
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _Avatar extends StatelessWidget {
  final String initials;
  final bool isActive;
  const _Avatar({required this.initials, required this.isActive});

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 44,
      height: 44,
      decoration: BoxDecoration(
        color: AppTheme.primary.withOpacity(0.12),
        shape: BoxShape.circle,
        border: Border.all(
          color: isActive
              ? AppTheme.success.withOpacity(0.4)
              : AppTheme.border,
          width: 1.5,
        ),
      ),
      child: Center(
        child: Text(initials,
            style: const TextStyle(
                color: AppTheme.primary,
                fontWeight: FontWeight.w700,
                fontSize: 15)),
      ),
    );
  }
}

class _RoleBadge extends StatelessWidget {
  final String role;
  const _RoleBadge(this.role);

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 2),
      decoration: BoxDecoration(
        color: AppTheme.secondary.withOpacity(0.1),
        borderRadius: BorderRadius.circular(6),
        border: Border.all(color: AppTheme.secondary.withOpacity(0.3)),
      ),
      child: Text(role,
          style: const TextStyle(
              fontSize: 10,
              color: AppTheme.secondary,
              fontWeight: FontWeight.w600)),
    );
  }
}

class _StatusBadge extends StatelessWidget {
  final bool isActive;
  const _StatusBadge({required this.isActive});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: (isActive ? AppTheme.success : AppTheme.textSecondary)
            .withOpacity(0.1),
        borderRadius: BorderRadius.circular(6),
      ),
      child: Text(
        isActive ? 'Active' : 'Inactive',
        style: TextStyle(
          fontSize: 10,
          color: isActive ? AppTheme.success : AppTheme.textSecondary,
          fontWeight: FontWeight.w600,
        ),
      ),
    );
  }
}

class _PwdBadge extends StatelessWidget {
  const _PwdBadge();

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
      decoration: BoxDecoration(
        color: AppTheme.warning.withOpacity(0.1),
        borderRadius: BorderRadius.circular(6),
      ),
      child: const Text('Pwd Reset',
          style: TextStyle(
              fontSize: 9,
              color: AppTheme.warning,
              fontWeight: FontWeight.w600)),
    );
  }
}

class _EmptyView extends StatelessWidget {
  final bool hasFilters;
  const _EmptyView({required this.hasFilters});

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.people_outline_rounded,
                size: 48, color: AppTheme.textSecondary),
            const SizedBox(height: 12),
            Text(
              hasFilters ? 'No users match filters' : 'No users yet',
              style: const TextStyle(
                  color: AppTheme.textSecondary, fontSize: 15),
            ),
          ],
        ),
      ),
    );
  }
}

class _ErrorView extends StatelessWidget {
  final String message;
  final VoidCallback onRetry;
  const _ErrorView({required this.message, required this.onRetry});

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.error_outline_rounded,
                color: AppTheme.error, size: 40),
            const SizedBox(height: 12),
            Text(message,
                textAlign: TextAlign.center,
                style: const TextStyle(
                    color: AppTheme.textSecondary, fontSize: 13)),
            const SizedBox(height: 16),
            TextButton.icon(
              onPressed: onRetry,
              icon: const Icon(Icons.refresh_rounded),
              label: const Text('Retry'),
            ),
          ],
        ),
      ),
    );
  }
}
