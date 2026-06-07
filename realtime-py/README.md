# Realtime Voice Pipeline Demo - Python Service

Python implementation of the voice-loop portion of the take-home. It replaces real telephony with a local fake caller that streams two WAV files over WebSocket, and uses OpenAI Realtime as the single speech-to-speech provider for STT, LLM, and TTS.

The TypeScript transcript API and React transcript UI are separate next steps.

## What Runs Here

- FastAPI WebSocket service at `/media-stream`
- OpenAI Realtime WebSocket bridge using `gpt-realtime`
- Local fake caller that streams `fixtures/audio_1.wav` and `fixtures/audio_2.wav`
- Barge-in handling with `conversation.item.truncate`
- Aligned JSON transcript persistence under `data/calls/`
- Per-turn latency metrics for STT final, LLM first token, TTS first byte, and voice-to-voice

## Architecture

```text
scripts/fake_call.py
  -> waits for the agent greeting
  -> streams WAV chunks in real time
  -> sends user_turn_start / media / user_turn_end events

app/server.py
  -> accepts fake caller WebSocket
  -> forwards audio frames to OpenAI Realtime
  -> forwards streamed agent audio back to the caller
  -> cuts off agent audio on barge-in

app/transcript.py
  -> tracks user and agent utterances
  -> records call-time offsets in milliseconds
  -> saves only the agent audio/text that was actually played
  -> marks interrupted agent utterances with interrupted=true and a trailing "-"
```

## Project Layout

```text
main.py              # Small service entrypoint
app/server.py        # FastAPI routes and WebSocket orchestration
app/realtime.py      # OpenAI Realtime protocol helpers
app/transcript.py    # Transcript state, interruption handling, latency metrics
app/audio.py         # WAV validation and frame chunking
app/config.py        # Environment config and system prompt
scripts/fake_call.py # Local caller that streams the two WAV files
```

## Real Vs Mocked

Real:

- OpenAI Realtime STT, LLM, and TTS
- Real recorded WAV input files
- WebSocket streaming between the fake caller, Python service, and OpenAI
- Transcript and latency JSON generated from runtime events

Mocked:

- Telephony provider. Twilio/SIP is replaced by `scripts/fake_call.py`.
- Caller timing. The fake caller decides when `audio_1.wav` starts, when `audio_2.wav` barges in, and when the call stops.
- Production endpointing. For deterministic local testing, each WAV boundary is treated as a user turn and committed to OpenAI at `user_turn_end`.

The assignment allows mocked providers. This implementation keeps real speech-to-speech model behavior while mocking telephony so the transcript-alignment behavior is easy to run locally.

## System Prompt

The system prompt is hardcoded in [app/config.py] as `SYSTEM_MESSAGE`.

It enforces the voice-output rules from the assignment:

- plain spoken text only
- no markdown, bullets, emoji, or visual formatting
- one to two sentences per turn
- numbers and acronyms spelled out for speech

The demo persona is a concise KFC phone-order agent so the recorded audio receives domain-relevant responses.

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
```

Set `OPENAI_API_KEY` in `.env`.

## Run The Service

```bash
.venv/bin/python main.py
```

The service starts on `http://localhost:5050`.

## Run The Fake Call

In a second terminal:

```bash
.venv/bin/python scripts/fake_call.py
```

The fake caller streams:

- `fixtures/audio_1.wav`
- `fixtures/audio_2.wav`

By default, the agent greets first like a customer-support call. The fake caller waits for that greeting to finish before streaming `audio_1.wav`.

The second turn waits until the next agent audio chunk is observed, then starts shortly afterward. When the fake caller's local user-start signal arrives during agent output, the service stops forwarding agent audio, sends a truncate event to OpenAI, and records the agent utterance as interrupted.

To skip the initial greeting and start with the caller, run:

```bash
.venv/bin/python scripts/fake_call.py --no-agent-greeting
```

## Transcript Output

After a fake call finishes, inspect:

```bash
data/calls/demo-call-001.json
```

Expected shape:

```json
{
	"call_id": "demo-call-001",
	"started_at": "2026-06-06T00:00:00+00:00",
	"audio_format": "pcm16_24000_mono",
	"utterances": [
		{
			"speaker": "agent",
			"text": "Hi, thanks for calling K F C. How can I help you today?",
			"start_ms": 0,
			"end_ms": 2500,
			"interrupted": false
		},
		{
			"speaker": "user",
			"text": "Hi, I'd like to place an order for a Zinger burger with fries and a Coke, please.",
			"start_ms": 2800,
			"end_ms": 7528
		},
		{
			"speaker": "agent",
			"text": "Sure, I can help-",
			"start_ms": 7520,
			"end_ms": 7770,
			"interrupted": true
		},
		{
			"speaker": "user",
			"text": "Actually, could you make that a Kentucky burger with fries and a Coke?",
			"start_ms": 7628,
			"end_ms": 11804
		}
	],
	"metrics": {
		"stt_first_final_ms": 567,
		"llm_first_token_ms": 1304,
		"tts_first_byte_ms": 1405,
		"voice_to_voice_ms": 1405
	},
	"latency_events": [
		{
			"turn_index": 1,
			"user_speech_end_clock_ms": 10348,
			"stt_first_final_ms": 567,
			"llm_first_token_ms": 1304,
			"tts_first_byte_ms": 1405,
			"voice_to_voice_ms": 1405
		},
		{
			"turn_index": 2,
			"user_speech_end_clock_ms": 16602,
			"stt_first_final_ms": 612,
			"llm_first_token_ms": 1180,
			"tts_first_byte_ms": 1290,
			"voice_to_voice_ms": 1290
		}
	]
}
```

The overlap between the interrupted agent utterance and the second user utterance is intentional. It represents detection/playback latency during barge-in.

## Latency Metrics

Metrics are measured with `time.monotonic()` inside the Python process:

- `stt_first_final_ms`: user turn end to final user transcription
- `llm_first_token_ms`: user turn end to first streamed agent transcript delta
- `tts_first_byte_ms`: user turn end to first streamed agent audio bytes
- `voice_to_voice_ms`: user turn end to first agent audio bytes sent back to the caller

These values are real runtime deltas, not constants. The `latency_events` array records each user turn. The top-level `metrics` object mirrors the first user turn for quick reporting.

The implementation streams audio and response chunks as they arrive. It does not wait for `response.done` before forwarding agent audio.

## Barge-In Behavior

When the second user turn starts while agent audio is active:

- outgoing agent audio is disabled immediately
- the active OpenAI response item is truncated with `conversation.item.truncate`
- the transcript finalizes the agent utterance with `interrupted: true`
- only played/forwarded agent text is saved
- a trailing `-` marks that the utterance was cut off

If the WebSocket disconnects mid-call, the server finalizes any active agent utterance as interrupted and saves the partial transcript.

## Audio Format

The fixtures are real spoken WAV files:

- PCM 16-bit
- 24 kHz
- mono

This format matches the OpenAI Realtime audio configuration used by the service and keeps local chunking simple.
