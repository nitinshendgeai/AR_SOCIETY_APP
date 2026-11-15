import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/l10n/app_locale.dart';
import 'package:ar_society_app/core/motion/loading.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/core/theme/design_tokens.dart';
import 'package:ar_society_app/features/gym/data/gym_api.dart';
import 'package:ar_society_app/features/resident_master/presentation/widgets/people_filters.dart';
import 'package:ar_society_app/shared/widgets/app_form.dart';
import 'package:ar_society_app/shared/widgets/app_status.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';

/// Ticking in: the trainer picks the wing and the flat, the flat's members appear, and he ticks the ones who are here.
/// Only the owners' side of a flat is listed (never tenants); someone already inside is shown and cannot be ticked again.
class GymCheckInScreen extends ConsumerStatefulWidget {
  const GymCheckInScreen({super.key});

  @override
  ConsumerState<GymCheckInScreen> createState() => _GymCheckInScreenState();
}

class _GymCheckInScreenState extends ConsumerState<GymCheckInScreen> {
  String? _wingId;
  String? _flatId;
  final Set<String> _ticked = {};
  bool _busy = false;

  Future<void> _checkIn() async {
    final flatId = _flatId;
    if (flatId == null || _ticked.isEmpty || _busy) return;
    setState(() => _busy = true);
    try {
      final r = await ref.read(gymApiProvider).checkIn(flatId, _ticked.toList());
      ref.invalidate(gymLiveProvider);
      ref.invalidate(gymFlatMembersProvider(flatId));
      if (!mounted) return;
      AppToast.success(context, context.trf('{n} checked in', {'n': r.checkedIn}));
      context.pop();
    } catch (e) {
      if (mounted) showErrorToast(context, e);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final flatId = _flatId;
    return AppPage(
      title: 'Check in members',
      body: Column(children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 8, 16, 8),
          child: WingFlatFilter(
            wingId: _wingId,
            flatId: flatId,
            wingHint: context.tr('Choose wing'),
            flatHint: context.tr('Choose flat'),
            onChanged: (w, f) => setState(() {
              _wingId = w;
              _flatId = f;
              _ticked.clear();
            }),
          ),
        ),
        Expanded(
          child: flatId == null
              ? Center(
                  child: Padding(
                    padding: const EdgeInsets.all(32),
                    child: Text(context.tr('Choose a wing and a flat to see its members.'),
                        textAlign: TextAlign.center, style: const TextStyle(color: AppTheme.textSecondary)),
                  ),
                )
              : ref.watch(gymFlatMembersProvider(flatId)).when(
                    loading: () => const SkeletonList(),
                    error: (e, _) => AppErrorState(
                        message: friendlyErrorMessage(e), onRetry: () => ref.invalidate(gymFlatMembersProvider(flatId))),
                    data: _members,
                  ),
        ),
        if (flatId != null)
          SafeArea(
            top: false,
            child: Padding(
              padding: const EdgeInsets.fromLTRB(16, 8, 16, 12),
              child: AppPrimaryButton(
                label: _ticked.isEmpty ? 'Tick who is here' : context.trf('Check in {n}', {'n': _ticked.length}),
                isLoading: _busy,
                onPressed: _ticked.isEmpty ? null : _checkIn,
              ),
            ),
          ),
      ]),
    );
  }

  Widget _members(GymFlatMembers flat) {
    if (flat.members.isEmpty) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(32),
          child: Text(
            context.tr(flat.letToTenants
                ? 'This flat is let to tenants. The gym is for owners and their families.'
                : 'No members are listed for this flat.'),
            key: const Key('gym-no-members'),
            textAlign: TextAlign.center,
            style: const TextStyle(color: AppTheme.textSecondary),
          ),
        ),
      );
    }
    return ListView(
      padding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
      children: [
        Padding(
          padding: const EdgeInsets.only(bottom: 6),
          child: Text(flat.flatLabel, style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w700)),
        ),
        for (final m in flat.members)
          Padding(
            padding: const EdgeInsets.only(bottom: 8),
            child: Container(
              decoration: BoxDecoration(color: AppTheme.cardBg, borderRadius: BorderRadius.circular(AppTheme.radiusM), boxShadow: AppTheme.cardShadow),
              // The tile's ripple is drawn on the nearest Material: on this transparent one, not hidden under the white box.
              child: Material(
                type: MaterialType.transparency,
                child: CheckboxListTile(
                key: Key('gym-member-${m.residentId}'),
                value: m.inside || _ticked.contains(m.residentId),
                onChanged: m.inside
                    ? null
                    : (v) => setState(() => v == true ? _ticked.add(m.residentId) : _ticked.remove(m.residentId)),
                controlAffinity: ListTileControlAffinity.leading,
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(AppTheme.radiusM)),
                title: Text(m.name, style: const TextStyle(fontWeight: FontWeight.w600)),
                subtitle: Text(context.tr(m.typeLabel)),
                secondary: m.inside ? AppStatusChip(label: context.tr('Inside now'), tone: AppTone.warning, icon: Icons.fitness_center_rounded) : null,
                ),
              ),
            ),
          ),
      ],
    );
  }
}
