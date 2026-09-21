import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/features/staff/domain/entities/staff_entities.dart';
import 'package:ar_society_app/features/staff/presentation/providers/staff_providers.dart';

const kStaffDepartments = [
  ('security',     'Security'),
  ('housekeeping', 'Housekeeping'),
  ('technical',    'Technical'),
  ('gym',          'Gym'),
  ('maintenance',  'Maintenance'),
  ('electrical',   'Electrical'),
  ('plumbing',     'Plumbing'),
  ('gardening',    'Gardening'),
  ('amenities',    'Amenities'),
  ('admin',        'Administration'),
];

String departmentLabel(String value) =>
    kStaffDepartments.firstWhere((d) => d.$1 == value, orElse: () => (value, value)).$2;

/// Admin/Committee screen to define reusable, department-scoped duty
/// checklists (e.g. "Security Gate Round", "Room Turnover"). Assigning a
/// duty from one of these templates snapshots its items onto that duty —
/// see duty_assign_screen.dart and StaffService.assign_duty() on the
/// backend.
class ChecklistTemplatesScreen extends ConsumerStatefulWidget {
  const ChecklistTemplatesScreen({super.key});

  @override
  ConsumerState<ChecklistTemplatesScreen> createState() => _ChecklistTemplatesScreenState();
}

class _ChecklistTemplatesScreenState extends ConsumerState<ChecklistTemplatesScreen> {
  String? _departmentFilter;

  @override
  Widget build(BuildContext context) {
    final societyId = ref.watch(currentUserProvider)?.societyId;
    if (societyId == null) {
      return const Scaffold(body: Center(child: Text('No society context')));
    }
    final templatesAsync = ref.watch(checklistTemplatesProvider(societyId));

    return Scaffold(
      backgroundColor: AppTheme.surface,
      appBar: AppBar(
        title: const Text('Checklist Templates'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh_rounded),
            onPressed: () => ref.read(checklistTemplatesProvider(societyId).notifier).refresh(),
          ),
        ],
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () => _openEditor(context, societyId: societyId),
        icon: const Icon(Icons.add_rounded),
        label: const Text('New Template'),
      ),
      body: Column(
        children: [
          SizedBox(
            height: 48,
            child: ListView(
              scrollDirection: Axis.horizontal,
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
              children: [
                _FilterChip(label: 'All', selected: _departmentFilter == null,
                    onTap: () => setState(() => _departmentFilter = null)),
                for (final d in kStaffDepartments)
                  Padding(
                    padding: const EdgeInsets.only(left: 8),
                    child: _FilterChip(
                      label: d.$2, selected: _departmentFilter == d.$1,
                      onTap: () => setState(() => _departmentFilter = d.$1),
                    ),
                  ),
              ],
            ),
          ),
          Expanded(
            child: templatesAsync.when(
              loading: () => const Center(child: CircularProgressIndicator()),
              error: (e, _) => Center(
                  child: Text(friendlyErrorMessage(e), style: const TextStyle(color: AppTheme.error))),
              data: (templates) {
                final filtered = _departmentFilter == null
                    ? templates
                    : templates.where((t) => t.department == _departmentFilter).toList();
                if (filtered.isEmpty) {
                  return const Center(
                    child: Padding(
                      padding: EdgeInsets.all(24),
                      child: Text('No checklist templates yet. Tap "New Template" to create one.',
                          textAlign: TextAlign.center,
                          style: TextStyle(color: AppTheme.textSecondary)),
                    ),
                  );
                }
                return ListView.builder(
                  padding: const EdgeInsets.fromLTRB(16, 8, 16, 88),
                  itemCount: filtered.length,
                  itemBuilder: (_, i) => _TemplateCard(
                    template: filtered[i],
                    onEdit: () => _openEditor(context, societyId: societyId, existing: filtered[i]),
                    onDelete: () => _confirmDelete(context, societyId: societyId, template: filtered[i]),
                  ),
                );
              },
            ),
          ),
        ],
      ),
    );
  }

  Future<void> _confirmDelete(BuildContext context,
      {required String societyId, required ChecklistTemplateEntity template}) async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Delete Template?'),
        content: Text('Permanently delete "${template.name}"? Duties already using it keep their checklist.'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancel')),
          ElevatedButton(
            style: ElevatedButton.styleFrom(backgroundColor: AppTheme.error),
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('Delete'),
          ),
        ],
      ),
    );
    if (ok == true) {
      try {
        await ref.read(checklistTemplatesProvider(societyId).notifier).delete(template.id);
      } catch (e) {
        if (context.mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
              SnackBar(content: Text(friendlyErrorMessage(e)), backgroundColor: AppTheme.error));
        }
      }
    }
  }

  void _openEditor(BuildContext context,
      {required String societyId, ChecklistTemplateEntity? existing}) {
    Navigator.push(context, MaterialPageRoute(
      builder: (_) => _TemplateEditorScreen(societyId: societyId, existing: existing),
    ));
  }
}

