from __future__ import annotations

from autopulse_backend.auth.api_keys import (
    ProjectContext,
    authenticate_dashboard_project,
    authenticate_project,
    authenticate_project_token,
    build_api_key_record,
    generate_api_key,
    parse_api_key,
    verify_api_key_secret,
)
from autopulse_backend.auth.dashboard import (
    DashboardAuthSession,
    clear_session_cookie,
    create_magic_link_token,
    get_dashboard_auth_session,
    require_dashboard_auth_session,
    revoke_current_dashboard_session,
    verify_magic_link_and_create_session,
)

__all__ = [
    "DashboardAuthSession",
    "ProjectContext",
    "authenticate_dashboard_project",
    "authenticate_project",
    "authenticate_project_token",
    "build_api_key_record",
    "clear_session_cookie",
    "create_magic_link_token",
    "generate_api_key",
    "get_dashboard_auth_session",
    "parse_api_key",
    "require_dashboard_auth_session",
    "revoke_current_dashboard_session",
    "verify_api_key_secret",
    "verify_magic_link_and_create_session",
]
