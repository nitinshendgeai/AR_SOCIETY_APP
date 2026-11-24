import 'package:dio/dio.dart';
import 'package:ar_society_app/core/api/api_client.dart';

/// The Accounts Agent API. The society is always taken from the signed-in user by the server; this client never
/// sends a society id for a society-scoped user.
double _d(Object? v) => double.tryParse('${v ?? 0}') ?? 0;
int _i(Object? v) => (v is num) ? v.toInt() : int.tryParse('${v ?? 0}') ?? 0;
String _apiDate(DateTime d) => '${d.year.toString().padLeft(4, '0')}-${d.month.toString().padLeft(2, '0')}-${d.day.toString().padLeft(2, '0')}';

const severities = ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'INFORMATIONAL'];
const findingStatuses = ['NEW', 'UNDER_REVIEW', 'APPROVED', 'REJECTED', 'RESOLVED', 'IGNORED'];

/// Words for the four kinds of claim, so a statistic is never presented as a confirmed error.
String findingClassLabel(String c) => switch (c) {
      'confirmed_validation_failure' => 'Confirmed validation failure',
      'strongly_suspected_anomaly' => 'Strongly suspected anomaly',
      'statistical_deviation' => 'Statistical deviation',
      _ => 'Informational observation',
    };

class AgentStatus {
  final String state; // operational | delayed | degraded | disabled
  final bool monitoringEnabled;
  final DateTime? lastMonitoredAt;
  final int pendingEvents;
  final int failedEvents;
  final String? lastError;
  final DateTime? lastLearningAt;
  final String learningConfidence;
  final int recentFailedEvents;
  final int acknowledgedFailedEvents;
  const AgentStatus({
    required this.state,
    required this.monitoringEnabled,
    this.lastMonitoredAt,
    this.pendingEvents = 0,
    this.failedEvents = 0,
    this.lastError,
    this.lastLearningAt,
    this.learningConfidence = 'none',
    this.recentFailedEvents = 0,
    this.acknowledgedFailedEvents = 0,
  });
  factory AgentStatus.fromJson(Map<String, dynamic> j) => AgentStatus(
        state: j['state'] as String? ?? 'operational',
        monitoringEnabled: j['monitoring_enabled'] as bool? ?? true,
        lastMonitoredAt: j['last_monitored_at'] == null ? null : DateTime.parse(j['last_monitored_at'] as String),
        pendingEvents: _i(j['pending_events']),
        failedEvents: _i(j['failed_events']),
        lastError: j['last_error'] as String?,
        lastLearningAt: j['last_learning_at'] == null ? null : DateTime.parse(j['last_learning_at'] as String),
        learningConfidence: j['learning_confidence'] as String? ?? 'none',
        recentFailedEvents: _i(j['recent_failed_events']),
        acknowledgedFailedEvents: _i(j['acknowledged_failed_events']),
      );
}

class LearningRun {
  final String id;
  final String status;
  final DateTime windowStart;
  final DateTime windowEnd;
  final DateTime? finishedAt;
  final int voucherCount;
  final int monthsCovered;
  final int daysCovered;
  final int patternCount;
  final double confidenceScore;
  final String confidenceLabel;
  final String? note;
  const LearningRun({
    required this.id,
    required this.status,
    required this.windowStart,
    required this.windowEnd,
    this.finishedAt,
    this.voucherCount = 0,
    this.monthsCovered = 0,
    this.daysCovered = 0,
    this.patternCount = 0,
    this.confidenceScore = 0,
    this.confidenceLabel = 'none',
    this.note,
  });
  factory LearningRun.fromJson(Map<String, dynamic> j) => LearningRun(
        id: j['id'] as String,
        status: j['status'] as String? ?? '',
        windowStart: DateTime.parse(j['window_start'] as String),
        windowEnd: DateTime.parse(j['window_end'] as String),
        finishedAt: j['finished_at'] == null ? null : DateTime.parse(j['finished_at'] as String),
        voucherCount: _i(j['voucher_count']),
        monthsCovered: _i(j['months_covered']),
        daysCovered: _i(j['days_covered']),
        patternCount: _i(j['pattern_count']),
        confidenceScore: _d(j['confidence_score']),
        confidenceLabel: j['confidence_label'] as String? ?? 'none',
        note: (j['summary'] as Map<String, dynamic>?)?['note'] as String?,
      );
}

