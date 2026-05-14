from __future__ import annotations

from lumonox.core.tracing import (
    build_trace_context,
    format_traceparent,
    generate_span_id,
    generate_trace_id,
    parse_traceparent,
)

_HEX = set("0123456789abcdef")


def test_generated_ids_are_lowercase_hex_of_otlp_length() -> None:
    trace_id = generate_trace_id()
    span_id = generate_span_id()
    assert len(trace_id) == 32 and set(trace_id) <= _HEX
    assert len(span_id) == 16 and set(span_id) <= _HEX
    assert generate_trace_id() != generate_trace_id()


def test_parse_traceparent_accepts_valid_w3c_header() -> None:
    trace_id, parent_span_id = parse_traceparent(
        "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"
    )
    assert trace_id == "4bf92f3577b34da6a3ce929d0e0e4736"
    assert parent_span_id == "00f067aa0ba902b7"


def test_parse_traceparent_uppercase_is_normalized() -> None:
    trace_id, parent_span_id = parse_traceparent(
        "00-4BF92F3577B34DA6A3CE929D0E0E4736-00F067AA0BA902B7-01"
    )
    assert trace_id == "4bf92f3577b34da6a3ce929d0e0e4736"
    assert parent_span_id == "00f067aa0ba902b7"


def test_parse_traceparent_rejects_malformed_or_zero_ids() -> None:
    for header in (
        None,
        "",
        "garbage",
        "00-tooshort-00f067aa0ba902b7-01",  # bad trace id
        "00-4bf92f3577b34da6a3ce929d0e0e4736-zzzzzzzzzzzzzzzz-01",  # non-hex span
        "99-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01",  # unknown version
        "00-00000000000000000000000000000000-00f067aa0ba902b7-01",  # all-zero trace
        "00-4bf92f3577b34da6a3ce929d0e0e4736-0000000000000000-01",  # all-zero parent
    ):
        assert parse_traceparent(header) == (None, None), header


def test_build_trace_context_continues_inbound_trace() -> None:
    header = format_traceparent("4bf92f3577b34da6a3ce929d0e0e4736", "00f067aa0ba902b7")
    trace_id, span_id, parent_span_id = build_trace_context(header)
    assert trace_id == "4bf92f3577b34da6a3ce929d0e0e4736"
    assert parent_span_id == "00f067aa0ba902b7"
    # A fresh span id is always minted for this hop, distinct from the parent.
    assert len(span_id) == 16 and span_id != parent_span_id


def test_build_trace_context_starts_fresh_trace_without_header() -> None:
    trace_id, span_id, parent_span_id = build_trace_context(None)
    assert len(trace_id) == 32 and set(trace_id) <= _HEX
    assert len(span_id) == 16 and set(span_id) <= _HEX
    assert parent_span_id is None


def test_build_trace_context_starts_fresh_trace_on_malformed_header() -> None:
    trace_id, span_id, parent_span_id = build_trace_context("not-a-traceparent")
    assert len(trace_id) == 32
    assert parent_span_id is None
