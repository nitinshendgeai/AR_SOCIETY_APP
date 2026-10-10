import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:ar_society_app/core/l10n/app_locale.dart';
import 'package:ar_society_app/core/layout/app_shell.dart' show kDesktopBreakpoint;
import 'package:ar_society_app/core/motion/motion.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';

/// The one layout for a full-page form: a header (back, title, what this is for), the fields grouped into
/// titled cards laid out in columns on a wide screen, and an action bar that stays at the bottom while the
/// page scrolls. Header, cards and bar share one content width, so everything lines up.
///
/// ```dart
/// AppFormPage(
///   title: 'Add Resident',
///   subtitle: 'Add a person to a flat',
///   formKey: _formKey,
///   submitLabel: 'Add Resident',
///   saving: isLoading,
///   onSubmit: _submit,
///   children: [
///     FormSection(title: 'Personal information', children: [
///       FormFieldBox(label: 'Full name', required: true, child: TextFormField(...)),
///       ...
///     ]),
///   ],
/// )
/// ```
class AppFormPage extends StatelessWidget {
  final String title;
  final String? subtitle;
  final GlobalKey<FormState>? formKey;
  final List<Widget> children;
  final String submitLabel;
  final IconData? submitIcon;
  final VoidCallback? onSubmit;
  final bool saving;

  /// Defaults to going back.
  final VoidCallback? onCancel;

  /// Small widgets beside the title (a status chip), and extra buttons on the right of the action bar's left side.
  final Widget? status;
  final Widget? footerNote;
  final double maxWidth;

  /// Buttons at the right of the header (a link to a related report) and extra buttons in the action bar before
  /// the main one (for example "Save and add another").
  final List<Widget> actions;
  final List<Widget> extraActions;

  const AppFormPage({
    super.key,
    required this.title,
    this.subtitle,
    this.formKey,
    required this.children,
    required this.submitLabel,
    this.submitIcon,
    this.onSubmit,
    this.saving = false,
    this.onCancel,
    this.status,
    this.footerNote,
    this.maxWidth = 1080,
    this.actions = const [],
    this.extraActions = const [],
  });

  @override
  Widget build(BuildContext context) {
    final desktop = MediaQuery.sizeOf(context).width >= kDesktopBreakpoint;
    final gutter = desktop ? 32.0 : 16.0;
    void back() => onCancel != null ? onCancel!() : (context.canPop() ? context.pop() : Navigator.maybePop(context));

    Widget column(Widget child) => Align(
          alignment: Alignment.topCenter,
          child: ConstrainedBox(constraints: BoxConstraints(maxWidth: maxWidth), child: child),
        );

    // A plain scroll view, not a lazy ListView: fields scrolled out of view stay mounted, so validate() checks
    // every one of them.
    final body = SingleChildScrollView(
      padding: EdgeInsets.fromLTRB(gutter, desktop ? 8 : 16, gutter, 28),
      child: column(Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        for (var i = 0; i < children.length; i++) ...[
          if (i > 0) const SizedBox(height: 20),
          AppReveal(index: i, child: children[i]),
        ],
      ])),
    );

    return Scaffold(
      backgroundColor: AppTheme.surface,
      // Phones keep the standard app bar (its back button is where people expect it); the desktop page gets the
      // fuller header below.
      appBar: desktop ? null : AppBar(title: Text(context.tr(title)), actions: actions),
      body: Column(children: [
        if (desktop)
          Padding(
            padding: EdgeInsets.fromLTRB(gutter, 24, gutter, 16),
            child: column(_Header(title: title, subtitle: subtitle, status: status, actions: actions, onBack: back)),
          ),
        Expanded(child: formKey == null ? body : Form(key: formKey, child: body)),
        _ActionBar(
          gutter: gutter,
          maxWidth: maxWidth,
          desktop: desktop,
          note: footerNote,
          extra: extraActions,
          submitLabel: submitLabel,
          submitIcon: submitIcon,
          saving: saving,
          onSubmit: onSubmit,
          onCancel: back,
        ),
      ]),
    );
  }
}

class _Header extends StatelessWidget {
  final String title;
  final String? subtitle;
  final Widget? status;
  final List<Widget> actions;
  final VoidCallback onBack;
  const _Header({required this.title, this.subtitle, this.status, this.actions = const [], required this.onBack});

