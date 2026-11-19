import 'package:dio/dio.dart';
import 'package:ar_society_app/core/api/api_client.dart';

/// What a sheet of each flat's vehicles or family members is: its columns, the names people give them, and the
/// template. Columns are found by their headings, in any order, so the society's own sheet works.
class PeopleImportSpec {
  final String kind; // vehicles | family
  final String title, noun, plural, fileName, endpoint;
  final List<String> templateHeader;
  final List<String> keys; // the server's field names, in template order
  final Map<String, List<String>> aliases;
  final List<String> required; // the keys a header row must have to be recognised
  final List<List<String>> templateExamples;
  final String intro;

  const PeopleImportSpec({
    required this.kind,
    required this.title,
    required this.noun,
    required this.plural,
    required this.fileName,
    required this.endpoint,
    required this.templateHeader,
    required this.keys,
    required this.aliases,
    required this.required,
    required this.templateExamples,
    required this.intro,
  });
}

const _wing = ['wing', 'building', 'block', 'tower', 'wing name'];
const _flat = ['flat no', 'flat number', 'flat', 'flat num', 'unit', 'unit no', 'flat no.', 'unit number', 'apartment'];

const vehiclesImportSpec = PeopleImportSpec(
  kind: 'vehicles',
  title: 'Import Vehicles',
  noun: 'Vehicle',
  plural: 'Vehicles',
  fileName: 'vehicles_import',
  endpoint: '/vehicles/import',
  templateHeader: ['Wing', 'Flat No', 'Vehicle Number', 'Type', 'Make', 'Model', 'Colour', 'Parking Slot', 'Owner Name', 'Remarks'],
  keys: ['wing', 'flat_number', 'vehicle_number', 'vehicle_type', 'make', 'model', 'color', 'parking_slot', 'owner_name', 'remarks'],
  aliases: {
    'wing': _wing,
    'flat_number': _flat,
    'vehicle_number': [
      'vehicle number', 'vehicle no', 'vehicle no.', 'registration number', 'registration no', 'reg no', 'reg number',
      'reg. no', 'number plate', 'plate no', 'plate number', 'licence plate', 'license plate', 'car number', 'bike number',
      'vehicle', 'number',
    ],
    'vehicle_type': ['type', 'vehicle type', 'kind', 'category', 'vehicle kind', 'two/four wheeler', '2w/4w'],
    'make': ['make', 'company', 'brand', 'manufacturer', 'vehicle make'],
    'model': ['model', 'vehicle model', 'variant'],
    'color': ['colour', 'color', 'vehicle colour', 'vehicle color'],
    'parking_slot': ['parking slot', 'parking', 'slot', 'parking no', 'parking number', 'parking slot no', 'slot no'],
    'owner_name': ['owner name', 'owner', 'vehicle owner', 'registered to', 'registered owner', 'user', 'resident name'],
    'remarks': ['remarks', 'notes', 'note', 'remark', 'comments'],
  },
  required: ['flat_number', 'vehicle_number'],
  templateExamples: [
    ['A', '101', 'MH12AB1234', 'Car', 'Honda', 'City', 'White', 'P-12', 'Asha Rao', ''],
    ['A', '101', 'MH12CD5678', 'Bike', 'Hero', 'Splendor', 'Black', '', '', ''],
    ['B', '201', 'MH14EF0001', 'Scooter', 'Honda', 'Activa', 'Red', 'P-30', 'Priya Nair', ''],
  ],
  intro: '1. Download the template and fill it in (Excel, Google Sheets…), or use your own sheet: columns are found by their '
      'headings (Wing, Flat No, Vehicle Number, Type, Make, Colour…), in any order.\n'
      '2. One row per vehicle: a flat with three vehicles has three rows. Wing and Flat No must match a flat already in the '
      'society; only Flat No and Vehicle Number are required. Spaces and dashes in the number do not matter.\n'
      '3. Type can be written the way people say it: Car, 4W, Bike, Two Wheeler, Scooter, Activa, Cycle, Auto… A blank type '
      'is a car. Owner Name links the vehicle to that resident or tenant of the flat when the name matches.\n'
      '4. A vehicle already registered to the flat is skipped, so you can import a corrected file again. A number registered '
      'to another flat is reported. Each row is checked first and nothing is saved until you press Import.',
);