class AgentDashboard {
  final AgentStatus status;
  final int transactionsAnalysed;
  final Map<String, int> open; // severity → open findings
  final int resolved;
  final int pendingApprovals;
  final int windowMonths;
  final LearningRun? lastRun;
  const AgentDashboard({
    required this.status,
    required this.transactionsAnalysed,
    required this.open,
    required this.resolved,
    required this.pendingApprovals,
    required this.windowMonths,
    this.lastRun,
  });
  factory AgentDashboard.fromJson(Map<String, dynamic> j) {
    final learning = j['learning'] as Map<String, dynamic>? ?? const {};
    final run = learning['last_run'];
    return AgentDashboard(
      status: AgentStatus.fromJson(j['status'] as Map<String, dynamic>),
      transactionsAnalysed: _i(j['transactions_analysed']),
      open: {for (final e in (j['findings_open'] as Map<String, dynamic>? ?? const {}).entries) e.key: _i(e.value)},
      resolved: _i(j['resolved_findings']),
      pendingApprovals: _i(j['pending_approvals']),
      windowMonths: _i(learning['window_months']),
      lastRun: run == null ? null : LearningRun.fromJson(run as Map<String, dynamic>),
    );
  }
}

class AgentFinding {
  final String id;
  final String? voucherId;
  final String? transactionRef;
  final DateTime? voucherDate;
  final String category;
  final String findingClass;
  final String severity;
  final double confidence;
  final String ruleCode;
  final String title;
  final String status;
  final String explanation;
  final String? recommendedAction;
  final String? learningConfidence;
  // detail only
  final String? expected;
  final String? actual;
  final Map<String, dynamic> evidence;
  final String? resolutionNote;
  final AgentVoucher? voucher;
  final List<AgentProposal> proposals;
  final String? aiExplanation;
  // Unified classification and the legal engine (Engine B)
  final String classification;
  final String engine;
  final String? complianceCategory;
  final String? legalRuleCode;
  final Map<String, dynamic>? legalSource;
  final String? flatId;
  final String? vendorId;
  final String? humanReviewStatus;
  /// The voucher's approval status (list rows): a finding on an unapproved voucher is marked as such (D-19).
  final String? voucherApprovalStatus;
  /// The voucher as it stood when the finding was raised, and whether it has changed since (D-17).
  final AgentVoucher? voucherAtDetection;
  final bool voucherChangedSinceDetection;
  /// Evidence with ids replaced by names (D-18). Empty when the server sent none.
  final List<MapEntry<String, String>> evidenceDisplay;

  const AgentFinding({
    required this.id,
    this.voucherId,
    this.transactionRef,
    this.voucherDate,
    required this.category,
    required this.findingClass,
    required this.severity,
    required this.confidence,
    required this.ruleCode,
    required this.title,
    required this.status,
    required this.explanation,
    this.recommendedAction,
    this.learningConfidence,
    this.expected,
    this.actual,
    this.evidence = const {},
    this.resolutionNote,
    this.voucher,
    this.proposals = const [],
    this.aiExplanation,
    this.classification = 'ADVISORY_OBSERVATION',
    this.engine = 'accounting',
    this.complianceCategory,
    this.legalRuleCode,
    this.legalSource,
    this.flatId,
    this.vendorId,
    this.humanReviewStatus,
    this.voucherApprovalStatus,
    this.voucherAtDetection,
    this.voucherChangedSinceDetection = false,
    this.evidenceDisplay = const [],
  });