  @override
  Widget build(BuildContext context) {
    return Row(crossAxisAlignment: CrossAxisAlignment.center, children: [
      IconButton.outlined(
        tooltip: context.tr('Back'),
        onPressed: onBack,
        icon: const Icon(Icons.arrow_back_rounded, size: 20),
        style: IconButton.styleFrom(
          backgroundColor: AppTheme.cardBg,
          side: const BorderSide(color: AppTheme.fieldBorder),
          fixedSize: const Size(40, 40),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
        ),
      ),
      const SizedBox(width: 16),
      Expanded(
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, mainAxisSize: MainAxisSize.min, children: [
          Row(children: [
            Flexible(
              child: Text(context.tr(title),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(fontSize: 24, fontWeight: FontWeight.w700, height: 1.2, color: AppTheme.textPrimary)),
            ),
            if (status != null) ...[const SizedBox(width: 12), status!],
          ]),
          if (subtitle != null) ...[
            const SizedBox(height: 2),
            Text(context.tr(subtitle!), style: const TextStyle(fontSize: 14, color: AppTheme.textSecondary)),
          ],
        ]),
      ),
      for (final a in actions) ...[const SizedBox(width: 8), a],
    ]);
  }
}

class _ActionBar extends StatelessWidget {
  final double gutter;
  final double maxWidth;
  final bool desktop;
  final Widget? note;
  final List<Widget> extra;
  final String submitLabel;
  final IconData? submitIcon;
  final bool saving;
  final VoidCallback? onSubmit;
  final VoidCallback onCancel;
  const _ActionBar({
    required this.gutter,
    required this.maxWidth,
    required this.desktop,
    required this.note,
    required this.extra,
    required this.submitLabel,
    required this.submitIcon,
    required this.saving,
    required this.onSubmit,
    required this.onCancel,
  });

  @override
  Widget build(BuildContext context) {
    final submit = AppPrimaryButton(
      label: context.tr(submitLabel),
      icon: submitIcon,
      isLoading: saving,
      expand: !desktop,
      onPressed: onSubmit,
    );
    return Container(
      decoration: const BoxDecoration(
        color: AppTheme.cardBg,
        border: Border(top: BorderSide(color: AppTheme.border)),
        boxShadow: [BoxShadow(color: Color(0x0F000000), blurRadius: 12, offset: Offset(0, -2))],
      ),
      padding: EdgeInsets.fromLTRB(gutter, 12, gutter, 12),
      child: SafeArea(
        top: false,
        child: Align(
          alignment: Alignment.topCenter,
          child: ConstrainedBox(
            constraints: BoxConstraints(maxWidth: maxWidth),
            child: desktop
                ? Row(children: [
                    Expanded(
                      child: DefaultTextStyle.merge(
                        style: const TextStyle(fontSize: 13, color: AppTheme.textSecondary),
                        child: note ?? Text(context.tr('Fields marked * are required')),
                      ),
                    ),
                    OutlinedButton(
                      onPressed: saving ? null : onCancel,
                      style: OutlinedButton.styleFrom(minimumSize: const Size(100, 44)),
                      child: Text(context.tr('Cancel')),
                    ),
                    for (final e in extra) ...[const SizedBox(width: 12), e],
                    const SizedBox(width: 12),
                    submit,
                  ])
                : Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.stretch, children: [
                    for (final e in extra) ...[e, const SizedBox(height: 8)],
                    submit,
                  ]),
          ),
        ),
      ),
    );
  }
}

/// A titled card of related fields. On a wide screen the title and a line of explanation sit on the left and the
/// fields in columns on the right; on a narrow one they stack.
class FormSection extends StatelessWidget {
  final String title;
  final String? description;
  final List<Widget> children;

  /// Columns of fields on a wide screen (1 for a section of long fields).
  final int columns;
  final Widget? trailing;

  const FormSection({
    super.key,
    required this.title,
    this.description,
    required this.children,
    this.columns = 2,
    this.trailing,
  });

  @override
  Widget build(BuildContext context) {
    final heading = Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Text(context.tr(title),
          style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w700, color: AppTheme.textPrimary)),
      if (description != null) ...[
        const SizedBox(height: 6),
        Text(context.tr(description!),
            style: const TextStyle(fontSize: 13, height: 1.45, color: AppTheme.textSecondary)),
      ],
    ]);
    final fields = FormGrid(columns: columns, children: children);

    return DecoratedBox(
      decoration: BoxDecoration(
        color: AppTheme.cardBg,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: AppTheme.border),
      ),
      child: LayoutBuilder(builder: (context, box) {
        final split = box.maxWidth >= 860;
        return Padding(
          padding: EdgeInsets.all(split ? 28 : 20),
          child: split
              ? Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  SizedBox(width: 260, child: heading),
                  const SizedBox(width: 40),
                  Expanded(child: fields),
                ])
              : Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    Expanded(child: heading),
                    if (trailing != null) trailing!,
                  ]),
                  const SizedBox(height: 18),
                  fields,
                ]),
        );
      }),
    );
  }
}

