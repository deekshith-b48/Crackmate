"use client";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Pause, Play, RotateCcw, SkipForward, Trash2, Flag } from "lucide-react";
import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Checkbox, Field, Textarea } from "@/components/ui/Field";
import { ConfirmDialog } from "@/components/ui/Dialog";
import { StepGenerating } from "@/components/ui/StepGenerating";
import { useToast } from "@/components/ui/Toast";
import { api } from "@/lib/api";
import { useJob } from "@/lib/stream";
import type { InterviewOptions, InterviewView } from "@/lib/types";
import { FeedbackPanel } from "./FeedbackPanel";
import { InterviewReport } from "./InterviewReport";
import { SpeechPlayer } from "./SpeechPlayer";
import { VoiceRecorder } from "./VoiceRecorder";

export function InterviewSession({ pid, sid, hasKey, options, onDeleted }: { pid: string; sid: string; hasKey: boolean; options: InterviewOptions; onDeleted: () => void }) {
  const client = useQueryClient();
  const toast = useToast();
  const key = ["interview", pid, sid];
  const { data: session } = useQuery({ queryKey: key, queryFn: () => api.get<InterviewView>(`/api/profiles/${pid}/interviews/${sid}`) });
  const evaluating = useJob<InterviewView>();
  const [draft, setDraft] = useState("");
  const [follow, setFollow] = useState(true);
  const [busy, setBusy] = useState(false);
  const [removing, setRemoving] = useState(false);
  const turn = session?.turn;

  useEffect(() => { setDraft(turn?.confirmed || turn?.original || ""); }, [turn?.id, turn?.retries, turn?.original, turn?.confirmed]);

  const store = (next: InterviewView) => { client.setQueryData(key, next); client.invalidateQueries({ queryKey: ["interviews", pid] }); client.invalidateQueries({ queryKey: ["dashboard", pid] }); };
  async function act(action: string, body: object = {}) {
    setBusy(true);
    try { store(await api.post<InterviewView>(`/api/profiles/${pid}/interviews/${sid}/${action}`, body)); }
    catch (error) { toast("bad", error instanceof Error ? error.message : "That did not work."); }
    finally { setBusy(false); }
  }
  async function transcribe(file: Blob) {
    setBusy(true);
    try {
      const form = new FormData();
      form.append("file", file, "answer.wav");
      store(await api.post<InterviewView>(`/api/profiles/${pid}/interviews/${sid}/transcribe`, form));
      toast("good", "Transcribed. Review the text, then confirm it.");
    } catch (error) { toast("bad", error instanceof Error ? error.message : "Transcription failed. You can type your answer."); }
    finally { setBusy(false); }
  }
  async function evaluate() {
    const next = await evaluating.run(`/api/profiles/${pid}/interviews/${sid}/evaluate`);
    if (next) store(next);
  }
  async function remove() {
    try { await api.del(`/api/profiles/${pid}/interviews/${sid}?confirm=true`); client.invalidateQueries({ queryKey: ["interviews", pid] }); toast("good", "Interview deleted."); onDeleted(); }
    catch (error) { toast("bad", error instanceof Error ? error.message : "Could not delete."); }
  }

  if (!session) return null;
  const finished = session.state === "completed" || session.state === "abandoned";
  const stateLabel: Record<string, string> = { "question ready": "Ready", "transcript review": "Reviewing answer", "feedback ready": "Answered", paused: "Paused", completed: "Completed", abandoned: "Abandoned" };

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone="brand">{session.mode}</Badge><Badge>{session.difficulty}</Badge><Badge>{session.coach ? "Feedback after each answer" : "Feedback at the end"}</Badge>
        <Badge tone={finished ? "neutral" : "good"}>{stateLabel[session.state] ?? session.state}</Badge>
        <div className="ml-auto flex gap-1">
          {!finished && session.state !== "paused" && <Button variant="ghost" size="sm" onClick={() => act("pause")} disabled={busy}><Pause className="size-4" /> Pause</Button>}
          {!finished && <Button variant="ghost" size="sm" onClick={() => act("end")} disabled={busy}><Flag className="size-4" /> End and view report</Button>}
          <Button variant="ghost" size="sm" onClick={() => setRemoving(true)} aria-label="Delete interview"><Trash2 className="size-4" /></Button>
        </div>
      </div>

      {finished ? <InterviewReport pid={pid} sid={sid} /> : session.state === "paused" ? (
        <Card className="text-center"><p className="mb-4 text-muted">Paused. Your confirmed answers are saved.</p><Button variant="primary" onClick={() => act("resume")}><Play className="size-4" /> Resume interview</Button></Card>
      ) : turn && (
        <Card className="space-y-5">
          <div>
            <p className="mb-2 text-xs text-muted">Question {session.index + 1} of {session.budget}{turn.depth > 0 && " · adaptive follow-up"}</p>
            <div className="h-1.5 overflow-hidden rounded-full bg-slate-100"><div className="h-full rounded-full bg-brand-600 transition-[width] duration-300" style={{ width: `${(session.index / session.budget) * 100}%` }} /></div>
          </div>
          <h2 className="text-xl font-semibold text-ink">{turn.question}</h2>
          <p className="-mt-3 text-xs text-muted">Generated practice question. Follow-ups replace the next planned question and count toward the budget.</p>
          {session.spoken && <SpeechPlayer text={turn.question} />}

          {session.state !== "feedback ready" ? (
            <>
              {turn.hint ? <p className="rounded-[var(--radius-control)] bg-warn-tint p-3 text-sm text-body">{turn.hint}</p> : <Button size="sm" onClick={() => act("hint")} disabled={busy}>Clarify this question</Button>}
              <VoiceRecorder maxSeconds={options.audio_seconds} maxMb={options.audio_mb} busy={busy} onAudio={transcribe} />
              <Field label="Review the transcript, or type your answer" htmlFor="answer" hint="Include an outline or code here if it helps. Code is reviewed as text.">
                <Textarea id="answer" maxLength={3500} value={draft} onChange={(e) => setDraft(e.target.value)} className="min-h-40" />
              </Field>
              {turn.original && <details className="text-sm"><summary className="cursor-pointer text-muted">Original speech transcript</summary><p className="mt-2 whitespace-pre-wrap">{turn.original}</p></details>}
              {evaluating.status === "running" && <StepGenerating title="Evaluating your confirmed answer" steps={evaluating.steps} running startedAt={evaluating.startedAt} />}
              {evaluating.status === "error" && <p role="alert" className="text-sm text-bad">{evaluating.error}</p>}
              <div className="flex flex-wrap items-center gap-2">
                <Button variant="primary" onClick={() => act("confirm", { text: draft })} disabled={!draft.trim() || busy}>Confirm answer</Button>
                {turn.confirmed && <Button variant="primary" onClick={evaluate} loading={evaluating.status === "running"} disabled={!hasKey}>Evaluate confirmed answer</Button>}
                <Button variant="ghost" onClick={() => act("idk")} disabled={busy}>I don’t know</Button>
                <Button variant="ghost" onClick={() => act("skip")} disabled={busy}><SkipForward className="size-4" /> Skip</Button>
              </div>
              {turn.confirmed && <p className="text-sm text-good" role="status">Confirmed answer saved. Ready to evaluate.</p>}
            </>
          ) : (
            <>
              {session.coach && turn.feedback ? (
                <>
                  <FeedbackPanel feedback={turn.feedback} />
                  <Button size="sm" onClick={() => act("retry")} disabled={busy}><RotateCcw className="size-4" /> Retry this question</Button>
                </>
              ) : (
                <>
                  <p className="text-sm text-good">Answer saved. Feedback will appear when the interview ends.</p>
                  {!session.coach && <Button size="sm" onClick={() => act("coach")} disabled={busy}>Reveal feedback now and switch to coach mode</Button>}
                </>
              )}
              <Checkbox checked={follow && turn.can_follow_up} disabled={!turn.can_follow_up} onChange={(e) => setFollow(e.target.checked)} label="Use an adaptive follow-up next" />
              <div className="flex justify-end"><Button variant="primary" onClick={() => act("next", { follow: follow && turn.can_follow_up })} disabled={busy}>{session.index + 1 >= session.budget ? "Finish interview" : "Next question"}</Button></div>
            </>
          )}
        </Card>
      )}
      <ConfirmDialog open={removing} onClose={() => setRemoving(false)} onConfirm={remove} title="Permanently delete this interview?" text="This removes the interview and its confirmed answers. It cannot be undone." confirmLabel="Delete interview" />
    </div>
  );
}
