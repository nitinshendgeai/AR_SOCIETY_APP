import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/features/auth/presentation/screens/login_screen.dart';
import 'package:ar_society_app/features/splash/presentation/screens/splash_screen.dart';
import 'package:ar_society_app/features/dashboard/role_dashboards.dart';
import 'package:ar_society_app/features/staff/presentation/screens/staff_home_screen.dart';
import 'package:ar_society_app/features/staff/presentation/screens/attendance_screen.dart';
import 'package:ar_society_app/features/staff/presentation/screens/duties_screen.dart';
import 'package:ar_society_app/features/staff/presentation/screens/handover_screen.dart';
import 'package:ar_society_app/features/auth/presentation/screens/change_password_screen.dart';
import 'package:ar_society_app/features/staff/presentation/providers/staff_providers.dart';
import 'package:ar_society_app/features/visitor/presentation/screens/visitor_list_screen.dart';
import 'package:ar_society_app/features/visitor/presentation/screens/create_visitor_screen.dart';
import 'package:ar_society_app/features/visitor/presentation/screens/visitor_approvals_screen.dart';
import 'package:ar_society_app/features/complaint/presentation/screens/complaint_list_screen.dart';
import 'package:ar_society_app/features/complaint/presentation/screens/complaint_detail_screen.dart';
import 'package:ar_society_app/features/complaint/presentation/screens/create_complaint_screen.dart';

class AppRoutes {
  static const splash             = '/';
  static const login              = '/login';
  static const changePassword     = '/change-password';
  static const home               = '/home';
  static const adminHome          = '/admin';
  static const committeeHome      = '/committee';
  static const residentHome       = '/resident';
  static const securityHome       = '/security';
  static const staffHome          = '/staff';
  static const staffAttendance    = '/staff/attendance/:staffId';
  static const staffDuties        = '/staff/duties/:staffId';
  static const staffHandover      = '/staff/handover/:staffId';
  // Visitor routes
  static const visitorsCreate     = '/visitors/create';
  static const visitorsMy         = '/visitors/my';
  static const visitorsPending    = '/visitors/pending';
  static const visitorsSociety    = '/visitors/society/:societyId';
  // Complaint routes
  static const complaints         = '/complaints';
  static const complaintsCreate   = '/complaints/create';
  static const complaintsDetail   = '/complaints/:complaintId';
  static const complaintsSociety  = '/complaints/society/:societyId';
}

final appRouterProvider = Provider<GoRouter>((ref) {
  final authState = ref.watch(authProvider);

  return GoRouter(
    initialLocation: AppRoutes.splash,
    debugLogDiagnostics: false,
    redirect: (context, state) {
      final isLoading       = authState is AuthLoading || authState is AuthInitial;
      final isAuthenticated = authState is AuthAuthenticated;
      final path = state.matchedLocation;
      final isOnSplash          = path == AppRoutes.splash;
      final isOnLogin           = path == AppRoutes.login;
      final isOnChangePassword  = path == AppRoutes.changePassword;

      if (isLoading) return isOnSplash ? null : AppRoutes.splash;
      if (!isAuthenticated && !isOnLogin) return AppRoutes.login;

      if (isAuthenticated) {
        final user = (authState as AuthAuthenticated).user;
        if (user.mustChangePassword && !isOnChangePassword) {
          return AppRoutes.changePassword;
        }
        if (!user.mustChangePassword && (isOnLogin || isOnSplash || isOnChangePassword)) {
          return _roleHome(ref);
        }
      }

      return null;
    },
    routes: [
      GoRoute(path: AppRoutes.splash, builder: (_, __) => const SplashScreen()),
      GoRoute(path: AppRoutes.login,  builder: (_, __) => const LoginScreen()),
      GoRoute(path: AppRoutes.changePassword,
          builder: (_, __) => const ChangePasswordScreen()),
      GoRoute(path: AppRoutes.home,   redirect: (_, __) => _roleHome(ref)),
      GoRoute(path: AppRoutes.adminHome,
          builder: (_, __) => const AdminDashboardScreen()),
      GoRoute(path: AppRoutes.committeeHome,
          builder: (_, __) => const CommitteeDashboardScreen()),
      GoRoute(path: AppRoutes.residentHome,
          builder: (_, __) => const ResidentDashboardScreen()),
      GoRoute(path: AppRoutes.securityHome,
          builder: (_, __) => const SecurityDashboardScreen()),
      GoRoute(path: AppRoutes.staffHome,
          builder: (_, __) => const StaffHomeScreen()),
      GoRoute(
        path: AppRoutes.staffAttendance,
        builder: (_, state) {
          final staffId = state.pathParameters['staffId']!;
          ref.read(staffIdProvider.notifier).state = staffId;
          return AttendanceScreen(staffId: staffId);
        },
      ),
      GoRoute(
        path: AppRoutes.staffDuties,
        builder: (_, state) => DutiesScreen(
            staffId: state.pathParameters['staffId']!),
      ),
      GoRoute(
        path: AppRoutes.staffHandover,
        builder: (_, state) => HandoverScreen(
          staffId: state.pathParameters['staffId']!,
          societyId: state.extra as String? ?? '',
        ),
      ),
      // Visitor routes (specific paths before parameterised)
      GoRoute(
        path: AppRoutes.visitorsCreate,
        builder: (_, state) => CreateVisitorScreen(
          societyId: state.extra as String? ??
              state.uri.queryParameters['societyId'] ?? '',
        ),
      ),
      GoRoute(
        path: AppRoutes.visitorsMy,
        builder: (_, __) => const VisitorListScreen(isMy: true),
      ),
      GoRoute(
        path: AppRoutes.visitorsPending,
        builder: (_, __) => const VisitorApprovalsScreen(),
      ),
      GoRoute(
        path: AppRoutes.visitorsSociety,
        builder: (_, state) => VisitorListScreen(
          isMy: false,
          societyId: state.pathParameters['societyId']!,
        ),
      ),
      // Complaint routes (literal 'create' and 'society' before :complaintId)
      GoRoute(
        path: AppRoutes.complaints,
        builder: (_, __) => const ComplaintListScreen(isMy: true),
      ),
      GoRoute(
        path: AppRoutes.complaintsCreate,
        builder: (_, state) => CreateComplaintScreen(
          societyId: state.uri.queryParameters['societyId'] ?? '',
        ),
      ),
      GoRoute(
        path: AppRoutes.complaintsSociety,
        builder: (_, state) => ComplaintListScreen(
          isMy: false,
          societyId: state.pathParameters['societyId']!,
        ),
      ),
      GoRoute(
        path: AppRoutes.complaintsDetail,
        builder: (_, state) => ComplaintDetailScreen(
          complaintId: state.pathParameters['complaintId']!,
        ),
      ),
    ],
    errorBuilder: (context, state) =>
        Scaffold(body: Center(child: Text('Route not found: \${state.uri}'))),
  );
});

String _roleHome(Ref ref) {
  final user = ref.read(currentUserProvider);
  if (user == null) return AppRoutes.login;
  switch (user.primaryRole) {
    case 'Admin':
    case 'Super Admin':
    case 'Society Admin': return AppRoutes.adminHome;
    case 'Committee':     return AppRoutes.committeeHome;
    case 'Security':      return AppRoutes.securityHome;
    case 'Staff':         return AppRoutes.staffHome;
    default:              return AppRoutes.residentHome;
  }
}
