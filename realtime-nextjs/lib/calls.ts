const SERVER_URL = process.env.SERVER_URL ?? 'http://localhost:5050';

export interface Utterance {
	speaker: 'user' | 'agent';
	text: string;
	start_ms: number;
	end_ms: number;
	item_id?: string;
	interrupted?: boolean;
}

export interface LatencyEvent {
	turn_index: number;
	user_speech_end_clock_ms: number | null;
	stt_first_final_ms: number | null;
	llm_first_token_ms: number | null;
	tts_first_byte_ms: number | null;
	voice_to_voice_ms: number | null;
}

export interface CallMetrics {
	stt_first_final_ms: number | null;
	llm_first_token_ms: number | null;
	tts_first_byte_ms: number | null;
	voice_to_voice_ms: number | null;
}

export interface Call {
	call_id: string;
	started_at: string;
	model?: string;
	audio_format: string;
	utterances: Utterance[];
	metrics: CallMetrics;
	latency_events: LatencyEvent[];
}

export function parseCallIdDate(callId: string): Date | null {
	const m = callId.match(/(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})(\d{3})Z/);
	if (!m) return null;
	return new Date(`${m[1]}-${m[2]}-${m[3]}T${m[4]}:${m[5]}:${m[6]}.${m[7]}Z`);
}

export function formatCallId(callId: string): string {
	const date = parseCallIdDate(callId);
	if (!date) return callId;
	return date.toLocaleString('en-US', {
		month: 'short',
		day: 'numeric',
		year: 'numeric',
		hour: 'numeric',
		minute: '2-digit',
		hour12: true
	});
}

export async function listCallIds(): Promise<string[]> {
	const res = await fetch(`${SERVER_URL}/calls`, { cache: 'no-store' });
	if (!res.ok) return [];
	const data = await res.json();
	return data.calls as string[];
}

export async function getCall(id: string): Promise<Call | null> {
	const res = await fetch(`${SERVER_URL}/calls/${encodeURIComponent(id)}`, {
		cache: 'no-store'
	});
	if (res.status === 404) return null;
	if (!res.ok) throw new Error(`Python API error: ${res.status}`);
	return res.json() as Promise<Call>;
}

export async function runDemoCall(): Promise<string> {
	const res = await fetch(`${SERVER_URL}/demo-call`, {
		method: 'POST',
		cache: 'no-store'
	});
	if (!res.ok) throw new Error(`Python API error: ${res.status}`);
	const data = await res.json();
	return data.call_id as string;
}
