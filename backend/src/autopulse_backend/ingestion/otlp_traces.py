from __future__ import annotations

import base64
import binascii
from datetime import UTC, datetime
from typing import Literal

from autopulse_backend.schemas import IngestBatchRequest, IngestEvent


def _decode_trace_bytes(raw: str, *, expected_len: int) -> bytes | None:
    value = raw.strip()
    if not value:
        return None
    try:
        decoded_hex = binascii.unhexlify(value)
        if len(decoded_hex) == expected_len:
            return decoded_hex
    except (binascii.Error, ValueError):
        pass
    try:
        decoded_b64 = base64.b64decode(value, validate=True)
        if len(decoded_b64) == expected_len:
            return decoded_b64
    except (binascii.Error, ValueError):
        return None
    return None


def _normalize_trace_id(raw: object) -> str | None:
    if not isinstance(raw, str):
        return None
    decoded = _decode_trace_bytes(raw, expected_len=16)
    return decoded.hex() if decoded else None


def _normalize_span_id(raw: object) -> str | None:
    if not isinstance(raw, str):
        return None
    decoded = _decode_trace_bytes(raw, expected_len=8)
    return decoded.hex() if decoded else None


def _any_value_to_python(raw: object) -> object:
    if not isinstance(raw, dict):
        return raw
    for key in (
        "stringValue",
        "boolValue",
        "intValue",
        "doubleValue",
        "bytesValue",
    ):
        if key in raw:
            return raw[key]
    if "arrayValue" in raw and isinstance(raw["arrayValue"], dict):
        values = raw["arrayValue"].get("values")
        if isinstance(values, list):
            return [_any_value_to_python(item) for item in values]
    if "kvlistValue" in raw and isinstance(raw["kvlistValue"], dict):
        values = raw["kvlistValue"].get("values")
        if isinstance(values, list):
            out: dict[str, object] = {}
            for item in values:
                if not isinstance(item, dict):
                    continue
                raw_key = item.get("key")
                if not isinstance(raw_key, str) or not raw_key:
                    continue
                key = raw_key
                out[key] = _any_value_to_python(item.get("value"))
            return out
    return raw


def _attributes_to_dict(raw: object) -> dict[str, object]:
    if not isinstance(raw, list):
        return {}
    out: dict[str, object] = {}
    for item in raw:
        if not isinstance(item, dict):
            continue
        key = item.get("key")
        if not isinstance(key, str) or not key:
            continue
        out[key] = _any_value_to_python(item.get("value"))
    return out


def _coerce_int(raw: object) -> int | None:
    if isinstance(raw, bool):
        return int(raw)
    if isinstance(raw, int):
        return raw
    if isinstance(raw, float):
        return int(raw)
    if isinstance(raw, str):
        try:
            return int(raw.strip())
        except ValueError:
            return None
    return None


def _safe_method(raw: object) -> str:
    if isinstance(raw, str) and raw.strip():
        return raw.strip().upper()[:24]
    return "SPAN"


def _safe_path(raw_path: object, span_name: object) -> str:
    if isinstance(raw_path, str) and raw_path.strip():
        path = raw_path.strip()
    elif isinstance(span_name, str) and span_name.strip():
        path = f"/{span_name.strip().lstrip('/')}"
    else:
        path = "/otlp/span"
    return path[:2048]


def _unix_nano_to_datetime(raw: object, *, fallback: datetime) -> datetime:
    value = _coerce_int(raw)
    if value is None or value <= 0:
        return fallback
    sec = value / 1_000_000_000
    return datetime.fromtimestamp(sec, tz=UTC)