/// Marks a field that should take a whole row of a [FormGrid] (an address, a note).
class FormFull extends StatelessWidget {
  final Widget child;
  const FormFull({super.key, required this.child});
  @override
  Widget build(BuildContext context) => child;
}

/// Lays fields out in equal columns (one on a narrow screen), rows aligned at the top.
class FormGrid extends StatelessWidget {
  final List<Widget> children;
  final int columns;
  final double gap;
  const FormGrid({super.key, required this.children, this.columns = 2, this.gap = 20});

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(builder: (context, box) {
      final cols = box.maxWidth >= 520 ? columns : 1;
      final cell = (box.maxWidth - gap * (cols - 1)) / cols;
      return Wrap(spacing: gap, runSpacing: 18, children: [
        for (final c in children)
          SizedBox(width: c is FormFull || cols == 1 ? box.maxWidth : cell, child: c),
      ]);
    });
  }
}

/// A label above a field: bold label, a red star when required, an optional line of help underneath.
class FormFieldBox extends StatelessWidget {
  final String label;
  final bool required;
  final String? helper;
  final Widget child;
  const FormFieldBox({super.key, required this.label, this.required = false, this.helper, required this.child});

  @override
  Widget build(BuildContext context) {
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Text.rich(TextSpan(children: [
        TextSpan(text: context.tr(label)),
        if (required) const TextSpan(text: ' *', style: TextStyle(color: AppTheme.error)),
      ]), style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: AppTheme.textPrimary)),
      const SizedBox(height: 6),
      child,
      if (helper != null) ...[
        const SizedBox(height: 5),
        Text(context.tr(helper!), style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
      ],
    ]);
  }
}

/// A yes/no setting as a bordered row: what it is, what it does, and the switch.
class FormSwitchTile extends StatelessWidget {
  final String title;
  final String? subtitle;
  final bool value;
  final ValueChanged<bool>? onChanged;
  const FormSwitchTile({super.key, required this.title, this.subtitle, required this.value, this.onChanged});

  @override
  Widget build(BuildContext context) {
    final enabled = onChanged != null;
    return DecoratedBox(
      decoration: BoxDecoration(
        color: value && enabled ? AppTheme.primarySoft.withOpacity(0.5) : AppTheme.cardBg,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: value && enabled ? AppTheme.primary.withOpacity(0.35) : AppTheme.fieldBorder),
      ),
      child: InkWell(
        borderRadius: BorderRadius.circular(10),
        onTap: enabled ? () => onChanged!(!value) : null,
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
          child: Row(children: [
            Expanded(
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text(context.tr(title),
                    style: TextStyle(
                        fontSize: 14, fontWeight: FontWeight.w600, color: enabled ? AppTheme.textPrimary : AppTheme.textTertiary)),
                if (subtitle != null)
                  Padding(
                    padding: const EdgeInsets.only(top: 2),
                    child: Text(context.tr(subtitle!),
                        style: const TextStyle(fontSize: 12.5, height: 1.35, color: AppTheme.textSecondary)),
                  ),
              ]),
            ),
            const SizedBox(width: 12),
            Switch(value: value, onChanged: onChanged),
          ]),
        ),
      ),
    );
  }
}

/// A date shown like a text field: tap to pick, a cross to clear.
class FormDateField extends StatelessWidget {
  final DateTime? value;
  final String hint;
  final String Function(DateTime) format;
  final VoidCallback onTap;
  final VoidCallback? onClear;
  final IconData icon;
  const FormDateField({
    super.key,
    required this.value,
    required this.hint,
    required this.onTap,
    required this.format,
    this.onClear,
    this.icon = Icons.calendar_today_rounded,
  });

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(8),
      child: InputDecorator(
        isEmpty: value == null,
        decoration: InputDecoration(
          prefixIcon: Icon(icon, size: 18, color: AppTheme.primary),
          suffixIcon: value != null && onClear != null
              ? IconButton(
                  tooltip: context.tr('Clear'),
                  icon: const Icon(Icons.close_rounded, size: 18, color: AppTheme.textSecondary),
                  onPressed: onClear)
              : null,
          hintText: hint,
        ),
        child: Text(value == null ? '' : format(value!),
            style: const TextStyle(fontSize: 14, color: AppTheme.textPrimary)),
      ),
    );
  }
}

/// The body of a form that opens in a sheet (a bottom sheet on a phone, a side panel on a computer): a header with
/// the title and what the sheet is for, a rule, then the fields. Used by every `showAppSheet` form so they look
/// like one product; fields inside should use [FormFieldBox] (label above) like the full-page forms.
class AppSheetFrame extends StatelessWidget {
  final String title;
  final String? subtitle;
  final Widget child;

