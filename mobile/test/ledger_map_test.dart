import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ar_society_app/features/accounts_agent/data/legal_api.dart';
import 'package:ar_society_app/features/accounts_agent/presentation/screens/ledger_map_screen.dart';

Dio _server(List<RequestOptions> seen, Object reply) {
  final dio = Dio();
  dio.interceptors.add(InterceptorsWrapper(onRequest: (options, handler) {
    seen.add(options);
    handler.resolve(Response(requestOptions: options, statusCode: 200, data: reply));
  }));
  return dio;
}

const _map = {
  'rows': [
    {'charge_head': 'Lift', 'element_code': 'lift_maintenance', 'element': 'Lift Maintenance', 'posted_ledger': 'Service Charges',
     'source': 'element', 'source_label': 'Standard element table', 'society_rule_ledger': 'Repairs & Maintenance Fund',
     'status': 'differs_from_society_rule', 'recent_postings': [{'ledger': 'Service Charges', 'amount': '600.00'}]},
    {'charge_head': 'Club Fee', 'element_code': null, 'posted_ledger': 'Service Charges', 'source': 'charge_type',
     'source_label': 'Default for the charge type (fallback)', 'status': 'no_element', 'recent_postings': []},
    {'charge_head': 'Service Charges', 'element_code': 'service_charges', 'posted_ledger': 'Service Charges', 'source': 'element',
     'status': 'ok', 'recent_postings': []},
  ],
  'unmatched_bill_lines': [],
  'ledgers': [{'id': 'a1', 'name': 'Repairs & Maintenance Fund'}],
  'fingerprint': 'f00d',
  'signed_off': null,
  'signed_off_current': false,
  'note': 'n',
};

void main() {
  test('map parses rows and counts what is flagged', () async {
    final seen = <RequestOptions>[];
    final m = await LegalApi(dio: _server(seen, _map)).ledgerMap();
    expect(seen.single.path, '/accounts-agent/ledger-mapping');
    expect(m.rows.length, 3);
    expect(m.flagged, 2);
    expect(m.rows.first.ruleLedger, 'Repairs & Maintenance Fund');
    expect(m.rows.first.recent.single['amount'], '600.00');
    expect(m.signedOffCurrent, isFalse);
  });

  test('sign-off sends the fingerprint of the map that was shown', () async {
    final seen = <RequestOptions>[];
    await LegalApi(dio: _server(seen, _map)).signOffLedgerMap(role: 'AUDITOR', note: 'reviewed', fingerprint: 'f00d');
    expect(seen.single.path, '/accounts-agent/ledger-mapping/sign-off');
    expect(seen.single.data, {'role': 'AUDITOR', 'note': 'reviewed', 'fingerprint': 'f00d'});
  });

  test('ledger rule payload names the element topic and the ledger', () {
    final p = buildLedgerRulePayload(elementCode: 'lift_maintenance', elementName: 'Lift', accountId: 'a1', documentId: 'd1',
        byeLawNumber: '67', page: ' 21 ');
    expect(p, {
      'rule_code': 'SOC-LED-LIFT-MAINTENANCE', 'title': 'Ledger for Lift', 'topic': 'ledger.element.lift_maintenance',
      'rule_category': 'ledger', 'source_level': 'D', 'source_document_id': 'd1',
      'calculation_method': {'type': 'element_ledger', 'account_id': 'a1'}, 'bye_law_number': '67', 'page_number': '21',
    });
    expect(() => buildLedgerRulePayload(elementCode: 'x', elementName: 'X', accountId: null, documentId: 'd'), throwsFormatException);
    expect(() => buildLedgerRulePayload(elementCode: 'x', elementName: 'X', accountId: 'a', documentId: null), throwsFormatException);
  });

  test('status labels never call a difference "OK"', () {
    expect(ledgerStatusLabel('differs_from_society_rule'), 'Differs from society rule');
    expect(ledgerStatusLabel('fallback_ledger'), contains('fallback'));
    expect(ledgerStatusLabel('ok'), 'OK');
  });
}
