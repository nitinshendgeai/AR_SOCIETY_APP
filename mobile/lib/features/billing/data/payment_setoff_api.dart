import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/api/api_client.dart';

double _num(Object? v) => double.tryParse(v?.toString() ?? '') ?? 0;

/// Money members have paid that isn't set off against a bill yet.
class UnappliedPayments {
  final int flats;
  final double amount;

  /// Of which: flats that still have open bills it could settle (payments
  /// recorded on account before set-off was automatic).
  final int flatsWithOpenBills;
  final double amountAgainstOpenBills;

  const UnappliedPayments(this.flats, this.amount, this.flatsWithOpenBills, this.amountAgainstOpenBills);
}

/// FastAPI /billing/online-payments/society/{id}/unapplied and /apply.
class PaymentSetOffApi {
  Future<UnappliedPayments> unapplied(String societyId) async {
    final j = (await ApiClient.instance.get('/billing/online-payments/society/$societyId/unapplied')).data
        as Map<String, dynamic>;
    return UnappliedPayments((j['flats'] as num?)?.toInt() ?? 0, _num(j['amount']),
        (j['flats_with_open_bills'] as num?)?.toInt() ?? 0, _num(j['amount_against_open_bills']));
  }

  /// Sets every flat's unapplied payments off against its open bills,
  /// oldest first. Returns (bills settled, amount).
  Future<(int, double)> apply(String societyId) async {
    final j = (await ApiClient.instance.post('/billing/online-payments/society/$societyId/apply')).data
        as Map<String, dynamic>;
    return ((j['bills'] as num?)?.toInt() ?? 0, _num(j['amount']));
  }
}

final paymentSetOffApiProvider = Provider<PaymentSetOffApi>((_) => PaymentSetOffApi());

final unappliedPaymentsProvider = FutureProvider.autoDispose.family<UnappliedPayments, String>(
  (ref, societyId) => ref.watch(paymentSetOffApiProvider).unapplied(societyId),
);
