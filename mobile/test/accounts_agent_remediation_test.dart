import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ar_society_app/features/accounts_agent/data/accounts_agent_api.dart';

// Regression tests for the Accounts Agent functional-audit items surfaced in the app (D-09, D-10, D-11, D-17, D-18, D-19).

Dio _server(List<RequestOptions> seen, Object reply) {
  final dio = Dio();
  dio.interceptors.add(InterceptorsWrapper(onRequest: (options, handler) {
    seen.add(options);
    handler.resolve(Response(requestOptions: options, statusCode: 200, data: reply));
  }));
  return dio;
}

Map<String, dynamic> _finding({Map<String, dynamic>? extra}) => {
      'id': 'f1', 'category': 'ledger_mapping', 'finding_class': 'strongly_suspected_anomaly', 'severity': 'MEDIUM',
      'confidence': 0.58, 'rule_code': 'S-MAP-01', 'title': 'Unusual ledger', 'status': 'NEW', 'explanation': 'x',
      ...?extra,
    };

void main() {
  test('D-17/D-18: the voucher as detected, the change flag and readable evidence are parsed', () {
    final f = AgentFinding.fromJson(_finding(extra: {
      'voucher_at_detection': {
        'voucher_number': 'PV/0026', 'voucher_date': '2026-11-18', 'amount': '12000.00', 'approval_status': 'pending',
        'is_cancelled': false,
        'entries': [
          {'account': 'Repairs — Plumbing', 'debit': '12000.00', 'credit': '0.00'},
          {'account': 'Bank Account', 'debit': '0.00', 'credit': '12000.00'},
        ],
      },
      'voucher_changed_since_detection': true,
      'evidence_display': [
        {'label': 'Usual ledger', 'value': 'Housekeeping & Cleaning'},
        {'label': 'Vendor', 'value': 'CleanPro Housekeeping'},
      ],
      'evidence': {'usual_ledger_id': '6cbf1bb4-9c10-4125-a9e0-47957806ad96'},
    }));
    expect(f.voucherChangedSinceDetection, isTrue);
    expect(f.voucherAtDetection!.number, 'PV/0026');
    expect(f.voucherAtDetection!.lines.first.account, 'Repairs — Plumbing');
    expect(f.voucherAtDetection!.lines.first.debit, 12000);
    expect(f.evidenceDisplay.map((e) => '${e.key}: ${e.value}'),
        ['Usual ledger: Housekeeping & Cleaning', 'Vendor: CleanPro Housekeeping']);
  });

  test('D-19: a finding on an unapproved voucher is recognised', () {
    expect(AgentFinding.fromJson(_finding(extra: {'voucher_approval_status': 'pending'})).onPendingVoucher, isTrue);
    expect(AgentFinding.fromJson(_finding(extra: {'voucher_approval_status': 'approved'})).onPendingVoucher, isFalse);
    expect(AgentFinding.fromJson(_finding()).onPendingVoucher, isFalse);
  });

  test('D-11: finding history is read from the history endpoint and labelled', () async {
    final seen = <RequestOptions>[];
    final rows = await AccountsAgentApi(dio: _server(seen, [
      {'created_at': '2026-11-20T10:00:00', 'actor': 'Accounts Agent', 'action': 'finding_created', 'details': {}},
      {'created_at': '2026-11-20T11:00:00', 'actor': 'User', 'action': 'proposal_self_approval_refused', 'details': {}},
    ])).findingHistory('f1');
    expect(seen.single.path, '/accounts-agent/findings/f1/history');
    expect(rows.map((r) => historyActionLabel(r.action)),
        ['Finding raised', 'Approval refused — the proposer cannot approve their own correction']);
  });

  test('D-09: the proposer of a correction is recognised (no approve button for them)', () {
    final p = AgentProposal.fromJson({
      'id': 'p1', 'finding_id': 'f1', 'action_type': 'cancel_voucher', 'status': 'PENDING', 'title': 't',
      'explanation': 'e', 'executable': true, 'before': {'lines': []}, 'created_by': 'u1',
      'requires_other_approver': true,
    });
    expect(p.requiresOtherApprover, isTrue);
    expect(p.proposedBy('u1'), isTrue);
    expect(p.proposedBy('u2'), isFalse);
    expect(p.proposedBy(null), isFalse);
  });

  test('D-10: dead-event recovery calls the audited endpoints', () async {
    final seen = <RequestOptions>[];
    final ev = {'id': 'e1', 'event_type': 'voucher.created', 'requeue_count': 1, 'requeues_left': 2, 'acknowledged': false};
    final api = AccountsAgentApi(dio: _server(seen, ev));
    final r = await api.requeueEvent('e1');
    await api.acknowledgeEvent('e1', 'voucher removed by migration');
    expect(r.requeuesLeft, 2);
    expect(seen.map((o) => '${o.method} ${o.path}'),
        ['POST /accounts-agent/events/e1/requeue', 'POST /accounts-agent/events/e1/acknowledge']);
    expect(seen.last.data, {'note': 'voucher removed by migration'});
    final listed = await AccountsAgentApi(dio: _server(seen, {'items': [ev]})).deadEvents();
    expect(listed.single.id, 'e1');
  });

  test('D-10: status separates recent and acknowledged failures', () {
    final s = AgentStatus.fromJson({'state': 'degraded', 'failed_events': 2, 'recent_failed_events': 1, 'acknowledged_failed_events': 3});
    expect([s.failedEvents, s.recentFailedEvents, s.acknowledgedFailedEvents], [2, 1, 3]);
  });
}
