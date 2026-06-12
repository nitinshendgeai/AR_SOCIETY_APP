import 'dart:ui';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/config/env.dart';
import 'package:ar_society_app/core/router/app_router.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';

Future<void> main() async {
  PlatformDispatcher.instance.onError = (error, stack) {
    print('[STARTUP_CRASH] PlatformDispatcher: $error');
    print('[STARTUP_CRASH] $stack');
    return true;
  };

  print('[STARTUP] 1 ensureInitialized');
  WidgetsFlutterBinding.ensureInitialized();

  FlutterError.onError = (details) {
    print('[STARTUP_CRASH] FlutterError: ${details.exception}');
    print('[STARTUP_CRASH] ${details.stack}');
  };

  print('[STARTUP] 2 dotenv.load');
  await dotenv.load(fileName: '.env').catchError((_) {});

  print('[STARTUP] 3 ApiClient.initialize');
  try {
    ApiClient.initialize();
  } catch (e, s) {
    print('[STARTUP_CRASH] ApiClient.initialize: $e\n$s');
  }

  print('[STARTUP] 4 platform setup');
  if (!kIsWeb) {
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

  print('[STARTUP] 5 runApp');
  runApp(const ProviderScope(child: ArSocietyApp()));
  print('[STARTUP] 6 runApp returned');
}

class ArSocietyApp extends ConsumerWidget {
  const ArSocietyApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    print('[STARTUP] ArSocietyApp.build');
    try {
      print('[STARTUP] watching appRouterProvider');
      final router = ref.watch(appRouterProvider);
      print('[STARTUP] appRouterProvider OK');

      print('[STARTUP] Env.appName');
      final title = Env.appName;
      print('[STARTUP] title=$title');

      print('[STARTUP] AppTheme.lightTheme');
      ThemeData theme;
      try {
        theme = AppTheme.lightTheme;
        print('[STARTUP] lightTheme OK');
      } catch (e, s) {
        print('[STARTUP_CRASH] AppTheme.lightTheme threw: $e\n$s');
        theme = ThemeData(useMaterial3: true);
        print('[STARTUP] using fallback ThemeData');
      }

      print('[STARTUP] MaterialApp.router');
      final app = MaterialApp.router(
        title: title,
        debugShowCheckedModeBanner: false,
        theme: theme,
        routerConfig: router,
      );
      print('[STARTUP] MaterialApp.router OK');
      return app;
    } catch (e, s) {
      print('[STARTUP_CRASH] ArSocietyApp.build: $e\n$s');
      rethrow;
    }
  }
}
