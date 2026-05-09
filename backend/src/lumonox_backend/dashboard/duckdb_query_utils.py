from __future__ import annotations

import json
from typing import Any


def dashboard_list_payload_cell(value: object) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def first_non_empty_str(a: object, b: object) -> str | None:
    for x in (a, b):
        if x is None:
            continue
        s = str(x).strip()
        if s:
            return s
    return None


def truncate_diagnosis_text(value: object, max_chars: int) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    if len(text) <= max_chars:
        return text
    return f"{text[: max_chars - 1]}…"
