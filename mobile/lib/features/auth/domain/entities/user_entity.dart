import 'package:ar_society_app/core/config/constants.dart';
import 'package:ar_society_app/features/auth/domain/entities/society_choice.dart';

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
  final bool termsAccepted;
  final bool setupCompleted;
  final String? societyId;

  /// The optional services this user's society can use (the platform owner may switch some off); null means
  /// not limited, e.g. the platform admin or a session from before this was sent.
  final List<String>? enabledServices;

  /// The societies this person can switch between (empty when they have just the one).
  final List<SocietyChoice> societies;

  const UserEntity({
    required this.id,
    required this.email,
    required this.fullName,
    required this.roles,
    this.phone,
    this.profileImage,
    this.mustChangePassword = false,
    this.termsAccepted = false,
    this.setupCompleted = false,
    this.societyId,
    this.enabledServices,
    this.societies = const [],
  });

  // ── Role helpers ───────────────────────────────────────────────────────────

  bool get isAdmin =>
      roles.contains(AppConstants.roleAdmin) ||
      roles.contains(AppConstants.roleSuperAdmin) ||
      roles.contains(AppConstants.roleSocietyAdmin);

  bool get isCommittee => roles.contains(AppConstants.roleCommittee) ||
      roles.any((r) => r.startsWith('Committee'));

  bool get isResident => roles.contains(AppConstants.roleResident);
  bool get isSecurity => roles.contains(AppConstants.roleSecurity) ||
      roles.any((r) => r.contains('Security'));
  bool get isStaff => roles.contains(AppConstants.roleStaff) ||
      roles.any((r) => r.contains('Staff') || r.contains('Supervisor'));

  bool get isManager => roles.contains(AppConstants.roleManager);

  /// Runs the platform itself (every society), belonging to none.
  bool get isPlatformAdmin => roles.contains('Platform Admin');

  bool get isAdminOrCommittee => isAdmin || isCommittee;

  /// Whether the society has this optional service switched on (see backend services_catalog keys).
  bool hasService(String key) => enabledServices == null || enabledServices!.contains(key);

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
    bool? termsAccepted,
    bool? setupCompleted,
    String? societyId,
    List<String>? enabledServices,
    List<SocietyChoice>? societies,
  }) {
    return UserEntity(
      id: id ?? this.id,
      email: email ?? this.email,
      fullName: fullName ?? this.fullName,
      roles: roles ?? this.roles,
      phone: phone ?? this.phone,
      profileImage: profileImage ?? this.profileImage,
      mustChangePassword: mustChangePassword ?? this.mustChangePassword,
      termsAccepted: termsAccepted ?? this.termsAccepted,
      setupCompleted: setupCompleted ?? this.setupCompleted,
      societyId: societyId ?? this.societyId,
      enabledServices: enabledServices ?? this.enabledServices,
      societies: societies ?? this.societies,
    );
  }

  @override
  String toString() => 'UserEntity($email, roles: $roles, societyId: $societyId)';
}
