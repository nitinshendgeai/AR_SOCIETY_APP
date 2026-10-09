/// Reading a resident file the way a person laid it out: columns found by their header (in any order, under the
/// names people actually use), dates as written in India (day first).
library;

/// The columns the import understands, in the order of the template.
const importTemplateHeader = [
  'Wing', 'Flat Number', 'Full Name', 'Resident Type', 'Is Primary', 'Phone', 'Email', 'Floor',
  'Possession Date', 'Electric Meter No', 'Consumer No',
];

const _keys = ['wing', 'flat', 'name', 'type', 'primary', 'phone', 'email', 'floor', 'possession', 'meter', 'consumer'];

const _aliases = <String, List<String>>{
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
  'meter': [
    'electric meter no', 'electric meter number', 'meter no', 'meter number', 'meter', 'electricity meter no',
    'electricity meter', 'electric meter', 'meter no.',
  ],
  'consumer': [
    'consumer no', 'consumer number', 'consumer no.', 'electricity consumer no', 'electric consumer no',
    'consumer', 'consumer id', 'consumer account no',
  ],
};

String _norm(String s) => s.toLowerCase().replaceAll(RegExp(r'[_\-.]'), ' ').replaceAll(RegExp(r'\s+'), ' ').trim();

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
