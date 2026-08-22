"""Event service for SSE (Server-Sent Events) streaming."""

from __future__ import annotations

import asyncio
import json
from collections import defaultdict
from typing import Any, AsyncGenerator

import structlog

logger = structlog.get_logger()


class EventService:
    """Manages SSE event streams per negotiation."""

    def __init__(self) -> None:
        self._queues: dict[str, list[asyncio.Queue]] = defaultdict(list)

    def subscribe(self, negotiation_id: str) -> asyncio.Queue:
        """Create a new subscriber queue for a negotiation."""
        queue: asyncio.Queue = asyncio.Queue()
        self._queues[negotiation_id].append(queue)
        logger.info("sse_subscriber_added", negotiation_id=negotiation_id)
        return queue

    def unsubscribe(self, negotiation_id: str, queue: asyncio.Queue) -> None:
        """Remove a subscriber queue."""
        if negotiation_id in self._queues:
            try:
                self._queues[negotiation_id].remove(queue)
            except ValueError:
                pass
            if not self._queues[negotiation_id]:
                del self._queues[negotiation_id]

    async def publish(self, negotiation_id: str, event: dict[str, Any]) -> None:
        """Publish an event to all subscribers of a negotiation."""
        if negotiation_id not in self._queues:
            return

        data = json.dumps(event, default=str)
        for queue in self._queues[negotiation_id]:
            try:
                await queue.put(data)
            except Exception as e:
                logger.error("sse_publish_error", error=str(e))

    async def publish_events(self, negotiation_id: str, events: list[dict[str, Any]]) -> None:
        """Publish multiple events."""
        for event in events:
            await self.publish(negotiation_id, event)

    async def event_generator(
        self, negotiation_id: str, queue: asyncio.Queue
    ) -> AsyncGenerator[str, None]:
        """Generate SSE events for a subscriber."""
        try:
            while True:
                try:
                    data = await asyncio.wait_for(queue.get(), timeout=30)
                    yield f"data: {data}\n\n"
                except asyncio.TimeoutError:
                    # Send keepalive
                    yield f": keepalive\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            self.unsubscribe(negotiation_id, queue)

    async def close_negotiation(self, negotiation_id: str) -> None:
        """Signal that the negotiation is complete and close all queues."""
        complete_event = json.dumps({"event_type": "NEGOTIATION_COMPLETE", "data": {}})
        if negotiation_id in self._queues:
            for queue in self._queues[negotiation_id]:
                await queue.put(complete_event)


# ─── Singleton ──────────────────────────────────────────────────────────────

_event_service: EventService | None = None


def get_event_service() -> EventService:
    global _event_service
    if _event_service is None:
        _event_service = EventService()
    return _event_service
