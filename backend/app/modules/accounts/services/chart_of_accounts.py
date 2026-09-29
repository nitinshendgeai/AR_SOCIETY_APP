"""
The standard chart of accounts every society's books start with — the
heads of the Balance Sheet and Income & Expenditure account a
co-operative housing society keeps under the Maharashtra model bye-laws
and the MCS Act (funds under bye-laws 13 and 67, members' dues, service
charges and the recoveries of bye-laws 66–67, and the usual running
expenses). A society can rename these, set opening balances and add its
own ledgers; the system ledgers (with a system_key) are the ones the
automatic postings from maintenance bills, receipts and vendor bills use.

Codes: 1xxx liabilities & funds, 2xxx assets, 3xxx income, 4xxx expenses.
"""
from typing import Dict, Optional

from sqlalchemy.orm import Session

from app.modules.accounts.models.accounts import Account, AccountGroup
from app.modules.billing.models.billing import ChargeType

# key, name, nature
STANDARD_GROUPS = [
    ("share_capital",        "Share Capital",                          "liability"),
    ("funds",                "Reserve Fund & Other Funds",             "liability"),
    ("ie_account",           "Income & Expenditure Account",           "liability"),
    ("loans",                "Loans",                                  "liability"),
    ("current_liabilities",  "Current Liabilities & Provisions",       "liability"),
    ("fixed_assets",         "Fixed Assets",                           "asset"),
    ("investments",          "Investments",                            "asset"),
    ("current_assets",       "Current Assets, Loans & Advances",       "asset"),
    ("cash_bank",            "Cash & Bank Balances",                   "asset"),
    ("income_members",       "Income from Members",                    "income"),
    ("other_income",         "Other Income",                           "income"),
    ("admin_expenses",       "Establishment & Administrative Expenses", "expense"),
    ("maintenance_expenses", "Repairs & Maintenance Expenses",         "expense"),
    ("utility_expenses",     "Utilities, Taxes & Insurance",           "expense"),
    ("other_expenses",       "Other Expenses",                         "expense"),
]

