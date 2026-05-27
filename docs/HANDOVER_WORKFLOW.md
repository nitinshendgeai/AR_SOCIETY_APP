# Shift Handover / Takeover Workflow

## FSM
```
DRAFT → SUBMITTED → ACCEPTED → VERIFIED → CLOSED
                  → DISPUTED → ACCEPTED
                             → SUBMITTED (re-submit after fixing)
```

## Handover Item Types
pending_task · incident · key · equipment · visitor · remark · maintenance

## API Flow
1. `POST /handovers/` — outgoing staff creates with summary + items
2. `POST /handovers/{id}/submit` — sends to incoming staff (requires incoming_staff_id)
3. `POST /handovers/{id}/accept` — incoming staff confirms takeover
4. `POST /handovers/{id}/verify` — supervisor verifies (optional)
5. `POST /handovers/{id}/dispute` — incoming staff raises concern → back to SUBMITTED

## Queries
- `GET /handovers/pending/{staff_id}` — pending handovers for a staff member
- `GET /handovers/society/{id}` — all handovers for society
- `GET /handovers/staff/{id}/history` — staff's handover history
