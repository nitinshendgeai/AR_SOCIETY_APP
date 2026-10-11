"""The built-in checklist a society starts with.

Three kinds of item:

- routine work — daily, weekly and monthly rounds that apply only when the society has the asset or the staff
  they are about (a lift check only where there is a lift, a gate-register check only where there are guards);
- statutory and compliance dates that apply to every society in India ("central");
- the same for Maharashtra, for a society whose state is Maharashtra.

IMPORTANT: the legal items are a working starting list, not legal advice. Dates, forms and thresholds change by
notification, and a society's own registration and bye-laws decide what applies to it. Each item carries its legal
basis so the committee or its advisor can check it, switch it off or reword it. A society in another state gets the
central items and adds its own state's rules as items of its own.
"""
from typing import Dict, List, Optional

PACKS = ("central", "maharashtra")


def _item(code: str, title: str, category: str, frequency: str = "daily", *, detail: str = "",
          weekday: Optional[int] = None, day: Optional[int] = None, months: str = "", lead: int = 0,
          asset: Optional[str] = None, staff: Optional[str] = None, statutory: bool = False, basis: str = "",
          pack: Optional[str] = None, link: Optional[str] = None, order: int = 100) -> Dict:
    return {"code": code, "title": title, "detail": detail, "category": category, "frequency": frequency,
            "due_weekday": weekday, "due_day": day, "due_months": months or None, "lead_days": lead,
            "asset_category": asset, "staff_department": staff, "statutory": statutory, "legal_basis": basis or None,
            "jurisdiction": pack, "link_key": link, "sort_order": order}


MON, TUE, WED, THU, FRI, SAT, SUN = range(7)

