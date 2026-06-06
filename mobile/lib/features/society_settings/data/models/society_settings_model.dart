class SocietySettingsModel {
  // Identity
  final String id;
  final String name;
  final String? societyCode;
  final String? address;
  final String? city;
  final String? state;
  final String? pincode;
  final String? country;
  final String? timezone;
  final String? website;
  final String? logoUrl;
  // Contact
  final String? contactEmail;
  final String? contactPhone;
  final String? contactPersonName;
  final String? emergencyContactName;
  final String? emergencyContactPhone;
  // Settings
  final int? maintenanceDay;
  final int? lateFeePercent;
  final bool allowTenantPortal;
  final bool requireVisitorApproval;
  // Trial & subscription (read-only)
  final String? accountStatus;
  final bool isTrial;
  final String? trialEndDate;
  final String? subscriptionPlan;
  final String? subscriptionStatus;
  // Limits & setup
  final int allowedUsers;
  final int allowedFlats;
  final bool setupCompleted;
  final int setupCompletionPercentage;

  const SocietySettingsModel({
    required this.id,
    required this.name,
    this.societyCode,
    this.address,
    this.city,
    this.state,
    this.pincode,
    this.country,
    this.timezone,
    this.website,
    this.logoUrl,
    this.contactEmail,
    this.contactPhone,
    this.contactPersonName,
    this.emergencyContactName,
    this.emergencyContactPhone,
    this.maintenanceDay,
    this.lateFeePercent,
    this.allowTenantPortal = true,
    this.requireVisitorApproval = true,
    this.accountStatus,
    this.isTrial = false,
    this.trialEndDate,
    this.subscriptionPlan,
    this.subscriptionStatus,
    this.allowedUsers = 50,
    this.allowedFlats = 100,
    this.setupCompleted = false,
    this.setupCompletionPercentage = 0,
  });

  factory SocietySettingsModel.fromJson(Map<String, dynamic> json) =>
      SocietySettingsModel(
        id: json['id'] as String,
        name: json['name'] as String,
        societyCode: json['society_code'] as String?,
        address: json['address'] as String?,
        city: json['city'] as String?,
        state: json['state'] as String?,
        pincode: json['pincode'] as String?,
        country: json['country'] as String?,
        timezone: json['timezone'] as String?,
        website: json['website'] as String?,
        logoUrl: json['logo_url'] as String?,
        contactEmail: json['contact_email'] as String?,
        contactPhone: json['contact_phone'] as String?,
        contactPersonName: json['contact_person_name'] as String?,
        emergencyContactName: json['emergency_contact_name'] as String?,
        emergencyContactPhone: json['emergency_contact_phone'] as String?,
        maintenanceDay: json['maintenance_day'] as int?,
        lateFeePercent: json['late_fee_percent'] as int?,
        allowTenantPortal: json['allow_tenant_portal'] as bool? ?? true,
        requireVisitorApproval:
            json['require_visitor_approval'] as bool? ?? true,
        accountStatus: json['account_status'] as String?,
        isTrial: json['is_trial'] as bool? ?? false,
        trialEndDate: json['trial_end_date'] as String?,
        subscriptionPlan: json['subscription_plan'] as String?,
        subscriptionStatus: json['subscription_status'] as String?,
        allowedUsers: json['allowed_users'] as int? ?? 50,
        allowedFlats: json['allowed_flats'] as int? ?? 100,
        setupCompleted: json['setup_completed'] as bool? ?? false,
        setupCompletionPercentage:
            json['setup_completion_percentage'] as int? ?? 0,
      );
}
