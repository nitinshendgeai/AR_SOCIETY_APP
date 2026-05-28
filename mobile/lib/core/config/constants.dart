/// App-wide constants.
class AppConstants {
  // Storage keys
  static const String accessTokenKey = 'access_token';
  static const String refreshTokenKey = 'refresh_token';
  static const String userKey = 'user_data';

  // Timeouts
  static const int connectTimeoutMs = 15000;
  static const int receiveTimeoutMs = 15000;

  // Roles
  static const String roleAdmin = 'Admin';
  static const String roleCommittee = 'Committee';
  static const String roleResident = 'Resident';
  static const String roleSecurity = 'Security';
  static const String roleStaff = 'Staff';
  static const String roleSuperAdmin = 'Super Admin';
  static const String roleSocietyAdmin = 'Society Admin';
}