# group key, system key, code, name, extra flags
STANDARD_LEDGERS = [
    # Liabilities & funds
    ("share_capital", "share_capital", "1001", "Share Capital", {}),
    ("funds", "reserve_fund", "1101", "Reserve Fund", {}),
    ("funds", "sinking_fund", "1102", "Sinking Fund", {}),
    ("funds", "repair_fund", "1103", "Repairs & Maintenance Fund", {}),
    ("funds", "major_repair_fund", "1104", "Major Repair Fund", {}),
    ("funds", "education_fund", "1105", "Education & Training Fund", {}),
    ("funds", "building_fund", "1106", "Building Fund", {}),
    ("ie_account", "ie_surplus", "1201", "Income & Expenditure Account (Surplus / Deficit)", {}),
    ("loans", "loans", "1301", "Loans", {}),
    ("current_liabilities", "sundry_creditors", "1401", "Sundry Creditors (Vendors)", {}),
    ("current_liabilities", "outstanding_expenses", "1402", "Outstanding Expenses", {}),
    ("current_liabilities", "member_deposits", "1403", "Deposits from Members", {}),
    ("current_liabilities", "tds_payable", "1404", "TDS Payable", {}),
    ("current_liabilities", "gst_payable", "1405", "GST Payable", {}),
    # Assets
    ("fixed_assets", "land_building", "2001", "Land & Building", {}),
    ("fixed_assets", "plant_machinery", "2002", "Plant & Machinery (Lift, Pumps, DG)", {}),
    ("fixed_assets", "furniture", "2003", "Furniture & Fixtures", {}),
    ("fixed_assets", "office_equipment", "2004", "Office Equipment & Computers", {}),
    ("investments", "fixed_deposits", "2101", "Fixed Deposits with Banks", {}),
    ("investments", "bank_shares", "2102", "Shares of Co-operative Bank", {}),
    ("current_assets", "members_dues", "2201", "Members' Dues (Maintenance Receivable)", {}),
    ("current_assets", "deposits_paid", "2202", "Deposits (Electricity, Water etc.)", {}),
    ("current_assets", "prepaid_expenses", "2203", "Prepaid Expenses", {}),
    ("current_assets", "interest_accrued", "2204", "Interest Accrued on Deposits", {}),
    ("current_assets", "tds_receivable", "2205", "TDS Receivable", {}),
    ("current_assets", "advances", "2206", "Advances to Vendors & Staff", {}),
    ("cash_bank", "cash", "2301", "Cash in Hand", {"is_cash": True}),
    ("cash_bank", "bank", "2302", "Bank Account", {"is_bank": True, "is_default_bank": True}),
    ("cash_bank", "petty_cash", "2303", "Petty Cash", {"is_cash": True}),
    # Income
    ("income_members", "service_charges", "3001", "Service Charges", {}),
    ("income_members", "property_tax_recovered", "3002", "Property Tax Recovered", {}),
    ("income_members", "water_recovered", "3003", "Water Charges Recovered", {}),
    ("income_members", "electricity_recovered", "3004", "Electricity Charges Recovered", {}),
    ("income_members", "insurance_recovered", "3005", "Insurance Charges Recovered", {}),
    ("income_members", "lease_rent_recovered", "3006", "Lease Rent / NA Tax Recovered", {}),
    ("income_members", "parking_charges", "3007", "Parking Charges", {}),
    ("income_members", "non_occupancy", "3008", "Non-Occupancy Charges", {}),
    ("income_members", "interest_on_arrears", "3009", "Interest on Arrears", {}),
    ("income_members", "amenities_income", "3010", "Amenities / Clubhouse Charges", {}),
    ("income_members", "other_charges_recovered", "3011", "Other Charges Recovered", {}),
    ("income_members", "transfer_premium", "3012", "Transfer Premium", {}),
    ("other_income", "interest_fd", "3101", "Interest on Fixed Deposits", {}),
    ("other_income", "interest_sb", "3102", "Interest on Savings Bank Account", {}),
    ("other_income", "hall_booking", "3103", "Hall / Amenity Booking Income", {}),
    ("other_income", "misc_income", "3104", "Miscellaneous Income", {}),
    ("other_income", "round_off", "3105", "Rounding Off", {}),
    # Expenses
    ("admin_expenses", "salaries", "4001", "Salaries & Wages", {}),
    ("admin_expenses", "audit_fees", "4002", "Audit Fees", {}),
    ("admin_expenses", "legal_fees", "4003", "Legal & Professional Fees", {}),
    ("admin_expenses", "printing_stationery", "4004", "Printing & Stationery", {}),
    ("admin_expenses", "postage_telephone", "4005", "Postage, Telephone & Internet", {}),
    ("admin_expenses", "bank_charges", "4006", "Bank Charges", {}),
    ("admin_expenses", "office_expenses", "4007", "Office & General Expenses", {}),
    ("admin_expenses", "meeting_expenses", "4008", "Meeting Expenses (AGM / Committee)", {}),
    ("admin_expenses", "computer_expenses", "4009", "Computer & Software Expenses", {}),
    ("maintenance_expenses", "security_charges", "4101", "Security Charges", {}),
    ("maintenance_expenses", "housekeeping", "4102", "Housekeeping & Cleaning", {}),
    ("maintenance_expenses", "garden", "4103", "Garden Maintenance", {}),
    ("maintenance_expenses", "lift_maintenance", "4104", "Lift Maintenance (AMC)", {}),
    ("maintenance_expenses", "repairs_building", "4105", "Repairs & Maintenance — Building", {}),
    ("maintenance_expenses", "repairs_electrical", "4106", "Repairs & Maintenance — Electrical", {}),
    ("maintenance_expenses", "repairs_plumbing", "4107", "Repairs & Maintenance — Plumbing", {}),
    ("maintenance_expenses", "pest_control", "4108", "Pest Control", {}),
    ("maintenance_expenses", "cctv_maintenance", "4109", "CCTV & Security Systems Maintenance", {}),
    ("maintenance_expenses", "generator_maintenance", "4110", "Generator (DG Set) Maintenance", {}),
    ("maintenance_expenses", "repairs_general", "4111", "Repairs & Maintenance — General", {}),
    ("utility_expenses", "electricity", "4201", "Electricity Charges (Common Areas)", {}),
    ("utility_expenses", "water_charges", "4202", "Water Charges", {}),
    ("utility_expenses", "property_tax", "4203", "Property Tax", {}),
    ("utility_expenses", "insurance", "4204", "Insurance Premium", {}),
    ("utility_expenses", "lease_rent", "4205", "Lease Rent / NA Tax", {}),
    ("other_expenses", "interest_on_loans", "4301", "Interest on Loans", {}),
    ("other_expenses", "depreciation", "4302", "Depreciation", {}),
    ("other_expenses", "misc_expenses", "4303", "Miscellaneous Expenses", {}),
]

