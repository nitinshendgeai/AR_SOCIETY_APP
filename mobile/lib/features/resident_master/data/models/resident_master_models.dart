// Resident Master domain models — Resident, Tenant, Agreement, Occupancy log,
// Vehicle. Mirrors the backend's ResidentOut/TenantOut/AgreementOut/
// OccupancyLogOut/VehicleOut response shapes (Phase M1.2/M1.3 backend).
//
// None of these carry flat/wing display fields — the backend intentionally
// only returns flat_id (see backend/app/schemas/resident.py,
// backend/app/schemas/tenant.py). Screens enrich with flat/wing display data
// by cross-referencing the existing society_structure providers
// (flatsBySocietyProvider), never by duplicating that lookup logic here.

// ── Resident ──────────────────────────────────────────────────────────────

enum ResidentType { owner, coOwner, family, dependent }

extension ResidentTypeX on ResidentType {
  static ResidentType fromString(String v) => switch (v) {
        'owner' => ResidentType.owner,
        'co_owner' => ResidentType.coOwner,
        'family' => ResidentType.family,
        'dependent' => ResidentType.dependent,
        _ => ResidentType.family,
      };

  String get value => switch (this) {
        ResidentType.owner => 'owner',
        ResidentType.coOwner => 'co_owner',
        ResidentType.family => 'family',
        ResidentType.dependent => 'dependent',
      };

  String get label => switch (this) {
        ResidentType.owner => 'Owner',
        ResidentType.coOwner => 'Co-Owner',
        ResidentType.family => 'Family',
        ResidentType.dependent => 'Dependent',
      };

  /// Only Owner/Co-Owner may be marked primary — mirrors
  /// backend `_PRIMARY_ALLOWED_TYPES` in resident_service.py /
  /// schemas/resident.py, enforced client-side before submission.
  bool get canBePrimary => this == ResidentType.owner || this == ResidentType.coOwner;
}

enum CommPreference { appOnly, sms, email, whatsapp, all }

extension CommPreferenceX on CommPreference {
  static CommPreference fromString(String? v) => switch (v) {
        'sms' => CommPreference.sms,
        'email' => CommPreference.email,
        'whatsapp' => CommPreference.whatsapp,
        'all' => CommPreference.all,
        _ => CommPreference.appOnly,
      };

  String get value => switch (this) {
        CommPreference.appOnly => 'app_only',
        CommPreference.sms => 'sms',
        CommPreference.email => 'email',
        CommPreference.whatsapp => 'whatsapp',
        CommPreference.all => 'all',
      };

  String get label => switch (this) {
        CommPreference.appOnly => 'App only',
        CommPreference.sms => 'SMS',
        CommPreference.email => 'Email',
        CommPreference.whatsapp => 'WhatsApp',
        CommPreference.all => 'All channels',
      };
}

class ResidentModel {
  final String id;
  final String flatId;
  final String? userId;
  final String fullName;
  final ResidentType residentType;
  final bool isPrimary;
  final String? phone;
  final String? email;
  final String? dateOfBirth;
  final String? moveInDate;
  final String? moveOutDate;
  final String? idProofType;
  final String? idProofNumber;
  final bool kycVerified;
  final String? kycDocUrl;
  final String? emergencyContactName;
  final String? emergencyContactPhone;
  final CommPreference commPreference;
  final String? photoUrl;
  final int familyMemberCount;
  final bool isActive;
  final List<String> warnings;

  const ResidentModel({
    required this.id,
    required this.flatId,
    this.userId,
    required this.fullName,
    required this.residentType,
    required this.isPrimary,
    this.phone,
    this.email,
    this.dateOfBirth,
    this.moveInDate,
    this.moveOutDate,
    this.idProofType,
    this.idProofNumber,
    this.kycVerified = false,
    this.kycDocUrl,
    this.emergencyContactName,
    this.emergencyContactPhone,
    this.commPreference = CommPreference.appOnly,
    this.photoUrl,
    this.familyMemberCount = 0,
    this.isActive = true,
    this.warnings = const [],
  });