# ── Daily routine ───────────────────────────────────────────────────────────────────────────────────────────────
DAILY: List[Dict] = [
    _item("walk_round", "Walk round the premises", "housekeeping",
          detail="Gate, lobbies, staircases, parking, terrace, garden and common toilets. Note what needs fixing and "
                 "raise a complaint or task for each.", link="complaints", order=10),
    _item("gate_register", "Check the gate register and last night's incidents", "security", staff="security",
          detail="Visitor log, vehicle entries and any incident reported by the night guard. Follow up anything "
                 "unusual.", link="visitors", order=11),
    _item("guard_turnout", "Guards on post, in uniform, with ID and patrol rounds signed", "security", staff="security",
          detail="Every post manned, relieving guards on time, patrol checkpoints signed, torches and radios in "
                 "working order.", link="staff", order=12),
    _item("attendance", "Confirm every staff member is on duty; arrange substitutes", "staff", staff="any",
          detail="Compare check-ins with the duty roster. Arrange cover for any absence before it leaves a post "
                 "empty.", link="staff", order=13),
    _item("duties_briefing", "Review today's duties and checklists with the supervisors", "staff", staff="any",
          detail="Each department's duties are assigned, with their checklists, and understood.", link="staff",
          order=14),
    _item("housekeeping_inspect", "Inspect cleaning and garbage handling", "housekeeping", staff="housekeeping",
          detail="Lobbies, staircases, lifts, toilets and parking are clean; wet and dry waste is segregated and "
                 "collected before the municipal vehicle arrives.", link="staff",
          basis="Solid Waste Management Rules — segregation at source", pack="central", order=15),
    _item("garden_upkeep", "Garden watered and kept", "housekeeping", staff="gardening",
          detail="Watering done, no stagnant water, cuttings removed.", link="staff", order=16),
    _item("technical_jobs", "Review the technical team's jobs (plumbing, electrical, repairs)", "technical",
          staff="technical", detail="Jobs from complaints and job cards are done or have a date.",
          link="complaints", order=17),
    _item("complaints_review", "Review new and pending complaints", "residents",
          detail="Assign new complaints, chase the ones that are late, close the ones that are fixed.",
          link="complaints", order=20),
    _item("cash_tally", "Tally cash in hand and enter yesterday's receipts and payments", "accounts",
          detail="Physical cash matches the cash book; every receipt and payment is entered with its voucher.",
          link="cash_bank_book", order=30),
    _item("bank_cash_cheques", "Bank the cash and cheques received", "accounts",
          detail="Cheques and cash received are banked the same or next working day, and entered as receipts.",
          link="accounts", order=31),
    _item("parking_walk", "Walk through parking", "safety",
          detail="Unauthorised or abandoned vehicles, fire lane and hydrant access kept clear.",
          link="parking", order=40),
    # Assets
    _item("lift_check", "Lifts: running, alarm, intercom, light and fan working; nobody trapped overnight", "assets",
          asset="lift", detail="Check every lift. Note any fault in the lift log and call the AMC vendor.",
          link="assets", order=50),
    _item("dg_check", "Generator: fuel, battery, oil and coolant; auto-start ready", "assets", asset="generator",
          detail="Fuel above the minimum, battery charged, no leaks, changeover panel in auto.",
          link="assets", order=51),
    _item("water_tank_pump", "Water: tank and sump levels, pumps running, no leaks or overflow", "technical",
          asset="water_tank", detail="Overhead tank and sump levels, float switches, pump running time, "
                                      "valves.", link="assets", order=52),
    _item("pump_check", "Pumps: running smoothly, no leaks, panel healthy", "technical", asset="pump",
          detail="Listen for noise and vibration; check pressure and the panel.", link="assets", order=53),
    _item("fire_check", "Fire safety: panel normal, extinguisher gauges green, exits and hydrants clear",
          "safety", asset="fire_safety",
          detail="No fault or alarm on the fire panel, extinguishers in place with seals intact, escape routes "
                 "free of obstruction.", link="assets",
          basis="Fire safety rules and NBC 2016 Part 4; Maharashtra Fire Prevention and Life Safety Measures Act, "
                "2006 (Maharashtra)", order=54),
    _item("cctv_check", "CCTV: every camera live and recording; date and time correct", "security", asset="cctv",
          detail="Check the monitor and the recorder's storage days.", link="assets", order=55),
    _item("intercom_check", "Intercom and gate communication tested", "security", asset="intercom",
          detail="Gate to flats and gate to office both work.", link="assets", order=56),
    _item("biometric_check", "Biometric / access devices working and in sync", "security", asset="biometric",
          link="assets", order=57),
    _item("stp_check", "STP / water treatment: running, blowers on, readings logged", "technical",
          asset="water_treatment", detail="Treated-water quality, chemical dosing, sludge, and the day's log "
                                           "entry.", link="assets",
          basis="Water (Prevention and Control of Pollution) Act, 1974 — consent conditions", pack="central",
          order=58),
    _item("electrical_check", "Common lights and electrical panels: nothing out, no sparking or heating", "technical",
          asset="electrical", detail="Staircase, lobby, parking and street lights; panel rooms locked and dry.",
          link="assets", order=59),
    _item("solar_check", "Solar: inverter generating, no alarms", "assets", asset="solar", link="assets", order=60),
    _item("gym_check", "Gym: equipment safe to use; broken machines taped off", "assets", asset="gym_equipment",
          link="assets", order=61),
    _item("vehicle_log", "Society vehicle: log, fuel and condition", "assets", asset="vehicle", link="assets",
          order=62),
]

# ── Weekly ───────────────────────────────────────────────────────────────────────────────────────────────────────
WEEKLY: List[Dict] = [
    _item("w_staff_roster", "Prepare next week's duty roster and approve leave", "staff", "weekly", weekday=MON,
          staff="any", link="staff", order=200),
    _item("w_defaulters", "Follow up on defaulters: reminders and calls", "accounts", "weekly", weekday=MON,
          link="defaulters", order=201),
    _item("w_mosquito", "Check terrace, tanks and sumps for stagnant water and mosquito breeding", "safety", "weekly",
          weekday=SAT, detail="Open the tank lids, clear water pooling on the terrace and in the basement.",
          basis="Municipal public-health rules on mosquito breeding", pack="central", order=202),
    _item("w_stores", "Check consumable stock against the stores register", "assets", "weekly", weekday=FRI,
          link="inventory", order=203),
    _item("w_dg_test", "Run the generator on load for 10–15 minutes", "assets", "weekly", weekday=SAT,
          asset="generator", detail="Record running hours, fuel used and any fault.", link="assets", order=204),
    _item("w_fire_pumps", "Test the fire pump, jockey pump and alarm", "safety", "weekly", weekday=TUE,
          asset="fire_safety", detail="Run the hydrant pumps and sound the alarm; record the readings.",
          link="assets", order=205),
    _item("w_lift_room", "Lift machine rooms and pits: clean, dry and locked", "assets", "weekly", weekday=WED,
          asset="lift", link="assets", order=206),
    _item("w_solar_clean", "Solar panels cleaned", "assets", "weekly", weekday=SUN, asset="solar", link="assets",
          order=207),
    _item("w_ac_filters", "Air-conditioner filters cleaned", "assets", "weekly", weekday=THU, asset="air_conditioner",
          link="assets", order=208),
    _item("w_backup", "Back up the society's records from the office computer", "assets", "weekly", weekday=FRI,
          asset="it_equipment", link="assets", order=209),
]

