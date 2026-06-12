import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/features/auth/presentation/screens/login_screen.dart';
import 'package:ar_society_app/features/splash/presentation/screens/splash_screen.dart';
import 'package:ar_society_app/features/dashboard/role_dashboards.dart'
    show AdminDashboardScreen, CommitteeDashboardScreen, ResidentDashboardScreen,
         SecurityDashboardScreen, ManagerDashboardScreen, SupervisorDashboardScreen;
import 'package:ar_society_app/features/staff/presentation/screens/staff_home_screen.dart';
import 'package:ar_society_app/features/staff/presentation/screens/attendance_screen.dart';
import 'package:ar_society_app/features/staff/presentation/screens/duties_screen.dart';
import 'package:ar_society_app/features/staff/presentation/screens/handover_screen.dart';
import 'package:ar_society_app/features/staff/presentation/screens/approval_screen.dart';
import 'package:ar_society_app/features/staff/presentation/screens/duty_assign_screen.dart';
import 'package:ar_society_app/features/staff/presentation/screens/staff_list_screen.dart';
import 'package:ar_society_app/features/staff/presentation/screens/staff_add_screen.dart';
import 'package:ar_society_app/features/staff/presentation/screens/staff_detail_screen.dart';
import 'package:ar_society_app/features/staff/presentation/screens/staff_edit_screen.dart';
import 'package:ar_society_app/features/staff/domain/entities/staff_entities.dart';
import 'package:ar_society_app/features/auth/presentation/screens/change_password_screen.dart';
import 'package:ar_society_app/features/staff/presentation/providers/staff_providers.dart';
import 'package:ar_society_app/features/visitor/presentation/screens/visitor_list_screen.dart';
import 'package:ar_society_app/features/visitor/presentation/screens/create_visitor_screen.dart';
import 'package:ar_society_app/features/visitor/presentation/screens/visitor_approvals_screen.dart';
import 'package:ar_society_app/features/complaint/presentation/screens/complaint_list_screen.dart';
import 'package:ar_society_app/features/complaint/presentation/screens/complaint_detail_screen.dart';
import 'package:ar_society_app/features/complaint/presentation/screens/create_complaint_screen.dart';
import 'package:ar_society_app/features/onboarding/presentation/screens/register_society_screen.dart';
import 'package:ar_society_app/features/onboarding/presentation/screens/trial_success_screen.dart';
import 'package:ar_society_app/features/onboarding/presentation/screens/setup_wizard_screen.dart';
import 'package:ar_society_app/features/onboarding/domain/registration_result.dart';
import 'package:ar_society_app/features/users/data/models/user_admin_models.dart';
import 'package:ar_society_app/features/users/presentation/screens/user_list_screen.dart';
import 'package:ar_society_app/features/users/presentation/screens/user_detail_screen.dart';
import 'package:ar_society_app/features/users/presentation/screens/create_user_screen.dart';
import 'package:ar_society_app/features/users/presentation/screens/edit_user_screen.dart';
import 'package:ar_society_app/features/users/presentation/screens/role_assignment_screen.dart';
import 'package:ar_society_app/features/society_settings/presentation/screens/society_settings_screen.dart';
import 'package:ar_society_app/features/society_structure/data/models/structure_models.dart';
import 'package:ar_society_app/features/society_structure/presentation/screens/wing_list_screen.dart';
import 'package:ar_society_app/features/society_structure/presentation/screens/wing_form_screen.dart';
import 'package:ar_society_app/features/society_structure/presentation/screens/floor_list_screen.dart';
import 'package:ar_society_app/features/society_structure/presentation/screens/floor_form_screen.dart';
import 'package:ar_society_app/features/society_structure/presentation/screens/flat_list_screen.dart';
import 'package:ar_society_app/features/society_structure/presentation/screens/flat_form_screen.dart';
import 'package:ar_society_app/features/society_structure/presentation/screens/flat_detail_screen.dart';
import 'package:ar_society_app/features/society_structure/presentation/screens/setup_wizard_screen.dart' as structure_wizard;

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
  static const staffApprovals     = '/staff/approvals';
  static const staffAssignDuty    = '/staff/assign-duty';
  static const staffList          = '/staff/list';
  static const staffAdd           = '/staff/add';
  static const staffDetail        = '/staff/:staffId/detail';
  static const staffEdit          = '/staff/:staffId/edit';
  static const managerHome        = '/manager';
  static const supervisorHome     = '/supervisor';
  // Visitor routes
  static const visitorsCreate     = '/visitors/create';
  static const visitorsMy         = '/visitors/my';
  static const visitorsPending    = '/visitors/pending';
  static const visitorsSociety    = '/visitors/society/:societyId';
  // Onboarding routes
  static const registerSociety    = '/register';
  static const trialSuccess       = '/trial-success';
  static const setupWizard        = '/setup-wizard';
  // Complaint routes
  static const complaints         = '/complaints';
  static const complaintsCreate   = '/complaints/create';
  static const complaintsDetail   = '/complaints/:complaintId';
  static const complaintsSociety  = '/complaints/society/:societyId';
  // Users & Roles
  static const usersList          = '/users';
  static const usersCreate        = '/users/create';
  static const usersDetail        = '/users/:userId';
  static const usersEdit          = '/users/:userId/edit';
  static const usersRoles         = '/users/:userId/roles';
  // Society Settings
  static const societySettings    = '/society-settings';
  // Society Structure
  static const wingsList          = '/wings';
  static const wingForm           = '/wings/form';
  static const floorsByWing       = '/wings/:wingId/floors';
  static const floorForm          = '/wings/:wingId/floors/form';
  static const flatsList          = '/flats';
  static const flatsByWing        = '/wings/:wingId/flats';
  static const flatDetail         = '/flats/detail';
  static const flatForm           = '/flats/form';
  static const structureWizard    = '/structure-wizard';
}

