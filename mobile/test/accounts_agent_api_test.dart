import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ar_society_app/features/accounts_agent/data/accounts_agent_api.dart';

/// A server that records each request and answers with [reply].
Dio _server(List<RequestOptions> seen, Object reply) {
  final dio = Dio();
  dio.interceptors.add(InterceptorsWrapper(onRequest: (options, handler) {
    seen.add(options);
    handler.resolve(Response(requestOptions: options, statusCode: 200, data: reply));
  }));
  return dio;
}

const _proposal = {
  'id': 'p1',
  'finding_id': 'f1',
  'action_type': 'cancel_voucher',
  'status': 'PENDING',
  'title': 'Cancel duplicate PV/2026-27/0002',
  'explanation': 'x',
  'executable': true,
  'before': {
    'lines': [
      {'account': 'Security Charges', 'debit': '25000.00', 'credit': '0.00'},
      {'account': 'Bank Account', 'debit': '0.00', 'credit': '25000.00'},
    ]
  },
  'after': {'is_cancelled': true, 'lines': []},
  'impact': [
    {'account': 'Bank Account', 'debit_before': '0', 'credit_before': '25000', 'debit_after': '0', 'credit_after': '0', 'net_effect': '25000.0 Dr'}
  ],
  'result': null,
};

void main() {
  test('approving always sends the explicit confirmation the server requires', () async {
    final seen = <RequestOptions>[];
    final api = AccountsAgentApi(dio: _server(seen, _proposal));
    await api.approve('p1', note: 'checked');
    expect(seen.single.path, '/accounts-agent/proposals/p1/approve');
    expect((seen.single.data as Map)['confirm'], true);
  });

  test('a proposal that cancels a voucher is read as such, with its ledger impact', () {
    final p = AgentProposal.fromJson(Map<String, dynamic>.from(_proposal));
    expect(p.cancelsVoucher, isTrue);
    expect(p.before.length, 2);
    expect(p.before.first.debit, 25000);
    expect(p.impact.single.account, 'Bank Account');
  });

  test('findings are requested page by page with the filters, and never with a society id', () async {
    final seen = <RequestOptions>[];
    final api = AccountsAgentApi(dio: _server(seen, {'items': [], 'total': 0, 'page': 2, 'page_size': 25}));
    await api.findings(const FindingsFilter(severity: 'HIGH', query: ' stationery ', page: 2));
    final q = seen.single.queryParameters;
    expect(q['severity'], 'HIGH');
    expect(q['q'], 'stationery');
    expect(q['page'], 2);
    expect(q.containsKey('society_id'), isFalse);
  });

  test('statistics are never labelled as confirmed errors', () {
    expect(findingClassLabel('statistical_deviation'), 'Statistical deviation');
    expect(findingClassLabel('confirmed_validation_failure'), 'Confirmed validation failure');
  });
}