# ── Monthly ──────────────────────────────────────────────────────────────────────────────────────────────────────
MONTHLY: List[Dict] = [
    _item("m_bills", "Generate and issue the month's maintenance bills", "accounts", "monthly", day=1, lead=2,
          link="billing", order=300),
    _item("m_bank_recon", "Reconcile the bank statement with the books", "accounts", "monthly", day=5, lead=2,
          link="bank_reconciliation", order=301),
    _item("m_attendance_final", "Finalise the month's attendance, leave and overtime before salary", "staff",
          "monthly", day=28, lead=3, staff="any", link="staff", order=302),
    _item("m_wages", "Pay the staff's wages by the 7th", "staff", "monthly", day=7, lead=3, staff="any",
          statutory=True, link="accounts",
          detail="Wages for the previous month, by bank transfer where possible, against signed receipts.",
          basis="Payment of Wages Act, 1936 / Code on Wages, 2019 — wages within the prescribed day of the next month",
          pack="central", order=303),
    _item("m_min_wages", "Check wages are not below the minimum wages notified for the work", "staff", "monthly",
          day=28, lead=3, staff="any", statutory=True,
          detail="Security, housekeeping and gardening wages against the current notified rates (they are revised "
                 "periodically).", basis="Minimum Wages Act, 1948 / Code on Wages, 2019", pack="central", order=304),
    _item("m_tds_deposit", "Deposit the TDS deducted last month", "accounts", "monthly", day=7, lead=3,
          statutory=True,
          detail="If TDS was deducted on contractor, professional, rent or salary payments, deposit it by the 7th.",
          basis="Income-tax Act — TDS deposit by the 7th of the next month", pack="central", link="accounts",
          order=305),
    _item("m_pf_esi", "Pay PF and ESIC contributions, if the society is registered", "accounts", "monthly", day=15,
          lead=3, staff="any", statutory=True,
          detail="Employees' Provident Fund and Employees' State Insurance contributions are due by the 15th.",
          basis="Employees' Provident Funds Act, 1952; Employees' State Insurance Act, 1948 (where applicable by "
                "number of employees and wages)", pack="central", order=306),
    _item("m_gst", "File the GST returns, if the society is registered", "accounts", "monthly", day=20, lead=9,
          statutory=True,
          detail="GSTR-1 by the 11th and GSTR-3B by the 20th. Applies only if the society is GST-registered "
                 "(member charges above the exemption limit).", basis="CGST Act, 2017", pack="central", order=307),
    _item("m_pt", "Deduct and deposit Professional Tax", "accounts", "monthly", day=31, lead=5, staff="any",
          statutory=True,
          detail="Deduct from staff whose pay crosses the slab and deposit as the society's enrolment requires.",
          basis="Maharashtra State Tax on Professions, Trades, Callings and Employments Act, 1975",
          pack="maharashtra", order=308),
    _item("m_committee", "Hold the managing committee meeting and circulate the minutes", "residents", "monthly",
          day=28, lead=10, statutory=True, link="meetings",
          detail="Notice and agenda go out in time; minutes are written, signed and recorded.",
          basis="Maharashtra Co-operative Societies Act, 1960 and the model bye-laws — the committee meets at "
                "regular intervals (monthly)", pack="maharashtra", order=309),
    _item("m_registers", "Keep the statutory registers up to date", "residents", "monthly", day=28, lead=5,
          statutory=True,
          detail="Members, share, nomination and transfer registers; the minutes book; the notice register.",
          basis="Maharashtra Co-operative Societies Rules, 1961 and the model bye-laws", pack="maharashtra",
          link="residents", order=310),
    _item("m_vendor_bills", "Check vendor bills against the work and the AMC visits done", "accounts", "monthly",
          day=25, lead=3, link="vendors", order=311),
    _item("m_stock_count", "Count the stores against the register", "assets", "monthly", day=30, lead=3,
          link="inventory", order=312),
    _item("m_pest_control", "Pest control done", "housekeeping", "monthly", day=15, lead=5, order=313),
    _item("m_extinguishers", "Inspect every fire extinguisher, hose and emergency light", "safety", "monthly",
          day=5, lead=3, asset="fire_safety", link="assets",
          basis="Fire safety rules and NBC 2016 Part 4", pack="central", order=314),
    _item("m_lift_amc", "Confirm the lift AMC visit was made; read the lift log", "assets", "monthly", day=28,
          lead=4, asset="lift", link="vendors", order=315),
    _item("m_water_test", "Send water and treated-water samples for testing", "technical", "monthly", day=10,
          lead=3, asset="water_treatment", link="assets",
          basis="Water (Prevention and Control of Pollution) Act, 1974 — consent conditions", pack="central",
          order=316),
    _item("m_police_verification", "Staff, domestic help and new tenants: ID and police verification on file",
          "security", "monthly", day=10, lead=3, statutory=True, link="residents",
          detail="Every new staff member, domestic helper and tenant has ID proof and police verification or "
                 "intimation, where the local police require it.", basis="Local police orders on verification of "
                 "staff, domestic help and tenants", pack="central", order=317),
]

