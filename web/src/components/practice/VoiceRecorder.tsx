"use client";
import { Mic, Square, Trash2, Upload } from "lucide-react";
import { useRef } from "react";
import { Button } from "@/components/ui/Button";
import { useRecorder } from "@/lib/useRecorder";

/** Record or upload a WAV. Audio goes to the server only when you press Transcribe. */
export function VoiceRecorder({ maxSeconds, maxMb, busy, onAudio }: { maxSeconds: number; maxMb: number; busy?: boolean; onAudio: (file: Blob) => void }) {
  const rec = useRecorder(maxSeconds);
  const picker = useRef<HTMLInputElement>(null);
  const recording = rec.state === "recording";
  return (
    <div className="rounded-[var(--radius-card)] border border-line bg-slate-50 p-4">
      <div className="flex flex-wrap items-center gap-4">
        <button onClick={recording ? rec.stop : rec.start} aria-label={recording ? "Stop recording" : "Start recording"}
          className={`flex size-14 items-center justify-center rounded-full text-white transition-colors duration-150 ${recording ? "bg-bad hover:bg-red-700" : "bg-brand-600 hover:bg-brand-700"}`}>
          {recording ? <Square className="size-5" /> : <Mic className="size-6" />}
        </button>
        <div className="min-w-40 flex-1">
          {recording ? (
            <>
              <div className="flex h-8 items-end gap-0.5" aria-hidden>
                {Array.from({ length: 24 }, (_, i) => <span key={i} className="w-1.5 rounded-sm bg-brand-500 transition-[height] duration-75" style={{ height: `${Math.max(12, Math.min(100, rec.level * 100 * (0.5 + ((i * 37) % 10) / 10)))}%` }} />)}
              </div>
              <p className="mt-1 text-sm font-medium text-bad" role="status">Recording… {rec.seconds}s of {maxSeconds}s</p>
            </>
          ) : <p className="text-sm text-muted">{rec.recording ? `Recorded ${rec.recording.seconds}s. Listen, then transcribe.` : "Press the mic and answer out loud."}</p>}
        </div>
        <Button size="sm" onClick={() => picker.current?.click()} disabled={recording}><Upload className="size-4" /> Upload WAV</Button>
        <input ref={picker} type="file" accept=".wav,audio/wav" className="sr-only" aria-label="Upload a WAV answer"
          onChange={(e) => { const f = e.target.files?.[0]; if (f && f.size <= maxMb * 1024 ** 2) onAudio(f); e.target.value = ""; }} />
      </div>
      {rec.error && <p role="alert" className="mt-3 text-sm text-warn">{rec.error}</p>}
      {rec.recording && !recording && (
        <div className="mt-4 flex flex-wrap items-center gap-3">
          <audio controls src={rec.recording.url} className="h-9 max-w-full" />
          <Button variant="primary" size="sm" loading={busy} onClick={() => onAudio(rec.recording!.blob)}>Transcribe recording</Button>
          <Button variant="ghost" size="sm" onClick={rec.reset}><Trash2 className="size-4" /> Discard</Button>
        </div>
      )}
      <p className="mt-3 text-xs text-muted">Up to {maxSeconds} seconds and {maxMb} MB. The recording is sent to Groq for transcription only when you press Transcribe, and is never saved.</p>
    </div>
  );
}
