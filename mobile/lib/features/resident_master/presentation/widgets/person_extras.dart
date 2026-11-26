import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/layout/app_sheet.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/features/resident_master/data/models/resident_master_models.dart';
import 'package:ar_society_app/features/resident_master/data/repositories/resident_master_repository.dart';
import 'package:ar_society_app/features/resident_master/presentation/providers/resident_master_providers.dart';
import 'package:ar_society_app/features/resident_master/presentation/widgets/resident_master_widgets.dart';
import 'package:ar_society_app/features/resident_master/presentation/widgets/vehicle_form_sheet.dart';
import 'package:ar_society_app/shared/widgets/app_form.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';
import 'package:ar_society_app/shared/widgets/confirm_remove.dart';

/// A family member typed into the Add form before the person exists. [relation] is a resident type for a resident
/// ('family' or 'dependent') and one of [tenantFamilyRelations] for a tenant.
class FamilyDraft {
  final String name;
  final String relation;
  final String? phone;
  const FamilyDraft({required this.name, required this.relation, this.phone});
}

class VehicleDraft {
  final String number;
  final VehicleType type;
  const VehicleDraft({required this.number, required this.type});
}

/// What was added in the Add form, kept by the form and saved once the person exists.
class PersonDrafts {
  final List<FamilyDraft> family = [];
  final List<VehicleDraft> vehicles = [];
  bool get isEmpty => family.isEmpty && vehicles.isEmpty;
}

/// Save what was added in the Add form against the new person. Returns what could not be saved (null when
/// everything was), so the form can say so instead of silently dropping it.
Future<String?> savePersonDrafts(
  WidgetRef ref,
  PersonDrafts drafts, {
  required bool tenant,
  required String personId,
  required String flatId,
}) async {
  final repo = ref.read(residentMasterRepositoryProvider);
  final societyId = ref.read(currentUserProvider)?.societyId;
  final problems = <String>[];
  for (final f in drafts.family) {
    final result = tenant
        ? await repo.addTenantFamily(personId, {
            'full_name': f.name,
            'relation': f.relation,
            if (f.phone != null) 'phone': f.phone,
          })
        : await repo.createResident({
            'flat_id': flatId,
            'full_name': f.name,
            'resident_type': f.relation,
            if (f.phone != null) 'phone': f.phone,
          });
    if (result is RmFailure) problems.add('${f.name}: ${rmFriendlyError((result as RmFailure).message)}');
  }
  for (final v in drafts.vehicles) {
    final result = await repo.createVehicle({
      'society_id': societyId,
      'flat_id': flatId,
      if (tenant) 'tenant_id': personId else 'resident_id': personId,
      'vehicle_number': v.number,
      'vehicle_type': v.type.value,
    });
    if (result is RmFailure) problems.add('${v.number}: ${rmFriendlyError((result as RmFailure).message)}');
  }
  if (problems.isEmpty) return null;
  return 'Saved, but not added: ${problems.join('; ')}. Add them from the person\'s edit form.';
}

/// The "Family members" and "Vehicles" parts of the resident and tenant forms. On a new person they collect drafts
/// (saved with the person); on an existing one they add and remove straight away.
class PersonExtrasSections extends ConsumerWidget {
  final bool tenant;

  /// The person being edited; null on the Add form.
  final String? personId;

  /// The flat of the person being edited (unused on the Add form).
  final String? flatId;

  /// A resident who is the flat's primary contact also shows the flat's vehicles that have no owner yet (a sheet
  /// import, say), which are the household's.
  final bool primary;
  final PersonDrafts drafts;
  final VoidCallback onDraftsChanged;

  const PersonExtrasSections({
    super.key,
    required this.tenant,
    required this.personId,
    required this.flatId,
    this.primary = false,
    required this.drafts,
    required this.onDraftsChanged,
  });

  bool get _editing => personId != null && flatId != null;

