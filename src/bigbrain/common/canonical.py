"""Canonical JSON encoding: sorted keys, no whitespace, UTF-8 -- the one shared
function anything that gets hashed or signed (audit entries, protocol envelopes)
must use, per BIGBRAIN_SPEC.md section 6.1.
"""

import json
from typing import Any


def canonical_json_bytes(data: dict[str, Any]) -> bytes:
    """Canonical JSON bytes for `data`: sorted keys, no extra whitespace, UTF-8.

    `data` must already be JSON-safe (plain dict/list/str/int/float/bool/None --
    e.g. the output of a pydantic model's `.model_dump(mode="json")`). This
    function does not coerce datetimes, enums, Paths, etc.
    """
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )
