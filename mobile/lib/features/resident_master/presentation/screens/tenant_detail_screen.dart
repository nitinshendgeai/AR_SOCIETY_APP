import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:ar_society_app/core/router/app_router.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/features/resident_master/data/models/resident_master_models.dart';
import 'package:ar_society_app/features/resident_master/presentation/providers/resident_master_providers.dart';
import 'package:ar_society_app/features/resident_master/presentation/widgets/resident_master_widgets.dart';
import 'package:ar_society_app/features/resident_master/presentation/widgets/occupancy_action_sheets.dart';
import 'package:ar_society_app/features/resident_master/presentation/widgets/vehicle_form_sheet.dart';
import 'package:ar_society_app/features/resident_master/presentation/widgets/agreement_renewal_sheet.dart';
import 'package:ar_society_app/features/society_structure/data/models/structure_models.dart';
import 'package:ar_society_app/features/society_structure/presentation/providers/structure_providers.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';

/// Canonical Tenant Detail screen — the flat's tenancy at a glance: who the
/// tenant is, what the current agreement says, and when it needs renewal.
class TenantDetailScreen extends ConsumerWidget {
  final TenantModel tenant;
  const TenantDetailScreen({super.key, required this.tenant});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final detailAsync = ref.watch(tenantDetailProvider(tenant.id));
    final user = ref.watch(currentUserProvider);
    final canEdit = user?.isAdminOrCommittee ?? false;

    return detailAsync.when(
      loading: () => const Scaffold(body: Center(child: CircularProgressIndicator())),
      error: (e, _) => Scaffold(
        appBar: AppBar(title: const Text('Tenant')),
        body: Center(child: Text(rmFriendlyError(e), style: const TextStyle(color: AppTheme.error))),
      ),
      data: (t) => _TenantDetailBody(tenant: t, canEdit: canEdit),
    );
  }
}

class _TenantDetailBody extends ConsumerWidget {
  final TenantModel tenant;
  final bool canEdit;
  const _TenantDetailBody({required this.tenant, required this.canEdit});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final flatsAsync = ref.watch(flatsBySocietyProvider);
    final flat = (flatsAsync.valueOrNull ?? <FlatModel>[])
        .where((f) => f.id == tenant.flatId)
        .cast<FlatModel?>()
        .firstWhere((f) => true, orElse: () => null);

    final vehiclesAsync = ref.watch(vehiclesByFlatProvider(tenant.flatId));
    final historyAsync = ref.watch(flatHistoryProvider(tenant.flatId));

    final canMoveIn = tenant.isActive && tenant.moveInDate == null;
    final canMoveOut = tenant.isActive && tenant.moveInDate != null && tenant.moveOutDate == null;
    final hasActiveAgreement = tenant.activeAgreementId != null && !tenant.hasMovedOut;
    final daysLeft = rmDaysUntil(tenant.agreementEndDate);

