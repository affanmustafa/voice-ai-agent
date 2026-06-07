import base64
import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.audio import pcm_duration_ms
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

    def to_dict(self) -> Dict[str, Any]:
        value: Dict[str, Any] = {
            "speaker": self.speaker,
            "text": self.text,
            "start_ms": self.start_ms,
            "end_ms": self.end_ms,
        }
        if self.interrupted is not None:
            value["interrupted"] = self.interrupted
        return value


@dataclass
class ActiveAgentUtterance:
    item_id: str
    start_ms: int
    transcript: str = ""
    played_text: str = ""
    played_audio_ms: int = 0
    first_audio_at_ms: Optional[int] = None


@dataclass
class ActiveUserTurn:
    item_id: Optional[str] = None
    start_ms: Optional[int] = None
    end_ms: Optional[int] = None
    fallback_text: Optional[str] = None


@dataclass
class LatencyEvent:
    turn_index: int
    user_speech_end_clock_ms: Optional[int] = None
    stt_first_final_ms: Optional[int] = None
    llm_first_token_ms: Optional[int] = None
    tts_first_byte_ms: Optional[int] = None
    voice_to_voice_ms: Optional[int] = None

    def to_dict(self) -> Dict[str, Optional[int]]:
        return {
            "turn_index": self.turn_index,
            "user_speech_end_clock_ms": self.user_speech_end_clock_ms,
            "stt_first_final_ms": self.stt_first_final_ms,
            "llm_first_token_ms": self.llm_first_token_ms,
            "tts_first_byte_ms": self.tts_first_byte_ms,
            "voice_to_voice_ms": self.voice_to_voice_ms,
        }


@dataclass
class LatencyTracker:
    events: List[LatencyEvent] = field(default_factory=list)
    active_event: Optional[LatencyEvent] = None

    def mark_user_speech_end(self) -> None:
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

    def mark_stt_final(self) -> None:
        event = self.active_event
        if event and event.stt_first_final_ms is None and event.user_speech_end_clock_ms is not None:
            event_clock_ms = now_ms()
            event.stt_first_final_ms = event_clock_ms - event.user_speech_end_clock_ms
            print(
                "LATENCY "
                f"turn_index={event.turn_index} "
                f"stt_final_clock_ms={event_clock_ms} "
                f"stt_first_final_ms={event.stt_first_final_ms}"
            )

    def mark_llm_first_token(self) -> None:
        event = self.active_event
        if event and event.llm_first_token_ms is None and event.user_speech_end_clock_ms is not None:
            event_clock_ms = now_ms()
            event.llm_first_token_ms = event_clock_ms - event.user_speech_end_clock_ms
            print(
                "LATENCY "
                f"turn_index={event.turn_index} "
                f"llm_first_token_clock_ms={event_clock_ms} "
                f"llm_first_token_ms={event.llm_first_token_ms}"
            )

    def mark_tts_first_byte(self) -> None:
        event = self.active_event
        if event and event.tts_first_byte_ms is None and event.user_speech_end_clock_ms is not None:
            event_clock_ms = now_ms()
            event.tts_first_byte_ms = event_clock_ms - event.user_speech_end_clock_ms
            print(
                "LATENCY "
                f"turn_index={event.turn_index} "
                f"tts_first_byte_clock_ms={event_clock_ms} "
                f"tts_first_byte_ms={event.tts_first_byte_ms}"
            )
        if event and event.voice_to_voice_ms is None and event.user_speech_end_clock_ms is not None:
            event_clock_ms = now_ms()
            event.voice_to_voice_ms = event_clock_ms - event.user_speech_end_clock_ms
            print(
                "LATENCY "
                f"turn_index={event.turn_index} "
                f"voice_to_voice_clock_ms={event_clock_ms} "
                f"voice_to_voice_ms={event.voice_to_voice_ms}"
            )

    def to_dict(self) -> Dict[str, Optional[int]]:
        if not self.events:
            return {
                "stt_first_final_ms": None,
                "llm_first_token_ms": None,
                "tts_first_byte_ms": None,
                "voice_to_voice_ms": None,
            }

        first_event = self.events[0]
        return {
            "stt_first_final_ms": first_event.stt_first_final_ms,
            "llm_first_token_ms": first_event.llm_first_token_ms,
            "tts_first_byte_ms": first_event.tts_first_byte_ms,
            "voice_to_voice_ms": first_event.voice_to_voice_ms,
        }

    def events_to_list(self) -> List[Dict[str, Optional[int]]]:
        return [event.to_dict() for event in self.events]


