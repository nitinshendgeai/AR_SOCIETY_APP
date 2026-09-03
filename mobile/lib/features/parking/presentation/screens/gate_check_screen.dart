import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/features/parking/domain/entities/parking_entities.dart';
import 'package:ar_society_app/features/parking/presentation/providers/parking_providers.dart';
import 'package:ar_society_app/features/staff/presentation/widgets/staff_widgets.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';

/// Security gate screen: a guard types (or, once ANPR/RFID land, scans) a
/// vehicle number, sees whether it's a registered resident/tenant vehicle,
/// an active visitor, or unregistered — then logs the entry or exit. The
/// lookup (GET /parking/gate/validate) and the log write (POST
/// /parking/access-log) are two separate calls so the guard can see who a
/// vehicle belongs to before deciding to let it in.
class GateCheckScreen extends ConsumerStatefulWidget {
  const GateCheckScreen({super.key});

  @override
  ConsumerState<GateCheckScreen> createState() => _GateCheckScreenState();
}

class _GateCheckScreenState extends ConsumerState<GateCheckScreen> {
  final _vehicleCtrl = TextEditingController();

  String get _societyId => ref.read(currentUserProvider)?.societyId ?? '';

  @override
  void dispose() {
    _vehicleCtrl.dispose();
    super.dispose();
  }

  void _check() {
    final number = _vehicleCtrl.text.trim();
    if (number.isEmpty) return;
    FocusScope.of(context).unfocus();
    ref.read(gateCheckProvider.notifier)
        .validate(societyId: _societyId, vehicleNumber: number);
  }

  void _reset() {
    _vehicleCtrl.clear();
    ref.read(gateCheckProvider.notifier).reset();
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(gateCheckProvider);

    return Scaffold(
      backgroundColor: AppTheme.surface,
      appBar: AppBar(title: const Text('Vehicle Gate Check')),
      body: ResponsiveBody(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(20),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              AppTextField(
                label: 'Vehicle Number',
                hint: 'e.g. MH12AB1234',
                controller: _vehicleCtrl,
                keyboardType: TextInputType.text,
                textInputAction: TextInputAction.done,
                onFieldSubmitted: _check,
              ),
              const SizedBox(height: 14),
              AppPrimaryButton(
                label: 'Check Vehicle',
                icon: Icons.search_rounded,
                isLoading: state is GateCheckLoading,
                onPressed: _check,
              ),
              const SizedBox(height: 20),
              if (state is GateCheckError) ...[
                AppErrorBanner(message: state.message),
              ],
              if (state is GateCheckLookedUp) ...[
                _LookupResultCard(lookup: state.lookup),
                const SizedBox(height: 16),
                Row(children: [
                  Expanded(
                    child: OutlinedButton.icon(
                      onPressed: () => ref
                          .read(gateCheckProvider.notifier)
                          .logAccess(societyId: _societyId, accessType: GateAccessType.entry),
                      icon: const Icon(Icons.login_rounded),
                      label: const Text('Log Entry'),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: OutlinedButton.icon(
                      onPressed: () => ref
                          .read(gateCheckProvider.notifier)
                          .logAccess(societyId: _societyId, accessType: GateAccessType.exit),
                      icon: const Icon(Icons.logout_rounded),
                      label: const Text('Log Exit'),
                    ),
                  ),
                ]),
                const SizedBox(height: 12),
                TextButton(onPressed: _reset, child: const Text('Check Another Vehicle')),
              ],
              if (state is GateCheckLogged) ...[
                _LookupResultCard(lookup: state.lookup),
                const SizedBox(height: 16),
                Container(
                  padding: const EdgeInsets.all(14),
                  decoration: BoxDecoration(
                    color: AppTheme.success.withOpacity(0.1),
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(color: AppTheme.success.withOpacity(0.3)),
                  ),
                  child: Row(children: [
                    const Icon(Icons.check_circle_rounded, color: AppTheme.success, size: 20),
                    const SizedBox(width: 10),
                    Expanded(
                      child: Text(
                        '${state.log.accessType.label} logged at '
                        '${_formatTime(state.log.accessTime)}',
                        style: const TextStyle(
                          fontSize: 13, fontWeight: FontWeight.w600,
                          color: AppTheme.textPrimary,
                        ),
                      ),
                    ),
                  ]),
                ),
                const SizedBox(height: 12),
                AppPrimaryButton(label: 'Check Another Vehicle', onPressed: _reset),
              ],
            ],
          ),
        ),
      ),
    );
  }

  String _formatTime(DateTime dt) {
    final local = dt.toLocal();
    final h = local.hour.toString().padLeft(2, '0');
    final m = local.minute.toString().padLeft(2, '0');
    return '$h:$m';
  }
}

class _LookupResultCard extends StatelessWidget {
  final GateVehicleLookupEntity lookup;
  const _LookupResultCard({required this.lookup});

  @override
  Widget build(BuildContext context) {
    final color = lookup.authorized ? AppTheme.success : AppTheme.error;
    final icon = lookup.authorized ? Icons.check_circle_rounded : Icons.gpp_bad_rounded;

    return AppCard(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(children: [
            Icon(icon, color: color, size: 24),
            const SizedBox(width: 10),
            Expanded(
              child: Text(
                lookup.authorized ? 'Access Granted' : 'Not Registered',
                style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700, color: color),
              ),
            ),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
              decoration: BoxDecoration(
                color: color.withOpacity(0.12),
                borderRadius: BorderRadius.circular(20),
              ),
              child: Text(lookup.category.label,
                  style: TextStyle(fontSize: 11, fontWeight: FontWeight.w600, color: color)),
            ),
          ]),
          const SizedBox(height: 10),
          Text(lookup.vehicleNumber,
              style: const TextStyle(
                  fontSize: 18, fontWeight: FontWeight.w700, color: AppTheme.textPrimary,
                  letterSpacing: 0.5)),
          const SizedBox(height: 8),
          if (lookup.ownerName != null) _DetailRow(label: 'Owner', value: lookup.ownerName!),
          if (lookup.flatNumber != null)
            _DetailRow(
              label: lookup.category == GateVehicleCategory.visitor ? 'Visiting Flat' : 'Flat',
              value: [
                if (lookup.wingName != null) lookup.wingName,
                lookup.flatNumber,
              ].where((s) => s != null).join(' — '),
            ),
          if (lookup.parkingSlot != null) _DetailRow(label: 'Slot', value: lookup.parkingSlot!),
          if (lookup.visitorPurpose != null)
            _DetailRow(label: 'Purpose', value: lookup.visitorPurpose!),
          const SizedBox(height: 8),
          Text(lookup.message,
              style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
        ],
      ),
    );
  }
}

class _DetailRow extends StatelessWidget {
  final String label;
  final String value;
  const _DetailRow({required this.label, required this.value});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 4),
      child: Row(
        children: [
          SizedBox(
            width: 90,
            child: Text(label,
                style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
          ),
          Expanded(
            child: Text(value,
                style: const TextStyle(
                    fontSize: 13, fontWeight: FontWeight.w600, color: AppTheme.textPrimary)),
          ),
        ],
      ),
    );
  }
}
