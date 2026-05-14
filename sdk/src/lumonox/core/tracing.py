"""W3C Trace Context helpers shared by the Lumonox framework adapters.

Lumonox does *lightweight* per-request tracing: every request the middleware
captures becomes one root span stamped onto the event payload the dashboard
already understands (``trace_id`` / ``span_id`` / ``parent_span_id`` /
``span_name``). When the inbound request carries a W3C ``traceparent`` header —
set by an upstream Lumonox-instrumented service, an API gateway, a service
mesh, or any OpenTelemetry-compatible client — the SDK *continues* that trace
instead of starting a fresh one, so a single logical request shows up as one
correlated trace across services.

This is deliberately not full distributed tracing (a stated non-goal): there is
no outbound context propagation, no span exporter, no sampling protocol — just
inbound continuation plus a per-request span. The id shapes match OTLP so the
OTLP ingest path and this path land in the same traces explorer.
"""

from __future__ import annotations

from secrets import token_hex

_TRACE_ID_LEN = 32
_SPAN_ID_LEN = 16
_ZERO_TRACE_ID = "0" * _TRACE_ID_LEN
_ZERO_SPAN_ID = "0" * _SPAN_ID_LEN
_HEX_DIGITS = frozenset("0123456789abcdef")


def generate_trace_id() -> str:
    """Return a fresh 32-char lowercase hex trace id (W3C / OTLP shape)."""
    return token_hex(16)


def generate_span_id() -> str:
    """Return a fresh 16-char lowercase hex span id (W3C / OTLP shape)."""
    return token_hex(8)


def _is_hex(value: str, length: int) -> bool:
    return len(value) == length and all(char in _HEX_DIGITS for char in value)


def parse_traceparent(header: str | None) -> tuple[str | None, str | None]:
    """Extract ``(trace_id, parent_span_id)`` from a W3C ``traceparent`` header.

    Returns ``(None, None)`` when the header is missing or malformed so the
    caller cleanly falls back to starting a new trace. Never raises — a bad
    header from a caller must never break the host request.
    """
    if not header or not isinstance(header, str):
        return None, None
    parts = header.strip().split("-")
    if len(parts) != 4:
        return None, None
    version, trace_id, parent_id, _flags = parts
    trace_id = trace_id.lower()
    parent_id = parent_id.lower()
    if version != "00":
        return None, None
    if not _is_hex(trace_id, _TRACE_ID_LEN) or trace_id == _ZERO_TRACE_ID:
        return None, None
    if not _is_hex(parent_id, _SPAN_ID_LEN) or parent_id == _ZERO_SPAN_ID:
        return None, None
    return trace_id, parent_id


def format_traceparent(trace_id: str, span_id: str) -> str:
    """Build a W3C ``traceparent`` header value (sampled flag set)."""
    return f"00-{trace_id}-{span_id}-01"


def build_trace_context(traceparent_header: str | None) -> tuple[str, str, str | None]:
    """Resolve ``(trace_id, span_id, parent_span_id)`` for one captured request.

    Continues an inbound W3C trace when ``traceparent_header`` is valid;
    otherwise starts a fresh trace. ``span_id`` is always newly generated for
    this request's span. ``parent_span_id`` is ``None`` for a root request.
    """
    inbound_trace_id, inbound_parent_span_id = parse_traceparent(traceparent_header)
    trace_id = inbound_trace_id or generate_trace_id()
    span_id = generate_span_id()
    return trace_id, span_id, inbound_parent_span_id
