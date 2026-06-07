import base64
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from app.config import settings


@dataclass(frozen=True)
class AudioChunk:
    payload: str
    timestamp_ms: int
    duration_ms: int
    byte_count: int


@dataclass(frozen=True)
class WavAudio:
    path: Path
    frames: bytes
    frame_count: int
    sample_rate: int
    channels: int
    sample_width: int

    @property
    def duration_ms(self) -> int:
        return round(self.frame_count * 1000 / self.sample_rate)

    def chunks(self, start_ms: int, chunk_ms: int = settings.chunk_ms) -> Iterator[AudioChunk]:
        bytes_per_frame = self.channels * self.sample_width
        frames_per_chunk = max(1, round(self.sample_rate * chunk_ms / 1000))
        bytes_per_chunk = frames_per_chunk * bytes_per_frame

        timestamp_ms = start_ms
        for offset in range(0, len(self.frames), bytes_per_chunk):
            chunk = self.frames[offset : offset + bytes_per_chunk]
            frame_count = len(chunk) // bytes_per_frame
            duration_ms = round(frame_count * 1000 / self.sample_rate)
            yield AudioChunk(
                payload=base64.b64encode(chunk).decode("ascii"),
                timestamp_ms=timestamp_ms,
                duration_ms=duration_ms,
                byte_count=len(chunk),
            )
            timestamp_ms += duration_ms


def load_wav(path: Path) -> WavAudio:
    with wave.open(str(path), "rb") as wav_file:
        sample_rate = wav_file.getframerate()
        channels = wav_file.getnchannels()
        sample_width = wav_file.getsampwidth()
        frame_count = wav_file.getnframes()
        frames = wav_file.readframes(frame_count)

    if sample_rate != settings.audio_sample_rate:
        raise ValueError(f"{path} must be {settings.audio_sample_rate} Hz, got {sample_rate} Hz")
    if channels != settings.audio_channels:
        raise ValueError(f"{path} must be mono, got {channels} channels")
    if sample_width != settings.audio_sample_width:
        raise ValueError(f"{path} must be 16-bit PCM, got {sample_width * 8}-bit samples")

    return WavAudio(
        path=path,
        frames=frames,
        frame_count=frame_count,
        sample_rate=sample_rate,
        channels=channels,
        sample_width=sample_width,
    )


def pcm_duration_ms(byte_count: int) -> int:
    bytes_per_second = settings.audio_sample_rate * settings.audio_channels * settings.audio_sample_width
    return round(byte_count * 1000 / bytes_per_second)
