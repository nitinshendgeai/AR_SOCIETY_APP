import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/api/api_client.dart';

class TrialStatus {
  final String accountStatus;
  final bool isTrial;
  final int trialDaysRemaining;
  final bool trialExpired;
  final bool expiryWarning;
  final bool expiryCritical;
  final bool setupCompleted;
  final int setupCompletionPercentage;

  const TrialStatus({
    required this.accountStatus,
    required this.isTrial,
    required this.trialDaysRemaining,
    required this.trialExpired,
    required this.expiryWarning,
    required this.expiryCritical,
    required this.setupCompleted,
    required this.setupCompletionPercentage,
  });

  factory TrialStatus.fromJson(Map<String, dynamic> json) => TrialStatus(
        accountStatus: json['account_status'] as String? ?? 'active',
        isTrial: json['is_trial'] as bool? ?? false,
        trialDaysRemaining: json['trial_days_remaining'] as int? ?? 0,
        trialExpired: json['trial_expired'] as bool? ?? false,
        expiryWarning: json['expiry_warning'] as bool? ?? false,
        expiryCritical: json['expiry_critical'] as bool? ?? false,
        setupCompleted: json['setup_completed'] as bool? ?? false,
        setupCompletionPercentage:
            json['setup_completion_percentage'] as int? ?? 0,
      );
}

/// Fetches trial/subscription status for a society.
/// Keyed by societyId so multiple societies can be cached independently.
final trialStatusProvider =
    FutureProvider.autoDispose.family<TrialStatus, String>((ref, societyId) async {
  final response = await ApiClient.instance.get(
    '/societies/$societyId/trial-status',
  );
  return TrialStatus.fromJson(response.data as Map<String, dynamic>);
});

// ── Society info ───────────────────────────────────────────────────────────────

class SocietyInfo {
  final String id;
  final String name;
  final String? societyCode;
  final int? totalFlats;
  final int? totalWings;

  const SocietyInfo({
    required this.id,
    required this.name,
    this.societyCode,
    this.totalFlats,
    this.totalWings,
  });

  factory SocietyInfo.fromJson(Map<String, dynamic> json) => SocietyInfo(
        id: json['id'] as String,
        name: json['name'] as String,
        societyCode: json['society_code'] as String?,
        totalFlats: json['total_flats'] as int?,
        totalWings: json['total_wings'] as int?,
      );
}

/// Fetches the current user's society info from GET /societies/.
/// Returns null if the request fails (graceful degradation).
final societyInfoProvider = FutureProvider.autoDispose<SocietyInfo?>((ref) async {
  try {
    final response = await ApiClient.instance.get('/societies/');
    final list = response.data as List<dynamic>? ?? [];
    if (list.isEmpty) return null;
    return SocietyInfo.fromJson(list.first as Map<String, dynamic>);
  } catch (_) {
    return null;
  }
});

