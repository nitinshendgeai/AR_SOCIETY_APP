# Help Assistant (Phase 2) — Architecture, Contract and Release Checklist

Status: **implemented and tested, not production-ready.** No live AI provider is wired in; see "Provider decision".
Audit that preceded it: `AR_SOCIETY_HELP_ASSISTANT_PHASE1_VERIFICATION.md`.

## 1. What it is

An in-app chat (Flutter web and mobile) that answers "how do I…" questions **from approved manuals only**, with
sources, and — for people allowed to see it — a short list of configuration gaps from read-only checks. It cannot look
up residents, dues, payments, vendors or any record, and it cannot change anything.

```
Flutter (HelpAssistantScreen) ──Dio + Bearer──▶ /api/v1/assistant/{status,ask,diagnostics}
                                                  │  get_current_user  (existing auth, suspension, no-society gates)
                                                  │  require_any_member
                                                  ▼
                                   service.py ── resolve_scope (user row → society / audience)
                                     │   ├── knowledge.py   approved docs → chunks → TF-IDF top-k
                                     │   ├── provider.py    disabled | mock (+ hard timeout)  ── question + excerpts only
                                     │   └── diagnostics.py SELECT-only counts, inside read_only_session
```

Code: `backend/app/modules/assistant/` (`schemas.py`, `knowledge.py`, `provider.py`, `diagnostics.py`, `service.py`,
`routes/assistant.py`), registered in `app/api/__init__.py`. Flutter: `mobile/lib/features/assistant/`, route
`/help-assistant`, reached from **Help** in the account menu (web) and More menu (phone). The static manual is still
available from the chat's **User manual** button on web.

## 2. API contract (`/api/v1/assistant`, all require a Bearer token)

Every response carries `request_id` (also the `X-Request-ID` header) and `Cache-Control: no-store`.
Request bodies reject unknown fields (`user_id`, `role`, `society_id`, `permissions` → 422).

| Call | Purpose |
|---|---|
| `GET /status` | `enabled`, `provider{mode,status}`, `audience`, `diagnostics_available`, `diagnostic_topics`, `needs_target_society`, `index_version`, `document_count`, `limits`, `suggested_questions` |
| `POST /ask` | `{question, history[], include_diagnostics, target_society_id?}` → `AskResponse` |
| `POST /diagnostics` | `{topics[], target_society_id?}` → `{findings[], read_only:true}` (POST only because it has a body) |

`AskResponse`: `status` (`answered` \| `insufficient_evidence` \| `restricted`), `answer`, `steps[]` (ordered, extracted
from the manual), `sources[{title, section, document, chunk_id}]`, `config_gaps[{topic,status,message,count}]`,
`uncertainty`, `escalation`, `provider{mode,status}`, `audience`, `index_version`.

Errors: 401 no/invalid token · 403 other society / no society / suspended / not manager-level for `/diagnostics` ·
400 platform admin without `target_society_id` · 404 unknown target society · 422 limits · 429 rate limit (with
`Retry-After`) · 503 `ASSISTANT_ENABLED=false`. Bodies never contain stack traces, SQL, provider messages or secrets.

Limits (settings, all server-side): question 1000 chars (hard cap 4000), history ≤ 6 user turns × 600 chars (50 accepted
then trimmed), answer ≤ 3000 chars, provider timeout 15 s, 20 requests/user/minute (per process).

## 3. Role and tenant decisions

* Identity, permissions and society come only from the authenticated `User` row. The JWT carries no role or society.
* `target_society_id` is **only** honoured for platform admins (`is_superadmin` and no society). A society-scoped user
  naming any other society gets 403 (their own is accepted and ignored). `society_id=None` is never treated as "all":
  a platform admin has no society until they name an existing one, and live checks without one return 400.
  Platform access in this codebase is all-or-nothing (no per-society platform grants), so authorisation is the flag
  plus the society existing.
