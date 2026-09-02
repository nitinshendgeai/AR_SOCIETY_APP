import 'package:flutter/material.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/resident_master/data/models/resident_master_models.dart';

// ── Resident type badge ──────────────────────────────────────────────────

class ResidentTypeBadge extends StatelessWidget {
  final ResidentType type;
  const ResidentTypeBadge({super.key, required this.type});

  Color get _color => switch (type) {
        ResidentType.owner => AppTheme.success,
        ResidentType.coOwner => AppTheme.secondary,
        ResidentType.family => AppTheme.primary,
        ResidentType.dependent => AppTheme.textSecondary,
      };

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: _color.withOpacity(0.12),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: _color.withOpacity(0.3)),
      ),
      child: Text(type.label,
          style: TextStyle(color: _color, fontSize: 11, fontWeight: FontWeight.w700)),
    );
  }
}

// ── Primary indicator ────────────────────────────────────────────────────

class PrimaryChip extends StatelessWidget {
  const PrimaryChip({super.key});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: AppTheme.warning.withOpacity(0.12),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: AppTheme.warning.withOpacity(0.3)),
      ),
      child: const Row(mainAxisSize: MainAxisSize.min, children: [
        Icon(Icons.star_rounded, size: 12, color: AppTheme.warning),
        SizedBox(width: 3),
        Text('PRIMARY',
            style: TextStyle(color: AppTheme.warning, fontSize: 10, fontWeight: FontWeight.w700)),
      ]),
    );
  }
}

// ── Agreement status badge ───────────────────────────────────────────────

class AgreementStatusBadge extends StatelessWidget {
  final AgreementStatus status;
  const AgreementStatusBadge({super.key, required this.status});

  Color get _color => switch (status) {
        AgreementStatus.active => AppTheme.success,
        AgreementStatus.expired => AppTheme.error,
        AgreementStatus.renewed => AppTheme.textSecondary,
        AgreementStatus.terminated => AppTheme.error,
      };

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: _color.withOpacity(0.12),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: _color.withOpacity(0.3)),
      ),
      child: Text(status.label.toUpperCase(),
          style: TextStyle(color: _color, fontSize: 10, fontWeight: FontWeight.w700)),
    );
  }
}

// ── Active/Inactive badge ────────────────────────────────────────────────

class ActiveBadge extends StatelessWidget {
  final bool isActive;
  const ActiveBadge({super.key, required this.isActive});

  @override
  Widget build(BuildContext context) {
    final color = isActive ? AppTheme.success : AppTheme.textSecondary;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: color.withOpacity(0.12),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: color.withOpacity(0.3)),
      ),
      child: Text(isActive ? 'ACTIVE' : 'INACTIVE',
          style: TextStyle(color: color, fontSize: 10, fontWeight: FontWeight.w700)),
    );
  }
}

// ── Section (card with title) ────────────────────────────────────────────

class RmSection extends StatelessWidget {
  final String title;
  final Widget? trailing;
  final List<Widget> children;
  const RmSection({super.key, required this.title, this.trailing, required this.children});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppTheme.cardBg,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: AppTheme.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(children: [
            Text(title,
                style: const TextStyle(
                    fontSize: 13, fontWeight: FontWeight.w700,
                    color: AppTheme.primary, letterSpacing: 0.4)),
            const Spacer(),
            if (trailing != null) trailing!,
          ]),
          const SizedBox(height: 12),
          ...children,
        ],
      ),
    );
  }
}

// ── Label/value row ───────────────────────────────────────────────────────

class RmRow extends StatelessWidget {
  final String label;
  final String value;
  const RmRow({super.key, required this.label, required this.value});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 130,
            child: Text(label,
                style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary, fontWeight: FontWeight.w500)),
          ),
          Expanded(
            child: Text(value,
                style: const TextStyle(fontSize: 13, color: AppTheme.textPrimary, fontWeight: FontWeight.w600)),
          ),
        ],
      ),
    );
  }
}

// ── Empty state ───────────────────────────────────────────────────────────

