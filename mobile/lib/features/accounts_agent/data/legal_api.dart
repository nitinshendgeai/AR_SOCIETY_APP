import 'package:dio/dio.dart';
import 'package:ar_society_app/core/api/api_client.dart';

/// Legal, bye-law and compliance side of the Accounts Agent. The server takes the society from the signed-in user;
/// nothing here sends a society id, and nothing here can change an accounting record.
int _i(Object? v) => (v is num) ? v.toInt() : int.tryParse('${v ?? 0}') ?? 0;
DateTime? _dt(Object? v) => v == null ? null : DateTime.tryParse(v as String);
Map<String, dynamic> _map(Object? v) => (v as Map?)?.cast<String, dynamic>() ?? const {};
List<Map<String, dynamic>> _list(Object? v) => [for (final x in (v as List? ?? const [])) (x as Map).cast<String, dynamic>()];
String _apiDate(DateTime d) => '${d.year.toString().padLeft(4, '0')}-${d.month.toString().padLeft(2, '0')}-${d.day.toString().padLeft(2, '0')}';

/// Plain words for the unified finding classes — a potential issue is never shown as a confirmed violation.
String classificationLabel(String c) => switch (c) {
      'CONFIRMED_ACCOUNTING_ERROR' => 'Confirmed accounting error',
      'CONFIRMED_STATUTORY_VALIDATION_FAILURE' => 'Confirmed statutory validation failure',
      'POTENTIAL_NON_COMPLIANCE' => 'Potential non-compliance (needs review)',
      'SUSPECTED_ACCOUNTING_ANOMALY' => 'Suspected accounting anomaly',
      'MISSING_DOCUMENTATION' => 'Missing documentation',
      'INTERNAL_POLICY_DEVIATION' => 'Internal policy deviation',
      'LEGAL_SOURCE_CONFLICT' => 'Legal source conflict',
      _ => 'Advisory observation',
    };

String verificationLabel(String v) => switch (v) {
      'VERIFIED_PRIMARY_SOURCE' => 'Verified (primary source)',
      'VERIFIED_SECONDARY_SOURCE' => 'Verified (secondary source)',
      'LEGAL_REVIEW_REQUIRED' => 'Legal review required',
      'REJECTED_SOURCE' => 'Rejected source',
      _ => 'Pending verification',
    };

const documentTypes = <String, String>{
  'REGISTERED_BYELAWS': 'Registered bye-laws',
  'BYELAW_AMENDMENT': 'Approved bye-law amendment',
  'AGM_MINUTES': 'AGM minutes',
  'SGM_MINUTES': 'SGM minutes',
  'COMMITTEE_MINUTES': 'Managing Committee minutes',
  'GOVERNMENT_ORDER': 'Government order',
  'REGISTRAR_CIRCULAR': 'Registrar circular',
  'BUDGET': 'Budget',
  'VENDOR_APPROVAL_POLICY': 'Vendor approval policy',
  'ACCOUNTING_POLICY': 'Accounting policy',
  'LEGAL_OPINION': 'Legal opinion',
  'AUDIT_REPORT': 'Audit report',
  'COURT_ORDER': 'Court / tribunal order',
  'OTHER': 'Other',
};

/// What status a verified document of each type takes (mirrors the server's rule).
const statusForType = <String, String>{
  'REGISTERED_BYELAWS': 'REGISTERED',
  'BYELAW_AMENDMENT': 'APPROVED_AMENDMENT',
  'AGM_MINUTES': 'GENERAL_BODY_APPROVED',
  'SGM_MINUTES': 'GENERAL_BODY_APPROVED',
  'BUDGET': 'GENERAL_BODY_APPROVED',
  'COMMITTEE_MINUTES': 'COMMITTEE_APPROVED',
  'VENDOR_APPROVAL_POLICY': 'COMMITTEE_APPROVED',
  'ACCOUNTING_POLICY': 'COMMITTEE_APPROVED',
};