* A login with no society that is not a platform admin gets manuals only; naming a society is 403.
* **Manuals are available to every authenticated member.** Live checks (`/diagnostics`, `include_diagnostics`) need
  `manager_above` (Manager, Committee, Society Admin, Platform Admin). Lower roles asking for them get the manual answer
  and a note, not an error. Audience (`resident|security|staff|supervisor|manager|committee|admin|platform_admin`) only
  re-ranks manual sections; it grants nothing. The Flutter role mapping is not consulted.
* Diagnostics for a topic whose optional service the platform switched off for that society are reported
  `unavailable` and not queried. The assistant itself is a core feature (no entry in `services_catalog.py`); the
  existing suspended-society and no-society gates apply because it uses `get_current_user`.
* Record lookups ("show dues of flat A-101", "list defaulters") are answered `restricted`. This is wording only: the
  assistant has no code path to those records, so disclosure is structurally impossible.
* `docs/RBAC_MATRIX.md` is **not** a source (stale: no Manager/Supervisor/Tenant). Re-admit it only after correction
  and independent review.

## 4. Read-only boundary

Diagnostics (`diagnostics.py`) are fresh `SELECT count(...)` queries filtered by `society_id`, returning counts and
fixed messages only. They do not import or call `AccountsService`, `BillingService` or `vendor_tds`. Still-existing
mutating GETs (verified at HEAD, **not** called): `GET /accounts/chart|ledgers|registers/cash-bank|members|summary|
expenses-by-element|bank-reconciliation|years/{society_id}`, `GET /billing/elements/{society_id}`,
`GET /vendors/tds/rules/{society_id}`. Recommended separate fix: make those reads non-seeding.
`read_only_session` also raises on any flush/commit during a check and, on PostgreSQL, runs
`SET LOCAL transaction_read_only = on` (**not exercised in tests: SQLite only** — verify on staging).

## 5. Knowledge sources

Approved (`knowledge.APPROVED_DOCUMENTS`, relative to `docs/`): `user-guide/DUX_OS_Help_Guide.html`,
`GUIDES/MAINTENANCE_BILLING_COMPLETE_GUIDE.md`, `GUIDES/MAINTENANCE_ELEMENT_WISE_MANUAL.md`,
`GUIDES/VENDOR_MASTERS_COMPLETE_GUIDE.md`, `MODULES/ACCOUNTS.md`, `ACCOUNTING_PROCEDURE.md`.
Rules: only listed files, only inside `docs/` (symlinks that leave it are ignored); 2 MB per file; never env files,
fixtures, code, `RBAC_MATRIX.md`, `AI_DEVELOPMENT_RULES.md`, `ARCHITECTURE.md`, `KNOWN_ISSUES.md`, audit reports.
Adding a document = editing that list in a reviewed change. Chunking is by heading (≤1400 chars), ranking is a small
TF-IDF (no vector DB), top 4 chunks / 6000 chars. `index_version` = hash of the chunker version and each file's bytes,
so re-indexing is deterministic; the index is built lazily at first use per process (restart to pick up edited docs).
Chunks that read like instructions to the assistant ("ignore previous instructions", "you are now…", "reveal…key")
are quarantined at indexing time. No match → `insufficient_evidence` ("I won't guess" + escalation), never an invented
procedure. The deploy image contains `docs/` (nixpacks copies the repo to `/app`); if a file is missing the index
simply has fewer documents (`document_count` in `/status`).

## 6. Provider configuration and decision

Settings (`app/core/config.py`, env-overridable, no secrets): `ASSISTANT_ENABLED` (true), `ASSISTANT_PROVIDER`
(`disabled` default \| `mock`), `ASSISTANT_PROVIDER_TIMEOUT_SECONDS` (15), `ASSISTANT_MAX_QUESTION_CHARS` (1000),
`ASSISTANT_MAX_HISTORY_TURNS` (6), `ASSISTANT_MAX_HISTORY_CHARS` (600), `ASSISTANT_MAX_ANSWER_CHARS` (3000),
`ASSISTANT_RATE_LIMIT_PER_MINUTE` (20). An unknown value, or `mock` with `APP_ENV=production`, behaves as disabled
(`provider.mode = "misconfigured"`). Disabled mode answers with the manual's own wording and says so in the app.

