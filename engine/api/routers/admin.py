"""Rutas de administración. Mutaciones exigen sesión y CSRF; el login no."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Response
from fastapi.responses import JSONResponse, StreamingResponse

from api.deps import AuthUser, Db, clear_auth_cookies, require_csrf, require_user
from api.schemas import (
    ActionName,
    AgentStatus,
    ApprovalOut,
    DataRequestPatch,
    EditIn,
    EventOut,
    LeadDetail,
    LeadOut,
    LeadPage,
    LeadPatch,
    MessageOut,
    MetricsOut,
    OrderOut,
    ProjectOut,
    RejectIn,
    ReplyIn,
    SettingsIn,
    SettingsOut,
    SuppressionIn,
    ThreadOut,
    TransitionIn,
    UserOut,
)
from api.services import (
    add_suppression,
    agent_rows,
    approve_hitl,
    delete_suppression,
    edit_hitl,
    enqueue_action,
    lead_detail,
    list_approvals,
    list_data_requests,
    list_events,
    list_leads,
    list_messages,
    list_orders,
    list_projects,
    list_suppression,
    manual_queue,
    mark_manual_sent,
    meta_categories,
    meta_statuses,
    metrics,
    patch_data_request,
    patch_lead,
    patch_project,
    read_settings_view,
    reject_hitl,
    reply_thread,
    sse_body,
    threads,
    transition_from_admin,
    write_settings,
)
from core.config import get_settings
from worker.wiring import channel_status

router = APIRouter(
    tags=["admin"],
    dependencies=[Depends(require_user), Depends(require_csrf)],
)


@router.post("/api/auth/logout", status_code=204)
def logout() -> Response:
    response = Response(status_code=204)
    clear_auth_cookies(response)
    return response


@router.get("/api/auth/me", response_model=UserOut)
def me(user: AuthUser) -> UserOut:
    return UserOut(email=user.email)


@router.get("/api/leads", response_model=LeadPage)
def leads(
    session: Db,
    status: str | None = None,
    q: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict[str, Any]:
    return list_leads(session, status=status, q=q, page=page, page_size=page_size)


@router.get("/api/leads/{id}", response_model=LeadDetail)
def lead_get(id: str, session: Db) -> dict[str, Any]:
    return lead_detail(session, id)


@router.patch("/api/leads/{id}", response_model=LeadOut)
def lead_patch(id: str, payload: LeadPatch, session: Db) -> dict[str, Any]:
    return patch_lead(session, id, payload)


@router.post("/api/leads/{id}/transition", response_model=LeadOut)
def lead_transition(id: str, payload: TransitionIn, session: Db) -> dict[str, Any]:
    return transition_from_admin(session, id, payload.to, payload.reason)


@router.get("/api/approvals", response_model=list[ApprovalOut])
def approvals(session: Db, status: str = "pending") -> list[dict[str, Any]]:
    return list_approvals(session, status)


@router.post("/api/approvals/{id}/approve", response_model=LeadOut)
def approve(id: str, session: Db, user: AuthUser) -> dict[str, Any]:
    return approve_hitl(session, id, user.email)


@router.post("/api/approvals/{id}/reject")
def reject(id: str, session: Db, user: AuthUser, payload: RejectIn | None = None) -> dict[str, str]:
    note = payload.note if payload is not None else None
    return reject_hitl(session, id, user.email, note)


@router.post("/api/approvals/{id}/edit")
def edit(id: str, session: Db, user: AuthUser, payload: EditIn | None = None) -> dict[str, str]:
    body = payload or EditIn()
    return edit_hitl(
        session,
        id,
        user.email,
        body_text=body.body_text,
        subject=body.subject,
        message_id=body.message_id,
    )


@router.get("/api/messages", response_model=list[MessageOut])
def messages(session: Db, lead_id: str | None = None) -> list[dict[str, Any]]:
    return list_messages(session, lead_id)


@router.get("/api/manual-queue", response_model=list[MessageOut])
def queue(session: Db) -> list[dict[str, Any]]:
    return manual_queue(session)


@router.post("/api/manual-queue/{id}/mark-sent", response_model=MessageOut)
def mark_sent(id: str, session: Db) -> dict[str, Any]:
    return mark_manual_sent(session, id)


@router.get("/api/conversations", response_model=list[ThreadOut])
def conversations(session: Db) -> list[dict[str, str]]:
    return threads(session)


@router.post("/api/conversations/{id}/reply", status_code=202)
def reply(id: str, payload: ReplyIn, session: Db) -> dict[str, str]:
    return reply_thread(session, id, payload.body_text)


@router.get("/api/agents", response_model=list[AgentStatus])
def agents(session: Db) -> list[dict[str, Any]]:
    rows = agent_rows(session)
    channels = channel_status(get_settings())
    for row in rows:
        row["channels"] = channels
    return rows


@router.post("/api/actions/{name}", status_code=202)
def action(name: ActionName, session: Db, user: AuthUser) -> JSONResponse:
    return JSONResponse(status_code=202, content=enqueue_action(session, name, user.email))


@router.get("/api/events", response_model=list[EventOut])
def events(
    session: Db,
    level: str | None = None,
    agent: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    return list_events(session, level=level, agent=agent, limit=limit)


@router.get("/api/events/stream")
def stream(session: Db) -> StreamingResponse:
    # Un comentario (y el último evento, si hay) y se cierra. Los tests no pueden colgar.
    body = sse_body(session)
    return StreamingResponse(iter([body]), media_type="text/event-stream")


@router.get("/api/metrics", response_model=MetricsOut)
def metrics_route(session: Db) -> dict[str, Any]:
    return metrics(session)


@router.get("/api/orders", response_model=list[OrderOut])
def orders(session: Db) -> list[dict[str, Any]]:
    return list_orders(session)


@router.get("/api/projects", response_model=list[ProjectOut])
def projects(session: Db) -> list[dict[str, Any]]:
    return list_projects(session)


@router.patch("/api/projects/{id}")
def project_patch(id: str, payload: dict[str, Any], session: Db) -> dict[str, Any]:
    return patch_project(session, id, payload)


@router.get("/api/settings", response_model=SettingsOut)
def settings_get(session: Db) -> dict[str, Any]:
    return read_settings_view(session)


@router.put("/api/settings", response_model=SettingsOut)
def settings_put(payload: SettingsIn, session: Db, user: AuthUser) -> dict[str, Any]:
    return write_settings(session, user.email, payload)


@router.get("/api/compliance/suppression")
def suppression_list(session: Db) -> list[dict[str, Any]]:
    return list_suppression(session)


@router.post("/api/compliance/suppression", status_code=201)
def suppression_add(payload: SuppressionIn, session: Db) -> dict[str, str]:
    return add_suppression(session, payload.kind, payload.value, payload.reason)


@router.delete("/api/compliance/suppression", status_code=204)
def suppression_delete(session: Db, id: str) -> Response:
    delete_suppression(session, id)
    return Response(status_code=204)


@router.get("/api/compliance/data-requests")
def data_requests(session: Db) -> list[dict[str, Any]]:
    return list_data_requests(session)


@router.patch("/api/compliance/data-requests")
def data_request_patch(payload: DataRequestPatch, session: Db) -> dict[str, str]:
    return patch_data_request(session, payload.id, payload.status)


@router.get("/api/meta/categories")
def categories() -> list[dict[str, str]]:
    return meta_categories()


@router.get("/api/meta/statuses")
def statuses() -> dict[str, Any]:
    return meta_statuses()