// ── Router provider ───────────────────────────────────────────────────────────
//
// appRouterProvider watches authProvider directly. Riverpod rebuilds the router
// whenever auth state changes. This is the safe pattern: no ref.read() inside
// GoRouter callbacks (which run outside Riverpod's build context and fail in
// dart2js release builds with "Instance of 'minified:...'").

final appRouterProvider = Provider<GoRouter>((ref) {
  final authState = ref.watch(authProvider);

  final router = GoRouter(
    initialLocation: AppRoutes.splash,
    debugLogDiagnostics: false,

    redirect: (context, state) {
      final path = state.matchedLocation;

      final isAuthenticated     = authState is AuthAuthenticated;
      final isOnSplash          = path == AppRoutes.splash;
      final isOnLogin           = path == AppRoutes.login;
      final isOnChangePassword  = path == AppRoutes.changePassword;
      final isOnSetupWizard     = path == AppRoutes.setupWizard;
      final isPublicRoute       = path == AppRoutes.registerSociety ||
                                  path == AppRoutes.trialSuccess;

      debugPrint('[ROUTE_REDIRECT] path=$path '
          'state=${authState.runtimeType} '
          'isAuth=$isAuthenticated');

      // Very first state before checkSession runs — hold on splash.
      // AuthLoading during login should NOT redirect away from login screen.
      if (authState is AuthInitial) {
        debugPrint('[ROUTE_REDIRECT] → AuthInitial: '
            '${isOnSplash ? "stay on splash" : "→ splash"}');
        return isOnSplash ? null : AppRoutes.splash;
      }

      // Mid-flight (session check or login in progress): stay wherever we are.
      if (authState is AuthLoading) {
        debugPrint('[ROUTE_REDIRECT] → AuthLoading: no redirect (stay on current screen)');
        return null;
      }

      // Not authenticated and not on a public page → login
      if (!isAuthenticated && !isOnLogin && !isPublicRoute) {
        debugPrint('[ROUTE_REDIRECT] → unauthenticated, → login');
        return AppRoutes.login;
      }

      if (isAuthenticated) {
        final user = (authState as AuthAuthenticated).user;
        debugPrint('[AUTH_STATE_UPDATED] user=${user.email} '
            'roles=${user.roles} primaryRole=${user.primaryRole} '
            'mustChangePassword=${user.mustChangePassword}');

        // 1. Force password change before anything else.
        if (user.mustChangePassword && !isOnChangePassword) {
          debugPrint('[ROUTE_REDIRECT] → must change password');
          return AppRoutes.changePassword;
        }

        // 2. After password change, require terms acceptance via setup wizard.
        if (!user.mustChangePassword && !user.termsAccepted && !isOnSetupWizard) {
          debugPrint('[ROUTE_REDIRECT] → terms not accepted, → setup wizard');
          return AppRoutes.setupWizard;
        }

        // 3. Once setup is complete, redirect away from auth/setup screens.
        if (!user.mustChangePassword && user.termsAccepted &&
            (isOnLogin || isOnSplash || isOnChangePassword || isOnSetupWizard)) {
          final home = _roleHome(ref);
          debugPrint('[ROUTE_REDIRECT] → role home: $home');
          return home;
        }
      }

      debugPrint('[ROUTE_REDIRECT] → null (no redirect)');
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
      GoRoute(path: AppRoutes.managerHome,
          builder: (_, __) => const ManagerDashboardScreen()),
      GoRoute(path: AppRoutes.supervisorHome,
          builder: (_, __) => const SupervisorDashboardScreen()),
      GoRoute(path: AppRoutes.staffHome,
          builder: (_, __) => const StaffHomeScreen()),
      GoRoute(
        path: AppRoutes.staffApprovals,
        builder: (_, state) {
          final societyId = state.extra as String? ?? '';
          return AttendanceApprovalScreen(societyId: societyId);
        },
      ),
      GoRoute(
        path: AppRoutes.staffAssignDuty,
        builder: (_, state) {
          final extra = state.extra as Map<String, dynamic>? ?? {};
          return DutyAssignScreen(
            societyId: extra['societyId'] as String? ?? '',
            preSelectedStaffId: extra['staffId'] as String?,
          );
        },
      ),
      GoRoute(
        path: AppRoutes.staffList,
        builder: (_, state) {
          final dept = state.uri.queryParameters['department'];
          return StaffListScreen(filterDepartment: dept);
        },
      ),
      // Staff Master CRUD — literal /add before parameterised /:staffId/*
      GoRoute(
        path: AppRoutes.staffAdd,
        builder: (_, __) => const StaffAddScreen(),
      ),
      GoRoute(
        path: AppRoutes.staffDetail,
        builder: (_, state) {
          final staff = state.extra as StaffEntity;
          return StaffDetailScreen(staff: staff);
        },
      ),
      GoRoute(
        path: AppRoutes.staffEdit,
        builder: (_, state) {
          final staff = state.extra as StaffEntity;
          return StaffEditScreen(staff: staff);
        },
      ),
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
      // Onboarding wizard (auth-gated; redirect target for new users)
      GoRoute(
        path: AppRoutes.setupWizard,
        builder: (_, __) => const SetupWizardScreen(),
      ),
      GoRoute(
        path: AppRoutes.registerSociety,
        builder: (_, __) => const RegisterSocietyScreen(),
      ),
      GoRoute(
        path: AppRoutes.trialSuccess,
        builder: (_, state) {
          final result = state.extra as RegistrationResult;
          return TrialSuccessScreen(result: result);
        },
      ),
      // Users & Roles (literal 'create' before :userId)
      GoRoute(
        path: AppRoutes.usersList,
        builder: (_, __) => const UserListScreen(),
      ),
      GoRoute(
        path: AppRoutes.usersCreate,
        builder: (_, __) => const CreateUserScreen(),
      ),
      GoRoute(
        path: AppRoutes.usersEdit,
        builder: (_, state) {
          final user = state.extra as AdminUserModel;
          return EditUserScreen(user: user);
        },
      ),
      GoRoute(
        path: AppRoutes.usersRoles,
        builder: (_, state) {
          final user = state.extra as AdminUserModel;
          return RoleAssignmentScreen(user: user);
        },
      ),
      GoRoute(
        path: AppRoutes.usersDetail,
        builder: (_, state) =>
            UserDetailScreen(userId: state.pathParameters['userId']!),
      ),
      // Society Settings
      GoRoute(
        path: AppRoutes.societySettings,
        builder: (_, __) => const SocietySettingsScreen(),
      ),
      // Society Structure — Wings
      GoRoute(
        path: AppRoutes.wingsList,
        builder: (_, __) => const WingListScreen(),
      ),
      GoRoute(
        path: AppRoutes.wingForm,
        builder: (_, state) =>
            WingFormScreen(wing: state.extra as WingModel?),
      ),
      // Society Structure — Floors (nested under wing)
      GoRoute(
        path: AppRoutes.floorsByWing,
        builder: (_, state) =>
            FloorListScreen(wing: state.extra as WingModel),
      ),
      GoRoute(
        path: AppRoutes.floorForm,
        builder: (_, state) {
          final extra = state.extra as Map<String, dynamic>;
          return FloorFormScreen(
            wing:  extra['wing'] as WingModel,
            floor: extra['floor'] as FloorModel?,
          );
        },
      ),
      // Society Structure — Flats
      GoRoute(
        path: AppRoutes.flatsList,
        builder: (_, __) => const FlatListScreen(),
      ),
      GoRoute(
        path: AppRoutes.flatsByWing,
        builder: (_, state) {
          final extra = state.extra as Map<String, dynamic>?;
          return FlatListScreen(
            filterWing:  extra?['wing'] as WingModel?,
            filterFloor: extra?['floor'] as FloorModel?,
          );
        },
      ),
      GoRoute(
        path: AppRoutes.flatDetail,
        builder: (_, state) =>
            FlatDetailScreen(flat: state.extra as FlatModel),
      ),
      GoRoute(
        path: AppRoutes.flatForm,
        builder: (_, state) {
          final extra = state.extra as Map<String, dynamic>?;
          return FlatFormScreen(
            flat:         extra?['flat'] as FlatModel?,
            defaultWing:  extra?['wing'] as WingModel?,
            defaultFloor: extra?['floor'] as FloorModel?,
          );
        },
      ),
      // Society Structure wizard (wings/floors/flats setup)
      GoRoute(
        path: AppRoutes.structureWizard,
        builder: (_, __) => const structure_wizard.SetupWizardScreen(),
      ),
    ],
    errorBuilder: (context, state) =>
        Scaffold(body: Center(child: Text('Route not found: ${state.uri}'))),
  );

  return router;
});

String _roleHome(Ref ref) {
  final user = ref.read(currentUserProvider);
  debugPrint('[ROUTE_REDIRECT] _roleHome: user=${user?.email} '
      'primaryRole=${user?.primaryRole}');
  if (user == null) return AppRoutes.login;
  switch (user.primaryRole) {
    case 'Admin':
    case 'Super Admin':
    case 'Society Admin': return AppRoutes.adminHome;
    case 'Committee':     return AppRoutes.committeeHome;
    case 'Security':      return AppRoutes.securityHome;
    case 'Manager':       return AppRoutes.managerHome;
    case 'Security Supervisor':
    case 'Housekeeping Supervisor':
    case 'Supervisor':    return AppRoutes.supervisorHome;
    case 'Staff':         return AppRoutes.staffHome;
    default:              return AppRoutes.residentHome;
  }
}