    return Scaffold(
      backgroundColor: AppTheme.surface,
      appBar: AppBar(
        title: Text(tenant.fullName),
        actions: [
          if (canEdit)
            IconButton(
              icon: const Icon(Icons.edit_rounded),
              tooltip: 'Edit',
              onPressed: () => context.push(AppRoutes.tenantForm, extra: {'tenant': tenant}),
            ),
        ],
      ),
      body: ResponsiveBody(child: ListView(
        padding: const EdgeInsets.all(20),
        children: [
          _HeaderCard(tenant: tenant),
          const SizedBox(height: 16),

          RmSection(title: 'Profile', children: [
            RmRow(label: 'Phone', value: tenant.phone ?? '—'),
            RmRow(label: 'Email', value: tenant.email ?? '—'),
            RmRow(label: 'ID Proof', value: tenant.idProofType != null
                ? '${tenant.idProofType} · ${tenant.idProofNumber ?? "—"}' : '—'),
            RmRow(label: 'KYC', value: tenant.kycVerified ? 'Verified' : 'Not verified'),
            RmRow(label: 'Police Verification', value: tenant.policeVerificationStatus.label),
            RmRow(label: 'Emergency Contact', value: tenant.emergencyContactName != null
                ? '${tenant.emergencyContactName} (${tenant.emergencyContactPhone ?? "—"})' : '—'),
            if (tenant.remarks != null && tenant.remarks!.isNotEmpty)
              RmRow(label: 'Remarks', value: tenant.remarks!),
          ]),
          const SizedBox(height: 16),

          RmSection(
            title: 'Flat',
            trailing: flat != null
                ? TextButton(onPressed: () => context.push(AppRoutes.flatDetail, extra: flat),
                    child: const Text('View Flat', style: TextStyle(fontSize: 12)))
                : null,
            children: [
              RmRow(label: 'Wing', value: flat?.wingName ?? '—'),
              RmRow(label: 'Flat', value: flat?.displayName ?? '—'),
              RmRow(label: 'Move-in Date', value: rmFormatDate(tenant.moveInDate)),
              if (tenant.moveOutDate != null) RmRow(label: 'Move-out Date', value: rmFormatDate(tenant.moveOutDate)),
            ],
          ),
          const SizedBox(height: 16),

          RmSection(
            title: 'Agreement',
            trailing: canEdit && hasActiveAgreement
                ? TextButton.icon(
                    onPressed: () => showAgreementRenewalSheet(context, ref, tenant: tenant),
                    icon: const Icon(Icons.autorenew_rounded, size: 16),
                    label: const Text('Renew', style: TextStyle(fontSize: 12)),
                  )
                : null,
            children: [
              if (tenant.agreementStartDate == null)
                const Text('No agreement on file.', style: TextStyle(fontSize: 13, color: AppTheme.textSecondary))
              else ...[
                Row(children: [
                  Expanded(
                    child: AgreementStatusBadge(
                      status: hasActiveAgreement
                          ? AgreementStatus.active
                          : (daysLeft != null && daysLeft < 0 ? AgreementStatus.expired : AgreementStatus.terminated),
                    ),
                  ),
                  if (daysLeft != null && daysLeft >= 0 && daysLeft <= 30 && hasActiveAgreement)
                    Text('Expires in $daysLeft day${daysLeft == 1 ? '' : 's'}',
                        style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w700, color: AppTheme.warning)),
                ]),
                const SizedBox(height: 8),
                RmRow(label: 'Start Date', value: rmFormatDate(tenant.agreementStartDate)),
                RmRow(label: 'End Date', value: rmFormatDate(tenant.agreementEndDate)),
                RmRow(label: 'Monthly Rent', value: tenant.monthlyRent != null ? '₹${tenant.monthlyRent}' : '—'),
                RmRow(label: 'Security Deposit', value: tenant.securityDeposit != null ? '₹${tenant.securityDeposit}' : '—'),
              ],
            ],
          ),
          const SizedBox(height: 16),

          RmSection(title: 'Agreement History', children: [
            Consumer(builder: (context, ref, _) {
              final historyAsync = ref.watch(tenantAgreementsProvider(tenant.id));
              return historyAsync.when(
                loading: () => const LinearProgressIndicator(),
                error: (e, _) => Text(rmFriendlyError(e), style: const TextStyle(color: AppTheme.error, fontSize: 12)),
                data: (agreements) {
                  if (agreements.isEmpty) {
                    return const Text('No agreement history available.',
                        style: TextStyle(fontSize: 13, color: AppTheme.textSecondary));
                  }
                  return Column(
                    children: [
                      for (int i = 0; i < agreements.length; i++) ...[
                        if (i > 0) const Divider(height: 20, color: AppTheme.border),
                        _AgreementHistoryTile(
                          agreement: agreements[i],
                          label: i == 0 ? 'CURRENT' : i == 1 ? 'PREVIOUS' : 'OLDER',
                        ),
                      ],
                    ],
                  );
                },
              );
            }),
          ]),
          const SizedBox(height: 16),

          RmSection(
            title: 'Vehicles',
            trailing: canEdit
                ? IconButton(
                    icon: const Icon(Icons.add_circle_outline_rounded, size: 20, color: AppTheme.primary),
                    tooltip: 'Add Vehicle',
                    onPressed: () => showVehicleFormSheet(context, ref, flatId: tenant.flatId, tenantId: tenant.id),
                  )
                : null,
            children: [
              vehiclesAsync.when(
                loading: () => const LinearProgressIndicator(),
                error: (e, _) => Text(rmFriendlyError(e), style: const TextStyle(color: AppTheme.error, fontSize: 12)),
                data: (vehicles) {
                  final own = vehicles.where((v) => v.tenantId == tenant.id).toList();
                  if (own.isEmpty) {
                    return const Text('No vehicles registered.', style: TextStyle(fontSize: 13, color: AppTheme.textSecondary));
                  }
                  return Column(
                    children: own.map((v) => Padding(
                          padding: const EdgeInsets.symmetric(vertical: 6),
                          child: Row(children: [
                            const Icon(Icons.directions_car_rounded, size: 18, color: AppTheme.textSecondary),
                            const SizedBox(width: 10),
                            Expanded(
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text(v.vehicleNumber, style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w700, color: AppTheme.textPrimary)),
                                  Text(v.vehicleType.label, style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
                                ],
                              ),
                            ),
                            if (canEdit)
                              IconButton(
                                icon: const Icon(Icons.edit_outlined, size: 18),
                                tooltip: 'Edit vehicle',
                                onPressed: () => showVehicleFormSheet(context, ref, flatId: tenant.flatId, tenantId: tenant.id, vehicle: v),
                              ),
                          ]),
                        )).toList(),
                  );
                },
              ),
            ],
          ),
          const SizedBox(height: 16),

          RmSection(title: 'Occupancy History', children: [
            historyAsync.when(
              loading: () => const LinearProgressIndicator(),
              error: (_, __) => const Text('Unable to load history', style: TextStyle(color: AppTheme.error, fontSize: 12)),
              data: (logs) {
                final relevant = logs.where((l) => l.tenantId == tenant.id).toList();
                if (relevant.isEmpty) {
                  return const Text('No occupancy events recorded yet.', style: TextStyle(fontSize: 13, color: AppTheme.textSecondary));
                }
                return Column(
                  children: relevant.map((l) => Padding(
                        padding: const EdgeInsets.symmetric(vertical: 6),
                        child: Row(children: [
                          const Icon(Icons.circle, size: 6, color: AppTheme.secondary),
                          const SizedBox(width: 8),
                          Expanded(child: Text(l.eventType.label, style: const TextStyle(fontSize: 13, color: AppTheme.textPrimary))),
                          Text(rmFormatDate(l.eventDate), style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
                        ]),
                      )).toList(),
                );
              },
            ),
          ]),

          if (canEdit && (canMoveIn || canMoveOut)) ...[
            const SizedBox(height: 24),
            if (canMoveIn)
              OutlinedButton.icon(
                onPressed: () => showTenantMoveInSheet(context, ref, tenant: tenant),
                icon: const Icon(Icons.login_rounded, size: 18),
                label: const Text('Move In'),
                style: OutlinedButton.styleFrom(
                  foregroundColor: AppTheme.success,
                  side: const BorderSide(color: AppTheme.success),
                  minimumSize: const Size(double.infinity, 44),
                ),
              ),
            if (canMoveOut)
              OutlinedButton.icon(
                onPressed: () => showTenantMoveOutSheet(context, ref, tenant: tenant),
                icon: const Icon(Icons.logout_rounded, size: 18),
                label: const Text('Move Out'),
                style: OutlinedButton.styleFrom(
                  foregroundColor: AppTheme.error,
                  side: const BorderSide(color: AppTheme.error),
                  minimumSize: const Size(double.infinity, 44),
                ),
              ),
          ],
          const SizedBox(height: 24),
        ],
      )),
    );
  }
}

