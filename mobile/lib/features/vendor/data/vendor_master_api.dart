import 'dart:convert';
import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/api/api_client.dart';

// ── Importing the vendor master from Excel / CSV ─────────────────────────────

/// One column of the file and the vendor field it is read into (null: not imported).
class VendorImportColumn {
  final int index;
  final String heading;
  final String? field;
  final String? sample;
  const VendorImportColumn({required this.index, required this.heading, this.field, this.sample});

  factory VendorImportColumn.fromJson(Map<String, dynamic> j) => VendorImportColumn(
        index: (j['index'] as num).toInt(),
        heading: j['heading'] as String? ?? '',
        field: j['field'] as String?,
        sample: j['sample'] as String?,
      );
}

class VendorImportRow {
  final int line;
  final String status; // ready | created | duplicate | error
  final String? name;
  final String? constitutionLabel;
  final String? tdsSection;
  final String? message;
  const VendorImportRow(
      {required this.line, required this.status, this.name, this.constitutionLabel, this.tdsSection, this.message});

  factory VendorImportRow.fromJson(Map<String, dynamic> j) => VendorImportRow(
        line: (j['line'] as num).toInt(),
        status: j['status'] as String? ?? 'error',
        name: j['name'] as String?,
        constitutionLabel: j['constitution_label'] as String?,
        tdsSection: j['tds_section'] as String?,
        message: j['message'] as String?,
      );
}

class VendorImportResult {
  final bool dryRun;
  final String fileName;
  final String sheet;
  final int totalRows;
  final List<VendorImportColumn> columns;
  final List<(String, String)> fields; // (field, label): everything a column can be pointed at
  final int ready;
  final int created;
  final int duplicates;
  final int errors;
  final String? message;
  final List<VendorImportRow> rows;
  const VendorImportResult({
    required this.dryRun,
    required this.fileName,
    required this.sheet,
    required this.totalRows,
    required this.columns,
    required this.fields,
    this.ready = 0,
    this.created = 0,
    this.duplicates = 0,
    this.errors = 0,
    this.message,
    this.rows = const [],
  });

  factory VendorImportResult.fromJson(Map<String, dynamic> j) => VendorImportResult(
        dryRun: j['dry_run'] as bool? ?? true,
        fileName: j['file_name'] as String? ?? '',
        sheet: j['sheet'] as String? ?? '',
        totalRows: (j['total_rows'] as num?)?.toInt() ?? 0,
        columns: [
          for (final c in (j['columns'] as List? ?? const [])) VendorImportColumn.fromJson(c as Map<String, dynamic>)
        ],
        fields: [
          for (final f in (j['fields'] as List? ?? const []))
            ((f as Map<String, dynamic>)['field'] as String, f['label'] as String),
        ],
        ready: (j['ready'] as num?)?.toInt() ?? 0,
        created: (j['created'] as num?)?.toInt() ?? 0,
        duplicates: (j['duplicates'] as num?)?.toInt() ?? 0,
        errors: (j['errors'] as num?)?.toInt() ?? 0,
        message: j['message'] as String?,
        rows: [for (final r in (j['rows'] as List? ?? const [])) VendorImportRow.fromJson(r as Map<String, dynamic>)],
      );
}

// ── TDS review ───────────────────────────────────────────────────────────────

class TdsIssue {
  final String code; // no_type | pan_mismatch | no_section | no_pan
  final String message;
  const TdsIssue(this.code, this.message);
}

/// One vendor's TDS setup, what is wrong with it, and the fix that can be worked out.
class TdsReviewRow {
  final String id;
  final String vendorCode;
  final String name;
  final String? pan;
  final String? constitution;
  final String? constitutionLabel;
  final String? section;
  final String? sectionLabel;
  final List<TdsIssue> issues;
  final String? suggestedConstitution;
  final String? suggestedConstitutionLabel;
  final String? suggestedSection;
  final String? suggestedSectionLabel;
  final bool canFix;
  const TdsReviewRow({
    required this.id,
    required this.vendorCode,
    required this.name,
    this.pan,
    this.constitution,
    this.constitutionLabel,
    this.section,
    this.sectionLabel,
    this.issues = const [],
    this.suggestedConstitution,
    this.suggestedConstitutionLabel,
    this.suggestedSection,
    this.suggestedSectionLabel,
    this.canFix = false,
  });

  factory TdsReviewRow.fromJson(Map<String, dynamic> j) => TdsReviewRow(
        id: j['id'] as String,
        vendorCode: j['vendor_code'] as String? ?? '',
        name: j['company_name'] as String? ?? '',
        pan: j['pan_number'] as String?,
        constitution: j['constitution'] as String?,
        constitutionLabel: j['constitution_label'] as String?,
        section: j['tds_section'] as String?,
        sectionLabel: j['tds_section_label'] as String?,
        issues: [
          for (final i in (j['issues'] as List? ?? const []))
            TdsIssue((i as Map<String, dynamic>)['code'] as String, i['message'] as String)
        ],
        suggestedConstitution: j['suggested_constitution'] as String?,
        suggestedConstitutionLabel: j['suggested_constitution_label'] as String?,
        suggestedSection: j['suggested_section'] as String?,
        suggestedSectionLabel: j['suggested_section_label'] as String?,
        canFix: j['can_fix'] as bool? ?? false,
      );

