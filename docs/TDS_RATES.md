# TDS on vendor payments: rates the app starts with (FY 2026-27 / AY 2027-28)

The app works out TDS when a vendor bill is paid (see `backend/app/modules/vendor/services/vendor_tds.py`). The rates,
limits and who they apply to are rows in `accounting_tax_configurations`, one per section and kind of payee, so they can be
edited when the law changes. The values below are what a society starts with. **Have the society's chartered accountant
confirm them**; this is not tax advice.

From 1 April 2026 these payments are deducted under **section 393 of the Income-tax Act, 2025** instead of the 1961 Act's
194C, 194J, 194I, 194H. The rates and limits were carried over, so the app keeps its section keys (194C...) and the labels
name both.

| Nature of payment | App section | Individual / HUF | Firm, LLP, company, other | Limit |
|---|---|---|---|---|
| Contractors: civil, transport, manpower, housekeeping, security, AMC | `194C` | 1% | 2% | ₹30,000 in one payment, or ₹1,00,000 in the year |
| Professional fees: CA, lawyer, architect, doctor | `194J_PROF` | 10% | 10% | ₹50,000 in the year |
| Technical services, call centre | `194J_TECH` | 2% | 2% | ₹50,000 in the year |
| Rent of plant and machinery | `194I_PM` | 2% | 2% | ₹6,00,000 in the year (₹50,000 a month) |
| Rent of land, building, furniture | `194I_LB` | 10% | 10% | ₹6,00,000 in the year (₹50,000 a month) |
| Commission or brokerage | `194H` | 2% | 2% | ₹20,000 in the year |

How a payment is worked out:
- TDS is on the value **without GST** when GST is shown separately on the bill.
- Under the limit nothing is deducted, but the payment counts towards the year. When the yearly limit is crossed, the
  payments made earlier in the year that were not taxed are brought in.
- **No PAN** (section 206AA): the higher of the normal rate and 20%.
- A **lower-deduction certificate** (section 197) replaces the rate for its dates.
- The vendor's type (individual, firm, company...) must agree with the 4th letter of its PAN, or the vendor cannot be saved.

## Left out on purpose
- **Section 206AB (higher rate for vendors who have not filed their return):** omitted by the Finance Act 2025 from
  1 April 2025. A vendor's filing status does not change the rate, so the app does not ask for it. (Some published charts
  still list it.)
- **Insurance commission** (2% for non-companies, 10% for companies) and **purchase of goods** (0.1% above ₹50 lakh, only for
  buyers with turnover above ₹10 crore): a housing society does not normally pay these. The app's two payee classes
  (individual/HUF and everyone else) also cannot tell a firm from a company, which the insurance commission rate needs.
- **E-commerce participants** and **transfer of immovable property:** not vendor bills.
- **Payment codes** (the "Code 1023, 1027..." numbers in some charts): not stored. The same code was given to technical and
  professional fees, which have different rates, so the chart needs checking against the official section 393 table before
  codes go into a return.
