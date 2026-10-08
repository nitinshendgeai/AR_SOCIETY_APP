import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';

DateTime? _dt(Object? v) => v == null ? null : DateTime.tryParse(v.toString());
double? _num(Object? v) => v == null ? null : double.tryParse(v.toString());

/// "06:00:00" -> TimeOfDay
TimeOfDay? parseTime(Object? v) {
  if (v == null) return null;
  final p = v.toString().split(':');
  if (p.length < 2) return null;
  return TimeOfDay(hour: int.tryParse(p[0]) ?? 0, minute: int.tryParse(p[1]) ?? 0);
}

/// TimeOfDay -> "06:00:00" for the API.
String apiTime(TimeOfDay t) => '${t.hour.toString().padLeft(2, '0')}:${t.minute.toString().padLeft(2, '0')}:00';

/// "6:00 AM"
String timeLabel(TimeOfDay? t) {
  if (t == null) return '';
  final h = t.hourOfPeriod == 0 ? 12 : t.hourOfPeriod;
  return '$h:${t.minute.toString().padLeft(2, '0')} ${t.period == DayPeriod.am ? 'AM' : 'PM'}';
}

String apiDate(DateTime d) => DateFormat('yyyy-MM-dd').format(d);
String dayLabel(DateTime? d) => d == null ? '' : DateFormat('EEE d MMM yyyy').format(d);

String _rupees(double v) => v == v.roundToDouble() ? v.toStringAsFixed(0) : v.toStringAsFixed(2);
String rupees(double? v) => v == null ? '' : '₹${_rupees(v)}';

/// (api value, label, icon)
const kAmenityTypes = <(String, String, IconData)>[
  ('clubhouse', 'Clubhouse', Icons.deck_rounded),
  ('gym', 'Gym', Icons.fitness_center_rounded),
  ('pool', 'Swimming pool', Icons.pool_rounded),
  ('party_hall', 'Party hall', Icons.celebration_rounded),
  ('guest_room', 'Guest room', Icons.hotel_rounded),
  ('sports_court', 'Sports court', Icons.sports_tennis_rounded),
  ('terrace', 'Terrace', Icons.roofing_rounded),
  ('conference', 'Meeting room', Icons.meeting_room_rounded),
  ('other', 'Other', Icons.apartment_rounded),
];
String amenityTypeLabel(String t) => kAmenityTypes.where((e) => e.$1 == t).firstOrNull?.$2 ?? t;
IconData amenityTypeIcon(String t) => kAmenityTypes.where((e) => e.$1 == t).firstOrNull?.$3 ?? Icons.apartment_rounded;

/// (api value, label, hint, kind) where kind is 'int', 'money', 'hours', or 'flag'.
const kRuleKinds = <(String, String, String, String)>[
  ('max_duration_hours', 'Longest booking', 'hours per booking', 'hours'),
  ('max_guests', 'Most people', 'people per booking', 'int'),
  ('max_bookings_per_week', 'Bookings a week', 'per person, per week', 'int'),
  ('max_bookings_per_month', 'Bookings a month', 'per person, per month', 'int'),
  ('min_advance_hours', 'Book at least', 'hours before it starts', 'hours'),
  ('max_advance_days', 'Book at most', 'days ahead', 'int'),
  ('charge_per_hour', 'Charge per hour', '₹ per hour', 'money'),
  ('deposit_required', 'Deposit', '₹ refundable deposit', 'money'),
  ('owners_only', 'Residents only', 'Only registered residents may book', 'flag'),
  ('approval_required', 'Needs approval', 'The committee approves each booking', 'flag'),
];
({String type, String label, String hint, String kind})? ruleKind(String t) {
  final r = kRuleKinds.where((e) => e.$1 == t).firstOrNull;
  return r == null ? null : (type: r.$1, label: r.$2, hint: r.$3, kind: r.$4);
}

