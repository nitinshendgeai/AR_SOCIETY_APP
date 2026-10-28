import 'package:flutter_test/flutter_test.dart';
import 'package:ar_society_app/features/resident_master/data/agreement_channel.dart';
import 'package:ar_society_app/features/resident_master/data/models/resident_master_models.dart';
import 'package:ar_society_app/features/resident_master/data/tenant_import_columns.dart';

void main() {
  group('tenant import columns', () {
    test('are found by their headings, in any order and under the names people use', () {
      final cols = TenantImportColumns.fromHeader(
          ['Sr', 'Tower', 'Unit No', 'Name of Tenant', 'Rent', 'Deposit', 'Lease Start', 'Lease End', 'Through', 'Broker Name'])!;
      final row = ['1', 'A', '101', 'Meena Shah', '25000', '75000', '01/04/2026', '28/02/2027', 'Agent', 'Ramesh Estates'];
      expect(cols.fields(row), containsPair('wing', 'A'));
      expect(cols.fields(row), containsPair('flat_number', '101'));
      expect(cols.fields(row), containsPair('full_name', 'Meena Shah'));
      expect(cols.fields(row), containsPair('monthly_rent', '25000'));
      expect(cols.fields(row), containsPair('agreement_start_date', '01/04/2026'));
      expect(cols.fields(row), containsPair('channel', 'Agent'));
      expect(cols.fields(row), containsPair('channel_name', 'Ramesh Estates'));
      expect(cols.fields(row)['email'], '');
    });

    test('the template headings are all recognised', () {
      final cols = TenantImportColumns.fromHeader(tenantImportTemplateHeader)!;
      final row = [for (var i = 0; i < tenantImportTemplateHeader.length; i++) 'v$i'];
      expect(cols.canonical(row), row);
    });

    test('a file with no heading row falls back to the template order; a heading row needs a flat and a name', () {
      expect(TenantImportColumns.fromHeader(['A', '101', 'Meena']), isNull);
      expect(TenantImportColumns.fromHeader(['Flat No', 'Rent']), isNull);
      final cols = TenantImportColumns.positional();
      expect(cols.fields(['A', '101', 'Meena'])['full_name'], 'Meena');
    });
  });

  group('agreement channel', () {
    test('has labels, and a name only for an agent, an app or another channel', () {
      expect(agreementChannelLabel('online_app'), 'Online app / portal');
      expect(agreementChannelLabel(null), '');
      expect(agreementChannelNameLabel('agent'), 'Agent / agency name');
      expect(agreementChannelNameLabel('online_app'), 'App or portal name');
      expect(agreementChannelHasName('direct'), isFalse);
      expect(agreementChannelHasName(null), isFalse);
      expect(agreementChannelHasName('agent'), isTrue);
    });

    test('is read from a tenant and from an agreement', () {
      final t = TenantModel.fromJson({
        'id': 't1', 'flat_id': 'f1', 'full_name': 'Meena Shah', 'agreement_channel': 'agent',
        'agreement_channel_name': 'Ramesh Estates',
      });
      expect(t.agreementChannel, 'agent');
      expect(t.agreementChannelName, 'Ramesh Estates');
      final a = AgreementModel.fromJson({
        'id': 'a1', 'society_id': 's1', 'flat_id': 'f1', 'tenant_id': 't1', 'start_date': '2026-04-01',
        'end_date': '2027-02-28', 'status': 'active', 'channel': 'direct',
      });
      expect(a.channel, 'direct');
      expect(a.channelName, isNull);
    });
  });
}
