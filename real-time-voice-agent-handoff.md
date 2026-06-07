# Handoff: Real-Time Voice Agent Python Service

## Context

Workspace: `/Users/affan/Desktop/Work/real-time-voice-agent`

Current focus was the Python service inside:

`/Users/affan/Desktop/Work/real-time-voice-agent/speech-assistant-openai-realtime-api-python`

The Python part of the take-home is functionally complete and verified locally. The next likely phase is the TypeScript API and React UI, but this handoff is scoped to the current Python implementation state.

## What Was Built

- FastAPI service entrypoint in `main.py`
- OpenAI Realtime bridge in `app/server.py`
- Transcript state, interruption handling, and persistence in `app/transcript.py`
- WAV validation and 20 ms chunking in `app/audio.py`
- Environment and prompt config in `app/config.py`
- Fake local caller in `scripts/fake_call.py`
- Real recorded audio fixtures:
  - `fixtures/audio_1.wav`
  - `fixtures/audio_2.wav`
- Tests:
  - `tests/test_audio.py`
  - `tests/test_transcript.py`

## Current Behavior

- The service accepts a local fake caller over WebSocket at `/media-stream`
- It forwards streamed PCM audio to OpenAI Realtime
- It streams OpenAI audio back to the fake caller
- It supports agent greeting first
- It handles barge-in by truncating the active OpenAI response and marking the transcript entry interrupted
- It persists aligned call transcripts to `data/calls/{call_id}.json`
- It records per-turn latency metrics and per-turn latency events

## Important Files

- [PLAN.md](/Users/affan/Desktop/Work/real-time-voice-agent/PLAN.md)
- [Readme.md](/Users/affan/Desktop/Work/real-time-voice-agent/speech-assistant-openai-realtime-api-python/Readme.md)
- [app/server.py](/Users/affan/Desktop/Work/real-time-voice-agent/speech-assistant-openai-realtime-api-python/app/server.py)
- [app/transcript.py](/Users/affan/Desktop/Work/real-time-voice-agent/speech-assistant-openai-realtime-api-python/app/transcript.py)
- [app/realtime.py](/Users/affan/Desktop/Work/real-time-voice-agent/speech-assistant-openai-realtime-api-python/app/realtime.py)
- [scripts/fake_call.py](/Users/affan/Desktop/Work/real-time-voice-agent/speech-assistant-openai-realtime-api-python/scripts/fake_call.py)

## Verified State

- Python tests pass:

```bash
cd speech-assistant-openai-realtime-api-python && .venv/bin/python -m pytest -q
```

- The live fake-call flow was run successfully with real audio fixtures and OpenAI Realtime
- Transcript JSON now includes:
  - `utterances`
  - `metrics`
  - `latency_events`
- Interrupted agent turns are saved with truncated text plus a trailing `-`

## Notable Decisions

- The fake caller is the telephony mock. OpenAI Realtime is real.
- Audio fixtures are real spoken WAV files, not synthetic text-to-speech.
- Runtime audio format is PCM 16-bit, 24 kHz, mono WAV locally, with base64 PCM frames over WebSocket.
- The implementation intentionally keeps barge-in overlap in the transcript to reflect real detection/playback latency.

## Gaps / Follow-Up

- `PLAN.md` is stale in places and still reflects the original scaffold layout (`pyservice/*`) and older event naming. It should be updated if you want the checklist to match the implemented code.
- The next product phase is not in the Python repo anymore; it is the TypeScript API + React UI from the assignment.

## Suggested Skills

- `grill-with-docs` if you want to reconcile the remaining plan/docs language with the implemented behavior before moving on
- `improve-codebase-architecture` if you want to clean up the Python module boundaries or reduce coupling before the next phase
- `openai-docs` if you need to validate any OpenAI Realtime API details before building the next stage

## Redactions

- No secrets were copied into this handoff.
- Any API key values remain in local environment files and are not included here.
