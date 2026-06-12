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
  // Catch any uncaught async/platform exception and print it to the browser
  // console so we can read it even in a minified release build.
  PlatformDispatcher.instance.onError = (error, stack) {
    print('[STARTUP_CRASH] PlatformDispatcher caught: $error');
    print('[STARTUP_CRASH] $stack');
    return true;
  };

  print('[STARTUP] 1 ensureInitialized');
  WidgetsFlutterBinding.ensureInitialized();

  // Catch any widget-layer exception (layout errors, build errors, etc.)
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
    print('[STARTUP_CRASH] ApiClient.initialize threw: $e');
    print('[STARTUP_CRASH] $s');
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
  runApp(
    const ProviderScope(
      child: ArSocietyApp(),
    ),
  );
  print('[STARTUP] 6 runApp returned');
}

class ArSocietyApp extends ConsumerWidget {
  const ArSocietyApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    print('[STARTUP] ArSocietyApp.build');
    try {
      final router = ref.watch(appRouterProvider);
      print('[STARTUP] appRouterProvider OK');
      return MaterialApp.router(
        title: Env.appName,
        debugShowCheckedModeBanner: false,
        theme: AppTheme.lightTheme,
        routerConfig: router,
      );
    } catch (e, s) {
      print('[STARTUP_CRASH] ArSocietyApp.build threw: $e');
      print('[STARTUP_CRASH] $s');
      rethrow;
    }
  }
}
