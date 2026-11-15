"use client";
import { Check, Compass, Lightbulb, MessageCircleQuestion } from "lucide-react";
import { useState } from "react";
import { Markdown } from "@/components/ui/Markdown";
import { cn } from "@/lib/cn";
import type { FeedbackData } from "@/lib/types";

const tone = (score: number) => (score >= 3 ? "bg-good" : score === 2 ? "bg-warn" : "bg-bad");

/** Scores, what was right, what to work on, a better answer, and the follow-up an interviewer might ask. */
export function FeedbackPanel({ feedback }: { feedback: FeedbackData }) {
  const [sources, setSources] = useState(false);
  return (
    <div className="space-y-5">
      <div className="grid gap-3 sm:grid-cols-2">
        {feedback.scores.map((s) => (
          <div key={s.key} className="rounded-[var(--radius-control)] border border-line p-3">
            <div className="mb-1.5 flex items-center justify-between text-sm"><span className="font-medium text-ink">{s.label}</span><span className="font-mono text-xs text-muted">{s.score}/4</span></div>
            <div className="mb-2 h-1.5 overflow-hidden rounded-full bg-slate-100"><div className={cn("h-full rounded-full transition-[width] duration-500", tone(s.score))} style={{ width: `${(s.score / 4) * 100}%` }} /></div>
            <p className="text-xs leading-relaxed text-muted">{s.reason}</p>
          </div>
        ))}
      </div>
      <p className="text-xs text-muted">Coaching estimates on a 0–4 scale. {feedback.scale}</p>
      <Block icon={Check} title="What was correct" body={feedback.correct} />
      <Block icon={Compass} title="What to work on" body={feedback.missing} />
      <Block icon={Lightbulb} title="A better way to say it" body={feedback.corrected} />
      <Block icon={MessageCircleQuestion} title="Follow-up an interviewer might ask" body={feedback.follow_up} />
      <button onClick={() => setSources(!sources)} className="text-sm text-muted underline-offset-2 hover:text-ink hover:underline" aria-expanded={sources}>Sources and evidence</button>
      {sources && <Markdown>{feedback.evidence_note}</Markdown>}
    </div>
  );
}

function Block({ icon: Icon, title, body }: { icon: typeof Check; title: string; body: string }) {
  return (
    <div className="flex gap-3">
      <div className="mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-full bg-brand-50 text-brand-600"><Icon className="size-4" aria-hidden /></div>
      <div><p className="font-medium text-ink">{title}</p><Markdown>{body}</Markdown></div>
    </div>
  );
}
