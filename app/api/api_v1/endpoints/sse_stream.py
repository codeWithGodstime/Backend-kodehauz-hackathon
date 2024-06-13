import asyncio
import json
import logging
from typing import Dict, List

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse

from app.api import deps
from app.core.config import settings
from app.models.event import ServerEvent
from app.models.workspace import Workspace  # noqa

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
router = APIRouter()
COUNTER = 0


events: Dict[int, List[ServerEvent]] = {}


def emit_event(event: ServerEvent, workspace: Workspace):
    global events
    if events.get(workspace.id) is None:
        events[workspace.id] = []
    events[workspace.id].append(event)


def get_event(workspace: Workspace):
    global events
    try:
        if events.get(workspace.id) is not None:
            return events[workspace.id].pop() if len(events[workspace.id]) else None
        return None
    except Exception as err:
        logger.error(err)
        return None


@router.get("/stream")
async def message_stream(
    request: Request,
    iterations: int = None,
    workspace: Workspace = Depends(deps.get_current_workspace_anonymous),
):
    async def event_generator():
        global COUNTER
        count = 0
        while True:
            count += 1
            if iterations and count > iterations:
                break
            if await request.is_disconnected():
                logger.debug("Request disconnected")
                break

            # Checks for new messages and return them to client if any
            event = get_event(workspace)
            if event:
                logger.debug("sending event", event)
                yield "event: {}\nid: {}\nretry: {}\ndata: {}\n\n".format(
                    event.name,
                    COUNTER,
                    settings.STREAM_RETRY_TIMEOUT,
                    json.dumps(event.data),
                )
                COUNTER += 1
            await asyncio.sleep(settings.STREAM_DELAY)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/stream2")
async def message_stream_2(
    request: Request,
    iterations: int = None,
    workspace: Workspace = Depends(deps.get_current_workspace_anonymous),
):
    async def event_generator():
        global COUNTER
        count = 0
        while True:
            count += 1
            if iterations and count > iterations:
                break
            if await request.is_disconnected():
                logger.debug("Request disconnected")
                break

            # Checks for new messages and return them to client if any
            event = get_event(workspace)
            if event:
                logger.debug("sending event", event)
                yield {
                    "event": event.name,
                    "id": COUNTER,
                    "retry": settings.STREAM_RETRY_TIMEOUT,
                    "data": json.dumps(event.data),
                }
                COUNTER += 1
            await asyncio.sleep(settings.STREAM_DELAY)

    return EventSourceResponse(event_generator())


@router.get("/test-event")
async def test_event(
    name: str = "testing",
    workspace: Workspace = Depends(deps.get_current_workspace_anonymous),
):
    emit_event(ServerEvent(name=name, data=["testing"]), workspace)


@router.get("/end-event")
async def end_event(workspace: Workspace = Depends(deps.get_current_workspace_anonymous)):
    emit_event(ServerEvent(name="end_event", data=["end-event"]), workspace)
