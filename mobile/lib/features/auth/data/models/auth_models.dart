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
/// roles is a flat List<String> returned by /auth/me via from_orm_with_roles.
class UserModel {
  final String id;
  final String email;
  final String fullName;
  final String? phone;
  final String? profileImage;
  final String status;
  final bool mustChangePassword;
  final bool termsAccepted;
  final bool setupCompleted;
  final String? societyId;
  final List<String> roles;

  const UserModel({
    required this.id,
    required this.email,
    required this.fullName,
    this.phone,
    this.profileImage,
    required this.status,
    this.mustChangePassword = false,
    this.termsAccepted = false,
    this.setupCompleted = false,
    this.societyId,
    required this.roles,
  });

  factory UserModel.fromJson(Map<String, dynamic> json) => UserModel(
        id: json['id'] as String,
        email: json['email'] as String,
        fullName: json['full_name'] as String,
        phone: json['phone'] as String?,
        profileImage: json['profile_image'] as String?,
        status: json['status'] as String? ?? 'active',
        mustChangePassword: json['must_change_password'] as bool? ?? false,
        termsAccepted: json['terms_accepted'] as bool? ?? false,
        setupCompleted: json['setup_completed'] as bool? ?? false,
        societyId: json['society_id'] as String?,
        roles: (json['roles'] as List<dynamic>?)
                ?.map((e) => e.toString())
                .toList() ??
            [],
      );

  UserEntity toEntity() => UserEntity(
        id: id,
        email: email,
        fullName: fullName,
        roles: roles,
        phone: phone,
        profileImage: profileImage,
        mustChangePassword: mustChangePassword,
        termsAccepted: termsAccepted,
        setupCompleted: setupCompleted,
        societyId: societyId,
      );
}
