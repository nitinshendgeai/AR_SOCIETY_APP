"""The Accounts Agent dashboard sections and which finding categories each one shows. "accounting_audit" collects
every category not claimed by another section (Engine A's per-voucher findings)."""
SECTIONS = {
    "accounting_audit": ("Accounting Audit", None),
    "bye_law_compliance": ("Bye-law Compliance", ("charges", "legal_sources", "transfer")),
    "member_ledger": ("Member Ledger Audit", ("member_ledger", "maintenance_billing", "recovery")),
    "vendor_expense": ("Vendor and Expense Audit", ("vendor_audit", "expenditure")),
    "funds": ("Fund Monitoring", ("funds", "fund_monitoring", "borrowing")),
    "budget": ("Budget Analysis", ("budget",)),
    "governance": ("Governance and Resolutions", ("expenditure_approval",)),
    "statutory": ("Statutory Compliance", ("statutory_compliance",)),
}
CLAIMED = tuple(c for _, cats in SECTIONS.values() if cats for c in cats)


def section_of(category: str) -> str:
    for key, (_, cats) in SECTIONS.items():
        if cats and category in cats:
            return key
    return "accounting_audit"
