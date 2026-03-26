"""Tests for message bus, scheduler, and pipeline orchestration."""

import asyncio
import os

import pytest

os.environ["DATABASE_PATH"] = ":memory:"

from src.orchestrator.message_bus import Message, MessageBus
from src.orchestrator.pipeline import MedGuardPipeline, PipelineStatus


# --- Message Bus Tests ---


@pytest.mark.asyncio
async def test_message_creation():
    msg = Message(
        topic="test.topic",
        agent_source="test_agent",
        payload={"key": "value"},
    )
    assert msg.topic == "test.topic"
    assert msg.message_id  # auto-generated UUID
    assert msg.timestamp  # auto-generated
    assert msg.correlation_id  # auto-generated


@pytest.mark.asyncio
async def test_publish_to_handler():
    bus = MessageBus()
    received = []

    async def handler(msg: Message):
        received.append(msg)

    bus.subscribe("test.topic", handler, "test_subscriber")

    await bus.publish(Message(topic="test.topic", agent_source="sender", payload={"data": 1}))

    assert len(received) == 1
    assert received[0].payload == {"data": 1}


@pytest.mark.asyncio
async def test_publish_to_queue():
    bus = MessageBus()
    queue = bus.subscribe_queue("test.topic", "test_subscriber")

    await bus.publish(Message(topic="test.topic", agent_source="sender", payload={"data": 2}))

    msg = await asyncio.wait_for(queue.get(), timeout=1.0)
    assert msg.payload == {"data": 2}


@pytest.mark.asyncio
async def test_multiple_subscribers():
    bus = MessageBus()
    received_a = []
    received_b = []

    async def handler_a(msg):
        received_a.append(msg)

    async def handler_b(msg):
        received_b.append(msg)

    bus.subscribe("test.topic", handler_a, "sub_a")
    bus.subscribe("test.topic", handler_b, "sub_b")

    await bus.publish(Message(topic="test.topic", agent_source="sender", payload={}))

    assert len(received_a) == 1
    assert len(received_b) == 1


@pytest.mark.asyncio
async def test_wildcard_subscriber():
    bus = MessageBus()
    received = []

    async def wildcard_handler(msg):
        received.append(msg)

    bus.subscribe("*", wildcard_handler, "wildcard")

    await bus.publish(Message(topic="topic.a", agent_source="sender", payload={}))
    await bus.publish(Message(topic="topic.b", agent_source="sender", payload={}))

    assert len(received) == 2


@pytest.mark.asyncio
async def test_no_subscribers_no_error():
    bus = MessageBus()
    # Should not raise
    await bus.publish(Message(topic="orphan.topic", agent_source="sender", payload={}))
    assert bus.stats["total_messages"] == 1


@pytest.mark.asyncio
async def test_handler_error_doesnt_break_bus():
    bus = MessageBus()
    received = []

    async def bad_handler(msg):
        raise ValueError("oops")

    async def good_handler(msg):
        received.append(msg)

    bus.subscribe("test", bad_handler, "bad")
    bus.subscribe("test", good_handler, "good")

    await bus.publish(Message(topic="test", agent_source="sender", payload={}))

    # Good handler should still receive despite bad handler error
    assert len(received) == 1


def test_bus_stats():
    bus = MessageBus()
    bus.subscribe("topic.a", lambda m: None, "sub1")
    bus.subscribe("topic.b", lambda m: None, "sub2")
    stats = bus.stats
    assert stats["handler_count"] == 2
    assert len(stats["topics"]) == 2


@pytest.mark.asyncio
async def test_message_correlation_id():
    """Messages in a pipeline run share a correlation_id."""
    bus = MessageBus()
    received = []

    async def handler(msg):
        received.append(msg)

    bus.subscribe("*", handler)

    corr_id = "pipeline-run-123"
    await bus.publish(
        Message(
            topic="stage.1",
            agent_source="a1",
            payload={},
            correlation_id=corr_id,
        )
    )
    await bus.publish(
        Message(
            topic="stage.2",
            agent_source="a2",
            payload={},
            correlation_id=corr_id,
        )
    )

    assert all(m.correlation_id == corr_id for m in received)


# --- Pipeline Status Tests ---


def test_pipeline_initial_status():
    pipeline = MedGuardPipeline()
    status = pipeline.get_status()
    assert status["status"] == "idle"
    assert status["run_count"] == 0
    assert status["last_run"] is None
    assert "scraper" in status["agents"]
    assert "compliance" in status["agents"]
    assert "reporter" in status["agents"]
    assert "alert" in status["agents"]


def test_pipeline_status_enum():
    assert PipelineStatus.IDLE.value == "idle"
    assert PipelineStatus.SCRAPING.value == "scraping"
    assert PipelineStatus.COMPLETED.value == "completed"
    assert PipelineStatus.FAILED.value == "failed"
