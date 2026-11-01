import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/layout/app_sheet.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/users/data/datasources/user_remote_datasource.dart';
import 'package:ar_society_app/features/users/data/models/user_admin_models.dart';
import 'package:ar_society_app/features/users/presentation/providers/user_providers.dart';
import 'package:ar_society_app/shared/widgets/app_form.dart';

/// The app login a resident signs in with. A login reaches a flat's bills and visitor approvals only through the
/// resident record it is linked to; this shows which login that is, and lets an admin link another or remove it.
class ResidentLoginLink extends ConsumerWidget {
  /// The linked login's id, or null when none is linked.
  final String? userId;
  final ValueChanged<String?> onChanged;
  const ResidentLoginLink({super.key, required this.userId, required this.onChanged});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final id = userId;
    final user = id == null ? null : ref.watch(userDetailProvider(id));
    final label = id == null
        ? 'Not linked to a login'
        : user!.when(
            data: (u) => '${u.fullName}${u.phone == null ? '' : ' · ${u.phone}'}',
            loading: () => 'Loading…',
            // Only an admin can read users: the link is still there.
            error: (_, __) => 'A login is linked',
          );
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Container(
        key: const ValueKey('resident-login-current'),
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: AppTheme.surface,
          borderRadius: BorderRadius.circular(AppTheme.radiusM),
          border: Border.all(color: AppTheme.border),
        ),
        child: Row(children: [
          Icon(id == null ? Icons.link_off_rounded : Icons.link_rounded,
              size: 20, color: id == null ? AppTheme.warning : AppTheme.success),
          const SizedBox(width: 10),
          Expanded(child: Text(label, style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600))),
        ]),
      ),
      const SizedBox(height: 8),
      Wrap(spacing: 8, runSpacing: 8, children: [
        OutlinedButton.icon(
          key: const ValueKey('resident-login-link'),
          onPressed: () async {
            final picked = await pickLoginToLink(context, currentUserId: id);
            if (picked != null) onChanged(picked.id);
          },
          icon: const Icon(Icons.link_rounded, size: 18),
          label: Text(id == null ? 'Link login' : 'Change login'),
        ),
        if (id != null)
          TextButton.icon(
            key: const ValueKey('resident-login-unlink'),
            onPressed: () => onChanged(null),
            style: TextButton.styleFrom(foregroundColor: AppTheme.error),
            icon: const Icon(Icons.link_off_rounded, size: 18),
            label: const Text('Unlink'),
          ),
      ]),
    ]);
  }
}

/// A searchable list of this society's logins (name, mobile, e-mail); returns the one chosen.
Future<AdminUserModel?> pickLoginToLink(BuildContext context, {String? currentUserId}) =>
    showAppSheet<AdminUserModel>(
      context: context,
      builder: (_) => _LoginPickerSheet(currentUserId: currentUserId),
    );

class _LoginPickerSheet extends StatefulWidget {
  final String? currentUserId;
  const _LoginPickerSheet({this.currentUserId});

  @override
  State<_LoginPickerSheet> createState() => _LoginPickerSheetState();
}

class _LoginPickerSheetState extends State<_LoginPickerSheet> {
  late final Future<List<AdminUserModel>> _users = UserRemoteDataSource().listUsers(limit: 1000);
  String _query = '';

  bool _matches(AdminUserModel u) {
    if (_query.isEmpty) return true;
    final q = _query.toLowerCase();
    return u.fullName.toLowerCase().contains(q) ||
        (u.phone?.toLowerCase().contains(q) ?? false) ||
        u.email.toLowerCase().contains(q);
  }

  @override
  Widget build(BuildContext context) => AppSheetFrame(
        title: 'Link a login',
        subtitle: 'Choose the login this resident signs in with',
        scrollBody: false,
        pinned: SheetSearchField(hint: 'Search by name, mobile or e-mail', onChanged: (v) => setState(() => _query = v.trim())),
        child: FutureBuilder<List<AdminUserModel>>(
          future: _users,
          builder: (context, snap) {
            if (snap.connectionState != ConnectionState.done) {
              return const Padding(padding: EdgeInsets.all(24), child: Center(child: CircularProgressIndicator()));
            }
            if (snap.hasError) {
              return const Padding(
                padding: EdgeInsets.all(24),
                child: Text('Only an admin can see the logins to link. Ask the society admin to do this.',
                    style: TextStyle(color: AppTheme.error)),
              );
            }
            final shown = snap.data!.where((u) => u.isActive && _matches(u)).toList();
            if (shown.isEmpty) {
              return const Padding(padding: EdgeInsets.all(24), child: Text('No login matches'));
            }
            return ListView(shrinkWrap: true, children: [
              for (final u in shown)
                PickerRow(
                  title: u.fullName,
                  subtitle: [if (u.phone != null) u.phone!, if (u.displayEmail != null) u.displayEmail!, u.primaryRole]
                      .join(' · '),
                  selected: u.id == widget.currentUserId,
                  onTap: () => Navigator.pop(context, u),
                ),
            ]);
          },
        ),
      );
}
