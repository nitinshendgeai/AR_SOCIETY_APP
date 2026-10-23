import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';

/// A field you type into to find one of a list — the way a ledger is chosen in an accounting program.
///
/// - Focus it and the whole list drops down; typing narrows it (every word typed must appear in the name).
/// - Up and Down move through the list, **Enter** takes the highlighted one and moves on to the next field.
/// - With something already chosen and nothing typed, Enter just moves on.
/// - Leaving the field with half a word typed puts the chosen value back.
/// - With [onCreate], a name that is not in the list can be made on the spot: the list offers **Create "name"**, and
///   Enter (when nothing matches) or Alt+C does it, the way Tally's Alt+C makes a ledger from inside a voucher.
///
/// On a phone, where a drop-down above the keyboard is cramped, use the screen's own picker sheet instead.
class TypeaheadField<T extends Object> extends StatefulWidget {
  final List<T> options;
  final T? value;
  final String Function(T) label;

  /// A smaller line to the right of each option (its group, its code).
  final String? Function(T)? detail;

  /// Extra words each option answers to, besides its label.
  final String Function(T)? searchText;
  final ValueChanged<T> onSelected;
  final String hint;
  final FocusNode? focusNode;
  final bool autofocus;
  final bool enabled;
  final String? errorText;

  /// Move to the next field once an option is chosen (the default).
  final bool advanceOnSelect;

  /// Makes a new option from what was typed and returns it (null: cancelled). Without it nothing can be created here.
  final Future<T?> Function(String name)? onCreate;

  const TypeaheadField({
    super.key,
    required this.options,
    required this.value,
    required this.label,
    required this.onSelected,
    this.detail,
    this.searchText,
    this.hint = 'Type to search',
    this.focusNode,
    this.autofocus = false,
    this.enabled = true,
    this.errorText,
    this.advanceOnSelect = true,
    this.onCreate,
  });

  @override
  State<TypeaheadField<T>> createState() => _TypeaheadFieldState<T>();
}

class _TypeaheadFieldState<T extends Object> extends State<TypeaheadField<T>> {
  late final TextEditingController _controller = TextEditingController(text: _valueText());
  FocusNode? _ownNode;
  FocusNode get _node => widget.focusNode ?? (_ownNode ??= FocusNode());

  String _valueText() => widget.value == null ? '' : widget.label(widget.value as T);

  @override
  void initState() {
    super.initState();
    _node.addListener(_onFocus);
  }

  @override
  void didUpdateWidget(covariant TypeaheadField<T> old) {
    super.didUpdateWidget(old);
    if (old.focusNode != widget.focusNode) {
      (old.focusNode ?? _ownNode)?.removeListener(_onFocus);
      _node.addListener(_onFocus);
    }
    // The value changed from outside (a form was reset, another field's choice narrowed this one's list).
    if (!_node.hasFocus && _controller.text != _valueText()) _controller.text = _valueText();
  }

  @override
  void dispose() {
    _node.removeListener(_onFocus);
    _ownNode?.dispose();
    _controller.dispose();
    super.dispose();
  }

  void _onFocus() {
    if (_node.hasFocus) {
      // Typing replaces what is there.
      _controller.selection = TextSelection(baseOffset: 0, extentOffset: _controller.text.length);
    } else if (_controller.text != _valueText()) {
      _controller.text = _valueText();
    }
  }

  bool get _showingAll => _controller.text.trim().isEmpty || (widget.value != null && _controller.text == _valueText());

  Iterable<T> _filter(TextEditingValue v) {
    if (_showingAll) return widget.options;
    final words = v.text.toLowerCase().split(RegExp(r'\s+')).where((w) => w.isNotEmpty).toList();
    bool inName(T o) => words.every(widget.label(o).toLowerCase().contains);
    final found = widget.options.where((o) {
      final hay = '${widget.label(o)} ${widget.searchText?.call(o) ?? ''}'.toLowerCase();
      return words.every(hay.contains);
    }).toList();
    // What is named as typed comes before what only matches by its group or code.
    return [...found.where(inName), ...found.where((o) => !inName(o))];
  }

  /// The text typed, when it is something new that could be created (not blank, not exactly an existing name).
  String? get _newName {
    if (widget.onCreate == null || _showingAll) return null;
    final text = _controller.text.trim();
    if (text.isEmpty) return null;
    final lower = text.toLowerCase();
    return widget.options.any((o) => widget.label(o).toLowerCase() == lower) ? null : text;
  }

