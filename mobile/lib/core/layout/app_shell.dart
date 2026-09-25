import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:ar_society_app/core/navigation/app_menu.dart';
import 'package:ar_society_app/core/router/app_router.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/auth/domain/entities/user_entity.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/features/users/presentation/providers/user_providers.dart';

/// Width from which the app switches to the desktop ERP layout: persistent
/// sidebar, top bar, centered content column. Below it (phones, small
/// tablets) screens keep their own drawer/app bar navigation.
const double kDesktopBreakpoint = 1024;

/// Widest the page content grows on large monitors; wider reads poorly.
const double kContentMaxWidth = 1280;

bool isDesktopLayout(BuildContext context) =>
    MediaQuery.sizeOf(context).width >= kDesktopBreakpoint;

final sidebarCollapsedProvider = StateProvider<bool>((_) => false);

/// Wraps every signed-in page. On desktop widths it adds the persistent
/// navigation sidebar and top bar around [child]; on narrow screens it
/// passes [child] through untouched.
class AppShell extends ConsumerWidget {
  final String location;
  final Widget child;
  const AppShell({super.key, required this.location, required this.child});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    if (!isDesktopLayout(context)) return child;
    final user = ref.watch(currentUserProvider);
    final granted = ref.watch(myFormCodesProvider).valueOrNull?.toSet() ?? const <String>{};
    final categories = visibleMenuCategories(granted, user: user);
    final active = _activeItem(categories, location);

    return Scaffold(
      backgroundColor: AppTheme.surface,
      body: Row(children: [
        _Sidebar(
          categories: categories,
          activeRoute: active?.$2.route,
          homeRoute: user == null ? AppRoutes.home : userRoleHome(user),
          location: location,
        ),
        const VerticalDivider(width: 1),
        Expanded(
          child: Column(children: [
            _TopBar(user: user, crumbs: _breadcrumbs(active)),
            Expanded(
              child: Align(
                alignment: Alignment.topCenter,
                child: ConstrainedBox(
                  constraints: const BoxConstraints(maxWidth: kContentMaxWidth),
                  child: child,
                ),
              ),
            ),
          ]),
        ),
      ]),
    );
  }

  /// The menu entry whose route is the longest prefix of the current path,
  /// so nested pages (e.g. a bill opened from Maintenance Billing) keep
  /// their section highlighted.
  static (AppMenuCategory, AppMenuItem)? _activeItem(List<AppMenuCategory> categories, String location) {
    (AppMenuCategory, AppMenuItem)? best;
    var bestLength = 0;
    for (final c in categories) {
      for (final item in c.items) {
        final route = item.route;
        if (route == null) continue;
        final matches = location == route || location.startsWith('$route/');
        if (matches && route.length > bestLength) {
          best = (c, item);
          bestLength = route.length;
        }
      }
    }
    if (best != null) return best;
    // Pages reached from a list (a complaint, a staff member's profile…)
    // keep their section highlighted: fall back to the entry sharing the
    // first path segment.
    final segment = _firstSegment(location);
    for (final c in categories) {
      for (final item in c.items) {
        if (item.route != null && _firstSegment(item.route!) == segment) return (c, item);
      }
    }
    return null;
  }

  static String _firstSegment(String path) => path.split('/').firstWhere((p) => p.isNotEmpty, orElse: () => '');

  static List<String> _breadcrumbs((AppMenuCategory, AppMenuItem)? active) =>
      active == null ? const ['Dashboard'] : [active.$1.label, active.$2.label];
}

class _Sidebar extends ConsumerWidget {
  final List<AppMenuCategory> categories;
  final String? activeRoute;
  final String homeRoute;
  final String location;
  const _Sidebar({
    required this.categories,
    required this.activeRoute,
    required this.homeRoute,
    required this.location,
  });

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final collapsed = ref.watch(sidebarCollapsedProvider);
    final onHome = activeRoute == null && location == homeRoute;