class LegalSource {
  final Map<String, dynamic> raw;
  const LegalSource(this.raw);
  String get ruleCode => raw['rule_code'] as String? ?? '';
  int get version => _i(raw['version']);
  String get title => raw['title'] as String? ?? '';
  String? get source => raw['source'] as String?;
  String? get levelName => raw['source_level_name'] as String?;
  String get reference => [
        if (raw['act_section'] != null) 'Section ${raw['act_section']}',
        if (raw['rule_number'] != null) 'Rule ${raw['rule_number']}',
        if (raw['bye_law_number'] != null) 'Bye-law ${raw['bye_law_number']}',
        if (raw['clause'] != null) 'Clause ${raw['clause']}',
        if (raw['page'] != null) 'p. ${raw['page']}',
      ].join(' · ');
  String? get effectiveFrom => raw['effective_from'] as String?;
  String? get effectiveUntil => raw['effective_until'] as String?;
  String get legalStatus => raw['legal_status'] as String? ?? 'UNVERIFIED';
  String get verificationStatus => raw['verification_status'] as String? ?? 'PENDING_VERIFICATION';
  bool get verified => raw['verified'] as bool? ?? false;
  bool get societySpecific => raw['society_specific'] as bool? ?? false;
  String? get uncertainty => raw['uncertainty'] as String?;
  String? get note => raw['verification_note'] as String?;
  List<String> get blockedBy => [for (final x in (raw['blocked_by_reviews'] as List? ?? const [])) '$x'];
  static LegalSource? from(Object? v) => v == null ? null : LegalSource(_map(v));
}

class OverviewSection {
  final String key, title;
  final int open;
  final Map<String, int> byClass, bySeverity;
  const OverviewSection(this.key, this.title, this.open, this.byClass, this.bySeverity);
  factory OverviewSection.fromJson(Map<String, dynamic> j) => OverviewSection(
        j['key'] as String,
        j['title'] as String,
        _i(j['open']),
        {for (final e in _map(j['by_class']).entries) e.key: _i(e.value)},
        {for (final e in _map(j['by_severity']).entries) e.key: _i(e.value)},
      );
}

class ComplianceOverview {
  final List<OverviewSection> sections;
  final Map<String, dynamic> financialHealth, legalLibrary, statutory;
  final int pendingApprovals;
  final DateTime? lastScanAt;
  const ComplianceOverview(this.sections, this.financialHealth, this.legalLibrary, this.statutory, this.pendingApprovals, this.lastScanAt);
  factory ComplianceOverview.fromJson(Map<String, dynamic> j) => ComplianceOverview(
        [for (final s in _list(j['sections'])) OverviewSection.fromJson(s)],
        _map(j['financial_health']),
        _map(j['legal_library']),
        _map(j['statutory']),
        _i(j['pending_approvals']),
        _dt(j['last_scan_at']),
      );
  OverviewSection? section(String key) => sections.where((s) => s.key == key).firstOrNull;
}

class LegalDocument {
  final Map<String, dynamic> raw;
  const LegalDocument(this.raw);
  String get id => raw['id'] as String;
  String get title => raw['title'] as String? ?? '';
  String get type => raw['document_type'] as String? ?? 'OTHER';
  String get status => raw['status'] as String? ?? 'UNVERIFIED';
  String get verification => raw['verification_status'] as String? ?? 'PENDING_VERIFICATION';
  bool get operative => raw['operative'] as bool? ?? false;
  bool get societySpecific => raw['society_specific'] as bool? ?? true;
  String get language => raw['language'] as String? ?? 'unknown';
  String get quality => raw['extraction_quality'] as String? ?? 'NONE';
  List<String> get issues => [for (final x in (raw['extraction_issues'] as List? ?? const [])) '$x'];
  int? get pages => raw['page_count'] as int?;
  String get sha256 => raw['sha256'] as String? ?? '';
}

class LegalRule {
  final Map<String, dynamic> raw;
  const LegalRule(this.raw);
  String get id => raw['id'] as String;
  String get code => raw['rule_code'] as String? ?? '';
  int get version => _i(raw['version']);
  String get title => raw['title'] as String? ?? '';
  String get category => raw['rule_category'] as String? ?? '';
  String get legalStatus => raw['legal_status'] as String? ?? '';
  String get verification => raw['verification_status'] as String? ?? '';
  String? get levelName => raw['source_level_name'] as String?;
  String? get note => raw['verification_note'] as String?;
  String? get effectiveFrom => raw['effective_from'] as String?;
  String? get effectiveUntil => raw['effective_until'] as String?;
  bool get societySpecific => raw['society_specific'] as bool? ?? false;
  String get reference => LegalSource({
        'act_section': raw['act_section'],
        'rule_number': raw['rule_number'],
        'bye_law_number': raw['bye_law_number'],
        'clause': raw['clause_reference'],
        'page': raw['page_number'],
      }).reference;
}

