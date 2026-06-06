class AdminUserModel {
  final String id;
  final String email;
  final String fullName;
  final String? phone;
  final String? profileImage;
  final String status;
  final List<String> roles;
  final bool mustChangePassword;
  final bool isActive;
  final String? createdAt;

  const AdminUserModel({
    required this.id,
    required this.email,
    required this.fullName,
    this.phone,
    this.profileImage,
    required this.status,
    required this.roles,
    this.mustChangePassword = false,
    this.isActive = true,
    this.createdAt,
  });

  factory AdminUserModel.fromJson(Map<String, dynamic> json) => AdminUserModel(
        id: json['id'] as String,
        email: json['email'] as String,
        fullName: json['full_name'] as String,
        phone: json['phone'] as String?,
        profileImage: json['profile_image'] as String?,
        status: json['status'] as String? ?? 'active',
        mustChangePassword: json['must_change_password'] as bool? ?? false,
        isActive: (json['status'] as String? ?? 'active') == 'active',
        createdAt: json['created_at'] as String?,
        roles: (json['roles'] as List<dynamic>?)
                ?.map((e) => e as String)
                .toList() ??
            [],
      );

  String get primaryRole => roles.isNotEmpty ? roles.first : 'No Role';
  String get initials {
    final parts = fullName.trim().split(' ');
    if (parts.length >= 2) return '${parts[0][0]}${parts[1][0]}'.toUpperCase();
    return fullName.isEmpty ? '?' : fullName[0].toUpperCase();
  }
}

class RoleModel {
  final String id;
  final String name;
  final String? description;

  const RoleModel({required this.id, required this.name, this.description});

  factory RoleModel.fromJson(Map<String, dynamic> json) => RoleModel(
        id: json['id'] as String,
        name: json['name'] as String,
        description: json['description'] as String?,
      );
}

class PasswordResetResult {
  final String temporaryPassword;

  const PasswordResetResult({required this.temporaryPassword});

  factory PasswordResetResult.fromJson(Map<String, dynamic> json) =>
      PasswordResetResult(
          temporaryPassword: json['temporary_password'] as String);
}
