"""JSON responses that mark server-stamped times as UTC.

Times the server records itself (created_at, checked_in_at, paid_at,
check_in_time ...) are stored as naive UTC. Sent without a zone, an app shows
the UTC digits as if they were local — about 5½ hours behind in India. This
response class adds the explicit `Z` to those values so each client converts to
its own clock.

Only keys ending in `_at` or `_time` are touched, and only when the value is a
date-time without a zone. Dates the user typed in (`due_date`, `expiry_date`,
`expected_arrival`) and plain times of day ("09:00:00") are left exactly as
they were.
"""
import re
from typing import Any

from fastapi.responses import JSONResponse

_NAIVE_STAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?$")


def _mark(value: Any) -> Any:
    if isinstance(value, dict):
        out = {}
        for key, item in value.items():
            if (isinstance(item, str) and isinstance(key, str)
                    and (key.endswith("_at") or key.endswith("_time"))
                    and _NAIVE_STAMP.match(item)):
                out[key] = item + "Z"
            else:
                out[key] = _mark(item)
        return out
    if isinstance(value, list):
        return [_mark(item) for item in value]
    return value


class UtcJSONResponse(JSONResponse):
    def render(self, content: Any) -> bytes:
        return super().render(_mark(content))
