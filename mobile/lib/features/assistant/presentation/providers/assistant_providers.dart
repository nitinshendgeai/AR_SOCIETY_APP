import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/features/assistant/data/assistant_api.dart';

final assistantApiProvider = Provider<AssistantApi>((_) => AssistantApi());

/// What the assistant can do for the signed-in person (read from the server).
final assistantStatusProvider = FutureProvider.autoDispose<AssistantStatus>(
  (ref) => ref.watch(assistantApiProvider).status(),
);

enum ChatRole { user, assistant, error }

class ChatMessage {
  final int id;
  final ChatRole role;
  final String text;
  final AssistantAnswer? answer;
  final String? retryQuestion; // set on an error: the question to ask again
  const ChatMessage(this.id, this.role, this.text,
      {this.answer, this.retryQuestion});
}

class ChatState {
  final List<ChatMessage> messages;
  final bool sending;
  const ChatState({this.messages = const [], this.sending = false});

  ChatState copyWith({List<ChatMessage>? messages, bool? sending}) => ChatState(
      messages: messages ?? this.messages, sending: sending ?? this.sending);
}

/// The conversation lives only in memory for as long as the screen is open: nothing is written to the device or
/// the server. Asking again is always safe because the assistant only reads.
class AssistantChat extends StateNotifier<ChatState> {
  final AssistantApi api;
  final bool includeDiagnostics;
  final int maxQuestionChars;
  int _next = 0;

  static const maxHistoryTurns = 6;

  AssistantChat(this.api,
      {this.includeDiagnostics = false, this.maxQuestionChars = 1000})
      : super(const ChatState());

  List<String> get _earlierQuestions {
    final qs = [
      for (final m in state.messages)
        if (m.role == ChatRole.user) m.text
    ];
    return qs.length <= maxHistoryTurns
        ? qs
        : qs.sublist(qs.length - maxHistoryTurns);
  }

  /// Adds the question to the conversation and asks. Ignored while another question is in flight.
  Future<void> send(String raw) async {
    final q = raw.trim();
    if (q.isEmpty || state.sending || q.length > maxQuestionChars) return;
    final earlier = _earlierQuestions;
    state = state.copyWith(
        messages: [...state.messages, ChatMessage(_next++, ChatRole.user, q)],
        sending: true);
    await _ask(q, earlier);
  }

  /// Asks the same question again after a failure, replacing the error: the question is not shown twice.
  Future<void> retry(int errorId) async {
    if (state.sending) return;
    final err = state.messages
        .where((m) => m.id == errorId && m.role == ChatRole.error)
        .firstOrNull;
    final q = err?.retryQuestion;
    if (q == null) return;
    final kept = [
      for (final m in state.messages)
        if (m.id != errorId) m
    ];
    final earlier = [
      for (final m in kept)
        if (m.role == ChatRole.user) m.text
    ]..removeLast();
    state = state.copyWith(messages: kept, sending: true);
    await _ask(
        q,
        earlier.length <= maxHistoryTurns
            ? earlier
            : earlier.sublist(earlier.length - maxHistoryTurns));
  }

  Future<void> _ask(String q, List<String> earlier) async {
    try {
      final a = await api.ask(q,
          earlierQuestions: earlier, includeDiagnostics: includeDiagnostics);
      if (!mounted) return;
      state = state.copyWith(messages: [
        ...state.messages,
        ChatMessage(_next++, ChatRole.assistant, a.answer, answer: a)
      ], sending: false);
    } catch (e) {
      if (!mounted) return;
      state = state.copyWith(
        messages: [
          ...state.messages,
          ChatMessage(_next++, ChatRole.error,
              assistantFailureMessage(failureKindOf(e)),
              retryQuestion: q),
        ],
        sending: false,
      );
    }
  }

  void clear() {
    if (!state.sending) state = const ChatState();
  }
}

/// Diagnostics are requested only when the server says this person may run them.
final assistantChatProvider =
    StateNotifierProvider.autoDispose<AssistantChat, ChatState>((ref) {
  final st = ref.watch(assistantStatusProvider).valueOrNull;
  return AssistantChat(
    ref.watch(assistantApiProvider),
    includeDiagnostics: (st?.diagnosticsAvailable ?? false) &&
        !(st?.needsTargetSociety ?? false),
    maxQuestionChars: st?.maxQuestionChars ?? 1000,
  );
});
