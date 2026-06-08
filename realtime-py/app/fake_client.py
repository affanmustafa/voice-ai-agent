import asyncio
import json
import time
from pathlib import Path
from typing import Any, Callable, Dict, NamedTuple, Optional

import websockets

from app.audio import load_wav
from app.config import settings
from app.transcript import generate_call_id


CALL_URI = f"ws://localhost:{settings.port}/media-stream"
ZERO_WAV = settings.fixture_dir / (
    "audio_0-tool-call.wav" if settings.tool_call_enabled else "audio_0.wav"
)
FIRST_WAV = settings.fixture_dir / "audio_1.wav"
SECOND_WAV = settings.fixture_dir / "audio_2.wav"
POST_SECOND_TURN_WAIT_MS = 5000


class StreamResult(NamedTuple):
    speech_end_ms: int
    stream_end_ms: int
    speech_end_time: float


async def send_json(ws: Any, event: dict) -> None:
    await ws.send(json.dumps(event))


async def send_media_frame(ws: Any, timestamp_ms: int, payload: str) -> None:
    await send_json(
        ws,
        {
            "event": "media",
            "media": {
                "timestamp_ms": timestamp_ms,
                "payload": payload,
            },
        },
    )


async def stream_turn(ws: Any, wav_path: Path, start_ms: int) -> StreamResult:
    audio = load_wav(wav_path)
    await send_json(ws, {"event": "user_turn_start", "timestamp_ms": start_ms})

    timestamp_ms = start_ms
    for chunk in audio.chunks(start_ms=start_ms):
        await send_media_frame(ws, chunk.timestamp_ms, chunk.payload)
        timestamp_ms = chunk.timestamp_ms + chunk.duration_ms
        await asyncio.sleep(chunk.duration_ms / 1000)

    speech_end_ms = timestamp_ms
    speech_end_time = time.monotonic()
    await send_json(ws, {"event": "user_turn_end", "timestamp_ms": speech_end_ms})
    return StreamResult(
        speech_end_ms=speech_end_ms,
        stream_end_ms=speech_end_ms,
        speech_end_time=speech_end_time,
    )


async def collect_server_events(
    ws: Any,
    stop: asyncio.Event,
    first_agent_audio: asyncio.Event,
    agent_done_events: asyncio.Queue,
    marks: Dict[str, float],
    on_event: Optional[Callable[[dict], None]] = None,
) -> None:
    async for message in ws:
        event = json.loads(message)
        event_name = event.get("event")
        if event_name == "media" and event.get("speaker") == "agent":
            if "agent_heard" not in marks and "speech_end" in marks:
                marks["agent_heard"] = time.monotonic()
            first_agent_audio.set()
        elif event_name == "agent_done":
            await agent_done_events.put(event)
        elif on_event:
            on_event(event)
        if event_name == "call_saved":
            stop.set()
            return


async def wait_for_agent_done(
    agent_done_events: asyncio.Queue,
    on_event: Optional[Callable[[dict], None]],
    timeout_message: str,
) -> Optional[dict]:
    try:
        return await asyncio.wait_for(agent_done_events.get(), timeout=30)
    except asyncio.TimeoutError:
        if on_event:
            on_event({"event": "demo_warning", "message": timeout_message})
        return None


async def run_fixture_call(
    *,
    uri: str = CALL_URI,
    zero_wav: Path = ZERO_WAV,
    first_wav: Path = FIRST_WAV,
    second_wav: Path = SECOND_WAV,
    barge_in_delay_ms: int = 200,
    on_event: Optional[Callable[[dict], None]] = None,
) -> str:
    call_id = generate_call_id()
    stop = asyncio.Event()
    first_agent_audio = asyncio.Event()
    agent_done_events = asyncio.Queue()
    marks: Dict[str, float] = {}

    async with websockets.connect(uri) as ws:
        await ws.send(
            json.dumps(
                {
                    "event": "start",
                    "call_id": call_id,
                    "stream_id": "local-demo",
                }
            )
        )
        collector = asyncio.create_task(
            collect_server_events(ws, stop, first_agent_audio, agent_done_events, marks, on_event)
        )

        current_ms = 100
        zero_result = await stream_turn(ws, zero_wav, current_ms)
        current_ms = zero_result.stream_end_ms
        zero_done = await wait_for_agent_done(
            agent_done_events,
            on_event,
            "timed out waiting for agent response to audio_0.wav",
        )
        if zero_done:
            current_ms = max(current_ms, int(zero_done.get("end_ms", 0)) + 300)
        first_agent_audio.clear()

        first_result = await stream_turn(ws, first_wav, current_ms)
        current_ms = first_result.stream_end_ms
        marks["speech_end"] = first_result.speech_end_time

        try:
            await asyncio.wait_for(first_agent_audio.wait(), timeout=30)
        except asyncio.TimeoutError:
            if on_event:
                on_event({"event": "demo_warning", "message": "timed out waiting for agent audio"})

        if "speech_end" in marks and "agent_heard" in marks:
            voice_to_voice_ms = int(round((marks["agent_heard"] - marks["speech_end"]) * 1000))
            await ws.send(
                json.dumps(
                    {
                        "event": "client_metric",
                        "voice_to_voice_ms": voice_to_voice_ms,
                    }
                )
            )
            if on_event:
                on_event({"event": "client_metric", "voice_to_voice_ms": voice_to_voice_ms})

        await asyncio.sleep(barge_in_delay_ms / 1000)
        current_ms += barge_in_delay_ms
        second_result = await stream_turn(ws, second_wav, current_ms)
        current_ms = second_result.stream_end_ms

        await asyncio.sleep(POST_SECOND_TURN_WAIT_MS / 1000)
        await ws.send(json.dumps({"event": "stop"}))
        await stop.wait()
        collector.cancel()

    return call_id
