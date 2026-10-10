# Certificates and NOCs

Screen: **Community → Certificates & NOC** (`/certificates`), open to every role.

## Flow
1. A resident (owner) or tenant picks what they need and sends the request. The office can also raise one for a flat
   (`flat_id` in the API). Society Admin and committee are notified.
2. Society Admin / committee approve or decline. Declining needs a reason. The member is notified either way.
3. On approval the certificate gets a number and the PDF can be downloaded by the member and the office.

## Rules
- Types: `noc_sale`, `noc_rent`, `noc_loan`, `noc_renovation`, `no_dues`, `address_proof`, `other`.
- Dues: `noc_sale`, `noc_rent`, `noc_loan` and `no_dues` need the flat to be clear. Otherwise approval answers 409
  with the amount; `override_dues: true` approves anyway and the dues are printed on the certificate.
- Numbering: `<NOC|ND|AP|CERT>/<financial year>/<4-digit serial>` per society, unique per society.
- A tenant can ask only for `address_proof` / `other`. One pending request per kind per flat.
- A login not linked to a flat cannot ask (422 with an explanation); the office can ask on a flat's behalf.
- Members see only their own requests; the office sees all in its society.

## API (`/api/v1/certificates`)
`GET /kinds` · `POST /society/{id}` · `GET /society/{id}?status=` · `GET /{id}` · `POST /{id}/decision`
(`approve`, `note`, `override_dues`; office only) · `POST /{id}/cancel` · `GET /{id}/pdf` (approved only).

## RBAC
Form `certificates` (rbac_seed + migration `c2a9102b3c4d`).
