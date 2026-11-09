from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from extract_matvenus_session import extract_messages, render_markdown  # noqa: E402


def test_extract_matvenus_completed_messages_with_spans():
    payload = {
        "id": "08b460b1-3d8c-4235-8a20-136f9f50eb4e",
        "completedMessages": [
            {
                "sender": "human",
                "msg_id": "u1",
                "spans": [{"type": "text", "content": "分析 388 aa 蛋白稳定性"}],
            },
            {
                "sender": "agent",
                "model": "venus",
                "msg_id": "a1",
                "spans": [
                    {
                        "type": "step",
                        "title": "结构位点筛选",
                        "spans": [{"type": "text", "content": "远离活性中心，优先柔性环区。"}],
                    },
                    {"type": "report", "content": "最终建议：先做 8 个单点。"},
                    {
                        "type": "tool_call",
                        "name": "session_lookup",
                        "arguments": {"token": "secret-token", "query": "stability"},
                    },
                ],
            },
        ],
    }

    messages = extract_messages(payload)

    assert len(messages) == 2
    assert messages[0].role == "Human"
    assert messages[1].role == "Agent"
    assert "结构位点筛选" in messages[1].text
    assert "最终建议" in messages[1].text
    assert "[REDACTED]" in messages[1].text
    assert "secret-token" not in messages[1].text

    markdown = render_markdown(Path("matvenus-session.json"), payload, messages)
    assert "Matvenus Session Review" in markdown
    assert "结构位点筛选" in markdown
    assert "session_lookup" in markdown


def test_extract_matvenus_stream_events():
    payload = {
        "id": "08b460b1-3d8c-4235-8a20-136f9f50eb4e",
        "stream_events": [
            {
                "event": "msg_user",
                "data": {
                    "role": "user",
                    "msg_id": "u1",
                    "content": [{"type": "text", "text": "分析 P338T"}],
                },
            },
            {
                "event": "msg_chunk",
                "data": {
                    "role": "assistant",
                    "msg_id": "a1",
                    "content": [
                        {
                            "type": "reasoning",
                            "reasoning": "识别为活力-稳定性权衡。",
                        },
                        {
                            "type": "text",
                            "text": "保留 P338T 活性收益，再做局部稳定性补偿。",
                        },
                        {
                            "type": "tool_call_chunk",
                            "name": "venusrem_mutation_prediction",
                            "args": '{"secret": "hidden", "task": "stability"}',
                        },
                    ],
                },
            },
            {
                "event": "tool_call",
                "data": {
                    "role": "assistant",
                    "msg_id": "a1",
                    "tool_name": "venusrem_mutation_prediction",
                    "tool_args": {"token": "secret-token", "task": "stability"},
                    "content": None,
                },
            },
        ],
    }

    messages = extract_messages(payload)

    assert len(messages) == 2
    assert messages[0].role == "Human"
    assert messages[1].role == "Agent"
    assert "活力-稳定性权衡" in messages[1].text
    assert "局部稳定性补偿" in messages[1].text
    assert "venusrem_mutation_prediction" in messages[1].tool_calls
    assert "[REDACTED]" in messages[1].text
    assert "secret-token" not in messages[1].text

    markdown = render_markdown(Path("matvenus-stream-events.json"), payload, messages)
    assert "Messages: `2`" in markdown
    assert "venusrem_mutation_prediction" in markdown
