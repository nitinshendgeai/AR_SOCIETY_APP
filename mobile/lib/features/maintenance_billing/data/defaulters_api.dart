import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:ar_society_app/core/api/api_client.dart';

double _num(Object? v) => double.tryParse(v?.toString() ?? '') ?? 0;
DateTime? _date(Object? v) => v == null ? null : DateTime.parse(v as String);

/// Age buckets, oldest last (backend AGE_BUCKETS).
const kDuesBuckets = <String, String>{
  'not_due': 'Not yet due',
  'upto_3': 'Up to 3 months',
  'm3_6': '3–6 months',
  'm6_12': '6–12 months',
  'over_12': 'Over 1 year',
};

class UnpaidBill {
  final String billId;
  final String invoiceNumber;
  final String period;
  final DateTime billDate;
  final DateTime dueDate;
  final double outstanding;
  final int daysOverdue;
  final String bucket;

  const UnpaidBill({
    required this.billId,
    required this.invoiceNumber,
    required this.period,
    required this.billDate,
    required this.dueDate,
    required this.outstanding,
    required this.daysOverdue,
    required this.bucket,
  });

  factory UnpaidBill.fromJson(Map<String, dynamic> j) => UnpaidBill(
        billId: j['bill_id'] as String,
        invoiceNumber: j['invoice_number'] as String,
        period: j['period'] as String? ?? '',
        billDate: _date(j['bill_date'])!,
        dueDate: _date(j['due_date'])!,
        outstanding: _num(j['outstanding']),
        daysOverdue: (j['days_overdue'] as num?)?.toInt() ?? 0,
        bucket: j['bucket'] as String? ?? 'not_due',
      );
}

/// One flat's maintenance dues, aged from the bills' due dates.
class FlatDues {
  final String flatId;
  final String flatLabel;
  final String memberName;
  final String? phone;
  final double total;
  final double inDefault;
  final bool isDefaulter;
  final Map<String, double> buckets;
  final DateTime oldestDueDate;
  final int daysOverdue;
  final int unpaidBills;
  final double onAccount;
  final DateTime? lastPaymentDate;
  final double? lastPaymentAmount;
  final DateTime? lastRemindedAt;
  final List<UnpaidBill> bills;

  const FlatDues({
    required this.flatId,
    required this.flatLabel,
    required this.memberName,
    this.phone,
    required this.total,
    required this.inDefault,
    required this.isDefaulter,
    required this.buckets,
    required this.oldestDueDate,
    required this.daysOverdue,
    required this.unpaidBills,
    required this.onAccount,
    this.lastPaymentDate,
    this.lastPaymentAmount,
    this.lastRemindedAt,
    required this.bills,
  });

  factory FlatDues.fromJson(Map<String, dynamic> j) => FlatDues(
        flatId: j['flat_id'] as String,
        flatLabel: j['flat_label'] as String? ?? '—',
        memberName: j['member_name'] as String? ?? '—',
        phone: j['phone'] as String?,
        total: _num(j['total']),
        inDefault: _num(j['in_default']),
        isDefaulter: j['is_defaulter'] as bool? ?? false,
        buckets: (j['buckets'] as Map<String, dynamic>? ?? const {}).map((k, v) => MapEntry(k, _num(v))),
        oldestDueDate: _date(j['oldest_due_date'])!,
        daysOverdue: (j['days_overdue'] as num?)?.toInt() ?? 0,
        unpaidBills: (j['unpaid_bills'] as num?)?.toInt() ?? 0,
        onAccount: _num(j['on_account']),
        lastPaymentDate: _date(j['last_payment_date']),
        lastPaymentAmount: j['last_payment_amount'] == null ? null : _num(j['last_payment_amount']),
        lastRemindedAt: j['last_reminded_at'] == null ? null : DateTime.parse(j['last_reminded_at'] as String),
        bills: (j['bills'] as List? ?? const []).map((e) => UnpaidBill.fromJson(e as Map<String, dynamic>)).toList(),
      );

