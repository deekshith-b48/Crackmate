"use client";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { AnimatePresence, motion } from "framer-motion";
import { ChevronDown, Eye, Lightbulb, Mic, Sparkles } from "lucide-react";
import { useState, type KeyboardEvent } from "react";
import { DifficultyBadge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Markdown } from "@/components/ui/Markdown";
import { StepGenerating } from "@/components/ui/StepGenerating";
import { useToast } from "@/components/ui/Toast";
import { api } from "@/lib/api";
import { cn } from "@/lib/cn";
import { useJob } from "@/lib/stream";
import type { LadderStep } from "@/lib/types";

const GRADES = [["Again", "1", "Bring it back today"], ["Hard", "2", "Back soon"], ["Good", "3", "Back in a few days"], ["Easy", "4", "Back much later"]] as const;
const LEVEL_LABEL: Record<string, string> = { why: "Why", how: "How", what_if_it_fails: "What if it fails", how_does_it_scale: "How does it scale" };

type Props = {
  pid: string; slot: string; question: string; answer: string; hint: string;
  position?: number; total?: number; autoFocus?: boolean; onRated?: () => void;
};

/**
 * Active recall: the answer starts hidden. Space reveals it, 1-4 rates it (Again, Hard, Good, Easy)
 * and the rating schedules the next review with SM-2. The card must be focused for shortcuts.
 */
