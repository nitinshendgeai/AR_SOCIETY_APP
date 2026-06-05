class RegistrationCredential {
  final String role;
  final String email;
  final String password;

  const RegistrationCredential({
    required this.role,
    required this.email,
    required this.password,
  });

  factory RegistrationCredential.fromJson(Map<String, dynamic> json) {
    return RegistrationCredential(
      role:     json['role'] as String,
      email:    json['email'] as String,
      password: json['password'] as String,
    );
  }
}

class RegistrationResult {
  final String societyId;
  final String societyName;
  final String societyCode;
  final String trialEndDate;
  final int trialDays;
  final List<RegistrationCredential> credentials;
  final String message;

  const RegistrationResult({
    required this.societyId,
    required this.societyName,
    required this.societyCode,
    required this.trialEndDate,
    required this.trialDays,
    required this.credentials,
    required this.message,
  });

  factory RegistrationResult.fromJson(Map<String, dynamic> json) {
    return RegistrationResult(
      societyId:   json['society_id'] as String,
      societyName: json['society_name'] as String,
      societyCode: json['society_code'] as String,
      trialEndDate: json['trial_end_date'] as String,
      trialDays:   json['trial_days'] as int,
      credentials: (json['credentials'] as List)
          .map((c) => RegistrationCredential.fromJson(c as Map<String, dynamic>))
          .toList(),
      message: json['message'] as String,
    );
  }

  RegistrationCredential? get adminCredential {
    final matches = credentials.where((c) => c.role == 'Society Admin');
    return matches.isEmpty ? null : matches.first;
  }
}