class LegalReview {
  final Map<String, dynamic> raw;
  const LegalReview(this.raw);
  String get id => raw['id'] as String;
  String get title => raw['title'] as String? ?? '';
  String get type => raw['review_type'] as String? ?? '';
  String get description => raw['description'] as String? ?? '';
  String get status => raw['status'] as String? ?? 'OPEN';
  bool get blocking => raw['blocking'] as bool? ?? false;
  bool get societySpecific => raw['society_specific'] as bool? ?? false;
  bool get isOpen => status == 'OPEN' || status == 'IN_REVIEW';
}

class SocietyResolution {
  final Map<String, dynamic> raw;
  const SocietyResolution(this.raw);
  String get id => raw['id'] as String;
  String get number => raw['resolution_number'] as String? ?? '';
  String get meetingType => raw['meeting_type'] as String? ?? '';
  DateTime? get meetingDate => _dt(raw['meeting_date']);
  String get authority => raw['approval_authority'] as String? ?? '';
  String get category => raw['category'] as String? ?? 'other';
  String get purpose => raw['purpose'] as String? ?? '';
  String? get amount => raw['approved_amount'] as String?;
  String get status => raw['status'] as String? ?? 'RECORDED';
  List<String> get problems => [for (final x in (raw['problems'] as List? ?? const [])) '$x'];
}

class ComplianceItem {
  final Map<String, dynamic> raw;
  const ComplianceItem(this.raw);
  String get id => raw['id'] as String;
  String get code => raw['code'] as String? ?? '';
  String get title => raw['title'] as String? ?? '';
  String get period => raw['financial_period'] as String? ?? '';
  DateTime? get due => _dt(raw['due_date']);
  String? get dueBasis => raw['due_date_basis'] as String?;
  String get applicability => raw['applicability'] as String? ?? '';
  String? get applicabilityReason => raw['applicability_reason'] as String?;
  String? get legalSource => raw['legal_source'] as String?;
  String? get role => raw['responsible_role'] as String?;
  String get status => raw['completion_status'] as String? ?? 'PENDING';
  bool get overdue => raw['overdue'] as bool? ?? false;
  bool get needsProfessional => raw['professional_verification_required'] as bool? ?? false;
}

class ArrearsRow {
  final Map<String, dynamic> raw;
  const ArrearsRow(this.raw);
  String get flatId => raw['flat_id'] as String;
  String get flat => raw['flat'] as String? ?? '';
  double get outstanding => double.tryParse('${raw['outstanding']}') ?? 0;
  int get overdueDays => _i(raw['overdue_days']);
  bool get defaulter => raw['defaulter'] as bool? ?? false;
  Map<String, dynamic> get ageing => _map(raw['ageing']);
}

class ArrearsReport {
  final List<ArrearsRow> flats;
  final double total;
  final int defaulterAfterMonths;
  final Map<String, dynamic> ageingTotals;
  final LegalSource? rule;
  final String note;
  const ArrearsReport(this.flats, this.total, this.defaulterAfterMonths, this.ageingTotals, this.rule, this.note);
  factory ArrearsReport.fromJson(Map<String, dynamic> j) => ArrearsReport(
        [for (final r in _list(j['flats'])) ArrearsRow(r)],
        double.tryParse('${j['total_outstanding']}') ?? 0,
        _i(j['defaulter_after_months']),
        _map(j['ageing_totals']),
        LegalSource.from(j['rule']),
        j['note'] as String? ?? '',
      );
}

class AssistantAnswer {
  final String? intent;
  final String answer;
  final List<LegalSource> sources;
  final bool verifiedLaw;
  final String? uncertainty;
  final String? disclaimer;
  final Map<String, dynamic> data;
  const AssistantAnswer(this.intent, this.answer, this.sources, this.verifiedLaw, this.uncertainty, this.disclaimer, this.data);
  factory AssistantAnswer.fromJson(Map<String, dynamic> j) => AssistantAnswer(
        j['intent'] as String?,
        j['answer'] as String? ?? '',
        [for (final s in _list(j['sources'])) LegalSource(s)],
        j['verified_law'] as bool? ?? false,
        j['uncertainty'] as String?,
        j['disclaimer'] as String?,
        _map(j['data']),
      );
  List<String> get suggestions => [for (final x in (data['suggestions'] as List? ?? const [])) '$x'];
}

