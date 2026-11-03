"""TapOrder FastAPI application entrypoint, security middleware, and 29 canonical routes."""

from __future__ import annotations

import logging
import time
import uuid
from pathlib import Path
from typing import Any

import yaml
from fastapi import Depends, FastAPI, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy import select, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.session import get_db, translate_db_operational_error
from app.errors import AppError
from app.models import BillMembership
from app.schemas import (
    AvailabilityInput,
    BootstrapGuestInput,
    CloseShiftInput,
    ItemStatusInput,
    ItemVersionInput,
    JoinInput,
    LoginInput,
    OpenShiftInput,
    OrderInput,
    PaymentInput,
)
from app.security import (
    GUEST_COOKIE_NAME,
    GUEST_TTL_SECONDS,
    PREAUTH_COOKIE_NAME,
    PREAUTH_TTL_SECONDS,
    STAFF_COOKIE_NAME,
    STAFF_TTL_SECONDS,
     authenticate_guest,
    authenticate_staff,
    log_structured_request,
)
from app.services.auth import bootstrap_preauth, login_staff, logout_staff
from app.services.common import get_request_id, iso_utc
from app.services.events_and_p2 import (
    get_guest_recommendations_snapshot,
    get_shift_report_snapshot,
    parse_sse_cursor,
    sse_event_generator,
)
from app.services.kitchen_and_payments import (
    create_cash_payment,
    get_cashier_bill_snapshot,
    get_cashier_tables_snapshot,
    get_kitchen_queue_snapshot,
    update_kitchen_item_status,
)
from app.services.ordering_and_billing import (
    cancel_guest_item,
    get_guest_bill_snapshot,
    submit_order,
)
from app.services.shifts import close_shift, get_current_shift_snapshot, open_shift
from app.services.tables_and_menu import (
    bootstrap_guest,
    export_table_qr,
    get_guest_menu_snapshot,
    get_kitchen_menu_snapshot,
    join_table_visit,
    update_menu_availability,
)

MAX_BODY_BYTES = 64 * 1024
EXPECTED_ALEMBIC_HEAD = "0001_initial_schema"
CANONICAL_OPENAPI_PATH = Path(__file__).resolve().parents[2] / "contracts" / "openapi.yaml"

logger = logging.getLogger("taporder.api")
if not logger.handlers:
    handler = logging.StreamHandler()
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


def _set_session_cookie(
    response: Response,
    *,
    name: str,
    value: str,
    max_age: int,
) -> None:
    settings = get_settings()
    response.set_cookie(
        key=name,
        value=value,
        max_age=max_age,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )


