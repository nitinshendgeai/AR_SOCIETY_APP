import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ar_society_app/features/accounts_agent/data/legal_api.dart';
import 'package:ar_society_app/features/accounts_agent/presentation/screens/rule_revision_screen.dart';
import 'package:ar_society_app/features/resident_master/data/datasources/resident_master_remote_datasource.dart';
import 'package:ar_society_app/features/resident_master/data/models/resident_master_models.dart';
import 'package:ar_society_app/features/resident_master/presentation/widgets/ownership_transfer_sheet.dart';

Dio _server(List<RequestOptions> seen, Object reply) {
  final dio = Dio();
  dio.interceptors.add(InterceptorsWrapper(onRequest: (options, handler) {
    seen.add(options);
    handler.resolve(Response(requestOptions: options, statusCode: 200, data: reply));
  }));
  return dio;
}

LegalRule _rule(Map<String, dynamic> calc, {String from = '2024-04-01'}) => LegalRule({
      'id': 'r1', 'rule_code': 'SOC-INT', 'version': 1, 'title': 'Interest', 'effective_from': from,
      'calculation_method': calc, 'superseded_by_id': null,
    });

ResidentModel _res(String id, String type, {bool active = true, String? out}) => ResidentModel.fromJson({
      'id': id, 'flat_id': 'f1', 'full_name': 'Person $id', 'resident_type': type, 'is_active': active, 'move_out_date': out,
    });

void main() {
  test('a revision keeps the calculation type and changes only the figure', () {
    final p = buildRevisionPayload(current: _rule({'type': 'max_pct', 'value': 12, 'unit': '% p.a.'}),
        effectiveFrom: DateTime(2027, 4, 1), changeNote: ' GB resolution 12/2027 ', value: '10', page: '14');
    expect(p, {
      'effective_from': '2027-04-01', 'change_note': 'GB resolution 12/2027',
      'calculation_method': {'type': 'max_pct', 'value': 10, 'unit': '% p.a.'}, 'page_number': '14',
    });
  });

  test('a revision must start after the current version and say why', () {
    final r = _rule({'type': 'max_pct', 'value': 12});
    expect(() => buildRevisionPayload(current: r, effectiveFrom: null, changeNote: 'x y z'), throwsFormatException);
    expect(() => buildRevisionPayload(current: r, effectiveFrom: DateTime(2024, 4, 1), changeNote: 'same day'), throwsFormatException);
    expect(() => buildRevisionPayload(current: r, effectiveFrom: DateTime(2027, 1, 1), changeNote: ''), throwsFormatException);
    expect(() => buildRevisionPayload(current: r, effectiveFrom: DateTime(2027, 1, 1), changeNote: 'new', value: 'abc'),
        throwsFormatException);
    // Text-only change: no figure, no calculation sent.
    expect(buildRevisionPayload(current: r, effectiveFrom: DateTime(2027, 1, 1), changeNote: 'wording', text: 'New text')
        .containsKey('calculation_method'), isFalse);
  });

  test('an element → ledger rule is revised to another ledger', () {
    final p = buildRevisionPayload(current: _rule({'type': 'element_ledger', 'account_id': 'old', 'element': 'lift'}),
        effectiveFrom: DateTime(2027, 4, 1), changeNote: 'policy change', accountId: 'new');
    expect(p['calculation_method'], {'type': 'element_ledger', 'account_id': 'new'});
    expect(() => buildRevisionPayload(current: _rule({'type': 'element_ledger'}), effectiveFrom: DateTime(2027, 4, 1),
        changeNote: 'x y z'), throwsFormatException);
  });

  test('revision goes to the versions endpoint', () async {
    final seen = <RequestOptions>[];
    await LegalApi(dio: _server(seen, {'id': 'r2', 'rule_code': 'SOC-INT', 'version': 2})).reviseRule('r1', {'change_note': 'x'});
    expect('${seen.single.method} ${seen.single.path}', 'POST /accounts-agent/legal/rules/r1/versions');
  });

  test('only other active owners and co-owners can receive the flat', () {
    final from = _res('a', 'owner');
    final rows = [from, _res('b', 'owner'), _res('c', 'co_owner'), _res('d', 'family'), _res('e', 'owner', active: false),
                  _res('f', 'owner', out: '2025-01-01')];
    expect(transferCandidates(rows, from).map((r) => r.id), ['b', 'c']);
  });

  test('ownership transfer request carries the previous owner and the papers', () async {
    final seen = <RequestOptions>[];
    await ResidentMasterRemoteDataSource(dio: _server(seen, {})).ownershipTransfer(
        flatId: 'f1', newOwnerId: 'b', transferDate: '2026-11-01', previousOwnerIds: ['a'], shareCertificateNo: 'SC-1',
        deedReference: '', notes: null);
    expect(seen.single.path, '/occupancy/ownership-transfer');
    expect(seen.single.data, {'flat_id': 'f1', 'new_owner_id': 'b', 'transfer_date': '2026-11-01', 'previous_owner_ids': ['a'],
      'share_certificate_no': 'SC-1'});
  });
}
