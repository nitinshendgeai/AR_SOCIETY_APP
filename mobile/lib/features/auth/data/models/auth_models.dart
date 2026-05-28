import 'package:ar_society_app/features/auth/domain/entities/user_entity.dart';

/// Maps to FastAPI TokenResponse schema.
class TokenModel {
  final String accessToken;
  final String refreshToken;
  final String tokenType;

  const TokenModel({
    required this.accessToken,
    required this.refreshToken,
    this.tokenType = 'bearer',
  });

  factory TokenModel.fromJson(Map<String, dynamic> json) => TokenModel(
        accessToken: json['access_token'] as String,
        refreshToken: json['refresh_token'] as String,
        tokenType: json['token_type'] as String? ?? 'bearer',
      );
}

/// Maps to FastAPI UserOut schema.
/// user_roles is a list of {role: {name: string}} objects.
class UserModel {
  final String id;
  final String email;
  final String fullName;
  final String? phone;
  final String? profileImage;
  final String status;
  final List<Map<String, dynamic>> userRoles;
  final bool mustChangePassword;

  const UserModel({
    required this.id,
    required this.email,
    required this.fullName,
    this.phone,
    this.profileImage,
    required this.status,
    required this.userRoles,
    this.mustChangePassword = false,
  });

  factory UserModel.fromJson(Map<String, dynamic> json) => UserModel(
        id: json['id'] as String,
        email: json['email'] as String,
        fullName: json['full_name'] as String,
        phone: json['phone'] as String?,
        profileImage: json['profile_image'] as String?,
        status: json['status'] as String? ?? 'active',
        mustChangePassword: json['must_change_password'] as bool? ?? false,
        userRoles: (json['user_roles'] as List<dynamic>?)
                ?.map((e) => e as Map<String, dynamic>)
                .toList() ??
            [],
      );

  /// Extract role names from nested user_roles structure.
  List<String> get roleNames => userRoles
      .map((ur) {
        final role = ur['role'] as Map<String, dynamic>?;
        return role?['name'] as String? ?? '';
      })
      .where((name) => name.isNotEmpty)
      .toList();

  UserEntity toEntity() => UserEntity(
        id: id,
        email: email,
        fullName: fullName,
        roles: roleNames,
        phone: phone,
        profileImage: profileImage,
        mustChangePassword: mustChangePassword,
      );
}