  @override
  Widget build(BuildContext context, WidgetRef ref) => Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          _familySection(context, ref),
          _vehicleSection(context, ref),
        ],
      );

  // ── Family ────────────────────────────────────────────────────────────

  Widget _familySection(BuildContext context, WidgetRef ref) {
    final rows = <Widget>[];
    if (!_editing) {
      for (var i = 0; i < drafts.family.length; i++) {
        final f = drafts.family[i];
        rows.add(_row(
          key: Key('family-draft-$i'),
          icon: Icons.person_outline_rounded,
          title: f.name,
          subtitle: _familySubtitle(f.relation, f.phone),
          removeKey: Key('family-draft-remove-$i'),
          onRemove: () {
            drafts.family.removeAt(i);
            onDraftsChanged();
          },
        ));
      }
    } else if (tenant) {
      final async = ref.watch(tenantFamilyProvider(personId!));
      rows.addAll(async.when(
        loading: () => [const LinearProgressIndicator()],
        error: (e, _) => [AppErrorBanner(message: rmFriendlyError(e))],
        data: (list) => [
          for (final m in list)
            _row(
              key: Key('family-${m.id}'),
              icon: Icons.person_outline_rounded,
              title: m.fullName,
              subtitle: _familySubtitle(m.relation, m.phone),
              removeKey: Key('family-remove-${m.id}'),
              onRemove: () => _removeSaved(
                context, ref, name: m.fullName, tenantFamily: true, id: m.id,
              ),
            ),
        ],
      ));
    } else {
      final async = ref.watch(residentsByFlatProvider(flatId!));
      rows.addAll(async.when(
        loading: () => [const LinearProgressIndicator()],
        error: (e, _) => [AppErrorBanner(message: rmFriendlyError(e))],
        data: (list) => [
          for (final r in list.where((r) =>
              r.id != personId && (r.residentType == ResidentType.family || r.residentType == ResidentType.dependent)))
            _row(
              key: Key('family-${r.id}'),
              icon: Icons.person_outline_rounded,
              title: r.fullName,
              subtitle: _familySubtitle(r.residentType.value, r.phone),
              removeKey: Key('family-remove-${r.id}'),
              onRemove: () => _removeSaved(context, ref, name: r.fullName, tenantFamily: false, id: r.id),
            ),
        ],
      ));
    }
    return FormSection(
      title: 'Family members',
      description: tenant
          ? 'The people who live with this tenant.'
          : 'The family and dependents who live in this flat. Remove one that was added by mistake.',
      columns: 1,
      children: [
        if (rows.isEmpty)
          Text('No family members added.', style: TextStyle(color: AppTheme.textSecondary, fontSize: 13)),
        ...rows,
        Align(
          alignment: Alignment.centerLeft,
          child: OutlinedButton.icon(
            key: const Key('family-add'),
            onPressed: () => _addFamily(context, ref),
            icon: const Icon(Icons.person_add_alt_1_rounded, size: 18),
            label: const Text('Add family member'),
          ),
        ),
      ],
    );
  }

  String _familySubtitle(String? relation, String? phone) {
    final label = tenant
        ? tenantRelationLabel(relation)
        : (relation == 'dependent' ? 'Dependent' : 'Family');
    return [label, if ((phone ?? '').isNotEmpty) phone!].join(' · ');
  }

  Future<void> _addFamily(BuildContext context, WidgetRef ref) async {
    final draft = await showAppSheet<FamilyDraft>(
      context: context,
      constraints: const BoxConstraints(maxWidth: 480),
      builder: (_) => _FamilySheet(tenant: tenant),
    );
    if (draft == null || !context.mounted) return;
    if (!_editing) {
      drafts.family.add(draft);
      onDraftsChanged();
      return;
    }
    final repo = ref.read(residentMasterRepositoryProvider);
    final result = tenant
        ? await repo.addTenantFamily(personId!, {
            'full_name': draft.name,
            'relation': draft.relation,
            if (draft.phone != null) 'phone': draft.phone,
          })
        : await repo.createResident({
            'flat_id': flatId,
            'full_name': draft.name,
            'resident_type': draft.relation,
            if (draft.phone != null) 'phone': draft.phone,
          });
    if (!context.mounted) return;
    switch (result) {
      case RmSuccess():
        _refreshFamily(ref);
        AppToast.success(context, '${draft.name} added');
      case RmFailure(:final message):
        AppToast.error(context, rmFriendlyError(message));
    }
  }

  Future<void> _removeSaved(
    BuildContext context,
    WidgetRef ref, {
    required String name,
    required bool tenantFamily,
    required String id,
  }) async {
    final ok = await confirmRemove(context,
        title: 'Remove $name?',
        message: 'Use this for a family member added by mistake. They are taken off the list.');
    if (!ok || !context.mounted) return;
    final repo = ref.read(residentMasterRepositoryProvider);
    final result = tenantFamily ? await repo.removeTenantFamily(personId!, id) : await repo.deleteResident(id);
    if (!context.mounted) return;
    switch (result) {
      case RmSuccess():
        _refreshFamily(ref);
        AppToast.success(context, '$name removed');
      case RmFailure(:final message):
        AppToast.error(context, rmFriendlyError(message));
    }
  }

  void _refreshFamily(WidgetRef ref) {
    if (tenant) {
      ref.invalidate(tenantFamilyProvider(personId!));
    } else {
      ref.invalidate(residentsByFlatProvider(flatId!));
      ref.read(residentListProvider.notifier).refresh();
    }
  }

  // ── Vehicles ──────────────────────────────────────────────────────────

  Widget _vehicleSection(BuildContext context, WidgetRef ref) {
    final rows = <Widget>[];
    if (!_editing) {
      for (var i = 0; i < drafts.vehicles.length; i++) {
        final v = drafts.vehicles[i];
        rows.add(_row(
          key: Key('vehicle-draft-$i'),
          icon: Icons.directions_car_outlined,
          title: v.number,
          subtitle: v.type.label,
          removeKey: Key('vehicle-draft-remove-$i'),
          onRemove: () {
            drafts.vehicles.removeAt(i);
            onDraftsChanged();
          },
        ));
      }
    } else {
      final async = ref.watch(vehiclesByFlatProvider(flatId!));
      rows.addAll(async.when(
        loading: () => [const LinearProgressIndicator()],
        error: (e, _) => [AppErrorBanner(message: rmFriendlyError(e))],
        data: (list) => [
          for (final v in list.where((v) => tenant
              ? v.tenantId == personId
              : v.residentId == personId || (primary && v.residentId == null && v.tenantId == null)))
            _row(
              key: Key('vehicle-${v.id}'),
              icon: Icons.directions_car_outlined,
              title: v.vehicleNumber,
              subtitle: v.vehicleType.label,
              removeKey: Key('vehicle-remove-${v.id}'),
              onRemove: () => confirmDeactivateVehicle(context, ref, flatId!, v),
            ),
        ],
      ));
    }
    return FormSection(
      title: 'Vehicles',
      description: 'Cars and bikes this person parks in the society. Remove one that was added by mistake.',
      columns: 1,
      children: [
        if (rows.isEmpty)
          Text('No vehicles added.', style: TextStyle(color: AppTheme.textSecondary, fontSize: 13)),
        ...rows,
        Align(
          alignment: Alignment.centerLeft,
          child: OutlinedButton.icon(
            key: const Key('vehicle-add'),
            onPressed: () => _addVehicle(context, ref),
            icon: const Icon(Icons.add_rounded, size: 18),
            label: const Text('Add vehicle'),
          ),
        ),
      ],
    );
  }

  Future<void> _addVehicle(BuildContext context, WidgetRef ref) async {
    if (_editing) {
      await showVehicleFormSheet(context, ref,
          flatId: flatId!, residentId: tenant ? null : personId, tenantId: tenant ? personId : null);
      return;
    }
    final draft = await showAppSheet<VehicleDraft>(
      context: context,
      constraints: const BoxConstraints(maxWidth: 480),
      builder: (_) => const _VehicleDraftSheet(),
    );
    if (draft == null) return;
    drafts.vehicles.add(draft);
    onDraftsChanged();
  }

  // ── A row ─────────────────────────────────────────────────────────────

  Widget _row({
    required Key key,
    required IconData icon,
    required String title,
    required String subtitle,
    required Key removeKey,
    required VoidCallback onRemove,
  }) =>
      Container(
        key: key,
        padding: const EdgeInsets.fromLTRB(12, 6, 4, 6),
        decoration: BoxDecoration(
          color: AppTheme.cardBg,
          borderRadius: BorderRadius.circular(AppTheme.radiusM),
          border: Border.all(color: AppTheme.border),
        ),
        child: Row(children: [
          Icon(icon, size: 20, color: AppTheme.textSecondary),
          const SizedBox(width: 10),
          Expanded(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text(title, style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 14)),
              Text(subtitle, style: TextStyle(color: AppTheme.textSecondary, fontSize: 12)),
            ]),
          ),
          IconButton(
            key: removeKey,
            tooltip: 'Remove',
            icon: Icon(Icons.delete_outline_rounded, size: 20, color: AppTheme.error),
            onPressed: onRemove,
          ),
        ]),
      );
}