  factory ResidentModel.fromJson(Map<String, dynamic> j) => ResidentModel(
        id: j['id'] as String,
        flatId: j['flat_id'] as String,
        userId: j['user_id'] as String?,
        fullName: j['full_name'] as String,
        residentType: ResidentTypeX.fromString(j['resident_type'] as String? ?? 'family'),
        isPrimary: j['is_primary'] as bool? ?? false,
        phone: j['phone'] as String?,
        email: j['email'] as String?,
        dateOfBirth: j['date_of_birth'] as String?,
        moveInDate: j['move_in_date'] as String?,
        moveOutDate: j['move_out_date'] as String?,
        idProofType: j['id_proof_type'] as String?,
        idProofNumber: j['id_proof_number'] as String?,
        kycVerified: j['kyc_verified'] as bool? ?? false,
        kycDocUrl: j['kyc_doc_url'] as String?,
        emergencyContactName: j['emergency_contact_name'] as String?,
        emergencyContactPhone: j['emergency_contact_phone'] as String?,
        commPreference: CommPreferenceX.fromString(j['comm_preference'] as String?),
        photoUrl: j['photo_url'] as String?,
        familyMemberCount: j['family_member_count'] as int? ?? 0,
        isActive: j['is_active'] as bool? ?? true,
        warnings: (j['warnings'] as List<dynamic>?)?.map((e) => e.toString()).toList() ?? const [],
      );
}

// ── Tenant ────────────────────────────────────────────────────────────────

enum PoliceVerificationStatus { pending, submitted, verified, rejected }

extension PoliceVerificationStatusX on PoliceVerificationStatus {
  static PoliceVerificationStatus fromString(String? v) => switch (v) {
        'submitted' => PoliceVerificationStatus.submitted,
        'verified' => PoliceVerificationStatus.verified,
        'rejected' => PoliceVerificationStatus.rejected,
        _ => PoliceVerificationStatus.pending,
      };

  String get value => switch (this) {
        PoliceVerificationStatus.pending => 'pending',
        PoliceVerificationStatus.submitted => 'submitted',
        PoliceVerificationStatus.verified => 'verified',
        PoliceVerificationStatus.rejected => 'rejected',
      };

  String get label => switch (this) {
        PoliceVerificationStatus.pending => 'Pending',
        PoliceVerificationStatus.submitted => 'Submitted',
        PoliceVerificationStatus.verified => 'Verified',
        PoliceVerificationStatus.rejected => 'Rejected',
      };
}

class TenantModel {
  final String id;
  final String flatId;
  final String? userId;
  final String fullName;
  final String? phone;
  final String? email;
  final String? agreementStartDate;
  final String? agreementEndDate;
  final String? monthlyRent;
  final String? securityDeposit;
  final String? agreementDocUrl;
  final String? idProofType;
  final String? idProofNumber;
  final bool kycVerified;
  final String? kycDocUrl;
  final PoliceVerificationStatus policeVerificationStatus;
  final String? policeVerificationDate;
  final String? emergencyContactName;
  final String? emergencyContactPhone;
  final String? moveInDate;
  final String? moveOutDate;
  final String? remarks;
  final String? activeAgreementId;
  final bool isActive;
  final List<String> warnings;

  const TenantModel({
    required this.id,
    required this.flatId,
    this.userId,
    required this.fullName,
    this.phone,
    this.email,
    this.agreementStartDate,
    this.agreementEndDate,
    this.monthlyRent,
    this.securityDeposit,
    this.agreementDocUrl,
    this.idProofType,
    this.idProofNumber,
    this.kycVerified = false,
    this.kycDocUrl,
    this.policeVerificationStatus = PoliceVerificationStatus.pending,
    this.policeVerificationDate,
    this.emergencyContactName,
    this.emergencyContactPhone,
    this.moveInDate,
    this.moveOutDate,
    this.remarks,
    this.activeAgreementId,
    this.isActive = true,
    this.warnings = const [],
  });

  /// True once move-out has been recorded — i.e. no longer the active
  /// occupant, independent of the soft-delete `isActive` flag.
  bool get hasMovedOut => moveOutDate != null;

