import 'package:dio/dio.dart';
import 'package:ar_society_app/core/api/api_client.dart';

/// Talks to `/assistant/*`. Every call is read-only on the server, so repeating one is always safe. The app sends no
/// user id, role or society: the server derives all of that from the signed-in session.
class AssistantApi {
  final Dio? _dio;
  AssistantApi({Dio? dio}) : _dio = dio;

  Dio get _client => _dio ?? ApiClient.instance;

  static final _askOptions =
      Options(receiveTimeout: const Duration(seconds: 30));

  Future<AssistantStatus> status() async {
    final r = await _client.get('/assistant/status');
    return AssistantStatus.fromJson(Map<String, dynamic>.from(r.data as Map));
  }

  Future<AssistantAnswer> ask(String question,
      {List<String> earlierQuestions = const [],
      bool includeDiagnostics = false}) async {
    final r = await _client.post(
      '/assistant/ask',
      data: {
        'question': question,
        // Only the person's own earlier questions, to help the search; answers are never sent back.
        'history': [
          for (final q in earlierQuestions) {'role': 'user', 'content': q}
        ],
        'include_diagnostics': includeDiagnostics,
      },
      options: _askOptions,
    );
    return AssistantAnswer.fromJson(Map<String, dynamic>.from(r.data as Map));
  }
}

List<T> _list<T>(Object? v, T Function(Map<String, dynamic>) f) => [
      for (final e in (v as List? ?? const []))
        f(Map<String, dynamic>.from(e as Map))
    ];

class AssistantStatus {
  final bool enabled;
  final String providerMode; // disabled | mock | misconfigured
  final bool diagnosticsAvailable;
  final bool needsTargetSociety;
  final int maxQuestionChars;
  final List<String> suggestedQuestions;

  const AssistantStatus({
    required this.enabled,
    required this.providerMode,
    required this.diagnosticsAvailable,
    required this.needsTargetSociety,
    required this.maxQuestionChars,
    required this.suggestedQuestions,
  });

  /// True when answers are the manuals' own wording rather than an AI summary.
  bool get manualsOnly => providerMode != 'mock' && providerMode != 'live';

  factory AssistantStatus.fromJson(Map<String, dynamic> j) => AssistantStatus(
        enabled: j['enabled'] == true,
        providerMode: (j['provider']?['mode'] ?? 'disabled').toString(),
        diagnosticsAvailable: j['diagnostics_available'] == true,
        needsTargetSociety: j['needs_target_society'] == true,
        maxQuestionChars:
            (j['limits']?['max_question_chars'] as num?)?.toInt() ?? 1000,
        suggestedQuestions: [
          for (final q in (j['suggested_questions'] as List? ?? const []))
            q.toString()
        ],
      );
}

class AssistantSource {
  final String title;
  final String section;
  const AssistantSource(this.title, this.section);
}

class AssistantFinding {
  final String topic;
  final String status; // gap | not_initialised | unavailable | ok
  final String message;
  const AssistantFinding(this.topic, this.status, this.message);
}

class AssistantAnswer {
  final String requestId;
  final String status; // answered | insufficient_evidence | restricted
  final String answer;
  final List<String> steps;
  final List<AssistantSource> sources;
  final List<AssistantFinding> configGaps;
  final String? uncertainty;
  final String? escalation;
  final String providerStatus;

  const AssistantAnswer({
    required this.requestId,
    required this.status,
    required this.answer,
    this.steps = const [],
    this.sources = const [],
    this.configGaps = const [],
    this.uncertainty,
    this.escalation,
    this.providerStatus = 'disabled',
  });

  factory AssistantAnswer.fromJson(Map<String, dynamic> j) => AssistantAnswer(
        requestId: (j['request_id'] ?? '').toString(),
        status: (j['status'] ?? 'answered').toString(),
        answer: (j['answer'] ?? '').toString(),
        steps: [
          for (final s in (j['steps'] as List? ?? const [])) s.toString()
        ],
        sources: _list(
            j['sources'],
            (m) => AssistantSource((m['title'] ?? '').toString(),
                (m['section'] ?? '').toString())),
        configGaps: _list(
            j['config_gaps'],
            (m) => AssistantFinding(
                (m['topic'] ?? '').toString(),
                (m['status'] ?? '').toString(),
                (m['message'] ?? '').toString())),
        uncertainty: j['uncertainty']?.toString(),
        escalation: j['escalation']?.toString(),
        providerStatus: (j['provider']?['status'] ?? 'disabled').toString(),
      );
}

/// Why a question did not get an answer, in terms the screen can word for the person.
enum AssistantFailureKind {
  offline,
  timeout,
  rateLimited,
  switchedOff,
  forbidden,
  tooLong,
  other
}

AssistantFailureKind failureKindOf(Object e) {
  if (e is DioException) {
    switch (e.type) {
      case DioExceptionType.connectionError:
        return AssistantFailureKind.offline;
      case DioExceptionType.connectionTimeout:
      case DioExceptionType.sendTimeout:
      case DioExceptionType.receiveTimeout:
        return AssistantFailureKind.timeout;
      default:
        break;
    }
    switch (e.response?.statusCode) {
      case 429:
        return AssistantFailureKind.rateLimited;
      case 503:
        return AssistantFailureKind.switchedOff;
      case 401:
      case 403:
        return AssistantFailureKind.forbidden;
      case 422:
        return AssistantFailureKind.tooLong;
    }
  }
  return AssistantFailureKind.other;
}

String assistantFailureMessage(AssistantFailureKind k) => switch (k) {
      AssistantFailureKind.offline =>
        'You appear to be offline. Check your connection and try again.',
      AssistantFailureKind.timeout => 'That took too long. Please try again.',
      AssistantFailureKind.rateLimited =>
        'You are asking too quickly. Please wait a minute and try again.',
      AssistantFailureKind.switchedOff =>
        'The help assistant is switched off right now. Please use the user manual.',
      AssistantFailureKind.forbidden =>
        'You are not allowed to use the assistant for this society.',
      AssistantFailureKind.tooLong =>
        'Please shorten your question and try again.',
      AssistantFailureKind.other =>
        'Something went wrong. Please try again, or use the user manual.',
    };
