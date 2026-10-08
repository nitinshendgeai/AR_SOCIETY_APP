import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ar_society_app/features/amenities/data/amenities_api.dart';

void main() {
  test('times are read from and written to the API in 24-hour form and shown in 12-hour form', () {
    final t = parseTime('18:30:00')!;
    expect(t, const TimeOfDay(hour: 18, minute: 30));
    expect(apiTime(t), '18:30:00');
    expect(timeLabel(t), '6:30 PM');
    expect(timeLabel(const TimeOfDay(hour: 0, minute: 5)), '12:05 AM');
    expect(timeLabel(const TimeOfDay(hour: 12, minute: 0)), '12:00 PM');
  });

  test('an amenity states its hours, and open-all-day when it has none', () {
    final a = AmenityItem.fromJson({
      'id': 'a1', 'name': 'Clubhouse', 'amenity_type': 'clubhouse', 'open_time': '06:00:00', 'close_time': '22:00:00',
      'capacity': 40, 'booking_required': true, 'approval_required': true, 'is_chargeable': false, 'is_active': true,
    });
    expect(a.hours, '6:00 AM – 10:00 PM');
    expect(a.approvalRequired, isTrue);
    expect(amenityTypeLabel(a.type), 'Clubhouse');
    expect(AmenityItem.fromJson({'id': 'a2', 'name': 'Garden', 'amenity_type': 'other'}).hours, 'Open all day');
  });

  test('rules read as plain sentences', () {
    expect(ruleText(const AmenityRule(id: 'r', type: 'max_duration_hours', value: '3')), 'Longest booking: 3 hours');
    expect(ruleText(const AmenityRule(id: 'r', type: 'max_duration_hours', value: '1.5')), 'Longest booking: 1.5 hours');
    expect(ruleText(const AmenityRule(id: 'r', type: 'max_guests', value: '1')), 'Most people: 1 person');
    expect(ruleText(const AmenityRule(id: 'r', type: 'max_advance_days', value: '30')), 'Book at most: 30 days ahead');
    expect(ruleText(const AmenityRule(id: 'r', type: 'charge_per_hour', value: '250')), 'Charge per hour: ₹250 an hour');
    expect(ruleText(const AmenityRule(id: 'r', type: 'owners_only')), 'Only registered residents may book');
  });

  test('a rate lists its prices', () {
    final r = AmenityRate.fromJson({'id': 'p', 'label': 'Std', 'flat_price': 800, 'deposit_amount': 500.5, 'is_default': true});
    expect(r.text, '₹800 per booking · ₹500.50 deposit');
    expect(r.isDefault, isTrue);
  });

  test('a booking carries who, which flat and what it costs; one in the past cannot be cancelled by its booker', () {
    final tomorrow = DateTime.now().add(const Duration(days: 1));
    final past = DateTime.now().subtract(const Duration(days: 1));
    String d(DateTime x) => '${x.year}-${x.month.toString().padLeft(2, '0')}-${x.day.toString().padLeft(2, '0')}';
    BookingItem make(String date) => BookingItem.fromJson({
          'id': 'b', 'amenity_id': 'a', 'amenity_name': 'Hall', 'booking_date': date, 'start_time': '10:00:00', 'end_time': '12:00:00',
          'guest_count': 4, 'status': 'approved', 'booked_by_name': 'Rohan', 'flat': 'A / 101', 'charge_amount': 625.0,
        });
    final b = make(d(tomorrow));
    expect(b.flat, 'A / 101');
    expect(b.charge, 625.0);
    expect(b.notStarted, isTrue);
    expect(b.isLive, isTrue);
    expect(make(d(past)).notStarted, isFalse);
    expect(bookingStatusLabel('pending'), 'Waiting for approval');
  });

  test('the day view lists the taken times and whether the day is closed', () {
    final v = DayView.fromJson({
      'open_time': '06:00:00', 'close_time': '22:00:00', 'closed': false,
      'bookings': [
        {'id': 'x', 'start_time': '10:00:00', 'end_time': '12:00:00', 'status': 'approved', 'mine': true},
        {'id': 'y', 'start_time': '14:00:00', 'end_time': '15:00:00', 'status': 'pending', 'mine': false, 'booked_by_name': 'Ravi', 'flat': 'B / 2'},
      ],
    });
    expect(v.taken.length, 2);
    expect(v.taken.first.mine, isTrue);
    expect(v.taken.last.who, 'Ravi');
    final closed = DayView.fromJson({'closed': true, 'closed_reason': 'Painting', 'bookings': []});
    expect(closed.closed, isTrue);
    expect(closed.closedReason, 'Painting');
  });
}