  factory AgentFinding.fromJson(Map<String, dynamic> j) => AgentFinding(
        id: j['id'] as String,
        voucherId: j['voucher_id'] as String?,
        transactionRef: j['transaction_ref'] as String?,
        voucherDate: j['voucher_date'] == null ? null : DateTime.parse(j['voucher_date'] as String),
        category: j['category'] as String? ?? '',
        findingClass: j['finding_class'] as String? ?? '',
        severity: j['severity'] as String? ?? 'LOW',
        confidence: _d(j['confidence']),
        ruleCode: j['rule_code'] as String? ?? '',
        title: j['title'] as String? ?? '',
        status: j['status'] as String? ?? 'NEW',
        explanation: j['explanation'] as String? ?? '',
        recommendedAction: j['recommended_action'] as String?,
        learningConfidence: j['learning_confidence'] as String?,
        expected: j['expected_behaviour'] as String?,
        actual: j['actual_behaviour'] as String?,
        evidence: (j['evidence'] as Map?)?.cast<String, dynamic>() ?? const {},
        resolutionNote: j['resolution_note'] as String?,
        voucher: j['voucher'] == null ? null : AgentVoucher.fromJson(j['voucher'] as Map<String, dynamic>),
        proposals: [for (final p in (j['proposals'] as List? ?? const [])) AgentProposal.fromJson(p as Map<String, dynamic>)],
        aiExplanation: j['ai_explanation'] as String?,
        classification: j['classification'] as String? ?? 'ADVISORY_OBSERVATION',
        engine: j['engine'] as String? ?? 'accounting',
        complianceCategory: j['compliance_category'] as String?,
        legalRuleCode: j['legal_rule_code'] as String?,
        legalSource: (j['legal_source'] as Map?)?.cast<String, dynamic>(),
        flatId: j['flat_id'] as String?,
        vendorId: j['vendor_id'] as String?,
        humanReviewStatus: j['human_review_status'] as String?,
        voucherApprovalStatus: j['voucher_approval_status'] as String? ?? (j['voucher'] as Map?)?['approval_status'] as String?,
        voucherAtDetection: j['voucher_at_detection'] == null
            ? null
            : AgentVoucher.fromSnapshot(j['voucher_at_detection'] as Map<String, dynamic>),
        voucherChangedSinceDetection: j['voucher_changed_since_detection'] as bool? ?? false,
        evidenceDisplay: [
          for (final e in (j['evidence_display'] as List? ?? const []))
            MapEntry('${(e as Map)['label']}', '${e['value']}'),
        ],
      );

  bool get isOpen => status == 'NEW' || status == 'UNDER_REVIEW' || status == 'APPROVED';

  /// The voucher behind this finding has not been approved yet (it may still change or be rejected).
  bool get onPendingVoucher => voucherApprovalStatus == 'pending';
}

/// One entry of a finding's audit trail (who did what, when) — GET /findings/{id}/history.
class FindingHistoryEntry {
  final DateTime at;
  final String actor; // "Accounts Agent" | "User"
  final String action;
  final Map<String, dynamic> details;
  const FindingHistoryEntry(this.at, this.actor, this.action, this.details);
  factory FindingHistoryEntry.fromJson(Map<String, dynamic> j) => FindingHistoryEntry(
        DateTime.parse(j['created_at'] as String),
        j['actor'] as String? ?? 'User',
        j['action'] as String? ?? '',
        (j['details'] as Map?)?.cast<String, dynamic>() ?? const {},
      );
}

/// Plain words for audit-trail actions.
String historyActionLabel(String a) => switch (a) {
      'finding_created' => 'Finding raised',
      'finding_auto_resolved' => 'Closed by the agent after re-checking',
      'finding_reopened' => 'Reopened — detected again',
      'finding_reviewed' => 'Reviewed',
      'proposal_created' => 'Correction proposed',
      'proposal_approved' => 'Correction approved and applied',
      'proposal_verified' => 'Agent re-checked the corrected voucher',
      'proposal_rejected' => 'Correction rejected',
      'proposal_stale' => 'Correction not applied — the voucher had changed',
      'proposal_failed' => 'Correction failed — nothing was changed',
      'proposal_acknowledged' => 'Recommendation acknowledged',
      'proposal_self_approval_refused' => 'Approval refused — the proposer cannot approve their own correction',
      _ => a.replaceAll('_', ' '),
    };

