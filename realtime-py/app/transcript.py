import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.config import settings


def now_ms() -> int:
    return int(time.monotonic() * 1000)


def generate_call_id(prefix: str = "call") -> str:
    now = datetime.now(timezone.utc)
    return f"{prefix}-{now.strftime('%Y%m%dT%H%M%S')}{now.microsecond // 1000:03d}Z"


def clean_text(text: str) -> str:
    return " ".join(text.strip().split())


def mark_interrupted_text(text: str) -> str:
    text = text.rstrip()
    if not text or text.endswith(("-", "—")):
        return text
    return f"{text.rstrip('.!?')}-"


@dataclass
class Utterance:
    speaker: str
    text: str
    start_ms: int
    end_ms: int
    interrupted: Optional[bool] = None
    item_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        value: Dict[str, Any] = {
            "speaker": self.speaker,
            "text": self.text,
            "start_ms": self.start_ms,
            "end_ms": self.end_ms,
        }
        if self.item_id is not None:
            value["item_id"] = self.item_id
        if self.interrupted is not None:
            value["interrupted"] = self.interrupted
        return value


@dataclass
class LatencyEvent:
    turn_index: int
    user_speech_end_clock_ms: Optional[int] = None
    stt_first_final_ms: Optional[int] = None
    llm_first_token_ms: Optional[int] = None
    tts_first_byte_ms: Optional[int] = None

    def to_dict(self) -> Dict[str, Optional[int]]:
        return {
            "turn_index": self.turn_index,
            "user_speech_end_clock_ms": self.user_speech_end_clock_ms,
            "stt_first_final_ms": self.stt_first_final_ms,
            "llm_first_token_ms": self.llm_first_token_ms,
            "tts_first_byte_ms": self.tts_first_byte_ms,
        }


@dataclass
class LatencyTracker:
    events: List[LatencyEvent] = field(default_factory=list)
    active_event: Optional[LatencyEvent] = None
    voice_to_voice_ms: Optional[int] = None

    def set_voice_to_voice(self, voice_to_voice_ms: int) -> None:
        self.voice_to_voice_ms = voice_to_voice_ms
        print(f"LATENCY voice_to_voice_ms={voice_to_voice_ms}")

    def mark_user_speech_end(self) -> LatencyEvent:
        self.active_event = LatencyEvent(
            turn_index=len(self.events) + 1,
            user_speech_end_clock_ms=now_ms(),
        )
        self.events.append(self.active_event)
        print(
            "LATENCY "
            f"turn_index={self.active_event.turn_index} "
            f"user_end_clock_ms={self.active_event.user_speech_end_clock_ms}"
        )
        return self.active_event

    def mark_stt_final(self, event: Optional[LatencyEvent] = None) -> None:
        event = event or self.active_event
        if event and event.stt_first_final_ms is None and event.user_speech_end_clock_ms is not None:
            event_clock_ms = now_ms()
            event.stt_first_final_ms = event_clock_ms - event.user_speech_end_clock_ms
            print(
                "LATENCY "
                f"turn_index={event.turn_index} "
                f"stt_final_clock_ms={event_clock_ms} "
                f"stt_first_final_ms={event.stt_first_final_ms}"
            )

    def mark_llm_first_token(self, event: Optional[LatencyEvent] = None) -> None:
        event = event or self.active_event
        if event and event.llm_first_token_ms is None and event.user_speech_end_clock_ms is not None:
            event_clock_ms = now_ms()
            event.llm_first_token_ms = event_clock_ms - event.user_speech_end_clock_ms
            print(
                "LATENCY "
                f"turn_index={event.turn_index} "
                f"llm_first_token_clock_ms={event_clock_ms} "
                f"llm_first_token_ms={event.llm_first_token_ms}"
            )

    def mark_tts_first_byte(self, event: Optional[LatencyEvent] = None) -> None:
        event = event or self.active_event
        if event and event.tts_first_byte_ms is None and event.user_speech_end_clock_ms is not None:
            event_clock_ms = now_ms()
            event.tts_first_byte_ms = event_clock_ms - event.user_speech_end_clock_ms
            print(
                "LATENCY "
                f"turn_index={event.turn_index} "
                f"tts_first_byte_clock_ms={event_clock_ms} "
                f"tts_first_byte_ms={event.tts_first_byte_ms}"
            )

    def to_dict(self) -> Dict[str, Optional[int]]:
        if not self.events:
            return {
                "stt_first_final_ms": None,
                "llm_first_token_ms": None,
                "tts_first_byte_ms": None,
                "voice_to_voice_ms": self.voice_to_voice_ms,
            }

        first_event = self.events[0]
        return {
            "stt_first_final_ms": first_event.stt_first_final_ms,
            "llm_first_token_ms": first_event.llm_first_token_ms,
            "tts_first_byte_ms": first_event.tts_first_byte_ms,
            "voice_to_voice_ms": self.voice_to_voice_ms,
        }

    def events_to_list(self) -> List[Dict[str, Optional[int]]]:
        return [event.to_dict() for event in self.events]