    return AnimatedContainer(
      duration: const Duration(milliseconds: 180),
      curve: Curves.easeOut,
      width: collapsed ? 72 : 256,
      color: AppTheme.cardBg,
      child: Column(children: [
        _Brand(collapsed: collapsed),
        const Divider(height: 1),
        Expanded(
          child: ListView(
            padding: const EdgeInsets.symmetric(vertical: 8),
            children: [
              _NavTile(
                icon: Icons.space_dashboard_rounded,
                label: 'Dashboard',
                selected: onHome,
                collapsed: collapsed,
                onTap: () => context.go(homeRoute),
              ),
              for (final c in categories) ...[
                if (collapsed)
                  const Padding(
                    padding: EdgeInsets.symmetric(horizontal: 20, vertical: 8),
                    child: Divider(height: 1),
                  )
                else
                  Padding(
                    padding: const EdgeInsets.fromLTRB(24, 18, 16, 6),
                    child: Text(c.label.toUpperCase(),
                        style: const TextStyle(
                          fontSize: 11,
                          fontWeight: FontWeight.w700,
                          letterSpacing: 0.8,
                          color: AppTheme.textTertiary,
                        )),
                  ),
                for (final item in c.items)
                  _NavTile(
                    icon: item.icon,
                    label: item.label,
                    selected: item.route == activeRoute,
                    collapsed: collapsed,
                    onTap: item.route == null ? null : () => context.go(item.route!),
                  ),
              ],
            ],
          ),
        ),
        const Divider(height: 1),
        _NavTile(
          icon: collapsed ? Icons.keyboard_double_arrow_right_rounded : Icons.keyboard_double_arrow_left_rounded,
          label: 'Collapse',
          selected: false,
          collapsed: collapsed,
          onTap: () => ref.read(sidebarCollapsedProvider.notifier).state = !collapsed,
        ),
        const SizedBox(height: 8),
      ]),
    );
  }
}

class _Brand extends ConsumerWidget {
  final bool collapsed;
  const _Brand({required this.collapsed});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final mark = Container(
      width: 36,
      height: 36,
      decoration: BoxDecoration(
        gradient: const LinearGradient(colors: [AppTheme.primary, AppTheme.primaryDark]),
        borderRadius: BorderRadius.circular(10),
      ),
      alignment: Alignment.center,
      child: const Text('D', style: TextStyle(color: Colors.white, fontWeight: FontWeight.w800, fontSize: 18)),
    );
    return SizedBox(
      height: 64,
      child: collapsed
          ? Center(child: mark)
          : Padding(
              padding: const EdgeInsets.symmetric(horizontal: 18),
              child: Row(children: [
                mark,
                const SizedBox(width: 12),
                const Expanded(
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text('DUX OS', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w800, letterSpacing: 0.2)),
                      Text('Society ERP', style: TextStyle(fontSize: 11.5, color: AppTheme.textSecondary)),
                    ],
                  ),
                ),
              ]),
            ),
    );
  }
}

class _NavTile extends StatelessWidget {
  final IconData icon;
  final String label;
  final bool selected;
  final bool collapsed;
  final VoidCallback? onTap;
  const _NavTile({
    required this.icon,
    required this.label,
    required this.selected,
    required this.collapsed,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final color = selected ? AppTheme.primary : AppTheme.textSecondary;
    final tile = Padding(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 1),
      child: Material(
        color: selected ? AppTheme.primarySoft : Colors.transparent,
        borderRadius: BorderRadius.circular(8),
        child: InkWell(
          borderRadius: BorderRadius.circular(8),
          hoverColor: AppTheme.surface,
          onTap: onTap,
          child: SizedBox(
            height: 40,
            child: Row(
              mainAxisAlignment: collapsed ? MainAxisAlignment.center : MainAxisAlignment.start,
              children: [
                if (!collapsed) const SizedBox(width: 12),
                Icon(icon, size: 20, color: color),
                if (!collapsed) ...[
                  const SizedBox(width: 12),
                  Expanded(
                    child: Text(
                      label,
                      overflow: TextOverflow.ellipsis,
                      style: TextStyle(
                        fontSize: 13.5,
                        fontWeight: selected ? FontWeight.w600 : FontWeight.w500,
                        color: selected ? AppTheme.primary : AppTheme.textPrimary,
                      ),
                    ),
                  ),
                ],
              ],
            ),
          ),
        ),
      ),
    );
    return collapsed ? Tooltip(message: label, waitDuration: const Duration(milliseconds: 300), child: tile) : tile;
  }
}

