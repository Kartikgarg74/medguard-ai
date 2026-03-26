"""In-process async pub/sub message bus for agent communication."""

import asyncio
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Coroutine

from src.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class Message:
    """Message passed between agents via the bus."""

    topic: str
    agent_source: str
    payload: dict
    correlation_id: str = ""
    priority: int = 1  # 0=low, 1=normal, 2=high, 3=critical
    timestamp: str = ""
    message_id: str = ""

    def __post_init__(self):
        if not self.message_id:
            self.message_id = str(uuid.uuid4())
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()
        if not self.correlation_id:
            self.correlation_id = str(uuid.uuid4())


# Type alias for subscriber handlers
Handler = Callable[[Message], Coroutine[Any, Any, None]]


class MessageBus:
    """
    Async in-process pub/sub message bus.

    Agents publish messages to topics. Subscribers receive
    messages on their own asyncio.Queue.
    """

    def __init__(self):
        self._subscribers: dict[str, list[tuple[str, asyncio.Queue]]] = {}
        self._handlers: dict[str, list[Handler]] = {}
        self._message_count = 0
        self._running = False

    def subscribe(self, topic: str, handler: Handler, subscriber_name: str = ""):
        """Register a handler for a topic."""
        if topic not in self._handlers:
            self._handlers[topic] = []
        self._handlers[topic].append(handler)
        logger.debug(f"MessageBus: '{subscriber_name or 'anon'}' subscribed to '{topic}'")

    def subscribe_queue(self, topic: str, subscriber_name: str = "") -> asyncio.Queue:
        """Subscribe with a queue (for pull-based consumption)."""
        if topic not in self._subscribers:
            self._subscribers[topic] = []
        queue: asyncio.Queue = asyncio.Queue()
        self._subscribers[topic].append((subscriber_name, queue))
        logger.debug(f"MessageBus: '{subscriber_name}' queue-subscribed to '{topic}'")
        return queue

    async def publish(self, message: Message):
        """Publish a message to all subscribers of the topic."""
        self._message_count += 1

        # Push-based: call handlers
        handlers = self._handlers.get(message.topic, [])
        for handler in handlers:
            try:
                await handler(message)
            except Exception as e:
                logger.error(f"MessageBus handler error on '{message.topic}': {e}")

        # Queue-based: enqueue for pull consumers
        subscribers = self._subscribers.get(message.topic, [])
        for name, queue in subscribers:
            await queue.put(message)

        # Wildcard subscribers (topic = "*")
        for handler in self._handlers.get("*", []):
            try:
                await handler(message)
            except Exception as e:
                logger.error(f"MessageBus wildcard handler error: {e}")

        for name, queue in self._subscribers.get("*", []):
            await queue.put(message)

        logger.debug(
            f"MessageBus: published '{message.topic}' from "
            f"'{message.agent_source}' "
            f"(handlers={len(handlers)}, queues={len(subscribers)})"
        )

    @property
    def stats(self) -> dict:
        topics = set(list(self._subscribers.keys()) + list(self._handlers.keys()))
        return {
            "total_messages": self._message_count,
            "topics": list(topics),
            "subscriber_count": sum(len(subs) for subs in self._subscribers.values()),
            "handler_count": sum(len(handlers) for handlers in self._handlers.values()),
        }


# Global message bus instance
_bus = MessageBus()


def get_message_bus() -> MessageBus:
    return _bus
