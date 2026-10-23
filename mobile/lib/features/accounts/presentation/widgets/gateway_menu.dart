import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';

/// One line of the Gateway: what it opens, the letter that opens it, and a hint such as a function key.
class GatewayItem {
  final String label;
  final String letter; // one letter; pressing it opens the item
  final IconData icon;
  final String? hint; // "F6"
  final String? badge; // "3 waiting"
  final VoidCallback onOpen;
  const GatewayItem({
    required this.label,
    required this.letter,
    required this.icon,
    required this.onOpen,
    this.hint,
    this.badge,
  });
}

class GatewaySection {
  final String title;
  final List<GatewayItem> items;
  const GatewaySection(this.title, this.items);
}

/// A menu worked entirely from the keyboard, like Tally's Gateway: **Up / Down** move the highlight (and wrap round),
/// **Enter** opens it, a **letter** opens the item that has it, **Esc** goes back. A mouse click opens an item too.
/// Keys with Ctrl, Alt or Cmd held are left alone, so the app's own shortcuts still work here.
class GatewayMenu extends StatefulWidget {
  final List<GatewaySection> sections;
  final VoidCallback? onBack;
  const GatewayMenu({super.key, required this.sections, this.onBack});

  @override
  State<GatewayMenu> createState() => _GatewayMenuState();
}

class _GatewayMenuState extends State<GatewayMenu> {
  final _focus = FocusNode(debugLabel: 'gateway');
  final _rowKeys = <int, GlobalKey>{};
  int _index = 0;

  List<GatewayItem> get _items => [for (final s in widget.sections) ...s.items];

  @override
  void dispose() {
    _focus.dispose();
    super.dispose();
  }

  void _move(int by) {
    final n = _items.length;
    if (n == 0) return;
    setState(() => _index = (_index + by + n) % n);
    WidgetsBinding.instance.addPostFrameCallback((_) {
      final ctx = _rowKeys[_index]?.currentContext;
      if (ctx != null) Scrollable.ensureVisible(ctx, alignment: 0.5, duration: const Duration(milliseconds: 100));
    });
  }

  KeyEventResult _onKey(FocusNode node, KeyEvent event) {
    if (event is! KeyDownEvent && event is! KeyRepeatEvent) return KeyEventResult.ignored;
    final keys = HardwareKeyboard.instance;
    if (keys.isControlPressed || keys.isAltPressed || keys.isMetaPressed) return KeyEventResult.ignored;
    final k = event.logicalKey;
    if (k == LogicalKeyboardKey.arrowDown) {
      _move(1);
      return KeyEventResult.handled;
    }
    if (k == LogicalKeyboardKey.arrowUp) {
      _move(-1);
      return KeyEventResult.handled;
    }
    if (k == LogicalKeyboardKey.enter || k == LogicalKeyboardKey.numpadEnter) {
      if (_items.isNotEmpty) _items[_index].onOpen();
      return KeyEventResult.handled;
    }
    if (k == LogicalKeyboardKey.escape) {
      widget.onBack?.call();
      return widget.onBack == null ? KeyEventResult.ignored : KeyEventResult.handled;
    }
    if (event is KeyDownEvent) {
      final label = k.keyLabel.toUpperCase();
      final i = _items.indexWhere((it) => it.letter.toUpperCase() == label);
      if (label.length == 1 && i >= 0) {
        setState(() => _index = i);
        _items[i].onOpen();
        return KeyEventResult.handled;
      }
    }
    return KeyEventResult.ignored;
  }

  @override
  Widget build(BuildContext context) {
    var flat = 0;
    return Focus(
      focusNode: _focus,
      autofocus: true,
      onKeyEvent: _onKey,
      child: ListView(
        padding: const EdgeInsets.fromLTRB(16, 8, 16, 24),
        children: [
          for (final section in widget.sections) ...[
            Padding(
              padding: const EdgeInsets.fromLTRB(8, 18, 8, 6),
              child: Text(section.title.toUpperCase(),
                  style: const TextStyle(
                      fontSize: 11.5, letterSpacing: .6, fontWeight: FontWeight.w700, color: AppTheme.textSecondary)),
            ),
            Container(
              decoration: BoxDecoration(color: AppTheme.cardBg, borderRadius: BorderRadius.circular(AppTheme.radiusM)),
              clipBehavior: Clip.antiAlias,
              child: Column(children: [
                for (final item in section.items) _row(item, flat++),
              ]),
            ),
          ],
        ],
      ),
    );
  }

  Widget _row(GatewayItem item, int i) {
    final selected = i == _index;
    return KeyedSubtree(
      key: _rowKeys.putIfAbsent(i, () => GlobalKey()),
      child: InkWell(
        key: Key('gateway-${item.letter.toLowerCase()}'),
        onTap: () {
          setState(() => _index = i);
          item.onOpen();
        },
        onHover: (h) {
          if (h && _index != i) setState(() => _index = i);
        },
        child: Container(
          color: selected ? AppTheme.primarySoft : null,
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 11),
          child: Row(children: [
            Icon(item.icon, size: 19, color: selected ? AppTheme.primary : AppTheme.textSecondary),
            const SizedBox(width: 12),
            Expanded(
              child: Text(item.label,
                  style: TextStyle(fontSize: 14.5, fontWeight: selected ? FontWeight.w700 : FontWeight.w500)),
            ),
            if (item.badge != null) ...[
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                decoration: BoxDecoration(color: AppTheme.warningSoft, borderRadius: BorderRadius.circular(10)),
                child: Text(item.badge!,
                    style: const TextStyle(fontSize: 11.5, fontWeight: FontWeight.w700, color: AppTheme.warning)),
              ),
              const SizedBox(width: 10),
            ],
            if (item.hint != null) ...[
              Text(item.hint!, style: const TextStyle(fontSize: 12, color: AppTheme.textTertiary)),
              const SizedBox(width: 10),
            ],
            Container(
              width: 24,
              height: 24,
              alignment: Alignment.center,
              decoration: BoxDecoration(
                color: selected ? AppTheme.primary : AppTheme.surface,
                borderRadius: BorderRadius.circular(6),
                border: Border.all(color: selected ? AppTheme.primary : AppTheme.border),
              ),
              child: Text(item.letter.toUpperCase(),
                  style: TextStyle(
                      fontSize: 12, fontWeight: FontWeight.w700, color: selected ? Colors.white : AppTheme.textSecondary)),
            ),
          ]),
        ),
      ),
    );
  }
}