class _FilterChip extends StatelessWidget {
  final String label;
  final bool selected;
  final VoidCallback onTap;
  const _FilterChip({required this.label, required this.selected, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return ChoiceChip(
      label: Text(label, style: const TextStyle(fontSize: 12)),
      selected: selected,
      onSelected: (_) => onTap(),
      selectedColor: AppTheme.primary.withOpacity(0.15),
      labelStyle: TextStyle(color: selected ? AppTheme.primary : AppTheme.textSecondary),
    );
  }
}

class _TemplateCard extends StatelessWidget {
  final ChecklistTemplateEntity template;
  final VoidCallback onEdit;
  final VoidCallback onDelete;
  const _TemplateCard({required this.template, required this.onEdit, required this.onDelete});

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      child: ExpansionTile(
        title: Text(template.name, style: const TextStyle(fontWeight: FontWeight.w600)),
        subtitle: Text('${departmentLabel(template.department)} · ${template.items.length} item(s)'),
        trailing: Row(mainAxisSize: MainAxisSize.min, children: [
          IconButton(icon: const Icon(Icons.edit_outlined), onPressed: onEdit),
          IconButton(icon: const Icon(Icons.delete_outline, color: AppTheme.error), onPressed: onDelete),
        ]),
        children: [
          for (final item in template.items)
            ListTile(
              dense: true,
              leading: Icon(item.isRequired ? Icons.check_box_outlined : Icons.check_box_outline_blank,
                  size: 18, color: AppTheme.textSecondary),
              title: Text(item.title, style: const TextStyle(fontSize: 13)),
              subtitle: item.description != null ? Text(item.description!) : null,
            ),
        ],
      ),
    );
  }
}

class _TemplateEditorScreen extends ConsumerStatefulWidget {
  final String societyId;
  final ChecklistTemplateEntity? existing;
  const _TemplateEditorScreen({required this.societyId, this.existing});

  @override
  ConsumerState<_TemplateEditorScreen> createState() => _TemplateEditorScreenState();
}

class _ItemDraft {
  final TextEditingController titleCtrl;
  bool isRequired;
  _ItemDraft({String title = '', this.isRequired = true}) : titleCtrl = TextEditingController(text: title);
}

class _TemplateEditorScreenState extends ConsumerState<_TemplateEditorScreen> {
  late final TextEditingController _nameCtrl;
  late final TextEditingController _descCtrl;
  late String _department;
  final List<_ItemDraft> _items = [];
  bool _saving = false;

  @override
  void initState() {
    super.initState();
    final e = widget.existing;
    _nameCtrl = TextEditingController(text: e?.name ?? '');
    _descCtrl = TextEditingController(text: e?.description ?? '');
    _department = e?.department ?? kStaffDepartments.first.$1;
    if (e != null && e.items.isNotEmpty) {
      _items.addAll(e.items.map((i) => _ItemDraft(title: i.title, isRequired: i.isRequired)));
    } else {
      _items.add(_ItemDraft());
    }
  }