class _FamilySheet extends StatefulWidget {
  final bool tenant;
  const _FamilySheet({required this.tenant});

  @override
  State<_FamilySheet> createState() => _FamilySheetState();
}

class _FamilySheetState extends State<_FamilySheet> {
  final _formKey = GlobalKey<FormState>();
  final _nameCtrl = TextEditingController();
  final _phoneCtrl = TextEditingController();
  late String _relation = widget.tenant ? 'spouse' : 'family';

  @override
  void dispose() {
    _nameCtrl.dispose();
    _phoneCtrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final options = widget.tenant ? tenantFamilyRelations : const {'family': 'Family member', 'dependent': 'Dependent'};
    return AppSheetFrame(
      title: 'Add family member',
      child: Form(
        key: _formKey,
        child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          FormFieldBox(
            label: 'Full name',
            required: true,
            child: TextFormField(
              key: const Key('family-name'),
              controller: _nameCtrl,
              textCapitalization: TextCapitalization.words,
              inputFormatters: [LengthLimitingTextInputFormatter(255)],
              validator: (v) => (v == null || v.trim().isEmpty) ? 'Name is required' : null,
            ),
          ),
          const SizedBox(height: 14),
          FormFieldBox(
            label: widget.tenant ? 'Relation' : 'Type',
            child: DropdownButtonFormField<String>(
              isExpanded: true,
              value: _relation,
              items: [for (final e in options.entries) DropdownMenuItem(value: e.key, child: Text(e.value))],
              onChanged: (v) => setState(() => _relation = v ?? _relation),
            ),
          ),
          const SizedBox(height: 14),
          FormFieldBox(
            label: 'Mobile',
            child: TextFormField(
              key: const Key('family-phone'),
              controller: _phoneCtrl,
              keyboardType: TextInputType.phone,
              inputFormatters: [FilteringTextInputFormatter.digitsOnly, LengthLimitingTextInputFormatter(10)],
              decoration: const InputDecoration(hintText: 'Optional'),
              validator: rmPhoneValidator,
            ),
          ),
          const SizedBox(height: 20),
          AppPrimaryButton(
            label: 'Add',
            onPressed: () {
              if (!_formKey.currentState!.validate()) return;
              final phone = _phoneCtrl.text.trim();
              Navigator.of(context).pop(FamilyDraft(
                name: _nameCtrl.text.trim(),
                relation: _relation,
                phone: phone.isEmpty ? null : phone,
              ));
            },
          ),
        ]),
      ),
    );
  }
}

