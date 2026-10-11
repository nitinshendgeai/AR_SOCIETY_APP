"""The manager's checklist on paper: a ruled sheet with a box to tick against each line, the society's letterhead, the
things the records say need attention, and a signature at the foot. Printed on A4 portrait."""
from datetime import date
from io import BytesIO
from typing import List

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import KeepTogether, Paragraph, Spacer, Table, TableStyle
from xml.sax.saxutils import escape

from app.modules.accounts.services.documents_pdf import GREY, P, _date, _doc, _footer, _grid, _p
from app.modules.billing.services.bill_pdf import INK, MUTED, society_header

GROUPS = (("daily", "Daily routine"), ("periodic", "Due this week or month"),
          ("compliance", "Statutory and compliance"))
STATE_WORDS = {"overdue": "OVERDUE", "due": "Due today", "soon": "Coming up", "unconfirmed": "Confirm if done",
               "done": "Done", "skipped": "Skipped"}


def _t(text) -> str:
    """The built-in PDF fonts have no rupee sign, so amounts are written "Rs.", as on the society's other papers."""
    return str(text or "").replace("₹", "Rs. ")


def _box() -> Table:
    t = Table([[""]], colWidths=[4.2 * mm], rowHeights=[4.2 * mm])
    t.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.8, INK)]))
    return t


def _line(item: dict) -> list:
    when = []
    if item["group"] != "daily":
        when.append(STATE_WORDS.get(item["state"], "") + (f" · {_date(item['due_on'])}" if item.get("due_on") else ""))
    if item.get("applies_because"):
        when.append(item["applies_because"])
    detail = _t(item.get("detail"))
    basis = _t(item.get("legal_basis"))
    cell = [Paragraph(f"<b>{escape(_t(item['title']))}</b>", P["td"])]
    if detail:
        cell.append(Paragraph(escape(detail), P["td_small"]))
    if basis:
        cell.append(Paragraph(f"Basis: {escape(basis)}", P["td_small"]))
    done = item["state"] in ("done", "skipped")
    return [_box(), cell, _p(" · ".join(w for w in when if w), "td_small"),
            _p(("Done " + _date(item["log"]["done_on"]) + " by " + (item["log"]["done_by"] or "")) if done and item.get("log")
               else "", "td_small")]


def checklist_pdf(society, data: dict) -> bytes:
    buf = BytesIO()
    name = society.name if society else "Society"
    day = date.fromisoformat(data["as_of"])
    doc = _doc(buf, A4, "Manager's Daily Checklist", name, True, margins=(12, 12, 10, 14))
    w = doc.width
    story: List = [*society_header(society, w), Spacer(1, 3 * mm),
                   Paragraph("MANAGER'S DAILY CHECKLIST", P["title"]),
                   _p(day.strftime("%A, %d %B %Y"), "sub"), Spacer(1, 3 * mm)]
    s = data["summary"]
    story.append(_p(f"Routine and statutory items today: {s['done']} done of {s['total']}"
                    f"{' · ' + str(s['overdue']) + ' overdue' if s['overdue'] else ''}"
                    f" · {s['live_open']} item(s) flagged from the records.", "note"))
    story.append(Spacer(1, 2 * mm))
    widths = [7 * mm, w - 7 * mm - 42 * mm - 36 * mm, 42 * mm, 36 * mm]
    for key, label in GROUPS:
        rows = [i for i in data["items"] if i["group"] == key]
        if not rows:
            continue
        table = [[_p("", "th"), _p(label, "th"), _p("When / why", "th"), _p("Done by", "th")]]
        table += [_line(i) for i in rows]
        story += [_grid(table, widths), Spacer(1, 3 * mm)]
    live = data["live"]
    if live:
        table = [[_p("", "th"), _p("Needs attention today — from the society's records", "th"), _p("What", "th"),
                  _p("Action taken", "th")]]
        for l in live:
            table.append([_box(), [Paragraph(f"<b>{escape(_t(l['title']))}</b>", P["td"])],
                          _p(_t(l.get("detail")) or l["severity"].capitalize(), "td_small"), _p("", "td")])
        story += [_grid(table, widths), Spacer(1, 2 * mm)]
    story += [KeepTogether([
        Spacer(1, 1 * mm), _p("Remarks / matters to report to the committee:", "td_b"), Spacer(1, 9 * mm),
        Table([[_p("Manager's signature", "sign"), _p("Date and time", "sign"), _p("Checked by (committee)", "sign")]],
              colWidths=[w / 3] * 3,
              style=TableStyle([("LINEABOVE", (0, 0), (-1, 0), 0.6, INK)])),
    ])]
    footer = _footer(name, "Manager's Daily Checklist")
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buf.getvalue()
