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