/// A monitoring job that failed repeatedly and was parked (D-10).
class DeadEvent {
  final String id;
  final String eventType;
  final String? lastError;
  final DateTime? deadAt;
  final int requeueCount;
  final int requeuesLeft;
  final bool acknowledged;
  final String? acknowledgeNote;
  const DeadEvent(this.id, this.eventType, this.lastError, this.deadAt, this.requeueCount, this.requeuesLeft,
      this.acknowledged, this.acknowledgeNote);
  factory DeadEvent.fromJson(Map<String, dynamic> j) => DeadEvent(
        j['id'] as String,
        j['event_type'] as String? ?? '',
        j['last_error'] as String?,
        j['dead_at'] == null ? null : DateTime.parse(j['dead_at'] as String),
        _i(j['requeue_count']),
        _i(j['requeues_left']),
        j['acknowledged'] as bool? ?? false,
        j['acknowledge_note'] as String?,
      );
}

class AgentVoucherLine {
  final int lineNo;
  final String account;
  final double debit;
  final double credit;
  final String? vendor;
  const AgentVoucherLine(this.lineNo, this.account, this.debit, this.credit, this.vendor);
  factory AgentVoucherLine.fromJson(Map<String, dynamic> j) =>
      AgentVoucherLine(_i(j['line_no']), j['account'] as String? ?? '', _d(j['debit']), _d(j['credit']), j['vendor'] as String?);
}

class AgentVoucher {
  final String id;
  final String number;
  final String type;
  final DateTime date;
  final double amount;
  final String? narration;
  final String? reference;
  final String approvalStatus;
  final bool cancelled;
  final String? sourceType;
  final List<AgentVoucherLine> lines;
  const AgentVoucher({
    required this.id,
    required this.number,
    required this.type,
    required this.date,
    required this.amount,
    this.narration,
    this.reference,
    required this.approvalStatus,
    required this.cancelled,
    this.sourceType,
    required this.lines,
  });
  factory AgentVoucher.fromJson(Map<String, dynamic> j) => AgentVoucher(
        id: j['id'] as String,
        number: j['voucher_number'] as String? ?? '',
        type: j['voucher_type'] as String? ?? '',
        date: DateTime.parse(j['voucher_date'] as String),
        amount: _d(j['amount']),
        narration: j['narration'] as String?,
        reference: j['reference'] as String?,
        approvalStatus: j['approval_status'] as String? ?? '',
        cancelled: j['is_cancelled'] as bool? ?? false,
        sourceType: j['source_type'] as String?,
        lines: [for (final e in (j['entries'] as List? ?? const [])) AgentVoucherLine.fromJson(e as Map<String, dynamic>)],
      );

  /// The snapshot the agent kept when it raised a finding (no id or type: it is a record, not a live voucher).
  factory AgentVoucher.fromSnapshot(Map<String, dynamic> j) => AgentVoucher(
        id: '',
        number: j['voucher_number'] as String? ?? '',
        type: '',
        date: DateTime.parse(j['voucher_date'] as String),
        amount: _d(j['amount']),
        narration: j['narration'] as String?,
        reference: j['reference'] as String?,
        approvalStatus: j['approval_status'] as String? ?? '',
        cancelled: j['is_cancelled'] as bool? ?? false,
        lines: [
          for (final (i, e) in (j['entries'] as List? ?? const []).indexed)
            AgentVoucherLine(i + 1, '${(e as Map)['account'] ?? ''}', _d(e['debit']), _d(e['credit']), null),
        ],
      );
}

class ProposalLine {
  final String account;
  final double debit;
  final double credit;
  const ProposalLine(this.account, this.debit, this.credit);
}

