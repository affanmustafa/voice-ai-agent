# Realtime Voice Agent UI

Next.js frontend and thin TypeScript API layer for the voice-agent transcript demo.

## What It Does

- `GET /api/calls` proxies to the Python service `GET /calls`
- `GET /api/calls/[id]` proxies to the Python service `GET /calls/{call_id}`
- `POST /api/demo-call` proxies to the Python service `POST /demo-call`
- The `Run demo` button triggers the WAV fixture call from the browser
- The main page lists saved calls and renders the selected transcript
- Agent and user turns are shown as separate chat bubbles
- Interrupted agent turns show a visible `interrupted` badge
- First-turn latency metrics are displayed below the transcript

## Run

Start the Python service first:

```bash
cd ../realtime-py
.venv/bin/python main.py
```

Then start Next.js:

```bash
cd ../realtime-nextjs
npm install
npm run dev
```

Open `http://localhost:3000`.

Click `Run demo` in the sidebar to start the fixture call. The request returns after the Python service finishes the three prerecorded WAV turns, saves the transcript JSON, and sends back the new `call_id`. The UI then refreshes and opens that call.

The default Python URL is `http://localhost:5050`. Override it with:

```bash
SERVER_URL=http://localhost:5050 npm run dev
```

## Project Layout

```text
app/api/calls/route.ts       # GET /api/calls proxy
app/api/calls/[id]/route.ts  # GET /api/calls/{id} proxy
app/api/demo-call/route.ts   # POST /api/demo-call proxy
app/page.tsx                 # transcript viewer shell
components/call-list.tsx     # saved call list
components/transcript-view.tsx
components/utterance-bubble.tsx
lib/calls.ts                 # transcript types, fetch helpers, call ID formatting
```

## Checks

```bash
npm run lint
npm run build
```
