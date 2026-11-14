import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/l10n/app_locale.dart';
import 'package:ar_society_app/core/navigation/app_menu.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/core/theme/design_tokens.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart' show currentUserProvider;
import 'package:ar_society_app/features/users/presentation/providers/user_providers.dart' show myFormCodesProvider;
import 'package:ar_society_app/shared/widgets/app_form.dart' show AppPage;
import 'package:ar_society_app/shared/widgets/app_widgets.dart' show AppEmptyState, AppErrorState;

/// One of the managers' phone tabs (Operations, Finance, People): the screens the person is granted in that area, as
/// large tiles under their menu group, with a search box that narrows them. It lists screens that already exist and
/// grants nothing: the list is the same server-granted menu, and the backend still refuses what a role may not do.
class MenuHubScreen extends ConsumerStatefulWidget {
  final String slug;
  const MenuHubScreen({super.key, required this.slug});

  @override
  ConsumerState<MenuHubScreen> createState() => _MenuHubScreenState();
}

class _MenuHubScreenState extends ConsumerState<MenuHubScreen> {
  String _query = '';

  @override
  Widget build(BuildContext context) {
    final hub = MenuHub.fromSlug(widget.slug);
    final user = ref.watch(currentUserProvider);
    final grants = ref.watch(myFormCodesProvider);
    return AppPage(
      title: hub?.label ?? 'Screens',
      body: hub == null || user == null
          ? const AppEmptyState(icon: Icons.search_off_rounded, title: 'Nothing here')
          : grants.when(
              loading: () => const Center(child: CircularProgressIndicator()),
              error: (e, _) => AppErrorState(
                  message: friendlyErrorMessage(e), onRetry: () => ref.invalidate(myFormCodesProvider)),
              data: (codes) {
                final groups = hub.categoriesIn(visibleMenuCategories(codes.toSet(), user: user));
                if (groups.isEmpty) {
                  return const AppEmptyState(
                      icon: Icons.lock_outline_rounded,
                      title: 'Nothing here for your role',
                      subtitle: 'Ask the society office if you need access to more screens');
                }
                final hits = searchMenu(groups, _query, translate: context.tr);
                final searching = _query.trim().isNotEmpty;
                return ListView(
                  padding: const EdgeInsets.fromLTRB(AppSpacing.l, AppSpacing.m, AppSpacing.l, AppSpacing.xl),
                  children: [
                    TextField(
                      key: const Key('hub-search'),
                      onChanged: (v) => setState(() => _query = v),
                      textInputAction: TextInputAction.search,
                      decoration: InputDecoration(
                        hintText: context.tr('Search screens'),
                        prefixIcon: const Icon(Icons.search_rounded),
                        isDense: true,
                      ),
                    ),
                    const SizedBox(height: AppSpacing.m),
                    if (searching && hits.isEmpty)
                      Padding(
                        padding: const EdgeInsets.all(AppSpacing.xl),
                        child: Center(
                          child: Text(context.tr('No screen matches'), style: const TextStyle(color: AppTheme.textSecondary)),
                        ),
                      ),
                    if (searching)
                      _Tiles([for (final h in hits) h.$2])
                    else
                      for (final g in groups) ...[
                        Padding(
                          padding: const EdgeInsets.only(top: AppSpacing.s, bottom: AppSpacing.s),
                          child: Semantics(
                            header: true,
                            child: Text(context.tr(g.label), style: Theme.of(context).textTheme.titleSmall),
                          ),
                        ),
                        _Tiles([for (final i in g.items) if (i.route != null) i]),
                        const SizedBox(height: AppSpacing.m),
                      ],
                  ],
                );
              },
            ),
    );
  }
}

class _Tiles extends StatelessWidget {
  final List<AppMenuItem> items;
  const _Tiles(this.items);

  @override
  Widget build(BuildContext context) {
    return GridView.builder(
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      gridDelegate: const SliverGridDelegateWithMaxCrossAxisExtent(
        maxCrossAxisExtent: 190,
        mainAxisExtent: 92,
        crossAxisSpacing: AppSpacing.s,
        mainAxisSpacing: AppSpacing.s,
      ),
      itemCount: items.length,
      itemBuilder: (context, i) {
        final item = items[i];
        // Colour and outline on the outer box, ink on a transparent Material inside (a shadow above a coloured Material
        // tints the card grey).
        return Container(
          decoration: BoxDecoration(
            color: AppTheme.cardBg,
            borderRadius: BorderRadius.circular(AppTheme.radiusM),
            boxShadow: AppTheme.cardShadow,
          ),
          child: Material(
            type: MaterialType.transparency,
            child: InkWell(
              borderRadius: BorderRadius.circular(AppTheme.radiusM),
              onTap: () => context.go(item.route!),
              child: Padding(
                padding: const EdgeInsets.all(AppSpacing.m),
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
                Icon(item.icon, color: AppTheme.primary, size: 26),
                Text(context.tr(item.label),
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(fontSize: 13.5, fontWeight: FontWeight.w600, color: AppTheme.textPrimary)),
                ]),
              ),
            ),
          ),
        );
      },
    );
  }
}
