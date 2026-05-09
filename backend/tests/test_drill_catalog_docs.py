from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DRILLS_DOC = REPO_ROOT / "docs" / "runbooks" / "PHASE5_INCIDENT_DRILLS.md"


def test_phase5_drill_doc_keeps_required_t11_catalog_entries() -> None:
    content = DRILLS_DOC.read_text(encoding="utf-8")
    required_ids = (
        "replay-recovery",
        "scheduler-absence",
        "realtime-degradation",
        "migration-rollback",
        "stale-aggregate-recovery",
    )
    for drill_id in required_ids:
        assert drill_id in content, f"missing required drill id: {drill_id}"


def test_phase5_drill_doc_mentions_frequency_and_evidence_log() -> None:
    content = DRILLS_DOC.read_text(encoding="utf-8")
    assert "Frequency" in content
    assert "PHASE5_DRILL_EVIDENCE_LOG.md" in content
