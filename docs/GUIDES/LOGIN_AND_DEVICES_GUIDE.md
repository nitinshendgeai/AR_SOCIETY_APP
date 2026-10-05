# Login, Devices and Sessions — Guide

How signing in works, what happens when one login is used on several devices, and what ends a session.
Written against the code (`backend/app/services/auth_service.py`, `session_service.py`, `core/dependencies.py`).

---

## 1. How it works

- A sign-in gives the device two tokens: an **access token** (1 hour) and a **refresh token** (7 days). The app renews
  the access token with the refresh token on its own, so someone who uses the app regularly stays signed in.
- Each sign-in is a **session** — one row per device (`user_sessions`) with the device's name ("Chrome on Windows",
  "Safari on iPhone"), IP address, when it signed in and when it was last used. Both tokens carry the session's id.
- Every request checks that its session has not been ended. **Ending a session stops that device at once** — it does
  not have to wait for its token to expire. The device's next request is refused, it cannot renew, and the app returns
  to the sign-in screen with *"You were signed out. Please sign in again."*

## 2. One login on several devices

This is allowed: signing in on a second device does not sign out the first. What the app adds is **visibility and
control**:

- **Account menu → Signed-in devices** lists every device signed in with your login, which one is *This device*, and
  when each was last used. **Sign out** ends one device; **Sign out N other devices** ends all but this one. Use it
  for a lost phone, a computer left signed in, or a login you suspect is being shared.
- **Sign out** (Account menu) ends this device's session on the server as well as in the app. Before, it only
  deleted the tokens from the device, so a copied token would have kept working for up to 7 days.

## 3. What ends a session

| Event | Effect |
|---|---|
| Sign out | This device only. |
| Signed-in devices → Sign out | The chosen device. |
| Signed-in devices → Sign out other devices | All except the one you are using. |
| **You change your password** | Every other device (this one stays signed in). |
| **An admin resets your password** | Every device. |
| `reset_user_password` / `create_platform_admin --reset-password` (Console) | Every device. |
| Account suspended or deactivated | Refused at once on the next request. |
| 7 days without opening the app | The refresh token expires; sign in again. |

Logins created before this feature existed keep working until they expire, and are turned into visible sessions the
first time they renew.

## 4. Guessing passwords

After **10 wrong passwords for one account in 15 minutes** the account refuses further sign-ins — even with the
right password — for the rest of that window ("Too many failed sign-in attempts. Please wait 15 minutes…"). Other
accounts are not affected. The count comes from the audit log, so it holds across restarts. An address that does not
exist gets the same plain "Invalid email/mobile number or password" as a wrong password.

## 5. Shared logins

Because a login can be open on any number of devices, a login shared between people (one "guard" login for the
whole security team, say) cannot tell who did what — attendance, visitor entries and the audit trail all name the
login, not the person. Give each person their own login (Users & Roles → add user, or add them as staff). The
device list is a way to spot a shared login: more devices than people who should have it.

## 6. Not covered yet

- A **limit on devices per login** (for example: a new sign-in signs out the oldest). Easy to add if you want it for
  some roles; it needs a decision on which.
- Two-step verification (OTP) at sign-in.
- Sign-in alerts ("a new device signed in to your account").
