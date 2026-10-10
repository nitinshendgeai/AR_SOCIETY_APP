import 'package:flutter/material.dart';
import 'package:ar_society_app/core/l10n/app_locale.dart';
import 'package:ar_society_app/core/l10n/language_picker.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:ar_society_app/core/navigation/app_menu.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/auth/domain/entities/user_entity.dart';
import 'package:ar_society_app/features/visitor/presentation/providers/visitor_providers.dart'
    show pendingVisitorApprovalsProvider;

/// Which tab a page belongs to: the tab whose route is the longest prefix of the
/// page's address, or none.
int? activePhoneTab(List<PhoneTab> tabs, String location) {
  int? best;
  var bestLength = 0;
  for (var i = 0; i < tabs.length; i++) {
    final r = tabs[i].route;
    final match = location == r || location.startsWith('$r/');
    if (match && r.length > bestLength) {
      best = i;
      bestLength = r.length;
    }
  }
  return best;
}

/// The bar is for the pages people move between (the tabs and the menu's own
/// pages). A page opened from one of those (a record, a form) has its own back
/// arrow and the bar steps aside.
bool showsPhoneBar(List<PhoneTab> tabs, List<AppMenuCategory> menu, String location) {
  if (tabs.any((t) => t.route == location)) return true;
  return menu.any((c) => c.items.any((i) => i.route == location));
}

/// Home, up to three screens for the person's role, and More (the full menu).
class PhoneBottomBar extends ConsumerWidget {
  final String location;
  final UserEntity user;
  final List<PhoneTab> tabs;
  final List<AppMenuCategory> menu;
  const PhoneBottomBar({super.key, required this.location, required this.user, required this.tabs, required this.menu});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final active = activePhoneTab(tabs, location);
    final waiting = user.isResident ? ref.watch(pendingVisitorApprovalsProvider).valueOrNull?.length ?? 0 : 0;

    Widget icon(PhoneTab t, {required bool selected}) {
      final base = Icon(t.icon);
      final badge = t.label == 'Visitors' ? waiting : 0;
      return badge > 0 ? Badge(label: Text('$badge'), child: base) : base;
    }

    return NavigationBar(
      height: 64,
      backgroundColor: AppTheme.cardBg,
      indicatorColor: AppTheme.primary.withOpacity(0.12),
      labelBehavior: NavigationDestinationLabelBehavior.alwaysShow,
      // A page that is none of the tabs (reached through More) lights More.
      selectedIndex: active ?? tabs.length,
      onDestinationSelected: (i) {
        if (i == tabs.length) {
          _showMore(context, ref, menu);
        } else {
          context.go(tabs[i].route);
        }
      },
      destinations: [
        for (var i = 0; i < tabs.length; i++)
          NavigationDestination(
            icon: icon(tabs[i], selected: false),
            selectedIcon: icon(tabs[i], selected: true),
            label: context.tr(tabs[i].label),
          ),
        NavigationDestination(icon: const Icon(Icons.menu_rounded), label: context.tr('More')),
      ],
    );
  }
}

void _showMore(BuildContext context, WidgetRef ref, List<AppMenuCategory> menu) {
  showModalBottomSheet<void>(
    context: context,
    isScrollControlled: true,
    showDragHandle: true,
    backgroundColor: AppTheme.cardBg,
    builder: (ctx) => DraggableScrollableSheet(
      expand: false,
      initialChildSize: 0.7,
      maxChildSize: 0.92,
      minChildSize: 0.4,
      builder: (ctx, controller) => ListView(
        controller: controller,
        padding: const EdgeInsets.fromLTRB(8, 0, 8, 24),
        children: [
          // Phones have no account menu, so the language is chosen here.
          Consumer(
            builder: (ctx, sheetRef, _) => ListTile(
              leading: const Icon(Icons.translate_rounded, color: AppTheme.textSecondary),
              title: Text(ctx.tr('Language')),
              trailing: Text(kLanguageNames[sheetRef.watch(localeProvider).languageCode] ?? 'English',
                  style: const TextStyle(color: AppTheme.textSecondary)),
              onTap: () {
                Navigator.of(ctx).pop();
                showLanguagePicker(context, ref);
              },
            ),
          ),
          const Divider(height: 8),
          for (final c in menu) ...[
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 14, 16, 4),
              child: Text(ctx.tr(c.label).toUpperCase(),
                  style: const TextStyle(
                      fontSize: 11, fontWeight: FontWeight.w700, letterSpacing: 0.8, color: AppTheme.textTertiary)),
            ),
            for (final item in c.items)
              ListTile(
                leading: Icon(item.icon, color: AppTheme.textSecondary),
                title: Text(ctx.tr(item.label)),
                onTap: item.route == null
                    ? null
                    : () {
                        Navigator.of(ctx).pop();
                        context.go(item.route!);
                      },
              ),
          ],
        ],
      ),
    ),
  );
}