class RmEmptyState extends StatelessWidget {
  final IconData icon;
  final String title;
  final String? subtitle;
  const RmEmptyState({super.key, required this.icon, required this.title, this.subtitle});

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, size: 48, color: AppTheme.border),
            const SizedBox(height: 16),
            Text(title,
                style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w600, color: AppTheme.textSecondary)),
            if (subtitle != null) ...[
              const SizedBox(height: 6),
              Text(subtitle!,
                  textAlign: TextAlign.center,
                  style: const TextStyle(fontSize: 13, color: AppTheme.textSecondary)),
            ],
          ],
        ),
      ),
    );
  }
}

// ── Form section header + field wrapper (mirrors staff_add/edit_screen) ────

class RmSectionHeader extends StatelessWidget {
  final String text;
  const RmSectionHeader(this.text, {super.key});

  @override
  Widget build(BuildContext context) => Text(
        text,
        style: const TextStyle(
            fontSize: 13, fontWeight: FontWeight.w700, color: AppTheme.primary, letterSpacing: 0.4),
      );
}

class RmFormField extends StatelessWidget {
  final String label;
  final Widget child;
  const RmFormField({super.key, required this.label, required this.child});

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.only(bottom: 16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(label,
                style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: AppTheme.textSecondary)),
            const SizedBox(height: 6),
            child,
          ],
        ),
      );
}

// ── Date formatting (kept local to this feature — see staff_widgets.dart
// for the equivalent used by the Staff module; not shared cross-feature) ──

String rmFormatDate(String? dateStr) {
  if (dateStr == null) return '—';
  try {
    final dt = DateTime.parse(dateStr);
    const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    return '${dt.day} ${months[dt.month - 1]} ${dt.year}';
  } catch (_) {
    return dateStr;
  }
}

// ── Error message mapping (Phase M1.4 §26) ─────────────────────────────────
//
// Never surface a raw Exception/Dio dump to the user. ResidentMasterRepository
// already maps most Dio failures into business-friendly `detail` text (see
// parseApiError in core/api/api_client.dart), but that shared helper still
// passes through the backend's raw "Access requires one of roles: ..." 403
// text verbatim (it isn't a recognized business-error shape) — catch that
// case here rather than modifying the cross-feature shared parser.
String rmFriendlyError(Object e) {
  final msg = e.toString().replaceFirst('Exception: ', '');
  final lower = msg.toLowerCase();
  if (lower.contains('access requires') || lower.contains('permission denied')) {
    return 'You do not have permission to view this.';
  }
  if (lower.contains('not found')) {
    return 'Unable to access this record.';
  }
  if (lower.isEmpty) return 'Something went wrong. Please try again.';
  return msg;
}

// ── Phone validation (certification gap: "abc123" previously accepted) ─────
//
// Mirrors the backend's validate_mobile_number (app/utils/phone.py): if
// provided, a phone number must reduce to a 10-digit number starting with
// 6-9, ignoring spaces/dashes and an optional +91/91/0 prefix. Shared by
// the Resident and Tenant forms so both stay consistent (Phase M1.9-R2 §3).
final RegExp _rmMobileRegExp = RegExp(r'^[6-9]\d{9}$');

String? rmPhoneValidator(String? v) {
  if (v == null || v.trim().isEmpty) return null;
  var digits = v.trim().replaceAll(RegExp(r'[\s\-()]'), '');
  if (digits.startsWith('+91')) {
    digits = digits.substring(3);
  } else if (digits.startsWith('91') && digits.length == 12) {
    digits = digits.substring(2);
  } else if (digits.startsWith('0') && digits.length == 11) {
    digits = digits.substring(1);
  }
  if (!_rmMobileRegExp.hasMatch(digits)) {
    return 'Enter a valid 10-digit mobile number';
  }
  return null;
}

/// Days remaining until [dateStr]; negative if already past.
int? rmDaysUntil(String? dateStr) {
  if (dateStr == null) return null;
  try {
    final dt = DateTime.parse(dateStr);
    final today = DateTime.now();
    final d0 = DateTime(today.year, today.month, today.day);
    return dt.difference(d0).inDays;
  } catch (_) {
    return null;
  }
}