const familyImportSpec = PeopleImportSpec(
  kind: 'family',
  title: 'Import Family Members',
  noun: 'Family member',
  plural: 'Family Members',
  fileName: 'family_members_import',
  endpoint: '/residents/family-import',
  templateHeader: ['Wing', 'Flat No', 'Name', 'Relationship', 'Mobile', 'Email', 'Date of Birth'],
  keys: ['wing', 'flat_number', 'full_name', 'relationship', 'phone', 'email', 'date_of_birth'],
  aliases: {
    'wing': _wing,
    'flat_number': _flat,
    'full_name': [
      'name', 'full name', 'member name', 'family member', 'family member name', 'name of member', 'person', 'resident name',
    ],
    'relationship': [
      'relationship', 'relation', 'relation with owner', 'relation to owner', 'relationship with owner', 'type',
      'resident type',
    ],
    'phone': ['mobile', 'phone', 'mobile no', 'mobile number', 'phone number', 'contact', 'contact no', 'phone no'],
    'email': ['email', 'email id', 'e-mail', 'mail id', 'email address'],
    'date_of_birth': ['date of birth', 'dob', 'birth date', 'd.o.b', 'd o b', 'birthday', 'born on', 'birthdate'],
  },
  required: ['flat_number', 'full_name'],
  templateExamples: [
    ['A', '101', 'Sunita Rao', 'Wife', '9876543210', '', '14/03/1982'],
    ['A', '101', 'Aarav Rao', 'Son', '', '', '01/06/2015'],
    ['B', '201', 'Kiran Patil', 'Father', '9876500000', '', ''],
  ],
  intro: '1. Download the template and fill it in (Excel, Google Sheets…), or use your own sheet: columns are found by their '
      'headings (Wing, Flat No, Name, Relationship, Mobile, Date of Birth…), in any order.\n'
      '2. One row per person. Wing and Flat No must match a flat already in the society; only Flat No and Name are required. '
      'Dates are read day first (14/03/1982).\n'
      '3. Relationship decides the type: Son, Daughter, Child… are added as Dependent; Wife, Husband, Father, Mother and '
      'the rest as Family. The flat\'s owners are not added here: use Import Residents for them.\n'
      '4. No app login is made for them: the office can give one later from the Residents list. A name already on the flat '
      'is skipped, so you can import a corrected file again. Each row is checked first and nothing is saved until you press Import.',
);

String _norm(String s) => s.toLowerCase().replaceAll(RegExp(r'[_\-./()]'), ' ').replaceAll(RegExp(r'\s+'), ' ').trim();

/// Which cell of a row holds which field, for one [PeopleImportSpec].
class PeopleImportColumns {
  final PeopleImportSpec spec;
  final Map<String, int> _index;
  const PeopleImportColumns._(this.spec, this._index);

  /// A file with no header row is read by position, as the template lays it out.
  factory PeopleImportColumns.positional(PeopleImportSpec spec) =>
      PeopleImportColumns._(spec, {for (var i = 0; i < spec.keys.length; i++) spec.keys[i]: i});

  /// The columns named by [headerRow], or null when it isn't a header row (it needs every [PeopleImportSpec.required] column).
  static PeopleImportColumns? fromHeader(PeopleImportSpec spec, List<String> headerRow) {
    final found = <String, int>{};
    for (var i = 0; i < headerRow.length; i++) {
      final cell = _norm(headerRow[i]);
      if (cell.isEmpty) continue;
      for (final e in spec.aliases.entries) {
        if (!found.containsKey(e.key) && e.value.map(_norm).contains(cell)) {
          found[e.key] = i;
          break;
        }
      }
    }
    return spec.required.every(found.containsKey) ? PeopleImportColumns._(spec, found) : null;
  }

  String cell(List<String> row, String key) {
    final i = _index[key];
    return i == null || i >= row.length ? '' : row[i].trim();
  }

  List<String> canonical(List<String> row) => [for (final k in spec.keys) cell(row, k)];
  Map<String, String> fields(List<String> row) => {for (final k in spec.keys) k: cell(row, k)};
}

/// One line of an import, as the server read it.
class PeopleImportOutcome {
  final int? line;
  final String status; // created | skipped | error
  final String? message;
  PeopleImportOutcome.fromJson(Map<String, dynamic> j)
      : line = j['line'] as int?,
        status = j['status'] as String,
        message = j['message'] as String?;
}

class PeopleImportApi {
  final Dio _dio;
  PeopleImportApi({Dio? dio}) : _dio = dio ?? ApiClient.instance;

  /// Rows are maps of the server's import fields (all text); `dryRun` checks them and writes nothing.
  Future<List<PeopleImportOutcome>> importRows(PeopleImportSpec spec, List<Map<String, dynamic>> rows, {required bool dryRun}) async {
    final r = await _dio.post(spec.endpoint,
        data: {'rows': rows, 'dry_run': dryRun}, options: Options(receiveTimeout: const Duration(minutes: 3)));
    return [for (final o in r.data as List) PeopleImportOutcome.fromJson(Map<String, dynamic>.from(o as Map))];
  }
}