  factory TenantModel.fromJson(Map<String, dynamic> j) => TenantModel(
        id: j['id'] as String,
        flatId: j['flat_id'] as String,
        userId: j['user_id'] as String?,
        fullName: j['full_name'] as String,
        phone: j['phone'] as String?,
        email: j['email'] as String?,
        agreementStartDate: j['agreement_start_date'] as String?,
        agreementEndDate: j['agreement_end_date'] as String?,
        monthlyRent: j['monthly_rent']?.toString(),
        securityDeposit: j['security_deposit']?.toString(),
        agreementDocUrl: j['agreement_doc_url'] as String?,
        idProofType: j['id_proof_type'] as String?,
        idProofNumber: j['id_proof_number'] as String?,
        kycVerified: j['kyc_verified'] as bool? ?? false,
        kycDocUrl: j['kyc_doc_url'] as String?,
        policeVerificationStatus:
            PoliceVerificationStatusX.fromString(j['police_verification_status'] as String?),
        policeVerificationDate: j['police_verification_date'] as String?,
        emergencyContactName: j['emergency_contact_name'] as String?,
        emergencyContactPhone: j['emergency_contact_phone'] as String?,
        moveInDate: j['move_in_date'] as String?,
        moveOutDate: j['move_out_date'] as String?,
        remarks: j['remarks'] as String?,
        activeAgreementId: j['active_agreement_id'] as String?,
        isActive: j['is_active'] as bool? ?? true,
        warnings: (j['warnings'] as List<dynamic>?)?.map((e) => e.toString()).toList() ?? const [],
      );
}

// ── Agreement ─────────────────────────────────────────────────────────────

enum AgreementStatus { active, expired, renewed, terminated }

extension AgreementStatusX on AgreementStatus {
  static AgreementStatus fromString(String v) => switch (v) {
        'expired' => AgreementStatus.expired,
        'renewed' => AgreementStatus.renewed,
        'terminated' => AgreementStatus.terminated,
        _ => AgreementStatus.active,
      };

  String get label => switch (this) {
        AgreementStatus.active => 'Active',
        AgreementStatus.expired => 'Expired',
        AgreementStatus.renewed => 'Renewed',
        AgreementStatus.terminated => 'Terminated',
      };
}

class AgreementModel {
  final String id;
  final String societyId;
  final String flatId;
  final String tenantId;
  final String startDate;
  final String endDate;
  final AgreementStatus status;
  final String? monthlyRent;
  final String? securityDeposit;
  final String? documentUrl;
  final String? renewalOfId;
  final String? terminationReason;

  const AgreementModel({
    required this.id,
    required this.societyId,
    required this.flatId,
    required this.tenantId,
    required this.startDate,
    required this.endDate,
    required this.status,
    this.monthlyRent,
    this.securityDeposit,
    this.documentUrl,
    this.renewalOfId,
    this.terminationReason,
  });

  factory AgreementModel.fromJson(Map<String, dynamic> j) => AgreementModel(
        id: j['id'] as String,
        societyId: j['society_id'] as String,
        flatId: j['flat_id'] as String,
        tenantId: j['tenant_id'] as String,
        startDate: j['start_date'] as String,
        endDate: j['end_date'] as String,
        status: AgreementStatusX.fromString(j['status'] as String? ?? 'active'),
        monthlyRent: j['monthly_rent']?.toString(),
        securityDeposit: j['security_deposit']?.toString(),
        documentUrl: j['document_url'] as String?,
        renewalOfId: j['renewal_of_id'] as String?,
        terminationReason: j['termination_reason'] as String?,
      );
}

// ── Occupancy log ─────────────────────────────────────────────────────────

enum OccupancyEventType {
  residentMoveIn,
  residentMoveOut,
  tenantMoveIn,
  tenantMoveOut,
  flatVacant,
  ownershipTransfer,
}

extension OccupancyEventTypeX on OccupancyEventType {
  static OccupancyEventType fromString(String v) => switch (v) {
        'resident_move_out' => OccupancyEventType.residentMoveOut,
        'tenant_move_in' => OccupancyEventType.tenantMoveIn,
        'tenant_move_out' => OccupancyEventType.tenantMoveOut,
        'flat_vacant' => OccupancyEventType.flatVacant,
        'ownership_transfer' => OccupancyEventType.ownershipTransfer,
        _ => OccupancyEventType.residentMoveIn,
      };