  /// Buttons kept at the bottom of the panel while the fields scroll (optional; most sheets put theirs at the end
  /// of [child]).
  final Widget? footer;
  const AppSheetFrame({super.key, required this.title, this.subtitle, required this.child, this.footer});

  @override
  Widget build(BuildContext context) {
    final desktop = MediaQuery.sizeOf(context).width >= kDesktopBreakpoint;
    final header = Padding(
      // On a computer the panel's close button sits at the right.
      padding: EdgeInsets.fromLTRB(desktop ? 28 : 20, desktop ? 24 : 6, desktop ? 64 : 20, 16),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text(context.tr(title),
            style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w700, height: 1.25, color: AppTheme.textPrimary)),
        if (subtitle != null) ...[
          const SizedBox(height: 3),
          Text(context.tr(subtitle!), style: const TextStyle(fontSize: 13.5, height: 1.4, color: AppTheme.textSecondary)),
        ],
      ]),
    );
    final bottomInset = MediaQuery.viewInsetsOf(context).bottom;
    final body = SingleChildScrollView(
      padding: EdgeInsets.fromLTRB(desktop ? 28 : 20, 20, desktop ? 28 : 20, 24 + (desktop ? 0 : bottomInset)),
      child: child,
    );

    if (desktop) {
      return SizedBox.expand(
        child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          header,
          const Divider(height: 1),
          Expanded(child: body),
          if (footer != null) ...[
            const Divider(height: 1),
            Padding(padding: const EdgeInsets.fromLTRB(28, 14, 28, 18), child: footer),
          ],
        ]),
      );
    }
    return Container(
      constraints: BoxConstraints(maxHeight: MediaQuery.sizeOf(context).height * 0.92),
      decoration: const BoxDecoration(
        color: AppTheme.cardBg,
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      child: SafeArea(
        top: false,
        child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          const SizedBox(height: 8),
          Center(
            child: Container(
              width: 36,
              height: 4,
              decoration: BoxDecoration(color: AppTheme.border, borderRadius: BorderRadius.circular(2)),
            ),
          ),
          header,
          const Divider(height: 1),
          Flexible(child: body),
          if (footer != null) ...[
            const Divider(height: 1),
            Padding(padding: EdgeInsets.fromLTRB(20, 12, 20, 12 + bottomInset), child: footer),
          ],
        ]),
      ),
    );
  }
}

/// The title row of a page that is not a form (settings, a list): title, a line under it, buttons at the right.
/// Lines up with [SettingsColumn] below it.
class AppPageHeader extends StatelessWidget {
  final String title;
  final String? subtitle;
  final List<Widget> actions;
  const AppPageHeader({super.key, required this.title, this.subtitle, this.actions = const []});

  @override
  Widget build(BuildContext context) {
    return Row(crossAxisAlignment: CrossAxisAlignment.center, children: [
      Expanded(
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, mainAxisSize: MainAxisSize.min, children: [
          Text(context.tr(title),
              style: const TextStyle(fontSize: 24, fontWeight: FontWeight.w700, height: 1.2, color: AppTheme.textPrimary)),
          if (subtitle != null) ...[
            const SizedBox(height: 2),
            Text(context.tr(subtitle!), style: const TextStyle(fontSize: 14, color: AppTheme.textSecondary)),
          ],
        ]),
      ),
      for (final a in actions) ...[const SizedBox(width: 8), a],
    ]);
  }
}

/// A scrolling column of [FormSection]s on one content width (a tab of settings), with the save button at the end.
class SettingsColumn extends StatelessWidget {
  final List<Widget> children;
  final Widget? save;
  final double maxWidth;
  const SettingsColumn({super.key, required this.children, this.save, this.maxWidth = 1080});

  @override
  Widget build(BuildContext context) {
    final desktop = MediaQuery.sizeOf(context).width >= kDesktopBreakpoint;
    final gutter = desktop ? 32.0 : 16.0;
    return SingleChildScrollView(
      padding: EdgeInsets.fromLTRB(gutter, 20, gutter, 32),
      child: Align(
        alignment: Alignment.topCenter,
        child: ConstrainedBox(
          constraints: BoxConstraints(maxWidth: maxWidth),
          child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
            for (var i = 0; i < children.length; i++) ...[
              if (i > 0) const SizedBox(height: 20),
              AppReveal(index: i, child: children[i]),
            ],
            if (save != null) ...[
              const SizedBox(height: 20),
              Align(alignment: Alignment.centerRight, child: save),
            ],
          ]),
        ),
      ),
    );
  }
}
