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
    uri: str,
    call_id: str,
    first_turn: Turn,
    second_turn: Turn,
    barge_in_delay_ms: int,
    post_second_turn_wait_ms: int,
    agent_greets_first: bool,
    use_text_fallback: bool,
) -> None:
    stop = asyncio.Event()
    first_agent_audio = asyncio.Event()
    agent_done_events = asyncio.Queue()
    async with websockets.connect(uri) as ws:
        await ws.send(
            json.dumps(
                {
                    "event": "start",
                    "call_id": call_id,
                    "stream_id": "local-demo",
                    "use_text_fallback": use_text_fallback,
                    "agent_greets_first": agent_greets_first,
                }
            )
        )
        printer = asyncio.create_task(print_server_events(ws, stop, first_agent_audio, agent_done_events))

        current_ms = 1000
        if agent_greets_first:
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

        await asyncio.sleep(post_second_turn_wait_ms / 1000)
        await ws.send(json.dumps({"event": "stop"}))
        await stop.wait()
        printer.cancel()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the local fake WAV call demo.")
    parser.add_argument("--uri", default=f"ws://localhost:{settings.port}/media-stream")
    parser.add_argument("--call-id", default=None)
    parser.add_argument("--first-wav", default=str(settings.fixture_dir / "audio_1.wav"))
    parser.add_argument("--second-wav", default=str(settings.fixture_dir / "audio_2.wav"))
    parser.add_argument("--barge-in-delay-ms", type=int, default=200)
    parser.add_argument("--post-second-turn-wait-ms", type=int, default=5000)
    parser.add_argument("--no-agent-greeting", dest="agent_greets_first", action="store_false")
    parser.set_defaults(agent_greets_first=True)
    args = parser.parse_args()

    call_id = args.call_id or generate_call_id()

    turns = [
        Turn(Path(args.first_wav)),
        Turn(Path(args.second_wav)),
    ]
    asyncio.run(
        run_fake_call(
            args.uri,
            call_id,
            turns[0],
            turns[1],
            args.barge_in_delay_ms,
            args.post_second_turn_wait_ms,
            args.agent_greets_first,
            use_text_fallback=False,
        )
    )


if __name__ == "__main__":
    main()