/// One line for a rule, e.g. "Longest booking: 3 hours".
String ruleText(AmenityRule r) {
  final k = ruleKind(r.type);
  if (k == null) return r.type;
  if (k.kind == 'flag') return k.hint;
  final v = r.value ?? '';
  final n = double.tryParse(v);
  final one = n == 1;
  final unit = switch (r.type) {
    'max_duration_hours' || 'min_advance_hours' => one ? 'hour' : 'hours',
    'max_guests' => one ? 'person' : 'people',
    'max_advance_days' => one ? 'day ahead' : 'days ahead',
    'max_bookings_per_week' => one ? 'a week' : 'a week',
    'max_bookings_per_month' => 'a month',
    _ => '',
  };
  if (k.kind == 'money') return '${k.label}: ${rupees(n)}${r.type == 'charge_per_hour' ? ' an hour' : ''}';
  return '${k.label}: ${n != null && n == n.roundToDouble() ? n.toStringAsFixed(0) : v} $unit'.trim();
}

Color bookingStatusColor(String s) => switch (s) {
      'approved' => AppTheme.success,
      'pending' => AppTheme.warning,
      'rejected' => AppTheme.error,
      'completed' => AppTheme.primary,
      _ => AppTheme.textSecondary,
    };
String bookingStatusLabel(String s) => switch (s) {
      'approved' => 'Confirmed',
      'pending' => 'Waiting for approval',
      'rejected' => 'Rejected',
      'cancelled' => 'Cancelled',
      'completed' => 'Done',
      _ => s,
    };

class AmenityItem {
  final String id;
  final String name;
  final String type;
  final String? description;
  final String? location;
  final int? capacity;
  final TimeOfDay? open;
  final TimeOfDay? close;
  final bool bookingRequired;
  final bool approvalRequired;
  final bool chargeable;
  final bool active;

  const AmenityItem({
    required this.id,
    required this.name,
    required this.type,
    this.description,
    this.location,
    this.capacity,
    this.open,
    this.close,
    this.bookingRequired = true,
    this.approvalRequired = false,
    this.chargeable = false,
    this.active = true,
  });

  factory AmenityItem.fromJson(Map<String, dynamic> j) => AmenityItem(
        id: j['id'] as String,
        name: j['name'] as String? ?? '',
        type: j['amenity_type'] as String? ?? 'other',
        description: j['description'] as String?,
        location: j['location'] as String?,
        capacity: j['capacity'] as int?,
        open: parseTime(j['open_time']),
        close: parseTime(j['close_time']),
        bookingRequired: j['booking_required'] as bool? ?? true,
        approvalRequired: j['approval_required'] as bool? ?? false,
        chargeable: j['is_chargeable'] as bool? ?? false,
        active: j['is_active'] as bool? ?? true,
      );

  String get hours => open == null || close == null ? 'Open all day' : '${timeLabel(open)} – ${timeLabel(close)}';
}

class AmenityRule {
  final String id;
  final String type;
  final String? value;
  const AmenityRule({required this.id, required this.type, this.value});
  factory AmenityRule.fromJson(Map<String, dynamic> j) =>
      AmenityRule(id: j['id'] as String, type: j['rule_type'] as String, value: j['rule_value'] as String?);
}

class AmenityRate {
  final String id;
  final String label;
  final double? perHour;
  final double? flat;
  final double? deposit;
  final bool isDefault;
  const AmenityRate({required this.id, required this.label, this.perHour, this.flat, this.deposit, this.isDefault = false});
  factory AmenityRate.fromJson(Map<String, dynamic> j) => AmenityRate(
        id: j['id'] as String,
        label: j['label'] as String? ?? '',
        perHour: _num(j['price_per_hour']),
        flat: _num(j['flat_price']),
        deposit: _num(j['deposit_amount']),
        isDefault: j['is_default'] as bool? ?? false,
      );

  String get text => [
        if (flat != null) '${rupees(flat)} per booking',
        if (perHour != null) '${rupees(perHour)} an hour',
        if (deposit != null) '${rupees(deposit)} deposit',
      ].join(' · ');
}

