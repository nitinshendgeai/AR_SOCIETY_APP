import 'package:ar_society_app/core/config/constants.dart';

/// Domain entity for authenticated user.
/// Roles come from the JWT payload and /auth/me response.
class UserEntity {
  final String id;
  final String email;
  final String fullName;
  final List<String> roles;
  final String? phone;
  final String? profileImage;
  final bool mustChangePassword;

  const UserEntity({
    required this.id,
    required this.email,
    required this.fullName,
    required this.roles,
    this.phone,
    this.profileImage,
    this.mustChangePassword = false,
  });

  // ── Role helpers ───────────────────────────────────────────────────────────

  bool get isAdmin =>
      roles.contains(AppConstants.roleAdmin) ||
      roles.contains(AppConstants.roleSuperAdmin) ||
      roles.contains(AppConstants.roleSocietyAdmin);

  bool get isCommittee => roles.contains(AppConstants.roleCommittee);
  bool get isResident => roles.contains(AppConstants.roleResident);
  bool get isSecurity => roles.contains(AppConstants.roleSecurity);
  bool get isStaff => roles.contains(AppConstants.roleStaff);

  bool get isAdminOrCommittee => isAdmin || isCommittee;

  /// Returns the primary role for routing decisions.
  /// Priority: Admin > Committee > Security > Staff > Resident
  String get primaryRole {
    if (isAdmin) return AppConstants.roleAdmin;
    if (isCommittee) return AppConstants.roleCommittee;
    if (isSecurity) return AppConstants.roleSecurity;
    if (isStaff) return AppConstants.roleStaff;
    return AppConstants.roleResident;
  }

  /// Role-based display label
  String get roleLabel {
    switch (primaryRole) {
      case AppConstants.roleAdmin:
        return 'Administrator';
      case AppConstants.roleCommittee:
        return 'Committee Member';
      case AppConstants.roleSecurity:
        return 'Security Officer';
      case AppConstants.roleStaff:
        return 'Staff Member';
      default:
        return 'Resident';
    }
  }

  UserEntity copyWith({
    String? id,
    String? email,
    String? fullName,
    List<String>? roles,
    String? phone,
    String? profileImage,
    bool? mustChangePassword,
  }) {
    return UserEntity(
      id: id ?? this.id,
      email: email ?? this.email,
      fullName: fullName ?? this.fullName,
      roles: roles ?? this.roles,
      phone: phone ?? this.phone,
      profileImage: profileImage ?? this.profileImage,
      mustChangePassword: mustChangePassword ?? this.mustChangePassword,
    );
  }

  @override
  String toString() => 'UserEntity($email, roles: $roles)';
}
