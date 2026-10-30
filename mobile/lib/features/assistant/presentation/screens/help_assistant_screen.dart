import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/help/help_launcher.dart';
import 'package:ar_society_app/core/l10n/app_locale.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/assistant/data/assistant_api.dart';
import 'package:ar_society_app/features/assistant/presentation/providers/assistant_providers.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';

/// In-app help chat. Answers come from the approved manuals (with their sources); it never changes anything.
class HelpAssistantScreen extends ConsumerWidget {
  const HelpAssistantScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final status = ref.watch(assistantStatusProvider);
    return Scaffold(
      backgroundColor: AppTheme.surface,
      appBar: AppBar(
        title: Text(context.tr('Help assistant')),
        actions: [
          if (helpAvailable)
            TextButton.icon(
              onPressed: () => openHelp(ref.read(currentUserProvider)),
              icon: const Icon(Icons.menu_book_outlined, size: 18),
              label: Text(context.tr('User manual')),
            ),
          if (status.hasValue &&
              status.value!.enabled &&
              ref.watch(assistantChatProvider).messages.isNotEmpty)
            IconButton(
              tooltip: context.tr('Clear chat'),
              icon: const Icon(Icons.delete_sweep_outlined),
              onPressed: () => ref.read(assistantChatProvider.notifier).clear(),
            ),
        ],
      ),
      body: status.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (e, _) => _Notice(
          icon: Icons.cloud_off_rounded,
          text: assistantFailureMessage(failureKindOf(e)),
          action: TextButton(
              onPressed: () => ref.invalidate(assistantStatusProvider),
              child: Text(context.tr('Try again'))),
        ),
        data: (s) => s.enabled
            ? _ChatBody(status: s)
            : _Notice(
                icon: Icons.pause_circle_outline_rounded,
                text: assistantFailureMessage(AssistantFailureKind.switchedOff),
                action: helpAvailable
                    ? TextButton(
                        onPressed: () =>
                            openHelp(ref.read(currentUserProvider)),
                        child: Text(context.tr('Open the user manual')))
                    : null,
              ),
      ),
    );
  }
}

class _Notice extends StatelessWidget {
  final IconData icon;
  final String text;
  final Widget? action;
  const _Notice({required this.icon, required this.text, this.action});

  @override
  Widget build(BuildContext context) => Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(mainAxisSize: MainAxisSize.min, children: [
            Icon(icon, size: 40, color: AppTheme.textSecondary),
            const SizedBox(height: 12),
            Text(text,
                textAlign: TextAlign.center,
                style: const TextStyle(color: AppTheme.textSecondary)),
            if (action != null) ...[const SizedBox(height: 8), action!],
          ]),
        ),
      );
}

class _ChatBody extends ConsumerStatefulWidget {
  final AssistantStatus status;
  const _ChatBody({required this.status});

  @override
  ConsumerState<_ChatBody> createState() => _ChatBodyState();
}

class _ChatBodyState extends ConsumerState<_ChatBody> {
  final _input = TextEditingController();
  final _scroll = ScrollController();
  final _focus = FocusNode();

  @override
  void dispose() {
    _input.dispose();
    _scroll.dispose();
    _focus.dispose();
    super.dispose();
  }

  void _send([String? text]) {
    final q = (text ?? _input.text).trim();
    if (q.isEmpty) return;
    ref.read(assistantChatProvider.notifier).send(q);
    _input.clear();
    // The field keeps its focus when Enter was pressed (see onEditingComplete below); asking for it again there makes
    // the browser drop its text box while Flutter still shows the field as focused, and typing then does nothing.
    if (!_focus.hasFocus) _focus.requestFocus();
  }

  void _toEnd() => WidgetsBinding.instance.addPostFrameCallback((_) {
        if (_scroll.hasClients) {
          _scroll.animateTo(_scroll.position.maxScrollExtent,
              duration: const Duration(milliseconds: 200),
              curve: Curves.easeOut);
        }
      });

  @override
  Widget build(BuildContext context) {
    final chat = ref.watch(assistantChatProvider);
    ref.listen(assistantChatProvider, (_, __) => _toEnd());
    final s = widget.status;
    return SafeArea(
      child: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(
              maxWidth:
                  820), // readable on wide web screens, full width on a phone
          child: Column(children: [
            if (s.manualsOnly)
              Container(
                width: double.infinity,
                color: AppTheme.primary.withValues(alpha: 0.06),
                padding:
                    const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                child: Text(
                  context.tr(
                      'AI summaries are off. Answers are taken straight from the approved manuals.'),
                  key: const Key('manualsOnlyBanner'),
                  style: const TextStyle(
                      fontSize: 12, color: AppTheme.textSecondary),
                ),
              ),
            if (s.needsTargetSociety)
              Padding(
                padding: const EdgeInsets.fromLTRB(16, 8, 16, 0),
                child: Text(
                  context.tr(
                      'Live configuration checks need a society. Platform admins can choose one in the Platform Console.'),
                  style: const TextStyle(
                      fontSize: 12, color: AppTheme.textSecondary),
                ),
              ),
            Expanded(
              child: chat.messages.isEmpty
                  ? _Welcome(questions: s.suggestedQuestions, onPick: _send)
                  : ListView.builder(
                      controller: _scroll,
                      padding: const EdgeInsets.all(16),
                      itemCount: chat.messages.length + (chat.sending ? 1 : 0),
                      itemBuilder: (_, i) {
                        if (i == chat.messages.length) return const _Typing();
                        return _Bubble(message: chat.messages[i]);
                      },
                    ),
            ),
            _Composer(
              controller: _input,
              focus: _focus,
              sending: chat.sending,
              maxChars: s.maxQuestionChars,
              onSend: _send,
            ),
          ]),
        ),
      ),
    );
  }
}

