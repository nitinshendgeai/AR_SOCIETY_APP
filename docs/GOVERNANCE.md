# Governance — meetings, polls, documents

Screens under **Community** in the menu. All three are open to every role; what a person can *do* depends on whether
they are on the office side (Society Admin, Committee, Manager).

## Meetings (`/meetings`)
- Office: schedule (title, date/time, place, agenda), optionally notify every resident and tenant, edit, record minutes.
- Minutes, attendees and resolutions are hidden from everyone but the office until the minutes are **published**.
- API: `/api/v1/governance/meetings/society/{id}` (POST/GET), `/meetings/{id}` (GET/PATCH), `/meetings/{id}/minutes` (PUT).

## Polls (`/polls`)
- Office creates a question with 2–10 distinct options and a closing date; can close early.
- One vote per **flat** (unique poll + flat). Only an active resident can vote. 409 if closed or already voted.
- Results are totals only and appear to a person after they vote, or to all once the poll closes.
- API: `/api/v1/governance/polls/society/{id}`, `/polls/{id}/vote`, `/polls/{id}/close`.

## Documents (`/documents`)
- Stored as bytea in Postgres. Max 10 MB; pdf, png, jpeg, txt, doc(x), xls(x). 415 / 413 otherwise.
- Visibility `everyone` or `committee`; delete is a soft delete.
- API: `/api/v1/governance/documents/society/{id}` (POST multipart/GET), `/documents/{id}/download`, `DELETE /documents/{id}`.

## RBAC
Forms `meetings`, `polls`, `documents` (rbac_seed + migration `b1f8091a2b3c`).
