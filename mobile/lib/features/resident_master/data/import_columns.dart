/// Reading a resident file the way a person laid it out: columns found by their header (in any order, under the
/// names people actually use), dates as written in India (day first).
library;

/// The columns the import understands, in the order of the template.
const importTemplateHeader = [
  'Wing', 'Flat Number', 'Full Name', 'Resident Type', 'Is Primary', 'Phone', 'Email', 'Floor',
  'Possession Date', 'Electric Meter No', 'Consumer No', 'Flat Type', 'Area (sq ft)',
];

// New columns go at the end so a file laid out by the older template still reads by position.
const _keys = [
  'wing', 'flat', 'name', 'type', 'primary', 'phone', 'email', 'floor', 'possession', 'meter', 'consumer',
  'bhk', 'area',
];

/// "Area", "Carpet Area (Sq.Ft.)", "Built up area in sqft", "Flat area sq m"… — a name for the area, with or without a unit.
final _areaAliases = [
  for (final base in ['area', 'flat area', 'carpet area', 'built up area', 'builtup area', 'super built up area', 'saleable area', 'sq ft', 'sqft'])
    for (final unit in ['', ' sq ft', ' sqft', ' in sq ft', ' in sqft', ' sq feet', ' sq m', ' sqm', ' sq mt', ' sq mtr', ' in sq m'])
      '$base$unit',
];

final _aliases = <String, List<String>>{
  'wing': ['wing', 'wing name', 'block', 'building', 'tower'],
  'flat': ['flat number', 'flat no', 'flat', 'flat num', 'unit', 'unit no', 'unit number', 'flat/unit no'],
  'name': ['full name', 'name', 'owner name', 'member name', 'resident name', 'name of member', 'name of owner'],
  'type': ['resident type', 'type', 'relationship'],
  'primary': ['is primary', 'primary', 'primary owner'],
  'phone': ['phone', 'mobile', 'mobile no', 'mobile number', 'phone number', 'contact', 'contact no', 'phone no'],
  'email': ['email', 'email id', 'e-mail', 'mail id', 'email address'],
  'floor': ['floor', 'floor no', 'floor number'],
  'possession': [
    'possession date', 'date of possession', 'possession', 'possession dt', 'possession on', 'handover date',
    'date of handover',
  ],
  // A sheet that gives the purchase date instead of the possession date: read the same way (possession wins when
  // a sheet has both).
  'purchase': [
    'purchase date', 'date of purchase', 'purchase dt', 'purchased on', 'purchase on', 'date of purchase possession',
    'possession purchase date', 'purchase possession date', 'possession purchase', 'purchase possession',
    'date of agreement', 'agreement date', 'sale deed date',
  ],
  'bhk': [
    'flat type', 'type of flat', 'flat configuration', 'configuration', 'bhk', 'bhk type', 'unit type',
    'type of unit', 'flat bhk',
  ],
  'area': _areaAliases,
  'meter': [
    'electric meter no', 'electric meter number', 'meter no', 'meter number', 'meter', 'electricity meter no',
    'electricity meter', 'electric meter', 'meter no.',
  ],
  'consumer': [
    'consumer no', 'consumer number', 'consumer no.', 'electricity consumer no', 'electric consumer no',
    'consumer', 'consumer id', 'consumer account no',
  ],
};

String _norm(String s) => s
    .toLowerCase()
    .replaceAll(RegExp(r'[_\-./()]'), ' ')
    .replaceAll(RegExp(r'\s+'), ' ')
    .trim();

/// Which cell holds which field.
class ImportColumns {
  final Map<String, int> _index;
  const ImportColumns._(this._index);

  /// A file with no header row is read by position, as the template lays it out.
  factory ImportColumns.positional() => ImportColumns._({for (var i = 0; i < _keys.length; i++) _keys[i]: i});

  /// The columns named by `headerRow`, or null when it isn't a header row (it needs a recognisable Wing or Flat
  /// column, plus at least one more known heading — a data row never gets this far by accident).
  static ImportColumns? fromHeader(List<String> headerRow) {
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
    final known = found.length;
    if (known < 2 || !(found.containsKey('wing') || found.containsKey('flat'))) return null;
    return ImportColumns._(found);
  }

  bool has(String key) => _index.containsKey(key);

  String cell(List<String> row, String key) {
    final i = _index[key];
    return i == null || i >= row.length ? '' : row[i].trim();
  }

  /// The date column of a row: the possession date, or — in a sheet that has only a purchase date — that.
  /// (Which heading it came from is returned so an error can name the column the person actually has.)
  ({String text, String heading}) dateOf(List<String> row) {
    final possession = cell(row, 'possession');
    if (possession.isNotEmpty || !has('purchase')) return (text: possession, heading: 'Possession Date');
    return (text: cell(row, 'purchase'), heading: 'Purchase Date');
  }

  /// The row in template order — what the preview shows and the error file is written from.
  List<String> canonical(List<String> row) => [for (final k in _keys) cell(row, k)];
}

const _months = {
  'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6, 'jul': 7, 'aug': 8, 'sep': 9, 'sept': 9, 'oct': 10,
  'nov': 11, 'dec': 12,
  'january': 1, 'february': 2, 'march': 3, 'april': 4, 'june': 6, 'july': 7, 'august': 8, 'september': 9,
  'october': 10, 'november': 11, 'december': 12,
};

