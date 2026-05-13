from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from lumonox_backend.auth import (
    DashboardAuthSession,
    ProjectContext,
    authenticate_dashboard_project,
    require_dashboard_auth_session,
)
from lumonox_backend.auth.rbac import require_member_or_above, require_owner_or_admin
from lumonox_backend.database import get_db_session
from lumonox_backend.models import DashboardUserBookmark, Project
from lumonox_backend.schemas import (
    DashboardBookmarkCreate,
    DashboardBookmarkItem,
    DashboardBookmarksListResponse,
    DashboardBookmarkUpdate,
)

router = APIRouter()


def _bookmark_visibility_api(
    row: DashboardUserBookmark,
) -> Literal["private", "project"]:
    if row.visibility == "project":
        return "project"
    return "private"


async def _bookmark_item(
    session: AsyncSession, row: DashboardUserBookmark
) -> DashboardBookmarkItem:
    project_name = await session.scalar(select(Project.name).where(Project.id == row.project_id))
    return DashboardBookmarkItem(
        id=row.id,
        title=row.title,
        pathname=row.pathname,
        query_string=row.query_string,
        hash_fragment=row.hash_fragment,
        notes=row.notes,
        visibility=_bookmark_visibility_api(row),
        created_by_user_id=row.user_id,
        created_at=row.created_at,
        updated_at=row.updated_at,
        project_id=row.project_id,
        project_name=str(project_name or ""),
    )


def _ensure_session_project_matches(context: ProjectContext, auth: DashboardAuthSession) -> None:
    if auth.project_id != context.project_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Session project does not match requested project",
        )


async def _bookmark_for_write(
    session: AsyncSession,
    *,
    bookmark_id: UUID,
    context: ProjectContext,
    auth: DashboardAuthSession,
) -> DashboardUserBookmark | None:
    row = await session.scalar(
        select(DashboardUserBookmark).where(
            DashboardUserBookmark.id == bookmark_id,
            DashboardUserBookmark.project_id == context.project_id,
        )
    )
    if row is None:
        return None
    if row.user_id == auth.user_id:
        return row
    if row.visibility == "project":
        require_owner_or_admin(auth)
        return row
    return None


@router.get("/bookmarks", response_model=DashboardBookmarksListResponse)
async def list_dashboard_bookmarks(
    context: Annotated[ProjectContext, Depends(authenticate_dashboard_project)],
    auth: Annotated[DashboardAuthSession, Depends(require_dashboard_auth_session)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> DashboardBookmarksListResponse:
    _ensure_session_project_matches(context, auth)
    result = await session.execute(
        select(DashboardUserBookmark, Project.name)
        .join(Project, DashboardUserBookmark.project_id == Project.id)
        .where(
            or_(
                DashboardUserBookmark.user_id == auth.user_id,
                and_(
                    DashboardUserBookmark.project_id == context.project_id,
                    DashboardUserBookmark.visibility == "project",
                ),
            )
        )
        .order_by(DashboardUserBookmark.updated_at.desc())
        .limit(500)
    )
    items: list[DashboardBookmarkItem] = []
    for row, project_name in result.all():
        items.append(
            DashboardBookmarkItem(
                id=row.id,
                title=row.title,
                pathname=row.pathname,
                query_string=row.query_string,
                hash_fragment=row.hash_fragment,
                notes=row.notes,
                visibility=_bookmark_visibility_api(row),
                created_by_user_id=row.user_id,
                created_at=row.created_at,
                updated_at=row.updated_at,
                project_id=row.project_id,
                project_name=str(project_name or ""),
            )
        )
    return DashboardBookmarksListResponse(items=items)


@router.post("/bookmarks", response_model=DashboardBookmarkItem)
async def create_dashboard_bookmark(
    payload: DashboardBookmarkCreate,
    context: Annotated[ProjectContext, Depends(authenticate_dashboard_project)],
    auth: Annotated[DashboardAuthSession, Depends(require_dashboard_auth_session)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> DashboardBookmarkItem:
    _ensure_session_project_matches(context, auth)
    require_member_or_above(auth)
    if payload.visibility == "project":
        require_owner_or_admin(auth)
    row = DashboardUserBookmark(
        user_id=auth.user_id,
        project_id=context.project_id,
        title=payload.title,
        pathname=payload.pathname,
        query_string=payload.query_string,
        hash_fragment=payload.hash_fragment,
        notes=payload.notes,
        visibility=payload.visibility,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return await _bookmark_item(session, row)


@router.put("/bookmarks/{bookmark_id}", response_model=DashboardBookmarkItem)
async def update_dashboard_bookmark(
    bookmark_id: UUID,
    payload: DashboardBookmarkUpdate,
    context: Annotated[ProjectContext, Depends(authenticate_dashboard_project)],
    auth: Annotated[DashboardAuthSession, Depends(require_dashboard_auth_session)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> DashboardBookmarkItem:
    _ensure_session_project_matches(context, auth)
    require_member_or_above(auth)
    row = await _bookmark_for_write(session, bookmark_id=bookmark_id, context=context, auth=auth)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bookmark not found")
    updates = payload.model_dump(exclude_unset=True)
    if "visibility" in updates:
        new_vis = updates["visibility"]
        if new_vis == "project":
            require_owner_or_admin(auth)
        if new_vis == "private" and row.visibility == "project" and row.user_id != auth.user_id:
            require_owner_or_admin(auth)
    for field_name, value in updates.items():
        setattr(row, field_name, value)
    await session.commit()
    await session.refresh(row)
    return await _bookmark_item(session, row)


@router.delete("/bookmarks/{bookmark_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_dashboard_bookmark(
    bookmark_id: UUID,
    context: Annotated[ProjectContext, Depends(authenticate_dashboard_project)],
    auth: Annotated[DashboardAuthSession, Depends(require_dashboard_auth_session)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> None:
    _ensure_session_project_matches(context, auth)
    require_member_or_above(auth)
    row = await _bookmark_for_write(session, bookmark_id=bookmark_id, context=context, auth=auth)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bookmark not found")
    await session.delete(row)
    await session.commit()
