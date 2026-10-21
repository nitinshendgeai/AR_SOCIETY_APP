import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/motion/loading.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/staff/domain/entities/staff_entities.dart';
import 'package:ar_society_app/features/staff/presentation/providers/staff_providers.dart';

String _department(String value) => value.isEmpty ? value : value[0].toUpperCase() + value.substring(1);

/// Lets a manager add the ready-made daily rounds (plumber, electrician, both) to the society's own
/// checklist templates. Ones the society already has are shown ticked and cannot be added twice.
Future<void> showStandardChecklistsSheet(BuildContext context, String societyId) {
  return showModalBottomSheet<void>(
    context: context,
    isScrollControlled: true,
    showDragHandle: true,
    builder: (_) => StandardChecklistsSheet(societyId: societyId),
  );
}

class StandardChecklistsSheet extends ConsumerStatefulWidget {
  final String societyId;
  const StandardChecklistsSheet({super.key, required this.societyId});

  @override
  ConsumerState<StandardChecklistsSheet> createState() => _StandardChecklistsSheetState();
}

class _StandardChecklistsSheetState extends ConsumerState<StandardChecklistsSheet> {
  final Set<String> _picked = {};
  bool _saving = false;

  Future<void> _add() async {
    setState(() => _saving = true);
    try {
      final added = await ref
          .read(checklistTemplatesProvider(widget.societyId).notifier)
          .addStandard(_picked.toList());
      if (!mounted) return;
      Navigator.pop(context);
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(
        content: Text(added == 0 ? 'Already in your templates' : 'Added $added checklist(s) to your templates'),
      ));
    } catch (e) {
      if (mounted) {
        setState(() => _saving = false);
        ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text(friendlyErrorMessage(e)), backgroundColor: AppTheme.error));
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final async = ref.watch(standardChecklistsProvider(widget.societyId));
    return DraggableScrollableSheet(
      expand: false,
      initialChildSize: 0.75,
      maxChildSize: 0.95,
      builder: (_, scroll) => Column(children: [
        const Padding(
          padding: EdgeInsets.fromLTRB(20, 0, 20, 4),
          child: Align(
            alignment: Alignment.centerLeft,
            child: Text('Standard checklists', style: TextStyle(fontWeight: FontWeight.w700, fontSize: 16)),
          ),
        ),
        const Padding(
          padding: EdgeInsets.fromLTRB(20, 0, 20, 8),
          child: Align(
            alignment: Alignment.centerLeft,
            child: Text('Add a ready-made daily round, then reword it to suit your society.',
                style: TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
          ),
        ),
        Expanded(
          child: async.when(
            loading: () => const AppLoader(),
            error: (e, _) => Center(
                child: Text(friendlyErrorMessage(e), style: const TextStyle(color: AppTheme.error))),
            data: (rows) => ListView(controller: scroll, children: [
              for (final c in rows)
                ExpansionTile(
                  key: ValueKey('std-${c.code}'),
                  leading: Checkbox(
                    value: c.alreadyAdded || _picked.contains(c.code),
                    onChanged: c.alreadyAdded
                        ? null
                        : (v) => setState(() => v == true ? _picked.add(c.code) : _picked.remove(c.code)),
                  ),
                  title: Text(c.name, style: const TextStyle(fontWeight: FontWeight.w600)),
                  subtitle: Text(
                    c.alreadyAdded
                        ? 'Already in your templates'
                        : 'For ${_department(c.department)} staff · ${c.itemCount} checks, '
                            '${c.requiredCount} must be ticked',
                    style: const TextStyle(fontSize: 12),
                  ),
                  children: [
                    for (final i in c.items)
                      ListTile(
                        dense: true,
                        leading: Icon(i.isRequired ? Icons.check_box_outlined : Icons.check_box_outline_blank,
                            size: 18, color: AppTheme.textSecondary),
                        title: Text(i.title, style: const TextStyle(fontSize: 13)),
                        subtitle: i.description != null ? Text(i.description!) : null,
                      ),
                  ],
                ),
            ]),
          ),
        ),
        SafeArea(
          top: false,
          child: Padding(
            padding: const EdgeInsets.fromLTRB(20, 8, 20, 12),
            child: SizedBox(
              width: double.infinity,
              child: ElevatedButton(
                key: const Key('add-standard-checklists'),
                onPressed: _picked.isEmpty || _saving ? null : _add,
                child: _saving
                    ? const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2))
                    : Text(_picked.isEmpty ? 'Pick a checklist to add' : 'Add ${_picked.length} to my templates'),
              ),
            ),
          ),
        ),
      ]),
    );
  }
}