class LegalApi {
  final Dio _dio;
  LegalApi({Dio? dio}) : _dio = dio ?? ApiClient.instance;
  static const _base = '/accounts-agent';

  Map<String, dynamic> _m(Response r) => (r.data as Map).cast<String, dynamic>();
  List<Map<String, dynamic>> _l(Response r) => _list(r.data);

  Future<ComplianceOverview> overview() async => ComplianceOverview.fromJson(_m(await _dio.get('$_base/compliance/overview')));
  Future<Map<String, dynamic>> scan() async => _m(await _dio.post('$_base/compliance/scan'));

  Future<Map<String, dynamic>> profile() async => _m(await _dio.get('$_base/legal/profile'));

  Future<List<LegalDocument>> documents({String scope = 'all'}) async =>
      [for (final d in _l(await _dio.get('$_base/legal/documents', queryParameters: {'scope': scope}))) LegalDocument(d)];

  Future<LegalDocument> upload({required List<int> bytes, required String fileName, required String type, required String title,
      String? requestedStatus, String? referenceNumber}) async {
    final form = FormData.fromMap({
      'file': MultipartFile.fromBytes(bytes, filename: fileName),
      'document_type': type,
      'title': title,
      if (requestedStatus != null) 'requested_status': requestedStatus,
      if (referenceNumber != null && referenceNumber.isNotEmpty) 'reference_number': referenceNumber,
    });
    return LegalDocument(_m(await _dio.post('$_base/legal/documents', data: form)));
  }

  Future<LegalDocument> verifyDocument(String id, {required String status, required String verification, required String note,
      DateTime? approvalDate, String? overrideDraftWarning}) async =>
      LegalDocument(_m(await _dio.post('$_base/legal/documents/$id/verify', data: {
        'status': status,
        'verification_status': verification,
        'note': note,
        if (approvalDate != null) 'approval_date': _apiDate(approvalDate),
        if (overrideDraftWarning != null && overrideDraftWarning.isNotEmpty) 'override_draft_warning': overrideDraftWarning,
      })));

  Future<List<LegalRule>> rules({bool history = false}) async =>
      [for (final r in _list(_m(await _dio.get('$_base/legal/rules', queryParameters: {'include_history': history}))['items'])) LegalRule(r)];

  Future<List<LegalReview>> reviews() async => [for (final r in _l(await _dio.get('$_base/legal/reviews'))) LegalReview(r)];

  Future<LegalReview> decideReview(String id, String status, String note) async =>
      LegalReview(_m(await _dio.post('$_base/legal/reviews/$id/decide', data: {'status': status, 'note': note})));

  Future<List<SocietyResolution>> resolutions() async => [for (final r in _l(await _dio.get('$_base/resolutions'))) SocietyResolution(r)];

  Future<SocietyResolution> createResolution(Map<String, dynamic> data) async =>
      SocietyResolution(_m(await _dio.post('$_base/resolutions', data: data)));

  Future<SocietyResolution> verifyResolution(String id) async =>
      SocietyResolution(_m(await _dio.post('$_base/resolutions/$id/verify', data: const {})));

  Future<int> importResolutions() async => _i(_m(await _dio.post('$_base/resolutions/import-governance'))['imported']);

  Future<List<ComplianceItem>> calendar() async => [for (final r in _l(await _dio.get('$_base/compliance/calendar'))) ComplianceItem(r)];

  Future<ComplianceItem> updateItem(String id, Map<String, dynamic> data) async =>
      ComplianceItem(_m(await _dio.put('$_base/compliance/calendar/$id', data: data)));

  Future<ArrearsReport> arrears() async => ArrearsReport.fromJson(_m(await _dio.get('$_base/recovery/arrears')));
  Future<Map<String, dynamic>> checklist(String flatId) async => _m(await _dio.get('$_base/recovery/checklist/$flatId'));

  Future<AssistantAnswer> ask(String q) async => AssistantAnswer.fromJson(_m(await _dio.post('$_base/assistant/ask', data: {'question': q.trim()})));
}
