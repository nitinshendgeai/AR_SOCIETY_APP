"""The vendor master in bulk: importing it from a file, and reviewing every vendor's TDS setup.

TDS is worked out from each vendor's type (individual, firm, company...) and the section of payment, so a vendor
with no type, a type that disagrees with its PAN, or no section where its category has a usual one would be deducted
at the wrong rate or not at all. `tds_review` lists those, with the fix that can be worked out (the type from the PAN,
the section from the category); `apply_tds_review` makes the fixes."""
from typing import Dict, List, Optional
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.tenant_scope import resolve_create_society_id
from app.models.audit_log import AuditAction
from app.models.user import User
from app.modules.vendor.models.vendor import Vendor, VendorCategory, VendorStatus
from app.modules.vendor.repositories.vendor_repo import _highest
from app.modules.vendor.services import vendor_import as vi
from app.modules.vendor.services import vendor_tds as t
from app.services.audit_service import AuditService


def _audit(db, entity, user, request, **kw):
    AuditService.log(db=db, action=AuditAction.CREATE if "imported" in kw.get("new_values", {}) else AuditAction.UPDATE,
                     module="vendor", entity_id=str(entity.id), entity_type="Vendor", user=user,
                     request=request, **kw)


# ── Import ────────────────────────────────────────────────────────────────────

def import_vendors(db: Session, society_id: UUID, data: bytes, filename: str, mapping: Optional[dict], dry_run: bool,
                   user: User, request=None) -> dict:
    """Add vendors from an Excel / CSV master. With `dry_run` nothing is saved: every row is checked and the result
    says what would happen. A vendor whose name, GSTIN or code the society already has is skipped, so the same file
    can be imported again safely."""
    society_id = resolve_create_society_id(user, society_id)
    try:
        header, body, sheet = vi.read_table(data, filename)
        field_map = vi.apply_override(vi.auto_map(header), header, mapping)
    except vi.ImportFileError as e:
        raise HTTPException(status_code=422, detail=str(e))
    labels = vi.column_labels(header)
    sample = {i: vi._text(c) for i, c in enumerate(body[0][1])} if body else {}
    columns = [{"index": i, "heading": labels[i], "field": f, "field_label": vi.FIELD_LABELS.get(f),
                "sample": sample.get(i) or None} for i, f in enumerate(field_map)]
    fields = [{"field": k, "label": v} for k, v in vi.FIELD_LABELS.items()]
    missing = [vi.FIELD_LABELS[f] for f in ("company_name", "mobile") if f not in field_map]
    if missing:
        message = (f"No {' or '.join(missing)} column was found. Name the column(s) in the heading row "
                   f"(for example 'Vendor Name' and 'Mobile'), or choose which column holds them.")
        if not dry_run:
            raise HTTPException(status_code=422, detail=message)
        return {"dry_run": True, "file_name": filename or "", "sheet": sheet, "total_rows": len(body),
                "message": message, "rows": [], "columns": columns, "fields": fields}

    existing = db.query(Vendor.company_name, Vendor.gst_number, Vendor.vendor_code).filter(
        Vendor.society_id == society_id, Vendor.is_active == True)  # noqa: E712
    names = {n.lower(): code for n, g, code in existing}
    gsts = {g: code for n, g, code in existing if g}
    codes = {code.lower() for n, g, code in existing}
    counter = _highest(db, Vendor.vendor_code, Vendor.society_id, society_id)

    rows, to_add = [], []
    seen_names, seen_gst, seen_codes = {}, {}, set()
    for line, raw in body:
        values, errors, notes = vi.parse_row(raw, field_map)
        row = {"line": line, "name": values.get("company_name"), "mobile": values.get("mobile"),
               "category": values.get("category"), "constitution": values.get("constitution"),
               "constitution_label": t.constitution_label(values.get("constitution")),
               "tds_section": values.get("tds_section"), "pan_number": values.get("pan_number")}
        if errors:
            rows.append({**row, "status": "error", "message": "; ".join(errors)})
            continue
        name_key = values["company_name"].lower()
        if name_key in names or name_key in seen_names:
            rows.append({**row, "status": "duplicate", "message":
                         f"A vendor named '{values['company_name']}' already exists ({names.get(name_key) or seen_names[name_key]}); skipped"})
            continue
        gst = values.get("gst_number")
        if gst and (gst in gsts or gst in seen_gst):
            rows.append({**row, "status": "duplicate", "message":
                         f"GSTIN {gst} already belongs to {gsts.get(gst) or seen_gst[gst]}; skipped"})
            continue
        code = values.get("vendor_code")
        if code and (code.lower() in codes or code.lower() in seen_codes):
            rows.append({**row, "status": "duplicate", "message": f"Vendor code {code} is already used; skipped"})
            continue
        if not code:
            while True:
                counter += 1
                code = f"VND-{str(counter).zfill(4)}"
                if code.lower() not in codes and code.lower() not in seen_codes:
                    break
        seen_codes.add(code.lower())
        seen_names[name_key] = code
        if gst:
            seen_gst[gst] = code
        values["vendor_code"] = code
        to_add.append(values)
        rows.append({**row, "status": "ready", "vendor_code": code, "message": "; ".join(notes) or None})

    created = 0
    if not dry_run and to_add:
        first = None
        for values in to_add:
            vendor = Vendor(society_id=society_id, registered_by=user.id, **{**values, "category": VendorCategory(values["category"])})
            db.add(vendor)
            db.flush()
            first = first or vendor
        _audit(db, first, user, request, new_values={"imported": len(to_add), "file": filename, "first_code": first.vendor_code})
        db.commit()
        created = len(to_add)
        for r in rows:
            if r["status"] == "ready":
                r["status"] = "created"
    return {
        "dry_run": dry_run, "file_name": filename or "", "sheet": sheet, "total_rows": len(body),
        "columns": columns, "fields": fields,
        "ready": sum(1 for r in rows if r["status"] == "ready"), "created": created,
        "duplicates": sum(1 for r in rows if r["status"] == "duplicate"),
        "errors": sum(1 for r in rows if r["status"] == "error"), "rows": rows,
    }