class ClosedDate {
  final String id;
  final DateTime date;
  final String? reason;
  const ClosedDate({required this.id, required this.date, this.reason});
  factory ClosedDate.fromJson(Map<String, dynamic> j) =>
      ClosedDate(id: j['id'] as String, date: _dt(j['blackout_date']) ?? DateTime.now(), reason: j['reason'] as String?);
}

class BookingItem {
  final String id;
  final String amenityId;
  final String amenityName;
  final DateTime date;
  final TimeOfDay start;
  final TimeOfDay end;
  final int guests;
  final String? purpose;
  final String status;
  final String? bookedBy;
  final String? flat;
  final String? approvedBy;
  final String? rejectionReason;
  final String? cancellationReason;
  final double? charge;
  final double? deposit;

  const BookingItem({
    required this.id,
    required this.amenityId,
    required this.amenityName,
    required this.date,
    required this.start,
    required this.end,
    this.guests = 1,
    this.purpose,
    required this.status,
    this.bookedBy,
    this.flat,
    this.approvedBy,
    this.rejectionReason,
    this.cancellationReason,
    this.charge,
    this.deposit,
  });

  factory BookingItem.fromJson(Map<String, dynamic> j) => BookingItem(
        id: j['id'] as String,
        amenityId: j['amenity_id'] as String,
        amenityName: j['amenity_name'] as String? ?? 'Amenity',
        date: _dt(j['booking_date']) ?? DateTime.now(),
        start: parseTime(j['start_time']) ?? const TimeOfDay(hour: 0, minute: 0),
        end: parseTime(j['end_time']) ?? const TimeOfDay(hour: 0, minute: 0),
        guests: j['guest_count'] as int? ?? 1,
        purpose: j['purpose'] as String?,
        status: j['status'] as String? ?? 'pending',
        bookedBy: j['booked_by_name'] as String?,
        flat: j['flat'] as String?,
        approvedBy: j['approved_by_name'] as String?,
        rejectionReason: j['rejection_reason'] as String?,
        cancellationReason: j['cancellation_reason'] as String?,
        charge: _num(j['charge_amount']),
        deposit: _num(j['deposit_amount']),
      );

  String get when => '${dayLabel(date)}, ${timeLabel(start)} – ${timeLabel(end)}';

  /// Starts in the future (in the device's clock), so it can still be cancelled by its booker.
  bool get notStarted => DateTime(date.year, date.month, date.day, start.hour, start.minute).isAfter(DateTime.now());
  bool get isLive => status == 'pending' || status == 'approved';
}

class DaySlot {
  final TimeOfDay start;
  final TimeOfDay end;
  final String status;
  final bool mine;
  final String? who;
  final String? flat;
  const DaySlot({required this.start, required this.end, required this.status, this.mine = false, this.who, this.flat});
}

class DayView {
  final TimeOfDay? open;
  final TimeOfDay? close;
  final bool closed;
  final String? closedReason;
  final List<DaySlot> taken;
  const DayView({this.open, this.close, this.closed = false, this.closedReason, this.taken = const []});

  factory DayView.fromJson(Map<String, dynamic> j) => DayView(
        open: parseTime(j['open_time']),
        close: parseTime(j['close_time']),
        closed: j['closed'] as bool? ?? false,
        closedReason: j['closed_reason'] as String?,
        taken: [
          for (final b in (j['bookings'] as List? ?? const []))
            DaySlot(
              start: parseTime(b['start_time'])!,
              end: parseTime(b['end_time'])!,
              status: b['status'] as String? ?? 'approved',
              mine: b['mine'] as bool? ?? false,
              who: b['booked_by_name'] as String?,
              flat: b['flat'] as String?,
            ),
        ],
      );
}

class AmenitiesApi {
  final Dio _dio;
  AmenitiesApi({Dio? dio}) : _dio = dio ?? ApiClient.instance;

  List<T> _list<T>(Response r, T Function(Map<String, dynamic>) f) =>
      (r.data as List).map((e) => f(e as Map<String, dynamic>)).toList();