class ProposalImpact {
  final String account;
  final double debitBefore;
  final double creditBefore;
  final double debitAfter;
  final double creditAfter;
  final String net;
  const ProposalImpact(this.account, this.debitBefore, this.creditBefore, this.debitAfter, this.creditAfter, this.net);
}

class AgentProposal {
  final String id;
  final String findingId;
  final String actionType; // edit_voucher | cancel_voucher | source_review
  final String status; // PENDING | EXECUTED | ACKNOWLEDGED | REJECTED | STALE | FAILED
  final String title;
  final String explanation;
  final bool executable;
  final List<ProposalLine> before;
  final List<ProposalLine>? after;
  final bool cancelsVoucher;
  final List<ProposalImpact> impact;
  final String? decisionNote;
  final String? verificationNote;
  final String? error;
  /// Who proposed it, and whether a different person must approve it (maker–checker, D-09).
  final String? createdBy;
  final bool requiresOtherApprover;

  const AgentProposal({
    required this.id,
    required this.findingId,
    required this.actionType,
    required this.status,
    required this.title,
    required this.explanation,
    required this.executable,
    required this.before,
    this.after,
    this.cancelsVoucher = false,
    this.impact = const [],
    this.decisionNote,
    this.verificationNote,
    this.error,
    this.createdBy,
    this.requiresOtherApprover = false,
  });

  static List<ProposalLine> _lines(Object? v) => [
        for (final l in (v as List? ?? const []))
          ProposalLine((l as Map)['account'] as String? ?? '', _d(l['debit']), _d(l['credit'])),
      ];

  factory AgentProposal.fromJson(Map<String, dynamic> j) {
    final before = (j['before'] as Map?)?.cast<String, dynamic>() ?? const {};
    final after = (j['after'] as Map?)?.cast<String, dynamic>();
    final result = (j['result'] as Map?)?.cast<String, dynamic>();
    return AgentProposal(
      id: j['id'] as String,
      findingId: j['finding_id'] as String? ?? '',
      actionType: j['action_type'] as String? ?? '',
      status: j['status'] as String? ?? 'PENDING',
      title: j['title'] as String? ?? '',
      explanation: j['explanation'] as String? ?? '',
      executable: j['executable'] as bool? ?? true,
      before: _lines(before['lines']),
      after: after == null ? null : _lines(after['lines']),
      cancelsVoucher: after?['is_cancelled'] == true,
      impact: [
        for (final i in (j['impact'] as List? ?? const []))
          ProposalImpact((i as Map)['account'] as String? ?? '', _d(i['debit_before']), _d(i['credit_before']),
              _d(i['debit_after']), _d(i['credit_after']), i['net_effect'] as String? ?? ''),
      ],
      decisionNote: j['decision_note'] as String?,
      verificationNote: ((result?['verification']) as Map?)?['note'] as String?,
      error: result?['error'] as String?,
      createdBy: j['created_by'] as String?,
      requiresOtherApprover: j['requires_other_approver'] as bool? ?? false,
    );
  }

  /// Maker–checker: the person who proposed a correction that changes the books cannot approve it.
  bool proposedBy(String? userId) => userId != null && createdBy == userId;
}

class AgentSettings {
  final bool monitoringEnabled;
  final String notifyMinSeverity;
  final double zThreshold;
  final double recurringTolerancePct;
  final int duplicateWindowDays;
  final int learningWindowMonths;
  /// "anthropic" when the society switched on Claude for bye-law answers and entry reading; "disabled" otherwise.
  final String aiProvider;
  /// The deployment has an Anthropic API key (without it the switch has no effect).
  final bool aiConfigured;
  final bool aiEnabled;
  const AgentSettings({
    required this.monitoringEnabled,
    required this.notifyMinSeverity,
    required this.zThreshold,
    required this.recurringTolerancePct,
    required this.duplicateWindowDays,
    required this.learningWindowMonths,
    this.aiProvider = 'disabled',
    this.aiConfigured = false,
    this.aiEnabled = false,
  });
  factory AgentSettings.fromJson(Map<String, dynamic> j) => AgentSettings(
        monitoringEnabled: j['monitoring_enabled'] as bool? ?? true,
        notifyMinSeverity: j['notify_min_severity'] as String? ?? 'HIGH',
        zThreshold: _d(j['z_threshold']),
        recurringTolerancePct: _d(j['recurring_tolerance_pct']),
        duplicateWindowDays: _i(j['duplicate_window_days']),
        learningWindowMonths: _i(j['learning_window_months']),
        aiProvider: j['llm_provider'] as String? ?? 'disabled',
        aiConfigured: j['ai_configured'] as bool? ?? false,
        aiEnabled: j['ai_enabled'] as bool? ?? false,
      );
}