def _clear_session_cookie(response: Response, *, name: str) -> None:
    settings = get_settings()
    response.delete_cookie(
        key=name,
        path="/",
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
    )


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(
        title="TapOrder API",
        version=settings.app_version,
    )

    canonical_spec: dict[str, Any] = yaml.safe_load(
        CANONICAL_OPENAPI_PATH.read_text(encoding="utf-8")
    )

    def custom_openapi() -> dict[str, Any]:
        return canonical_spec

    application.openapi = custom_openapi  # type: ignore[method-assign]

    @application.middleware("http")
    async def security_and_request_middleware(request: Request, call_next: Any) -> Response:
        req_id = request.headers.get("X-Request-ID") or f"req-{uuid.uuid4().hex[:12]}"
        request.state.request_id = req_id
        start_ts = time.perf_counter()

        # Check Content-Length header and actual body size <= 64KiB
        cl_header = request.headers.get("Content-Length")
        if cl_header and cl_header.isdigit() and int(cl_header) > MAX_BODY_BYTES:
            err_body = {
                "error": {
                    "code": "PAYLOAD_TOO_LARGE",
                    "message": "Kích thước dữ liệu gửi lên vượt quá giới hạn 64KiB.",
                    "details": {"max_bytes": MAX_BODY_BYTES},
                    "request_id": req_id,
                }
            }
            return JSONResponse(
                status_code=413,
                content=err_body,
                headers={
                    "Cache-Control": "no-store",
                    "Referrer-Policy": "no-referrer",
                    "X-Content-Type-Options": "nosniff",
                    "X-Request-ID": req_id,
                },
            )

        if request.method in {"POST", "PUT", "PATCH"}:
            body_bytes = await request.body()
            if len(body_bytes) > MAX_BODY_BYTES:
                err_body = {
                    "error": {
                        "code": "PAYLOAD_TOO_LARGE",
                        "message": "Kích thước dữ liệu gửi lên vượt quá giới hạn 64KiB.",
                        "details": {"max_bytes": MAX_BODY_BYTES},
                        "request_id": req_id,
                    }
                }
                return JSONResponse(
                    status_code=413,
                    content=err_body,
                    headers={
                        "Cache-Control": "no-store",
                        "Referrer-Policy": "no-referrer",
                        "X-Content-Type-Options": "nosniff",
                        "X-Request-ID": req_id,
                    },
                )

        response: Response = await call_next(request)
        duration_ms = (time.perf_counter() - start_ts) * 1000.0

        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Request-ID"] = req_id
        content_type = response.headers.get("content-type", "")
        if "text/event-stream" in content_type:
            response.headers["Cache-Control"] = "no-cache"
            response.headers["X-Accel-Buffering"] = "no"
        else:
            response.headers.setdefault("Cache-Control", "no-store")

        log_structured_request(
            logger,
            request_id=req_id,
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=duration_ms,
        )
        return response

    @application.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        req_id = get_request_id(request)
        headers = {
            "Cache-Control": "no-store",
            "Referrer-Policy": "no-referrer",
            "X-Content-Type-Options": "nosniff",
            "X-Request-ID": req_id,
            **exc.headers,
        }
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "details": exc.details,
                    "request_id": req_id,
                }
            },
            headers=headers,
        )

    @application.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        req_id = get_request_id(request)
        sanitized_errors: list[dict[str, Any]] = []
        for err in exc.errors():
            loc = [str(p) for p in err.get("loc", [])]
            # Check if a domain AppError was raised inside a Pydantic validator
            ctx = err.get("ctx") or {}
            inner = ctx.get("error")
            if isinstance(inner, AppError):
                return await handle_app_error(request, inner)
            sanitized_errors.append(
                {
                    "path": ".".join(loc),
                    "type": str(err.get("type", "validation_error")),
                    "msg": str(err.get("msg", "Invalid value")),
                }
            )
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Dữ liệu đầu vào không hợp lệ.",
                    "details": {"fields": sanitized_errors},
                    "request_id": req_id,
                }
            },
            headers={
                "Cache-Control": "no-store",
                "Referrer-Policy": "no-referrer",
                "X-Content-Type-Options": "nosniff",
                "X-Request-ID": req_id,
            },
        )

    @application.exception_handler(OperationalError)
    async def handle_operational_error(request: Request, exc: OperationalError) -> JSONResponse:
        app_err = translate_db_operational_error(exc)
        return await handle_app_error(request, app_err)

    @application.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, _exc: Exception) -> JSONResponse:
        req_id = get_request_id(request)
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "Đã xảy ra lỗi hệ thống ngoài dự kiến.",
                    "details": {},
                    "request_id": req_id,
                }
            },
            headers={
                "Cache-Control": "no-store",
                "Referrer-Policy": "no-referrer",
                "X-Content-Type-Options": "nosniff",
                "X-Request-ID": req_id,
            },
        )

    # --- Health Endpoints (2) ---
    @application.get("/api/health/live", tags=["health"], operation_id="health_live")
    def health_live() -> dict[str, Any]:
        return {"data": {"status": "ok"}}

    @application.get("/api/health/ready", tags=["health"], operation_id="health_ready")
    def health_ready(db: Session = Depends(get_db)) -> dict[str, Any]:
        try:
            rev = db.execute(text("SELECT version_num FROM alembic_version LIMIT 1")).scalar_one_or_none()
            guard = db.execute(text("SELECT id FROM shift_guard WHERE id = 1")).scalar_one_or_none()
            clock = db.execute(text("SELECT id FROM event_clock WHERE id = 1")).scalar_one_or_none()
        except Exception as exc:
            db.rollback()
            raise AppError(
                status_code=503,
                code="SERVICE_UNAVAILABLE",
                message="Cơ sở dữ liệu hoặc lược đồ chưa sẵn sàng.",
                details={},
            ) from exc

        if rev != EXPECTED_ALEMBIC_HEAD or guard != 1 or clock != 1:
            raise AppError(
                status_code=503,
                code="SERVICE_UNAVAILABLE",
                message="Phiên bản migration cơ sở dữ liệu chưa khớp.",
                details={"schema_revision": str(rev) if rev else None},
            )
        return {"data": {"status": "ready", "schema_revision": str(rev)}}

    # --- Auth Endpoints (4) ---
    @application.get("/api/v1/auth/bootstrap", tags=["auth"], operation_id="auth_bootstrap")
    def api_auth_bootstrap(
        request: Request,
        response: Response,
        db: Session = Depends(get_db),
    ) -> dict[str, Any]:
        raw_token, body = bootstrap_preauth(request, db)
        _set_session_cookie(
            response,
            name=PREAUTH_COOKIE_NAME,
            value=raw_token,
            max_age=PREAUTH_TTL_SECONDS,
        )
        return body

    @application.post("/api/v1/auth/login", tags=["auth"], operation_id="auth_login")
    def api_auth_login(
        payload: LoginInput,
        request: Request,
        response: Response,
        db: Session = Depends(get_db),
    ) -> dict[str, Any]:
        raw_staff_token, body = login_staff(request, db, payload)
        _clear_session_cookie(response, name=PREAUTH_COOKIE_NAME)
        _set_session_cookie(
            response,
            name=STAFF_COOKIE_NAME,
            value=raw_staff_token,
            max_age=STAFF_TTL_SECONDS,
        )
        return body

    @application.get("/api/v1/auth/session", tags=["auth"], operation_id="auth_session")
    def api_auth_session(
        request: Request,
        db: Session = Depends(get_db),
    ) -> dict[str, Any]:
        staff = authenticate_staff(request, db, required_role=None, require_csrf=False)
        return {
            "data": {
                "staff": {
                    "id": str(staff.user_id),
                    "username": staff.username,
                    "role": staff.role,
                },
                "csrf_token": staff.csrf_token,
                "expires_at": iso_utc(staff.expires_at),
            }
        }

    @application.post(
        "/api/v1/auth/logout",
        status_code=204,
        tags=["auth"],
        operation_id="auth_logout",
    )
    def api_auth_logout(
        request: Request,
        db: Session = Depends(get_db),
    ) -> Response:
        logout_staff(request, db)
        resp = Response(status_code=204)
        _clear_session_cookie(resp, name=STAFF_COOKIE_NAME)
        return resp

    # --- Guest Endpoints (6) ---
    @application.post("/api/v1/guest/bootstrap", tags=["guest"], operation_id="guest_bootstrap")
    def api_guest_bootstrap(
        payload: BootstrapGuestInput,
        request: Request,
        response: Response,
        db: Session = Depends(get_db),
    ) -> dict[str, Any]:
        new_raw_token, body = bootstrap_guest(request, db, payload)
        if new_raw_token is not None:
            _set_session_cookie(
                response,
                name=GUEST_COOKIE_NAME,
                value=new_raw_token,
                max_age=GUEST_TTL_SECONDS,
            )
        return body

    @application.post("/api/v1/guest/join", tags=["guest"], operation_id="guest_join")
    def api_guest_join(
        payload: JoinInput,
        request: Request,
        db: Session = Depends(get_db),
    ) -> dict[str, Any]:
        guest = authenticate_guest(request, db, require_csrf=True, rate_bucket="read")
        return join_table_visit(request, db, guest, payload)

    @application.get("/api/v1/guest/menu", tags=["guest"], operation_id="guest_menu")
    def api_guest_menu(
        request: Request,
        category_id: uuid.UUID | None = Query(default=None),
        db: Session = Depends(get_db),
    ) -> dict[str, Any]:
        authenticate_guest(request, db, require_csrf=False, rate_bucket="read")
        return get_guest_menu_snapshot(db, category_id=category_id)

    @application.post(
        "/api/v1/guest/orders",
        status_code=201,
        tags=["guest"],
        operation_id="guest_submit_order",
    )
    def api_guest_submit_order(
        payload: OrderInput,
        request: Request,
        response: Response,
        db: Session = Depends(get_db),
    ) -> dict[str, Any]:
        guest = authenticate_guest(request, db, require_csrf=True, rate_bucket="order")
        status_code, body, replayed = submit_order(request, db, guest, payload)
        response.status_code = status_code
        if replayed:
            response.headers["Idempotency-Replayed"] = "true"
        return body

    @application.get("/api/v1/guest/bills/{id}", tags=["guest"], operation_id="guest_get_bill")
    def api_guest_get_bill(
        id: uuid.UUID,
        request: Request,
        db: Session = Depends(get_db),
    ) -> dict[str, Any]:
        guest = authenticate_guest(request, db, require_csrf=False, rate_bucket="read")
        return get_guest_bill_snapshot(db, guest, id)

    @application.post(
        "/api/v1/guest/items/{id}/cancel",
        tags=["guest"],
        operation_id="guest_cancel_item",
    )
    def api_guest_cancel_item(
        id: uuid.UUID,
        payload: ItemVersionInput,
        request: Request,
        response: Response,
        db: Session = Depends(get_db),
    ) -> dict[str, Any]:
        guest = authenticate_guest(request, db, require_csrf=True, rate_bucket="read")
        status_code, body, replayed = cancel_guest_item(request, db, guest, id, payload)
        response.status_code = status_code
        if replayed:
            response.headers["Idempotency-Replayed"] = "true"
        return body

    # --- Kitchen Endpoints (4) ---
    @application.get("/api/v1/kitchen/queue", tags=["kitchen"], operation_id="kitchen_get_queue")
    def api_kitchen_get_queue(
        request: Request,
        cursor: str | None = Query(default=None),
        limit: int = Query(default=50, ge=1, le=100),
        status: str | None = Query(default=None),
        table_id: uuid.UUID | None = Query(default=None),
        db: Session = Depends(get_db),
    ) -> dict[str, Any]:
        authenticate_staff(
            request, db, required_role="barista", require_csrf=False, rate_bucket="read"
        )
        return get_kitchen_queue_snapshot(
            db,
            cursor=cursor,
            limit=limit,
            status_filter=status,
            table_id_filter=table_id,
        )

    @application.patch(
        "/api/v1/kitchen/items/{id}/status",
        tags=["kitchen"],
        operation_id="kitchen_update_item_status",
    )
    def api_kitchen_update_item_status(
        id: uuid.UUID,
        payload: ItemStatusInput,
        request: Request,
        response: Response,
        db: Session = Depends(get_db),
    ) -> dict[str, Any]:
        staff = authenticate_staff(
            request, db, required_role="barista", require_csrf=True, rate_bucket="mutation"
        )
        status_code, body, replayed = update_kitchen_item_status(request, db, staff, id, payload)
        response.status_code = status_code
        if replayed:
            response.headers["Idempotency-Replayed"] = "true"
        return body

    @application.get("/api/v1/kitchen/menu", tags=["kitchen"], operation_id="kitchen_get_menu")
    def api_kitchen_get_menu(
        request: Request,
        db: Session = Depends(get_db),
    ) -> dict[str, Any]:
        authenticate_staff(
            request, db, required_role="barista", require_csrf=False, rate_bucket="read"
        )
        return get_kitchen_menu_snapshot(db)

    @application.patch(
        "/api/v1/kitchen/menu/{id}/availability",
        tags=["kitchen"],
        operation_id="kitchen_update_availability",
    )
    def api_kitchen_update_availability(
        id: uuid.UUID,
        payload: AvailabilityInput,
        request: Request,
        response: Response,
        db: Session = Depends(get_db),
    ) -> dict[str, Any]:
        staff = authenticate_staff(
            request, db, required_role="barista", require_csrf=True, rate_bucket="mutation"
        )
        status_code, body, replayed = update_menu_availability(request, db, staff, id, payload)
        response.status_code = status_code
        if replayed:
            response.headers["Idempotency-Replayed"] = "true"
        return body

    # --- Cashier Endpoints (7) ---
    @application.get("/api/v1/cashier/tables", tags=["cashier"], operation_id="cashier_get_tables")
    def api_cashier_get_tables(
        request: Request,
        db: Session = Depends(get_db),
    ) -> dict[str, Any]:
        authenticate_staff(
            request, db, required_role="cashier", require_csrf=False, rate_bucket="read"
        )
        return get_cashier_tables_snapshot(db)

    @application.get(
        "/api/v1/cashier/bills/{id}", tags=["cashier"], operation_id="cashier_get_bill"
    )
    def api_cashier_get_bill(
        id: uuid.UUID,
        request: Request,
        db: Session = Depends(get_db),
    ) -> dict[str, Any]:
        authenticate_staff(
            request, db, required_role="cashier", require_csrf=False, rate_bucket="read"
        )
        return get_cashier_bill_snapshot(db, id)

    @application.post(
        "/api/v1/cashier/bills/{id}/payments",
        status_code=201,
        tags=["cashier"],
        operation_id="cashier_create_payment",
    )
    def api_cashier_create_payment(
        id: uuid.UUID,
        payload: PaymentInput,
        request: Request,
        response: Response,
        db: Session = Depends(get_db),
    ) -> dict[str, Any]:
        staff = authenticate_staff(
            request, db, required_role="cashier", require_csrf=True, rate_bucket="mutation"
        )
        status_code, body, replayed = create_cash_payment(request, db, staff, id, payload)
        response.status_code = status_code
        if replayed:
            response.headers["Idempotency-Replayed"] = "true"
        return body

    @application.get(
        "/api/v1/cashier/shifts/current",
        tags=["cashier"],
        operation_id="cashier_get_current_shift",
    )
    def api_cashier_get_current_shift(
        request: Request,
        db: Session = Depends(get_db),
    ) -> dict[str, Any]:
        authenticate_staff(
            request, db, required_role="cashier", require_csrf=False, rate_bucket="read"
        )
        return get_current_shift_snapshot(db)

    @application.post(
        "/api/v1/cashier/shifts",
        status_code=201,
        tags=["cashier"],
        operation_id="cashier_open_shift",
    )
    def api_cashier_open_shift(
        _payload: OpenShiftInput,
        request: Request,
        response: Response,
        db: Session = Depends(get_db),
    ) -> dict[str, Any]:
        staff = authenticate_staff(
            request, db, required_role="cashier", require_csrf=True, rate_bucket="mutation"
        )
        status_code, body, replayed = open_shift(request, db, staff)
        response.status_code = status_code
        if replayed:
            response.headers["Idempotency-Replayed"] = "true"
        return body

    @application.post(
        "/api/v1/cashier/shifts/{id}/close",
        tags=["cashier"],
        operation_id="cashier_close_shift",
    )
    def api_cashier_close_shift(
        id: uuid.UUID,
        payload: CloseShiftInput,
        request: Request,
        response: Response,
        db: Session = Depends(get_db),
    ) -> dict[str, Any]:
        staff = authenticate_staff(
            request, db, required_role="cashier", require_csrf=True, rate_bucket="mutation"
        )
        status_code, body, replayed = close_shift(request, db, staff, id, payload)
        response.status_code = status_code
        if replayed:
            response.headers["Idempotency-Replayed"] = "true"
        return body

    @application.get(
        "/api/v1/cashier/tables/{id}/qr",
        tags=["cashier"],
        operation_id="cashier_export_table_qr",
    )
    def api_cashier_export_table_qr(
        id: uuid.UUID,
        request: Request,
        db: Session = Depends(get_db),
    ) -> dict[str, Any]:
        staff = authenticate_staff(
            request, db, required_role="cashier", require_csrf=False, rate_bucket="read"
        )
        return export_table_qr(request, db, staff, id)

    # --- SSE Endpoints (4) ---
    @application.get(
        "/api/v1/guest/bills/{id}/events",
        tags=["events"],
        operation_id="guest_bill_events",
    )
    async def api_guest_bill_events(
        id: uuid.UUID,
        request: Request,
        after: str | None = Query(default=None),
        db: Session = Depends(get_db),
    ) -> StreamingResponse:
        guest = authenticate_guest(request, db, require_csrf=False, rate_bucket="read")
        mem = db.execute(
            select(BillMembership).where(
                BillMembership.bill_id == id,
                BillMembership.guest_session_id == guest.session_id,
            )
        ).scalar_one_or_none()
        # Release request DB session before starting SSE stream
        db.close()
        if mem is None:
            raise AppError(
                status_code=404,
                code="NOT_FOUND",
                message="Không tìm thấy hóa đơn thuộc phiên khách hiện tại.",
                details={},
            )
        cursor = parse_sse_cursor(after, request.headers.get("Last-Event-ID"))
        max_ticks_hdr = request.headers.get("X-Test-SSE-Max-Ticks")
        max_ticks = int(max_ticks_hdr) if (max_ticks_hdr and max_ticks_hdr.isdigit()) else None
        return StreamingResponse(
            sse_event_generator(
                request,
                principal_key=f"guest:{guest.session_id}",
                principal_kind="guest",
                raw_cookie_token=guest.raw_token,
                audience="guest",
                initial_cursor=cursor,
                bill_id=id,
                max_ticks=max_ticks,
            ),
            media_type="text/event-stream",
        )

    @application.get(
        "/api/v1/guest/menu/events",
        tags=["events"],
        operation_id="guest_menu_events",
    )
    async def api_guest_menu_events(
        request: Request,
        after: str | None = Query(default=None),
        db: Session = Depends(get_db),
    ) -> StreamingResponse:
        guest = authenticate_guest(request, db, require_csrf=False, rate_bucket="read")
        db.close()
        cursor = parse_sse_cursor(after, request.headers.get("Last-Event-ID"))
        max_ticks_hdr = request.headers.get("X-Test-SSE-Max-Ticks")
        max_ticks = int(max_ticks_hdr) if (max_ticks_hdr and max_ticks_hdr.isdigit()) else None
        return StreamingResponse(
            sse_event_generator(
                request,
                principal_key=f"guest:{guest.session_id}",
                principal_kind="guest",
                raw_cookie_token=guest.raw_token,
                audience="menu",
                initial_cursor=cursor,
                max_ticks=max_ticks,
            ),
            media_type="text/event-stream",
        )

    @application.get(
        "/api/v1/kitchen/events",
        tags=["events"],
        operation_id="kitchen_events",
    )
    async def api_kitchen_events(
        request: Request,
        after: str | None = Query(default=None),
        db: Session = Depends(get_db),
    ) -> StreamingResponse:
        staff = authenticate_staff(
            request, db, required_role="barista", require_csrf=False, rate_bucket="read"
        )
        db.close()
        cursor = parse_sse_cursor(after, request.headers.get("Last-Event-ID"))
        max_ticks_hdr = request.headers.get("X-Test-SSE-Max-Ticks")
        max_ticks = int(max_ticks_hdr) if (max_ticks_hdr and max_ticks_hdr.isdigit()) else None
        return StreamingResponse(
            sse_event_generator(
                request,
                principal_key=f"staff:{staff.session_id}",
                principal_kind="staff",
                raw_cookie_token=staff.raw_token,
                audience="kitchen",
                initial_cursor=cursor,
                required_role="barista",
                max_ticks=max_ticks,
            ),
            media_type="text/event-stream",
        )

    @application.get(
        "/api/v1/cashier/events",
        tags=["events"],
        operation_id="cashier_events",
    )
    async def api_cashier_events(
        request: Request,
        after: str | None = Query(default=None),
        db: Session = Depends(get_db),
    ) -> StreamingResponse:
        staff = authenticate_staff(
            request, db, required_role="cashier", require_csrf=False, rate_bucket="read"
        )
        db.close()
        cursor = parse_sse_cursor(after, request.headers.get("Last-Event-ID"))
        max_ticks_hdr = request.headers.get("X-Test-SSE-Max-Ticks")
        max_ticks = int(max_ticks_hdr) if (max_ticks_hdr and max_ticks_hdr.isdigit()) else None
        return StreamingResponse(
            sse_event_generator(
                request,
                principal_key=f"staff:{staff.session_id}",
                principal_kind="staff",
                raw_cookie_token=staff.raw_token,
                audience="cashier",
                initial_cursor=cursor,
                required_role="cashier",
                max_ticks=max_ticks,
            ),
            media_type="text/event-stream",
        )

    # --- P2 Endpoints (2) ---
    @application.get(
        "/api/v1/guest/recommendations",
        tags=["guest", "p2"],
        operation_id="guest_recommendations",
    )
    def api_guest_recommendations(
        request: Request,
        db: Session = Depends(get_db),
    ) -> dict[str, Any]:
        authenticate_guest(request, db, require_csrf=False, rate_bucket="read")
        return get_guest_recommendations_snapshot(db)

    @application.get(
        "/api/v1/cashier/shifts/{id}/report",
        tags=["cashier", "p2"],
        operation_id="cashier_shift_report",
    )
    def api_cashier_shift_report(
        id: uuid.UUID,
        request: Request,
        db: Session = Depends(get_db),
    ) -> dict[str, Any]:
        authenticate_staff(
            request, db, required_role="cashier", require_csrf=False, rate_bucket="read"
        )
        return get_shift_report_snapshot(db, id)

    return application


app = create_app()

