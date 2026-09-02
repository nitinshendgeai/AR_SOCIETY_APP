/// Auto-generated flat number for the Nth unit on [floor] — unique within a
/// wing since the backend's assert_unique_flat_number scopes uniqueness per
/// wing (not per floor), and the floor digit(s) are always part of the
/// string: floor 1 unit 3 -> "103", ground (0) unit 1 -> "G01", basement -1
/// unit 1 -> "B101".
String autoFlatNumber(int floor, int unit) {
  final unitStr = unit.toString().padLeft(2, '0');
  if (floor == 0) return 'G$unitStr';
  if (floor < 0) return 'B${-floor}$unitStr';
  return '$floor$unitStr';
}

/// [count] flat numbers for [floor] that aren't already in [existing] —
/// skips any unit index whose generated number collides with a
/// manually-added flat already on that floor, rather than stopping at the
/// first collision.
List<String> nextFlatNumbers(int floor, int count, Set<String> existing) {
  final result = <String>[];
  var unit = 1;
  while (result.length < count && unit < 10000) {
    final candidate = autoFlatNumber(floor, unit);
    if (!existing.contains(candidate)) result.add(candidate);
    unit++;
  }
  return result;
}
