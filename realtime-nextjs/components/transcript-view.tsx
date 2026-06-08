'use client';

import { useEffect, useState } from 'react';
import { Separator } from '@/components/ui/separator';
import { UtteranceBubble } from './utterance-bubble';
import { formatCallId } from '@/lib/calls';
import type { Call } from '@/lib/calls';

function LatencyPill({
	label,
	value
}: {
	label: string;
	value: number | null;
}) {
	return (
		<div className="flex flex-col items-center gap-0.5">
			<span className="text-xs text-muted-foreground">{label}</span>
			<span className="text-sm font-medium tabular-nums">
				{value != null ? `${value}ms` : '—'}
			</span>
		</div>
	);
}

// Average a metric across turns, ignoring missing values. Returns a rounded
// integer, or null if no turn had the value.
function average(values: Array<number | null | undefined>): number | null {
	const present = values.filter(
		(v): v is number => typeof v === 'number'
	);
	if (present.length === 0) return null;
	return Math.round(present.reduce((a, b) => a + b, 0) / present.length);
}

export function TranscriptView({ callId }: { callId: string }) {
	const [loadedCall, setLoadedCall] = useState<{
		callId: string;
		call: Call | null;
	} | null>(null);

	useEffect(() => {
		const controller = new AbortController();

		fetch(`/api/calls/${encodeURIComponent(callId)}`, {
			signal: controller.signal
		})
			.then((r) => (r.ok ? r.json() : null))
			.then((data: Call | null) => setLoadedCall({ callId, call: data }))
			.catch((error: unknown) => {
				if (error instanceof DOMException && error.name === 'AbortError') {
					return;
				}
				setLoadedCall({ callId, call: null });
			});

		return () => controller.abort();
	}, [callId]);

	const call = loadedCall?.callId === callId ? loadedCall.call : null;
	const loading = loadedCall?.callId !== callId;

	if (loading) {
		return (
			<div className="flex-1 flex items-center justify-center text-muted-foreground text-sm">
				Loading…
			</div>
		);
	}

	if (!call) {
		return (
			<div className="flex-1 flex items-center justify-center text-muted-foreground text-sm">
				Call not found.
			</div>
		);
	}

	return (
		<div className="flex-1 flex flex-col overflow-hidden">
			<div className="px-6 py-4 border-b">
				<h2 className="text-sm font-semibold">{formatCallId(call.call_id)}</h2>
				<p className="text-xs text-muted-foreground font-mono">
					{call.call_id}
				</p>
				<p className="text-xs text-muted-foreground font-mono">
					Model: {call.model ?? 'Unknown'}
				</p>
			</div>

			<div className="flex-1 overflow-y-auto px-6 py-4 flex flex-col gap-4">
				{call.utterances.map((u, i) => {
					const previous = call.utterances[i - 1];
					const next = call.utterances[i + 1];
					const overlapMs = previous
						? Math.max(0, previous.end_ms - u.start_ms)
						: 0;
					const overlappedByNextMs = next
						? Math.max(0, u.end_ms - next.start_ms)
						: 0;

					const toolCalls =
						u.speaker === 'agent' && previous?.speaker === 'user'
							? (call.tool_calls ?? []).filter(
									(tc) => tc.turn_item_id === previous.item_id
								)
							: [];

					// Per-turn voice-to-voice: each entry maps to a user turn in
					// order, so match it to the Nth agent reply.
					const agentReplyIndex =
						u.speaker === 'agent'
							? call.utterances
									.slice(0, i + 1)
									.filter((x) => x.speaker === 'agent').length - 1
							: -1;
					const v2vTurn =
						u.speaker === 'agent'
							? (call.voice_to_voice_per_turn ?? [])[agentReplyIndex]
							: undefined;

					return (
						<UtteranceBubble
							key={`${u.speaker}-${u.start_ms}-${i}`}
							utterance={u}
							overlapMs={overlapMs}
							previousSpeaker={previous?.speaker}
							overlappedByNextMs={overlappedByNextMs}
							toolCalls={toolCalls}
							voiceToVoiceMs={v2vTurn?.voice_to_voice_ms}
							latencyEvent={
								u.speaker === 'agent'
									? call.latency_events[agentReplyIndex]
									: undefined
							}
						/>
					);
				})}
			</div>

			<div className="border-t px-6 py-4">
				<p className="text-xs text-muted-foreground mb-3 font-medium uppercase tracking-wide">
					Latency (average across turns)
				</p>
				<Separator className="mb-3" />
				<div className="flex gap-6 flex-wrap">
					<LatencyPill
						label="Voice-to-voice"
						value={average(
							(call.voice_to_voice_per_turn ?? []).map(
								(t) => t.voice_to_voice_ms
							)
						)}
					/>
					<LatencyPill
						label="STT"
						value={average(
							call.latency_events.map((e) => e.stt_first_final_ms)
						)}
					/>
					<LatencyPill
						label="LLM first token"
						value={average(
							call.latency_events.map((e) => e.llm_first_token_ms)
						)}
					/>
					<LatencyPill
						label="TTS first byte"
						value={average(
							call.latency_events.map((e) => e.tts_first_byte_ms)
						)}
					/>
				</div>
			</div>
		</div>
	);
}
