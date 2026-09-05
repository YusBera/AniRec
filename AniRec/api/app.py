"""AniRec's HTTP boundary.

A second client for the service layer the desktop already uses. Nothing here
re-implements a rule: every route resolves a service out of ``ApiContainer``
and calls the same method ``gui/workers/operations.py`` calls, with the same
``CancellationToken`` and the same ``progress_callback``. The Qt worker bodies
are three to eight lines each for exactly this reason - they bind a thread to
a service and decide nothing - so the handlers below are their equals rather
than their copies. When the desktop frontend is eventually retired, those
workers delete and these remain as the only binding.

Error responses use ``presentable_error``, which is the redacted,
traceback-free model the desktop error dialog already receives. A secret
cannot reach a browser through this boundary that could not already reach a
dialog, and the same redaction is what guarantees it.

Every response is a Pydantic model from ``models.py`` rather than a bare
``dict``, which is what lets FastAPI's generated ``/openapi.json`` describe
the contract completely enough for ``openapi-typescript`` to generate
``frontend/src/api/generated/schema.d.ts`` from it - see that file's header
for the generation command.

The feed falls back to the bundled sample library when no profile is
configured, which is what the desktop's "look around with sample data" mode
does. That keeps this runnable without MyAnimeList credentials while still
exercising the real models, the real projection and the real HTTP boundary -
the response is marked ``source: "sample"`` so a client can say so rather than
presenting demonstration figures as real.
"""

from __future__ import annotations

import json
import os
from typing import Any, Callable, Iterator

from fastapi import Body, FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from ..application.pipeline import CancellationToken
from ..models import PipelineProgress
from ..presentation import recommendation_view_models
from ..services import ApiConnectionService
from .container import ApiContainer, build_container
from .models import (
    Catalogue,
    ErrorEnvelope,
    FeedbackRequest,
    FeedbackResponse,
    FeedResponse,
    HealthResponse,
    LocalState,
    OperationAcceptedResponse,
    OperationListResponse,
    OperationSnapshotResponse,
    OperationStartRequest,
    ProfileSummary,
    SystemStateResponse,
)
from .operations import (
    OperationAlreadyRunningError,
    OperationRegistry,
    error_payload,
)
from .security import TOKEN_ENV_VAR, TokenAuthMiddleware, token_from_environment
from .serialization import (
    any_to_dict,
    catalogue_to_dict,
    local_state_to_dict,
    view_model_to_dict,
)

# The exact key format gui/workers/operations.py mints, restated rather than
# imported: that module is a Qt module, and importing it here would put
# PySide6 in the API's dependency graph for the sake of one f-string.
SUPPORTED_KINDS = frozenset(
    {
        "sync",
        "recommendation",
        "more-recommendations",
        "list-sync",
        "profile-lookup",
        "api-test",
    }
)


# What a feed with nowhere to persist reports instead of a stored state.
EMPTY_LOCAL_STATE = LocalState(
    hidden_mal_ids=(),
    watch_later_mal_ids=(),
    liked_mal_ids=(),
    disliked_mal_ids=(),
    show_hidden=False,
)

EMPTY_CATALOGUE = Catalogue(genres=(), studios=(), years=(), statuses=())


def operation_key(kind: str, profile_id: str) -> str:
    resolved = str(kind).strip()
    normalized = str(profile_id).strip()
    if not normalized:
        raise ValueError("profile_id is required.")
    if ":" in normalized:
        raise ValueError("profile_id cannot contain ':'.")
    return f"{resolved}:{normalized}"


def _default_origins() -> tuple[str, ...]:
    """Dev origins, plus whatever the launcher names.

    A packaged desktop shell's webview is not served from
    ``http://localhost:5173`` - Tauri v2 serves its own content from an
    origin this process cannot predict (it has changed across Tauri
    versions and differs slightly by platform). Rather than guess it here,
    the launcher that actually knows - the Rust side, which reads it from
    ``tauri.conf.json`` at build time - passes it through
    ``ANIREC_ALLOWED_ORIGIN`` (comma-separated for more than one).
    """
    base = ("http://localhost:5173", "http://127.0.0.1:5173")
    extra = os.environ.get("ANIREC_ALLOWED_ORIGIN", "")
    named = tuple(origin.strip() for origin in extra.split(",") if origin.strip())
    return base + named


