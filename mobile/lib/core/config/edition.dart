import 'package:ar_society_app/features/auth/domain/entities/user_entity.dart';

/// Which build of the app this is, chosen at compile time with `--dart-define=APP_EDITION=field`.
///
/// * **full** (the default; the web app and any build without the flag): every screen, as before.
/// * **field**: the Android APK for the people who work on the ground and for residents — residents and tenants,
///   security, technical staff and gym trainers. Accounts, finance, administration and the other management screens
///   stay on the web app: they are not in this build's menu, their addresses bounce to the person's own dashboard,
///   and a web-only role (admin, committee, manager, platform admin) is told to use the web app at sign-in.
///
/// Like the menu and route guards, this is a convenience: the backend still refuses every request a role may not make.
class AppEdition {
  static const String _compiled = String.fromEnvironment('APP_EDITION');

  static bool get isField => _compiled == 'field';

  /// Roles that belong in the field build (the exact names the backend seeds, see docs/USERS_AND_ROLES.md).
  static const fieldRoles = <String>{
    'Resident',
    'Tenant',
    'Security Staff',
    'Security Supervisor',
    'Technical Staff',
    'Technical Supervisor',
    'Gym Trainer',
  };

  /// The menu entries (by form code) the field build keeps. Everything else lives on the web app.
  static const fieldFormCodes = <String>{
    'visitors',
    'parcels',
    'domestic_help',
    'complaints',
    'notices',
    'amenities',
    'meetings',
    'polls',
    'documents',
    'certificates',
    'my_bills',
    'edit_my_info',
    'lights_check',          // the electrician's and plumber's monthly check of the common lights
    'staff',                 // the Staff Portal: attendance, duties, checklists for security / technical / gym staff
  };

  /// Whether [user] may use the field build: has at least one field role and no web-only role.
  static bool allowsUser(UserEntity user) {
    if (user.isPlatformAdmin || user.isAdminOrCommittee || user.isManager) return false;
    return user.roles.any(fieldRoles.contains);
  }

  static const webOnlyMessage =
      'This app is for residents, security, technical and gym staff. Please use the web app for your role.';
}