def convert_otlp_json_to_ingest_batch(
    payload: dict[str, object],
    *,
    max_events: int,
    sdk_version: str = "otlp-http-json",
) -> IngestBatchRequest:
    resource_spans = payload.get("resourceSpans")
    if not isinstance(resource_spans, list):
        raise ValueError("OTLP payload must contain resourceSpans[]")

    now = datetime.now(tz=UTC)
    events: list[IngestEvent] = []
    for resource_span in resource_spans:
        if len(events) >= max_events:
            break
        if not isinstance(resource_span, dict):
            continue
        resource_attrs = _attributes_to_dict(
            resource_span.get("resource", {}).get("attributes")
            if isinstance(resource_span.get("resource"), dict)
            else None
        )
        service_name = str(resource_attrs.get("service.name") or "unknown-service")[:120]
        environment = str(
            resource_attrs.get("deployment.environment")
            or resource_attrs.get("environment")
            or "unknown"
        )[:120]

        scopes = resource_span.get("scopeSpans")
        if not isinstance(scopes, list):
            scopes = resource_span.get("instrumentationLibrarySpans")
        if not isinstance(scopes, list):
            continue
        for scope_span in scopes:
            if len(events) >= max_events:
                break
            if not isinstance(scope_span, dict):
                continue
            scope_name = ""
            scope = scope_span.get("scope") or scope_span.get("instrumentationLibrary")
            if isinstance(scope, dict):
                raw_scope_name = scope.get("name")
                if isinstance(raw_scope_name, str):
                    scope_name = raw_scope_name.strip()
            spans = scope_span.get("spans")
            if not isinstance(spans, list):
                continue
            for span in spans:
                if len(events) >= max_events:
                    break
                if not isinstance(span, dict):
                    continue
                span_attrs = _attributes_to_dict(span.get("attributes"))
                span_name = span.get("name")
                method = _safe_method(span_attrs.get("http.method"))
                path = _safe_path(
                    span_attrs.get("http.route")
                    or span_attrs.get("http.target")
                    or span_attrs.get("url.path"),
                    span_name,
                )
                start_at = _unix_nano_to_datetime(span.get("startTimeUnixNano"), fallback=now)
                end_at = _unix_nano_to_datetime(span.get("endTimeUnixNano"), fallback=start_at)
                latency_ms = max(0.0, (end_at - start_at).total_seconds() * 1000)
                status_code = _coerce_int(span_attrs.get("http.status_code")) or 0
                status = span.get("status")
                status_enum = 0
                status_message = ""
                if isinstance(status, dict):
                    status_enum = _coerce_int(status.get("code")) or 0
                    raw_message = status.get("message")
                    if isinstance(raw_message, str):
                        status_message = raw_message
                if status_code <= 0:
                    status_code = 500 if status_enum == 2 else 200
                etype: Literal["request", "error", "job"] = (
                    "error" if status_code >= 500 or status_enum == 2 else "request"
                )
                trace_id = _normalize_trace_id(span.get("traceId"))
                span_id = _normalize_span_id(span.get("spanId"))
                parent_span_id = _normalize_span_id(span.get("parentSpanId"))
                request_id_raw = span_attrs.get("http.request_id") or span_attrs.get("request_id")
                request_id = (
                    str(request_id_raw)[:128]
                    if isinstance(request_id_raw, str) and request_id_raw.strip()
                    else (trace_id[:128] if trace_id else None)
                )
                event = IngestEvent.model_validate(
                    {
                        "type": etype,
                        "timestamp": start_at,
                        "service_name": service_name,
                        "environment": environment,
                        "method": method,
                        "path": path,
                        "status_code": status_code,
                        "latency_ms": latency_ms,
                        "request_id": request_id,
                        "trace_id": trace_id,
                        "span_id": span_id,
                        "parent_span_id": parent_span_id,
                        "span_name": str(span_name)[:255] if isinstance(span_name, str) else None,
                        "span_kind": _coerce_int(span.get("kind")),
                        "span_scope": scope_name[:120] if scope_name else None,
                        "otlp_status_code": status_enum,
                        "otlp_status_message": status_message[:512] if status_message else None,
                    }
                )
                events.append(event)

    if not events:
        raise ValueError("No valid spans found in OTLP payload")
    return IngestBatchRequest(events=events, sdk_version=sdk_version)
