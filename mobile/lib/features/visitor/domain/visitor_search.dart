import 'package:ar_society_app/features/visitor/domain/entities/visitor_entities.dart';

/// Lower case with everything but letters, digits and Devanagari letters taken out, so "mh 12-ab 1234" and
/// "MH12AB1234", or "A - 101" and "a101", compare equal.
String _squash(String s) => s.toLowerCase().replaceAll(RegExp(r'[^a-z0-9ऀ-ॿ]'), '');

/// The visitors that match [query]: every word of it must be found in the visitor's name, mobile number, flat
/// (as "A-101" or just "101"), vehicle number or purpose. Case, spaces and hyphens do not matter. A blank query
/// returns [visitors] unchanged. The order is kept.
///
/// The pass code is deliberately not searchable: it is a secret the guest reads out at the gate.
List<VisitorEntity> filterVisitors(List<VisitorEntity> visitors, String query) {
  final words = query.trim().split(RegExp(r'\s+')).map(_squash).where((w) => w.isNotEmpty).toList();
  if (words.isEmpty) return visitors;
  bool matches(VisitorEntity v) {
    final fields = <String>[
      _squash(v.name),
      _squash(v.mobile),
      if (v.flatNumber != null) _squash(v.flatNumber!),
      if (v.flatLabel != null) _squash(v.flatLabel!),
      if (v.vehicle != null) _squash(v.vehicle!.vehicleNumber),
      if (v.purpose != null) _squash(v.purpose!),
    ];
    return words.every((w) => fields.any((f) => f.contains(w)));
  }

  return visitors.where(matches).toList();
}
