import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:ar_society_app/core/layout/app_sheet.dart';
import 'package:ar_society_app/core/router/app_router.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/auth/domain/entities/society_choice.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';

/// Whether the signed-in person has logins in more than one society (so a switcher is worth showing).
bool canSwitchSociety(WidgetRef ref) => (ref.watch(currentUserProvider)?.societies.length ?? 0) > 1;

/// Pick another society to open. The same password was proved at sign-in, so no password is asked again; the app
/// starts over with that society's data.
Future<void> showSocietySwitcher(BuildContext context, WidgetRef ref) {
  final societies = ref.read(currentUserProvider)?.societies ?? const <SocietyChoice>[];
  return showAppSheet(
    context: context,
    builder: (sheetContext) => _SwitcherSheet(societies: societies, outerContext: context),
  );
}

class _SwitcherSheet extends ConsumerStatefulWidget {
  final List<SocietyChoice> societies;
  final BuildContext outerContext;
  const _SwitcherSheet({required this.societies, required this.outerContext});

  @override
  ConsumerState<_SwitcherSheet> createState() => _SwitcherSheetState();
}

class _SwitcherSheetState extends ConsumerState<_SwitcherSheet> {
  String? _busy;

  Future<void> _pick(SocietyChoice c) async {
    if (c.current || c.societyId == null) return;
    setState(() => _busy = c.societyId);
    final error = await ref.read(authProvider.notifier).switchSociety(c.societyId!);
    if (!mounted) return;
    if (error != null) {
      setState(() => _busy = null);
      showErrorToast(context, error);
      return;
    }
    // The app restarts with the new society; start it from the front door rather than on the old page.
    Navigator.of(context).pop();
    GoRouter.of(widget.outerContext).go(AppRoutes.splash);
  }

  @override
  Widget build(BuildContext context) => SafeArea(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(16, 4, 16, 20),
          child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.stretch, children: [
            const Text('Switch society', style: TextStyle(fontSize: 18, fontWeight: FontWeight.w700)),
            const SizedBox(height: 4),
            const Text('You are signed in to each of these with the same details.',
                style: TextStyle(color: AppTheme.textSecondary, fontSize: 13)),
            const SizedBox(height: 12),
            for (final c in widget.societies)
              Card(
                margin: const EdgeInsets.only(bottom: 8),
                child: ListTile(
                  leading: Icon(c.current ? Icons.check_circle_rounded : Icons.apartment_rounded,
                      color: c.current ? AppTheme.success : AppTheme.primary),
                  title: Text(c.societyName, style: const TextStyle(fontWeight: FontWeight.w600)),
                  subtitle: Text(c.current ? 'You are here${c.roleLabel.isEmpty ? '' : ' · ${c.roleLabel}'}' : c.roleLabel),
                  trailing: _busy == c.societyId
                      ? const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2))
                      : (c.current ? null : const Icon(Icons.chevron_right_rounded)),
                  onTap: _busy != null ? null : () => _pick(c),
                ),
              ),
          ]),
        ),
      );
}
