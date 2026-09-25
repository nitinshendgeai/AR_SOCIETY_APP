import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/config/env.dart';
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

  runApp(const ProviderScope(child: ArSocietyApp()));
}

class ArSocietyApp extends ConsumerWidget {
  const ArSocietyApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final router = ref.watch(appRouterProvider);

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
      routerConfig: router,
      // Desktop-width web gets the denser ERP theme; phones keep the
      // touch-first one. Re-evaluated as the browser window is resized.
      builder: (context, child) => isDesktopLayout(context)
          ? Theme(data: AppTheme.desktopTheme(Theme.of(context)), child: child!)
          : child!,
    );
  }
}
