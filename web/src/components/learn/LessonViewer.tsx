"use client";
import { AlertTriangle, BookMarked } from "lucide-react";
import { useState } from "react";
import { Markdown } from "@/components/ui/Markdown";
import type { LessonView } from "@/lib/types";
import { QuestionCard } from "./QuestionCard";

/** A lesson laid out for reading: concept first, then your project, then the questions to answer out loud. */
export function LessonViewer({ pid, lesson }: { pid: string; lesson: LessonView }) {
  const [showSources, setShowSources] = useState(false);
  return (
    <article className="space-y-8">
      {lesson.sections.map((section) => (
        <section key={section.label}>
          <h3 className="mb-2 text-lg font-semibold text-ink">{section.label}</h3>
          <Markdown>{section.body}</Markdown>
        </section>
      ))}

      <section>
        <h3 className="mb-1 text-lg font-semibold text-ink">Practice questions</h3>
        <p className="mb-4 text-sm text-muted">Try answering out loud first. Press Space on a card to reveal the answer.</p>
        <div className="space-y-3">
          {lesson.questions.map((q, i) => (
            <QuestionCard key={q.qid + i} pid={pid} slot={lesson.slot} question={q.question} answer={q.answer} hint={q.hint} position={i} total={lesson.questions.length} />
          ))}
        </div>
      </section>

      {lesson.follow_ups.length > 0 && (
        <section>
          <h3 className="mb-4 text-lg font-semibold text-ink">Deeper follow-ups</h3>
          <div className="space-y-3">
            {lesson.follow_ups.map((q, i) => <QuestionCard key={q.qid + i} pid={pid} slot={lesson.slot} question={q.question} answer={q.answer} hint={q.hint} />)}
          </div>
        </section>
      )}

      <section>
        <h3 className="mb-2 text-lg font-semibold text-ink">Self-check</h3>
        <Markdown>{lesson.exercise}</Markdown>
      </section>

      {lesson.assumptions && (
        <div className="flex gap-3 rounded-[var(--radius-card)] border border-amber-200 bg-warn-tint p-4">
          <AlertTriangle className="mt-0.5 size-5 shrink-0 text-warn" aria-hidden />
          <div><p className="mb-1 font-medium text-ink">Assumptions and missing information</p><Markdown>{lesson.assumptions}</Markdown></div>
        </div>
      )}

      <section>
        <button onClick={() => setShowSources(!showSources)} className="flex items-center gap-2 text-sm font-medium text-muted hover:text-ink" aria-expanded={showSources}>
          <BookMarked className="size-4" /> Sources and evidence ({lesson.passages.length})
        </button>
        {showSources && (
          <div className="mt-3 space-y-3">
            <Markdown>{lesson.evidence_note}</Markdown>
            {lesson.passages.map((p) => (
              <details key={p.id} className="rounded-[var(--radius-control)] border border-line px-3 py-2 text-sm">
                <summary className="cursor-pointer font-medium text-ink">{p.title}</summary>
                <p className="mt-1 break-all text-xs text-muted">{p.location}{p.license ? ` · ${p.license}` : ""}</p>
                <p className="mt-2 whitespace-pre-wrap text-body">{p.text}</p>
              </details>
            ))}
          </div>
        )}
      </section>
    </article>
  );
}
