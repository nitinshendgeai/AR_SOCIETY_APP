import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ar_society_app/features/accounts_agent/data/legal_api.dart';
import 'package:ar_society_app/features/accounts_agent/presentation/screens/society_rule_form_screen.dart';

Dio _server(List<RequestOptions> seen, Object reply) {
  final dio = Dio();
  dio.interceptors.add(InterceptorsWrapper(onRequest: (options, handler) {
    seen.add(options);
    handler.resolve(Response(requestOptions: options, statusCode: 200, data: reply));
  }));
  return dio;
}

LegalRule _rule(String code, String topic, String? type, {bool society = false, String? supersededBy, String title = 'T'}) => LegalRule({
      'id': code, 'rule_code': code, 'topic': topic, 'title': title, 'rule_category': 'charges', 'society_specific': society,
      'superseded_by_id': supersededBy, 'calculation_method': type == null ? null : {'type': type, 'value': 1},
    });

const _interest = RuleTopic('charges.interest_on_arrears.max_rate_pct', 'Interest ceiling', 'charges', 'max_pct');

void main() {
  test('topics come from the latest jurisdiction rules that carry one figure', () {
    final topics = numericTopics([
      _rule('A', 'charges.interest_on_arrears.max_rate_pct', 'max_pct', title: 'Interest'),
      _rule('A0', 'charges.interest_on_arrears.max_rate_pct', 'max_pct', supersededBy: 'A'),
      _rule('B', 'charges.apportionment', 'apportionment'),          // not a single figure
      _rule('C', 'funds.sinking_fund.rate', 'min_pct', title: 'Sinking'),
      _rule('S', 'charges.non_occupancy.max_pct', 'max_pct', society: true),   // a society's own rule is not a topic source
    ]);
    expect(topics.map((t) => t.topic), ['charges.interest_on_arrears.max_rate_pct', 'funds.sinking_fund.rate']);
  });

  test('payload carries the figure as the topic\'s calculation and normalises the code', () {
    final p = buildSocietyRulePayload(
        ruleCode: ' soc-bl70 ', title: 'Bye-law 70 interest', level: 'D', documentId: 'doc1', topic: _interest, value: '10.5',
        byeLawNumber: '70', page: '14', effectiveFrom: DateTime(2024, 4, 1), clause: '  ');
    expect(p, {
      'rule_code': 'SOC-BL70', 'title': 'Bye-law 70 interest', 'topic': 'charges.interest_on_arrears.max_rate_pct',
      'rule_category': 'charges', 'source_level': 'D', 'source_document_id': 'doc1',
      'calculation_method': {'type': 'max_pct', 'value': 10.5}, 'bye_law_number': '70', 'page_number': '14',
      'effective_from': '2024-04-01', 'severity': 'MEDIUM',
    });
  });

  test('a free-text topic is recorded without a calculation', () {
    final p = buildSocietyRulePayload(ruleCode: 'SOC-PARK', title: 'Parking allotment', level: 'E', documentId: 'd',
        topic: null, otherTopic: 'parking.allotment');
    expect(p['topic'], 'parking.allotment');
    expect(p.containsKey('calculation_method'), isFalse);
    expect(p['rule_category'], 'other');
  });

  test('invalid input is refused before anything is sent', () {
    Map<String, dynamic> build({String code = 'SOC-1', String level = 'D', String? doc = 'd', String? value = '5', String title = 'Title'}) =>
        buildSocietyRulePayload(ruleCode: code, title: title, level: level, documentId: doc, topic: _interest, value: value);
    expect(() => build(code: 'x'), throwsFormatException);
    expect(() => build(code: 'bad code!'), throwsFormatException);
    expect(() => build(level: 'A'), throwsFormatException);        // a society cannot record statutory law
    expect(() => build(doc: null), throwsFormatException);
    expect(() => build(value: 'ten'), throwsFormatException);
    expect(() => build(value: '-1'), throwsFormatException);
    expect(() => build(title: ' '), throwsFormatException);
    expect(build()['calculation_method'], {'type': 'max_pct', 'value': 5});
  });

  test('create and verify go to the rule endpoints without a society id', () async {
    final seen = <RequestOptions>[];
    final api = LegalApi(dio: _server(seen, {'id': 'r1', 'rule_code': 'SOC-1', 'verification_status': 'VERIFIED_SECONDARY_SOURCE'}));
    await api.createSocietyRule({'rule_code': 'SOC-1'});
    final r = await api.verifyRule('r1', verification: 'VERIFIED_SECONDARY_SOURCE', note: 'checked', pageNumber: '14', legalStatus: 'BINDING');
    expect(seen.map((o) => '${o.method} ${o.path}'), ['POST /accounts-agent/legal/rules', 'POST /accounts-agent/legal/rules/r1/verify']);
    expect(seen.last.data, {'verification_status': 'VERIFIED_SECONDARY_SOURCE', 'note': 'checked', 'page_number': '14', 'legal_status': 'BINDING'});
    expect(seen.every((o) => !o.queryParameters.containsKey('society_id')), isTrue);
    expect(r.isVerified, isTrue);
  });
}