export function QuestionCard({ pid, slot, question, answer, hint, position = 0, total = 1, autoFocus, onRated }: Props) {
  const [revealed, setRevealed] = useState(false);
  const [showHint, setShowHint] = useState(false);
  const [result, setResult] = useState("");
  const toast = useToast();
  const client = useQueryClient();

  async function rate(grade: string) {
    try {
      const out = await api.post<{ message: string }>(`/api/profiles/${pid}/reviews/rate`, { slot, question, answer, hint, grade });
      setResult(out.message);
      client.invalidateQueries({ queryKey: ["dashboard", pid] });
      client.invalidateQueries({ queryKey: ["due", pid] });
      onRated?.();
    } catch (error) {
      toast("bad", error instanceof Error ? error.message : "Could not save your rating.");
    }
  }

  function onKeyDown(e: KeyboardEvent<HTMLDivElement>) {
    if ((e.target as HTMLElement).closest("button, input, textarea, a")) return; // never steal keys from controls
    if (e.key === " ") { e.preventDefault(); setRevealed(true); }
    if (revealed && !result && ["1", "2", "3", "4"].includes(e.key)) rate(GRADES[Number(e.key) - 1][0]);
  }

  return (
    <div
      tabIndex={0}
      autoFocus={autoFocus}
      onKeyDown={onKeyDown}
      aria-label={`Question: ${question}`}
      className="rounded-[var(--radius-card)] border border-line bg-surface p-5 outline-none focus-visible:border-brand-500 focus-visible:ring-2 focus-visible:ring-brand-100"
    >
      <div className="flex items-start gap-3">
        {total > 1 && <DifficultyBadge position={position} total={total} />}
        <p className="flex-1 font-medium text-ink">{question}</p>
      </div>

      {hint && !revealed && (
        <div className="mt-3">
          {showHint ? <p className="flex gap-2 text-sm text-muted"><Lightbulb className="mt-0.5 size-4 shrink-0 text-warn" />{hint}</p>
            : <button onClick={() => setShowHint(true)} className="text-sm text-muted underline-offset-2 hover:text-ink hover:underline">Need a nudge? Show a hint</button>}
        </div>
      )}

      {!revealed && (
        <div className="mt-4 flex items-center gap-3">
          <Button variant="primary" size="sm" onClick={() => setRevealed(true)}><Eye className="size-4" /> Show answer</Button>
          <span className="text-xs text-muted">or press <kbd className="rounded border border-line bg-slate-50 px-1.5 font-mono text-[11px]">Space</kbd></span>
        </div>
      )}

      <AnimatePresence>
        {revealed && (
          <motion.div initial={{ opacity: 0, rotateX: -80, y: -8 }} animate={{ opacity: 1, rotateX: 0, y: 0 }} transition={{ duration: 0.28, ease: "easeOut" }} style={{ transformPerspective: 800, transformOrigin: "top" }} className="mt-4 border-t border-line pt-4">
            <p className="mb-1 text-xs font-medium uppercase tracking-wide text-muted">Spoken answer</p>
            <Markdown>{answer}</Markdown>
            <Ladder pid={pid} slot={slot} question={question} answer={answer} />
            <div className="mt-5">
              {result ? <p className="text-sm font-medium text-good" role="status">{result}</p> : (
                <>
                  <p className="mb-2 text-xs text-muted">How well did you recall it? Press 1 to 4.</p>
                  <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                    {GRADES.map(([grade, key, note]) => (
                      <button key={grade} onClick={() => rate(grade)} title={note}
                        className={cn("flex flex-col items-center rounded-[var(--radius-control)] border px-3 py-2 text-sm font-medium transition-colors duration-150",
                          grade === "Again" ? "border-red-200 text-bad hover:bg-bad-tint" : grade === "Hard" ? "border-amber-200 text-warn hover:bg-warn-tint" : grade === "Good" ? "border-brand-200 text-brand-700 hover:bg-brand-50" : "border-green-200 text-good hover:bg-good-tint")}>
                        {grade}<span className="font-mono text-[11px] font-normal opacity-60">{key}</span>
                      </button>
                    ))}
                  </div>
                </>
              )}
              <a href="/practice/interview/" className="mt-3 inline-flex items-center gap-1.5 text-xs text-muted hover:text-brand-600"><Mic className="size-3.5" /> Say it aloud in the Interview Room</a>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

function Ladder({ pid, slot, question, answer }: { pid: string; slot: string; question: string; answer: string }) {
  const body = { slot, question, answer };
  const key = ["ladder", pid, slot, question];
  const client = useQueryClient();
  const saved = useQuery({ queryKey: key, queryFn: () => api.post<{ status: string; steps: LadderStep[] | null }>(`/api/profiles/${pid}/ladder/lookup`, body) });
  const job = useJob<{ status: string; steps: LadderStep[] | null }>();
  const [open, setOpen] = useState<number | null>(null);
  const steps = saved.data?.steps;

  async function build() {
    const out = await job.run(`/api/profiles/${pid}/ladder/build`, body);
    if (out) client.setQueryData(key, out);
  }

  if (job.status === "running") return <div className="mt-4"><StepGenerating title="Building follow-ups" steps={job.steps} running startedAt={job.startedAt} /></div>;
  if (!steps) {
    return (
      <div className="mt-4">
        <Button size="sm" onClick={build}><Sparkles className="size-4" /> Build follow-up ladder</Button>
        {job.status === "error" && <p role="alert" className="mt-2 text-sm text-bad">{job.error}</p>}
      </div>
    );
  }
  return (
    <div className="mt-4">
      <p className="mb-2 text-xs font-medium uppercase tracking-wide text-muted">Follow-up ladder · most likely, never guaranteed</p>
      <div className="space-y-1.5">
        {steps.map((step, index) => (
          <div key={step.level} className="rounded-[var(--radius-control)] border border-line">
            <button onClick={() => setOpen(open === index ? null : index)} className="flex w-full items-center gap-3 px-3 py-2 text-left text-sm" aria-expanded={open === index}>
              <span className="flex size-5 shrink-0 items-center justify-center rounded-full bg-brand-50 text-[11px] font-semibold text-brand-700">{index + 1}</span>
              <span className="flex-1"><span className="font-medium text-ink">{LEVEL_LABEL[step.level] ?? step.level}:</span> {step.question}</span>
              <ChevronDown className={cn("size-4 text-muted transition-transform duration-150", open === index && "rotate-180")} />
            </button>
            {open === index && <div className="border-t border-line px-3 py-2"><Markdown>{step.answer}</Markdown></div>}
          </div>
        ))}
      </div>
    </div>
  );
}