  String get label => switch (this) {
        OccupancyEventType.residentMoveIn => 'Resident moved in',
        OccupancyEventType.residentMoveOut => 'Resident moved out',
        OccupancyEventType.tenantMoveIn => 'Tenant moved in',
        OccupancyEventType.tenantMoveOut => 'Tenant moved out',
        OccupancyEventType.flatVacant => 'Flat vacated',
        OccupancyEventType.ownershipTransfer => 'Ownership transferred',
      };
}

class OccupancyLogModel {
  final String flatId;
  final OccupancyEventType eventType;
  final String eventDate;
  final String? residentId;
  final String? tenantId;
  final String? notes;
  final String createdAt;

  const OccupancyLogModel({
    required this.flatId,
    required this.eventType,
    required this.eventDate,
    this.residentId,
    this.tenantId,
    this.notes,
    required this.createdAt,
  });

  factory OccupancyLogModel.fromJson(Map<String, dynamic> j) => OccupancyLogModel(
        flatId: j['flat_id'] as String,
        eventType: OccupancyEventTypeX.fromString(j['event_type'] as String? ?? 'resident_move_in'),
        eventDate: j['event_date'] as String,
        residentId: j['resident_id'] as String?,
        tenantId: j['tenant_id'] as String?,
        notes: j['notes'] as String?,
        createdAt: j['created_at'] as String? ?? j['event_date'] as String,
      );
}

// ── Vehicle ───────────────────────────────────────────────────────────────

enum VehicleType { car, motorcycle, scooter, auto, truck, van, bicycle, other }

extension VehicleTypeX on VehicleType {
  static VehicleType fromString(String v) => switch (v) {
        'motorcycle' => VehicleType.motorcycle,
        'scooter' => VehicleType.scooter,
        'auto' => VehicleType.auto,
        'truck' => VehicleType.truck,
        'van' => VehicleType.van,
        'bicycle' => VehicleType.bicycle,
        'other' => VehicleType.other,
        _ => VehicleType.car,
      };

  String get value => switch (this) {
        VehicleType.car => 'car',
        VehicleType.motorcycle => 'motorcycle',
        VehicleType.scooter => 'scooter',
        VehicleType.auto => 'auto',
        VehicleType.truck => 'truck',
        VehicleType.van => 'van',
        VehicleType.bicycle => 'bicycle',
        VehicleType.other => 'other',
      };

  String get label => switch (this) {
        VehicleType.car => 'Car',
        VehicleType.motorcycle => 'Motorcycle',
        VehicleType.scooter => 'Scooter',
        VehicleType.auto => 'Auto',
        VehicleType.truck => 'Truck',
        VehicleType.van => 'Van',
        VehicleType.bicycle => 'Bicycle',
        VehicleType.other => 'Other',
      };
}

class VehicleModel {
  final String id;
  final String societyId;
  final String? flatId;
  final String? residentId;
  final String? tenantId;
  final String vehicleNumber;
  final VehicleType vehicleType;
  final String? make;
  final String? model;
  final String? color;
  final String? year;
  final String? parkingSlot;
  final String? rfidTag;
  final String? insuranceExpiry;
  final String? rcNumber;
  final bool isActive;

  const VehicleModel({
    required this.id,
    required this.societyId,
    this.flatId,
    this.residentId,
    this.tenantId,
    required this.vehicleNumber,
    required this.vehicleType,
    this.make,
    this.model,
    this.color,
    this.year,
    this.parkingSlot,
    this.rfidTag,
    this.insuranceExpiry,
    this.rcNumber,
    this.isActive = true,
  });

  factory VehicleModel.fromJson(Map<String, dynamic> j) => VehicleModel(
        id: j['id'] as String,
        societyId: j['society_id'] as String,
        flatId: j['flat_id'] as String?,
        residentId: j['resident_id'] as String?,
        tenantId: j['tenant_id'] as String?,
        vehicleNumber: j['vehicle_number'] as String,
        vehicleType: VehicleTypeX.fromString(j['vehicle_type'] as String? ?? 'car'),
        make: j['make'] as String?,
        model: j['model'] as String?,
        color: j['color'] as String?,
        year: j['year'] as String?,
        parkingSlot: j['parking_slot'] as String?,
        rfidTag: j['rfid_tag'] as String?,
        insuranceExpiry: j['insurance_expiry'] as String?,
        rcNumber: j['rc_number'] as String?,
        isActive: j['is_active'] as bool? ?? true,
      );
}
