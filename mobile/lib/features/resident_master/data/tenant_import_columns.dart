/// Reading a tenants file by its headings, in any order and under the names people use. The same idea as the shops and
/// residents imports, with the tenant columns.
library;

const tenantImportTemplateHeader = [
  'Wing', 'Flat No', 'Tenant Name', 'Mobile', 'Email', 'Agreement Start', 'Agreement End', 'Monthly Rent',
  'Security Deposit', 'Move-in Date', 'Channel', 'Agent / App Name', 'ID Proof Type', 'ID Proof Number', 'Remarks',
];

const _keys = [
  'wing', 'flat_number', 'full_name', 'phone', 'email', 'agreement_start_date', 'agreement_end_date', 'monthly_rent',
  'security_deposit', 'move_in_date', 'channel', 'channel_name', 'id_proof_type', 'id_proof_number', 'remarks',
];

const _aliases = <String, List<String>>{
  'wing': ['wing', 'building', 'block', 'tower', 'wing name'],
  'flat_number': ['flat no', 'flat number', 'flat', 'flat num', 'unit', 'unit no', 'flat no.', 'room no', 'apartment'],
  'full_name': ['tenant name', 'tenant', 'name', 'full name', 'name of tenant', 'renter', 'lessee'],
  'phone': ['mobile', 'phone', 'mobile no', 'mobile number', 'tenant mobile', 'tenant phone', 'contact', 'phone number'],
  'email': ['email', 'email id', 'tenant email', 'e-mail', 'email address'],
  'agreement_start_date': [
    'agreement start', 'agreement start date', 'start date', 'lease start', 'rent start', 'agreement from',
    'from date', 'agreement date', 'start',
  ],
  'agreement_end_date': [
    'agreement end', 'agreement end date', 'end date', 'lease end', 'agreement to', 'to date', 'expiry', 'expiry date',
    'valid till', 'end',
  ],
  'monthly_rent': ['monthly rent', 'rent', 'rent per month', 'monthly rent amount', 'rent amount'],
  'security_deposit': ['security deposit', 'deposit', 'security', 'deposit amount', 'refundable deposit'],
  'move_in_date': ['move in date', 'move-in date', 'move in', 'date of move in', 'possession date', 'joining date'],
  'channel': [
    'channel', 'agreement channel', 'through', 'source', 'agreement through', 'via', 'agreement via', 'mode',
    'agreement source',
  ],
  'channel_name': [
    'agent / app name', 'agent name', 'agent', 'app name', 'broker name', 'broker', 'agency', 'channel name',
    'portal name', 'agent/app name', 'agent or app name',
  ],
  'id_proof_type': ['id proof type', 'id type', 'id proof', 'document type', 'kyc type'],
  'id_proof_number': ['id proof number', 'id number', 'id no', 'document number', 'aadhaar', 'aadhaar no', 'pan'],
  'remarks': ['remarks', 'notes', 'note', 'remark', 'comments'],
};

String _norm(String s) => s.toLowerCase().replaceAll(RegExp(r'[_\-.]'), ' ').replaceAll(RegExp(r'\s+'), ' ').trim();

class TenantImportColumns {
  final Map<String, int> _index;
  const TenantImportColumns._(this._index);

  factory TenantImportColumns.positional() =>
      TenantImportColumns._({for (var i = 0; i < _keys.length; i++) _keys[i]: i});

  /// The columns named by `headerRow`, or null when it isn't a header row: it needs a Flat No column, a Tenant Name
  /// column and nothing else is required.
  static TenantImportColumns? fromHeader(List<String> headerRow) {
    final found = <String, int>{};
    for (var i = 0; i < headerRow.length; i++) {
      final cell = _norm(headerRow[i]);
      if (cell.isEmpty) continue;
      for (final e in _aliases.entries) {
        if (!found.containsKey(e.key) && e.value.map(_norm).contains(cell)) {
          found[e.key] = i;
          break;
        }
      }
    }
    if (!found.containsKey('flat_number') || !found.containsKey('full_name')) return null;
    return TenantImportColumns._(found);
  }

  String cell(List<String> row, String key) {
    final i = _index[key];
    return i == null || i >= row.length ? '' : row[i].trim();
  }

  List<String> canonical(List<String> row) => [for (final k in _keys) cell(row, k)];

  Map<String, String> fields(List<String> row) => {for (final k in _keys) k: cell(row, k)};
}