  bool get hasIssues => issues.isNotEmpty;
}

class TdsReview {
  final int total;
  final int withIssues;
  final int fixable;
  final List<TdsReviewRow> vendors;
  const TdsReview({this.total = 0, this.withIssues = 0, this.fixable = 0, this.vendors = const []});

  factory TdsReview.fromJson(Map<String, dynamic> j) => TdsReview(
        total: (j['total'] as num?)?.toInt() ?? 0,
        withIssues: (j['with_issues'] as num?)?.toInt() ?? 0,
        fixable: (j['fixable'] as num?)?.toInt() ?? 0,
        vendors: [for (final v in (j['vendors'] as List? ?? const [])) TdsReviewRow.fromJson(v as Map<String, dynamic>)],
      );
}

class TdsFixResult {
  final int fixed;
  final List<String> failed; // "Vendor: why"
  const TdsFixResult(this.fixed, this.failed);

  factory TdsFixResult.fromJson(Map<String, dynamic> j) => TdsFixResult(
        (j['fixed'] as List? ?? const []).length,
        [
          for (final f in (j['failed'] as List? ?? const []))
            '${(f as Map<String, dynamic>)['company_name']}: ${f['message']}'
        ],
      );
}

// ── TDS rates and the register of what was deducted ──────────────────────────

/// One rate-and-limit row: the percentage deducted for a section and kind of payee, with the yearly and
/// single-payment limits under which nothing is deducted.
class TdsRule {
  final String id;
  final String code;
  final String name;
  final String section;
  final String payeeClass; // individual_huf | other | any
  final String rate;
  final String? yearlyLimit;
  final String? singleLimit;
  final DateTime? effectiveFrom;
  final DateTime? effectiveTo;
  final bool active;
  final String? notes;
  const TdsRule({
    required this.id,
    required this.code,
    required this.name,
    required this.section,
    required this.payeeClass,
    required this.rate,
    this.yearlyLimit,
    this.singleLimit,
    this.effectiveFrom,
    this.effectiveTo,
    this.active = true,
    this.notes,
  });

  factory TdsRule.fromJson(Map<String, dynamic> j) => TdsRule(
        id: j['id'] as String,
        code: j['code'] as String? ?? '',
        name: j['name'] as String? ?? '',
        section: j['section'] as String? ?? '',
        payeeClass: j['payee_class'] as String? ?? 'any',
        rate: '${j['rate']}',
        yearlyLimit: j['yearly_limit'] as String?,
        singleLimit: j['single_limit'] as String?,
        effectiveFrom: DateTime.tryParse('${j['effective_from'] ?? ''}'),
        effectiveTo: DateTime.tryParse('${j['effective_to'] ?? ''}'),
        active: j['is_active'] as bool? ?? true,
        notes: j['notes'] as String?,
      );

  String get payeeLabel => switch (payeeClass) {
        'individual_huf' => 'Individual / HUF',
        'other' => 'Firm, LLP, company, other',
        _ => 'Everyone',
      };

  /// "2" for 2.0000, "0.5" for 0.5000.
  String get rateText {
    final d = double.tryParse(rate) ?? 0;
    return d == d.roundToDouble() ? d.toStringAsFixed(0) : d.toString();
  }
}

/// One TDS deduction on a vendor payment, with the date it is due to be deposited.
class TdsRegisterRow {
  final String paymentNumber;
  final DateTime date;
  final String vendor;
  final String? pan;
  final String? constitution;
  final String? sectionLabel;
  final String amountSettled;
  final String base;
  final String rate;
  final String tds;
  final String netPaid;
  final DateTime? depositDue;
  final String? note;
  const TdsRegisterRow({
    required this.paymentNumber,
    required this.date,
    required this.vendor,
    this.pan,
    this.constitution,
    this.sectionLabel,
    required this.amountSettled,
    required this.base,
    required this.rate,
    required this.tds,
    required this.netPaid,
    this.depositDue,
    this.note,
  });

  factory TdsRegisterRow.fromJson(Map<String, dynamic> j) => TdsRegisterRow(
        paymentNumber: j['payment_number'] as String? ?? '',
        date: DateTime.parse(j['payment_date'] as String),
        vendor: j['vendor'] as String? ?? '',
        pan: j['pan'] as String?,
        constitution: j['constitution'] as String?,
        sectionLabel: j['section_label'] as String?,
        amountSettled: '${j['amount_settled']}',
        base: '${j['tds_base']}',
        rate: '${j['rate']}',
        tds: '${j['tds_amount']}',
        netPaid: '${j['net_paid']}',
        depositDue: DateTime.tryParse('${j['deposit_due'] ?? ''}'),
        note: j['note'] as String?,
      );
}

