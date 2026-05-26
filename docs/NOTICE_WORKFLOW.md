# Notice & Communication — Workflow

## Notice FSM
```
DRAFT → PUBLISHED → EXPIRED/ARCHIVED
```

## Audience Targeting
all_residents · owners_only · tenants_only · specific_wings · specific_flats · all_staff · security_team · committee · all

## Acknowledgement Flow
Notice published → Resident reads → POST /acknowledge → ack_count++
GET /{notice_id}/acknowledgements → rate, pending count, list of acknowledgers

## Emergency Alerts
Trigger (active) → Resolve (resolved/cancelled)
Alert types: fire · water_leakage · lift_failure · power_failure · security_threat · medical · gas_leak
Channel flags: push_sent · sms_sent · whatsapp_sent (future integration)

## Communication Log
Every dispatch attempt → CommunicationLog with channel, status, sent_at
Channels: in_app · sms · email · push · whatsapp
