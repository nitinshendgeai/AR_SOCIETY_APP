import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
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
