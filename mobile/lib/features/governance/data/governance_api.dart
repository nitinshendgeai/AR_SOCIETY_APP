import 'dart:typed_data';
import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/utils/server_time.dart';

String apiDay(DateTime d) =>
    '${d.year.toString().padLeft(4, '0')}-${d.month.toString().padLeft(2, '0')}-${d.day.toString().padLeft(2, '0')}';

DateTime _day(Object? v) => DateTime.parse(v as String);

// ── Meetings ─────────────────────────────────────────────────────────────────

const kMeetingTypes = <(String, String)>[
  ('agm', 'Annual general meeting'),
  ('sgm', 'Special general meeting'),
  ('committee', 'Committee meeting'),
  ('other', 'Other'),
];
String meetingTypeLabel(String v) =>
    kMeetingTypes.where((e) => e.$1 == v).firstOrNull?.$2 ?? v;

const kOutcomes = <(String, String)>[
  ('carried', 'Carried'),
  ('rejected', 'Rejected'),
  ('deferred', 'Deferred')
];

class Attendee {
  String name;
  String? flatLabel, designation;
  bool present;
  Attendee(
      {required this.name,
      this.flatLabel,
      this.designation,
      this.present = true});
  Attendee.fromJson(Map<String, dynamic> j)
      : name = j['name'] as String,
        flatLabel = j['flat_label'] as String?,
        designation = j['designation'] as String?,
        present = j['present'] as bool? ?? true;
  Map<String, dynamic> toJson() => {
        'name': name,
        'flat_label': flatLabel,
        'designation': designation,
        'present': present
      };
}

class Resolution {
  String text, outcome;
  String? proposedBy, secondedBy;
  int number;
  Resolution(
      {required this.text,
      this.outcome = 'carried',
      this.proposedBy,
      this.secondedBy,
      this.number = 0});
  Resolution.fromJson(Map<String, dynamic> j)
      : text = j['text'] as String,
        outcome = j['outcome'] as String? ?? 'carried',
        proposedBy = j['proposed_by'] as String?,
        secondedBy = j['seconded_by'] as String?,
        number = (j['number'] as num?)?.toInt() ?? 0;
  Map<String, dynamic> toJson() => {
        'text': text,
        'outcome': outcome,
        'proposed_by': proposedBy,
        'seconded_by': secondedBy
      };
}

class Meeting {
  final String id, title, meetingType, status;
  final DateTime date;
  final String? startTime, venue, agenda, minutes;
  final bool minutesPublished;
  final List<Attendee> attendees;
  final List<Resolution> resolutions;
  Meeting.fromJson(Map<String, dynamic> j)
      : id = j['id'] as String,
        title = j['title'] as String,
        meetingType = j['meeting_type'] as String? ?? 'other',
        status = j['status'] as String? ?? 'scheduled',
        date = _day(j['meeting_date']),
        startTime = j['start_time'] as String?,
        venue = j['venue'] as String?,
        agenda = j['agenda'] as String?,
        minutes = j['minutes'] as String?,
        minutesPublished = j['minutes_published'] as bool? ?? false,
        attendees = [
          for (final a in (j['attendees'] as List? ?? const []))
            Attendee.fromJson(a as Map<String, dynamic>)
        ],
        resolutions = [
          for (final r in (j['resolutions'] as List? ?? const []))
            Resolution.fromJson(r as Map<String, dynamic>)
        ];

  bool get hasMinutes =>
      (minutes ?? '').isNotEmpty ||
      resolutions.isNotEmpty ||
      attendees.isNotEmpty;
  bool get upcoming =>
      status == 'scheduled' &&
      !date.isBefore(DateTime(
          DateTime.now().year, DateTime.now().month, DateTime.now().day));
}

// ── Polls ────────────────────────────────────────────────────────────────────

class PollOptionView {
  final String id, label;
  final int? votes;
  PollOptionView.fromJson(Map<String, dynamic> j)
      : id = j['id'] as String,
        label = j['label'] as String,
        votes = (j['votes'] as num?)?.toInt();
}

class Poll {
  final String id, question, resultsAfter;
  final String? description, myOptionId;
  final DateTime closesOn;
  final bool open, canVote, resultsVisible;
  final int votes, flats;
  final List<PollOptionView> options;
  Poll.fromJson(Map<String, dynamic> j)
      : id = j['id'] as String,
        question = j['question'] as String,
        description = j['description'] as String?,
        resultsAfter = j['results_after'] as String? ?? 'vote',
        closesOn = _day(j['closes_on']),
        open = j['open'] as bool? ?? false,
        canVote = j['can_vote'] as bool? ?? false,
        resultsVisible = j['results_visible'] as bool? ?? false,
        myOptionId = j['my_option_id'] as String?,
        votes = (j['votes'] as num?)?.toInt() ?? 0,
        flats = (j['flats'] as num?)?.toInt() ?? 0,
        options = [
          for (final o in (j['options'] as List))
            PollOptionView.fromJson(o as Map<String, dynamic>)
        ];
}

// ── Documents ────────────────────────────────────────────────────────────────

