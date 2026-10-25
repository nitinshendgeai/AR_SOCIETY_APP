import 'package:flutter/material.dart';
import 'package:ar_society_app/features/staff/domain/entities/staff_entities.dart';
import 'package:ar_society_app/shared/widgets/app_form.dart';

/// Who a staff member can report to. The server stores a login (user id), so only
/// staff with a login can be saved; the others are listed greyed out so it is clear
/// why they cannot be picked. Anyone active can be chosen, not just managers.
class ReportingManagerField extends StatelessWidget {
  final List<StaffEntity> allStaff;
  final String? selectedUserId;
  /// The staff member being edited (never offered as their own manager); null when adding.
  final String? excludeStaffId;
  final ValueChanged<String?> onChanged;

  const ReportingManagerField({
    super.key,
    required this.allStaff,
    required this.selectedUserId,
    required this.onChanged,
    this.excludeStaffId,
  });

  static bool _isOff(StaffEntity s) => s.status == 'inactive' || s.status == 'terminated';

  @override
  Widget build(BuildContext context) {
    // A manager who has since left stays listed while chosen, so the form still shows who it is.
    final others = allStaff
        .where((s) => s.id != excludeStaffId)
        .where((s) => !_isOff(s) || (s.userId != null && s.userId == selectedUserId))
        .toList()
      ..sort((a, b) => a.fullName.toLowerCase().compareTo(b.fullName.toLowerCase()));
    final withLogin = others.where((s) => s.userId != null).toList();
    final withoutLogin = others.where((s) => s.userId == null).toList();

    String label(StaffEntity s) => '${s.fullName} (${s.departmentLabel})';

    return FormFieldBox(
      label: 'Reporting manager',
      child: DropdownButtonFormField<String>(
        isExpanded: true,
        value: withLogin.any((s) => s.userId == selectedUserId) ? selectedUserId : null,
        decoration: const InputDecoration(hintText: 'Select reporting manager'),
        items: [
          const DropdownMenuItem(value: null, child: Text('No reporting manager')),
          ...withLogin.map((s) => DropdownMenuItem(
                value: s.userId,
                child: Text(label(s), overflow: TextOverflow.ellipsis),
              )),
          // Distinct placeholder values, so they never collide with "no manager".
          ...withoutLogin.map((s) => DropdownMenuItem(
                value: 'nologin:${s.id}',
                enabled: false,
                child: Text('${label(s)} · no login', overflow: TextOverflow.ellipsis,
                    style: TextStyle(color: Theme.of(context).disabledColor)),
              )),
        ],
        onChanged: onChanged,
      ),
    );
  }
}
