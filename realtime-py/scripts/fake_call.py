import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import NamedTuple

import websockets

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.audio import load_wav
from app.config import settings
from app.transcript import generate_call_id

CALL_URI = f"ws://localhost:{settings.port}/media-stream"
FIRST_WAV = settings.fixture_dir / "audio_1.wav"
SECOND_WAV = settings.fixture_dir / "audio_2.wav"
POST_SECOND_TURN_WAIT_MS = 5000
AGENT_GREETS_FIRST = False


class Turn(NamedTuple):
    wav_path: Path


async def stream_turn(ws, wav_path: Path, start_ms: int) -> int:
    audio = load_wav(wav_path)
    await ws.send(json.dumps({"event": "user_turn_start", "timestamp_ms": start_ms}))

    timestamp_ms = start_ms
    for chunk in audio.chunks(start_ms=start_ms):
        await ws.send(
            json.dumps(
                {
                    "event": "media",
                    "media": {
                        "timestamp_ms": chunk.timestamp_ms,
                        "payload": chunk.payload,
                    },
                }
            )
        )
        timestamp_ms = chunk.timestamp_ms + chunk.duration_ms
        await asyncio.sleep(chunk.duration_ms / 1000)

    await ws.send(json.dumps({"event": "user_turn_end", "timestamp_ms": timestamp_ms}))
    return timestamp_ms


async def print_server_events(
    ws,
    stop: asyncio.Event,
    first_agent_audio: asyncio.Event,
    agent_done_events: asyncio.Queue,
) -> None:
    async for message in ws:
        event = json.loads(message)
        event_name = event.get("event")
        if event_name == "media" and event.get("speaker") == "agent":
            first_agent_audio.set()
        elif event_name == "agent_done":
            await agent_done_events.put(event)
        elif event_name == "clear":
            print("agent audio cleared because of barge-in")
        else:
            print(event)
        if event_name == "call_saved":
            stop.set()
            return


async def run_fake_call(
    first_turn: Turn,
    second_turn: Turn,
    barge_in_delay_ms: int,
) -> None:
    stop = asyncio.Event()
    first_agent_audio = asyncio.Event()
    agent_done_events = asyncio.Queue()
    async with websockets.connect(CALL_URI) as ws:
        await ws.send(
            json.dumps(
                {
                    "event": "start",
                    "call_id": generate_call_id(),
                    "stream_id": "local-demo",
                    "use_text_fallback": False,
                    "agent_greets_first": AGENT_GREETS_FIRST,
                }
            )
        )
        printer = asyncio.create_task(print_server_events(ws, stop, first_agent_audio, agent_done_events))

        current_ms = 1000
        if AGENT_GREETS_FIRST:
            try:
                greeting_done = await asyncio.wait_for(agent_done_events.get(), timeout=30)
                current_ms = max(current_ms, int(greeting_done.get("end_ms", 0)) + 300)
                first_agent_audio.clear()
            except asyncio.TimeoutError:
                print("timed out waiting for agent greeting; sending first turn anyway")

        current_ms = await stream_turn(ws, first_turn.wav_path, current_ms)

        try:
            await asyncio.wait_for(first_agent_audio.wait(), timeout=30)
        except asyncio.TimeoutError:
            print("timed out waiting for agent audio; sending second turn anyway")

        await asyncio.sleep(barge_in_delay_ms / 1000)
        current_ms += barge_in_delay_ms
        current_ms = await stream_turn(ws, second_turn.wav_path, current_ms)

        await asyncio.sleep(POST_SECOND_TURN_WAIT_MS / 1000)
        await ws.send(json.dumps({"event": "stop"}))
        await stop.wait()
        printer.cancel()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the local fake WAV call demo.")
    parser.add_argument("--barge-in-delay-ms", type=int, default=200)
    args = parser.parse_args()

    turns = [
        Turn(FIRST_WAV),
        Turn(SECOND_WAV),
    ]
    asyncio.run(
        run_fake_call(
            turns[0],
            turns[1],
            args.barge_in_delay_ms,
        )
    )


if __name__ == "__main__":
    main()