A provider receives **only** `question` and manual `excerpts` — no identity, society, role, history or diagnostics —
its output is length-bounded, screened, and never supplies sources/steps/gaps. Timeout, exception, empty/non-string or
instruction-like output all fall back to the manual wording (`provider.status` = `timeout|error|malformed`).

**Decision needed before a live provider (nothing was assumed or added):** which provider/model, the variable names for
its key (suggest `ASSISTANT_API_KEY` + `ASSISTANT_MODEL`, backend only, blank = disabled like `SMTP_HOST`), whether
sending question text and public manual excerpts to an external service is acceptable under the society data policy
(personal data can be typed into a question — consider an input scrubber), retry policy (suggest none; fall back),
and the SDK vs `httpx` (already a dependency) choice. Also decide a retention rule before logging any prompts.
Logs currently hold request id, audience, status, counts and question *length* only.

## 7. Tests and how to run them

```
cd backend   # Python 3.12, as in CI; isolated SQLite file, never a real database
DATABASE_URL=sqlite:///./test_ar_society.db SECRET_KEY=test-only-secret-key-0123456789abcdef APP_ENV=test \
  SCHEDULER_ENABLED=false python -m pytest tests/assistant -q -o log_cli=false -p no:cacheprovider
cd ../mobile && cp .env.example .env && flutter test test/help_assistant_test.dart   # then: rm .env
```
Backend (`tests/assistant/`): auth and invalid tokens; identity fields rejected; cross-society for resident/manager/
admin; platform admin target rules; roles × diagnostics; suspended society and switched-off services; restricted-data
refusals and no leakage; grounding, sources, uncertainty; provider disabled/mock/timeout/failure/malformed/injection/
oversize; provider payload privacy; limits, history trimming, rate limit; whole-database snapshot and commit-count
unchanged on every path; mutating reads booby-trapped; AST check that the package never imports or names them; knowledge
allowlist, exclusions, determinism, versioning, quarantine, injected-document resistance.
Flutter (`mobile/test/help_assistant_test.dart`): loading, suggestions, answer with steps/sources/gaps, errors
(offline, timeout, 429, off), retry without duplicates, history ≤ 6 user turns only, no double send, diagnostics flag,
phone and wide layouts, Enter to send.

## 8. Deployment checklist (do not skip)

- [ ] Review this change set (nothing here is committed or deployed).
- [ ] Decide the provider question in §6; until then ship with `ASSISTANT_PROVIDER=disabled` (default).
- [ ] CI green on Python 3.12 (backend) and Flutter 3.47.5 (`flutter analyze --no-fatal-infos`, `flutter test`).
- [ ] On staging with Postgres: `/status`, `/ask`, `/diagnostics` as resident, manager, admin and platform admin; confirm
      `SET LOCAL transaction_read_only` works and diagnostics create no rows (e.g. compare `accounts` count).
- [ ] Confirm `docs/` is present in the deployed image (`document_count` = 6 in `/status`).
- [ ] Rate limit is per process (Railway runs one worker); revisit before scaling out.
- [ ] Decide whether to add `assistant` to `services_catalog.py` so the platform owner can switch it off per society.
- [ ] Platform admin target-society picker in the app (the API supports it; the UI shows a note only).
- [ ] Hindi/Marathi strings for the new labels (they fall back to English today).
- [ ] Separately fix the seeding GET endpoints listed in §4.
- [ ] Reconcile and independently review `RBAC_MATRIX.md` before it is ever used as a source.
