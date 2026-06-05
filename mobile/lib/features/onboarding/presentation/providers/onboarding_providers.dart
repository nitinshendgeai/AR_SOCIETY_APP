import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:dio/dio.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/features/onboarding/data/onboarding_remote_datasource.dart';
import 'package:ar_society_app/features/onboarding/domain/registration_result.dart';

// ── State ─────────────────────────────────────────────────────────────────────

sealed class OnboardingState {}

class OnboardingIdle extends OnboardingState {}

class OnboardingLoading extends OnboardingState {}

class OnboardingSuccess extends OnboardingState {
  final RegistrationResult result;
  OnboardingSuccess(this.result);
}

class OnboardingError extends OnboardingState {
  final String message;
  OnboardingError(this.message);
}

// ── Notifier ──────────────────────────────────────────────────────────────────

class OnboardingNotifier extends StateNotifier<OnboardingState> {
  final OnboardingRemoteDataSource _ds;

  OnboardingNotifier(this._ds) : super(OnboardingIdle());

  Future<void> register({
    required String societyName,
    required String societyCode,
    required String contactPersonName,
    required String contactEmail,
    required String contactMobile,
    required String city,
    required String state,
    int totalWings = 1,
    int totalFlats = 1,
  }) async {
    this.state = OnboardingLoading();
    try {
      final data = await _ds.registerSociety(
        societyName:        societyName,
        societyCode:        societyCode,
        contactPersonName:  contactPersonName,
        contactEmail:       contactEmail,
        contactMobile:      contactMobile,
        city:               city,
        state:              state,
        totalWings:         totalWings,
        totalFlats:         totalFlats,
      );
      this.state = OnboardingSuccess(RegistrationResult.fromJson(data));
    } on DioException catch (e) {
      final msg = _parseError(e);
      this.state = OnboardingError(msg);
    } catch (e) {
      this.state = OnboardingError('Unexpected error: $e');
    }
  }

  void reset() => state = OnboardingIdle();

  String _parseError(DioException e) {
    if (e.response?.data is Map) {
      final d = e.response!.data as Map<String, dynamic>;
      if (d.containsKey('detail')) return d['detail'].toString();
    }
    switch (e.response?.statusCode) {
      case 409: return 'Society name, code, or contact is already registered.';
      case 422: return 'Invalid registration data. Please check all fields.';
      default:  return 'Registration failed. Please try again.';
    }
  }
}

// ── Provider ──────────────────────────────────────────────────────────────────

final onboardingProvider =
    StateNotifierProvider<OnboardingNotifier, OnboardingState>((ref) {
  return OnboardingNotifier(OnboardingRemoteDataSource());
});
