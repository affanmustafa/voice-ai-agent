# Real-Time Voice Agent Demo

## Stack

- `realtime-py/`: FastAPI service, fake WAV caller, OpenAI Realtime bridge, transcript persistence
- `realtime-nextjs/`: Next.js app, API proxy routes, transcript UI
- Storage: JSON files under `realtime-py/data/calls/`

## Architecture

```text
realtime-py/scripts/fake_call.py
  -> streams audio_1.wav and audio_2.wav as timed 20 ms PCM frames
  -> sends user_turn_start / media / user_turn_end events

realtime-py/app/server.py
  -> accepts the fake caller WebSocket at /media-stream
  -> forwards audio frames to OpenAI Realtime
  -> streams agent audio frames back to the caller
  -> handles barge-in and writes aligned transcripts
  -> exposes GET /calls and GET /calls/{call_id}

realtime-nextjs/
  -> proxies GET /api/calls and GET /api/calls/[id] to Python
  -> renders the transcript as chat bubbles with timings and interruption markers
```

The Python / TypeScript split is deliberate. Python owns the realtime audio loop and transcript alignment because that is the timing-sensitive part. Next.js owns the read-only transcript API proxy and UI because the frontend only needs saved call records, not direct audio-stream access.

## Real Vs Mocked

Real:

- OpenAI Realtime STT, LLM, and TTS
- Recorded WAV input files
- WebSocket streaming from fake caller to Python and from Python to OpenAI
- Runtime transcript and latency values

Mocked:

- Telephony. There is no Twilio/SIP provider; `scripts/fake_call.py` is the caller.
- Caller timing. The fake caller decides when each WAV starts and when the second user turn barges in.
- Production endpointing. Each WAV file boundary is treated as a deterministic user turn.

This implementation uses OpenAI Realtime as the single-provider shortcut instead of a mock STT -> LLM -> TTS chain. The trade-off is less control over internal provider stages, but much more realistic transcription and generated speech while keeping the local architecture small.

## Audio Format

Input fixtures are WAV files containing:

- PCM 16-bit
- 24 kHz
- mono

At runtime the fake caller reads the WAV container, validates the format, slices the raw PCM into 20 ms frames, base64-encodes each frame, and sends those frames over WebSocket. OpenAI Realtime is configured for `audio/pcm` at 24 kHz, so the service does not transcode during the call.

PCM was chosen over mu-law because this demo does not use a telephony provider. Mu-law is common at an 8 kHz phone boundary, but it reduces fidelity and would add unnecessary conversion here. MP3 is also avoided at runtime because it is compressed and would need decoding before streaming.

If this service were connected to a real phone provider or SIP trunk, mu-law would be a reasonable boundary format because many telephony streams use 8 kHz audio. In this demo, telephony is mocked by `fake_call.py`, so PCM is simpler and closer to the WAV fixtures and OpenAI Realtime input format.

## Barge-In

The second WAV starts while the agent is speaking. When the service receives `user_turn_start` during an active agent utterance, it:

- stops forwarding agent audio immediately
- sends `conversation.item.truncate` to OpenAI Realtime with the played audio offset
- sends a `clear` event back to the fake caller
- finalizes only the agent text/audio that was actually played
- writes `interrupted: true` and appends `-` to the cut-off text

The transcript intentionally keeps small overlap between the interrupted agent turn and the next user turn. That mirrors real detection/playback latency.

## Latency

Latency is measured with `time.monotonic()` inside the Python process and saved under both `metrics` and `latency_events`.

- `stt_first_final_ms`: user turn end -> final user transcript event
- `llm_first_token_ms`: user turn end -> first streamed agent transcript delta
- `tts_first_byte_ms`: user turn end -> first streamed agent audio bytes
- `voice_to_voice_ms`: user turn end -> first agent audio bytes sent back to caller

The implementation streams frames as they arrive and does not wait for `response.done` before forwarding audio.

These are honest runtime measurements and are above the 800 ms industry target. The goal here is the streaming architecture and instrumentation, not hitting production-grade latency in a local take-home demo.

## Disconnect Behavior