class _TopBar extends ConsumerWidget {
  final UserEntity? user;
  final List<String> crumbs;
  const _TopBar({required this.user, required this.crumbs});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return Container(
      height: 56,
      padding: const EdgeInsets.symmetric(horizontal: 24),
      decoration: const BoxDecoration(
        color: AppTheme.cardBg,
        border: Border(bottom: BorderSide(color: AppTheme.border)),
      ),
      child: Row(children: [
        for (var i = 0; i < crumbs.length; i++) ...[
          if (i > 0)
            const Padding(
              padding: EdgeInsets.symmetric(horizontal: 8),
              child: Icon(Icons.chevron_right_rounded, size: 18, color: AppTheme.textTertiary),
            ),
          Text(
            crumbs[i],
            style: TextStyle(
              fontSize: 13.5,
              fontWeight: i == crumbs.length - 1 ? FontWeight.w600 : FontWeight.w500,
              color: i == crumbs.length - 1 ? AppTheme.textPrimary : AppTheme.textSecondary,
            ),
          ),
        ],
        const Spacer(),
        if (user != null) _UserMenu(user: user!),
      ]),
    );
  }
}

class _UserMenu extends ConsumerWidget {
  final UserEntity user;
  const _UserMenu({required this.user});

  String get _initials {
    final parts = user.fullName.trim().split(RegExp(r'\s+')).where((p) => p.isNotEmpty).toList();
    if (parts.isEmpty) return '?';
    return (parts.first[0] + (parts.length > 1 ? parts.last[0] : '')).toUpperCase();
  }

  Future<void> _signOut(BuildContext context, WidgetRef ref) async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Sign out?'),
        content: const Text('You will be returned to the login screen.'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancel')),
          FilledButton(
            style: FilledButton.styleFrom(backgroundColor: AppTheme.error),
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('Sign out'),
          ),
        ],
      ),
    );
    if (ok == true) ref.read(authProvider.notifier).logout();
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return PopupMenuButton<String>(
      tooltip: 'Account',
      offset: const Offset(0, 48),
      onSelected: (v) {
        if (v == 'logout') _signOut(context, ref);
      },
      itemBuilder: (_) => [
        PopupMenuItem<String>(
          enabled: false,
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(user.fullName,
                style: const TextStyle(fontWeight: FontWeight.w600, color: AppTheme.textPrimary)),
            Text(user.email, style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
          ]),
        ),
        const PopupMenuDivider(),
        const PopupMenuItem<String>(
          value: 'logout',
          child: Row(children: [
            Icon(Icons.logout_rounded, size: 18, color: AppTheme.error),
            SizedBox(width: 10),
            Text('Sign out', style: TextStyle(color: AppTheme.error)),
          ]),
        ),
      ],
      child: Row(children: [
        CircleAvatar(
          radius: 16,
          backgroundColor: AppTheme.primarySoft,
          child: Text(_initials,
              style: const TextStyle(fontSize: 12.5, fontWeight: FontWeight.w700, color: AppTheme.primary)),
        ),
        const SizedBox(width: 10),
        Column(
          mainAxisAlignment: MainAxisAlignment.center,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(user.fullName, style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600)),
            Text(user.primaryRole,
                style: const TextStyle(fontSize: 11.5, color: AppTheme.textSecondary)),
          ],
        ),
        const SizedBox(width: 4),
        const Icon(Icons.expand_more_rounded, size: 18, color: AppTheme.textSecondary),
      ]),
    );
  }
}