def create_app(
    *,
    root_override: str | None = None,
    container: ApiContainer | None = None,
    registry: OperationRegistry | None = None,
    allow_origins: tuple[str, ...] | None = None,
    token: str | None = None,
    on_shutdown_requested: Callable[[], None] | None = None,
) -> FastAPI:
    """Build the app.

    ``token`` is normally left unset here and read from ``ANIREC_API_TOKEN``
    instead (see ``security.py``); it is a constructor parameter as well
    purely so tests can supply one without touching process environment.
    When a token is required, the interactive docs are disabled entirely -
    see the module docstring on ``TokenAuthMiddleware`` for why leaving them
    reachable would still be low risk, and why removing them anyway costs
    nothing a packaged build needs.
    """
    services = container or build_container(root_override)
    operations = registry or OperationRegistry()
    resolved_token = token if token is not None else token_from_environment()
    origins = allow_origins if allow_origins is not None else _default_origins()

    app = FastAPI(
        title="AniRec",
        version="0.1.0",
        summary="HTTP boundary over the existing AniRec service layer.",
        docs_url=None if resolved_token else "/docs",
        redoc_url=None if resolved_token else "/redoc",
        openapi_url=None if resolved_token else "/openapi.json",
    )
    app.state.container = services
    app.state.operations = operations
    app.state.token_required = bool(resolved_token)

    if resolved_token:
        app.add_middleware(TokenAuthMiddleware, token=resolved_token)

    # Listed explicitly rather than "*": a stray page on another origin must
    # not be able to read a response from a local API that can hold a
    # MyAnimeList token. The token above stops it from acting; this stops it
    # from reading what a same-origin-unaware request might still trigger.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(origins),
        allow_credentials=False,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "X-AniRec-Token"],
    )

    @app.exception_handler(StarletteHTTPException)
    async def http_error(_request: Request, error: StarletteHTTPException) -> JSONResponse:
        # FastAPI's default shape for a raised HTTPException is
        # {"detail": "..."}. Every other error on this boundary is
        # {"error": {...presentable_error...}}; a client should not need a
        # second error shape for the routes that reject input before reaching
        # a service. Retryable is conservative (False) here because a 4xx
        # from bad input will not succeed on an unchanged retry - a caller
        # that wants "try again after fixing this" reads that from the
        # description rather than the flag.
        code = "unauthorized" if error.status_code == 401 else "invalid_request"
        detail = error.detail if isinstance(error.detail, str) else "Request rejected."
        return JSONResponse(
            status_code=error.status_code,
            content={
                "error": {
                    "code": code,
                    "title": detail,
                    "description": detail,
                    "solution": "",
                    "retryable": False,
                }
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(
        _request: Request, error: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "invalid_request",
                    "title": "AniRec could not read that request",
                    "description": "The request body did not match what this endpoint expects.",
                    "solution": "",
                    "retryable": False,
                }
            },
        )

    @app.exception_handler(Exception)
    async def unhandled(_request: Request, error: Exception) -> JSONResponse:
        return JSONResponse(status_code=500, content={"error": error_payload(error)})

    # -- system -----------------------------------------------------------

    @app.get(
        "/api/health",
        response_model=HealthResponse,
        # Registers ErrorEnvelope/ApiError into the OpenAPI document's
        # components even though every route can produce them via an
        # exception handler rather than a normal return - one mention is
        # enough for openapi-typescript to emit the type once, reusably.
        responses={401: {"model": ErrorEnvelope}, 500: {"model": ErrorEnvelope}},
    )
    def health() -> HealthResponse:
        return HealthResponse(status="ok", version=app.version)

    @app.get("/api/system/state", response_model=SystemStateResponse)
    def system_state() -> SystemStateResponse:
        profile = services.profiles.active_profile()
        settings = services.settings.load()
        return SystemStateResponse(
            profile=(
                None
                if profile is None
                else ProfileSummary(profile_id=profile.profile_id, username=profile.username)
            ),
            needs_setup=services.onboarding.needs_setup(),
            mal_client_id_present=bool(settings.client_id),
            active_operations=tuple(
                OperationSnapshotResponse(**r.snapshot()) for r in operations.active()
            ),
        )

    @app.post("/api/system/shutdown", status_code=202)
    def request_shutdown() -> dict[str, bool]:
        """Ask the process to stop serving. The launcher owns the actual exit.

        This flips ``uvicorn.Server.should_exit`` when ``__main__.py`` wired
        it up as ``on_shutdown_requested`` - the documented way to stop a
        server built with ``uvicorn.Server`` from inside a request handler,
        which lets in-flight responses (including this one) finish and the
        ASGI lifespan close cleanly. Outside a real server (tests, or a
        caller that never provided the hook) this is a no-op that still
        answers normally, which is deliberate: a test exercising "does this
        route exist and require the token" should not need a live server.

        The shell holds the child process handle regardless and force-kills
        it if this does not result in exit within its own timeout - this
        route is the graceful path, not the only path.
        """
        if on_shutdown_requested is not None:
            on_shutdown_requested()
        return {"accepted": True}

    # -- discover ---------------------------------------------------------

    @app.get("/api/discover/feed", response_model=FeedResponse)
    def discover_feed(include_hidden: bool = Query(False)) -> FeedResponse:
        """The feed, its local votes, and the terms it can be filtered by.

        One request rather than three. The three answers are derived from the
        same loaded result, and splitting them would let a client render cards
        against one generation while filtering them against another.
        """
        profile = services.profiles.active_profile()
        source = "profile"
        result = None
        if profile is not None:
            result = services.results.load(profile.profile_id)
        if result is None or not result.recommendations:
            result = services.samples.load()
            source = "sample"
        if result is None:
            return FeedResponse(
                source="empty",
                ephemeral=True,
                profile=None,
                state_profile_id=None,
                recommendations=(),
                hidden_count=0,
                catalogue=EMPTY_CATALOGUE,
                state=EMPTY_LOCAL_STATE,
                user_stats={},
            )

        models = recommendation_view_models(result.recommendations)
        # Ephemeral whenever what is being shown is not the active profile's
        # own persisted result - which today means the bundled sample
        # library. That library's SampleDataService.profile_id is
        # intentionally rejected by paths.profile_dir (see
        # is_sample_profile and tests/test_ephemeral_profile_semantics.py for
        # why this is a formalized boundary, not an accident to work around).
        # The desktop resolves the identical case the identical way -
        # MainWindow._enter_demo_mode calls set_ephemeral(True), so the review
        # loop works in memory and nothing is written.
        ephemeral = source != "profile"
        state = (
            None if ephemeral else services.recommendation_state.load(profile.profile_id)
        )
        visible = models
        if state is not None and not include_hidden and not state.show_hidden:
            visible = tuple(
                model
                for model in models
                if model.mal_id is None or model.mal_id not in state.hidden_mal_ids
            )
        return FeedResponse(
            source=source,
            ephemeral=ephemeral,
            profile=(
                None
                if ephemeral
                else ProfileSummary(profile_id=profile.profile_id, username=profile.username)
            ),
            state_profile_id=None if ephemeral else profile.profile_id,
            recommendations=tuple(view_model_to_dict(model) for model in visible),
            hidden_count=len(models) - len(visible),
            # Built from every model, not just the visible ones: a filter term
            # should not vanish from the control because the only title
            # carrying it is currently hidden.
            catalogue=catalogue_to_dict(models),
            state=EMPTY_LOCAL_STATE if state is None else local_state_to_dict(state),
            user_stats=dict(result.user_stats),
        )

    @app.post("/api/discover/feedback", response_model=FeedbackResponse)
    def discover_feedback(payload: FeedbackRequest) -> FeedbackResponse:
        """One vote. Mirrors what the card's three controls write."""
        profile_id = payload.profile_id.strip()
        if not profile_id:
            raise HTTPException(status_code=400, detail="profile_id is required.")

        state_service = services.recommendation_state
        if payload.action == "hidden":
            state = state_service.set_hidden(profile_id, payload.mal_id, payload.value)
        elif payload.action == "watch_later":
            state = state_service.set_watch_later(profile_id, payload.mal_id, payload.value)
        else:
            state = state_service.set_feedback(
                profile_id,
                payload.mal_id,
                payload.sentiment,
                genres=payload.genres,
                title=payload.title,
            )
        return FeedbackResponse(state=local_state_to_dict(state))

    # -- operations -------------------------------------------------------

    @app.get("/api/operations", response_model=OperationListResponse)
    def list_operations() -> OperationListResponse:
        return OperationListResponse(
            operations=tuple(
                OperationSnapshotResponse(**record.snapshot()) for record in operations.all()
            )
        )

    @app.get("/api/operations/{operation_id}", response_model=OperationSnapshotResponse)
    def get_operation(operation_id: str) -> OperationSnapshotResponse:
        record = operations.get(operation_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Unknown operation.")
        return OperationSnapshotResponse(**record.snapshot())

    @app.post(
        "/api/operations/{kind}",
        status_code=202,
        response_model=OperationAcceptedResponse,
    )
    def start_operation(
        kind: str, payload: OperationStartRequest = Body(default=OperationStartRequest())
    ) -> OperationAcceptedResponse:
        if kind not in SUPPORTED_KINDS:
            raise HTTPException(
                status_code=404, detail=f"Unsupported operation kind: {kind}"
            )
        profile = services.profiles.active_profile()
        profile_id = (payload.profile_id or (profile.profile_id if profile else "")).strip()
        username = (payload.username or (profile.username if profile else "")).strip()
        if not profile_id:
            raise HTTPException(
                status_code=409,
                detail="No active profile. Complete setup or pass profile_id.",
            )
        try:
            key = operation_key(kind, profile_id)
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

        handler = _build_handler(services, kind, payload, username, profile_id)
        try:
            record = operations.start(
                key, kind, profile_id, handler, serialize_result=any_to_dict
            )
        except OperationAlreadyRunningError as error:
            # 409, not 500: the desktop refuses the same start for the same
            # reason and the client's response is the same - do nothing, the
            # first one is still going.
            raise HTTPException(status_code=409, detail=str(error)) from error
        return OperationAcceptedResponse(**record.snapshot())

    @app.delete("/api/operations/{operation_id}")
    def cancel_operation(operation_id: str) -> dict[str, Any]:
        if not operations.cancel(operation_id):
            raise HTTPException(
                status_code=404, detail="No running operation with that id."
            )
        return {"cancelled": True, "id": operation_id}

    @app.get("/api/operations/{operation_id}/events")
    def operation_events(operation_id: str) -> StreamingResponse:
        """Server-sent events: ``started``, ``progress``/``step``, a terminal
        ``result``/``error``/``cancelled``, then ``finished``.

        Payload shapes are declared in ``models.ProgressEvent`` and in
        ``operations.error_payload``'s corresponding ``ApiError`` field for
        ``error``, but are not part of the OpenAPI document FastAPI generates
        for this route - it describes the streaming response's envelope, not
        the individual frames inside it. ``frontend/src/api/types.ts``
        declares these by hand for that reason.
        """
        record = operations.get(operation_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Unknown operation.")

        def stream() -> Iterator[str]:
            for item in record.follow():
                yield (
                    f"id: {item['seq']}\n"
                    f"event: {item['event']}\n"
                    f"data: {json.dumps(item['data'])}\n\n"
                )

        return StreamingResponse(
            stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    return app


def _build_handler(
    services: ApiContainer,
    kind: str,
    payload: OperationStartRequest,
    username: str,
    profile_id: str,
) -> Callable[[CancellationToken, Callable[[PipelineProgress], None]], Any]:
    """The one place a kind is bound to a service call.

    Each branch is the body of the matching ``BaseWorker.execute`` in
    ``gui/workers/operations.py``, with ``self.cancellation_token`` and
    ``self.report_progress`` arriving as arguments instead of attributes.
    """
    settings = services.settings.load()

    if kind == "sync":
        def run_sync(token: CancellationToken, report) -> Any:
            return services.orchestrator.run_sync(
                username,
                settings.pipeline,
                progress_callback=report,
                cancellation_token=token,
            )

        return run_sync

    if kind == "recommendation":
        def run_full(token: CancellationToken, report) -> Any:
            state = services.recommendation_state.load(profile_id)
            return services.orchestrator.run_full(
                username,
                settings.pipeline,
                progress_callback=report,
                cancellation_token=token,
                excluded_mal_ids=state.hidden_mal_ids,
            )

        return run_full

    if kind == "more-recommendations":
        count = max(1, int(payload.count or 5))

        def run_more(token: CancellationToken, report) -> Any:
            existing = services.results.load(profile_id)
            if existing is None or not existing.recommendations:
                raise ValueError("There is no generated feed to extend.")
            state = services.recommendation_state.load(profile_id)
            return services.orchestrator.run_more(
                username,
                settings.pipeline,
                existing_recommendations=existing.recommendations,
                excluded_mal_ids=state.hidden_mal_ids,
                count=count,
                progress_callback=report,
                cancellation_token=token,
            )

        return run_more

    if kind == "list-sync":
        def run_list_sync(token: CancellationToken, _report) -> Any:
            state = services.recommendation_state.load(profile_id)
            return services.mal_sync.sync(
                profile_id,
                username,
                watch_later_mal_ids=state.watch_later_mal_ids,
                client_id=settings.client_id,
                include_nsfw=settings.pipeline.include_nsfw,
                cancellation_token=token,
            )

        return run_list_sync

    if kind == "profile-lookup":
        target = payload.target or username

        def run_lookup(token: CancellationToken, _report) -> Any:
            return services.profiles.validate_public_profile(
                target, settings.client_id or "", cancellation=token
            )

        return run_lookup

    if kind == "api-test":
        def run_api_test(_token: CancellationToken, _report) -> Any:
            ApiConnectionService().test(settings)
            return {"ok": True}

        return run_api_test

    raise HTTPException(status_code=404, detail=f"Unsupported operation kind: {kind}")
