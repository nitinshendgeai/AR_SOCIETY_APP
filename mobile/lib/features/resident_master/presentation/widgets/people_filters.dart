import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/resident_master/presentation/providers/resident_master_providers.dart';
import 'package:ar_society_app/features/society_structure/data/models/structure_models.dart';
import 'package:ar_society_app/features/society_structure/presentation/providers/structure_providers.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';

/// A labelled row of choices, one selected: the value `null` is "all". Scrolls sideways on a narrow screen.
class FilterChoiceRow<T> extends StatelessWidget {
  final String label;
  final List<(T?, String)> options;
  final T? value;
  final ValueChanged<T?> onChanged;
  final String keyPrefix;
  const FilterChoiceRow({
    super.key,
    required this.label,
    required this.options,
    required this.value,
    required this.onChanged,
    required this.keyPrefix,
  });

  @override
  Widget build(BuildContext context) => Row(children: [
        SizedBox(
          width: 84,
          child: Text(label, style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w700, color: AppTheme.textSecondary)),
        ),
        Expanded(
          child: SizedBox(
            height: 38,
            child: ListView.separated(
              scrollDirection: Axis.horizontal,
              itemCount: options.length,
              separatorBuilder: (_, __) => const SizedBox(width: 8),
              itemBuilder: (_, i) {
                final (v, text) = options[i];
                return AppFilterPill(
                  key: ValueKey('$keyPrefix-${v ?? 'all'}'),
                  label: text,
                  selected: v == value,
                  onTap: () => onChanged(v),
                );
              },
            ),
          ),
        ),
      ]);
}

/// Wing and flat pickers. The flat list is the chosen wing's flats and stays closed until a wing is chosen. The wings
/// are the ones the society's flats belong to, so nothing more is loaded than the list already has.
class WingFlatFilter extends ConsumerWidget {
  final String? wingId;
  final String? flatId;
  final void Function(String? wingId, String? flatId) onChanged;
  const WingFlatFilter({super.key, required this.wingId, required this.flatId, required this.onChanged});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final flats = (ref.watch(flatsBySocietyProvider).valueOrNull ?? const <FlatModel>[]).where((f) => f.isActive).toList();
    final wings = <String, String>{for (final f in flats) f.wingId: f.wingName ?? ''}
      ..removeWhere((_, name) => name.isEmpty);
    final wingNames = wings.entries.toList()..sort((a, b) => a.value.compareTo(b.value));
    final inWing = [for (final f in flats) if (f.wingId == wingId) f]
      ..sort((a, b) => _natural(a.flatNumber, b.flatNumber));
    return Row(children: [
      Expanded(
        child: DropdownButtonFormField<String?>(
          key: const ValueKey('filter-wing'),
          initialValue: wings.containsKey(wingId) ? wingId : null,
          isExpanded: true,
          decoration: const InputDecoration(labelText: 'Wing', isDense: true),
          items: [
            const DropdownMenuItem<String?>(value: null, child: Text('All wings')),
            for (final w in wingNames) DropdownMenuItem<String?>(value: w.key, child: Text(w.value)),
          ],
          onChanged: (w) => onChanged(w, null),
        ),
      ),
      const SizedBox(width: 10),
      Expanded(
        child: DropdownButtonFormField<String?>(
          key: ValueKey('filter-flat-${wingId ?? 'none'}'),
          initialValue: inWing.any((f) => f.id == flatId) ? flatId : null,
          isExpanded: true,
          decoration: const InputDecoration(labelText: 'Flat', isDense: true),
          items: [
            const DropdownMenuItem<String?>(value: null, child: Text('All flats')),
            for (final f in inWing) DropdownMenuItem<String?>(value: f.id, child: Text(f.flatNumber)),
          ],
          // Closed until a wing is chosen
          onChanged: wingId == null ? null : (f) => onChanged(wingId, f),
        ),
      ),
    ]);
  }
}

