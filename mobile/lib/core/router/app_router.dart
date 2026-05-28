import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/features/auth/presentation/screens/login_screen.dart';
import 'package:ar_society_app/features/splash/presentation/screens/splash_screen.dart';
import 'package:ar_society_app/features/dashboard/home_placeholder_screen.dart';

// ── Route names ───────────────────────────────────────────────────────────────

class AppRoutes {
  static const splash    = '/';
  static const login     = '/login';
  static const home      = '/home';
  // Role-specific roots — extended as modules are built
  static const adminHome     = '/admin';
  static const committeeHome = '/committee';
  static const residentHome  = '/resident';
  static const securityHome  = '/security';
  static const staffHome     = '/staff';
}

// ── Router provider ───────────────────────────────────────────────────────────

final appRouterProvider = Provider<GoRouter>((ref) {
  final authState = ref.watch(authProvider);

  return GoRouter(
    initialLocation: AppRoutes.splash,
    debugLogDiagnostics: false,
    redirect: (context, state) {
      final isLoading        = authState is AuthLoading || authState is AuthInitial;
      final isAuthenticated  = authState is AuthAuthenticated;
      final isOnSplash       = state.matchedLocation == AppRoutes.splash;
      final isOnLogin        = state.matchedLocation == AppRoutes.login;

      // Still checking session — stay on splash
      if (isLoading) {
        return isOnSplash ? null : AppRoutes.splash;
      }

      // Not authenticated → login
      if (!isAuthenticated && !isOnLogin) {
        return AppRoutes.login;
      }

      // Authenticated on login/splash → route to role-specific home
      if (isAuthenticated && (isOnLogin || isOnSplash)) {
        return _roleHome(ref);
      }

      return null; // no redirect
    },
    routes: [
      GoRoute(
        path: AppRoutes.splash,
        builder: (_, __) => const SplashScreen(),
      ),
      GoRoute(
        path: AppRoutes.login,
        builder: (_, __) => const LoginScreen(),
      ),
      // Generic home (resolves based on role)
      GoRoute(
        path: AppRoutes.home,
        redirect: (_, __) => _roleHome(ref),
      ),
      // Role-specific placeholders — replaced with real dashboards later
      GoRoute(
        path: AppRoutes.adminHome,
        builder: (_, __) => const HomePlaceholderScreen(role: 'Admin'),
      ),
      GoRoute(
        path: AppRoutes.committeeHome,
        builder: (_, __) => const HomePlaceholderScreen(role: 'Committee'),
      ),
      GoRoute(
        path: AppRoutes.residentHome,
        builder: (_, __) => const HomePlaceholderScreen(role: 'Resident'),
      ),
      GoRoute(
        path: AppRoutes.securityHome,
        builder: (_, __) => const HomePlaceholderScreen(role: 'Security'),
      ),
      GoRoute(
        path: AppRoutes.staffHome,
        builder: (_, __) => const HomePlaceholderScreen(role: 'Staff'),
      ),
    ],
    errorBuilder: (context, state) => Scaffold(
      body: Center(
        child: Text('Route not found: ${state.uri}'),
      ),
    ),
  );
});

/// Returns the home route for the current user's primary role.
String _roleHome(Ref ref) {
  final user = ref.read(currentUserProvider);
  if (user == null) return AppRoutes.login;
  switch (user.primaryRole) {
    case 'Admin':
    case 'Super Admin':
    case 'Society Admin':
      return AppRoutes.adminHome;
    case 'Committee':
      return AppRoutes.committeeHome;
    case 'Security':
      return AppRoutes.securityHome;
    case 'Staff':
      return AppRoutes.staffHome;
    default:
      return AppRoutes.residentHome;
  }
}
