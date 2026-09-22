"""Resumable WebSocket stream endpoint."""

from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from api.errors import ApiError
from api.security import ApiCapability, require_websocket_capability
from api.streaming import StreamFanout, StreamSessionConfig
from infrastructure.logging import get_logger

router = APIRouter(tags=["streams"])
_LOGGER = get_logger("api.routes.streams")


@router.websocket("/v1/simulations/{run_id}/stream")
async def stream_simulation(websocket: WebSocket, run_id: str) -> None:
    settings = websocket.app.state.settings
    try:
        accepted_protocols = require_websocket_capability(
            websocket,
            settings,
            capability=ApiCapability.OBJECTIVE_INSPECTION,
        )
    except ApiError as exc:
        _LOGGER.warning(
            "stream_auth_rejected",
            run_id=run_id,
            reason_code=exc.code,
        )
        await websocket.close(code=4401)
        return

    subprotocol = accepted_protocols[0] if accepted_protocols else None
    await websocket.accept(subprotocol=subprotocol)

    after_cursor = 0
    raw_after = websocket.query_params.get("after_cursor")
    if raw_after is not None:
        try:
            after_cursor = int(raw_after)
        except ValueError:
            await websocket.close(code=4400)
            return
        if after_cursor < 0:
            await websocket.close(code=4400)
            return

    fanout: StreamFanout | None = getattr(websocket.app.state, "stream_fanout", None)
    if fanout is None:
        stream_repo = websocket.app.state.stream_repository
        fanout = StreamFanout(stream_repo=stream_repo, settings=settings)
        websocket.app.state.stream_fanout = fanout

    config = StreamSessionConfig(
        run_id=run_id,
        after_cursor=after_cursor,
        queue_size=settings.api_stream_queue_size,
        heartbeat_seconds=settings.api_stream_heartbeat_seconds,
        poll_seconds=settings.api_stream_poll_seconds,
    )
    _LOGGER.info(
        "stream_route_open",
        route_template="WS /v1/simulations/{run_id}/stream",
        run_id=run_id,
        cursor=after_cursor,
    )
    try:
        async for envelope in fanout.subscribe(config):
            await websocket.send_json(
                envelope.model_dump(mode="json", exclude_none=True)
            )
            if envelope.kind.value == "completion":
                break
    except WebSocketDisconnect:
        _LOGGER.info(
            "stream_client_disconnect",
            run_id=run_id,
            reason_code="client_disconnect",
        )
    except Exception:
        _LOGGER.error(
            "stream_route_failed",
            run_id=run_id,
            reason_code="stream_route_failed",
        )
        try:
            await websocket.close(code=1011)
        except Exception:
            pass
