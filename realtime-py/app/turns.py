import base64
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from app.audio import pcm_duration_ms
from app.transcript import LatencyEvent, LatencyTracker, Utterance, clean_text, mark_interrupted_text


@dataclass
class Turn:
    turn_id: int
    user_start_ms: Optional[int] = None
    user_end_ms: Optional[int] = None
    user_item_id: Optional[str] = None
    user_transcript: str = ""
    latency_event: Optional[LatencyEvent] = None

    agent_item_id: Optional[str] = None
    agent_start_ms: Optional[int] = None
    agent_transcript: str = ""
    agent_played_text: str = ""
    agent_audio_ms: int = 0
    agent_interrupted: Optional[bool] = None


@dataclass
class TurnStore:
    latency: LatencyTracker
    turns: List[Turn] = field(default_factory=list)
    user_item_to_turn: Dict[str, Turn] = field(default_factory=dict)
    agent_item_to_turn: Dict[str, Turn] = field(default_factory=dict)
    pending_user_turns: List[Turn] = field(default_factory=list)
    awaiting_agent_turns: List[Turn] = field(default_factory=list)
    active_user: Optional[Turn] = None
    active_agent: Optional[Turn] = None

    def start_user_turn(self, timestamp_ms: int) -> None:
        if self.active_user:
            return

        turn = Turn(turn_id=len(self.turns) + 1, user_start_ms=timestamp_ms)
        self.turns.append(turn)
        self.active_user = turn

    def finish_user_turn(self, timestamp_ms: int) -> None:
        turn = self.active_user
        if not turn or turn.user_end_ms is not None:
            return

        turn.user_end_ms = timestamp_ms
        turn.latency_event = self.latency.mark_user_speech_end()
        self.pending_user_turns.append(turn)
        self.awaiting_agent_turns.append(turn)
        self.active_user = None

    def attach_user_item(self, item_id: str) -> None:
        if item_id in self.user_item_to_turn:
            return

        turn = self.pending_user_turns[0] if self.pending_user_turns else self.active_user
        if not turn:
            return

        turn.user_item_id = item_id
        self.user_item_to_turn[item_id] = turn

    def finalize_user_transcript(self, text: str, item_id: Optional[str] = None) -> None:
        turn = self.user_item_to_turn.get(item_id) if item_id else self.first_pending_user()
        if not turn and item_id:
            turn = self.first_pending_user()
        if not turn:
            turn = self.active_user
        if not turn:
            return

        if item_id and not turn.user_item_id:
            turn.user_item_id = item_id
            self.user_item_to_turn[item_id] = turn

        self.remove_pending_user(turn)
        self.latency.mark_stt_final(turn.latency_event)
        turn.user_transcript = clean_text(text or "")

    def attach_agent_item(self, item_id: str, timestamp_ms: int) -> Turn:
        mapped_turn = self.agent_item_to_turn.get(item_id)
        if mapped_turn:
            return mapped_turn

        turn = self.awaiting_agent_turns[0] if self.awaiting_agent_turns else self.active_user_or_agent_or_last()
        if not turn:
            turn = Turn(turn_id=len(self.turns) + 1)
            self.turns.append(turn)

        turn.agent_item_id = item_id
        turn.agent_start_ms = timestamp_ms
        self.agent_item_to_turn[item_id] = turn
        self.active_agent = turn
        self.remove_awaiting_agent(turn)
        return turn

    def append_agent_transcript(self, item_id: str, delta: str, timestamp_ms: int) -> None:
        turn = self.attach_agent_item(item_id, timestamp_ms)
        self.latency.mark_llm_first_token(turn.latency_event)
        turn.agent_transcript += delta

    def note_agent_audio_sent(self, item_id: str, audio_base64: str, timestamp_ms: int) -> None:
        turn = self.attach_agent_item(item_id, timestamp_ms)
        self.latency.mark_tts_first_byte(turn.latency_event)
        audio_bytes = base64.b64decode(audio_base64)
        turn.agent_audio_ms += pcm_duration_ms(len(audio_bytes))
        turn.agent_played_text = clean_text(turn.agent_transcript)

    def finalize_agent(self, interrupted: bool) -> None:
        turn = self.active_agent
        if not turn:
            return
        turn.agent_interrupted = interrupted
        self.active_agent = None

    def active_agent_item_id(self) -> Optional[str]:
        return self.active_agent.agent_item_id if self.active_agent else None

    def active_agent_audio_ms(self) -> int:
        return self.active_agent.agent_audio_ms if self.active_agent else 0

    def agent_audio_end_ms(self, fallback_ms: int) -> int:
        if not self.active_agent or self.active_agent.agent_start_ms is None:
            return fallback_ms
        return self.active_agent.agent_start_ms + self.active_agent.agent_audio_ms

    def to_utterances(self) -> List[Utterance]:
        utterances: List[Utterance] = []
        for turn in self.turns:
            user_text = clean_text(turn.user_transcript)
            if user_text:
                user_start_ms = turn.user_start_ms if turn.user_start_ms is not None else 0
                user_end_ms = turn.user_end_ms if turn.user_end_ms is not None else user_start_ms
                utterances.append(
                    Utterance(
                        speaker="user",
                        text=user_text,
                        start_ms=user_start_ms,
                        end_ms=max(user_start_ms, user_end_ms),
                        item_id=turn.user_item_id,
                    )
                )

            agent_text = clean_text(turn.agent_played_text or turn.agent_transcript)
            if agent_text and turn.agent_start_ms is not None:
                interrupted = bool(turn.agent_interrupted)
                if interrupted:
                    agent_text = mark_interrupted_text(agent_text)
                utterances.append(
                    Utterance(
                        speaker="agent",
                        text=agent_text,
                        start_ms=turn.agent_start_ms,
                        end_ms=max(turn.agent_start_ms, turn.agent_start_ms + turn.agent_audio_ms),
                        interrupted=interrupted,
                        item_id=turn.agent_item_id,
                    )
                )
        return utterances

    def first_pending_user(self) -> Optional[Turn]:
        return self.pending_user_turns[0] if self.pending_user_turns else None

    def active_user_or_agent_or_last(self) -> Optional[Turn]:
        return self.active_user or self.active_agent or (self.turns[-1] if self.turns else None)

    def remove_pending_user(self, turn: Turn) -> None:
        if turn in self.pending_user_turns:
            self.pending_user_turns.remove(turn)

    def remove_awaiting_agent(self, turn: Turn) -> None:
        if turn in self.awaiting_agent_turns:
            self.awaiting_agent_turns.remove(turn)