/// A date as it is written in an Indian sheet: 01/04/2019, 1-4-19, 01.04.2019, 2019-04-01, 1-Apr-2019 or
/// 1 April 2019 — day first. A time after the date is ignored. Null when it isn't a real date.
DateTime? parseImportDate(String text) {
  var t = text.trim();
  if (t.isEmpty) return null;
  t = t.split(RegExp(r'[T ](?=\d{1,2}:)')).first.trim();
  int? y, m, d;

  final iso = RegExp(r'^(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})$').firstMatch(t);
  final dmy = RegExp(r'^(\d{1,2})[-/.](\d{1,2})[-/.](\d{2}|\d{4})$').firstMatch(t);
  final named = RegExp(r'^(\d{1,2})[-/. ]+([A-Za-z]{3,9})[-/., ]+(\d{2}|\d{4})$').firstMatch(t);
  if (iso != null) {
    y = int.parse(iso[1]!);
    m = int.parse(iso[2]!);
    d = int.parse(iso[3]!);
  } else if (dmy != null) {
    d = int.parse(dmy[1]!);
    m = int.parse(dmy[2]!);
    y = _year(dmy[3]!);
  } else if (named != null) {
    d = int.parse(named[1]!);
    m = _months[named[2]!.toLowerCase()];
    y = _year(named[3]!);
  }
  if (y == null || m == null || d == null) return null;
  if (m < 1 || m > 12 || d < 1 || d > 31) return null;
  final date = DateTime(y, m, d);
  // 31/02/2020 rolls over to March in DateTime; that is not a date.
  if (date.year != y || date.month != m || date.day != d) return null;
  return date;
}

int _year(String s) {
  final n = int.parse(s);
  if (s.length == 4) return n;
  return n <= 49 ? 2000 + n : 1900 + n;
}

/// A flat type as people write it: "2 BHK", "2bhk", "2-BHK", "2", "1 RK", "Studio", "Penthouse"…
/// [value] is what the flat stores (1BHK…4BHK, Studio, Penthouse, Duplex, Shop, Office, Other); [note] says when
/// a reading was a guess; [error] when it can't be read at all.
({String? value, String? note, String? error}) parseFlatType(String text) {
  // "2.5 BHK" is a 2 BHK with a small extra room: read as 2 (the dot is dropped below, so take the .5 off first).
  final t = text.toLowerCase().replaceAllMapped(RegExp(r'(\d)\.5'), (m) => m[1]!).replaceAll(RegExp(r'[\s\-_./]'), '');
  if (t.isEmpty) return (value: null, note: null, error: null);
  final bhk = RegExp(r'^(\d{1,2})(bhk|bedroom|bedrooms|br|bed)?$').firstMatch(t);
  if (bhk != null && (bhk[2] != null || RegExp(r'^\d$').hasMatch(t))) {
    final n = int.parse(bhk[1]!);
    if (n >= 1 && n <= 4) return (value: '${n}BHK', note: null, error: null);
    if (n >= 5) return (value: 'Other', note: '$n BHK is saved as "Other"', error: null);
  }
  const named = {
    '1rk': 'Studio', 'rk': 'Studio', 'studio': 'Studio', 'studioapartment': 'Studio', 'penthouse': 'Penthouse',
    'duplex': 'Duplex', 'shop': 'Shop', 'office': 'Office', 'other': 'Other',
  };
  final hit = named[t];
  if (hit != null) {
    return (value: hit, note: t == '1rk' || t == 'rk' ? '1 RK is saved as "Studio"' : null, error: null);
  }
  return (
    value: null,
    note: null,
    error: 'Flat Type "$text" is not recognised (use 1 BHK, 2 BHK, 3 BHK, 4 BHK, Studio, Penthouse, Duplex, Shop, '
        'Office or Other)',
  );
}

/// A flat's area in square feet from "650", "650.5", "1,050", "650 sq ft", "650 sqft" or "60 sq m" (square metres are
/// converted). [error] when it isn't a sensible area.
({double? sqft, String? error}) parseAreaSqft(String text) {
  var t = text.toLowerCase().trim();
  if (t.isEmpty) return (sqft: null, error: null);
  if (t.startsWith('-')) return (sqft: null, error: 'Area "$text" is not a sensible flat area');
  final metric = RegExp(r'(sq\.?\s*m(tr|eters?|etres?)?\b|sqm|m2|m²)').hasMatch(t);
  final number = RegExp(r'\d[\d,]*(?:\.\d+)?').firstMatch(t)?.group(0);
  final value = number == null ? null : double.tryParse(number.replaceAll(',', ''));
  if (value == null) return (sqft: null, error: 'Area "$text" is not a number (square feet, e.g. 650)');
  final sqft = (metric ? value * 10.7639 : value);
  if (sqft <= 0 || sqft > 100000) {
    return (sqft: null, error: 'Area "$text" is not a sensible flat area (between 1 and 1,00,000 sq ft)');
  }
  return (sqft: (sqft * 100).round() / 100, error: null);
}