class LearningStatus {
  final DateTime windowStart;
  final DateTime windowEnd;
  final LearningRun? lastRun;
  final bool limited;
  final String message;
  const LearningStatus({required this.windowStart, required this.windowEnd, this.lastRun, required this.limited, required this.message});
  factory LearningStatus.fromJson(Map<String, dynamic> j) => LearningStatus(
        windowStart: DateTime.parse(j['window_start'] as String),
        windowEnd: DateTime.parse(j['window_end'] as String),
        lastRun: j['last_run'] == null ? null : LearningRun.fromJson(j['last_run'] as Map<String, dynamic>),
        limited: j['limited'] as bool? ?? true,
        message: j['message'] as String? ?? '',
      );
}

class FindingsPage {
  final List<AgentFinding> items;
  final int total;
  const FindingsPage(this.items, this.total);
}

/// What the findings list is filtered by. Value-equal so it can key a provider.
class FindingsFilter {
  final String? severity;
  final String? category;
  final String? status;
  final DateTime? from;
  final DateTime? to;
  final String query;
  final int page;
  final String? section;
  const FindingsFilter({this.severity, this.category, this.status, this.from, this.to, this.query = '', this.page = 1, this.section});

  FindingsFilter copyWith({String? severity, String? category, String? status, DateTime? from, DateTime? to, String? query, int? page, bool clearSeverity = false, bool clearCategory = false, bool clearStatus = false, bool clearDates = false}) =>
      FindingsFilter(
        severity: clearSeverity ? null : (severity ?? this.severity),
        category: clearCategory ? null : (category ?? this.category),
        status: clearStatus ? null : (status ?? this.status),
        from: clearDates ? null : (from ?? this.from),
        to: clearDates ? null : (to ?? this.to),
        query: query ?? this.query,
        page: page ?? this.page,
        section: section,
      );

  @override
  bool operator ==(Object other) =>
      other is FindingsFilter && other.severity == severity && other.category == category && other.status == status && other.from == from && other.to == to && other.query == query && other.page == page && other.section == section;
  @override
  int get hashCode => Object.hash(severity, category, status, from, to, query, page, section);
}

class AccountsAgentApi {
  final Dio _dio;
  AccountsAgentApi({Dio? dio}) : _dio = dio ?? ApiClient.instance;

  static const _base = '/accounts-agent';

  Map<String, dynamic> _m(Response r) => r.data as Map<String, dynamic>;

  Future<AgentDashboard> dashboard() async => AgentDashboard.fromJson(_m(await _dio.get('$_base/dashboard')));
  Future<AgentSettings> settings() async => AgentSettings.fromJson(_m(await _dio.get('$_base/settings')));

  Future<AgentSettings> updateSettings({double? zThreshold, double? recurringTolerancePct, int? duplicateWindowDays, String? notifyMinSeverity, String? aiProvider}) async =>
      AgentSettings.fromJson(_m(await _dio.put('$_base/settings', data: {
        if (aiProvider != null) 'llm_provider': aiProvider,
        if (zThreshold != null) 'z_threshold': zThreshold,
        if (recurringTolerancePct != null) 'recurring_tolerance_pct': recurringTolerancePct,
        if (duplicateWindowDays != null) 'duplicate_window_days': duplicateWindowDays,
        if (notifyMinSeverity != null) 'notify_min_severity': notifyMinSeverity,
      })));