# ── Statutory and compliance dates, central ──────────────────────────────────────────────────────────────────────
CENTRAL: List[Dict] = [
    _item("c_tds_return", "File the TDS return (quarterly)", "compliance", "on_dates", day=31, months="7,10,1,5",
          lead=21, statutory=True,
          detail="Q1 by 31 July, Q2 by 31 October, Q3 by 31 January and Q4 by 31 May. Applies if TDS was "
                 "deducted.", basis="Income-tax Act — TDS statements (Forms 24Q / 26Q)", pack="central", order=400),
    _item("c_advance_tax", "Pay advance tax, if the tax payable is ₹10,000 or more", "compliance", "on_dates",
          day=15, months="6,9,12,3", lead=14, statutory=True,
          detail="Tax on interest and other taxable income. Instalments fall on 15 June, 15 September, 15 December "
                 "and 15 March.", basis="Income-tax Act — advance tax", pack="central", order=401),
    _item("c_itr", "File the society's income-tax return", "compliance", "on_dates", day=31, months="10", lead=30,
          statutory=True,
          detail="Due date is the one for a taxpayer whose accounts are audited; it can be extended by "
                 "notification.", basis="Income-tax Act — return of income", pack="central", order=402),
    _item("c_gst_annual", "File the GST annual return, if registered", "compliance", "on_dates", day=31, months="12",
          lead=30, statutory=True, basis="CGST Act, 2017", pack="central", order=403),
    _item("c_insurance", "Renew the building and common-area insurance", "compliance", "licence", lead=30,
          detail="Fire and allied perils for the buildings; add public liability and machinery cover. Record the "
                 "policy number and the date it runs to.", basis="Bye-laws and prudent practice", pack="central",
          order=404),
    _item("c_electrical", "Electrical safety inspection and earthing test", "compliance", "licence", lead=30,
          asset="electrical", statutory=True,
          detail="Periodic inspection and testing of the installation, earthing and lightning arrester by a "
                 "licensed contractor or the Electrical Inspector. Record the certificate and its date.",
          basis="Electricity Act, 2003 and the CEA safety regulations", pack="central", link="assets", order=405),
    _item("c_stp_consent", "Pollution Control Board consent for the STP", "compliance", "licence", lead=45,
          asset="water_treatment", statutory=True,
          detail="Consent to operate, renewed as the Board requires. Record the consent number and its validity.",
          basis="Water (Prevention and Control of Pollution) Act, 1974", pack="central", link="assets", order=406),
    _item("c_security_agency", "Security agency licence and contractor's registration are valid", "compliance",
          "licence", lead=30, staff="security", statutory=True,
          detail="Ask the agency for its current licence (PSARA) and, for contract labour, the contractor's "
                 "licence; keep copies. Record the date it runs to.",
          basis="Private Security Agencies (Regulation) Act, 2005; Contract Labour (Regulation and Abolition) Act, "
                "1970", pack="central", order=407),
    _item("c_fire_drill", "Fire evacuation drill and staff training (twice a year)", "safety", "on_dates", day=15,
          months="2,8", lead=14, asset="fire_safety",
          detail="Drill for residents and staff, with a record of who took part.",
          basis="NBC 2016 Part 4 and local fire department guidance", pack="central", link="assets", order=408),
    _item("c_water_tank", "Clean the water tanks and sumps (twice a year)", "technical", "on_dates", day=15,
          months="4,10", lead=14, asset="water_tank",
          detail="Drain, scrub, disinfect and refill; keep the cleaning certificate.",
          basis="Municipal public-health guidance", pack="central", link="assets", order=409),
    _item("c_pre_monsoon", "Pre-monsoon check: terrace drains, waterproofing, electrical panels, lightning arrester",
          "safety", "on_dates", day=15, months="5", lead=21, pack="central", order=410),
    _item("c_emergency_list", "Update the emergency contacts displayed at the gate and notice board", "safety",
          "on_dates", day=5, months="1,4,7,10", lead=5,
          detail="Police, fire, ambulance, electrician, plumber, lift vendor, committee office bearers.",
          pack="central", order=411),
]

