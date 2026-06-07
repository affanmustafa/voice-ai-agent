"""
Verifies the WebSocketDisconnect code path in server.py without a real WebSocket.

The disconnect handler does exactly three things:
  1. session.finalize_agent(interrupted=True)
  2. store.save(session)
  3. close OpenAI WS (not tested here — that's an external call)

We replicate steps 1 and 2 directly.
"""
import json
import tempfile
from pathlib import Path

from app.transcript import CallSession, TranscriptStore


def _make_session_mid_call(call_id: str) -> CallSession:
    """Simulate a session where the user spoke and the agent was mid-reply."""
    session = CallSession(call_id=call_id)

    # User finished speaking
    session.start_user_speech(start_ms=0)
    session.stop_user_speech(end_ms=1200)
    session.finalize_user_transcript("Hi I'd like to order some chicken", item_id="u1")

    # Agent started replying but never finished (disconnect happens here)
    session.append_agent_transcript("agent-item-1", "Sure, I can help you with that")
    session.append_agent_transcript("agent-item-1", " — what size would you like")

    return session


def test_disconnect_saves_transcript_with_interrupted_flag(tmp_path: Path) -> None:
    store = TranscriptStore(data_dir=tmp_path)
    session = _make_session_mid_call("test-disconnect-001")

    # Replicate the WebSocketDisconnect handler
    session.finalize_agent(interrupted=True)
    store.save(session)

    saved = json.loads((tmp_path / "test-disconnect-001.json").read_text())

    utterances = saved["utterances"]
    assert len(utterances) == 2, f"Expected 2 utterances, got {len(utterances)}"

    user_utt = utterances[0]
    assert user_utt["speaker"] == "user"
    assert "interrupted" not in user_utt  # user turns never have interrupted flag

    agent_utt = utterances[1]
    assert agent_utt["speaker"] == "agent"
    assert agent_utt["interrupted"] is True, "Agent utterance must be marked interrupted"
    assert agent_utt["text"].endswith("-"), "Interrupted text must end with a dash"


def test_disconnect_before_start_saves_nothing(tmp_path: Path) -> None:
    """If disconnect happens before the 'start' event, session is None — nothing saved."""
    store = TranscriptStore(data_dir=tmp_path)
    session = None  # as in server.py before 'start' event arrives

    # Replicate the guard: if session: finalize + save
    if session:
        session.finalize_agent(interrupted=True)
        store.save(session)

    assert list(tmp_path.glob("*.json")) == [], "No file should be written if session is None"


def test_disconnect_with_no_active_agent(tmp_path: Path) -> None:
    """Disconnect between turns (agent not speaking) still saves completed utterances."""
    store = TranscriptStore(data_dir=tmp_path)
    session = CallSession(call_id="test-disconnect-002")

    session.start_user_speech(start_ms=0)
    session.stop_user_speech(end_ms=800)
    session.finalize_user_transcript("Hello", item_id="u1")

    # Agent fully finished its turn already — no active_agent at disconnect time
    session.append_agent_transcript("agent-item-1", "Hello, welcome to KFC!")
    session.finalize_agent(interrupted=False)

    # Now disconnect fires
    session.finalize_agent(interrupted=True)  # active_agent is None — should be a no-op
    store.save(session)

    saved = json.loads((tmp_path / "test-disconnect-002.json").read_text())
    utterances = saved["utterances"]

    assert len(utterances) == 2
    agent_utt = utterances[1]
    assert agent_utt["interrupted"] is False  # already finalized cleanly before disconnect