@dataclass
class CallSession:
    call_id: str
    started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    latest_client_timestamp_ms: int = 0
    stream_id: Optional[str] = None
    utterances: List[Utterance] = field(default_factory=list)
    active_user: ActiveUserTurn = field(default_factory=ActiveUserTurn)
    active_agent: Optional[ActiveAgentUtterance] = None
    latency: LatencyTracker = field(default_factory=LatencyTracker)

    def update_client_timestamp(self, timestamp_ms: int) -> None:
        self.latest_client_timestamp_ms = max(self.latest_client_timestamp_ms, timestamp_ms)

    def start_user_speech(self, start_ms: Optional[int] = None) -> None:
        if self.active_user.start_ms is not None:
            return
        self.active_user = ActiveUserTurn(start_ms=start_ms if start_ms is not None else self.latest_client_timestamp_ms)

    def stop_user_speech(self, end_ms: Optional[int] = None) -> None:
        if self.active_user.end_ms is not None:
            return
        self.active_user.end_ms = end_ms if end_ms is not None else self.latest_client_timestamp_ms
        self.latency.mark_user_speech_end()

    def set_user_fallback_text(self, text: str) -> None:
        self.active_user.fallback_text = text

    def set_user_item(self, item_id: str) -> None:
        self.active_user.item_id = item_id

    def finalize_user_transcript(self, text: str, item_id: Optional[str] = None) -> None:
        self.latency.mark_stt_final()
        if item_id:
            self.active_user.item_id = item_id

        final_text = clean_text(text or self.active_user.fallback_text or "")
        if not final_text:
            return

        start_ms = self.active_user.start_ms
        if start_ms is None:
            start_ms = max(0, self.latest_client_timestamp_ms)
        end_ms = self.active_user.end_ms
        if end_ms is None:
            end_ms = max(start_ms, self.latest_client_timestamp_ms)

        self.utterances.append(
            Utterance(
                speaker="user",
                text=final_text,
                start_ms=start_ms,
                end_ms=max(start_ms, end_ms),
            )
        )
        self.active_user = ActiveUserTurn()

    def maybe_finalize_user_with_fallback(self) -> None:
        if self.active_user.fallback_text:
            self.finalize_user_transcript(self.active_user.fallback_text)

    def start_agent_audio(self, item_id: str) -> None:
        if self.active_agent is None or self.active_agent.item_id != item_id:
            self.active_agent = ActiveAgentUtterance(
                item_id=item_id,
                start_ms=self.latest_client_timestamp_ms,
            )

    def append_agent_transcript(self, item_id: str, delta: str) -> None:
        self.latency.mark_llm_first_token()
        self.start_agent_audio(item_id)
        if self.active_agent:
            self.active_agent.transcript += delta

    def note_agent_audio_sent(self, item_id: str, audio_base64: str) -> None:
        self.latency.mark_tts_first_byte()
        self.start_agent_audio(item_id)
        if not self.active_agent:
            return

        audio_bytes = base64.b64decode(audio_base64)
        self.active_agent.played_audio_ms += pcm_duration_ms(len(audio_bytes))
        self.active_agent.played_text = clean_text(self.active_agent.transcript)
        if self.active_agent.first_audio_at_ms is None:
            self.active_agent.first_audio_at_ms = self.latest_client_timestamp_ms

    def agent_audio_end_ms(self) -> int:
        if not self.active_agent:
            return self.latest_client_timestamp_ms
        return self.active_agent.start_ms + self.active_agent.played_audio_ms

    def current_agent_audio_offset_ms(self) -> int:
        if not self.active_agent:
            return 0
        return max(0, self.active_agent.played_audio_ms)

    def finalize_agent(self, interrupted: bool) -> None:
        if not self.active_agent:
            return

        text = clean_text(self.active_agent.played_text or self.active_agent.transcript)
        if interrupted:
            text = mark_interrupted_text(text)
        if text:
            self.utterances.append(
                Utterance(
                    speaker="agent",
                    text=text,
                    start_ms=self.active_agent.start_ms,
                    end_ms=max(self.active_agent.start_ms, self.agent_audio_end_ms()),
                    interrupted=interrupted,
                )
            )
        self.active_agent = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "call_id": self.call_id,
            "started_at": self.started_at,
            "audio_format": "pcm16_24000_mono",
            "utterances": [utterance.to_dict() for utterance in self.utterances],
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
