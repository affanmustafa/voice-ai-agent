import json
from typing import Any, Dict

from app.config import SYSTEM_MESSAGE, settings


LOG_EVENT_TYPES = {
    "error",
    "response.done",
    "response.cancelled",
    "response.output_audio.done",
    "response.output_audio_transcript.done",
    "conversation.item.input_audio_transcription.completed",
    "input_audio_buffer.committed",
    "session.created",
    "session.updated",
}


def realtime_url() -> str:
    return f"wss://api.openai.com/v1/realtime?model={settings.openai_model}&temperature={settings.temperature}"


def openai_headers() -> Dict[str, str]:
    if not settings.openai_api_key:
        raise RuntimeError("Missing OPENAI_API_KEY. Add it to .env before running the live Realtime demo.")
    return {"Authorization": f"Bearer {settings.openai_api_key}"}


def _sanitize_for_log(value: Any) -> Any:
    if isinstance(value, dict):
        sanitized: Dict[str, Any] = {}
        for key, item in value.items():
            if key in {"audio", "delta", "payload"} and isinstance(item, str) and len(item) > 120:
                sanitized[key] = f"<redacted {len(item)} chars>"
            else:
                sanitized[key] = _sanitize_for_log(item)
        return sanitized
    if isinstance(value, list):
        return [_sanitize_for_log(item) for item in value]
    return value


def session_update_event() -> Dict[str, Any]:
    return {
        "type": "session.update",
        "session": {
            "type": "realtime",
            "model": settings.openai_model,
            "output_modalities": ["audio"],
            "audio": {
                "input": {
                    "format": {
                        "type": "audio/pcm",
                        "rate": settings.audio_sample_rate,
                    },
                    "transcription": {
                        "model": "gpt-realtime-whisper",
                        "language": "en",
                    },
                    "turn_detection": None,
                },
                "output": {
                    "format": {
                        "type": "audio/pcm",
                        "rate": settings.audio_sample_rate,
                    },
                    "voice": settings.voice,
                },
            },
            "instructions": SYSTEM_MESSAGE,
        },
    }


async def initialize_session(openai_ws: Any) -> None:
    event = session_update_event()
    await openai_ws.send(json.dumps(event))


async def send_truncate(openai_ws: Any, item_id: str, audio_end_ms: int) -> None:
    event = {
        "type": "conversation.item.truncate",
        "item_id": item_id,
        "content_index": 0,
        "audio_end_ms": max(0, audio_end_ms),
    }
    await openai_ws.send(json.dumps(event))


async def cancel_response(openai_ws: Any) -> None:
    event = {"type": "response.cancel"}
    await openai_ws.send(json.dumps(event))


async def commit_audio_user_turn(openai_ws: Any) -> None:
    event = {"type": "input_audio_buffer.commit"}
    await openai_ws.send(json.dumps(event))


async def request_response(openai_ws: Any) -> None:
    await openai_ws.send(json.dumps({"type": "response.create"}))
