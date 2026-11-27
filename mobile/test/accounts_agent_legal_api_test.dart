import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ar_society_app/features/accounts_agent/data/accounts_agent_api.dart';
import 'package:ar_society_app/features/accounts_agent/data/legal_api.dart';
import 'package:ar_society_app/features/accounts_agent/presentation/widgets/agent_widgets.dart';

Dio _server(List<RequestOptions> seen, Object reply) {
  final dio = Dio();
  dio.interceptors.add(InterceptorsWrapper(onRequest: (options, handler) {
    seen.add(options);
    handler.resolve(Response(requestOptions: options, statusCode: 200, data: reply));
  }));
  return dio;
}

const _source = {
  'rule_code': 'MH-CHG-NONOCC-CAP',
  'version': 1,
  'title': 'Non-occupancy charges — ceiling as % of service charges',
  'source': 'Maharashtra Co-operative Societies (Amendment) Rules, 2026',
  'source_level_name': 'statute',
  'rule_number': '106C-12 (sub-rule to be verified)',
  'effective_from': '2026-06-22',
  'legal_status': 'UNVERIFIED',
  'verification_status': 'PENDING_VERIFICATION',
  'verified': false,
  'society_specific': false,
  'blocked_by_reviews': ['Rule 106C-12 numbering'],
  'uncertainty': 'This legal reference has not been verified.',
};

void main() {
  test('element review: findings with their fixes, and applying the chosen ones', () async {
    final seen = <RequestOptions>[];
    final api = LegalApi(dio: _server(seen, {
      'summary': {'elements': 12, 'to_fix': 1, 'high': 1},
      'recommendations': [
        {'id': 'f1', 'kind': 'wrong_ledger_nature', 'severity': 'HIGH', 'element': 'Sinking Fund', 'in_use': true,
         'title': "'Sinking Fund' is credited to the wrong kind of ledger", 'detail': 'A fund held for the members…',
         'current_ledger': 'Service Charges', 'proposed_ledger': 'Sinking Fund', 'bye_law_ref': 'Bye-laws 13(c), 67(a)(v)'},
      ],
      'applied': [{'id': 'f1', 'change': "'Sinking Fund' now credits 'Sinking Fund'"}],
    }));
    final r = await api.elementReview();
    expect(seen.last.path, '/accounts-agent/ledger-mapping/element-review');
    expect(r.elements, 12);
    expect(r.fixes.single.severity, 'HIGH');
    expect(r.fixes.single.proposedLedger, 'Sinking Fund');
    final done = await api.applyElementFixes(['f1']);
    expect(seen.last.path, '/accounts-agent/ledger-mapping/element-review/apply');
    expect(seen.last.data, {'ids': ['f1']});
    expect(done.single, contains('now credits'));
  });

  test('a potential issue is never labelled as confirmed', () {
    expect(classificationLabel('POTENTIAL_NON_COMPLIANCE'), contains('needs review'));
    expect(classificationLabel('POTENTIAL_NON_COMPLIANCE').toLowerCase(), isNot(contains('confirmed')));
    expect(classificationLabel('CONFIRMED_STATUTORY_VALIDATION_FAILURE'), 'Confirmed statutory validation failure');
    expect(classificationLabel('anything-else'), 'Advisory observation');
  });

  test('assistant answer keeps sources, verification and uncertainty', () async {
    final seen = <RequestOptions>[];
    final api = LegalApi(dio: _server(seen, {
      'intent': 'non_occupancy',
      'answer': 'Capped at 10%.',
      'sources': [_source],
      'verified_law': false,
      'uncertainty': 'Not verified.',
      'data': {},
    }));
    final a = await api.ask('  non-occupancy?  ');
    expect(seen.single.path, '/accounts-agent/assistant/ask');
    expect(seen.single.data, {'question': 'non-occupancy?'});
    expect(seen.single.queryParameters.containsKey('society_id'), isFalse);
    expect(a.verifiedLaw, isFalse);
    expect(a.sources.single.reference, 'Rule 106C-12 (sub-rule to be verified)');
    expect(a.sources.single.blockedBy, ['Rule 106C-12 numbering']);
  });

  test('finding carries classification, engine and legal source', () {
    final f = AgentFinding.fromJson({
      'id': 'f1', 'title': 'x', 'severity': 'HIGH', 'confidence': 0.6, 'rule_code': 'L-CHG-NOC-01', 'status': 'NEW',
      'finding_class': 'POTENTIAL_NON_COMPLIANCE', 'classification': 'POTENTIAL_NON_COMPLIANCE', 'engine': 'legal',
      'category': 'charges', 'explanation': 'e', 'legal_source': _source,
    });
    expect(f.engine, 'legal');
    expect(LegalSource.from(f.legalSource)!.ruleCode, 'MH-CHG-NONOCC-CAP');
  });

  test('section filter is sent to the findings endpoint', () async {
    final seen = <RequestOptions>[];
    final api = AccountsAgentApi(dio: _server(seen, {'items': [], 'total': 0}));
    await api.findings(const FindingsFilter(section: 'funds'));
    expect(seen.single.queryParameters['section'], 'funds');
  });

  test('document verification sends the explicit status and note', () async {
    final seen = <RequestOptions>[];
    final api = LegalApi(dio: _server(seen, {'id': 'd1', 'title': 't', 'status': 'REGISTERED', 'operative': true}));
    final d = await api.verifyDocument('d1', status: 'REGISTERED', verification: 'VERIFIED_SECONDARY_SOURCE', note: 'certified copy',
        approvalDate: DateTime(2020, 5, 1));
    expect(seen.single.data, {
      'status': 'REGISTERED', 'verification_status': 'VERIFIED_SECONDARY_SOURCE', 'note': 'certified copy', 'approval_date': '2020-05-01'
    });
    expect(d.operative, isTrue);
  });

  testWidgets('legal source card shows that the rule is not verified', (tester) async {
    await tester.pumpWidget(const MaterialApp(home: Scaffold(body: SingleChildScrollView(child: LegalSourceCard(source: LegalSource(_source))))));
    expect(find.text('Pending verification'), findsOneWidget);
    expect(find.text('This legal reference has not been verified.'), findsOneWidget);
    expect(find.textContaining('106C-12'), findsWidgets);
  });
}
