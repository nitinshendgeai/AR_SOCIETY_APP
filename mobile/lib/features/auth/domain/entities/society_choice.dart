/// One society a person can sign in to or switch to (one login per society).
class SocietyChoice {
  final String? societyId; // null: the platform console
  final String societyName;
  final List<String> roles;
  final bool current;

  const SocietyChoice({this.societyId, required this.societyName, this.roles = const [], this.current = false});

  factory SocietyChoice.fromJson(Map<String, dynamic> j) => SocietyChoice(
        societyId: j['society_id'] as String?,
        societyName: j['society_name'] as String? ?? 'Society',
        roles: (j['roles'] as List<dynamic>? ?? const []).map((e) => e.toString()).toList(),
        current: j['current'] as bool? ?? false,
      );

  /// e.g. "Resident" or "Society Admin, Committee".
  String get roleLabel => roles.join(', ');
}
