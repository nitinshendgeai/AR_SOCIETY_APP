/// A device signed in to the account, as GET /auth/sessions returns it.
class DeviceSession {
  final String id;
  final String device;
  final String? ipAddress;
  final DateTime signedInAt;
  final DateTime? lastSeenAt;

  /// True for the device that is asking.
  final bool current;

  const DeviceSession({
    required this.id,
    required this.device,
    this.ipAddress,
    required this.signedInAt,
    this.lastSeenAt,
    required this.current,
  });

  factory DeviceSession.fromJson(Map<String, dynamic> j) => DeviceSession(
        id: j['id'] as String,
        device: (j['device'] as String?)?.trim().isNotEmpty == true ? j['device'] as String : 'Unknown device',
        ipAddress: j['ip_address'] as String?,
        // The server sends UTC without a zone marker.
        signedInAt: DateTime.parse('${j['signed_in_at']}${_z(j['signed_in_at'])}').toLocal(),
        lastSeenAt: j['last_seen_at'] == null
            ? null
            : DateTime.parse('${j['last_seen_at']}${_z(j['last_seen_at'])}').toLocal(),
        current: j['current'] as bool? ?? false,
      );

  static String _z(dynamic v) {
    final s = '$v';
    return s.endsWith('Z') || s.contains('+') ? '' : 'Z';
  }
}

/// "just now", "5 minutes ago", "3 hours ago", "yesterday", "12 Oct".
String sinceLabel(DateTime? when, {DateTime? now}) {
  if (when == null) return '';
  final diff = (now ?? DateTime.now()).difference(when);
  if (diff.inMinutes < 1) return 'just now';
  if (diff.inMinutes < 60) return '${diff.inMinutes} minute${diff.inMinutes == 1 ? '' : 's'} ago';
  if (diff.inHours < 24) return '${diff.inHours} hour${diff.inHours == 1 ? '' : 's'} ago';
  if (diff.inDays == 1) return 'yesterday';
  if (diff.inDays < 7) return '${diff.inDays} days ago';
  const m = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  return '${when.day} ${m[when.month - 1]}';
}