  @override
  void dispose() {
    _nameCtrl.dispose();
    _descCtrl.dispose();
    for (final i in _items) { i.titleCtrl.dispose(); }
    super.dispose();
  }

  Future<void> _save() async {
    final name = _nameCtrl.text.trim();
    final items = _items
        .where((i) => i.titleCtrl.text.trim().isNotEmpty)
        .toList();
    if (name.isEmpty || items.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
        content: Text('Name and at least one checklist item are required'),
        backgroundColor: AppTheme.error,
      ));
      return;
    }

    setState(() => _saving = true);
    final itemPayload = [
      for (var i = 0; i < items.length; i++)
        {'title': items[i].titleCtrl.text.trim(), 'sequence': i, 'is_required': items[i].isRequired},
    ];
    try {
      final notifier = ref.read(checklistTemplatesProvider(widget.societyId).notifier);
      if (widget.existing == null) {
        await notifier.create(
          department: _department, name: name,
          description: _descCtrl.text.trim().isEmpty ? null : _descCtrl.text.trim(),
          items: itemPayload,
        );
      } else {
        await notifier.updateTemplate(
          widget.existing!.id, name: name, department: _department,
          description: _descCtrl.text.trim().isEmpty ? null : _descCtrl.text.trim(),
          items: itemPayload,
        );
      }
      if (mounted) Navigator.pop(context);
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text(friendlyErrorMessage(e)), backgroundColor: AppTheme.error));
      }
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppTheme.surface,
      appBar: AppBar(title: Text(widget.existing == null ? 'New Template' : 'Edit Template')),
      body: ListView(
        padding: const EdgeInsets.all(20),
        children: [
          DropdownButtonFormField<String>(
            value: _department,
            decoration: const InputDecoration(labelText: 'Department *'),
            items: [for (final d in kStaffDepartments) DropdownMenuItem(value: d.$1, child: Text(d.$2))],
            onChanged: (v) => setState(() => _department = v ?? _department),
          ),
          const SizedBox(height: 14),
          TextField(
            controller: _nameCtrl,
            decoration: const InputDecoration(labelText: 'Template Name *', hintText: 'e.g. Security Gate Round'),
          ),
          const SizedBox(height: 14),
          TextField(
            controller: _descCtrl,
            maxLines: 2,
            decoration: const InputDecoration(labelText: 'Description (optional)'),
          ),
          const SizedBox(height: 20),
          const Text('Checklist Items', style: TextStyle(fontWeight: FontWeight.w700, fontSize: 14)),
          const SizedBox(height: 8),
          for (var i = 0; i < _items.length; i++)
            Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: Row(children: [
                Expanded(
                  child: TextField(
                    controller: _items[i].titleCtrl,
                    decoration: InputDecoration(hintText: 'Item ${i + 1}', isDense: true),
                  ),
                ),
                Checkbox(
                  value: _items[i].isRequired,
                  onChanged: (v) => setState(() => _items[i].isRequired = v ?? true),
                ),
                const Text('Required', style: TextStyle(fontSize: 11)),
                IconButton(
                  icon: const Icon(Icons.remove_circle_outline, size: 20, color: AppTheme.error),
                  onPressed: _items.length <= 1 ? null : () => setState(() => _items.removeAt(i)),
                ),
              ]),
            ),
          TextButton.icon(
            onPressed: () => setState(() => _items.add(_ItemDraft())),
            icon: const Icon(Icons.add_rounded),
            label: const Text('Add Item'),
          ),
          const SizedBox(height: 20),
          ElevatedButton(
            onPressed: _saving ? null : _save,
            child: _saving
                ? const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2))
                : const Text('Save Template'),
          ),
        ],
      ),
    );
  }
}