/// Flat numbers in the order people count them: 2, 10, 101, A-2, A-10.
int _natural(String a, String b) {
  final na = int.tryParse(a), nb = int.tryParse(b);
  if (na != null && nb != null) return na.compareTo(nb);
  if (na != null) return -1;
  if (nb != null) return 1;
  return a.compareTo(b);
}

/// The "moved in" choices shared by the Residents and Tenants lists.
const movedInOptions = <(bool?, String)>[(null, 'All'), (true, 'Moved in'), (false, 'Not moved in')];


/// "Show the next 50" under a list that has more rows on the server than it has fetched.
class LoadMoreButton extends StatelessWidget {
  final int shown;
  final bool loading;
  final VoidCallback onPressed;
  final Key? buttonKey;
  const LoadMoreButton({super.key, required this.shown, required this.loading, required this.onPressed, this.buttonKey});

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.symmetric(vertical: 12),
        child: Center(
          child: loading
              ? const SizedBox(width: 24, height: 24, child: CircularProgressIndicator(strokeWidth: 2))
              : OutlinedButton.icon(
                  key: buttonKey,
                  onPressed: onPressed,
                  icon: const Icon(Icons.expand_more_rounded),
                  label: Text('Showing $shown, load the next 50'),
                ),
        ),
      );
}


/// "Residents 24 · Tenants 9": how many of each there are under the filters picked. The count of the list being looked
/// at follows all of its filters; the other count follows the filters the two lists share (wing, flat, active,
/// move-in and search), so the pair reads as one picture of the wing or flat. A count that could not be fetched shows
/// a dash.
class PeopleCountStrip extends ConsumerWidget {
  final PeopleCountQuery residents;
  final PeopleCountQuery tenants;

  /// Which count belongs to the list on screen, to stress it.
  final bool residentsList;
  const PeopleCountStrip({super.key, required this.residents, required this.tenants, required this.residentsList});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final r = ref.watch(residentCountProvider(residents));
    final t = ref.watch(tenantCountProvider(tenants));
    return Align(
      alignment: Alignment.centerLeft,
      child: Wrap(spacing: 8, runSpacing: 6, children: [
        _CountChip(
          chipKey: const ValueKey('people-count-residents'),
          icon: Icons.people_alt_rounded,
          label: 'Residents',
          count: r,
          stressed: residentsList,
        ),
        _CountChip(
          chipKey: const ValueKey('people-count-tenants'),
          icon: Icons.key_rounded,
          label: 'Tenants',
          count: t,
          stressed: !residentsList,
        ),
      ]),
    );
  }
}

class _CountChip extends StatelessWidget {
  final Key chipKey;
  final IconData icon;
  final String label;
  final AsyncValue<int?> count;
  final bool stressed;
  const _CountChip({
    required this.chipKey,
    required this.icon,
    required this.label,
    required this.count,
    required this.stressed,
  });

  @override
  Widget build(BuildContext context) {
    final value = count.when(data: (n) => n?.toString() ?? '—', loading: () => '…', error: (_, __) => '—');
    final color = stressed ? AppTheme.primary : AppTheme.textSecondary;
    return Semantics(
      label: '$label: $value',
      child: Container(
        key: chipKey,
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
        decoration: BoxDecoration(
          color: stressed ? AppTheme.primary.withOpacity(0.08) : AppTheme.cardBg,
          borderRadius: BorderRadius.circular(AppTheme.radiusXl),
          border: Border.all(color: stressed ? AppTheme.primary.withOpacity(0.4) : AppTheme.border),
        ),
        child: Row(mainAxisSize: MainAxisSize.min, children: [
          Icon(icon, size: 14, color: color),
          const SizedBox(width: 6),
          Text(label, style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: color)),
          const SizedBox(width: 6),
          Text(value, style: TextStyle(fontSize: 13, fontWeight: FontWeight.w800, color: color)),
        ]),
      ),
    );
  }
}