class _VehicleDraftSheet extends StatefulWidget {
  const _VehicleDraftSheet();

  @override
  State<_VehicleDraftSheet> createState() => _VehicleDraftSheetState();
}

class _VehicleDraftSheetState extends State<_VehicleDraftSheet> {
  final _formKey = GlobalKey<FormState>();
  final _numberCtrl = TextEditingController();
  VehicleType _type = VehicleType.car;

  @override
  void dispose() {
    _numberCtrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => AppSheetFrame(
        title: 'Add vehicle',
        child: Form(
          key: _formKey,
          child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.stretch, children: [
            FormFieldBox(
              label: 'Vehicle number',
              required: true,
              child: TextFormField(
                key: const Key('vehicle-number'),
                controller: _numberCtrl,
                textCapitalization: TextCapitalization.characters,
                inputFormatters: [LengthLimitingTextInputFormatter(30)],
                decoration: const InputDecoration(hintText: 'e.g. MH12AB1234'),
                validator: rmVehicleNumberValidator,
              ),
            ),
            const SizedBox(height: 14),
            FormFieldBox(
              label: 'Vehicle type',
              child: DropdownButtonFormField<VehicleType>(
                value: _type,
                items: [for (final t in VehicleType.values) DropdownMenuItem(value: t, child: Text(t.label))],
                onChanged: (v) => setState(() => _type = v ?? _type),
              ),
            ),
            const SizedBox(height: 20),
            AppPrimaryButton(
              label: 'Add',
              onPressed: () {
                if (!_formKey.currentState!.validate()) return;
                Navigator.of(context).pop(VehicleDraft(number: _numberCtrl.text.trim(), type: _type));
              },
            ),
          ]),
        ),
      );
}
