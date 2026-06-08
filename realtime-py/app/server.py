import asyncio
import json
from typing import Any, Dict, Optional

import websockets
from fastapi import FastAPI, HTTPException, WebSocket
from fastapi.responses import JSONResponse
from fastapi.websockets import WebSocketDisconnect

from app.realtime import (
    LOG_EVENT_TYPES,
    commit_audio_user_turn,
    initialize_session,
    openai_headers,
    log_openai_event,
    realtime_url,
    request_response,
    send_text_user_turn,
    send_truncate,
)
from app.transcript import CallSession, TranscriptStore, generate_call_id


app = FastAPI(title="Realtime Voice Pipeline Demo")
store = TranscriptStore()
AGENT_GREETING = "In English, greet the caller as a KFC ordering assistant and ask how you can help."

@app.get("/calls", response_class=JSONResponse)
async def list_calls() -> Dict[str, Any]:
    return {"calls": store.list_ids()}


@app.get("/calls/{call_id}", response_class=JSONResponse)
async def get_call(call_id: str) -> Dict[str, Any]:
    try:
        return store.load(call_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Call not found")


@app.websocket("/media-stream")
async def handle_media_stream(websocket: WebSocket) -> None:
    await websocket.accept()

    session: Optional[CallSession] = None
    stop_event = asyncio.Event()
    outgoing_audio_enabled = True
    use_text_fallback = True
    agent_greets_first = False
    suppressed_agent_items = set()
    transcript_saved = False

    async with websockets.connect(realtime_url(), additional_headers=openai_headers()) as openai_ws:
        await initialize_session(openai_ws)

        def save_transcript(interrupted: bool) -> None:
            nonlocal transcript_saved
            if not session or transcript_saved:
                return
            session.maybe_finalize_user_with_fallback()
            session.finalize_agent(interrupted=interrupted)
            store.save(session)
            transcript_saved = True

        async def handle_barge_in() -> None:
            nonlocal outgoing_audio_enabled
            if not session or not session.active_agent:
                return
            outgoing_audio_enabled = False
            interrupted_item_id = session.active_agent.item_id
            suppressed_agent_items.add(interrupted_item_id)
            await send_truncate(
                openai_ws,
                interrupted_item_id,
                session.current_agent_audio_offset_ms(),
            )
            session.finalize_agent(interrupted=True)
            await websocket.send_json({"event": "clear", "reason": "barge_in"})

        async def receive_from_client() -> None:
            nonlocal session, outgoing_audio_enabled, use_text_fallback, agent_greets_first
            try:
                async for message in websocket.iter_text():
                    data = json.loads(message)
                    event = data.get("event")

                    if event == "start":
                        call_id = data.get("call_id") or data.get("start", {}).get("call_id") or generate_call_id()
                        session = CallSession(call_id=call_id)
                        session.stream_id = data.get("stream_id") or data.get("start", {}).get("stream_id")
                        use_text_fallback = bool(data.get("use_text_fallback", True))
                        agent_greets_first = bool(data.get("agent_greets_first", False))
                        await websocket.send_json({"event": "ready", "call_id": session.call_id})
                        if agent_greets_first:
                            await request_response(openai_ws, instructions=AGENT_GREETING)
                        continue

                    if not session:
                        continue

                    if event == "user_turn_start":
                        session.start_user_speech(data.get("timestamp_ms"))
                        if use_text_fallback and data.get("text"):
                            session.set_user_fallback_text(data["text"])
                        await handle_barge_in()
                        continue

                    if event == "user_turn_end":
                        session.stop_user_speech(data.get("timestamp_ms"))
                        if use_text_fallback and data.get("text"):
                            session.set_user_fallback_text(data["text"])
                            session.finalize_user_transcript(data["text"])
                            outgoing_audio_enabled = True
                            await send_text_user_turn(openai_ws, data["text"])
                        elif not use_text_fallback:
                            outgoing_audio_enabled = True
                            await commit_audio_user_turn(openai_ws)
                        continue

                    if event == "media":
                        media = data.get("media", {})
                        timestamp_ms = int(media.get("timestamp_ms", 0))
                        session.update_client_timestamp(timestamp_ms)
                        if not use_text_fallback:
                            await openai_ws.send(
                                json.dumps(
                                    {
                                        "type": "input_audio_buffer.append",
                                        "audio": media.get("payload", ""),
                                    }
                                )
                            )
                        continue

                    if event == "stop":
                        if session:
                            save_transcript(interrupted=False)
                            await websocket.send_json({"event": "call_saved", "call_id": session.call_id})
                        stop_event.set()
                        await openai_ws.close()
                        break
            except WebSocketDisconnect:
                pass
            finally:
                if not stop_event.is_set():
                    save_transcript(interrupted=True)
                    stop_event.set()
                    if openai_ws.state.name == "OPEN":
                        await openai_ws.close()

        async def send_to_client() -> None:
            nonlocal outgoing_audio_enabled
            try:
                async for openai_message in openai_ws:
                    if stop_event.is_set():
                        break

                    event = json.loads(openai_message)
                    event_type = event.get("type")
                    log_openai_event("OpenAI <-", event)
                    if event_type in LOG_EVENT_TYPES:
                        print(f"Realtime event: {event_type}")

                    if not session:
                        continue

                    if event_type == "input_audio_buffer.speech_started":
                        if session.active_user.start_ms is None:
                            session.start_user_speech(event.get("audio_start_ms"))
                        await handle_barge_in()
                        continue

                    if event_type == "input_audio_buffer.speech_stopped":
                        session.stop_user_speech(event.get("audio_end_ms"))
                        outgoing_audio_enabled = True
                        continue

                    if event_type == "input_audio_buffer.committed":
                        if event.get("item_id"):
                            session.set_user_item(event["item_id"])
                        continue

                    if event_type == "conversation.item.input_audio_transcription.completed":
                        session.finalize_user_transcript(
                            event.get("transcript", ""),
                            item_id=event.get("item_id"),
                        )
                        outgoing_audio_enabled = True
                        if not use_text_fallback:
                            await request_response(openai_ws)
                        continue

                    if event_type == "response.output_audio_transcript.delta":
                        item_id = event.get("item_id")
                        if item_id in suppressed_agent_items:
                            continue
                        if item_id:
                            session.append_agent_transcript(item_id, event.get("delta", ""))
                        continue

                    if event_type == "response.output_audio.delta":
                        item_id = event.get("item_id")
                        if item_id in suppressed_agent_items:
                            continue
                        delta = event.get("delta")
                        if item_id and delta and outgoing_audio_enabled:
                            session.note_agent_audio_sent(item_id, delta)
                            await websocket.send_json(
                                {
                                    "event": "media",
                                    "speaker": "agent",
                                    "item_id": item_id,
                                    "media": {
                                        "payload": delta,
                                        "timestamp_ms": session.agent_audio_end_ms(),
                                    },
                                }
                            )
                        continue

                    if event_type == "response.output_audio.done":
                        if event.get("item_id") in suppressed_agent_items:
                            continue
                        end_ms = session.agent_audio_end_ms()
                        session.finalize_agent(interrupted=False)
                        await websocket.send_json(
                            {
                                "event": "agent_done",
                                "item_id": event.get("item_id"),
                                "end_ms": end_ms,
                            }
                        )
                        continue
            except Exception as exc:
                if not stop_event.is_set():
                    print(f"Error processing Realtime events: {exc}")
                    stop_event.set()

        await asyncio.gather(receive_from_client(), send_to_client())