class _Welcome extends StatelessWidget {
  final List<String> questions;
  final void Function(String) onPick;
  const _Welcome({required this.questions, required this.onPick});

  @override
  Widget build(BuildContext context) =>
      ListView(padding: const EdgeInsets.all(16), children: [
        Text(context.tr('Ask how to do something in DuxOS'),
            style: const TextStyle(
                fontSize: 18,
                fontWeight: FontWeight.w600,
                color: AppTheme.textPrimary)),
        const SizedBox(height: 4),
        Text(
          context.tr(
              'I explain the steps from the approved manuals. I cannot look up residents, dues or payments, and I never change anything.'),
          style: const TextStyle(color: AppTheme.textSecondary),
        ),
        const SizedBox(height: 16),
        for (final q in questions)
          Padding(
            padding: const EdgeInsets.only(bottom: 8),
            // A full-width card, not a chip: the questions are long, and the theme's chips are the same grey as the page.
            child: Semantics(
              button: true,
              label: q,
              child: Material(
                color: AppTheme.cardBg,
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(12),
                  side: const BorderSide(color: AppTheme.border),
                ),
                child: InkWell(
                  borderRadius: BorderRadius.circular(12),
                  onTap: () => onPick(q),
                  child: Padding(
                    padding: const EdgeInsets.symmetric(
                        horizontal: 14, vertical: 12),
                    child: Row(children: [
                      const Icon(Icons.chat_bubble_outline_rounded,
                          size: 18, color: AppTheme.primary),
                      const SizedBox(width: 10),
                      Expanded(
                          child: Text(q,
                              style: const TextStyle(
                                  color: AppTheme.textPrimary))),
                      const Icon(Icons.north_east_rounded,
                          size: 16, color: AppTheme.textTertiary),
                    ]),
                  ),
                ),
              ),
            ),
          ),
      ]);
}

class _Typing extends StatelessWidget {
  const _Typing();

  @override
  Widget build(BuildContext context) => Semantics(
        liveRegion: true,
        label: 'Looking through the manuals',
        child: Padding(
          padding: const EdgeInsets.symmetric(vertical: 8),
          child: Row(children: [
            const SizedBox(
                width: 16,
                height: 16,
                child: CircularProgressIndicator(strokeWidth: 2)),
            const SizedBox(width: 10),
            Text(context.tr('Looking through the manuals…'),
                style: const TextStyle(color: AppTheme.textSecondary)),
          ]),
        ),
      );
}

class _Composer extends StatelessWidget {
  final TextEditingController controller;
  final FocusNode focus;
  final bool sending;
  final int maxChars;
  final void Function([String?]) onSend;
  const _Composer(
      {required this.controller,
      required this.focus,
      required this.sending,
      required this.maxChars,
      required this.onSend});

  @override
  Widget build(BuildContext context) => Container(
        padding: const EdgeInsets.fromLTRB(12, 8, 12, 8),
        decoration: const BoxDecoration(
            color: AppTheme.cardBg,
            border: Border(top: BorderSide(color: AppTheme.border))),
        child: Row(crossAxisAlignment: CrossAxisAlignment.end, children: [
          Expanded(
            // Enter sends and Shift+Enter starts a new line. Handled as a key press: on the web a text-input "send"
            // action makes the browser drop its text box, after which typing does nothing until the next click.
            child: Focus(
              onKeyEvent: (node, event) {
                if (event is KeyDownEvent &&
                    (event.logicalKey == LogicalKeyboardKey.enter ||
                        event.logicalKey == LogicalKeyboardKey.numpadEnter) &&
                    !HardwareKeyboard.instance.isShiftPressed &&
                    !controller.value.composing.isValid) {
                  if (!sending) onSend();
                  return KeyEventResult.handled;
                }
                return KeyEventResult.ignored;
              },
              child: TextField(
                key: const Key('assistantInput'),
                controller: controller,
                focusNode: focus,
                minLines: 1,
                maxLines: 4,
                maxLength: maxChars,
                textInputAction:
                    TextInputAction.send, // the phone keyboard's send key
                onEditingComplete:
                    () {}, // keep the focus (and the keyboard) after sending
                onSubmitted: sending ? null : (_) => onSend(),
                decoration: InputDecoration(
                  hintText: context.tr('Type your question'),
                  counterText: '',
                  border: const OutlineInputBorder(),
                  isDense: true,
                ),
              ),
            ),
          ),
          const SizedBox(width: 8),
          IconButton.filled(
            key: const Key('assistantSend'),
            style: IconButton.styleFrom(
                backgroundColor: AppTheme.primary,
                foregroundColor: Colors.white),
            tooltip: context.tr('Send'),
            onPressed: sending ? null : () => onSend(),
            icon: const Icon(Icons.send_rounded),
          ),
        ]),
      );
}

