import 'dart:async';

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/assistant/data/assistant_api.dart';
import 'package:ar_society_app/features/assistant/presentation/providers/assistant_providers.dart';
import 'package:ar_society_app/features/assistant/presentation/screens/help_assistant_screen.dart';

/// Records every call so the tests can see exactly what the app sends, and answers from a script.
class _FakeApi extends AssistantApi {
  final List<({String q, List<String> earlier, bool diag})> calls = [];
  Object? failWith;
  Completer<AssistantAnswer>? hold;
  AssistantStatus statusValue;
  _FakeApi({AssistantStatus? status}) : statusValue = status ?? _status();

  @override
  Future<AssistantStatus> status() async => statusValue;

  @override
  Future<AssistantAnswer> ask(String question, {List<String> earlierQuestions = const [], bool includeDiagnostics = false}) {
    calls.add((q: question, earlier: earlierQuestions, diag: includeDiagnostics));
    if (hold != null) return hold!.future;
    if (failWith != null) return Future.error(failWith!);
    return Future.value(_answer());
  }
}

AssistantStatus _status({bool enabled = true, String mode = 'disabled', bool diag = false, bool needsTarget = false}) =>
    AssistantStatus(
      enabled: enabled,
      providerMode: mode,
      diagnosticsAvailable: diag,
      needsTargetSociety: needsTarget,
      maxQuestionChars: 200,
      suggestedQuestions: const ['How do I generate the maintenance bills?', 'How do I add a vendor?'],
    );

AssistantAnswer _answer({String text = 'Open Maintenance Billing and create the cycle.'}) => AssistantAnswer(
      requestId: 'r1',
      status: 'answered',
      answer: text,
      steps: const ['Create the cycle', 'Preview it'],
      sources: const [AssistantSource('Maintenance Billing — Complete Guide', 'Make and issue a bill')],
      configGaps: const [AssistantFinding('maintenance_elements', 'gap', '2 elements have no ledger linked.')],
      uncertainty: 'Please confirm with your administrator.',
    );

DioException _dio(DioExceptionType t, {int? status}) => DioException(
      requestOptions: RequestOptions(path: '/assistant/ask'),
      type: t,
      response: status == null ? null : Response(requestOptions: RequestOptions(path: '/assistant/ask'), statusCode: status),
    );

Widget _app(_FakeApi api) => ProviderScope(
      overrides: [assistantApiProvider.overrideWithValue(api)],
      child: MaterialApp(theme: AppTheme.lightTheme, home: const HelpAssistantScreen()),
    );

Future<void> _ask(WidgetTester t, String q) async {
  await t.enterText(find.byKey(const Key('assistantInput')), q);
  await t.tap(find.byKey(const Key('assistantSend')));
  await t.pumpAndSettle();
}