# Which ledger a maintenance bill line is credited to, by the standard
# maintenance element its charge head came from. Service-type heads are the
# society's service charges; recoveries of the society's own outgoings
# (tax, water, electricity, insurance, lease rent) have their own income
# heads; fund contributions go straight to the fund, never to income.
ELEMENT_LEDGER = {
    "service_charges": "service_charges",
    "lift_maintenance": "service_charges",
    "security": "service_charges",
    "housekeeping": "service_charges",
    "property_tax": "property_tax_recovered",
    "water_charges": "water_recovered",
    "common_electricity": "electricity_recovered",
    "insurance": "insurance_recovered",
    "lease_rent_na_tax": "lease_rent_recovered",
    "repair_fund": "repair_fund",
    "sinking_fund": "sinking_fund",
    "education_fund": "education_fund",
    "parking": "parking_charges",
    "amenities": "amenities_income",
}

CHARGE_TYPE_LEDGER = {
    ChargeType.MAINTENANCE: "service_charges",
    ChargeType.WATER: "water_recovered",
    ChargeType.PARKING: "parking_charges",
    ChargeType.SINKING_FUND: "sinking_fund",
    ChargeType.REPAIR_FUND: "repair_fund",
    ChargeType.AMENITIES: "amenities_income",
    ChargeType.PENALTY: "interest_on_arrears",
    ChargeType.SPECIAL_ASSESSMENT: "other_charges_recovered",
    ChargeType.OTHER: "other_charges_recovered",
}

# Expense head a vendor bill is booked to, by the vendor's category —
# used when the bill doesn't name one.
VENDOR_CATEGORY_LEDGER = {
    "electrical": "repairs_electrical",
    "plumbing": "repairs_plumbing",
    "lift": "lift_maintenance",
    "security": "security_charges",
    "housekeeping": "housekeeping",
    "gardening": "garden",
    "pest_control": "pest_control",
    "cctv": "cctv_maintenance",
    "water_supply": "water_charges",
    "generator": "generator_maintenance",
    "civil": "repairs_building",
    "it": "computer_expenses",
    "other": "repairs_general",
}


def bill_line_ledger_key(line, element_code: Optional[str] = None) -> str:
    """System key of the ledger a maintenance bill line is credited to."""
    desc = (line.description or "").lower()
    if line.charge_type == ChargeType.PENALTY:
        return "interest_on_arrears"
    if "non-occupancy" in desc or "non occupancy" in desc:
        return "non_occupancy"
    if element_code in ELEMENT_LEDGER:
        return ELEMENT_LEDGER[element_code]
    if "property tax" in desc or "municipal tax" in desc:
        return "property_tax_recovered"
    if "transfer" in desc and "premium" in desc:
        return "transfer_premium"
    return CHARGE_TYPE_LEDGER.get(line.charge_type, "other_charges_recovered")


def seed_chart_of_accounts(db: Session, society_id, bank_settings=None) -> Dict[str, Account]:
    """Create the standard groups and ledgers a society is missing (by
    system key), so it is safe to call again after new standard ledgers are
    added. `bank_settings`: the society's MaintenanceSettings, whose bank
    details name the default bank ledger. Caller commits."""
    groups = {g.system_key: g for g in db.query(AccountGroup).filter(
        AccountGroup.society_id == society_id).all() if g.system_key}
    taken_group_names = {g.name for g in db.query(AccountGroup.name).filter(
        AccountGroup.society_id == society_id)}
    for order, (key, name, nature) in enumerate(STANDARD_GROUPS):
        if key in groups:
            continue
        g = AccountGroup(society_id=society_id, name=name if name not in taken_group_names else f"{name} (Standard)",
                         nature=nature, system_key=key, sort_order=(order + 1) * 10, is_system=True)
        db.add(g)
        groups[key] = g
    db.flush()

    accounts = {a.system_key: a for a in db.query(Account).filter(
        Account.society_id == society_id).all() if a.system_key}
    taken_names = {a.name for a in db.query(Account.name).filter(Account.society_id == society_id)}
    for order, (group_key, key, code, name, flags) in enumerate(STANDARD_LEDGERS):
        if key in accounts:
            continue
        flags = dict(flags)
        if key == "bank" and bank_settings is not None and bank_settings.bank_name:
            name = f"{bank_settings.bank_name}"
            if bank_settings.bank_account_number:
                name += f" A/c {bank_settings.bank_account_number[-4:]}"
            flags.update(bank_name=bank_settings.bank_name,
                         bank_account_number=bank_settings.bank_account_number,
                         bank_ifsc=bank_settings.bank_ifsc)
        if name in taken_names:
            name = f"{name} (Standard)"
        a = Account(society_id=society_id, group_id=groups[group_key].id, code=code, name=name,
                    system_key=key, sort_order=(order + 1) * 10, is_system=True, **flags)
        db.add(a)
        accounts[key] = a
        taken_names.add(name)
    db.flush()
    return accounts