  Future<void> _create() async {
    final name = _newName;
    if (name == null) return;
    final made = await widget.onCreate!(name);
    if (made != null && mounted) _chosen(made);
  }

  void _chosen(T o) {
    _controller.text = widget.label(o);
    widget.onSelected(o);
    if (widget.advanceOnSelect) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) _node.nextFocus();
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(builder: (context, c) {
      return RawAutocomplete<T>(
        textEditingController: _controller,
        focusNode: _node,
        optionsBuilder: _filter,
        displayStringForOption: widget.label,
        onSelected: _chosen,
        fieldViewBuilder: (context, controller, node, onFieldSubmitted) => CallbackShortcuts(
          bindings: {
            if (widget.onCreate != null) const SingleActivator(LogicalKeyboardKey.keyC, alt: true): _create,
          },
          // Rebuilt as the text changes, so the "nothing matches" line is always current.
          child: ValueListenableBuilder<TextEditingValue>(
            valueListenable: controller,
            builder: (context, value, _) => TextField(
              controller: controller,
              focusNode: node,
              autofocus: widget.autofocus,
              enabled: widget.enabled,
              decoration: InputDecoration(
                hintText: widget.hint,
                errorText: widget.errorText,
                // The drop-down is not shown when nothing matches, so say it here.
                helperText: _newName != null && _filter(value).isEmpty
                    ? 'Nothing matches. Press Enter or Alt+C to create "$_newName"'
                    : null,
                suffixIcon: const Icon(Icons.arrow_drop_down_rounded),
              ),
              // Enter is handled here, not by the text field's own "next": with nothing typed it moves on,
              // otherwise it takes the highlighted option (which then moves on). With a new name that matches
              // nothing, it creates it.
              onEditingComplete: () {},
              onSubmitted: (_) {
                if (_showingAll && widget.value != null) {
                  node.nextFocus();
                } else if (_newName != null && _filter(controller.value).isEmpty) {
                  _create();
                } else {
                  onFieldSubmitted();
                }
              },
            ),
          ),
        ),
        optionsViewBuilder: (context, onSelected, options) {
          final list = options.toList();
          return Align(
            alignment: Alignment.topLeft,
            child: Material(
              elevation: 6,
              borderRadius: BorderRadius.circular(AppTheme.radiusS),
              color: AppTheme.cardBg,
              child: ConstrainedBox(
                constraints: BoxConstraints(maxWidth: c.maxWidth, maxHeight: 280),
                child: SizedBox(
                  width: c.maxWidth,
                  child: list.isEmpty && _newName == null
                      ? const Padding(
                          padding: EdgeInsets.all(14),
                          child: Text('Nothing matches', style: TextStyle(color: AppTheme.textSecondary)),
                        )
                      : ListView.builder(
                          padding: const EdgeInsets.symmetric(vertical: 4),
                          shrinkWrap: true,
                          itemCount: list.length + (_newName == null ? 0 : 1),
                          itemBuilder: (context, i) {
                            if (i == list.length) {
                              return InkWell(
                                key: const Key('typeahead-create'),
                                onTap: _create,
                                child: Padding(
                                  padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                                  child: Row(children: [
                                    const Icon(Icons.add_circle_outline_rounded, size: 18, color: AppTheme.primary),
                                    const SizedBox(width: 8),
                                    Expanded(
                                      child: Text(
                                        list.isEmpty
                                            ? 'Create "$_newName"  (Enter or Alt+C)'
                                            : 'Create "$_newName"  (Alt+C)',
                                        overflow: TextOverflow.ellipsis,
                                        style: const TextStyle(
                                            fontSize: 14, fontWeight: FontWeight.w600, color: AppTheme.primary),
                                      ),
                                    ),
                                  ]),
                                ),
                              );
                            }
                            final o = list[i];
                            final highlighted = AutocompleteHighlightedOption.of(context) == i;
                            final detail = widget.detail?.call(o);
                            return InkWell(
                              onTap: () => onSelected(o),
                              child: Container(
                                color: highlighted ? AppTheme.primarySoft : null,
                                padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                                child: Row(children: [
                                  Expanded(
                                      child: Text(widget.label(o),
                                          overflow: TextOverflow.ellipsis,
                                          style: const TextStyle(fontSize: 14, color: AppTheme.textPrimary))),
                                  if (detail != null && detail.isNotEmpty) ...[
                                    const SizedBox(width: 12),
                                    Text(detail, style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
                                  ],
                                ]),
                              ),
                            );
                          },
                        ),
                ),
              ),
            ),
          );
        },
      );
    });
  }
}
