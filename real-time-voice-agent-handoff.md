# Handoff: Real-Time Voice Agent — Full Stack

## Context

Workspace: `/Users/affan/Desktop/Work/real-time-voice-agent`

This is a take-home assignment (SF-ENG-0042) to build a single-call demo of a Retell/Vapi/Bland-style voice agent. The Python service is complete. The Next.js frontend is functionally complete. The root README now documents the architecture, latency, audio format, barge-in behavior, run commands, and known disconnect behavior.

---

## What Was Built This Session

### Python (`realtime-py/`)
- Added `generate_call_id()` to `app/transcript.py` — produces IDs like `call-20260607T143022123Z`
- Added `list_ids()` to `TranscriptStore` in `app/transcript.py`
- Added two REST endpoints to `app/server.py`:
  - `GET /calls` — returns `{ calls: [...] }`
  - `GET /calls/{call_id}` — returns full transcript JSON or 404
- Added disconnect test: `realtime-py/tests/test_disconnect.py` — 3 tests covering mid-call disconnect, pre-start disconnect, and between-turn disconnect. All pass.

### Next.js (`realtime-nextjs/`)
- `lib/calls.ts` — types, fetch helpers (`listCallIds`, `getCall`), and formatters (`parseCallIdDate`, `formatCallId`) for timestamp-based call IDs. Default `SERVER_URL` is `http://localhost:5050`.
- `app/api/calls/route.ts` — proxies to Python `GET /calls`
- `app/api/calls/[id]/route.ts` — proxies to Python `GET /calls/{call_id}`
- `app/page.tsx` — client component, fetches call list on mount, two-panel layout (sidebar + transcript)
- `components/call-list.tsx` — sidebar, formats timestamp call IDs into human-readable labels
- `components/transcript-view.tsx` — fetches transcript on selection, renders bubbles + latency strip
- `components/utterance-bubble.tsx` — agent left / user right, amber border + `interrupted` badge on cut turns

---

## Architecture

- **Python** owns: WebSocket bridge to OpenAI Realtime, transcript state + interruption handling, file persistence, REST read endpoints
- **Next.js** owns: proxy API routes, UI
- **No shared volume** — Next.js calls Python over HTTP via `SERVER_URL` env var (Docker: `http://realtime-py:5050`)
- Python server runs on **port 5050** (set in `app/config.py`)

---

## Current State

### What works
- Full voice pipeline: fake caller → Python → OpenAI Realtime → back
- Barge-in with transcript truncation and `interrupted: true` flag
- REST endpoints verified manually
- Next.js UI renders call list, transcript bubbles, latency strip, interrupted markers
- Timestamp-based call IDs formatted correctly in UI
- Disconnect handling tested and verified (unit tests)

### Git state
`realtime-py` appears to be tracked as normal files, not as a submodule. `realtime-nextjs/` is currently untracked and needs to be added before committing.

### What's left
1. Add `realtime-nextjs/` to git before committing.
2. Optional: add Docker for a cleaner demo.
3. Optional: put verbose OpenAI event logging behind an env flag for a quieter final run.

---

## Key Files

| File | Purpose |
|------|---------|
| `realtime-py/app/server.py` | FastAPI app — WebSocket bridge + REST endpoints |
| `realtime-py/app/transcript.py` | CallSession, TranscriptStore, LatencyTracker |
| `realtime-py/app/config.py` | Settings + SYSTEM_MESSAGE (voice output rules) |
| `realtime-py/scripts/fake_call.py` | Fake caller for local testing |
| `realtime-py/tests/test_disconnect.py` | Disconnect handling tests |
| `realtime-nextjs/lib/calls.ts` | Types + fetch helpers + call ID formatter |
| `realtime-nextjs/app/page.tsx` | Main page — two-panel shell |
| `realtime-nextjs/components/` | call-list, transcript-view, utterance-bubble |

---

## Notable Decisions

- OpenAI Realtime API used as single-provider STT+LLM+TTS shortcut (no Deepgram/ElevenLabs)
- PCM 16-bit 24kHz mono — matches OpenAI Realtime's native format, avoids transcoding
- Barge-in overlap intentionally kept in transcript (realistic detection latency)
- Call IDs are timestamp-based (`call-YYYYMMDDTHHMMSSXXXZ`) — UI parses and formats them
- No auth, no multi-tenancy — out of scope per spec

---

## How to Run

```bash
# Python
cd realtime-py && .venv/bin/uvicorn app.server:app --host 0.0.0.0 --port 5050 --reload

# Fake call (separate terminal)
cd realtime-py && .venv/bin/python scripts/fake_call.py

# Next.js
cd realtime-nextjs && npm run dev
```

To test disconnect: start both, wait for agent to finish at least one turn, then `Ctrl+C` the fake caller. Check `realtime-py/data/calls/<call-id>.json` for `"interrupted": true` on the last agent utterance.

---

## Suggested Skills

- `grill-with-docs` — verify README content against the spec PDF before submitting
- `grill-me` — prep for the architecture questions in the evaluation (section 04 of the spec)
- `improve-codebase-architecture` — if you want to tighten module boundaries before submission

---

## Redactions

No secrets included. API keys remain in local `.env` files.