  Future<List<AmenityItem>> amenities(String societyId, {bool includeClosed = false}) async =>
      _list(await _dio.get('/amenities/society/$societyId', queryParameters: {'include_closed': includeClosed}), AmenityItem.fromJson);

  Future<AmenityItem> amenity(String id) async =>
      AmenityItem.fromJson((await _dio.get('/amenities/$id')).data as Map<String, dynamic>);

  Future<AmenityItem> create(Map<String, dynamic> body) async =>
      AmenityItem.fromJson((await _dio.post('/amenities/', data: body)).data as Map<String, dynamic>);

  Future<AmenityItem> update(String id, Map<String, dynamic> body) async =>
      AmenityItem.fromJson((await _dio.patch('/amenities/$id', data: body)).data as Map<String, dynamic>);

  Future<List<AmenityRule>> rules(String id) async => _list(await _dio.get('/amenities/$id/rules'), AmenityRule.fromJson);
  Future<void> setRule(String id, String type, String? value) =>
      _dio.post('/amenities/$id/rules', data: {'rule_type': type, if (value != null) 'rule_value': value});
  Future<void> deleteRule(String ruleId) => _dio.delete('/amenities/rules/$ruleId');

  Future<List<AmenityRate>> rates(String id) async => _list(await _dio.get('/amenities/$id/pricing'), AmenityRate.fromJson);
  Future<void> addRate(String id, Map<String, dynamic> body) => _dio.post('/amenities/$id/pricing', data: body);
  Future<void> deleteRate(String rateId) => _dio.delete('/amenities/pricing/$rateId');

  Future<List<ClosedDate>> closedDates(String id) async => _list(await _dio.get('/amenities/$id/blackouts'), ClosedDate.fromJson);
  Future<void> closeDate(String id, DateTime d, String? reason) =>
      _dio.post('/amenities/$id/blackouts', data: {'blackout_date': apiDate(d), if (reason != null && reason.isNotEmpty) 'reason': reason});
  Future<void> reopenDate(String closedId) => _dio.delete('/amenities/blackouts/$closedId');

  Future<DayView> day(String id, DateTime d) async =>
      DayView.fromJson((await _dio.get('/amenities/$id/day', queryParameters: {'for_date': apiDate(d)})).data as Map<String, dynamic>);

  Future<BookingItem> book(Map<String, dynamic> body) async =>
      BookingItem.fromJson((await _dio.post('/amenities/bookings', data: body)).data as Map<String, dynamic>);

  Future<List<BookingItem>> mine() async => _list(await _dio.get('/amenities/bookings/me/list', queryParameters: {'limit': 100}), BookingItem.fromJson);

  Future<List<BookingItem>> pending(String societyId) async =>
      _list(await _dio.get('/amenities/bookings/society/$societyId/pending'), BookingItem.fromJson);

  Future<List<BookingItem>> all(String societyId, {String? status, String? amenityId}) async => _list(
      await _dio.get('/amenities/bookings/society/$societyId', queryParameters: {
        'limit': 200,
        if (status != null) 'status': status,
        if (amenityId != null) 'amenity_id': amenityId,
      }),
      BookingItem.fromJson);

  Future<BookingItem> approve(String id) async =>
      BookingItem.fromJson((await _dio.post('/amenities/bookings/$id/approve', data: {})).data as Map<String, dynamic>);
  Future<BookingItem> reject(String id, String reason) async =>
      BookingItem.fromJson((await _dio.post('/amenities/bookings/$id/reject', data: {'reason': reason})).data as Map<String, dynamic>);
  Future<BookingItem> cancel(String id, {String? reason}) async => BookingItem.fromJson(
      (await _dio.post('/amenities/bookings/$id/cancel', data: {if (reason != null && reason.isNotEmpty) 'reason': reason})).data
          as Map<String, dynamic>);
  Future<BookingItem> complete(String id, {bool damage = false, String? notes}) async => BookingItem.fromJson(
      (await _dio.post('/amenities/bookings/$id/complete', data: {'damage_noted': damage, if (notes != null && notes.isNotEmpty) 'damage_notes': notes})).data
          as Map<String, dynamic>);
}