# ── TDS review ────────────────────────────────────────────────────────────────

def _review_one(v: Vendor) -> dict:
    """What is wrong with a vendor's TDS setup, and the fix that can be worked out from what is known."""
    issues: List[dict] = []
    suggested_constitution = suggested_section = None
    pan_kind = vi.PAN_CONSTITUTION.get(v.pan_number[3]) if v.pan_number and len(v.pan_number) == 10 else None
    if not v.constitution:
        suggested_constitution = pan_kind or vi.constitution_from_name(v.company_name)
        issues.append({"code": "no_type", "message": "No type: TDS can't be worked out" + (
            f" (the PAN suggests {t.constitution_label(suggested_constitution)})" if suggested_constitution else "")})
    else:
        clash = t.pan_mismatch(v.pan_number, v.constitution)
        if clash:
            suggested_constitution = pan_kind
            issues.append({"code": "pan_mismatch", "message": clash})
    effective_type = v.constitution or suggested_constitution
    if effective_type and not v.tds_section:
        usual = t.CATEGORY_DEFAULT_SECTION.get(v.category.value)
        if usual:
            suggested_section = usual
            issues.append({"code": "no_section", "message":
                           f"No TDS section: nothing is deducted. {v.category.value.replace('_', ' ').title()} vendors "
                           f"are usually paid under {t.SECTION_LABELS.get(usual, usual)}"})
    if effective_type and not v.pan_number:
        issues.append({"code": "no_pan", "message": "No PAN: TDS is deducted at 20% when this vendor is paid"})
    return {
        "id": str(v.id), "vendor_code": v.vendor_code, "company_name": v.company_name,
        "category": v.category.value, "status": v.status.value, "pan_number": v.pan_number,
        "constitution": v.constitution, "constitution_label": t.constitution_label(v.constitution),
        "tds_section": v.tds_section, "tds_section_label": t.SECTION_LABELS.get(v.tds_section or ""),
        "issues": issues, "suggested_constitution": suggested_constitution,
        "suggested_constitution_label": t.constitution_label(suggested_constitution),
        "suggested_section": suggested_section, "suggested_section_label": t.SECTION_LABELS.get(suggested_section or ""),
        "can_fix": bool(suggested_constitution or suggested_section),
    }


