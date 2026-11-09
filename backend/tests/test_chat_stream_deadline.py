import asyncio
import json

from app.api import chat


def test_chat_stream_deadline_emits_terminal_timeout_and_cancels_agent():
    cancelled = False

    async def stalled_agent():
        nonlocal cancelled
        try:
            await asyncio.Event().wait()
            yield "unreachable"
        finally:
            cancelled = True

    async def collect():
        return [
            frame
            async for frame in chat._iter_with_chat_deadline(
                stalled_agent(), timeout_seconds=0.01
            )
        ]

    frames = asyncio.run(collect())
    events = [json.loads(frame) for frame in frames if frame.startswith("{")]

    assert any(
        event.get("type") == "text" and "时限" in event.get("content", "")
        for event in events
    )
    terminal = [event for event in events if event.get("type") == "done"]
    assert len(terminal) == 1
    assert terminal[0]["status"] == "timeout"
    assert cancelled
