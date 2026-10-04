# Staff Duties, Printed Sheets and Daily In/Out — Complete Guide

How a manager or supervisor gives duties to staff, prints the day's checklist for staff who work from paper, and
records it afterwards; and how daily in/out works. Written against the code (`backend/app/modules/staff/`).

**Who:** the Manager (all departments) and department supervisors (their own department's staff only) assign, print,
enter and cancel. Staff use the app on their phone *or* a printed sheet.

---

## 1. The idea

```
Checklist template  ─┐
(per department)     │
                     ▼
   Assign Duty ──▶ one duty per staff per day  ──▶  printed sheet (paper)  ──┐
   (staff, days,        each with its own                                     ├─▶ done: ticked on paper, then
    weekdays)           copy of the checklist  ──▶  My Duties (phone)  ───────┘   "Enter from sheet" — or ticked in the app
                                                                  │
                                         supervisor checks ──▶ Verify
```

---

## 2. Checklist templates (once)

**Where:** Operations → **Checklist Templates** (Manager and above).

A named list for a department, e.g. *Night gate round* — Check main gate lock and boom barrier\*, Log every visitor in
the register\*, Inspect CCTV feed. `*` = required: the duty can't be completed until required items are ticked.
Duties **copy** the items when assigned, so editing a template later never changes a duty already given.

**Print a blank sheet** from the template's printer icon: the checklist with name, date and times left to fill in by
hand, for a department that fills it in every day without assigning in the app.

> Write checklist items in English / Latin letters — the printed sheet cannot show Marathi or Hindi characters.

---

## 3. Assign duties

**Where:** Manager / Supervisor dashboard → **Assign Duty**.

| Field | How it works |
|---|---|
| **Assign to** | Pick one or several staff (chips grouped by department; *Select all* per department). New staff on probation can be chosen; only inactive / terminated staff are left out. A supervisor is limited to their own department. |
| **Checklist template** | Optional; shown for the departments of the staff chosen. Its items are copied onto every duty made. |
| **Duty, description, location** | The duty name fills in from the template if you leave it blank. |
| **Duty date** | The first (or only) day. |
| **Repeat on more days** | Switch on for a daily round or the same duty on certain weekdays: choose **Until** (up to 62 days) and tick the weekdays. |
| **Start / end time** | Optional, 24-hour (`9:30` is accepted). |

The form says what it will make — *"Makes 12 duties (2 staff × 6 days)"* — and afterwards what it did: how many duties
were made and which days were **left out and why** (*On approved leave*; *Already has this duty on that day*). Doing
the same plan twice never doubles anything. At most 600 duties at a time.

There is no background job: a plan is made when you save it, so you can print a week or a month ahead.

**Cancel:** Operations → **Duties** → the day → a duty → **Cancel**. For a plan you choose *Only this day* or *This and
later days* (for that staff member only; others in the plan are untouched). A duty that someone has started (an item
ticked, or completed) can't be cancelled.

---

## 4. Print the sheets

**Where:** Operations → **Duties** → printer icon → *Print sheets for this day* or *for 7 days*. Staff can print their
own from **My Duties** (today, tomorrow or the next 7 days). A supervisor gets only their own department's.

One **A4 page per staff member per day** on the society letterhead:

- name, employee code, department, date, shift;
- a strip for **IN time / OUT time / staff signature**;
- each duty (location and time) with its checklist as **tick boxes** and a **remarks** column — items already done in
  the app print as *Done*;
- supervisor's remarks, and **staff / supervisor signature** lines.

If nothing is assigned for the chosen day the app says so instead of printing a blank page.

### Housekeeping: the floor-wise sheet (one page for all floors)

Housekeeping works floor by floor, so there is a second layout: **every floor is a row** and the duty's checklist
items are the tick columns, with **Time** and **Initials** at the end — one A4 page covers a whole wing (23 floors fit
on one page). Each staff member gets their own page, so three housekeeping staff means three pages a day.

1. Make a checklist template for housekeeping whose items are what is checked on each floor (*Corridor swept*,
   *Corridor mopped*, *Dustbins emptied*, *Lift cleaned*, *Staircase cleaned*). `*` = must be done on every floor.
2. Assign it to the housekeeping staff (Assign Duty, repeat daily).
3. **Duties → print icon → Housekeeping floor-wise sheets** (this day or 7 days). Staff can print their own from
   **My Duties → print icon → Floor-wise sheet**; **Checklist Templates → print icon → Blank floor-wise sheet** prints
   one with name and date left blank.

The floors come from **Structure → Wings / Floors**. A society with several wings gets one page per wing per staff
member (to print one wing only, the API takes `wing_id`). A wing with no floors entered falls back to 1…its total floors;
with no wings at all the app asks you to add them first.

The sheet is for paper: the per-floor ticks are not stored in the app. When you enter the filled sheet
(*Enter from sheet*), tick each item that was done and mark the duty completed as usual.

---

## 5. Entering a filled-in sheet

**Where:** Operations → **Duties** → the day → a duty → **Enter from sheet** (not offered for a day that hasn't come).

For one staff member and one day, enter what is written on the paper:

1. **Attendance** — the status if the sheet says (Present, Half day, Absent, On leave, Off duty) and the **IN / OUT
   times as written** (24-hour). An OUT earlier than the IN is the **next morning** (a 22:00–06:00 night shift). A shift
   over 20 hours is refused as a typo. Entering the sheet records the attendance as **approved**; entering it again
   corrects the same day rather than adding another.
2. **Each duty** — tick the items done, add a remark if the sheet has one, and switch **Mark duty completed**. Required
   items must be ticked first. Only what you changed is sent, so items the staff member ticked in the app stay as
   "ticked in the app".
3. **Save sheet.** Everything is checked before anything is saved.

Each item you enter keeps **who entered it and that it came from paper** (shown on the duty as *Entered from the
printed sheet*). A duty the supervisor has **verified** can't be changed.

Then **Verify** the completed duties as usual (Duties → *Awaiting Verification*).

---

## 6. Daily in / out

Staff with a phone punch **in** and **out** in **Attendance**; staff on paper have it entered from their sheet (§5).

| Rule | How it works |
|---|---|
| Date of a punch | The **society's** date and clock (set in Society Settings; India by default) — not the server's. |
| Time shown | Each person's own local time (a 9:00 AM punch shows 9:00). |
| Approval | A punch-in and a punch-out wait for the supervisor of the department (Approvals). A sheet entered by a supervisor is already approved. |
| Night shift | A guard who punched in at 22:00 checks out at 06:00 the next day on the same record. While still punched in, a new punch-in is refused ("Check out first"); a punch-in left open for more than 18 hours (forgotten check-out) no longer blocks the next day; a supervisor can enter that day's real IN / OUT from the sheet (§5). |
| Late | A punch-in more than 30 minutes after the shift start (on the society's clock) counts as late in the daily summary. |
| Rejected punch | Doesn't count as present; the staff member can punch in again. |
| Overtime | Hours beyond 8 on a record. |
| Corrections | Staff request a **status** correction on a past record (not the times); the supervisor approves or rejects (Attendance Corrections). To fix times, enter the day from the sheet. |

---

## 7. A week in practice

1. **Sunday evening** — Manager: Assign Duty → Ramesh Patil and Suresh Jadhav → *Night gate round* (template) →
   *Main gate* → Monday, repeat until Saturday → Assign. *"Makes 12 duties"*.
2. Duties → Monday → print → give each guard his sheet for the week (7 days).
3. **Each night** the guard ticks the sheet and writes IN / OUT times; or ticks the items on his phone.
4. **Next morning** — the supervisor opens Duties → yesterday → **Enter from sheet** for each guard: times, ticks,
   *Mark duty completed* → Save. Then **Verify**.
5. A guard goes on leave: his days are skipped when the plan is made; for leave approved later, **Cancel** the days.

---

## 8. Not covered yet

- Editing a duty (cancel and re-assign instead).
- Marathi / Hindi text on the printed sheet.
- A duty roster view across a week (the Duties screen is one day at a time).
