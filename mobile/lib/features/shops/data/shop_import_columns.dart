/// Reading a shops file by its headings, in any order and under the names people use. The same idea as the
/// resident import, with the shop columns.
library;

const shopImportTemplateHeader = [
  'Shop Number', 'Owner Name', 'Phone', 'Email', 'Floor', 'Location', 'Area Sqft', 'Business Name', 'Occupancy',
  'Tenant Name', 'Tenant Phone', 'Possession Date', 'Electric Meter No', 'Consumer No', 'Remarks',
];

const _keys = [
  'shop_number', 'owner_name', 'owner_phone', 'owner_email', 'floor', 'location', 'area_sqft', 'business_name',
  'occupancy', 'tenant_name', 'tenant_phone', 'possession_date', 'electric_meter_no', 'electric_consumer_no',
  'remarks',
];

const _aliases = <String, List<String>>{
  'shop_number': ['shop number', 'shop no', 'shop', 'shop num', 'unit', 'unit no', 'shop/unit no', 'shop no.'],
  'owner_name': ['owner name', 'owner', 'name of owner', 'name', 'member name', 'name of member'],
  'owner_phone': ['phone', 'mobile', 'mobile no', 'mobile number', 'owner phone', 'owner mobile', 'contact', 'phone number'],
  'owner_email': ['email', 'email id', 'owner email', 'e-mail', 'email address'],
  'floor': ['floor', 'floor no', 'floor number'],
  'location': ['location', 'block', 'wing', 'building', 'address', 'position'],
  'area_sqft': ['area sqft', 'area', 'area sq ft', 'area (sq ft)', 'carpet area', 'area in sqft', 'built up area'],
  'business_name': ['business name', 'business', 'shop name', 'trade name', 'name of shop', 'firm name', 'firm'],
  'occupancy': ['occupancy', 'status', 'occupied by', 'usage', 'occupancy status'],
  'tenant_name': ['tenant name', 'tenant', 'occupant name', 'occupant', 'name of tenant'],
  'tenant_phone': ['tenant phone', 'tenant mobile', 'occupant phone', 'tenant contact'],
  'possession_date': [
    'possession date', 'date of possession', 'possession', 'possession dt', 'handover date', 'date of handover',
  ],
  'electric_meter_no': [
    'electric meter no', 'electric meter number', 'meter no', 'meter number', 'meter', 'electricity meter no',
    'electricity meter', 'electric meter',
  ],
  'electric_consumer_no': [
    'consumer no', 'consumer number', 'electricity consumer no', 'electric consumer no', 'consumer', 'consumer id',
  ],
  'remarks': ['remarks', 'notes', 'note', 'remark', 'comments'],
};

String _norm(String s) => s.toLowerCase().replaceAll(RegExp(r'[_\-.]'), ' ').replaceAll(RegExp(r'\s+'), ' ').trim();

class ShopImportColumns {
  final Map<String, int> _index;
  const ShopImportColumns._(this._index);

  factory ShopImportColumns.positional() =>
      ShopImportColumns._({for (var i = 0; i < _keys.length; i++) _keys[i]: i});

  /// The columns named by `headerRow`, or null when it isn't a header row: it needs a Shop Number column and one
  /// more recognised heading.
  static ShopImportColumns? fromHeader(List<String> headerRow) {
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
    if (found.length < 2 || !found.containsKey('shop_number')) return null;
    return ShopImportColumns._(found);
  }

  String cell(List<String> row, String key) {
    final i = _index[key];
    return i == null || i >= row.length ? '' : row[i].trim();
  }

  List<String> canonical(List<String> row) => [for (final k in _keys) cell(row, k)];

  Map<String, String> fields(List<String> row) => {for (final k in _keys) k: cell(row, k)};
}