On a normal `stop` event, Python saves the transcript as complete. If the fake caller WebSocket disconnects mid-call, the server saves the partial transcript and marks any active agent utterance as interrupted. If the OpenAI-side WebSocket fails, the service logs the failure and stops the loop; that path is a known limitation compared with the client-disconnect path.

## Environment

Python reads environment variables from `realtime-py/.env`.

Required:

- `OPENAI_API_KEY`: OpenAI API key used by the Realtime WebSocket connection.

Optional:

- `OPENAI_REALTIME_MODEL`: defaults to `gpt-realtime`
- `HOST`: defaults to `0.0.0.0`
- `PORT`: defaults to `5050`
- `SILENCE_DURATION_MS`: defaults to `700`

Example `realtime-py/.env`:

```bash
OPENAI_API_KEY=your_api_key
OPENAI_REALTIME_MODEL=gpt-realtime
HOST=127.0.0.1
PORT=5050
```

Next.js reads `realtime-nextjs/.env`.

Required when Python is not running at the default URL:

- `SERVER_URL`: base URL for the Python API. Defaults to `http://localhost:5050`.

Example `realtime-nextjs/.env`:

```bash
SERVER_URL=http://localhost:5050
```

## Run

Python service:

```bash
cd realtime-py
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
# set OPENAI_API_KEY in .env
.venv/bin/python main.py
```

Fake call in another terminal:

```bash
cd realtime-py
.venv/bin/python scripts/fake_call.py
```

Next.js UI:

```bash
cd realtime-nextjs
npm install
npm run dev
```

Open `http://localhost:3000`. The Python service should be running on `http://localhost:5050`. If needed, set `SERVER_URL=http://localhost:5050` for the Next.js process.

## API

Python exposes:

- `GET http://localhost:5050/calls`
- `GET http://localhost:5050/calls/{call_id}`

Next.js proxies:

- `GET http://localhost:3000/api/calls`
- `GET http://localhost:3000/api/calls/{call_id}`

## Transcript Shape

Transcript files are saved as timestamp-based IDs, for example:

```text
realtime-py/data/calls/call-20260607T191735726Z.json
```

Example:

```json
{
	"call_id": "call-20260607T180117475Z",
	"started_at": "2026-06-07T18:01:19.421022+00:00",
	"audio_format": "pcm16_24000_mono",
	"utterances": [
		{
			"speaker": "agent",
			"text": "Hello, thank you for calling KFC! How can I help you today?",
			"start_ms": 0,
			"end_ms": 3650,
			"interrupted": false
		},
		{
			"speaker": "user",
			"text": "Hi, I'd like to place an order for a Zinger burger with fries and a Coke, please.",
			"start_ms": 3950,
			"end_ms": 8678
		},
		{
			"speaker": "agent",
			"text": "Sure, I can help with that-",
			"start_ms": 8670,
			"end_ms": 9420,
			"interrupted": true
		},
		{
			"speaker": "user",
			"text": "Actually, could you make that a Kentucky burger with fries and a Coke?",
			"start_ms": 8878,
			"end_ms": 13054
		},
		{
			"speaker": "agent",
			"text": "Got it, we'll switch that to a Kentucky Burger. Would you like to keep the same drink or change it?",
			"start_ms": 13038,
			"end_ms": 18138,
			"interrupted": false
		}
	],
	"metrics": {
		"stt_first_final_ms": 573,
		"llm_first_token_ms": 1098,
		"tts_first_byte_ms": 1185,
		"voice_to_voice_ms": 1185
	},
	"latency_events": [
		{
			"turn_index": 1,
			"user_speech_end_clock_ms": 19948,
			"stt_first_final_ms": 573,
			"llm_first_token_ms": 1098,
			"tts_first_byte_ms": 1185,
			"voice_to_voice_ms": 1185
		},
		{
			"turn_index": 2,
			"user_speech_end_clock_ms": 25818,
			"stt_first_final_ms": 817,
			"llm_first_token_ms": 1731,
			"tts_first_byte_ms": 1846,
			"voice_to_voice_ms": 1846
		}
	]
}
```