def tds_review(db: Session, society_id: UUID, only_issues: bool = False) -> dict:
    vendors = db.query(Vendor).filter(Vendor.society_id == society_id, Vendor.is_active == True)\
        .order_by(Vendor.company_name).all()  # noqa: E712
    rows = [_review_one(v) for v in vendors]
    needs = [r for r in rows if r["issues"]]
    return {
        "total": len(rows), "with_issues": len(needs), "fixable": sum(1 for r in needs if r["can_fix"]),
        "no_type": sum(1 for r in rows if any(i["code"] == "no_type" for i in r["issues"])),
        "vendors": needs if only_issues else rows,
    }


def apply_tds_review(db: Session, society_id: UUID, items: Optional[List[dict]], use_suggestions: bool,
                     user: User, request=None) -> dict:
    """Fix vendors' type and section. `items` are explicit {vendor_id, constitution?, tds_section?}; with
    `use_suggestions` every other vendor with a worked-out fix gets it. Each is checked as a vendor edit is (the type
    must agree with the PAN), and a vendor that fails is reported and left unchanged."""
    from app.modules.vendor.services.vendor_service import VendorService_
    vendors: Dict[str, Vendor] = {str(v.id): v for v in db.query(Vendor).filter(
        Vendor.society_id == society_id, Vendor.is_active == True)}  # noqa: E712
    wanted: Dict[str, dict] = {}
    for it in items or []:
        vid = str(it.get("vendor_id"))
        if vid not in vendors:
            raise HTTPException(422, "A vendor in the list isn't in this society")
        wanted[vid] = {k: it[k] for k in ("constitution", "tds_section") if it.get(k)}
    if use_suggestions:
        for vid, v in vendors.items():
            if vid in wanted:
                continue
            r = _review_one(v)
            fix = {}
            if r["suggested_constitution"]:
                fix["constitution"] = r["suggested_constitution"]
            if r["suggested_section"]:
                fix["tds_section"] = r["suggested_section"]
            elif fix.get("constitution") and not v.tds_section:
                usual = t.CATEGORY_DEFAULT_SECTION.get(v.category.value)
                if usual:
                    fix["tds_section"] = usual
            if fix:
                wanted[vid] = fix
    fixed, failed = [], []
    for vid, fix in wanted.items():
        v = vendors[vid]
        merged = {"pan_number": v.pan_number, "constitution": v.constitution, "tds_section": v.tds_section,
                  "tds_lower_rate": v.tds_lower_rate, "tds_lower_valid_from": v.tds_lower_valid_from,
                  "tds_lower_valid_to": v.tds_lower_valid_to, **fix}
        try:
            VendorService_._check_tds_setup(merged)
        except HTTPException as e:
            failed.append({"vendor_id": vid, "company_name": v.company_name, "message": e.detail})
            continue
        old = {k: getattr(v, k) for k in fix}
        for k, val in fix.items():
            setattr(v, k, val)
        _audit(db, v, user, request, old_values={k: str(x) if x is not None else None for k, x in old.items()},
               new_values={k: str(x) for k, x in fix.items()})
        fixed.append({"vendor_id": vid, "company_name": v.company_name, **fix})
    db.commit()
    return {"fixed": fixed, "failed": failed}
