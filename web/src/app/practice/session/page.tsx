"use client";
import { askAssistant } from "@/lib/assistant";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ClipboardCheck } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { NoProfile } from "@/components/learn/NoProfile";
import { FeedbackPanel } from "@/components/practice/FeedbackPanel";
import { PageHeader } from "@/components/shell/PageHeader";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { Field, Textarea } from "@/components/ui/Field";
import { StepGenerating } from "@/components/ui/StepGenerating";
import { api } from "@/lib/api";
import { useProfiles, type Status } from "@/lib/profile";
import { useJob } from "@/lib/stream";
import type { Attempt, FeedbackData, PracticeFocus } from "@/lib/types";

const newId = () => crypto.randomUUID().replace(/-/g, "");

export default function Practice() {
  const { active } = useProfiles();
  const pid = active?.id;
  const client = useQueryClient();
  const { data: status } = useQuery({ queryKey: ["status"], queryFn: () => api.get<Status>("/api/status") });
  const { data: focus = [], isLoading } = useQuery({ queryKey: ["focus", pid], queryFn: () => api.get<PracticeFocus[]>(`/api/profiles/${pid}/practice/focus`), enabled: !!pid });
  const { data: attempts = [] } = useQuery({ queryKey: ["attempts", pid], queryFn: () => api.get<Attempt[]>(`/api/profiles/${pid}/practice/attempts`), enabled: !!pid });
  const [slot, setSlot] = useState("");
  const [index, setIndex] = useState(0);
  const [attempt, setAttempt] = useState(newId);
  const [flags, setFlags] = useState({ hint: false, revealed: false });
  const [text, setText] = useState("");
  const [feedback, setFeedback] = useState<FeedbackData | null>(null);
  const job = useJob<{ feedback: FeedbackData }>();
  const current = focus.find((f) => f.slot === (slot || focus[0]?.slot));
  const question = current?.questions[index];
  const done = current && index >= current.questions.length;

  function go(next: number) {
    setIndex(next); setAttempt(newId()); setFlags({ hint: false, revealed: false }); setText(""); setFeedback(null); job.reset();
  }

  async function submit() {
    const out = await job.run(`/api/profiles/${pid}/practice/answer`, { slot: current!.slot, index, attempt_id: attempt, text, ...flags });
    if (out) { setFeedback(out.feedback); client.invalidateQueries({ queryKey: ["attempts", pid] }); client.invalidateQueries({ queryKey: ["dashboard", pid] }); }
  }

  return (
    <>
      <PageHeader title="Practice" description="Answer one question at a time, then review the feedback before moving on." />
      {!pid ? <NoProfile /> : isLoading ? null : !current ? (
        <EmptyState icon={ClipboardCheck} title="Learn something to practise it" text="Generate a project or skill lesson and its practice questions will unlock here." action={<Link href="/learn/skills/"><Button variant="primary">Open Skills</Button></Link>} />
      ) : (
        <div className="space-y-6">
          <Field label="Practice focus" htmlFor="focus" className="max-w-md">
            <select id="focus" value={current.slot} onChange={(e) => { setSlot(e.target.value); go(0); }} className="h-10 w-full rounded-[var(--radius-control)] border border-line bg-surface px-3 text-sm text-ink">
              {focus.map((f) => <option key={f.slot} value={f.slot}>{f.title}</option>)}
            </select>
          </Field>
          {done ? (
            <EmptyState icon={ClipboardCheck} title="Practice session complete" text="Nice work. Revisit your attempts below, or start again to sharpen your answers." action={<Button variant="primary" onClick={() => go(0)}>Start again</Button>} />
          ) : question && (
            <Card className="space-y-5">
              <div>
                <div className="mb-2 flex items-center justify-between text-xs text-muted"><span>Question {index + 1} of {current.questions.length}</span></div>
                <div className="h-1.5 overflow-hidden rounded-full bg-slate-100"><div className="h-full rounded-full bg-brand-600 transition-[width] duration-300" style={{ width: `${(index / current.questions.length) * 100}%` }} /></div>
              </div>
              <h2 className="text-xl font-semibold text-ink">{question.question}</h2>
              {flags.hint ? <p className="rounded-[var(--radius-control)] bg-warn-tint p-3 text-sm text-body">Hint: {question.hint}</p> : !feedback && <Button size="sm" onClick={() => setFlags({ ...flags, hint: true })}>Show hint</Button>}
              {job.status === "running" ? <StepGenerating title="Reviewing your answer" steps={job.steps} running startedAt={job.startedAt} /> : !feedback ? (
                <>
                  <Field label="Your answer" htmlFor="answer" hint="Answer as you would out loud. Code is reviewed as text."><Textarea id="answer" maxLength={3500} value={text} onChange={(e) => setText(e.target.value)} className="min-h-40" /></Field>
                  {job.status === "error" && <p role="alert" className="text-sm text-bad">{job.error}</p>}
                  <div className="flex gap-2"><Button variant="primary" onClick={submit} disabled={!text.trim() || !status?.has_key}>Get feedback</Button><Button variant="ghost" onClick={() => go(index + 1)}>Skip question</Button></div>
                  {status && !status.has_key && <p className="text-xs text-warn">{askAssistant("score my answer to this question")}</p>}
                </>
              ) : (
                <>
                  <FeedbackPanel feedback={feedback} />
                  <div className="flex justify-end"><Button variant="primary" onClick={() => go(index + 1)}>Next question</Button></div>
                </>
              )}
            </Card>
          )}
        </div>
      )}
      {pid && attempts.length > 0 && (
        <section className="mt-10">
          <h2 className="mb-3 text-lg font-semibold text-ink">Attempt history</h2>
          <div className="space-y-2">
            {attempts.map((a) => (
              <details key={a.id} className="rounded-[var(--radius-card)] border border-line bg-surface">
                <summary className="cursor-pointer px-4 py-3 text-sm"><span className="font-medium text-ink">{a.question}</span><span className="ml-2 text-muted">· {a.focus} · {a.created_at.slice(0, 16)} UTC</span></summary>
                <div className="space-y-4 border-t border-line p-4"><div><p className="mb-1 text-xs font-medium uppercase tracking-wide text-muted">Your answer</p><p className="whitespace-pre-wrap text-sm">{a.answer}</p></div><FeedbackPanel feedback={a.feedback} /></div>
              </details>
            ))}
          </div>
        </section>
      )}
    </>
  );
}
