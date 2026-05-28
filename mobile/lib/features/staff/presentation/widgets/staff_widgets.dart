import 'package:flutter/material.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/staff/domain/entities/staff_entities.dart';

// ── Status badge ──────────────────────────────────────────────────────────────

class AttendanceStatusBadge extends StatelessWidget {
  final AttendanceStatus status;
  const AttendanceStatusBadge({super.key, required this.status});

  Color get _color {
    switch (status) {
      case AttendanceStatus.present:  return AppTheme.success;
      case AttendanceStatus.absent:   return AppTheme.error;
      case AttendanceStatus.halfDay:  return AppTheme.warning;
      case AttendanceStatus.leave:    return AppTheme.secondary;
      case AttendanceStatus.overtime: return AppTheme.primary;
      case AttendanceStatus.offDuty:  return AppTheme.textSecondary;
    }
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: _color.withOpacity(0.12),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: _color.withOpacity(0.3)),
      ),
      child: Text(
        status.label,
        style: TextStyle(color: _color, fontSize: 12, fontWeight: FontWeight.w600),
      ),
    );
  }
}

// ── Handover status badge ─────────────────────────────────────────────────────

class HandoverStatusBadge extends StatelessWidget {
  final HandoverStatus status;
  const HandoverStatusBadge({super.key, required this.status});

  Color get _color {
    switch (status) {
      case HandoverStatus.draft:     return AppTheme.textSecondary;
      case HandoverStatus.submitted: return AppTheme.warning;
      case HandoverStatus.accepted:  return AppTheme.success;
      case HandoverStatus.disputed:  return AppTheme.error;
      case HandoverStatus.verified:  return AppTheme.primary;
      case HandoverStatus.closed:    return AppTheme.textSecondary;
    }
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: _color.withOpacity(0.12),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: _color.withOpacity(0.3)),
      ),
      child: Text(
        status.label,
        style: TextStyle(color: _color, fontSize: 12, fontWeight: FontWeight.w600),
      ),
    );
  }
}

// ── Info row ──────────────────────────────────────────────────────────────────

class InfoRow extends StatelessWidget {
  final IconData icon;
  final String label;
  final String value;
  final Color? valueColor;

  const InfoRow({
    super.key,
    required this.icon,
    required this.label,
    required this.value,
    this.valueColor,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Row(
        children: [
          Icon(icon, size: 16, color: AppTheme.textSecondary),
          const SizedBox(width: 10),
          Text(label,
              style: const TextStyle(color: AppTheme.textSecondary, fontSize: 13)),
          const Spacer(),
          Text(value,
              style: TextStyle(
                  fontWeight: FontWeight.w600,
                  fontSize: 13,
                  color: valueColor ?? AppTheme.textPrimary)),
        ],
      ),
    );
  }
}

// ── Section header ────────────────────────────────────────────────────────────

class SectionHeader extends StatelessWidget {
  final String title;
  final Widget? trailing;
  const SectionHeader({super.key, required this.title, this.trailing});

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Text(title,
            style: const TextStyle(
                fontSize: 15,
                fontWeight: FontWeight.w700,
                color: AppTheme.textPrimary)),
        const Spacer(),
        if (trailing != null) trailing!,
      ],
    );
  }
}

// ── Empty state ───────────────────────────────────────────────────────────────

class EmptyState extends StatelessWidget {
  final IconData icon;
  final String title;
  final String? subtitle;

  const EmptyState({
    super.key,
    required this.icon,
    required this.title,
    this.subtitle,
  });

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
                style: const TextStyle(
                    fontSize: 15,
                    fontWeight: FontWeight.w600,
                    color: AppTheme.textSecondary)),
            if (subtitle != null) ...[
              const SizedBox(height: 6),
              Text(subtitle!,
                  textAlign: TextAlign.center,
                  style: const TextStyle(
                      fontSize: 13, color: AppTheme.textSecondary)),
            ]
          ],
        ),
      ),
    );
  }
}

// ── Card tile ─────────────────────────────────────────────────────────────────

class AppCard extends StatelessWidget {
  final Widget child;
  final VoidCallback? onTap;
  final EdgeInsetsGeometry padding;

  const AppCard({
    super.key,
    required this.child,
    this.onTap,
    this.padding = const EdgeInsets.all(16),
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: padding,
        decoration: BoxDecoration(
          color: AppTheme.cardBg,
          borderRadius: BorderRadius.circular(14),
          border: Border.all(color: AppTheme.border),
        ),
        child: child,
      ),
    );
  }
}

// ── Time display ──────────────────────────────────────────────────────────────

String formatTime(DateTime? dt) {
  if (dt == null) return '--:--';
  final h = dt.hour.toString().padLeft(2, '0');
  final m = dt.minute.toString().padLeft(2, '0');
  return '$h:$m';
}

String formatHours(double? hours) {
  if (hours == null) return '--';
  final h = hours.floor();
  final m = ((hours - h) * 60).round();
  return '${h}h ${m}m';
}

String formatDate(String? dateStr) {
  if (dateStr == null) return '--';
  try {
    final dt = DateTime.parse(dateStr);
    const months = ['Jan','Feb','Mar','Apr','May','Jun',
                    'Jul','Aug','Sep','Oct','Nov','Dec'];
    return '${dt.day} ${months[dt.month - 1]} ${dt.year}';
  } catch (_) { return dateStr; }
}
