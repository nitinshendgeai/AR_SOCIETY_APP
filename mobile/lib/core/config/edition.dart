import 'package:ar_society_app/features/auth/domain/entities/user_entity.dart';

/// Which build of the app this is, chosen at compile time with `--dart-define=APP_EDITION=field`.
///
/// * **full** (the default; the web app and any build without the flag): every screen, as before.
/// * **field**: the Android APK for residents and tenants, security, technical staff and gym trainers, plus the
///   society's administrators, committee members and managers for **Accounts** and **Stores** (inventory). Finance
///   and billing, administration and the other management screens stay on the web app: they are not in this
///   build's menu and their addresses bounce to the person's own dashboard. A platform admin is told to use the
///   web app at sign-in.
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
    'accounts',              // chart of accounts, vouchers, cash and bank books, ledgers (admin, committee, manager)
    'inventory',             // Stores: consumable stock, stock in, issue to staff and return (admin, committee, manager)
  };

  /// Whether [user] may use the field build: a field role, or a society admin, committee member or manager (who
  /// get Accounts and Stores here, see [fieldFormCodes]). A platform admin (no society of their own) uses the web app.
  static bool allowsUser(UserEntity user) {
    if (user.isPlatformAdmin) return false;
    if (user.isAdminOrCommittee || user.isManager) return true;
    return user.roles.any(fieldRoles.contains);
  }

  static const webOnlyMessage =
      'This app is for residents, society staff and administrators. Platform administrators, please use the web app.';
}