const kDocCategories = <(String, String)>[
  ('bylaws', 'Bye-laws'),
  ('minutes', 'Minutes'),
  ('audit', 'Audit and accounts'),
  ('insurance', 'Insurance'),
  ('agreement', 'Agreements'),
  ('notice', 'Notices'),
  ('other', 'Other'),
];
String docCategoryLabel(String v) =>
    kDocCategories.where((e) => e.$1 == v).firstOrNull?.$2 ?? v;

class SocietyDoc {
  final String id, title, category, visibility, fileName, mimeType;
  final String? description;
  final int sizeBytes;
  final DateTime? createdAt;
  SocietyDoc.fromJson(Map<String, dynamic> j)
      : id = j['id'] as String,
        title = j['title'] as String,
        category = j['category'] as String? ?? 'other',
        visibility = j['visibility'] as String? ?? 'everyone',
        fileName = j['file_name'] as String,
        mimeType = j['mime_type'] as String,
        description = j['description'] as String?,
        sizeBytes = (j['size_bytes'] as num?)?.toInt() ?? 0,
        createdAt = parseStampOrNull(j['created_at']);
}

String sizeText(int bytes) {
  if (bytes < 1024) return '$bytes B';
  if (bytes < 1024 * 1024) return '${(bytes / 1024).toStringAsFixed(0)} KB';
  return '${(bytes / (1024 * 1024)).toStringAsFixed(1)} MB';
}

// ── API ──────────────────────────────────────────────────────────────────────

class GovernanceApi {
  final Dio _dio;
  GovernanceApi({Dio? dio}) : _dio = dio ?? ApiClient.instance;

  Future<List<Meeting>> meetings(String sid) async => [
        for (final m in (await _dio.get('/governance/meetings/society/$sid'))
            .data as List)
          Meeting.fromJson(m as Map<String, dynamic>)
      ];

  Future<Meeting> createMeeting(String sid, Map<String, dynamic> body) async =>
      Meeting.fromJson(
          (await _dio.post('/governance/meetings/society/$sid', data: body))
              .data as Map<String, dynamic>);

  Future<Meeting> updateMeeting(String id, Map<String, dynamic> body) async =>
      Meeting.fromJson(
          (await _dio.patch('/governance/meetings/$id', data: body)).data
              as Map<String, dynamic>);

  Future<Meeting> saveMinutes(String id, Map<String, dynamic> body) async =>
      Meeting.fromJson(
          (await _dio.put('/governance/meetings/$id/minutes', data: body)).data
              as Map<String, dynamic>);

  Future<List<Poll>> polls(String sid) async => [
        for (final p
            in (await _dio.get('/governance/polls/society/$sid')).data as List)
          Poll.fromJson(p as Map<String, dynamic>)
      ];

  Future<Poll> createPoll(String sid, Map<String, dynamic> body) async =>
      Poll.fromJson(
          (await _dio.post('/governance/polls/society/$sid', data: body)).data
              as Map<String, dynamic>);

  Future<Poll> vote(String pollId, String optionId) async =>
      Poll.fromJson((await _dio.post('/governance/polls/$pollId/vote',
              data: {'option_id': optionId}))
          .data as Map<String, dynamic>);

  Future<Poll> closePoll(String pollId) async =>
      Poll.fromJson((await _dio.post('/governance/polls/$pollId/close')).data
          as Map<String, dynamic>);

  Future<List<SocietyDoc>> documents(String sid) async => [
        for (final d in (await _dio.get('/governance/documents/society/$sid'))
            .data as List)
          SocietyDoc.fromJson(d as Map<String, dynamic>)
      ];

  Future<SocietyDoc> addDocument(String sid,
      {required String title,
      required String category,
      required String visibility,
      String? description,
      required Uint8List bytes,
      required String fileName,
      required String mimeType}) async {
    final form = FormData.fromMap({
      'title': title,
      'category': category,
      'visibility': visibility,
      if (description != null && description.isNotEmpty)
        'description': description,
      'file': MultipartFile.fromBytes(bytes,
          filename: fileName, contentType: DioMediaType.parse(mimeType)),
    });
    return SocietyDoc.fromJson(
        (await _dio.post('/governance/documents/society/$sid', data: form)).data
            as Map<String, dynamic>);
  }

  Future<Uint8List> download(String id) async {
    final r = await _dio.get<List<int>>('/governance/documents/$id/download',
        options: Options(responseType: ResponseType.bytes));
    return Uint8List.fromList(r.data!);
  }

  Future<void> deleteDocument(String id) =>
      _dio.delete('/governance/documents/$id');
}

final governanceApiProvider = Provider<GovernanceApi>((_) => GovernanceApi());

final meetingsProvider = FutureProvider.autoDispose
    .family<List<Meeting>, String>(
        (ref, sid) => ref.watch(governanceApiProvider).meetings(sid));
final pollsProvider = FutureProvider.autoDispose.family<List<Poll>, String>(
    (ref, sid) => ref.watch(governanceApiProvider).polls(sid));
final documentsProvider = FutureProvider.autoDispose
    .family<List<SocietyDoc>, String>(
        (ref, sid) => ref.watch(governanceApiProvider).documents(sid));