# ── Maharashtra ──────────────────────────────────────────────────────────────────────────────────────────────────
MAHARASHTRA: List[Dict] = [
    _item("mh_audit", "Complete the statutory audit of the year's accounts", "compliance", "on_dates", day=31,
          months="8", lead=60, statutory=True, link="accounts",
          detail="The accounts of the financial year (ending 31 March) are audited by an auditor from the "
                 "approved panel. The legal outer limit is six months from year end, 30 September; aim to finish "
                 "in time for the AGM notice.",
          basis="Maharashtra Co-operative Societies Act, 1960 — section 81 (audit)", pack="maharashtra", order=500),
    _item("mh_agm", "Hold the Annual General Meeting", "compliance", "on_dates", day=30, months="9", lead=45,
          statutory=True, link="meetings",
          detail="Within six months of the end of the financial year (by 30 September): at least 14 days' written "
                 "notice, the audited statements, the budget, and the appointment of the auditor for the next "
                 "year.", basis="Maharashtra Co-operative Societies Act, 1960 — section 75 (general meeting)",
          pack="maharashtra", order=501),
    _item("mh_returns", "File the audited accounts and annual returns with the Registrar", "compliance",
          "on_dates", day=31, months="10", lead=30, statutory=True,
          detail="After the AGM, file the audit report, balance sheet and the returns the Registrar's office asks "
                 "for. Check the time limit with your Registrar's office.",
          basis="Maharashtra Co-operative Societies Act, 1960 and Rules, 1961", pack="maharashtra", order=502),
    _item("mh_fire_form_b", "Fire Form B: inspection report by a licensed agency (every six months)", "compliance",
          "on_dates", day=31, months="1,7", lead=30, asset="fire_safety", statutory=True, link="assets",
          detail="The licensed agency inspects the fire-fighting installations and submits Form B to the Fire "
                 "Department every January and July. Keep a copy.",
          basis="Maharashtra Fire Prevention and Life Safety Measures Act, 2006", pack="maharashtra", order=503),
    _item("mh_lift_licence", "Lift licence: renew and keep the inspection certificate", "compliance", "licence",
          lead=45, asset="lift", statutory=True, link="assets",
          detail="Each lift is licensed and inspected every year by the Electrical Inspector (Lifts). Record the "
                 "licence number and the date it runs to.",
          basis="Maharashtra Lifts and Escalators Act, 2017", pack="maharashtra", order=504),
    _item("mh_committee_term", "Committee election: hold it before the committee's term ends", "compliance",
          "licence", lead=120, statutory=True, link="meetings",
          detail="The managing committee's term is five years; the election is conducted through the State "
                 "Co-operative Election Authority. Record the date the current term ends.",
          basis="Maharashtra Co-operative Societies Act, 1960 — committee term and elections", pack="maharashtra",
          order=505),
]

ALL_ITEMS: List[Dict] = DAILY + WEEKLY + MONTHLY + CENTRAL + MAHARASHTRA

# Link keys — the app maps each to a screen.
LINK_KEYS = ("complaints", "visitors", "staff", "staff_approvals", "cash_bank_book", "accounts", "recurring",
             "approvals", "parking", "assets", "inventory", "defaulters", "billing", "bank_reconciliation", "vendors",
             "meetings", "residents", "tenants", "pending_changes", "password_resets", "amenities", "certificates",
             "parcels")


def packs_for_state(state: Optional[str]) -> List[str]:
    """The packs a society gets: central always, and its state's own where one is built in."""
    s = (state or "").strip().lower()
    packs = ["central"]
    if "maharashtra" in s:
        packs.append("maharashtra")
    return packs


def items_for(packs: List[str]) -> List[Dict]:
    return [i for i in ALL_ITEMS if i["jurisdiction"] is None or i["jurisdiction"] in packs]
