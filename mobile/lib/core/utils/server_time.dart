/// Times the server stamps itself (created, checked in, paid, reviewed ...).
///
/// The API sends them as UTC with a trailing `Z`. Read them with [parseStamp]
/// so the app shows each person's own clock; showing the raw UTC digits reads
/// about 5½ hours behind in India. A value without a zone (an older server) is
/// taken to be UTC too.
///
/// Dates a person typed in (due date, expiry, expected arrival) are not
/// stamps — keep reading those with `DateTime.parse` as before.
DateTime parseStamp(String s) {
  final hasZone = s.endsWith('Z') || RegExp(r'[+-]\d{2}:?\d{2}$').hasMatch(s);
  return DateTime.parse(hasZone ? s : '${s}Z').toLocal();
}

DateTime? parseStampOrNull(Object? v) {
  if (v == null) return null;
  final s = v.toString();
  if (s.isEmpty) return null;
  try {
    return parseStamp(s);
  } catch (_) {
    return null;
  }
}