class _Bubble extends ConsumerWidget {
  final ChatMessage message;
  const _Bubble({required this.message});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final isUser = message.role == ChatRole.user;
    final isError = message.role == ChatRole.error;
    final a = message.answer;
    final bg = isUser
        ? AppTheme.primary
        : (isError ? AppTheme.error.withValues(alpha: 0.08) : AppTheme.cardBg);
    final fg = isUser ? Colors.white : AppTheme.textPrimary;
    return Align(
      alignment: isUser ? Alignment.centerRight : Alignment.centerLeft,
      child: Semantics(
        container: true,
        label: isUser ? 'You asked' : (isError ? 'Error' : 'Assistant answer'),
        child: Container(
          margin: const EdgeInsets.only(bottom: 12),
          constraints: BoxConstraints(
              maxWidth: MediaQuery.sizeOf(context).width * 0.9 > 640
                  ? 640
                  : MediaQuery.sizeOf(context).width * 0.9),
          // A Material (not a decorated Container) so the expandable Steps/Sources rows can paint their ink.
          child: Material(
            color: bg,
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(14),
              side: isUser
                  ? BorderSide.none
                  : const BorderSide(color: AppTheme.border),
            ),
            clipBehavior: Clip.antiAlias,
            child: Padding(
              padding: const EdgeInsets.all(12),
              child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    SelectableText(message.text, style: TextStyle(color: fg)),
                    if (isError)
                      TextButton.icon(
                        key: const Key('assistantRetry'),
                        onPressed: () => ref
                            .read(assistantChatProvider.notifier)
                            .retry(message.id),
                        icon: const Icon(Icons.refresh_rounded, size: 18),
                        label: Text(context.tr('Try again')),
                      ),
                    if (a != null) ..._answerExtras(context, a),
                  ]),
            ),
          ),
        ),
      ),
    );
  }

  List<Widget> _answerExtras(BuildContext context, AssistantAnswer a) => [
        if (a.steps.isNotEmpty)
          ExpansionTile(
            key: const Key('assistantSteps'),
            tilePadding: EdgeInsets.zero,
            childrenPadding: const EdgeInsets.only(bottom: 8),
            title: Text('${context.tr('Steps')} (${a.steps.length})',
                style: const TextStyle(fontWeight: FontWeight.w600)),
            children: [
              for (var i = 0; i < a.steps.length; i++)
                Align(
                    alignment: Alignment.centerLeft,
                    child: Padding(
                        padding: const EdgeInsets.only(bottom: 4),
                        child: SelectableText('${i + 1}. ${a.steps[i]}'))),
            ],
          ),
        if (a.configGaps.isNotEmpty) ...[
          const SizedBox(height: 4),
          Text(context.tr('Setup checks'),
              style: const TextStyle(fontWeight: FontWeight.w600)),
          for (final f in a.configGaps)
            Padding(
              padding: const EdgeInsets.only(top: 4),
              child:
                  Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Icon(
                    f.status == 'gap'
                        ? Icons.warning_amber_rounded
                        : Icons.info_outline_rounded,
                    size: 16,
                    color: f.status == 'gap'
                        ? AppTheme.warning
                        : AppTheme.textSecondary),
                const SizedBox(width: 6),
                Expanded(
                    child:
                        Text(f.message, style: const TextStyle(fontSize: 13))),
              ]),
            ),
        ],
        if (a.uncertainty != null)
          Padding(
              padding: const EdgeInsets.only(top: 6),
              child: Text(a.uncertainty!,
                  style: const TextStyle(
                      fontSize: 12,
                      fontStyle: FontStyle.italic,
                      color: AppTheme.textSecondary))),
        if (a.escalation != null)
          Padding(
              padding: const EdgeInsets.only(top: 6),
              child: Text(a.escalation!,
                  style: const TextStyle(
                      fontSize: 12, color: AppTheme.textSecondary))),
        if (a.sources.isNotEmpty)
          ExpansionTile(
            key: const Key('assistantSources'),
            tilePadding: EdgeInsets.zero,
            childrenPadding: const EdgeInsets.only(bottom: 8),
            title: Text('${context.tr('Sources')} (${a.sources.length})',
                style: const TextStyle(fontWeight: FontWeight.w600)),
            children: [
              for (final s in a.sources)
                Align(
                  alignment: Alignment.centerLeft,
                  child: Padding(
                    padding: const EdgeInsets.only(bottom: 4),
                    child: Text('${s.title} › ${s.section}',
                        style: const TextStyle(
                            fontSize: 12, color: AppTheme.textSecondary)),
                  ),
                ),
            ],
          ),
      ];
}