  Future<AgentStatus> setMonitoring(bool enabled) async =>
      AgentStatus.fromJson(_m(await _dio.post('$_base/monitoring', data: {'enabled': enabled})));

  Future<LearningStatus> learningStatus() async => LearningStatus.fromJson(_m(await _dio.get('$_base/learning/status')));
  Future<LearningRun> runLearning() async => LearningRun.fromJson(_m(await _dio.post('$_base/learning/run')));

  Future<List<LearningRun>> learningHistory() async =>
      [for (final r in (_m(await _dio.get('$_base/learning/history', queryParameters: {'page_size': 20}))['items'] as List)) LearningRun.fromJson(r as Map<String, dynamic>)];

  Future<FindingsPage> findings(FindingsFilter f, {int pageSize = 25}) async {
    final r = _m(await _dio.get('$_base/findings', queryParameters: {
      if (f.severity != null) 'severity': f.severity,
      if (f.category != null) 'category': f.category,
      if (f.status != null) 'status': f.status,
      if (f.from != null) 'date_from': _apiDate(f.from!),
      if (f.to != null) 'date_to': _apiDate(f.to!),
      if (f.query.trim().isNotEmpty) 'q': f.query.trim(),
      if (f.section != null) 'section': f.section,
      'page': f.page,
      'page_size': pageSize,
    }));
    return FindingsPage([for (final x in (r['items'] as List)) AgentFinding.fromJson(x as Map<String, dynamic>)], _i(r['total']));
  }

  Future<AgentFinding> finding(String id) async => AgentFinding.fromJson(_m(await _dio.get('$_base/findings/$id')));

  Future<AgentFinding> review(String id, String status, {String? note}) async =>
      AgentFinding.fromJson(_m(await _dio.post('$_base/findings/$id/review', data: {'status': status, if (note != null && note.isNotEmpty) 'note': note})));

  Future<AgentProposal> propose(String findingId) async => AgentProposal.fromJson(_m(await _dio.post('$_base/findings/$findingId/proposals')));
  Future<AgentProposal> proposal(String id) async => AgentProposal.fromJson(_m(await _dio.get('$_base/proposals/$id')));

  Future<List<AgentProposal>> pendingProposals() async =>
      [for (final p in (_m(await _dio.get('$_base/proposals', queryParameters: {'status': 'PENDING', 'page_size': 50}))['items'] as List)) AgentProposal.fromJson(p as Map<String, dynamic>)];

  /// Approval always sends `confirm: true`; the server refuses an approval without it.
  Future<AgentProposal> approve(String id, {String? note}) async =>
      AgentProposal.fromJson(_m(await _dio.post('$_base/proposals/$id/approve', data: {'confirm': true, if (note != null && note.isNotEmpty) 'note': note})));

  /// The finding's audit trail: raised, reviewed, proposals and their decisions (D-11).
  Future<List<FindingHistoryEntry>> findingHistory(String id) async {
    final r = await _dio.get('$_base/findings/$id/history');
    return [for (final x in (r.data as List)) FindingHistoryEntry.fromJson(x as Map<String, dynamic>)];
  }

  /// Parked monitoring jobs, and the two recovery actions (D-10). Both are audited by the server.
  Future<List<DeadEvent>> deadEvents() async =>
      [for (final e in (_m(await _dio.get('$_base/events/dead'))['items'] as List)) DeadEvent.fromJson(e as Map<String, dynamic>)];
  Future<DeadEvent> requeueEvent(String id) async => DeadEvent.fromJson(_m(await _dio.post('$_base/events/$id/requeue')));
  Future<DeadEvent> acknowledgeEvent(String id, String note) async =>
      DeadEvent.fromJson(_m(await _dio.post('$_base/events/$id/acknowledge', data: {'note': note})));

  Future<AgentProposal> reject(String id, String reason) async =>
      AgentProposal.fromJson(_m(await _dio.post('$_base/proposals/$id/reject', data: {'reason': reason})));
}