@dataclass
class CallSession:
    call_id: str
    started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    latest_client_timestamp_ms: int = 0
    stream_id: Optional[str] = None
    latency: LatencyTracker = field(default_factory=LatencyTracker)
    turn_store: Any = field(init=False)

    def __post_init__(self) -> None:
        from app.turns import TurnStore

        self.turn_store = TurnStore(latency=self.latency)

    def update_client_timestamp(self, timestamp_ms: int) -> None:
        self.latest_client_timestamp_ms = max(self.latest_client_timestamp_ms, timestamp_ms)

    def start_user_speech(self, start_ms: Optional[int] = None) -> None:
        self.turn_store.start_user_turn(start_ms if start_ms is not None else self.latest_client_timestamp_ms)

    def stop_user_speech(self, end_ms: Optional[int] = None) -> None:
        self.turn_store.finish_user_turn(end_ms if end_ms is not None else self.latest_client_timestamp_ms)

    def set_user_item(self, item_id: str) -> None:
        self.turn_store.attach_user_item(item_id)

    def finalize_user_transcript(self, text: str, item_id: Optional[str] = None) -> None:
        self.turn_store.finalize_user_transcript(text, item_id=item_id)

    def append_agent_transcript(self, item_id: str, delta: str) -> None:
        self.turn_store.append_agent_transcript(item_id, delta, self.latest_client_timestamp_ms)

    def note_agent_audio_sent(self, item_id: str, audio_base64: str) -> None:
        self.turn_store.note_agent_audio_sent(item_id, audio_base64, self.latest_client_timestamp_ms)

    def agent_audio_end_ms(self) -> int:
        return self.turn_store.agent_audio_end_ms(self.latest_client_timestamp_ms)

    def current_agent_audio_offset_ms(self) -> int:
        return self.turn_store.active_agent_audio_ms()

    def active_agent_item_id(self) -> Optional[str]:
        return self.turn_store.active_agent_item_id()

    def finalize_agent(self, interrupted: bool) -> None:
        self.turn_store.finalize_agent(interrupted=interrupted)

    def set_voice_to_voice(self, voice_to_voice_ms: int) -> None:
        self.latency.set_voice_to_voice(voice_to_voice_ms)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "call_id": self.call_id,
            "started_at": self.started_at,
            "model": settings.openai_model,
            "audio_format": "pcm16_24000_mono",
            "utterances": [utterance.to_dict() for utterance in self.turn_store.to_utterances()],
            "metrics": self.latency.to_dict(),
            "latency_events": self.latency.events_to_list(),
        }


class TranscriptStore:
    def __init__(self, data_dir: Path = settings.data_dir) -> None:
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def path_for(self, call_id: str) -> Path:
        return self.data_dir / f"{call_id}.json"

    def save(self, session: CallSession) -> Path:
        path = self.path_for(session.call_id)
        path.write_text(json.dumps(session.to_dict(), indent=2) + "\n", encoding="utf-8")
        return path

    def list_ids(self) -> list[str]:
        return [p.stem for p in sorted(self.data_dir.glob("*.json"))]

    def load(self, call_id: str) -> Dict[str, Any]:
        return json.loads(self.path_for(call_id).read_text(encoding="utf-8"))
