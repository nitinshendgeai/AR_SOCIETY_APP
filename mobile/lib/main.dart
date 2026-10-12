import 'dart:ui' show PointerDeviceKind;
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter/services.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/app_reset.dart';
import 'package:ar_society_app/core/config/env.dart';
import 'package:ar_society_app/core/l10n/app_locale.dart';
import 'package:ar_society_app/core/router/app_router.dart';
import 'package:ar_society_app/core/layout/app_shell.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/core/push/push_notifications.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/features/visitor/presentation/providers/visitor_providers.dart' show pendingVisitorApprovalsProvider;

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();

  await dotenv.load(fileName: '.env').catchError((_) {});

  try {
    ApiClient.initialize();
  } catch (_) {}

  PushNotifications.instance.initialize();

  if (!kIsWeb) {
    // Portrait lock and status bar styling are native-mobile-only concepts.
    await SystemChrome.setPreferredOrientations([
      DeviceOrientation.portraitUp,
      DeviceOrientation.portraitDown,
    ]);
    SystemChrome.setSystemUIOverlayStyle(
      const SystemUiOverlayStyle(
        statusBarColor: Colors.transparent,
        statusBarIconBrightness: Brightness.dark,
      ),
    );
  }

  final language = await loadSavedLanguage();
  runApp(ResettableScope(language: language));
}

/// The app's provider scope, rebuilt from scratch whenever [AppReset.restart] is called (after switching society),
/// so nothing from the previous society stays in memory. The stored sign-in is kept, so it comes back up signed in.
class ResettableScope extends StatefulWidget {
  final String language;
  const ResettableScope({super.key, required this.language});

  @override
  State<ResettableScope> createState() => _ResettableScopeState();
}

class _ResettableScopeState extends State<ResettableScope> {
  late String _language = widget.language;

  @override
  void initState() {
    super.initState();
    AppReset.epoch.addListener(_onReset);
  }

  @override
  void dispose() {
    AppReset.epoch.removeListener(_onReset);
    super.dispose();
  }

  Future<void> _onReset() async {
    final language = await loadSavedLanguage();      // keep a language chosen during this session
    if (mounted) setState(() => _language = language);
  }

  @override
  Widget build(BuildContext context) => ProviderScope(
        key: ValueKey(AppReset.epoch.value),
        overrides: [initialLanguageProvider.overrideWithValue(_language)],
        child: const ArSocietyApp(),
      );
}

/// Flutter's default scroll behaviour on desktop browsers ignores mouse dragging, so a horizontal
/// row that overflows (filter chips, wide tables) could not be scrolled without a trackpad or
/// Shift + wheel and the items past the edge were out of reach. Allow dragging with the mouse too.
class AppScrollBehavior extends MaterialScrollBehavior {
  const AppScrollBehavior();

  @override
  Set<PointerDeviceKind> get dragDevices => {
        PointerDeviceKind.touch,
        PointerDeviceKind.mouse,
        PointerDeviceKind.stylus,
        PointerDeviceKind.trackpad,
      };
}

class ArSocietyApp extends ConsumerWidget {
  const ArSocietyApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final router = ref.watch(appRouterProvider);
    final locale = ref.watch(localeProvider);

    // Once signed in, register this device for push notifications.
    ref.listen<AuthState>(authProvider, (previous, next) {
      if (next is AuthAuthenticated && previous is! AuthAuthenticated) {
        PushNotifications.instance.register(
          openRoute: (route) => router.push(route),
          // A visitor logged while the app is open: show them right away
          // rather than on the next 15-second poll.
          onForegroundMessage: (_) => ref.invalidate(pendingVisitorApprovalsProvider),
        );
      }
    });

    return MaterialApp.router(
      title: Env.appName,
      debugShowCheckedModeBanner: false,
      theme: AppTheme.lightTheme,
      locale: locale,
      supportedLocales: kSupportedLocales,
      localizationsDelegates: const [
        GlobalMaterialLocalizations.delegate,
        GlobalWidgetsLocalizations.delegate,
        GlobalCupertinoLocalizations.delegate,
      ],
      scrollBehavior: const AppScrollBehavior(),
      routerConfig: router,
      // Desktop-width web gets the denser ERP theme; phones keep the
      // touch-first one. Re-evaluated as the browser window is resized.
      builder: (context, child) => isDesktopLayout(context)
          ? Theme(data: AppTheme.desktopTheme(Theme.of(context)), child: child!)
          : child!,
    );
  }
}