class TdsRegister {
  final List<TdsRegisterRow> rows;
  final String total;
  const TdsRegister({this.rows = const [], this.total = '0'});

  factory TdsRegister.fromJson(Map<String, dynamic> j) => TdsRegister(
        rows: [for (final r in (j['rows'] as List? ?? const [])) TdsRegisterRow.fromJson(r as Map<String, dynamic>)],
        total: '${j['total_tds'] ?? 0}',
      );
}

typedef TdsRegisterRange = ({String societyId, DateTime from, DateTime to});

class VendorMasterApi {
  final Dio _dio;
  VendorMasterApi({Dio? dio}) : _dio = dio ?? ApiClient.instance;

  /// Reads an Excel (.xlsx) or CSV master. With [dryRun] nothing is saved: every row is checked and the result says
  /// what would happen. [mapping] ({column heading: field or null}) overrides the automatic column match.
  Future<VendorImportResult> importFile(
    String societyId,
    Uint8List bytes,
    String fileName, {
    required bool dryRun,
    Map<String, String?>? mapping,
  }) async {
    final res = await _dio.post(
      '/vendors/import/$societyId',
      data: FormData.fromMap({
        'file': MultipartFile.fromBytes(bytes, filename: fileName),
        'dry_run': dryRun.toString(),
        if (mapping != null) 'mapping': jsonEncode(mapping),
      }),
      options: Options(receiveTimeout: const Duration(minutes: 2), sendTimeout: const Duration(minutes: 2)),
    );
    return VendorImportResult.fromJson(res.data as Map<String, dynamic>);
  }

  Future<Uint8List> importTemplate() async {
    final res = await _dio.get<List<int>>('/vendors/import-template', options: Options(responseType: ResponseType.bytes));
    return Uint8List.fromList(res.data!);
  }

  Future<List<TdsRule>> tdsRules(String societyId) async => [
        for (final r in (await _dio.get('/vendors/tds/rules/$societyId')).data as List) TdsRule.fromJson(r as Map<String, dynamic>)
      ];

  /// Correct a rate or limit. A null limit means no limit.
  Future<void> updateTdsRule(String id,
          {required String rate, String? yearlyLimit, String? singleLimit, required bool active}) =>
      _dio.patch('/vendors/tds/rules/$id',
          data: {'rate': rate, 'yearly_limit': yearlyLimit, 'single_limit': singleLimit, 'is_active': active});

  Future<TdsRegister> tdsRegister(String societyId, DateTime from, DateTime to) async => TdsRegister.fromJson((await _dio
          .get('/vendors/tds/register/$societyId', queryParameters: {'from_date': _day(from), 'to_date': _day(to)}))
      .data as Map<String, dynamic>);

  static String _day(DateTime d) =>
      '${d.year.toString().padLeft(4, '0')}-${d.month.toString().padLeft(2, '0')}-${d.day.toString().padLeft(2, '0')}';

  Future<TdsReview> tdsReview(String societyId) async =>
      TdsReview.fromJson((await _dio.get('/vendors/society/$societyId/tds-review')).data as Map<String, dynamic>);

  /// Fix vendors' type and section: the [items] given, and with [useSuggestions] every vendor whose fix can be
  /// worked out.
  Future<TdsFixResult> applyTdsFixes(String societyId,
          {List<({String vendorId, String? constitution, String? section})> items = const [],
          bool useSuggestions = false}) async =>
      TdsFixResult.fromJson((await _dio.post('/vendors/society/$societyId/tds-review/apply', data: {
        'use_suggestions': useSuggestions,
        'items': [
          for (final i in items)
            {
              'vendor_id': i.vendorId,
              if (i.constitution != null) 'constitution': i.constitution,
              if (i.section != null) 'tds_section': i.section,
            }
        ],
      })).data as Map<String, dynamic>);
}

final vendorMasterApiProvider = Provider<VendorMasterApi>((_) => VendorMasterApi());

final tdsReviewProvider = FutureProvider.autoDispose.family<TdsReview, String>(
  (ref, societyId) => ref.watch(vendorMasterApiProvider).tdsReview(societyId),
);

final tdsRulesProvider = FutureProvider.autoDispose.family<List<TdsRule>, String>(
  (ref, societyId) => ref.watch(vendorMasterApiProvider).tdsRules(societyId),
);

final tdsRegisterProvider = FutureProvider.autoDispose.family<TdsRegister, TdsRegisterRange>(
  (ref, k) => ref.watch(vendorMasterApiProvider).tdsRegister(k.societyId, k.from, k.to),
);
