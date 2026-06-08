import json
from typing import Any, Dict

from app.config import SYSTEM_MESSAGE, TOOL_CALL_MESSAGE, settings


LOG_EVENT_TYPES = {
    "error",
    "response.done",
    "response.cancelled",
    "response.output_audio.done",
    "response.output_audio_transcript.done",
    "conversation.item.input_audio_transcription.completed",
    "input_audio_buffer.committed",
    "response.function_call_arguments.done",
    "session.created",
    "session.updated",
}


# Function-calling tool: the agent calls this to look up menu items. We run
# top-k RAG over the hardcoded menu and return name/price/in_stock, which the
# model weaves into its spoken reply.
MENU_TOOL = {
    "type": "function",
    "name": "lookup_menu",
    "description": (
        "Look up KFC menu items, their prices, and whether they are in stock. "
        "Call this for any item the customer wants to order or asks about before "
        "confirming it."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The menu item or food the customer mentioned, e.g. 'Zinger burger' or 'chicken piece'.",
            }
        },
        "required": ["query"],
    },
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
    # Tool calling is opt-in via TOOL_CALL_ENABLED. When off, we omit the tool
    # and its prompt rules entirely so the model never pays the tool round-trip.
    instructions = SYSTEM_MESSAGE
    if settings.tool_call_enabled:
        instructions = f"{SYSTEM_MESSAGE}\n\n{TOOL_CALL_MESSAGE}"

    session: Dict[str, Any] = {
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
        "instructions": instructions,
    }
    if settings.tool_call_enabled:
        session["tools"] = [MENU_TOOL]
        session["tool_choice"] = "auto"

    return {"type": "session.update", "session": session}


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


async def send_function_call_output(openai_ws: Any, call_id: str, output: Any) -> None:
    """Return a function-call result to the model as a conversation item."""
    event = {
        "type": "conversation.item.create",
        "item": {
            "type": "function_call_output",
            "call_id": call_id,
            "output": json.dumps(output),
        },
    }
    await openai_ws.send(json.dumps(event))
