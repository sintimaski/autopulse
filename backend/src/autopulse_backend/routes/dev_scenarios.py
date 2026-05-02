from __future__ import annotations

import asyncio
import random
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from autopulse_backend.auth import ProjectContext, authenticate_project
from autopulse_backend.config import get_settings
from autopulse_backend.database import get_db_session
from autopulse_backend.ingestion.scenario_events import (
    generate_scenario_events,
    split_csv_values,
)
from autopulse_backend.schemas import IngestBatchRequest, IngestEvent
from autopulse_backend.services.ingest_service import persist_ingest_batch

router = APIRouter(prefix="/dev/scenarios", tags=["dev-scenarios"])


class ScenarioGenerateRequest(BaseModel):
    duration_seconds: int = Field(default=90, ge=5, le=3600)
    base_rate_per_second: float = Field(default=6.0, ge=0.1, le=500.0)
    spike_chance: float = Field(default=0.16, ge=0.0, le=1.0)
    spike_multiplier: float = Field(default=2.8, ge=1.0, le=25.0)
    error_burst_chance: float = Field(default=0.08, ge=0.0, le=1.0)
    service_names: str = Field(default="api,worker")
    environments: str = Field(default="dev,staging")
    sdk_version: str = Field(default="scenario-test-1.0")
    seed: int | None = None


class ScenarioGenerateResponse(BaseModel):
    accepted: int
    generated: int
    duration_seconds: int
    base_rate_per_second: float
    spike_windows: int
    error_burst_windows: int
    reached_event_cap: bool


@router.get("/ok")
async def scenario_ok() -> dict[str, object]:
    return {"status": "ok", "scenario": "dev"}


@router.get("/client-error")
async def scenario_client_error() -> None:
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Simulated client error from dev scenario route.",
    )


@router.get("/server-error")
async def scenario_server_error() -> None:
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Simulated server error from dev scenario route.",
    )


@router.get("/slow")
async def scenario_slow(
    delay_ms: Annotated[int, Query(ge=0, le=10000)] = 900,
) -> dict[str, object]:
    await asyncio.sleep(delay_ms / 1000)
    return {"status": "ok", "delay_ms": delay_ms}


@router.post("/traffic", response_model=ScenarioGenerateResponse)
async def generate_traffic_scenario(
    payload: ScenarioGenerateRequest,
    context: Annotated[ProjectContext, Depends(authenticate_project)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ScenarioGenerateResponse:
    settings = get_settings()
    duration_seconds = min(payload.duration_seconds, settings.dev_scenarios_max_duration_seconds)
    service_names = split_csv_values(payload.service_names) or ("scenario-api",)
    environments = split_csv_values(payload.environments) or ("dev",)
    rng = random.Random(payload.seed)  # nosec B311 - deterministic synthetic traffic generator
    now = datetime.now(tz=UTC)
    events_raw, stats = generate_scenario_events(
        now=now,
        duration_seconds=duration_seconds,
        base_rate_per_second=payload.base_rate_per_second,
        rng=rng,
        service_names=service_names,
        environments=environments,
        spike_chance=payload.spike_chance,
        spike_multiplier=payload.spike_multiplier,
        error_burst_chance=payload.error_burst_chance,
        max_events=settings.dev_scenarios_max_events,
    )
    batch = IngestBatchRequest(
        sdk_version=payload.sdk_version,
        events=[IngestEvent.model_validate(item) for item in events_raw],
    )
    accepted = await persist_ingest_batch(
        session=session,
        project_id=context.project_id,
        batch=batch,
        received_at=now,
    )
    return ScenarioGenerateResponse(
        accepted=accepted.accepted,
        generated=stats.generated_events,
        duration_seconds=duration_seconds,
        base_rate_per_second=payload.base_rate_per_second,
        spike_windows=stats.spike_windows,
        error_burst_windows=stats.error_burst_windows,
        reached_event_cap=stats.generated_events >= settings.dev_scenarios_max_events,
    )
