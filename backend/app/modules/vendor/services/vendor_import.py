"""Reading a vendor master from an Excel (.xlsx) or CSV file.

Pure parsing, no database: `read_table` turns the file into a header row and data rows, `auto_map` matches its
headings to the vendor fields, and `parse_row` turns one row into the values for a Vendor or the reasons it can't be.
VendorService_.import_vendors does the checking against the society's existing vendors and the saving.

TDS depends on what kind of person or firm the vendor is, so the import works that out for every row: from the Type
column when there is one ("Pvt Ltd", "Proprietor", "Partnership"...), otherwise from the 4th letter of the PAN (P =
individual, C = company, F = firm...), otherwise from a company-style name ("... Pvt Ltd", "... LLP"). The section
(194C contract, 194J professional...) comes from the Section column, otherwise from the vendor's category. Whatever was
worked out rather than given is said in the row's notes, so it can be checked.
"""
import csv
import io
import re
from typing import Any, Dict, List, Optional, Tuple

from app.modules.inventory.services.asset_import import (
    ImportFileError, MAX_BYTES, MAX_ROWS, HEADER_SEARCH_ROWS, _csv_rows, _xlsx_rows, _key, _text, _col_letter,
    column_labels, parse_date, parse_money,
)
from app.modules.vendor.models.vendor import VendorCategory
from app.modules.vendor.services.vendor_tds import (
    CATEGORY_DEFAULT_SECTION, CONSTITUTION_VALUES, SECTION_VALUES, constitution_label,
)

__all__ = ["ImportFileError", "MAX_BYTES", "column_labels", "_text"]

# field -> (label, [heading names, written the way _key() writes them])
FIELDS: Dict[str, Tuple[str, List[str]]] = {
    "vendor_code": ("Vendor code", ["vendorcode", "vendorid", "code", "vendorno", "suppliercode", "supplierid"]),
    "company_name": ("Vendor name", ["vendorname", "name", "companyname", "company", "vendor", "supplier",
                                     "suppliername", "firmname", "nameofvendor", "partyname", "party", "ledgername"]),
    "contact_person": ("Contact person", ["contactperson", "contactname", "person", "contact", "ownername",
                                          "representative", "spoc"]),
    "mobile": ("Mobile", ["mobile", "mobileno", "mobilenumber", "phone", "phoneno", "phonenumber", "contactno",
                          "contactnumber", "cell", "cellno", "telephone", "tel"]),
    "email": ("Email", ["email", "emailid", "emailaddress", "mail"]),
    "category": ("Category", ["category", "vendorcategory", "servicetype", "service", "nature", "natureofservice",
                              "natureofwork", "trade", "workcategory", "kind"]),
    "constitution": ("Type (for TDS)", ["type", "vendortype", "constitution", "constitutiontype", "entitytype",
                                        "typeofvendor", "typeoffirm", "firmtype", "legalstatus",
                                        "assesseetype", "assesseestatus", "typeofentity", "organisationtype"]),
    "pan_number": ("PAN", ["pan", "panno", "pannumber", "pancard", "pancard", "permanentaccountnumber"]),
    "gst_number": ("GSTIN", ["gst", "gstin", "gstno", "gstnumber", "gstinno", "gstregistrationnumber"]),
    "tds_section": ("TDS section", ["tdssection", "section", "tds", "tdscode", "natureofpayment", "tdsnature",
                                    "paymentsection"]),
    "address": ("Address", ["address", "addr", "streetaddress", "officeaddress"]),
    "city": ("City", ["city", "town", "location"]),
    "pincode": ("Pincode", ["pincode", "pin", "zip", "zipcode", "postalcode"]),
    "bank_account": ("Bank account no.", ["bankaccount", "bankaccountno", "bankaccountnumber", "accountno",
                                          "accountnumber", "acno", "acnumber", "accno"]),
    "bank_name": ("Bank name", ["bankname", "bank", "nameofbank"]),
    "bank_ifsc": ("IFSC", ["ifsc", "ifsccode", "bankifsc", "ifscno"]),
    "tds_lower_rate": ("Lower TDS rate (%)", ["lowertdsrate", "lowerdeductionrate", "lowerrate", "certificaterate",
                                              "section197rate", "tdslowerrate"]),
    "tds_lower_cert_no": ("Lower-deduction certificate no.", ["certificateno", "certificatenumber",
                                                              "lowerdeductioncertificate", "section197certificate",
                                                              "lowerdeductioncertno", "certno"]),
    "tds_lower_valid_from": ("Certificate valid from", ["certificatevalidfrom", "certvalidfrom", "validfrom"]),
    "tds_lower_valid_to": ("Certificate valid to", ["certificatevalidto", "certvalidto", "validto", "validtill",
                                                    "validupto", "certificatevalidtill"]),
    "notes": ("Notes", ["notes", "remarks", "comments", "description", "details"]),
}
FIELD_LABELS = {k: v[0] for k, v in FIELDS.items()}
_BY_KEY = {key: field for field, (_, keys) in FIELDS.items() for key in keys}

