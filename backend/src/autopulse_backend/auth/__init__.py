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
    bootstrap_dashboard_tenant_for_user,
    clear_session_cookie,
    create_magic_link_token,
    get_dashboard_auth_session,
    issue_dashboard_session_for_user,
    require_dashboard_auth_session,
    revoke_current_dashboard_session,
    verify_magic_link_and_create_session,
)
from autopulse_backend.auth.rbac import (
    ensure_dashboard_admin_or_owner,
    ensure_dashboard_not_viewer,
    normalize_membership_role,
    require_dashboard_org_member,
    require_owner,
    require_owner_or_admin,
)

__all__ = [
    "DashboardAuthSession",
    "ProjectContext",
    "ensure_dashboard_admin_or_owner",
    "ensure_dashboard_not_viewer",
    "issue_dashboard_session_for_user",
    "normalize_membership_role",
    "require_dashboard_org_member",
    "require_owner",
    "require_owner_or_admin",
    "authenticate_dashboard_project",
    "authenticate_project",
    "authenticate_project_token",
    "build_api_key_record",
    "bootstrap_dashboard_tenant_for_user",
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