  /// The bucket of the oldest dues — how far behind the member is.
  String get worstBucket {
    for (final k in kDuesBuckets.keys.toList().reversed) {
      if ((buckets[k] ?? 0) > 0) return k;
    }
    return 'not_due';
  }
}

class DuesSummary {
  final DateTime asOf;
  final int minMonths;
  final int flatsWithDues;
  final double totalOutstanding;
  final int defaulters;
  final double defaultersOutstanding;
  final double inDefault;
  final Map<String, double> buckets;
  final double? interestRatePct;

  const DuesSummary({
    required this.asOf,
    required this.minMonths,
    required this.flatsWithDues,
    required this.totalOutstanding,
    required this.defaulters,
    required this.defaultersOutstanding,
    required this.inDefault,
    required this.buckets,
    this.interestRatePct,
  });

  factory DuesSummary.fromJson(Map<String, dynamic> j) => DuesSummary(
        asOf: _date(j['as_of'])!,
        minMonths: (j['min_months'] as num?)?.toInt() ?? 3,
        flatsWithDues: (j['flats_with_dues'] as num?)?.toInt() ?? 0,
        totalOutstanding: _num(j['total_outstanding']),
        defaulters: (j['defaulters'] as num?)?.toInt() ?? 0,
        defaultersOutstanding: _num(j['defaulters_outstanding']),
        inDefault: _num(j['in_default']),
        buckets: {
          for (final b in (j['buckets'] as List? ?? const []))
            (b as Map<String, dynamic>)['key'] as String: _num(b['amount']),
        },
        interestRatePct: j['interest_rate_pct'] == null ? null : _num(j['interest_rate_pct']),
      );
}

class DefaultersReport {
  final DuesSummary summary;
  final List<FlatDues> flats;
  const DefaultersReport({required this.summary, required this.flats});

  factory DefaultersReport.fromJson(Map<String, dynamic> j) => DefaultersReport(
        summary: DuesSummary.fromJson(j['summary'] as Map<String, dynamic>),
        flats: (j['flats'] as List).map((e) => FlatDues.fromJson(e as Map<String, dynamic>)).toList(),
      );
}

class ReminderResult {
  final int flatsReminded;
  final int notifications;
  final List<String> flatsWithoutLogin;
  const ReminderResult(this.flatsReminded, this.notifications, this.flatsWithoutLogin);
}

/// FastAPI /billing/defaulters/*.
class DefaultersApi {
  final Dio _dio;
  DefaultersApi({Dio? dio}) : _dio = dio ?? ApiClient.instance;

  Future<DefaultersReport> report(String societyId, {int minMonths = 3, bool includeAll = false}) async {
    final r = await _dio.get('/billing/defaulters/$societyId',
        queryParameters: {'min_months': minMonths, 'include_all': includeAll});
    return DefaultersReport.fromJson(r.data as Map<String, dynamic>);
  }

  Future<Uint8List> pdf(String societyId, {int minMonths = 3, bool includeAll = false}) async {
    final r = await _dio.get<List<int>>('/billing/defaulters/$societyId',
        queryParameters: {'min_months': minMonths, 'include_all': includeAll, 'format': 'pdf'},
        options: Options(responseType: ResponseType.bytes));
    return Uint8List.fromList(r.data!);
  }

  /// [flatIds] null: every defaulter.
  Future<ReminderResult> remind(String societyId, {List<String>? flatIds, int minMonths = 3}) async {
    final r = await _dio.post('/billing/defaulters/$societyId/remind', data: {
      if (flatIds != null) 'flat_ids': flatIds,
      'min_months': minMonths,
    });
    final j = r.data as Map<String, dynamic>;
    return ReminderResult(
      (j['flats_reminded'] as num?)?.toInt() ?? 0,
      (j['notifications'] as num?)?.toInt() ?? 0,
      (j['flats_without_app_login'] as List? ?? const []).map((e) => e.toString()).toList(),
    );
  }
}