class _HeaderCard extends StatelessWidget {
  final TenantModel tenant;
  const _HeaderCard({required this.tenant});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: [AppTheme.secondary.withOpacity(0.14), AppTheme.secondary.withOpacity(0.03)],
          begin: Alignment.topLeft, end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppTheme.secondary.withOpacity(0.18)),
      ),
      child: Row(children: [
        Container(
          width: 56, height: 56,
          decoration: BoxDecoration(color: AppTheme.secondary.withOpacity(0.16), shape: BoxShape.circle),
          child: const Icon(Icons.groups_2_rounded, color: AppTheme.secondary, size: 28),
        ),
        const SizedBox(width: 16),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(tenant.fullName, style: const TextStyle(fontSize: 19, fontWeight: FontWeight.w700, color: AppTheme.textPrimary)),
              const SizedBox(height: 6),
              ActiveBadge(isActive: tenant.isActive && !tenant.hasMovedOut),
            ],
          ),
        ),
      ]),
    );
  }
}

/// One row in the Agreement History timeline — CURRENT/PREVIOUS/OLDER label
/// (by recency, per the newest-first ordering the backend already returns)
/// plus dates/rent/deposit/status, mirroring the compact RmRow styling used
/// throughout Resident Master rather than introducing a new visual system.
class _AgreementHistoryTile extends StatelessWidget {
  final AgreementModel agreement;
  final String label;
  const _AgreementHistoryTile({required this.agreement, required this.label});

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(children: [
          Text(label,
              style: const TextStyle(fontSize: 11, fontWeight: FontWeight.w700, color: AppTheme.primary, letterSpacing: 0.6)),
          const SizedBox(width: 8),
          AgreementStatusBadge(status: agreement.status),
        ]),
        const SizedBox(height: 6),
        Text('${rmFormatDate(agreement.startDate)} → ${rmFormatDate(agreement.endDate)}',
            style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: AppTheme.textPrimary)),
        if (agreement.monthlyRent != null || agreement.securityDeposit != null) ...[
          const SizedBox(height: 2),
          Text([
            if (agreement.monthlyRent != null) 'Rent ₹${agreement.monthlyRent}',
            if (agreement.securityDeposit != null) 'Deposit ₹${agreement.securityDeposit}',
          ].join(' · '), style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
        ],
        if (agreement.terminationReason != null) ...[
          const SizedBox(height: 2),
          Text(agreement.terminationReason!, style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
        ],
      ],
    );
  }
}
