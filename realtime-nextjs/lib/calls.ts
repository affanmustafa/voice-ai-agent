const SERVER_URL = process.env.SERVER_URL ?? 'http://localhost:5050';

export interface Utterance {
	speaker: 'user' | 'agent';
	text: string;
	start_ms: number;
	end_ms: number;
	interrupted?: boolean;
}

export interface LatencyEvent {
	turn_index: number;
	user_speech_end_clock_ms: number;
	stt_first_final_ms: number;
	llm_first_token_ms: number;
	tts_first_byte_ms: number;
	voice_to_voice_ms: number;
}

export interface CallMetrics {
	stt_first_final_ms: number;
	llm_first_token_ms: number;
	tts_first_byte_ms: number;
	voice_to_voice_ms: number;
}

export interface Call {
	call_id: string;
	started_at: string;
	audio_format: string;
	utterances: Utterance[];
	metrics: CallMetrics;
	latency_events: LatencyEvent[];
}

// Parses call IDs like "call-20260607T143022123Z" → Date.
// Returns null for IDs that don't match (e.g. "demo-call-001").
export function parseCallIdDate(callId: string): Date | null {
	const m = callId.match(/(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})(\d{3})Z/)
	if (!m) return null
	return new Date(`${m[1]}-${m[2]}-${m[3]}T${m[4]}:${m[5]}:${m[6]}.${m[7]}Z`)
}

export function formatCallId(callId: string): string {
	const date = parseCallIdDate(callId)
	if (!date) return callId
	return date.toLocaleString('en-US', {
		month: 'short',
		day: 'numeric',
		year: 'numeric',
		hour: 'numeric',
		minute: '2-digit',
		hour12: true,
	})
}

export async function listCallIds(): Promise<string[]> {
	const res = await fetch(`${SERVER_URL}/calls`);
	if (!res.ok) return [];
	const data = await res.json();
	return data.calls as string[];
}

export async function getCall(id: string): Promise<Call | null> {
	const res = await fetch(`${SERVER_URL}/calls/${encodeURIComponent(id)}`);
	if (res.status === 404) return null;
	if (!res.ok) throw new Error(`Python API error: ${res.status}`);
	return res.json() as Promise<Call>;
}