TEXT_LIMITS = {"vendor_code": 20, "company_name": 255, "contact_person": 255, "address": 1000, "city": 100,
               "bank_name": 100, "tds_lower_cert_no": 50, "notes": 2000}


def _header_row(rows: List[List[Any]]) -> int:
    best, best_hits = 0, 0
    for i, r in enumerate(rows[:HEADER_SEARCH_ROWS]):
        hits = len({_BY_KEY[_key(c)] for c in r if _key(c) in _BY_KEY})
        if hits > best_hits:
            best, best_hits = i, hits
    return best


def read_table(data: bytes, filename: str) -> Tuple[List[Any], List[Tuple[int, List[Any]]], str]:
    """(header cells, [(line number in the file, cells)], sheet name) from an .xlsx or .csv file."""
    if not data:
        raise ImportFileError("The file is empty.")
    if len(data) > MAX_BYTES:
        raise ImportFileError(f"The file is larger than {MAX_BYTES // (1024 * 1024)} MB. Split it and import in parts.")
    name = (filename or "").lower()
    if data[:4] == b"PK\x03\x04" or name.endswith((".xlsx", ".xlsm")):
        raw, sheet = _xlsx_rows(data)
    elif data[:8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" or name.endswith(".xls"):
        raise ImportFileError("Old Excel files (.xls) can't be read. Open it in Excel and Save As .xlsx or .csv.")
    else:
        raw, sheet = _csv_rows(data), "CSV"
    rows = [(n, r) for n, r in enumerate(raw, start=1) if any(_text(c) for c in r)]
    if not rows:
        raise ImportFileError("No data found in the file.")
    start = _header_row([r for _, r in rows])
    header, body = rows[start][1], rows[start + 1:]
    if len(body) > MAX_ROWS:
        raise ImportFileError(f"The file has {len(body)} rows; the limit is {MAX_ROWS} per import. Split it.")
    return header, body, sheet


def auto_map(header: List[Any]) -> List[Optional[str]]:
    taken, out = set(), []
    for cell in header:
        field = _BY_KEY.get(_key(cell))
        if field and field not in taken:
            taken.add(field)
            out.append(field)
        else:
            out.append(None)
    return out


def apply_override(header_map: List[Optional[str]], header: List[Any], override: Optional[Dict[str, Optional[str]]]
                   ) -> List[Optional[str]]:
    if not override:
        return header_map
    out = list(header_map)
    for i, cell in enumerate(header):
        label = _text(cell) or f"Column {_col_letter(i)}"
        if label in override:
            field = override[label]
            if field not in (None, "") and field not in FIELDS:
                raise ImportFileError(f"'{field}' is not a field that can be imported.")
            out[i] = field or None
    seen = set()
    for f in out:
        if f:
            if f in seen:
                raise ImportFileError(f"Two columns are set to {FIELD_LABELS[f]}; each field can come from one column.")
            seen.add(f)
    return out


# ── Values ────────────────────────────────────────────────────────────────────

_CATEGORY_WORDS = [
    ("lift", ["lift", "elevator", "escalator"]),
    ("cctv", ["cctv", "camera", "surveillance", "access control", "biometric"]),
    ("generator", ["generator", "dg", "genset", "diesel"]),
    ("security", ["security", "guard", "manpower", "watchman", "bouncer"]),
    ("housekeeping", ["housekeeping", "house keeping", "cleaning", "cleaner", "sweeping", "janitorial", "facility",
                      "facilities", "sanitation"]),
    ("gardening", ["garden", "gardening", "landscape", "landscaping", "horticulture", "lawn"]),
    ("pest_control", ["pest", "pest control", "termite", "fumigation", "rodent"]),
    ("water_supply", ["water", "tanker", "water supply", "borewell", "stp", "wtp", "plant operator"]),
    ("electrical", ["electrical", "electrician", "electric", "wiring", "lighting", "ups", "transformer"]),
    ("plumbing", ["plumbing", "plumber", "pipe", "pipes", "sanitary", "drainage"]),
    ("civil", ["civil", "construction", "contractor", "painting", "painter", "waterproofing", "mason", "repair",
               "repairs", "carpentry", "carpenter", "renovation", "fabrication"]),
    ("it", ["it", "software", "computer", "network", "website", "app", "erp", "technology"]),
    ("other", ["other", "others", "misc", "miscellaneous", "general"]),
]


def _words(text: str) -> str:
    return " " + re.sub(r"[^a-z0-9]+", " ", text.lower()).strip() + " "


def parse_category(text: str) -> Optional[str]:
    w = _words(text)
    if not w.strip():
        return None
    for v in (c.value for c in VendorCategory):
        if w.strip() == v.replace("_", " "):
            return v
    for value, words in _CATEGORY_WORDS:
        if any(f" {k} " in w for k in words):
            return value
    return None


# Words people use for the vendor's type, in the order they are tried ("private limited" before "limited").
_CONSTITUTION_WORDS = [
    ("llp", ["llp", "limited liability partnership", "llc"]),
    ("private_limited", ["private limited", "pvt ltd", "pvt limited", "p ltd", "pvt", "private", "opc",
                         "one person company"]),
    ("public_limited", ["public limited", "public ltd", "limited", "ltd", "corporation", "corp"]),
    ("partnership_firm", ["partnership", "partnership firm", "firm", "partners"]),
    ("huf", ["huf", "hindu undivided family"]),
    ("individual_proprietor", ["individual", "proprietor", "proprietorship", "proprietary", "sole proprietor",
                               "sole proprietorship", "self", "person", "freelancer", "natural person",
                               "individual proprietor"]),
    ("aop_boi", ["aop", "boi", "association", "association of persons", "body of individuals"]),
    ("cooperative_society", ["cooperative", "co operative", "coop", "co op", "cooperative society", "society"]),
    ("trust", ["trust", "charitable trust", "foundation"]),
    ("government", ["government", "govt", "municipal", "corporation government", "local authority", "public sector"]),
    ("other", ["other", "others"]),
]

# The 4th letter of a PAN names the kind of holder.
PAN_CONSTITUTION = {"P": "individual_proprietor", "H": "huf", "F": "partnership_firm", "C": "private_limited",
                    "A": "aop_boi", "B": "aop_boi", "T": "trust", "G": "government", "L": "government",
                    "J": "government"}


def parse_constitution(text: str) -> Optional[str]:
    w = _words(text)
    if not w.strip():
        return None
    for v in CONSTITUTION_VALUES:
        if w.strip() == v.replace("_", " "):
            return v
    for value, words in _CONSTITUTION_WORDS:
        if any(f" {k} " in w for k in words):
            return value
    return None


def constitution_from_name(name: str) -> Optional[str]:
    """A company-style name says what it is: '... Pvt Ltd', '... LLP'. Names like '... Enterprises' or '& Co' say
    nothing, so those give None."""
    w = _words(name)
    if " llp " in w:
        return "llp"
    if any(f" {k} " in w for k in ("pvt ltd", "pvt limited", "private limited", "p ltd")):
        return "private_limited"
    if any(f" {k} " in w for k in ("limited", "ltd")):
        return "public_limited"
    return None


_SECTION_WORDS = [
    ("194J_PROF", ["194jb", "194j b", "194j professional", "194j prof", "professional", "professional fees",
                   "professional fee", "fees for professional services", "194j"]),
    ("194J_TECH", ["194ja", "194j a", "194j technical", "technical", "technical services", "technical service"]),
    ("194I_PM", ["194ia", "194i a", "plant and machinery", "plant machinery", "machinery rent", "rent machinery"]),
    ("194I_LB", ["194ib", "194i b", "194i", "rent", "building rent", "land rent", "rent building", "property rent"]),
    ("194H", ["194h", "commission", "brokerage"]),
    ("194C", ["194c", "contract", "contractor", "works contract", "work contract", "job work"]),
]


def parse_section(text: str) -> Optional[str]:
    t = _text(text)
    if not t:
        return None
    if t.upper() in SECTION_VALUES:
        return t.upper()
    w = _words(t)
    for value, words in _SECTION_WORDS:
        if any(f" {k} " in w for k in words):
            return value
    return None


def _no_tds(text: str) -> bool:
    return _words(text).strip() in ("no", "none", "nil", "na", "n a", "not applicable", "exempt", "no tds")


# ── One row ───────────────────────────────────────────────────────────────────

def parse_row(raw: List[Any], field_map: List[Optional[str]]) -> Tuple[Dict[str, Any], List[str], List[str]]:
    """(values for the Vendor, errors, notes). Errors mean the row is not imported; notes are things filled in or
    worked out that the person should know."""
    cells: Dict[str, Any] = {}
    for i, field in enumerate(field_map):
        if field and i < len(raw):
            cells[field] = raw[i]
    values: Dict[str, Any] = {}
    errors: List[str] = []
    notes: List[str] = []

    for field, limit in TEXT_LIMITS.items():
        t = _text(cells.get(field))
        if len(t) > limit:
            errors.append(f"{FIELD_LABELS[field]} is longer than {limit} characters")
        elif t:
            values[field] = t
    if "company_name" not in values and not any("Vendor name" in e for e in errors):
        errors.append("Vendor name is required")

    from app.schemas import validators as val
    mobile = _text(cells.get("mobile"))
    if not mobile:
        errors.append("Mobile is required")
    else:
        # several numbers in one cell ("98..., 99...") — the first is the vendor's
        first = re.split(r"[,/;\n]", mobile)[0].strip()
        try:
            m = val.mobile_any(first)
        except ValueError as e:
            m = None
        if not m or not re.fullmatch(r"\+?\d{7,15}", m):
            errors.append(f"Mobile '{mobile}' is not a phone number")
        else:
            values["mobile"] = m
            if first != mobile:
                notes.append("More than one number given; the first is used")

    email = _text(cells.get("email"))
    if email:
        try:
            values["email"] = val.email(re.split(r"[,;\s]", email)[0])
        except ValueError:
            errors.append(f"Email '{email}' is not valid")

    raw_cat = _text(cells.get("category"))
    cat = parse_category(raw_cat)
    if cat is None:
        values["category"] = "other"
        notes.append(f"Category '{raw_cat}' not recognised, imported as Other" if raw_cat
                     else "No category, imported as Other")
    else:
        values["category"] = cat

    pincode = _text(cells.get("pincode"))
    if pincode:
        if re.fullmatch(r"\d{6}", pincode):
            values["pincode"] = pincode
        else:
            errors.append(f"Pincode '{pincode}' must be 6 digits")

    from app.modules.vendor.routes.vendor import _PAN, _GST, _IFSC
    pan = _text(cells.get("pan_number")).replace(" ", "").upper()
    if pan:
        if _PAN.match(pan):
            values["pan_number"] = pan
        else:
            errors.append(f"PAN '{pan}' is not valid (e.g. ABCDE1234F)")
    gst = _text(cells.get("gst_number")).replace(" ", "").upper()
    if gst:
        if _GST.match(gst):
            values["gst_number"] = gst
        else:
            errors.append(f"GSTIN '{gst}' is not valid (15 characters)")
    ifsc = _text(cells.get("bank_ifsc")).replace(" ", "").upper()
    if ifsc:
        if _IFSC.match(ifsc):
            values["bank_ifsc"] = ifsc
        else:
            errors.append(f"IFSC '{ifsc}' is not valid (e.g. HDFC0001234)")
    acct = _text(cells.get("bank_account")).replace(" ", "").replace("-", "")
    if acct:
        if re.fullmatch(r"[0-9A-Za-z]{5,34}", acct):
            values["bank_account"] = acct
        else:
            errors.append("Bank account number is not valid")

    # ── TDS: the vendor's type, then the section ──
    raw_type = _text(cells.get("constitution"))
    constitution = parse_constitution(raw_type) if raw_type else None
    if raw_type and constitution is None:
        notes.append(f"Type '{raw_type}' not recognised")
    pan_kind = PAN_CONSTITUTION.get(values["pan_number"][3]) if values.get("pan_number") else None
    if constitution is None:
        constitution = pan_kind or constitution_from_name(values.get("company_name", ""))
        if constitution:
            how = "its PAN" if pan_kind else "its name"
            notes.append(f"Type worked out from {how}: {constitution_label(constitution)}")
    elif pan_kind and values.get("pan_number"):
        from app.modules.vendor.services.vendor_tds import pan_mismatch
        clash = pan_mismatch(values["pan_number"], constitution)
        if clash:
            errors.append(clash)
    if constitution:
        values["constitution"] = constitution
    else:
        notes.append("Type unknown: TDS can't be worked out until it is set (Vendors > TDS review)")

    raw_section = _text(cells.get("tds_section"))
    if raw_section and _no_tds(raw_section):
        notes.append("No TDS section: nothing will be deducted")
    elif raw_section:
        section = parse_section(raw_section)
        if section is None:
            notes.append(f"TDS section '{raw_section}' not recognised")
        elif constitution:
            values["tds_section"] = section
    if constitution and "tds_section" not in values and not (raw_section and _no_tds(raw_section)):
        usual = CATEGORY_DEFAULT_SECTION.get(values["category"])
        if usual:
            values["tds_section"] = usual
            notes.append(f"TDS section {usual} (usual for this category)")

    if values.get("constitution") and not values.get("pan_number"):
        notes.append("No PAN: TDS would be deducted at 20% when paid")

    # ── Lower-deduction certificate ──
    rate = _text(cells.get("tds_lower_rate"))
    if rate:
        r = parse_money(rate.replace("%", ""))
        if r is None or not (0 <= r <= 30):
            errors.append(f"Lower TDS rate '{rate}' must be between 0 and 30")
        else:
            values["tds_lower_rate"] = r
    for field in ("tds_lower_valid_from", "tds_lower_valid_to"):
        if _text(cells.get(field)):
            d = parse_date(cells.get(field))
            if d is None:
                errors.append(f"{FIELD_LABELS[field]} '{_text(cells.get(field))}' is not a date (use dd/mm/yyyy)")
            else:
                values[field] = d
    if values.get("tds_lower_valid_from") and values.get("tds_lower_valid_to") \
            and values["tds_lower_valid_to"] < values["tds_lower_valid_from"]:
        errors.append("The certificate's valid-to date is before its valid-from date")
    if values.get("tds_lower_rate") is not None and not values.get("constitution"):
        errors.append("A lower-deduction certificate needs the vendor's type")
    return values, errors, notes


# ── The template ──────────────────────────────────────────────────────────────

TEMPLATE_HEADINGS = ["Vendor Name", "Category", "Type", "PAN", "GSTIN", "TDS Section", "Contact Person", "Mobile",
                     "Email", "Address", "City", "Pincode", "Bank Name", "Bank Account No", "IFSC",
                     "Lower TDS Rate (%)", "Certificate No", "Certificate Valid From", "Certificate Valid To", "Notes"]
_TEMPLATE_SAMPLES = [
    ["Sparkle Housekeeping Services", "Housekeeping", "Proprietor", "ABCPK1234F", "", "194C", "Ramesh Kumar",
     "9876543210", "sparkle@example.com", "Shop 4, Main Road", "Pune", "411001", "HDFC Bank", "50100012345678",
     "HDFC0001234", "", "", "", "", ""],
    ["Shield Security Pvt Ltd", "Security", "Pvt Ltd", "AABCS1234P", "27AABCS1234P1Z5", "194C", "Anil Rao",
     "9822012345", "", "", "Pune", "", "", "", "", "0.5", "LDC/2026/118", "01/04/2026", "31/03/2027", ""],
    ["CA Mehta & Associates", "Other", "Partnership firm", "AAFFM1234Q", "", "Professional fees", "", "9811122233",
     "", "", "", "", "", "", "", "", "", "", "", ""],
]


def template_csv() -> str:
    """A CSV with every importable column and example rows. Vendor Name and Mobile are required; Type (or a PAN, or a
    'Pvt Ltd' / 'LLP' name) decides the TDS rate."""
    out = io.StringIO()
    w = csv.writer(out, lineterminator="\n")
    w.writerow(TEMPLATE_HEADINGS)
    w.writerows(_TEMPLATE_SAMPLES)
    return out.getvalue()