void main() {
  group('failure wording', () {
    test('each failure maps to a kind and a plain message', () {
      expect(failureKindOf(_dio(DioExceptionType.connectionError)), AssistantFailureKind.offline);
      expect(failureKindOf(_dio(DioExceptionType.receiveTimeout)), AssistantFailureKind.timeout);
      expect(failureKindOf(_dio(DioExceptionType.badResponse, status: 429)), AssistantFailureKind.rateLimited);
      expect(failureKindOf(_dio(DioExceptionType.badResponse, status: 503)), AssistantFailureKind.switchedOff);
      expect(failureKindOf(_dio(DioExceptionType.badResponse, status: 403)), AssistantFailureKind.forbidden);
      expect(failureKindOf(_dio(DioExceptionType.badResponse, status: 422)), AssistantFailureKind.tooLong);
      expect(failureKindOf(StateError('x')), AssistantFailureKind.other);
      for (final k in AssistantFailureKind.values) {
        expect(assistantFailureMessage(k), isNotEmpty);
      }
    });

    test('the answer is parsed with its sources, steps and gaps', () {
      final a = AssistantAnswer.fromJson({
        'request_id': 'abc',
        'status': 'insufficient_evidence',
        'answer': 'I could not find this.',
        'steps': ['one'],
        'sources': [
          {'title': 'T', 'section': 'S', 'document': 'd.md', 'chunk_id': 'd.md#1'}
        ],
        'config_gaps': [
          {'topic': 'vendor_tds', 'status': 'not_initialised', 'message': 'm'}
        ],
        'provider': {'mode': 'disabled', 'status': 'timeout'},
      });
      expect(a.status, 'insufficient_evidence');
      expect(a.sources.single.section, 'S');
      expect(a.configGaps.single.topic, 'vendor_tds');
      expect(a.providerStatus, 'timeout');
    });
  });

  group('chat controller', () {
    test('sends only the person\'s own earlier questions, at most six', () async {
      final api = _FakeApi();
      final chat = AssistantChat(api, includeDiagnostics: true);
      for (var i = 1; i <= 9; i++) {
        await chat.send('question $i');
      }
      final last = api.calls.last;
      expect(last.q, 'question 9');
      expect(last.earlier, ['question 3', 'question 4', 'question 5', 'question 6', 'question 7', 'question 8']);
      expect(last.diag, isTrue);
      expect(chat.state.messages.length, 18); // 9 questions + 9 answers, nothing else stored
    });

    test('empty, over-long and concurrent questions are not sent', () async {
      final api = _FakeApi()..hold = Completer();
      final chat = AssistantChat(api, maxQuestionChars: 10);
      await chat.send('   ');
      await chat.send('x' * 11);
      expect(api.calls, isEmpty);
      final first = chat.send('first');
      await chat.send('second'); // ignored while the first is in flight
      expect(api.calls.length, 1);
      api.hold!.complete(_answer());
      await first;
      expect(chat.state.sending, isFalse);
    });

    test('retry asks the same question again without showing it twice', () async {
      final api = _FakeApi()..failWith = _dio(DioExceptionType.connectionError);
      final chat = AssistantChat(api);
      await chat.send('how do I bill?');
      expect(chat.state.messages.map((m) => m.role), [ChatRole.user, ChatRole.error]);
      api.failWith = null;
      await chat.retry(chat.state.messages.last.id);
      expect(chat.state.messages.map((m) => m.role), [ChatRole.user, ChatRole.assistant]);
      expect(api.calls.map((c) => c.q), ['how do I bill?', 'how do I bill?']);
      expect(api.calls.last.earlier, isEmpty);
    });

    test('clear empties the conversation', () async {
      final chat = AssistantChat(_FakeApi());
      await chat.send('hello');
      chat.clear();
      expect(chat.state.messages, isEmpty);
    });
  });

  group('screen', () {
    testWidgets('shows a loading indicator, then suggestions and the manuals-only banner', (t) async {
      final api = _FakeApi();
      await t.pumpWidget(_app(api));
      expect(find.byType(CircularProgressIndicator), findsOneWidget);
      await t.pumpAndSettle();
      expect(find.text('How do I generate the maintenance bills?'), findsOneWidget);
      expect(find.byKey(const Key('manualsOnlyBanner')), findsOneWidget);
    });

    testWidgets('a suggested question shows a typing state, then the answer with steps, sources and gaps', (t) async {
      final api = _FakeApi()..hold = Completer();
      await t.pumpWidget(_app(api));
      await t.pumpAndSettle();
      await t.tap(find.text('How do I add a vendor?'));
      await t.pump();
      expect(find.text('Looking through the manuals…'), findsOneWidget);
      expect(find.byType(CircularProgressIndicator), findsOneWidget);
      expect(t.widget<IconButton>(find.byKey(const Key('assistantSend'))).onPressed, isNull); // no double sends

      api.hold!.complete(_answer());
      await t.pumpAndSettle();
      expect(find.text('Open Maintenance Billing and create the cycle.'), findsOneWidget);
      expect(find.text('Steps (2)'), findsOneWidget);
      expect(find.text('Sources (1)'), findsOneWidget);
      expect(find.text('2 elements have no ledger linked.'), findsOneWidget);
      expect(find.text('Please confirm with your administrator.'), findsOneWidget);
      expect(find.text('Maintenance Billing — Complete Guide › Make and issue a bill'), findsNothing); // collapsed

      await t.ensureVisible(find.byKey(const Key('assistantSources')));
      await t.tap(find.text('Sources (1)'));
      await t.pumpAndSettle();
      expect(find.text('Maintenance Billing — Complete Guide › Make and issue a bill'), findsOneWidget);
      await t.tap(find.text('Steps (2)'));
      await t.pumpAndSettle();
      expect(find.text('1. Create the cycle'), findsOneWidget);
    });

    testWidgets('a failed question shows the reason and Try again repeats it once', (t) async {
      final api = _FakeApi()..failWith = _dio(DioExceptionType.connectionError);
      await t.pumpWidget(_app(api));
      await t.pumpAndSettle();
      await _ask(t, 'how do I bill?');
      expect(find.textContaining('offline'), findsOneWidget);
      expect(find.text('how do I bill?'), findsOneWidget);

      api.failWith = null;
      await t.tap(find.byKey(const Key('assistantRetry')));
      await t.pumpAndSettle();
      expect(find.textContaining('offline'), findsNothing);
      expect(find.text('how do I bill?'), findsOneWidget); // still shown once, not duplicated
      expect(find.text('Open Maintenance Billing and create the cycle.'), findsOneWidget);
      expect(api.calls.length, 2);
    });

    testWidgets('timeout and rate-limit failures have their own wording', (t) async {
      final api = _FakeApi()..failWith = _dio(DioExceptionType.receiveTimeout);
      await t.pumpWidget(_app(api));
      await t.pumpAndSettle();
      await _ask(t, 'q1');
      expect(find.text('That took too long. Please try again.'), findsOneWidget);
      api.failWith = _dio(DioExceptionType.badResponse, status: 429);
      await t.tap(find.byKey(const Key('assistantRetry')));
      await t.pumpAndSettle();
      expect(find.textContaining('too quickly'), findsOneWidget);
    });

    testWidgets('when the assistant is switched off the person is told, and there is no composer', (t) async {
      await t.pumpWidget(_app(_FakeApi(status: _status(enabled: false))));
      await t.pumpAndSettle();
      expect(find.textContaining('switched off'), findsOneWidget);
      expect(find.byKey(const Key('assistantInput')), findsNothing);
    });

    testWidgets('an AI provider in use hides the manuals-only banner', (t) async {
      await t.pumpWidget(_app(_FakeApi(status: _status(mode: 'mock'))));
      await t.pumpAndSettle();
      expect(find.byKey(const Key('manualsOnlyBanner')), findsNothing);
    });

    testWidgets('diagnostics are requested only for people the server allows, and not for a platform admin without a society', (t) async {
      final allowed = _FakeApi(status: _status(diag: true));
      await t.pumpWidget(_app(allowed));
      await t.pumpAndSettle();
      await _ask(t, 'q');
      expect(allowed.calls.single.diag, isTrue);

      final platform = _FakeApi(status: _status(diag: true, needsTarget: true));
      await t.pumpWidget(_app(platform));
      await t.pumpAndSettle();
      await _ask(t, 'q');
      expect(platform.calls.single.diag, isFalse);

      final resident = _FakeApi();
      await t.pumpWidget(_app(resident));
      await t.pumpAndSettle();
      await _ask(t, 'q');
      expect(resident.calls.single.diag, isFalse);
    });

    testWidgets('lays out on a phone and on a wide web window without overflow, and Enter sends', (t) async {
      for (final size in const [Size(360, 640), Size(1280, 800)]) {
        t.view.physicalSize = size;
        t.view.devicePixelRatio = 1;
        final api = _FakeApi();
        await t.pumpWidget(_app(api));
        await t.pumpAndSettle();
        await t.enterText(find.byKey(const Key('assistantInput')), 'how do I bill?');
        await t.testTextInput.receiveAction(TextInputAction.send);
        await t.pumpAndSettle();
        expect(api.calls.length, 1, reason: 'Enter should send at $size');
        expect(t.takeException(), isNull, reason: 'no overflow at $size');
      }
      addTearDown(t.view.reset);
    });
  });
}
