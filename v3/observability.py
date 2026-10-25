from __future__ import annotations

import json
import logging
from typing import Any


LOGGER = logging.getLogger("imjingang.v3")


def audit(event: str, **fields: Any) -> None:
    allowed = {key: value for key, value in fields.items() if key in {
        "request_id", "session_id", "backend", "region", "model", "tool", "ok", "duration_ms", "record_count", "error_type"
    }}
    LOGGER.info(json.dumps({"event": event, **allowed}, ensure_ascii=False, default=str))
